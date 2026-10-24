"""About the data: what a data set is, where it came from and what was done to it.

``about(data)`` gives labelled lines in five sections, the same in Python and
on the website (the service sends them with every data answer as "about"):

- **file**: the file's name and type;
- **data**: worked out from the numbers: spectra, points, the x range and
  step, the intensity range, missing points, the map grid and the groups;
- **measurement**: what the instrument file says, with the same labels for
  every file type (Instrument, Software, Title, Type, Laser, Accumulations,
  Started, Took, Operator, Mode, Sheet, Variables); only the lines the file has;
- **settings**: every other instrument setting (a Shimadzu method, EnSpectr
  experiment settings), "Section › name" -> value;
- **notes**: what was assumed while reading the file;
- **history**: each processing step with its settings, or "Nothing yet: the
  data as read.".

Each section (but file, notes and history) is a list of [label, value] pairs
with values as text, ready to show. "text" has everything as plain text, for
copying into a lab notebook.

Data processed on the service arrives without its file's details; when it
brings its earlier "about" along (``meta["about"]``), the file, measurement,
settings and notes are taken from there, while the facts and the steps are
always worked out from the data as it is now.

Example:
    >>> import spectrum_toolkit as stk
    >>> info = stk.about(stk.example())
    >>> info["data"][0]
    ['Spectra', '3']
    >>> info["history"]
    ['Nothing yet: the data as read.']
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from .core import Spectrum, SpectrumCollection

# The name of each file type, as people know it (meta["file_type"] from the readers); the file's own
# extension follows it, e.g. "Renishaw WiRE (.wdf)", "Text (.esp)".
FILE_TYPES = {"wdf": "Renishaw WiRE", "shimadzu": "Shimadzu UVProbe", "matlab": "MATLAB",
              "spreadsheet": "Spreadsheet", "text": "Text", "example": "Example spectra (made up)"}
# y units that are only a unit, so the label says "Intensity (counts)" rather than just "counts".
_PLAIN_Y_UNITS = {"counts", "count", "cts", "a.u.", "au", "arb. units", "arbitrary units", "cps"}
NOTHING_DONE = "Nothing yet: the data as read."


def _nice(v: float, digits: int = 5) -> str:
    """A number as short text: at most `digits` significant digits, no exponent for everyday sizes."""
    if v is None or not np.isfinite(v):
        return "–"
    text = f"{v:.{digits}g}"
    if "e" in text and 1e-4 <= abs(v) < 1e15:                     # e.g. 1.2e+04 -> 12000
        text = f"{v:.{max(0, digits - 1 - int(np.floor(np.log10(abs(v)))))}f}"
    return text


def _x_label(unit: str) -> str:
    """The label of the x range: the unit when it describes the axis ("Raman shift (cm⁻¹)"), else x (unit)."""
    if not unit:
        return "x"
    return unit if "(" in unit or " " in unit else f"x ({unit})"


def _y_label(unit: str) -> str:
    """The label of the intensity range: "Intensity (counts)", "Absorbance", or y (unit) for other names."""
    if not unit:
        return "Intensity"
    if unit.lower() in _PLAIN_Y_UNITS:
        return f"Intensity ({unit})"
    return unit if unit[0].isupper() and len(unit) > 3 else f"y ({unit})"


def _when(text: str) -> str:
    """An ISO time ("2023-11-22T08:55:48Z") as "22 Nov 2023, 08:55 UTC"."""
    try:
        t = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return str(text)
    return t.strftime("%d %b %Y, %H:%M") + (" UTC" if str(text).endswith("Z") else "")


def _took(start: str, end: str) -> str | None:
    """The time between two ISO times as "36 min 52 s" (None when either is missing or unreadable)."""
    try:
        a, b = (datetime.fromisoformat(str(t).replace("Z", "+00:00")) for t in (start, end))
    except (TypeError, ValueError):
        return None
    s = int(round((b - a).total_seconds()))
    if s < 0:
        return None
    h, m, s = s // 3600, s % 3600 // 60, s % 60
    return " ".join(p for p in (f"{h} h" if h else "", f"{m} min" if m else "", f"{s} s" if s or not (h or m) else "") if p)


def _data_lines(x: np.ndarray, Y: np.ndarray, x_unit: str, y_unit: str, meta: dict, positions, groups) -> list:
    """The facts worked out from the numbers."""
    lines = [["Spectra", str(Y.shape[0])], ["Points each", str(x.size)]]
    lines.append([_x_label(x_unit), f"{_nice(np.nanmin(x))} – {_nice(np.nanmax(x))}" if x.size else "–"])
    steps = np.abs(np.diff(np.sort(x)))
    steps = steps[steps > 0]
    if steps.size:
        mid, lo, hi = float(np.median(steps)), float(steps.min()), float(steps.max())
        even = hi - lo <= 0.01 * mid                                  # within 1 %: an even step
        lines.append(["Step", _nice(mid, 3) if even else f"{_nice(mid, 3)} ({_nice(lo, 3)} – {_nice(hi, 3)})"])
    else:
        lines.append(["Step", "–"])
    finite = Y[np.isfinite(Y)]
    lines.append([_y_label(y_unit), f"{_nice(finite.min())} – {_nice(finite.max())}" if finite.size else "–"])
    missing = int(Y.size - finite.size)
    lines.append(["Missing points", "none" if not missing else f"{missing} of {Y.size}"])
    grid = meta.get("map") if isinstance(meta.get("map"), dict) else None
    if grid and grid.get("points"):
        n = [int(p) for p in grid["points"] if int(p) > 1] or [1]       # leave out directions with 1 point
        step = [abs(float(s)) for p, s in zip(grid["points"], grid.get("step") or []) if int(p) > 1]
        unit = " µm" if any("µm" in str(label) for label in meta.get("position_labels") or []) else ""
        text = " × ".join(map(str, n)) + (f", step {' × '.join(_nice(s, 3) for s in step)}{unit}" if step else "")
        lines.append(["Map", text])
    elif positions is not None and len(positions):
        lines.append(["Map", f"{len(positions)} positions"])
    else:
        lines.append(["Map", "no"])
    if groups:
        counts: dict = {}
        for g in groups:
            counts[g or "(no group)"] = counts.get(g or "(no group)", 0) + 1
        lines.append(["Groups", f"{len(counts)}: " + ", ".join(f"{g} ({n})" for g, n in counts.items())])
    else:
        lines.append(["Groups", "none"])
    return lines


def _measurement_lines(meta: dict) -> list:
    """What the file says about the measurement, with the same labels for every file type."""
    lines = []

    def add(label, value):
        if value not in (None, "", [], {}):
            lines.append([label, str(value)])

    add("Instrument", meta.get("instrument"))
    add("Software", meta.get("software"))
    add("Title", meta.get("title"))
    kind = str(meta.get("measurement") or "")                     # "single", "series" or "map" (.wdf)
    if kind:
        add("Type", kind.capitalize() + (f", {meta['scan']} scan" if meta.get("scan") else ""))
    if meta.get("laser_nm"):
        add("Laser", f"{_nice(float(meta['laser_nm']))} nm")
    add("Accumulations", meta.get("accumulations"))
    if meta.get("start"):
        add("Started", _when(meta["start"]))
        add("Took", _took(meta["start"], meta.get("end")))
    add("Operator", meta.get("operator"))
    add("Mode", meta.get("measuring_mode"))
    if meta.get("sheet"):
        sheets = meta.get("sheets") or []
        add("Sheet", str(meta["sheet"]) + (f" (of {len(sheets)})" if len(sheets) > 1 else ""))
    chosen = (meta.get("variables") or {}).get("chosen") if isinstance(meta.get("variables"), dict) else None
    if chosen:
        add("Variables", ", ".join(f"{k} = {v}" for k, v in chosen.items() if v))
    return lines


def _flatten(d: Any, prefix: str = "") -> list:
    """A nested dict of settings as ["Section › name", value] lines (empty values left out)."""
    out = []
    for k, v in (d or {}).items():
        name = f"{prefix} › {k}" if prefix else str(k)
        if isinstance(v, dict):
            out += _flatten(v, name)
        elif v not in (None, "", [], {}):
            out.append([name, v if isinstance(v, str) else _nice(v, 8) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)])
    return out


def _setting_lines(meta: dict) -> list:
    """Every other instrument setting: a Shimadzu method, the settings lines of a text file (.esp)."""
    lines = _flatten(meta.get("method"))
    lines += _flatten(meta.get("metadata"))
    return lines


def _step_text(step: dict) -> str:
    """One processing step as "baseline: airpls (lam 1e+06, max_iter 50, tol 0.001)"."""
    settings = []
    for k, v in step.items():
        if k in ("step", "method"):
            continue
        if k == "spikes" and isinstance(v, dict):                     # despike: which spikes went, as a count
            n = sum(len(s) for s in v.values())
            settings.append(f"{n} spike{'s' if n != 1 else ''} in {len(v)} spectr{'a' if len(v) != 1 else 'um'}")
        elif isinstance(v, (list, tuple, dict)) and len(v) > 4:
            settings.append(f"{k} ({len(v)} values)")
        else:
            settings.append(f"{k} {_nice(v) if isinstance(v, float) else v}")
    name = str(step.get("step", "step")) + (f": {step['method']}" if step.get("method") else "")
    return name + (f" ({', '.join(settings)})" if settings else "")


def _as_text(info: dict) -> str:
    """Everything as plain text, for copying."""
    out = ["About the data"]
    if info["file"]:
        out.append(f"File: {info['file']['name']} · {info['file']['type']}" if info["file"]["name"]
                   else f"File: {info['file']['type']}")
    for title, key in (("Data", "data"), ("Measurement", "measurement"), ("All instrument settings", "settings")):
        if info[key]:
            out += ["", title] + [f"  {label}: {value}" for label, value in info[key]]
    for title, key in (("While reading", "notes"), ("Done to the data", "history")):
        if info[key]:
            out += ["", title] + [f"  - {t}" for t in info[key]]
    return "\n".join(out)


def _carried(old: Any) -> dict:
    """The file's details from an earlier "about" (sent back by the website), checked: only text is kept."""
    old = old if isinstance(old, dict) else {}
    pairs = lambda v: [[str(p[0]), str(p[1])] for p in v if isinstance(p, (list, tuple)) and len(p) == 2] \
        if isinstance(v, list) else []
    f = old.get("file")
    file = {"name": None if f.get("name") is None else str(f["name"]), "type": str(f.get("type") or "")} \
        if isinstance(f, dict) else None
    notes = [str(n) for n in old.get("notes")] if isinstance(old.get("notes"), list) else []
    return {"file": file, "measurement": pairs(old.get("measurement")), "settings": pairs(old.get("settings")),
            "notes": notes}


def about(data: Spectrum | SpectrumCollection) -> dict:
    """About a Spectrum or collection: its file, facts from the numbers, the measurement, every
    instrument setting, what was assumed while reading and what was done to it; see the module
    description. Returns {"file", "data", "measurement", "settings", "notes", "history", "text"}."""
    if isinstance(data, Spectrum):
        x, Y, positions, groups = data.x, data.y[None, :], None, [data.group] if data.group else []
    elif isinstance(data, SpectrumCollection):
        x, Y, positions, groups = data.x, data.Y, data.positions, list(data.groups)
    else:
        raise TypeError(f"about needs a Spectrum or SpectrumCollection; got {type(data).__name__}.")
    meta = data.meta if isinstance(data.meta, dict) else {}
    carried = _carried(meta.get("about"))                            # the file's details, after processing
    kind = meta.get("file_type")
    source = meta.get("source")
    name = Path(str(source)).name if source else None
    ext = Path(name).suffix.lower() if name else ""
    kind_name = FILE_TYPES.get(kind, str(kind) if kind else "File")
    info = {
        "file": {"name": name, "type": kind_name + (f" ({ext})" if ext else "")} if (source or kind) else carried["file"],
        "data": _data_lines(np.asarray(x, dtype=float), np.asarray(Y, dtype=float), data.x_unit, data.y_unit,
                            meta, positions, groups),
        "measurement": _measurement_lines(meta) or carried["measurement"],
        "settings": _setting_lines(meta) or carried["settings"],
        "notes": [str(n) for n in meta.get("load_notes") or []] or carried["notes"],
        "history": [_step_text(s) for s in data.history if isinstance(s, dict)] or [NOTHING_DONE],
    }
    info["text"] = _as_text(info)
    return info


__all__ = ["about", "FILE_TYPES"]
