"""Plotting: look at spectra, at what a processing step did, and at scores.

Three functions (``plot`` and ``compare`` also as methods ``s.plot()``):

``stk.plot(*data, kind=...)``
    Draw one or more spectra or collections on one set of axes.
    "lines"  one line per spectrum (default). Many spectra (a map) are drawn
             thin and see-through, coloured along a colour map, without a
             legend, and fast.
    "stack"  lines shifted upwards one above the other, so shapes can be
             compared; ``offset`` sets the shift (automatic by default).
    "mean"   per collection: the mean spectrum with a shaded band of ±1
             standard deviation; shows how much a set of repeats varies.
    "image"  a collection as a picture: one row per spectrum, colour =
             intensity. The quickest view of hundreds of spectra.
    Extras: ``peaks=5`` labels the 5 most prominent bands with their
    position; ``marks={1585: "C=C"}`` draws labelled vertical lines.

``stk.compare(before, after)``
    Before/after view of one processing step. The top panel shows both;
    the lower panel shows what was removed (before - after). Spikes found by
    ``despike`` are shaded. For steps that change the scale (normalize,
    derivative) the result is drawn on its own y axis on the right.

``stk.scatter(x, y, groups=...)``
    Points coloured by group, e.g. PCA scores (as in main.m).

How everything looks is set by a style (see ``spectrum_toolkit.style``):
``style="publication"`` or "matlab", and any setting by name, e.g.
``c.plot(style="publication", aspect="square", box_width=2, colors="matlab")``.
``save="name.tiff"`` saves with the style's dpi and colour mode; for more
control use ``stk.export(ax, ...)``.

matplotlib is needed only for plotting (``pip install "spectrum-toolkit[plot]"``).

>>> import matplotlib
>>> matplotlib.use("Agg")                     # draw without a window (for tests)
>>> from spectrum_toolkit import Spectrum
>>> ax = Spectrum([1, 2, 3], [4, 6, 5], name="s").plot()
>>> ax.get_lines()[0].get_label()
's'
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .core import Spectrum, SpectrumCollection
from .style import (DEFAULTS, _check_one, _colors, _fill, _style_labels_and_title, _style_text, _style_ticks,
                    export, finish_axes, get_style, legend, line_settings, styled, to_rgba)

Data = Spectrum | SpectrumCollection

KINDS = ("lines", "stack", "mean", "image")

_MANY = 10            # more spectra than this: colours from the colour map
_HUGE = 200           # more than this: thin see-through lines, drawn in one go


def _plt():
    """Import matplotlib.pyplot, or explain how to install it."""
    try:
        import matplotlib.pyplot as plt
    except ImportError as e:                                     # only plotting needs matplotlib
        raise ImportError('Plotting needs matplotlib: pip install "spectrum-toolkit[plot]" '
                          "(or: uv add matplotlib).") from e
    return plt


def _rows(item: Data) -> tuple[np.ndarray, np.ndarray, tuple]:
    """(x, Y as 2-D, names) for a Spectrum or a collection, so both are handled alike."""
    if isinstance(item, Spectrum):
        return item.x, item.y[None, :], (item.name or "spectrum",)
    if isinstance(item, SpectrumCollection):
        return item.x, item.Y, item.names
    raise TypeError(f"Can only plot Spectrum or SpectrumCollection, got {type(item).__name__}.")


def _group_labels(item: Data) -> list[str]:
    """The group of each spectrum of an item ("(no group)" for none)."""
    from .groups import NO_GROUP
    if isinstance(item, Spectrum):
        return [item.group or NO_GROUP]
    return [g or NO_GROUP for g in item.groups] if item.groups else [NO_GROUP] * len(item)


def _check_color_by(color_by, kind: str, data) -> list | None:
    """color_by checked: None, or the group of every spectrum (refused when no spectrum has a group)."""
    from .groups import NO_GROUP
    if color_by is None:
        return None
    if color_by != "group":
        raise ValueError(f'color_by must be "group" or None; got {color_by!r}.')
    if kind == "image":
        raise ValueError('color_by="group" is for kind "lines", "stack" and "mean"; an image has no line colours.')
    labels = [g for item in data for g in _group_labels(item)]
    if not labels:                                                  # no spectra at all: nothing to colour
        return None
    if all(g == NO_GROUP for g in labels):
        raise ValueError("These spectra have no groups yet; set them with set_groups "
                         "(suggest_groups proposes some).")
    return labels


def _split_groups(item: Data) -> list:
    """(group, data) for each group of an item, in the order the groups first appear."""
    from .groups import NO_GROUP, by_group
    if isinstance(item, Spectrum):
        return [(item.group or NO_GROUP, item)]
    if not item.groups:
        return [(NO_GROUP, item)]
    return list(by_group(item).items())


def _spike_ranges(item: Data, name: str | None = None) -> list[tuple[float, float]]:
    """x ranges of the spikes that despike removed (from history), for one name or all."""
    ranges = []
    for step in item.history:
        if step.get("step") == "despike":
            for spectrum, events in step.get("spikes", {}).items():
                if name is None or spectrum == name:
                    ranges += [(e["x_from"], e["x_to"]) for e in events]
    return ranges


_RANGE_KEYS = ("color", "alpha", "hatch", "edge_color", "edge_width", "edge_style")   # highlight_... for one range
_MARK_KEYS = ("color", "style", "width", "alpha", "span")                             # mark_... for one mark


def _check_highlight(highlight, look=None):
    """highlight as given: None, "spikes", or a list of ranges; anything else is an error.

    Each range is [lo, hi], or a dict {"range": [lo, hi], "label": ..., and any of
    color, alpha, hatch, edge_color, edge_width, edge_style for this range only}.
    Returns None, "spikes" or a list of dicts.
    """
    if highlight is None or highlight == "spikes":
        return highlight
    example = 'highlight must be "spikes" or a list of x ranges such as [[1570, 1640]] or ' \
              '[{"range": [1570, 1640], "label": "G band", "color": "blue"}]'

    def is_range(r):
        return isinstance(r, (list, tuple)) and len(r) == 2 and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in r)
    if not isinstance(highlight, (list, tuple)):
        raise ValueError(f"{example}; got {highlight!r}.")
    items = []
    for r in highlight:
        item = dict(r) if isinstance(r, dict) else {"range": r}
        if not is_range(item.get("range")):
            raise ValueError(f"{example}; got {r!r}.")
        unknown = set(item) - {"range", "label", *_RANGE_KEYS}
        if unknown:
            raise ValueError(f"highlight: unknown key(s) {', '.join(sorted(unknown))}; use range, label, "
                             f"{', '.join(_RANGE_KEYS)}.")
        for key in _RANGE_KEYS:
            if key in item:
                _check_one(f"highlight_{key}", item[key])
        item["range"] = tuple(item["range"])
        items.append(item)
    return items


def _check_marks(marks):
    """marks as given: a list of x, or a dict x -> label or x -> {"label": ..., and own mark settings}."""
    if not marks:
        return []
    if isinstance(marks, dict):
        items = []
        for x, value in marks.items():
            item = dict(value) if isinstance(value, dict) else {"label": value}
            unknown = set(item) - {"label", *_MARK_KEYS}
            if unknown:
                raise ValueError(f"marks: unknown key(s) {', '.join(sorted(unknown))}; use label, "
                                 f"{', '.join(_MARK_KEYS)}.")
            for key in _MARK_KEYS:
                if key in item:
                    _check_one(f"mark_{key}", item[key])
            items.append({"x": float(x), "label": str(item.pop("label", f"{float(x):g}")), **item})
        return items
    if not isinstance(marks, (list, tuple)) or not all(
            isinstance(m, (int, float)) and not isinstance(m, bool) for m in marks):
        raise ValueError(f'marks must be a list of x such as [1585, 1620] or a dict such as {{1620: "C=C"}}; '
                         f'got {marks!r}.')
    return [{"x": float(m), "label": f"{m:g}"} for m in marks]


def _inside(ranges, lines):
    """Only the ranges that overlap the x span of the drawn lines (e.g. spikes in a part cut off by trim)."""
    if not lines:                                                   # nothing drawn: nothing to shade
        return []
    lo = min(float(np.min(x)) for x, _ in lines)
    hi = max(float(np.max(x)) for x, _ in lines)
    return [(a, b) for a, b in ranges if max(a, b) >= lo and min(a, b) <= hi]


def _shade(ax, ranges, look, spikes: bool = True):
    """Shade x ranges: spikes (spike_color, spike_alpha) or highlighted ranges (dicts, highlight_...)."""
    look = look or DEFAULTS
    for item in ranges:
        if spikes:
            item = {"range": item, "color": look["spike_color"], "alpha": look["spike_alpha"], "hatch": None,
                    "edge_color": None}

        def own(key):                                            # the range's own value, else the style's
            return item[key] if key in item else look[f"highlight_{key}"]
        lo, hi = item["range"]
        if lo == hi:                                             # a 1-point range: make it visible
            lo, hi = lo - 0.5, hi + 0.5
        edge = own("edge_color")
        hatch = own("hatch")
        ax.axvspan(lo, hi, facecolor=to_rgba(own("color"), own("alpha")),
                   edgecolor=to_rgba(edge) if edge is not None else "none",
                   lw=own("edge_width") if edge is not None else 0, ls=own("edge_style"), hatch=hatch,
                   hatchcolor=to_rgba(edge if edge is not None else own("color")) if hatch else None)


def _zoom(ax, region, lines, margin: float = 0.05):
    """Set x limits to region and fit the y limits to the data inside it (margin: share of its height)."""
    lo, hi = sorted(region)
    inside = [y[(x >= lo) & (x <= hi)] for x, y in lines]
    inside = [v[np.isfinite(v)] for v in inside]
    inside = [v for v in inside if v.size]
    left, right = ax.get_xlim()
    ax.set_xlim((hi, lo) if left > right else (lo, hi))         # keep the direction (inverted or not)
    if inside:
        a, b = min(v.min() for v in inside), max(v.max() for v in inside)
        pad = margin * (b - a or 1)
        ax.set_ylim(a - pad, b + pad)


def _ranges(ax, look) -> None:
    """Fixed axis limits (x_range, y_range); a None end stays automatic.

    Peak labels of bands cut off by y_range are kept: they move down to the
    top of the box.
    """
    if look is None:
        return
    for name, get, put in (("x_range", ax.get_xlim, ax.set_xlim), ("y_range", ax.get_ylim, ax.set_ylim)):
        wanted = look[name]
        if wanted is None:
            continue
        now = get()
        low, high = sorted(now)
        lo = low if wanted[0] is None else wanted[0]
        hi = high if wanted[1] is None else wanted[1]
        lo, hi = sorted((lo, hi))
        put((hi, lo) if now[0] > now[1] else (lo, hi))           # keep the direction (inverted or not)
    if look["y_range"] is not None:
        top = max(ax.get_ylim())
        for t in getattr(ax, "_spectrum_texts", []):
            if t.xycoords == "data" and t.xy[1] > top:
                t.xy = (t.xy[0], top)


def _height_at(spectra, lo, hi=None):
    """Highest y of the drawn spectra at x = lo (or within lo..hi); None where nothing is drawn."""
    tops = []
    for x, y, _ in spectra:
        if hi is None:
            if min(x) <= lo <= max(x):
                order = np.argsort(x)
                tops.append(float(np.interp(lo, x[order], y[order])))
        else:
            inside = y[(x >= min(lo, hi)) & (x <= max(lo, hi))]
            if inside.size:
                tops.append(float(inside.max()))
    return max(tops) if tops else None


def _write(ax, text: str, x: float, y: float | None, what: str, look, color=None, line=None, pad=None):
    """Write one label (what: mark_label, peak_label or highlight_label) with its own settings.

    y is the top of the spectrum there, used for position "peak" (None: put it at the top);
    line: settings of a line from (x, y) up to the label (peak_line); pad: distance in
    points when the caller has already chosen it. Returns the text.
    """
    import matplotlib as mpl
    plain = look is None                                         # "matplotlib" preset: its own font
    look = look or {**DEFAULTS, "font_size": mpl.rcParams["font.size"]}

    def get(key):
        return look[f"{what}_{key}"]
    on_peak = get("position") == "peak" and y is not None
    pad = get("pad") if pad is None else pad
    if pad is None:                                              # automatic distance
        pad = 15 if line else 3 if on_peak else 0
    if on_peak:
        xy, coords = (x, y), "data"
    else:                                                        # just above the box
        xy, coords = (x, 1.0), ("data", "axes fraction")
    arrow = None
    if line:
        arrow = dict(arrowstyle="-", color=to_rgba(line["color"], line["alpha"]), lw=line["width"],
                     ls=line["style"], shrinkA=1, shrinkB=1)
    t = ax.annotate(text, xy, xycoords=coords, xytext=(0, pad), textcoords="offset points", ha="center",
                    va="bottom", annotation_clip=False, arrowprops=arrow)
    size = get("size") if get("size") is not None else look["font_size"] * 0.75
    _style_text(t, look, size=size, weight=get("weight") or look["font_weight"],
                color=color if color is not None else get("color"), alpha=get("alpha"), italic=get("italic"),
                font=get("font"), rotation=get("rotation"))
    if plain:
        t.set_fontfamily(mpl.rcParams["font.family"])
    if get("box"):                                               # a box behind the text, so it stays readable
        t.set_bbox(dict(boxstyle="round,pad=0.25", facecolor=to_rgba(get("fill"), get("fill_alpha")),
                        edgecolor=_fill(get("box_color"), 1.0), lw=0.8))
    ax._spectrum_texts = getattr(ax, "_spectrum_texts", []) + [t]   # for moving overlapping labels apart
    return t


def _band_positions(x, y, peaks, look, region=None):
    """Indexes and refined x positions of the bands to label on one line (sorted x, y)."""
    from scipy.signal import find_peaks
    if region:
        keep = (x >= min(region)) & (x <= max(region))
        x, y = x[keep], y[keep]
    if isinstance(peaks, (int, np.integer)):
        # Prominence: how far a band stands out from the valleys on both sides,
        # so noise wiggles on a big band are not labelled.
        sensitivity = look["peak_sensitivity"] if look else 0.02
        idx, props = find_peaks(y, prominence=sensitivity * np.ptp(y), distance=3)
        idx = idx[np.argsort(props["prominences"])[::-1][:int(peaks)]]
    else:
        idx = [int(np.argmax(np.where(np.abs(np.arange(x.size) - np.argmin(np.abs(x - p))) <= 3, y, -np.inf)))
               for p in peaks]
    found = []
    for i in idx:
        xp = x[i]
        if 0 < i < x.size - 1 and x[i - 1] < x[i] < x[i + 1]:
            # Position between the points: top of the parabola through the
            # highest point and its two neighbours (standard peak refinement).
            a, b, _ = np.polyfit(x[i - 1:i + 2] - x[i], y[i - 1:i + 2], 2)
            if a < 0:
                xp = x[i] - b / (2 * a)
        found.append((x[i], y[i], xp))
    return found, (np.ptp(y) if y.size else 0.0)


def _label_peaks(ax, spectra, peaks, look, region=None):
    """Write the position above the most prominent bands of the chosen spectra (peak_spectra).

    peaks : number of bands to label per spectrum (the most prominent), or a
        list of x positions (each labelled at the highest point within 3 points).
    """
    which = look["peak_spectra"] if look else "first"
    chosen = spectra[:1] if which == "first" else spectra if which == "all" else \
        [spectra[k] for k in which if k < len(spectra)]
    use = look or DEFAULTS
    line = ({k: use[f"peak_line_{k}"] for k in ("color", "alpha", "width", "style")}
            if use["peak_line"] else None)
    tops, height = [], 0.0
    for x, y, color in chosen:
        order = np.argsort(x)
        found, h = _band_positions(x[order], y[order], peaks, look, region)
        height = max(height, h)
        for xi, yi, xp in found:
            automatic = use["peak_label_pad"] is None and line is None and use["peak_label_position"] == "peak"
            # automatic distance (as before): 2 % of the data height above the band
            y_at = yi + 0.02 * h if automatic else yi
            label_color = color if use["peak_label_color"] == "line" else None
            _write(ax, use["peak_label_format"].format(xp), xi, y_at, "peak_label", look, color=label_color,
                   line=line, pad=0 if automatic else None)
            tops.append(yi)
    if tops and use["peak_label_position"] == "peak":
        top = max(tops) + 0.12 * height                           # room for the labels
        if top > ax.get_ylim()[1]:
            ax.set_ylim(ax.get_ylim()[0], top)


def _marks(ax, marks, look, spectra):
    """Vertical lines at given x (marks, checked by _check_marks), each labelled."""
    use = look or DEFAULTS
    lo, hi = ax.get_ylim()
    ax.set_ylim(lo, hi)                                          # fixed: lines drawn to the bottom stay there
    for item in marks:
        def own(key):                                            # the mark's own value, else the style's
            return item[key] if key in item else use[f"mark_{key}"]
        xm, peak = item["x"], _height_at(spectra, item["x"])
        kw = dict(color=to_rgba(own("color"), own("alpha")), ls=own("style"), lw=own("width"), zorder=0.6,
                  marker="None")
        span = own("span") if peak is not None else "full"
        if span == "full":
            ax.axvline(xm, **kw)
        elif span == "peak":                                     # from the bottom up to the spectrum
            ax.plot([xm, xm], [lo, peak], **kw)
        else:                                                    # a short line above the spectrum
            ax.plot([xm, xm], [peak + 0.02 * (hi - lo), peak + 0.08 * (hi - lo)], **kw)
        if item["label"]:
            above = peak if span != "tick" or peak is None else peak + 0.08 * (hi - lo)
            _write(ax, item["label"], xm, above, "mark_label", look)


def _highlight_labels(ax, items, look, spectra):
    """The labels of highlighted ranges, centred above each range."""
    for item in items:
        if item.get("label"):
            lo, hi = item["range"]
            _write(ax, str(item["label"]), (lo + hi) / 2, _height_at(spectra, lo, hi), "highlight_label", look)


def _separate(ax, look) -> None:
    """Move labels that would overlap apart (label_overlap = "move"): up when they share an x, else sideways."""
    from matplotlib.text import Text
    texts = getattr(ax, "_spectrum_texts", [])
    if len(texts) < 2 or (look or DEFAULTS)["label_overlap"] != "move":
        return
    renderer = ax.figure.canvas.get_renderer()
    points = 72 / ax.figure.dpi                                  # pixels -> points

    def box(t):                                                  # the text only, not its line to the band
        t.update_positions(renderer)                             # place it at its current offset first
        return Text.get_window_extent(t, renderer).padded(1)
    placed = []
    for t in sorted(texts, key=lambda t: (box(t).x0, box(t).y0)):
        hits = [b for b in placed if box(t).overlaps(b)]
        while hits:
            mine, dx, dy = box(t), *t.xyann
            other = hits[0]
            side = min(mine.x1, other.x1) - max(mine.x0, other.x0)   # how much they overlap sideways
            if side > 0.5 * mine.width:                          # nearly the same x: put it above the other
                t.xyann = (dx, dy + (other.y1 - mine.y0 + 1) * points)
            else:                                                # side by side: shift it right
                t.xyann = (dx + (other.x1 - mine.x0 + 1) * points, dy)
            hits = [b for b in placed if box(t).overlaps(b)]
        placed.append(box(t))


def _labels(ax, first: Data, look, xlabel, ylabel, title, invert_x):
    """Axis labels (from the units unless given), title, direction of x."""
    ax.set_xlabel(xlabel if xlabel is not None else (first.x_unit or "x"))
    if ylabel is not False:
        ax.set_ylabel(ylabel if ylabel is not None else (first.y_unit or "Intensity"))
    if title:
        ax.set_title(title)
    if invert_x and not ax.xaxis_inverted():
        ax.invert_xaxis()                                        # e.g. IR spectra are often drawn high to low


def _save(ax, save, look):
    """Save with the style's settings when save= was given."""
    if save:
        export(ax, save, style={"preset": "clean", **look} if look else "matplotlib")


def _line_colors(look, plt, n: int) -> list:
    """One palette colour per spectrum: the style's colors, or the colour map for many spectra."""
    if n > _MANY or look is None:
        cmap = plt.get_cmap(look["cmap"] if look else "viridis")
        if n > _MANY:
            return [tuple(c) for c in cmap(np.linspace(0, 0.9, n))]
        cycle = plt.rcParams["axes.prop_cycle"].by_key().get("color", ["C0"])   # matplotlib's own colours
        return [cycle[k % len(cycle)] for k in range(n)]
    palette = _colors(look, n)
    return [palette[k % len(palette)] for k in range(n)]


def line_colors(n: int, style: str | dict | None = None, groups=None, **settings: Any) -> list[str]:
    """The colour plot draws each of n spectra in, as "#rrggbb".

    The same steps as plot: the palette of the style (``colors``) in order,
    repeating; more than 10 spectra take their colours from the colour map
    (``cmap``); with ``groups`` (one per spectrum, as for ``color_by="group"``)
    every group gets one colour, in the order the groups first appear, and
    spectra without a group ("" or None) share one; then ``line_color`` (one
    colour, or one per spectrum, None = the palette colour) and colour letters
    in ``line_format`` replace those colours. Transparency is left out.

    Useful to match colours elsewhere (a table, a second figure), and for the
    website, which shows each spectrum's colour before drawing.

    Parameters
    ----------
    n : how many spectra are drawn.
    style : a preset name, a dict of settings or a style file (as for plot).
    groups : one group name per spectrum, or None.
    **settings : any style setting, as for plot.

    >>> line_colors(3, style="clean")
    ['#1f77b4', '#ff7f0e', '#2ca02c']
    >>> line_colors(3, style="clean", groups=["CV", "CV", "MB"])
    ['#1f77b4', '#1f77b4', '#ff7f0e']
    >>> line_colors(3, style="clean", line_color=[None, "red", None])
    ['#1f77b4', '#ff0000', '#2ca02c']
    """
    from matplotlib.colors import to_hex
    from .groups import NO_GROUP
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ValueError(f"n must be a whole number of spectra, 1 or more; got {n!r}.")
    if groups is not None:
        if not isinstance(groups, (list, tuple)) or len(groups) != n:
            raise ValueError(f"groups must be a list with one group per spectrum ({n}); got {groups!r}.")
        groups = [str(g) if g not in (None, "") else NO_GROUP for g in groups]   # no group: one shared colour
    look = get_style(style, **settings)
    plt = _plt()
    with styled(look):                                           # the "matplotlib" preset uses matplotlib's own colours
        if groups is None:
            palette = _line_colors(look, plt, n)
        else:
            order = list(dict.fromkeys(groups))                  # groups in the order they first appear
            by_group = _line_colors(look, plt, len(order))
            palette = [by_group[order.index(g)] for g in groups]
        drawn = [line_settings(look, k, palette[k])["color"] if look else palette[k] for k in range(n)]
    return [to_hex(c, keep_alpha=False) for c in drawn]


def _emphasized(emphasize, names: list, labels: list, n: int) -> set:
    """The spectrum numbers to emphasize (plot's emphasize), checked."""
    if emphasize is None:
        return set()
    chosen = set()
    for item in emphasize if isinstance(emphasize, (list, tuple)) else [emphasize]:
        if isinstance(item, str):
            if item in labels:
                item = labels.index(item)
            elif item in names:
                item = names.index(item)
            else:
                raise ValueError(f"emphasize: no spectrum named {item!r}.")
        if not isinstance(item, (int, np.integer)) or isinstance(item, bool) or not -n <= item < n:
            raise ValueError(f"emphasize: {item!r} is not a spectrum number from 0 to {n - 1} or a name.")
        chosen.add(int(item) % n)
    return chosen


def _draw(ax, x, y, k: int, color, look, chosen: set, base: float, label: str):
    """Draw spectrum number k with its own line settings; returns the line."""
    import matplotlib as mpl
    if look is None:                                                 # "matplotlib" preset: its own defaults
        kw = dict(color=to_rgba(color), linewidth=mpl.rcParams["lines.linewidth"])
        look = DEFAULTS                                              # for emphasize_width, faded_alpha, fill
    else:
        kw = line_settings(look, k, color)
    if k in chosen:                                                  # emphasized: on top, thicker and solid
        width = look["emphasize_width"] if look["emphasize_width"] is not None else 2 * kw["linewidth"]
        kw.update(linewidth=width, color=kw["color"][:3] + (1.0,), zorder=3)
    elif chosen:                                                     # the others fade behind them
        for part in ("color", "markeredgecolor", "markerfacecolor"):
            if kw.get(part) not in (None, "none"):
                kw[part] = kw[part][:3] + (look["faded_alpha"],)
    line, = ax.plot(x, y, label=label, **kw)
    if look["fill"]:                                                 # area between the line and its zero
        fill = look["fill_color"] if look["fill_color"] is not None else kw["color"]
        ax.fill_between(x, base, y, color=to_rgba(fill, look["fill_alpha"]), lw=0,
                        zorder=line.get_zorder() - 0.1)
    return line


# ------------------------------------------------------------------ extras (wish list 7)
_NOTE_KEYS = ("color", "alpha", "size", "weight", "italic", "font", "rotation", "box", "box_color", "fill",
              "fill_alpha", "arrow_color", "arrow_alpha", "arrow_width", "arrow_style", "arrow_head")
_INSET_KEYS = ("position", "scale", "lines")


def _number(v) -> bool:
    return isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool)


def _check_notes(notes):
    """notes as given: None, or a list of dicts with text, x, y and the note's own settings."""
    if notes is None:
        return []
    example = 'notes must be a list such as [{"text": "D band", "x": 1350, "y": 0.8}]'
    if not isinstance(notes, (list, tuple)):
        raise ValueError(f"{example}; got {notes!r}.")
    checked = []
    for note in notes:
        if not isinstance(note, dict) or "text" not in note or not _number(note.get("x")) \
                or not _number(note.get("y")):
            raise ValueError(f"{example}; each needs text, x and y; got {note!r}.")
        unknown = set(note) - {"text", "x", "y", "coords", "arrow", *_NOTE_KEYS}
        if unknown:
            raise ValueError(f"notes: unknown key(s) {', '.join(sorted(unknown))}; use text, x, y, coords, arrow, "
                             f"{', '.join(_NOTE_KEYS)}.")
        if note.get("coords", "data") not in ("data", "axes"):
            raise ValueError(f'notes: coords must be "data" or "axes"; got {note["coords"]!r}.')
        arrow = note.get("arrow")
        if arrow is not None and not (isinstance(arrow, (list, tuple)) and len(arrow) == 2
                                      and all(_number(v) for v in arrow)):
            raise ValueError(f"notes: arrow must be the [x, y] it points at; got {arrow!r}.")
        for key in _NOTE_KEYS:
            if key in note:
                _check_one(f"note_{key}", note[key])
        checked.append(dict(note))
    return checked


def _check_inset(inset):
    """inset as given: None, [lo, hi], or {"region": [lo, hi], ...}; returned as a dict."""
    if inset is None:
        return None
    item = dict(inset) if isinstance(inset, dict) else {"region": inset}
    region = item.get("region")
    if not (isinstance(region, (list, tuple)) and len(region) == 2 and all(_number(v) for v in region)):
        raise ValueError(f'inset must be an x range such as [1550, 1650] or {{"region": [1550, 1650], '
                         f'"position": "upper left"}}; got {inset!r}.')
    unknown = set(item) - {"region", *_INSET_KEYS}
    if unknown:
        raise ValueError(f"inset: unknown key(s) {', '.join(sorted(unknown))}; use region, "
                         f"{', '.join(_INSET_KEYS)}.")
    for key in _INSET_KEYS:
        if key in item:
            _check_one(f"inset_{key}", item[key])
    return item


def _cut_gaps(item: Data) -> list[tuple[float, float]]:
    """x ranges removed by cut (from history), only those with data on both sides."""
    gaps = []
    for step in item.history:
        if step.get("step") == "cut" and step.get("lo") is not None and step.get("hi") is not None:
            lo, hi = step["lo"], step["hi"]
            if item.x.min() < lo and hi < item.x.max():
                gaps.append((lo, hi))
    return gaps


def _break(x, y, gaps):
    """x and y with an empty point (NaN) in each gap, so the line is not drawn across it."""
    if not gaps:
        return x, y
    order = np.argsort(x)
    x, y = x[order], y[order]
    for lo, hi in gaps:
        i = int(np.searchsorted(x, (lo + hi) / 2))                   # first point after the gap
        if 0 < i < x.size:
            x, y = np.insert(x, i, (lo + hi) / 2), np.insert(y, i, np.nan)
    return x, y


def _cut_marks(ax, gaps, look) -> None:
    """// marks on the bottom (and top) box line at both edges of each gap."""
    import matplotlib.transforms as mtransforms
    color = look["cut_mark_color"] if look["cut_mark_color"] is not None else look["box_color"]
    width = look["cut_mark_width"] if look["cut_mark_width"] is not None else look["box_width"]
    on_x = mtransforms.blended_transform_factory(ax.transData, ax.transAxes)   # x in data, y in the box
    sides = [0] + ([1] if look["box"] == "closed" else [])
    for lo, hi in set(gaps):
        for y in sides:
            ax.plot([lo, hi], [y, y], transform=on_x, ls="none", marker=[(-1, -1), (1, 1)],
                    markersize=look["cut_mark_size"], markeredgecolor=to_rgba(color), markeredgewidth=width,
                    clip_on=False, zorder=5, label="_cut mark")


def _band(Y, kind: str):
    """Lower and upper edge of the band around the mean, or None."""
    m = Y.mean(axis=0)
    if kind == "none":
        return None
    if kind in ("std", "2std"):
        sd = Y.std(axis=0) * (2 if kind == "2std" else 1)
        return m - sd, m + sd
    if kind == "minmax":
        return Y.min(axis=0), Y.max(axis=0)
    from scipy.stats import t                                        # "ci95": 95 % confidence of the mean
    n = len(Y)
    half = t.ppf(0.975, n - 1) * Y.std(axis=0, ddof=1) / np.sqrt(n) if n > 1 else np.zeros_like(m)
    return m - half, m + half


def _line_names(ax, spectra, names, look) -> list:
    """Each spectrum's name next to the visible end of its line; returns the texts written."""
    right = look["line_name_position"] == "right"
    lo, hi = sorted(ax.get_xlim())
    written = []
    for (x, y, color), name in zip(spectra, names):
        inside = (x >= lo) & (x <= hi) & np.isfinite(y)
        if not inside.any():
            continue
        xs, ys = x[inside], y[inside]
        at = np.argmax(xs) if right != ax.xaxis_inverted() else np.argmin(xs)   # the end on that side of the box
        t = ax.annotate(str(name), (xs[at], ys[at]), xytext=(look["line_name_pad"] * (1 if right else -1), 0),
                        textcoords="offset points", ha="left" if right else "right", va="center",
                        annotation_clip=False)
        _style_text(t, look, size=look["line_name_size"] or look["legend_size"],
                    weight=look["line_name_weight"] or look["font_weight"],
                    color=color if look["line_name_color"] == "line" else look["line_name_color"],
                    alpha=look["line_name_alpha"], italic=look["line_name_italic"], font=look["line_name_font"])
        written.append(t)
    return written


def _names_width(ax, names, side: str) -> float:
    """How far (in points) the line names reach past the box on one side; 0 when there are none."""
    if not names:
        return 0.0
    renderer = ax.figure.canvas.get_renderer()
    box = ax.get_window_extent(renderer)
    reach = 0.0
    for t in names:
        t.update_positions(renderer)
        edge = t.get_window_extent(renderer)
        reach = max(reach, edge.x1 - box.x1 if side == "right" else box.x0 - edge.x0)
    return reach * 72 / ax.figure.dpi                            # pixels -> points


def _scale_bar(ax, look, unit: str | None, names=()) -> None:
    """A vertical bar of scale_bar y units beside the box, with its size written next to it.

    The bar stands 8 points outside the box, or 6 points past the line names
    when they are on the same side, so the two never cover each other.
    """
    import matplotlib.transforms as mtransforms
    height = look["scale_bar"]
    lo, hi = ax.get_ylim()
    ax.set_ylim(lo, hi)                                          # fixed, so the bar keeps its meaning
    y0 = min(lo, hi) + 0.05 * abs(hi - lo)
    right = look["scale_bar_position"] == "right"
    side = "right" if right else "left"
    away = 8.0
    if names and look["line_name_position"] == side:
        away = max(away, _names_width(ax, names, side) + 6.0)
    x = 1.0 if right else 0.0
    shift = mtransforms.ScaledTranslation((away if right else -away) / 72, 0, ax.figure.dpi_scale_trans)
    on_y = mtransforms.blended_transform_factory(ax.transAxes, ax.transData) + shift   # x in the box, y in data
    color = to_rgba(look["scale_bar_color"], look["scale_bar_alpha"])
    ax.plot([x, x], [y0, y0 + height], transform=on_y, color=color, lw=look["scale_bar_width"],
            solid_capstyle="butt", clip_on=False, marker="None", scalex=False, scaley=False)
    text = look["scale_bar_label"] or f"{height:g} {unit or ''}".strip()
    t = ax.annotate(text, (x, y0 + height / 2), xycoords=on_y, xytext=(4 if right else -4, 0),
                    textcoords="offset points", ha="left" if right else "right", va="center", rotation=90,
                    annotation_clip=False)
    _style_text(t, look, size=look["scale_bar_label_size"] or look["font_size"] * 0.75,
                weight=look["scale_bar_label_weight"] or look["font_weight"], color=look["scale_bar_color"],
                alpha=look["scale_bar_alpha"], italic=look["scale_bar_label_italic"],
                font=look["scale_bar_label_font"], rotation=90)


def _notes(ax, notes, look) -> None:
    """Free text on the plot, each optionally with an arrow to a point."""
    import matplotlib as mpl
    plain = look is None
    use = look or {**DEFAULTS, "font_size": mpl.rcParams["font.size"]}
    for note in notes:
        def own(key):                                            # the note's own value, else the style's
            return note[key] if key in note else use[f"note_{key}"]
        coords = "axes fraction" if note.get("coords") == "axes" else "data"
        arrow = None
        if note.get("arrow") is not None:
            arrow = dict(arrowstyle=own("arrow_head"), color=to_rgba(own("arrow_color"), own("arrow_alpha")),
                         lw=own("arrow_width"), ls=own("arrow_style"), shrinkA=2, shrinkB=2)
        t = ax.annotate(str(note["text"]), tuple(note["arrow"]) if arrow else (note["x"], note["y"]),
                        xytext=(note["x"], note["y"]), textcoords=coords, xycoords="data" if arrow else coords,
                        ha="center", va="center", arrowprops=arrow, annotation_clip=False)
        _style_text(t, use, size=own("size") or use["font_size"], weight=own("weight") or use["font_weight"],
                    color=own("color"), alpha=own("alpha"), italic=own("italic"), font=own("font"),
                    rotation=own("rotation"))
        if plain:
            t.set_fontfamily(mpl.rcParams["font.family"])
        if own("box"):
            t.set_bbox(dict(boxstyle="round,pad=0.3", facecolor=to_rgba(own("fill"), own("fill_alpha")),
                            edgecolor=_fill(own("box_color"), 1.0), lw=0.8))


# Where each inset corner sits, 0 to 1 of the box. Left and lower places leave
# room inside the box for the inset's own tick labels (on its left and bottom).
_INSET_PLACES = {"upper left": (0.12, 0.97), "upper right": (0.97, 0.97), "lower left": (0.12, 0.13),
                 "lower right": (0.97, 0.13)}


def _inset(ax, inset, look) -> None:
    """A small copy of the plot, zoomed to an x range, inside the box."""
    from matplotlib.lines import Line2D
    use = look or DEFAULTS

    def own(key):
        return inset[key] if key in inset else use[f"inset_{key}"]
    size = own("scale")
    cx, cy = _INSET_PLACES[own("position")]
    left = cx if cx < 0.5 else cx - size                         # the corner stays where it was asked
    bottom = cy if cy < 0.5 else cy - size
    small = ax.inset_axes([left, bottom, size, size])
    drawn = []
    for line in ax.get_lines():                                  # copy the spectra (data lines only)
        if line.get_transform() != ax.transData or not line.get_label() or line.get_label().startswith("_"):
            continue
        copy = Line2D(line.get_xdata(), line.get_ydata())
        copy.update_from(line)
        copy.set_transform(small.transData)
        small.add_line(copy)
        drawn.append((np.asarray(line.get_xdata(), float), np.asarray(line.get_ydata(), float)))
    if drawn:
        _zoom(small, inset["region"], [(x, np.where(np.isfinite(y), y, np.nan)) for x, y in drawn])
    if ax.xaxis_inverted():
        small.invert_xaxis()
    tick_size = use["inset_tick_label_size"] or (use["tick_label_size"] or use["font_size"]) * 0.8
    if look:
        count = use["inset_tick_count"]
        finish_axes(small, {**look, "aspect": None, "tick_label_size": tick_size, "zero_lines": None,
                            "x_ticks_at": None, "y_ticks_at": None, "x_tick_step": None, "y_tick_step": None,
                            "x_tick_count": count, "y_tick_count": count,
                            "top_axis": "none", "right_axis": "none", "x_log": False, "y_log": False})
    else:
        from matplotlib.ticker import MaxNLocator
        small.tick_params(labelsize=tick_size)
        if use["inset_tick_count"]:
            small.xaxis.set_major_locator(MaxNLocator(use["inset_tick_count"]))
            small.yaxis.set_major_locator(MaxNLocator(use["inset_tick_count"]))
    ax._spectrum_inset = small                                   # the legend keeps clear of it (_legend_clear_of_inset)
    if own("lines"):
        color = to_rgba(use["inset_line_color"], use["inset_line_alpha"])
        # alpha given apart: matplotlib would otherwise draw the lines half see-through
        shown = ax.indicate_inset_zoom(small, edgecolor=color, alpha=use["inset_line_alpha"],
                                       lw=use["inset_line_width"])
        if hasattr(shown, "connectors"):                         # matplotlib 3.10 and later: one artist
            shown.set_linestyle(use["inset_line_style"])
        else:                                                    # older: the frame and the joining lines
            frame, joins = shown
            frame.set_linestyle(use["inset_line_style"])
            for join in joins:
                join.set_color(color)
                join.set_linewidth(use["inset_line_width"])
                join.set_linestyle(use["inset_line_style"])


# Legend places tried, in order, when the legend at "best" would cover the inset.
_LEGEND_TRIES = ("upper right", "upper left", "lower right", "lower left", "center right", "center left",
                 "upper center", "lower center")


def _legend_clear_of_inset(ax, look) -> None:
    """Move a legend at "best" to the first place where it does not cover the inset (with its tick labels)."""
    leg, small = ax.get_legend(), getattr(ax, "_spectrum_inset", None)
    use = look or DEFAULTS
    if leg is None or small is None or use["legend_position"] is not None or use["legend_location"] != "best":
        return
    renderer = ax.figure.canvas.get_renderer()
    taken = small.get_tightbbox(renderer)                        # the inset box and its numbers
    if not leg.get_window_extent(renderer).overlaps(taken):
        return
    points = [line.get_transform().transform(line.get_xydata()) for line in ax.get_lines()]
    points = np.concatenate(points) if points else np.empty((0, 2))
    texts = [t for t in ax.texts if t.get_visible() and t.get_text()]   # notes and labels
    best, fewest = "best", None
    for place in _LEGEND_TRIES:                                  # the free place that covers the fewest data points
        leg.set_loc(place)
        box = leg.get_window_extent(renderer)
        if box.overlaps(taken):
            continue
        covered = int(np.sum((points[:, 0] >= box.x0) & (points[:, 0] <= box.x1)
                             & (points[:, 1] >= box.y0) & (points[:, 1] <= box.y1)))
        covered += 10_000 * sum(box.overlaps(t.get_window_extent(renderer)) for t in texts)   # never over text
        if fewest is None or covered < fewest:
            best, fewest = place, covered
    leg.set_loc(best)                                            # no free place: "best", left to matplotlib


def _second_axes(ax, look) -> None:
    """A second axis on top (another x unit) and/or on the right (another y unit)."""
    made = []
    if look["top_axis"] != "none":
        if look["top_axis"] == "wavelength":                     # Raman shift -> absolute wavelength
            laser = 1e7 / look["top_axis_laser"]                 # laser line in absolute cm⁻¹

            def forward(v):
                with np.errstate(divide="ignore", invalid="ignore"):
                    return 1e7 / (laser - np.asarray(v, float))

            def back(w):
                with np.errstate(divide="ignore", invalid="ignore"):
                    return laser - 1e7 / np.asarray(w, float)
            label = look["top_axis_label"] or "Wavelength (nm)"
        else:
            a, b = look["top_axis_scale"], look["top_axis_offset"]

            def forward(v):
                return np.asarray(v, float) * a + b

            def back(w):
                return (np.asarray(w, float) - b) / a
            label = look["top_axis_label"] or ax.get_xlabel()
        top = ax.secondary_xaxis("top", functions=(forward, back))
        top.set_xlabel(label)
        made.append((top, "top"))
    if look["right_axis"] != "none":
        a, b = look["right_axis_scale"], look["right_axis_offset"]
        right = ax.secondary_yaxis("right", functions=(lambda v: np.asarray(v, float) * a + b,
                                                        lambda w: (np.asarray(w, float) - b) / a))
        right.set_ylabel(look["right_axis_label"] or ax.get_ylabel())
        made.append((right, "right"))
    for second, side in made:
        on = look[f"{side}_ticks"] if look[f"{side}_ticks"] is not None else True
        labels_on = look[f"{side}_tick_labels"] if look[f"{side}_tick_labels"] is not None else True
        own = {**look, "bottom_ticks": False, "bottom_tick_labels": False, "left_ticks": False,
               "left_tick_labels": False, f"{side}_ticks": on, f"{side}_tick_labels": labels_on,
               "tick_label_sides": [side] if labels_on else [], "tick_sides": [side] if on else []}
        _style_ticks(second, own, twin=False)
        _style_labels_and_title(second, own)
        for name, spine in second.spines.items():                # the main box draws the line, unless it is off
            spine.set_visible(name == side and not ax.spines[side].get_visible())


def plot(*data: Data, kind: str = "lines", ax=None, region: tuple[float, float] | None = None,
         offset: float | None = None, labels: list[str] | None = None, color=None, highlight=None,
         emphasize: list | int | str | None = None, color_by: str | None = None,
         peaks: int | list | None = None, marks: dict | list | None = None, title: str | None = None,
         xlabel: str | None = None, ylabel: str | None = None, invert_x: bool = False,
         notes: list | None = None, inset: list | dict | None = None,
         style: str | dict | None = None, save: str | None = None, **style_settings: Any):
    """Draw spectra and/or collections on one set of axes.

    Parameters
    ----------
    *data : one or more Spectrum or SpectrumCollection; each may have its own x.
    kind : "lines" (default), "stack", "mean" or "image" (see the module description).
    ax : draw into this matplotlib Axes; default a new figure.
    region : (lo, hi) x range to show; y limits follow the data inside it.
    offset : "stack" only: vertical shift between spectra; default automatic.
    labels : legend labels, one per spectrum (or per collection for "mean");
        default the spectrum names.
    color : old name of the style setting line_color (one colour, or one per spectrum).
    highlight : "spikes" shades the spikes removed by despike (from history,
        spike_color); a list of x ranges [[lo, hi], ...] shades those
        (highlight_color ...). A range can also be a dict with its own label
        and settings: {"range": [1570, 1640], "label": "G band", "color": "blue"}.
        None (default) shades nothing.
    emphasize : spectra to bring forward, by number (0 = first) or name, e.g.
        [0, 3]: drawn on top, thicker (emphasize_width) and solid; the others
        fade (faded_alpha). For "mean", the numbers count the collections.
    color_by : "group": one colour per group (see set_groups), and one legend
        entry per group; with kind="mean", one mean per group. labels then
        name the groups. Spectra in no group are shown as "(no group)".
    peaks : label band positions (on the first spectrum, or see peak_spectra):
        a number (that many of the most prominent bands) or a list of x positions.
    marks : vertical lines: a list of x, a dict x -> label, or x -> a dict
        with the label and the mark's own settings, e.g.
        {1620: {"label": "C=C", "color": "red", "style": "--"}}.
    title, xlabel, ylabel : text; the labels default to the units.
    invert_x : draw x from high to low.
    notes : free text on the plot, a list of dicts {"text": ..., "x": ..., "y": ...};
        optional "coords" ("data", default, or "axes": 0 to 1 of the box),
        "arrow": [x, y] (data) to point at, and the note's own settings
        (the note_... names without "note_"), e.g. "color": "red".
    inset : a small zoomed view of an x range inside the plot: [lo, hi], or a
        dict {"region": [lo, hi]} with the inset's own "position", "scale" and
        "lines" (see inset_position, inset_scale, inset_lines).
    style : a preset ("clean" default, "publication", "matlab", "matplotlib"),
        a dict, or a .json file; see ``spectrum_toolkit.style``.
    save : file name to save to (type from the extension; dpi and colour
        mode from the style).
    **style_settings : any style setting by name, e.g. aspect="square",
        box_width=2, line_width=1.5, colors="matlab", tick_direction="in", grid=False,
        line_format="o--", line_alpha=[1, 0.4], marker_fill="none", fill=True.

    With no spectra at all (a collection of 0 spectra, e.g. every spectrum
    left out with drop), any kind draws an empty frame: the x axis spans the
    data's x, y has no numbers, and the title, labels, marks, notes and
    shaded ranges are drawn as usual.

    Returns the matplotlib Axes.
    """
    if not data:
        raise ValueError("Nothing to plot: give at least one Spectrum or SpectrumCollection.")
    if kind not in KINDS:
        raise ValueError(f"Unknown kind {kind!r}. Choose one of: {', '.join(KINDS)}.")
    highlight = _check_highlight(highlight)                         # a wrong value is an error, not ignored
    marks = _check_marks(marks)
    notes = _check_notes(notes)
    inset = _check_inset(inset)
    if color is not None:                                           # old argument: same as line_color
        style_settings.setdefault("line_color", color)
    group_of = _check_color_by(color_by, kind, data)                # one group per spectrum, or None
    nothing = all(len(_rows(item)[1]) == 0 for item in data)        # no spectra at all (e.g. every one left out)
    if nothing:                                                     # an empty frame: drawn as "lines" with no lines
        kind = "lines"
    if group_of is not None and kind == "mean":                     # one mean per group
        parts = [(g, part) for item in data for g, part in _split_groups(item)]
        data = tuple(part for _, part in parts)
        labels = list(labels) if labels else [g for g, _ in parts]
    look = get_style(style, **style_settings)
    plt = _plt()
    with styled(look):
        if ax is None:
            _, ax = plt.subplots()
        rows = [_rows(item) for item in data]                       # (x, Y, names) per item
        n_total = sum(len(Y) for _, Y, _ in rows)
        drawn = []                                                   # (x, y) actually drawn, for zooming
        spectra = []                                                 # (x, y, colour) of each spectrum line
        if kind == "image":
            if len(data) != 1 or len(rows[0][1]) < 2:
                raise ValueError('kind="image" shows one collection of at least 2 spectra.')
            x, Y, _ = rows[0]
            order = np.argsort(x)                                    # pcolormesh needs ascending x
            # Colour limits from the 1st and 99th percentile, so one very bright
            # spectrum does not turn all the others into one dark colour.
            lo, hi = np.percentile(Y, [1, 99])
            use = look or DEFAULTS
            limits = use["color_limits"] or (None, None)              # fixed limits, else the percentiles
            lo, hi = (lo if limits[0] is None else limits[0]), (hi if limits[1] is None else limits[1])
            mesh = ax.pcolormesh(x[order], np.arange(len(Y)) + 1, Y[:, order], shading="nearest",
                                 vmin=lo, vmax=hi)
            if use["colorbar"]:
                ax.figure.colorbar(mesh, ax=ax, label=use["colorbar_label"] or ylabel or data[0].y_unit or "Intensity",
                                   fraction=use["colorbar_fraction"], shrink=use["colorbar_length"],
                                   ticks=use["colorbar_ticks_at"])
            if use["image_y"] == "name":                               # spectrum names instead of numbers
                ax.set_yticks(np.arange(len(Y)) + 1, rows[0][2])
                ax.set_ylabel("spectrum")
            else:
                from matplotlib.ticker import MaxNLocator
                ax.yaxis.set_major_locator(MaxNLocator(integer=True))   # whole spectrum numbers only
                ax.set_ylabel("spectrum number")
            ax.grid(False)
            if region:
                ax.set_xlim(*sorted(region))
            _labels(ax, data[0], look, xlabel, False, title, invert_x)
            _ranges(ax, look)
            _notes(ax, notes, look)
            finish_axes(ax, look)
            _save(ax, save, look)
            return ax
        if kind == "mean":
            labels = list(labels) if labels else [getattr(d, "name", None) or f"set {i + 1}" for i, d in enumerate(data)]
            names = [getattr(d, "name", None) for d in data]
            colors = _line_colors(look, plt, len(rows))
            chosen = _emphasized(emphasize, names, labels, len(rows))
            use = look or DEFAULTS
            for i, (item, (x, Y, _)) in enumerate(zip(data, rows)):
                m = Y.mean(axis=0)
                xd, md = _break(x, m, _cut_gaps(item) if use["cut_marks"] else [])
                line = _draw(ax, xd, md, i, colors[i], look, chosen, 0.0, label=f"{labels[i]} (n={len(Y)})")
                band = _band(Y, use["mean_band"])
                if band is not None:                                  # the shaded band around the mean
                    band_color = use["mean_band_color"] if use["mean_band_color"] is not None else line.get_color()
                    lo_band, hi_band = (_break(x, b, _cut_gaps(item) if use["cut_marks"] else [])[1] for b in band)
                    ax.fill_between(xd, lo_band, hi_band, color=to_rgba(band_color, use["mean_band_alpha"]), lw=0)
                    drawn += [(x, band[0]), (x, band[1])]
                else:
                    drawn.append((x, m))
                spectra.append((x, m, line.get_color()))
            n_lines = len(rows)
        else:
            all_names = [n for _, _, names in rows for n in names]
            if group_of is not None:                                 # labels name the groups
                order = list(dict.fromkeys(group_of))
                if labels and len(labels) != len(order):
                    raise ValueError(f"Got {len(labels)} labels for {len(order)} groups ({', '.join(order)}).")
                called = dict(zip(order, labels or order))
                labels = [called[g] for g in group_of]
            labels = list(labels) if labels else all_names
            if len(labels) != n_total:
                raise ValueError(f"Got {len(labels)} labels for {n_total} spectra.")
            colors = _line_colors(look, plt, n_total)
            entries = labels                                         # legend text per line
            if group_of is not None:                                 # one colour and one legend entry per group
                palette = _line_colors(look, plt, len(order))
                colors = [palette[order.index(g)] for g in group_of]
                entries = [label if group_of.index(g) == k else "_" + label
                           for k, (g, label) in enumerate(zip(group_of, labels))]
            chosen = _emphasized(emphasize, all_names, labels, n_total)
            if kind == "stack" and offset is None:
                # Automatic shift: 60 % of the typical (median) height of one spectrum:
                # neighbours overlap a little at their tallest bands, but each
                # spectrum stays large enough to read its shape.
                heights = [np.ptp(y) for _, Y, _ in rows for y in Y]
                offset = 0.6 * float(np.median(heights)) or 1.0
            k = 0                                                    # running spectrum number
            segments = []
            for item, (x, Y, _) in zip(data, rows):
                gaps = _cut_gaps(item) if look and look["cut_marks"] else []
                for y in Y:
                    base = k * offset if kind == "stack" else 0.0             # where this line's zero is
                    y = y + base
                    drawn.append((x, y))
                    xd, yd = _break(x, y, gaps)                          # a gap where cut removed points
                    if n_total > _HUGE and not chosen:
                        segments.append(np.column_stack([xd, yd]))    # drawn together below, much faster
                        spectra.append((x, y, colors[k]))
                    else:
                        line = _draw(ax, xd, yd, k, colors[k], look, chosen, base, label=entries[k])
                        spectra.append((x, y, line.get_color()))
                    k += 1
            if segments:
                from matplotlib.collections import LineCollection
                width = (look["line_width"] if look and not isinstance(look["line_width"], (list, tuple))
                         else 1.0) * 0.4
                see_through = 0.35                                     # many lines: see-through unless line_alpha is set
                if look:                                               # line_color and line_alpha: one or one per spectrum
                    colors = [line_settings(look, i, c)["color"] for i, c in enumerate(colors)]
                    see_through = see_through if look["line_alpha"] is None else None   # None: alpha in the colours
                ax.add_collection(LineCollection(segments, colors=colors, linewidths=width, alpha=see_through))
                ax.autoscale_view()
                for k, label in enumerate(entries):                  # groups still get their legend entries
                    if not label.startswith("_") and group_of is not None:
                        ax.plot([], [], color=colors[k], label=label)
            if kind == "stack":
                ax.set_yticks([])                                    # absolute values mean little once shifted
            n_lines = n_total if group_of is None else len(order)
        if nothing:                                                  # no lines: the x axis still spans the data
            lo = min(float(x.min()) for x, _, _ in rows)
            hi = max(float(x.max()) for x, _, _ in rows)
            pad = ax.margins()[0] * (hi - lo)                        # the same margin as when lines are drawn
            ax.set_xlim(lo - pad, hi + pad)
            ax.set_yticks([])                                        # no intensities, so no numbers on y
        if highlight == "spikes":
            # spikes outside the drawn x range (cut off by trim) would stretch the axis: skip them
            _shade(ax, _inside([r for item in data for r in _spike_ranges(item)], drawn), look)
        elif highlight:
            _shade(ax, highlight, look, spikes=False)
        if region:
            _zoom(ax, region, drawn, (look or DEFAULTS)["y_margin"])
        if peaks is not None:
            _label_peaks(ax, spectra, peaks, look, region)
        if marks:
            _marks(ax, marks, look, spectra)
        if highlight and highlight != "spikes":
            _highlight_labels(ax, highlight, look, spectra)
        _labels(ax, data[0], look, xlabel, ylabel if kind != "stack" else (ylabel or "Intensity (shifted)"),
                title, invert_x)
        _ranges(ax, look)                                            # after invert_x: the direction is kept
        if look:
            names = _line_names(ax, spectra, labels, look) if look["line_names"] else []
            if look["scale_bar"]:
                _scale_bar(ax, look, data[0].y_unit, names)
            if look["cut_marks"]:
                _cut_marks(ax, [g for item in data for g in _cut_gaps(item)], look)
        _notes(ax, notes, look)
        if inset:
            _inset(ax, inset, look)
        legend(ax, look, n_lines)
        if inset:
            _legend_clear_of_inset(ax, look)
        if look and (look["top_axis"] != "none" or look["right_axis"] != "none"):
            main = {**look}                                          # the main axes leave those sides to the new axes
            if look["top_axis"] != "none":
                main.update(top_ticks=False, top_tick_labels=False)
            if look["right_axis"] != "none":
                main.update(right_ticks=False, right_tick_labels=False)
            finish_axes(ax, main)
            _second_axes(ax, look)
        else:
            finish_axes(ax, look)
        _separate(ax, look)
        _save(ax, save, look)
    return ax


# The plot arguments a panel can have; every other key of a panel is a style setting.
PANEL_ARGUMENTS = ("data", "kind", "region", "offset", "labels", "color", "highlight", "emphasize", "color_by",
                   "peaks", "marks", "title", "xlabel", "ylabel", "invert_x", "notes", "inset", "letter",
                   "after", "index", "removed")
# The arguments of a panel of kind "compare" (a before/after view, as stk.compare).
_COMPARE_ARGUMENTS = ("data", "kind", "after", "index", "region", "removed", "labels", "title", "xlabel",
                      "invert_x", "letter")


def _panel_layout(n: int, layout) -> list[list]:
    """The grid of panels: one row per list, each place the panel's number (0 = first) or None (empty).

    layout: None (one column up to 3 panels, else two columns), [rows, columns],
    or text such as "AA;BC": rows split by ";", one letter per panel (in the
    order they first appear), the same letter in several places for a panel
    across them, and "." for an empty place.
    """
    if layout is None:
        rows, cols = (n, 1) if n <= 3 else (-(-n // 2), 2)
    elif isinstance(layout, str):
        grid = [list(row.replace(" ", "")) for row in layout.split(";")]
        if not all(grid) or len({len(row) for row in grid}) != 1:
            raise ValueError(f'layout text needs rows of the same length, split by ";", e.g. "AA;BC"; got {layout!r}.')
        order = list(dict.fromkeys(c for row in grid for c in row if c != "."))
        for letter in order:                                         # each panel must fill a rectangle
            places = [(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v == letter]
            rs, cs = [r for r, _ in places], [c for _, c in places]
            if len(places) != (max(rs) - min(rs) + 1) * (max(cs) - min(cs) + 1):
                raise ValueError(f"layout {layout!r}: panel {letter!r} must fill a rectangle.")
        if len(order) != n:                                          # one letter per panel
            raise ValueError(f"layout {layout!r} has {len(order)} panels ({', '.join(order)}), but got {n}.")
        return [[None if v == "." else order.index(v) for v in row] for row in grid]
    elif (isinstance(layout, (list, tuple)) and len(layout) == 2
          and all(isinstance(v, int) and not isinstance(v, bool) and v >= 1 for v in layout)):
        rows, cols = layout
        if rows * cols < n:
            raise ValueError(f"layout {list(layout)} has room for {rows * cols} panels, but got {n}.")
    else:
        raise ValueError(f'layout must be [rows, columns], e.g. [2, 2], or text such as "AA;BC"; got {layout!r}.')
    return [[k if k < n else None for k in range(r * cols, (r + 1) * cols)] for r in range(rows)]


def _ratios(name: str, value, count: int):
    """widths / heights of panels, checked: one positive number per column / row."""
    if value is None:
        return None
    if (not isinstance(value, (list, tuple)) or len(value) != count
            or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 for v in value)):
        what = "column" if name == "widths" else "row"
        raise ValueError(f"{name} must be one number above 0 per {what} ({count}), e.g. {[1] * count}; got {value!r}.")
    return list(value)


def _panel_letter(ax, text: str, look) -> None:
    """The panel's letter, above the top left corner of the box or inside it."""
    use = look or DEFAULTS
    outside = use["panel_letter_position"] == "outside"
    t = ax.annotate(text, (0, 1), xycoords="axes fraction", xytext=(0, 4) if outside else (6, -6),
                    textcoords="offset points", ha="right" if outside else "left",
                    va="bottom" if outside else "top", annotation_clip=False)
    size = use["panel_letter_size"] or (use["font_size"] if look else 10) * 1.2
    if look:
        _style_text(t, look, size=size, weight=use["panel_letter_weight"], color=use["panel_letter_color"],
                    alpha=use["panel_letter_alpha"], italic=use["panel_letter_italic"],
                    font=use["panel_letter_font"])
    else:
        t.set_fontsize(size)
        t.set_fontweight(use["panel_letter_weight"])


def panels(items: list, layout: list | tuple | str | None = None, *, by: str | None = None,
           kind: str | None = None, widths: list | None = None,
           heights: list | None = None, share_x: bool = False, share_y: bool = False, title: str | None = None,
           xlabel: str | None = None, ylabel: str | None = None, style: str | dict | None = None,
           save: str | None = None, **style_settings: Any) -> list:
    """Several plots in one figure, each with a letter: (a), (b), (c) ...

    Parameters
    ----------
    items : one entry per panel, in reading order (left to right, then down).
        An entry is a Spectrum or SpectrumCollection, or a dict with "data"
        (one item, or a list of items for one panel) and any plot arguments
        ("kind", "title", "peaks", "marks", "highlight", "region", "notes",
        "inset" ...; see ``plot``). Any other key of the dict is a style
        setting for that panel only, e.g. {"data": d, "kind": "stack",
        "line_width": 2}. "letter" replaces the panel's letter (False: none).
        Kind "compare" is a before/after view as ``compare``:
        {"data": before, "after": after, "kind": "compare", "index": 0,
        "region": ..., "removed": ..., "labels": ...}; its "removed" strip
        stays under it, in the same place of the layout.
    by : "group": items is one collection (or Spectrum / list of them) and
        each group (see set_groups) gets a panel, titled with its name and
        number of spectra.
    kind : the kind of every panel that does not give its own.
    layout : [rows, columns]; or text such as "AA;BC" (rows split by ";",
        one letter per panel in the order of items, the same letter in several
        places for a panel across them, "." for an empty place); default one
        column for up to 3 panels, else two columns.
    widths, heights : relative width of each column and height of each row,
        e.g. widths=[2, 1]; default all equal.
    share_x, share_y : panels share the x (or y) range; the numbers and the
        axis label are then written only on the outer panels.
    title : one title over the whole figure (each panel's own title goes in its dict).
    xlabel, ylabel : text of the shared labels (panel_shared_labels); default
        the first panel's labels.
    style, save, **style_settings : as in ``plot``, for every panel. The
        figure is size x layout (each panel gets the size of one plot).
        Panel settings: panel_letters, panel_letter_format ..., panel_spacing,
        panel_spacing_x, panel_spacing_y, panel_legend, panel_shared_labels,
        panel_colorbar.

    Returns the list of the panels' matplotlib Axes (``axes[0].figure`` is the figure).
    """
    from .style import _size_inches, place_outside_legend
    if by is not None:                                               # one panel per group
        if by != "group":
            raise ValueError(f'by must be "group" or None; got {by!r}.')
        data = items if isinstance(items, (list, tuple)) else [items]
        if _check_color_by("group", "lines", data) is None:
            raise ValueError("Nothing to split into groups.")
        items = [{"data": part, "title": f"{group} ({len(_rows(part)[1])})"}
                 for item in data for group, part in _split_groups(item)]
    if not isinstance(items, (list, tuple)) or not items:
        raise ValueError("panels needs a list with at least one panel.")
    if kind is not None and kind not in KINDS + ("compare",):
        raise ValueError(f"Unknown kind {kind!r}. Choose one of: {', '.join(KINDS + ('compare',))}.")
    entries = []
    for i, item in enumerate(items):                                 # every panel as a dict, checked
        entry = dict(item) if isinstance(item, dict) else {"data": item}
        if "data" not in entry:
            raise ValueError(f'Panel {i + 1} has no "data".')
        if kind is not None:
            entry.setdefault("kind", kind)
        if entry.get("kind") == "compare" and "after" not in entry:
            raise ValueError(f'Panel {i + 1}: kind "compare" needs "after" (the data after the step).')
        if entry.get("kind") != "compare" and any(k in entry for k in ("after", "index", "removed")):
            raise ValueError(f'Panel {i + 1}: "after", "index" and "removed" are for kind "compare".')
        entries.append(entry)
    grid = _panel_layout(len(entries), layout)
    rows, cols = len(grid), len(grid[0])
    widths, heights = _ratios("widths", widths, cols), _ratios("heights", heights, rows)
    look = get_style(style, **style_settings)
    use = look or DEFAULTS
    shared_bar = use["panel_colorbar"] == "shared"
    figure_legend = use["panel_legend"] != "each"
    plt = _plt()
    with styled(look):
        width, height = _size_inches(look) if look else plt.rcParams["figure.figsize"]
        fig = plt.figure(figsize=(width * cols, height * rows), layout="constrained")
        mosaic = [[str(k) if k is not None else "." for k in row] for row in grid]
        made = fig.subplot_mosaic(mosaic, empty_sentinel=".", width_ratios=widths, height_ratios=heights)
        axes = [made[str(k)] for k in range(len(entries))]
        across, down = (use[k] if use[k] is not None else use["panel_spacing"]       # x and y, else both
                        for k in ("panel_spacing_x", "panel_spacing_y"))
        fig.get_layout_engine().set(wspace=across, hspace=down)
        views = [i for i, e in enumerate(entries) if e.get("kind") == "compare"]     # drawn in a new place below
        anchor = next((i for i in range(len(entries)) if i not in views), None)       # the panel the others follow
        for i, ax in enumerate(axes):                                # shared ranges; which numbers show is set below
            if i in views or i == anchor:
                continue
            if share_x:
                ax.sharex(axes[anchor])
            if share_y:
                ax.sharey(axes[anchor])
        strips = {}                                                  # compare panels: their "removed" strip
        images = [i for i, e in enumerate(entries) if e.get("kind") == "image"]
        limits = _shared_limits([entries[i] for i in images], look) if shared_bar and images else None
        looks = []
        for i, (ax, entry) in enumerate(zip(axes, entries)):
            data = entry["data"] if isinstance(entry["data"], (list, tuple)) else [entry["data"]]
            arguments = {k: v for k, v in entry.items() if k in PANEL_ARGUMENTS and k not in ("data", "letter")}
            own = {k: v for k, v in entry.items() if k not in PANEL_ARGUMENTS}
            if limits is not None and i in images:                   # one colour scale, one bar (drawn below)
                own = {"color_limits": limits, **own, "colorbar": False}
            if figure_legend:                                        # one legend for the figure (drawn below)
                own = {**own, "legend": False}
            try:
                if i in views:
                    ax = axes[i] = _compare_panel(entry, ax, style, {**style_settings, **own}, strips, i)
                    first = axes[anchor] if anchor is not None else axes[views[0]]
                    if ax is not first:                              # follow the others' ranges
                        if share_x:
                            ax.sharex(first)
                        if share_y:
                            ax.sharey(first)
                else:
                    plot(*data, ax=ax, style=style, **arguments, **{**style_settings, **own})
            except (TypeError, ValueError) as error:                 # say which panel is wrong
                raise ValueError(f"Panel {i + 1}: {error}") from None
            panel_look = get_style(style, **{**style_settings, **own})
            looks.append(panel_look)
            panel_use = panel_look or DEFAULTS
            letter = entry.get("letter", True)
            if letter is not False and letter is not None and (panel_use["panel_letters"] or isinstance(letter, str)):
                if not isinstance(letter, str):
                    name = chr(ord("a") + i) if i < 26 else str(i + 1)
                    name = name.upper() if panel_use["panel_letter_case"] == "upper" else name
                    letter = panel_use["panel_letter_format"].format(name)
                _panel_letter(ax, letter, panel_look)
        bottoms = [strips.get(i, ax) for i, ax in enumerate(axes)]   # where each panel's x numbers are
        _shared_labels(fig, axes, look, xlabel, ylabel, bottoms)       # before the inner labels are removed
        _outer_numbers(axes, grid, share_x, share_y, bottoms)
        if figure_legend:
            _figure_legend(fig, axes, look, under_title=bool(title))
        if limits is not None:
            _shared_colorbar(fig, [axes[i] for i in images], look, entries[images[0]]["data"])
        if title:                                                    # styled like the panel titles
            heading = fig.suptitle(title)
            if look:
                _style_text(heading, look, size=use["title_size"], weight=use["title_weight"] or use["font_weight"],
                            color=use["title_color"], alpha=use["title_alpha"], italic=use["title_italic"],
                            font=use["title_font"])
        fig.canvas.draw()                                            # run the layout, then place what depends on it
        if title and fig.legends and use["panel_legend"] == "figure top":
            _legend_under_title(fig)
        for ax, panel_look in zip(axes, looks):
            place_outside_legend(ax, panel_look)
            _separate(ax, panel_look)
        _save(axes[0], save, look)
    return axes


def _compare_panel(entry: dict, ax, style, settings: dict, strips: dict, i: int):
    """A panel of kind "compare" in the place of ax; returns the view's axes (its strip goes in strips[i])."""
    unknown = sorted(k for k in entry if k in PANEL_ARGUMENTS and k not in _COMPARE_ARGUMENTS)
    if unknown:
        raise ValueError(f'{", ".join(unknown)} cannot be used with kind "compare"; it takes '
                         f'{", ".join(k for k in _COMPARE_ARGUMENTS if k not in ("data", "kind", "letter"))}.')
    before = entry["data"][0] if isinstance(entry["data"], (list, tuple)) else entry["data"]
    look = get_style(style, **settings)
    view, strip = _compare_view(before, entry["after"], entry.get("index", 0), entry.get("region"),
                                entry.get("removed", "auto"), tuple(entry.get("labels") or ("before", "after")),
                                entry.get("title"), entry.get("xlabel"), entry.get("invert_x", False), ax, look)
    if strip is not None:
        strips[i] = strip
    return view


def _legend_under_title(fig) -> None:
    """A legend at the top of a figure with a title: under the title, with the panels moved down to make room.

    (matplotlib's layout would put the title and the legend in the same place.)
    """
    leg = fig.legends[-1]
    renderer = fig.canvas.get_renderer()
    height, gap = fig.bbox.height, 4 * fig.dpi / 72              # pixels; gap = 4 points
    room = (leg.get_window_extent(renderer).height + gap) / height
    fig.get_layout_engine().set(rect=(0, 0, 1, 1 - room))       # the panels end below the legend
    fig.canvas.draw()
    under = fig._suptitle.get_window_extent(renderer).y0 - gap
    leg.set_bbox_to_anchor((0, 0, 1, under / height), transform=fig.transFigure)


def _outer_numbers(axes, grid, share_x: bool, share_y: bool, bottoms=None) -> None:
    """Shared axes: x numbers and label only where no panel is below, y only where none is to the left.

    bottoms: the axes that carries each panel's x numbers (a compare panel's strip), default the panel.
    """
    bottoms = bottoms or axes
    for k, ax in enumerate(axes):
        places = [(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v == k]
        bottom, left = max(r for r, _ in places), min(c for _, c in places)
        rows_of, cols_of = {r for r, _ in places}, {c for _, c in places}
        below = any(grid[r][c] not in (None, k) for r in range(bottom + 1, len(grid)) for c in cols_of)
        beside = any(grid[r][c] not in (None, k) for r in rows_of for c in range(left))
        if share_x and below:
            bottoms[k].tick_params(labelbottom=False)
            bottoms[k].set_xlabel("")
        if share_y and beside:
            ax.tick_params(labelleft=False)
            ax.set_ylabel("")


def _shared_labels(fig, axes, look, xlabel, ylabel, bottoms=None) -> None:
    """panel_shared_labels: one x label under the figure and/or one y label on its left.

    bottoms: the axes that carries each panel's x label (a compare panel's strip), default the panel.
    """
    from .style import style_axis_label
    shared = (look or DEFAULTS)["panel_shared_labels"]
    for axis, own, wanted in (("x", xlabel, shared in (True, "x")), ("y", ylabel, shared in (True, "y"))):
        if not wanted:
            continue
        holders = (bottoms or axes) if axis == "x" else axes
        text = own if own is not None else getattr(holders[0], f"get_{axis}label")()
        for ax in holders:                                           # the panels' own labels go
            getattr(ax, f"set_{axis}label")("")
        label = fig.supxlabel(text) if axis == "x" else fig.supylabel(text)
        if look:
            style_axis_label(label, look, axis)


_FIGURE_LEGEND = {"figure top": "outside upper center", "figure bottom": "outside lower center",
                  "figure right": "outside right upper"}


def _figure_legend(fig, axes, look, under_title: bool = False) -> None:
    """panel_legend: one legend for the whole figure, each name once, in the order the panels show them.

    under_title: a legend on top goes under the figure title (placed by _legend_under_title).
    """
    from .style import legend_entries, legend_options, style_legend_box
    use = look or DEFAULTS
    seen = {}
    for ax in axes:
        for handle, label in zip(*ax.get_legend_handles_labels()):
            seen.setdefault(label, handle)
    labels, handles = list(seen), list(seen.values())
    show = use["legend"]
    if not labels or show is False or (show == "auto" and not 1 < len(labels) <= 10):
        return
    place = _FIGURE_LEGEND[use["panel_legend"]]
    by_hand = under_title and use["panel_legend"] == "figure top"
    if by_hand:
        place = "upper center"
    if look is None:
        fig.legend(handles, labels, loc=place).set_in_layout(not by_hand)
        return
    handles, labels = legend_entries(handles, labels, look)
    columns = None
    if use["panel_legend"] != "figure right" and use["legend_columns"] == 1:
        columns = len(labels)                                        # above or below: one row
    leg = fig.legend(handles, labels, loc=place, **legend_options(look, len(labels), columns))
    leg.set_in_layout(not by_hand)                               # placed by hand: the layout leaves room instead
    style_legend_box(leg, look)


def _shared_limits(entries, look) -> list:
    """One colour scale for the image panels: color_limits, else the 1st and 99th percentile of all of them."""
    use = look or DEFAULTS
    values = np.concatenate([_rows(e["data"] if not isinstance(e["data"], (list, tuple)) else e["data"][0])[1].ravel()
                             for e in entries])
    lo, hi = np.percentile(values, [1, 99])
    wanted = use["color_limits"] or (None, None)
    return [float(lo) if wanted[0] is None else wanted[0], float(hi) if wanted[1] is None else wanted[1]]


def _shared_colorbar(fig, axes, look, first) -> None:
    """panel_colorbar "shared": one colour bar beside all image panels."""
    use = look or DEFAULTS
    first = first[0] if isinstance(first, (list, tuple)) else first
    fig.colorbar(axes[0].collections[0], ax=axes, label=use["colorbar_label"] or first.y_unit or "Intensity",
                 fraction=use["colorbar_fraction"], shrink=use["colorbar_length"], ticks=use["colorbar_ticks_at"])


def _describe(step: dict, short: bool = False) -> str:
    """One-line description of a history step, e.g. 'baseline: airpls, lam=1e+06'; short: 'baseline (airpls)'."""
    if short:
        return f"{step.get('step', '?')} ({step['method']})" if step.get("method") else step.get("step", "?")
    skip = {"step", "method", "spikes"}
    settings = ", ".join(f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}"
                         for k, v in step.items() if k not in skip and v is not None)
    return f"{step.get('step', '?')}: {step.get('method', '')}" + (f", {settings}" if settings else "")


def _pick(item: Data, index: int | str) -> Spectrum:
    """One spectrum of a collection by number or name (a Spectrum is returned as is)."""
    if isinstance(item, Spectrum):
        return item
    if isinstance(index, str):
        if index not in item.names:
            raise ValueError(f"No spectrum named {index!r}.")
        index = item.names.index(index)
    return item[index]


def compare(before: Data, after: Data, index: int | str = 0, *, region: tuple[float, float] | None = None,
            removed: bool | str = "auto", labels: tuple[str, str] = ("before", "after"),
            title: str | None = None, xlabel: str | None = None, invert_x: bool = False, ax=None,
            style: str | dict | None = None, save: str | None = None, **style_settings: Any):
    """Before/after view of a processing step, for one spectrum.

    Parameters
    ----------
    before, after : the data before and after the step (Spectrum or collection).
    index : which spectrum of a collection, by number (0 = first) or name.
    region : (lo, hi) x range to show.
    removed : show the lower "removed" panel (before - after). "auto": yes
        when both have the same x and the step does not change the scale.
    labels : legend labels of the two lines.
    title : default: the step and its settings, from ``after.history``.
    ax : draw into the place of this matplotlib Axes (it is split in two when
        the "removed" part is shown); default a new figure. ``panels`` uses
        this for panels of kind "compare".
    style, save, xlabel, invert_x, **style_settings : as in ``plot``.

    Returns the matplotlib Axes of the top panel (the lower one is
    ``ax.figure.axes[1]`` when shown on a figure of its own).
    """
    look = get_style(style, **style_settings)
    with styled(look):
        ax, _ = _compare_view(before, after, index, region, removed, labels, title, xlabel, invert_x, ax, look)
        _save(ax, save, look)
    return ax


def _compare_view(before, after, index, region, removed, labels, title, xlabel, invert_x, ax, look) -> tuple:
    """compare's view, on a figure of its own (ax None) or in the place of ax; returns (top, strip or None)."""
    plt = _plt()
    b, a = _pick(before, index), _pick(after, index)
    step = a.history[-1] if len(a.history) > len(b.history) else {}
    rescaled = step.get("step") in ("normalize", "derivative")      # the y scale is different afterwards
    same_x = b.x.shape == a.x.shape and np.allclose(b.x, a.x)
    if removed == "auto":
        removed = same_x and not rescaled
    elif removed and not same_x:
        raise ValueError("Cannot show what was removed: before and after have different x (resample first).")
    own_figure = ax is None
    if own_figure and removed:
        w, h = plt.rcParams["figure.figsize"]
        fig, (ax, low) = plt.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [2.2, 1]},
                                      figsize=(w, max(h, w * 0.6)))
    elif own_figure:
        fig, ax = plt.subplots()
        low = None
    elif removed:                                                   # the strip hangs under the view's own box, so
        fig = ax.figure                                             # boxes in a column of panels stay lined up
        low = ax.inset_axes([0, -1 / 2.2 - 0.05, 1, 1 / 2.2], sharex=ax)    # 2.2 : 1, as on its own figure
    else:
        fig, low = ax.figure, None
    # On its own figure the legend always shows (as before); in a given place legend=False is respected.
    show = True if own_figure else (look is None or look["legend"] is not False)
    _compare_into(ax, low, b, a, step, rescaled, same_x, region, labels, title, xlabel, invert_x, look, show,
                  short_title=not own_figure)
    if own_figure:
        fig.tight_layout()
    return ax, low


def _compare_into(ax, low, b: Spectrum, a: Spectrum, step: dict, rescaled: bool, same_x: bool, region,
                  labels, title, xlabel, invert_x: bool, look, show_legend: bool = True,
                  short_title: bool = False) -> None:
    """Draw a before/after view into ax (and the "removed" part into low, when given).

    show_legend False: no legend (a panel whose names go in the figure legend).
    short_title: the default title without the settings, "baseline (airpls)" (for a panel).
    """
    plt = _plt()
    palette = plt.rcParams["axes.prop_cycle"].by_key().get("color", ["tab:blue", "tab:red"])
    main, second = palette[0], palette[1 % len(palette)]
    ax.plot(b.x, b.y, color="0.55", label=labels[0])
    drawn = [(b.x, b.y)]
    target = ax.twinx() if rescaled else ax                        # own y axis when the scale changed
    target.plot(a.x, a.y, color=main, label=labels[1])
    if rescaled:
        target.set_ylabel(a.y_unit or f"{labels[1]} ({step.get('method', '')})", color=main)
        target.grid(False)
        ax.plot([], [], color=main, label=labels[1])                # so the legend lists both lines
    else:
        drawn.append((a.x, a.y))
    if step.get("step") == "baseline" and same_x:
        ax.plot(b.x, b.y - a.y, "--", color=second, label="baseline")
    # Shade spikes only when the step shown is despike (not earlier steps).
    spikes = [(e["x_from"], e["x_to"]) for e in step.get("spikes", {}).get(a.name, [])]
    _shade(ax, spikes, look)
    if low is not None:
        low.plot(b.x, b.y - a.y, color="k")
        low.axhline(0, color="0.6", lw=0.6, marker="None")
        low.set_ylabel("removed")
        _shade(low, spikes, look)
    margin = (look or DEFAULTS)["y_margin"]
    if region:
        _zoom(ax, region, drawn, margin)
        if low is not None:
            m = (b.x >= min(region)) & (b.x <= max(region))
            d = (b.y - a.y)[m]
            if d.size:
                pad = margin * (np.ptp(d) or 1)
                low.set_ylim(d.min() - pad, d.max() + pad)
    title = title if title is not None else (_describe(step, short=short_title) if step else "")
    title = f"{a.name}: {title}" if a.name and title else (a.name or title)
    legend(ax, look, 2, force=show_legend)
    ax.set_title(title, fontsize="medium")
    ax.set_ylabel(b.y_unit or "Intensity")
    bottom = low if low is not None else ax
    bottom.set_xlabel(xlabel if xlabel is not None else (b.x_unit or "x"))
    if low is not None:
        ax.tick_params(labelbottom=False)                           # the numbers go under the strip
    if invert_x and not ax.xaxis_inverted():
        ax.invert_xaxis()
    _ranges(ax, look)                                               # y_range: the top panel; x_range: both
    for axis in dict.fromkeys(a for a in (ax, low, target) if a is not None):   # the view, the strip, the right axis
        finish_axes(axis, look if axis is ax else ({**look, "aspect": None} if look else None))
    if rescaled:                                                    # the right axis label in the colour of its line
        target.yaxis.label.set_color(main)


def scatter(x, y, groups=None, *, names: list[str] | None = None, ax=None, marker: str = "o",
            marker_size: float = 30, title: str | None = None, xlabel: str = "", ylabel: str = "",
            style: str | dict | None = None, save: str | None = None, **style_settings: Any):
    """Points coloured by group, e.g. scores of a PCA (MATLAB's gscatter).

    Parameters
    ----------
    x, y : numbers, one per point.
    groups : one group label per point (e.g. ["CV", "CV", "MB", ...] or
        numbers); each group gets its own colour and a legend entry, in the
        order the groups first appear. None: one group.
    names : legend names for the groups, in that order (default the labels).
    marker, marker_size : point shape and area (points²).
    title, xlabel, ylabel, style, save, **style_settings : as in ``plot``;
        e.g. zero_lines="both", aspect="square", x_tick_step=0.03.

    Returns the matplotlib Axes.
    """
    plt = _plt()
    look = get_style(style, **style_settings)
    x, y = np.asarray(x, float), np.asarray(y, float)
    if x.shape != y.shape:
        raise ValueError(f"x and y must have the same length, got {x.size} and {y.size}.")
    groups = np.zeros(x.size, int) if groups is None else np.asarray(groups)
    if groups.shape != x.shape:
        raise ValueError(f"groups must have one label per point ({x.size}), got {groups.size}.")
    unique = list(dict.fromkeys(groups.tolist()))                    # order of first appearance
    names = list(names) if names else [str(g) for g in unique]
    if len(names) != len(unique):
        raise ValueError(f"Got {len(names)} names for {len(unique)} groups.")
    with styled(look):
        if ax is None:
            _, ax = plt.subplots()
        for g, name in zip(unique, names):
            m = groups == g
            ax.scatter(x[m], y[m], s=marker_size, marker=marker, label=name, zorder=2)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if title:
            ax.set_title(title)
        legend(ax, look, len(unique))
        finish_axes(ax, look)
        _save(ax, save, look)
    return ax


__all__ = ["plot", "panels", "compare", "scatter", "line_colors", "KINDS"]
