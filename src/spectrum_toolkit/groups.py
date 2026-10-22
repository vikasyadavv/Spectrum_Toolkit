"""Groups: which sample or class each spectrum belongs to (e.g. CV, MB, RhB).

Groups are stored with the data, one label per spectrum (``c.groups``), and
follow the spectra through every step (trim, despike, baseline, select ...).
Plots use them (one colour, one mean or one panel per group), and later
analyses (PCA) will too.

- ``set_groups(c, ...)``   say which group each spectrum belongs to, in one of
  five ways (see below). Nothing is ever guessed silently.
- ``suggest_groups(c)``    propose groups from the files or the names, with
  the reason, for the user to confirm; it sets nothing.
- ``by_group(c)``          one collection per group.

The same are available as methods: ``c.set_groups(...)``, ``c.suggest_groups()``,
``c.by_group()``.

>>> from spectrum_toolkit import SpectrumCollection
>>> c = SpectrumCollection([1, 2], [[1, 1], [2, 2], [3, 3]], names=["CV 1", "CV 2", "MB 1"])
>>> c.set_groups("name").groups
('CV', 'CV', 'MB')
>>> c.set_groups({"A": [0], "B": [1, 2]}).groups
('A', 'B', 'B')
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .core import Spectrum, SpectrumCollection

# How a spectrum in no group is shown in plots and counts.
NO_GROUP = "(no group)"

# Words that number measurements rather than name a sample: "Spectrum 3",
# "Spot2" or "Scan 12" say nothing about which sample it is.
_GENERIC = {"spectrum", "spectra", "spot", "point", "scan", "measurement", "acquisition", "frame", "pixel",
            "sample", "column", "run", "repeat", "rep", "accumulation", "acc", "s", "spec", "data", "file", "no"}

_FORMS = ('give groups as a dict of spectrum numbers or names, e.g. {"CV": range(0, 14), "MB": [14, 15]}; '
          'a list with one label per spectrum; "name" (from the names, e.g. "CV 1" -> CV); '
          '"file" (the file each spectrum came from); or pattern=r"..." (the part of the name in brackets)')


# ------------------------------------------------------------------ helpers
def _name_group(name: str) -> str:
    """The group a name points to: the name without its running number and generic words.

    "CV 1", "CV_2", "CV-3" -> "CV"; "CV10-4M: Spectrum 1" -> "CV10-4M";
    "Spectrum 1", "Spot2" -> "" (they say nothing about the sample).
    """
    text = name.strip()
    for _ in range(3):                                           # "CV: Spectrum 1 (2)" needs a few rounds
        before = text
        text = re.sub(r"[\s_\-.#:(]*\d+\)?$", "", text)          # the running number at the end
        words = re.split(r"[\s_\-:]+", text)
        if words and words[-1].lower() in _GENERIC:              # a generic last word: drop it
            text = text[: len(text) - len(words[-1])]
        text = text.rstrip(" _-.#:(")
        if text == before:
            break
    return text if text.lower() not in _GENERIC else ""


def _from_names(c: SpectrumCollection) -> list[str]:
    """Groups from the names, refused when the names do not show groups."""
    labels = [_name_group(n) for n in c.names]
    found = [g for g in labels if g]
    if not found:
        raise ValueError(f"The names do not show groups (they look like {c.names[0]!r}, {c.names[-1]!r}); "
                         f"give them another way: {_FORMS}.")
    if len(c) > 1 and len(set(found)) == len(c):
        raise ValueError(f"Every spectrum would be its own group (names such as {c.names[0]!r}, {c.names[1]!r}); "
                         f"give the groups another way: {_FORMS}.")
    return labels


def _sources(c: SpectrumCollection) -> list[str] | None:
    """The file each spectrum came from (without folder and extension), or None when not known."""
    sources = c.meta.get("sources")                              # set by combine, one per spectrum
    if isinstance(sources, (list, tuple)) and len(sources) == len(c) and all(sources):
        return [Path(s).stem for s in sources]
    if c.meta.get("source"):                                     # loaded from one file
        return [Path(c.meta["source"]).stem] * len(c)
    return None


def _from_dict(c: SpectrumCollection, groups: dict) -> list[str]:
    """Groups from {"CV": range(0, 14), "MB": [14, "MB 2"], ...}: numbers (0 = first) or names."""
    labels = [""] * len(c)
    for group, members in groups.items():
        if isinstance(members, (int, str)) and not isinstance(members, bool):
            members = [members]
        for m in members:
            if isinstance(m, str):
                if m not in c.names:
                    raise ValueError(f"Group {group!r}: no spectrum named {m!r}.")
                k = c.names.index(m)
            elif isinstance(m, int) and not isinstance(m, bool):
                if not 0 <= m < len(c):
                    raise ValueError(f"Group {group!r}: spectrum number {m} does not exist; "
                                     f"there are {len(c)} (0 to {len(c) - 1}).")
                k = m
            else:
                raise ValueError(f"Group {group!r}: {m!r} is not a spectrum number or name.")
            if labels[k] and labels[k] != str(group):
                raise ValueError(f"Spectrum {k} ({c.names[k]!r}) is in two groups: {labels[k]!r} and {group!r}.")
            labels[k] = str(group)
    return labels


def _counts(labels) -> dict:
    """How many spectra each group has, in the order the groups first appear."""
    counts: dict[str, int] = {}
    for g in labels:
        counts[g or NO_GROUP] = counts.get(g or NO_GROUP, 0) + 1
    return counts


# ------------------------------------------------------------------ public
def set_groups(c: SpectrumCollection, groups: Any = None, *, pattern: str | None = None,
               rename: dict | None = None) -> SpectrumCollection:
    """Say which group (sample, class) each spectrum belongs to.

    Parameters
    ----------
    c : the collection.
    groups : one of
        - a dict of spectrum numbers (0 = first) or names per group:
          ``{"CV": range(0, 14), "MB": range(14, 19), "RhB": [19, 20, "Spot 3"]}``;
          spectra not listed are in no group;
        - a list with one label per spectrum: ``["CV", "CV", "MB", ...]``
          ("" or None for no group);
        - "name": from the names, without the running number and words such
          as "Spectrum" or "Spot": "CV 1", "CV_2" -> CV. Refused when the
          names do not show groups ("Spectrum 1", "Spot2");
        - "file": the file each spectrum came from (after ``combine`` of
          several files, or ``load`` of one);
        - None (with no pattern): remove the groups.
    pattern : a regular expression applied to each name instead; the part in
        brackets is the group: ``pattern=r"^(\\w+)_"`` on "CV_spot1" gives CV.
        A name it does not match is in no group.
    rename : new names for groups, e.g. {"CV10-4M": "CV"}.

    Returns a new collection; ``c`` is unchanged. Setting groups is not a
    processing step, so it is not added to the history.
    """
    if isinstance(c, Spectrum):
        raise ValueError('One spectrum has one group: use s.copy_with(group="CV").')
    if not isinstance(c, SpectrumCollection):
        raise TypeError(f"set_groups needs a SpectrumCollection, got {type(c).__name__}.")
    if pattern is not None:
        if groups is not None:
            raise ValueError("Give groups or pattern, not both.")
        try:
            rule = re.compile(pattern)
        except re.error as e:
            raise ValueError(f"pattern {pattern!r} is not a valid regular expression: {e}.") from None
        labels = []
        for n in c.names:
            m = rule.search(n)
            labels.append("" if not m else (m.group(1) if rule.groups else m.group(0)) or "")
        if not any(labels):
            raise ValueError(f"pattern {pattern!r} matches none of the names (e.g. {c.names[0]!r}).")
    elif groups is None:
        return c.copy_with(groups=())
    elif isinstance(groups, str):
        if groups == "name":
            labels = _from_names(c)
        elif groups == "file":
            labels = _sources(c)
            if labels is None:
                raise ValueError("It is not known which file each spectrum came from; load the files with "
                                 "stk.load or stk.combine, or give the groups another way.")
        else:
            raise ValueError(f"Unknown groups {groups!r}: {_FORMS}.")
    elif isinstance(groups, dict):
        labels = _from_dict(c, groups)
    elif isinstance(groups, (list, tuple)):
        if len(groups) != len(c):
            raise ValueError(f"Got {len(groups)} group labels for {len(c)} spectra; give one per spectrum.")
        labels = ["" if g is None else str(g) for g in groups]
    else:
        raise ValueError(f"Cannot read groups {groups!r}: {_FORMS}.")
    if rename:
        labels = [str(rename.get(g, g)) if g else g for g in labels]
    return c.copy_with(groups=tuple(labels))


def suggest_groups(c: SpectrumCollection) -> dict:
    """Propose groups, with the reason, for the user to confirm or change; nothing is set.

    Several files give one group per file; otherwise names that show groups
    ("CV 1", "MB 2") give one group per name. Names that only number the
    spectra ("Spectrum 1", "Spot2") give no proposal.

    Returns {"by": "file", "name" or None, "groups": one label per spectrum
    or None, "counts": {group: number of spectra}, "message": plain text}.
    Apply a proposal with ``c.set_groups(proposal["groups"])``.
    """
    files = _sources(c)
    if files and len(set(files)) > 1:
        counts = _counts(files)
        listed = ", ".join(f"{g} ({n})" for g, n in counts.items())
        return {"by": "file", "groups": files, "counts": counts,
                "message": f"One group per file: {listed}. Use these, or rename them?"}
    try:
        labels = _from_names(c)
    except ValueError:
        return {"by": None, "groups": None, "counts": {},
                "message": f"The names (e.g. {c.names[0]!r}) do not show which sample each spectrum is. "
                           "Are they one group or several? Give the groups by spectrum numbers, "
                           'e.g. {"CV": range(0, 14), "MB": range(14, 19)}, or by file.'}
    counts = _counts(labels)
    listed = ", ".join(f"{g} ({n})" for g, n in counts.items())
    one = len([g for g in counts if g != NO_GROUP]) == 1
    return {"by": "name", "groups": labels, "counts": counts,
            "message": (f"From the names, all spectra look like one group: {listed}." if one
                        else f"From the names: {listed}.") + " Use these, or change them?"}


def by_group(c: SpectrumCollection) -> dict:
    """One collection per group, in the order the groups first appear.

    Spectra in no group come under "(no group)". The history is unchanged
    (splitting by group is not a processing step).
    """
    if not isinstance(c, SpectrumCollection) or not c.groups:
        raise ValueError("These spectra have no groups yet; set them with set_groups "
                         "(suggest_groups proposes some).")
    out = {}
    for g in dict.fromkeys(c.groups):
        rows = [k for k, label in enumerate(c.groups) if label == g]
        out[g or NO_GROUP] = c.copy_with(Y=c.Y[rows], names=tuple(c.names[k] for k in rows),
                                         positions=None if c.positions is None else c.positions[rows],
                                         groups=tuple(c.groups[k] for k in rows))
    return out


__all__ = ["set_groups", "suggest_groups", "by_group", "NO_GROUP"]
