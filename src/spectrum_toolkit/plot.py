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
from .style import DEFAULTS, _check_one, _colors, _fill, _style_text, export, finish_axes, get_style, legend, line_settings, styled, to_rgba

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


def _zoom(ax, region, lines):
    """Set x limits to region and fit the y limits to the data inside it."""
    lo, hi = sorted(region)
    inside = [y[(x >= lo) & (x <= hi)] for x, y in lines]
    inside = [v for v in inside if v.size]
    left, right = ax.get_xlim()
    ax.set_xlim((hi, lo) if left > right else (lo, hi))         # keep the direction (inverted or not)
    if inside:
        a, b = min(v.min() for v in inside), max(v.max() for v in inside)
        pad = 0.05 * (b - a or 1)
        ax.set_ylim(a - pad, b + pad)


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


def plot(*data: Data, kind: str = "lines", ax=None, region: tuple[float, float] | None = None,
         offset: float | None = None, labels: list[str] | None = None, color=None, highlight=None,
         emphasize: list | int | str | None = None,
         peaks: int | list | None = None, marks: dict | list | None = None, title: str | None = None,
         xlabel: str | None = None, ylabel: str | None = None, invert_x: bool = False,
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
    peaks : label band positions (on the first spectrum, or see peak_spectra):
        a number (that many of the most prominent bands) or a list of x positions.
    marks : vertical lines: a list of x, a dict x -> label, or x -> a dict
        with the label and the mark's own settings, e.g.
        {1620: {"label": "C=C", "color": "red", "style": "--"}}.
    title, xlabel, ylabel : text; the labels default to the units.
    invert_x : draw x from high to low.
    style : a preset ("clean" default, "publication", "matlab", "matplotlib"),
        a dict, or a .json file; see ``spectrum_toolkit.style``.
    save : file name to save to (type from the extension; dpi and colour
        mode from the style).
    **style_settings : any style setting by name, e.g. aspect="square",
        box_width=2, line_width=1.5, colors="matlab", tick_direction="in", grid=False,
        line_format="o--", line_alpha=[1, 0.4], marker_fill="none", fill=True.

    Returns the matplotlib Axes.
    """
    if not data:
        raise ValueError("Nothing to plot: give at least one Spectrum or SpectrumCollection.")
    if kind not in KINDS:
        raise ValueError(f"Unknown kind {kind!r}. Choose one of: {', '.join(KINDS)}.")
    highlight = _check_highlight(highlight)                         # a wrong value is an error, not ignored
    marks = _check_marks(marks)
    if color is not None:                                           # old argument: same as line_color
        style_settings.setdefault("line_color", color)
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
            mesh = ax.pcolormesh(x[order], np.arange(len(Y)) + 1, Y[:, order], shading="nearest",
                                 vmin=lo, vmax=hi)
            ax.figure.colorbar(mesh, ax=ax, label=ylabel or data[0].y_unit or "Intensity")
            ax.set_ylabel("spectrum number")
            ax.grid(False)
            if region:
                ax.set_xlim(*sorted(region))
            _labels(ax, data[0], look, xlabel, False, title, invert_x)
            finish_axes(ax, look)
            _save(ax, save, look)
            return ax
        if kind == "mean":
            labels = list(labels) if labels else [getattr(d, "name", None) or f"set {i + 1}" for i, d in enumerate(data)]
            names = [getattr(d, "name", None) for d in data]
            colors = _line_colors(look, plt, len(rows))
            chosen = _emphasized(emphasize, names, labels, len(rows))
            for i, (x, Y, _) in enumerate(rows):
                m, sd = Y.mean(axis=0), Y.std(axis=0)
                line = _draw(ax, x, m, i, colors[i], look, chosen, 0.0, label=f"{labels[i]} (n={len(Y)})")
                ax.fill_between(x, m - sd, m + sd, color=line.get_color(), alpha=0.25, lw=0)
                drawn += [(x, m - sd), (x, m + sd)]
                spectra.append((x, m, line.get_color()))
            n_lines = len(rows)
        else:
            all_names = [n for _, _, names in rows for n in names]
            labels = list(labels) if labels else all_names
            if len(labels) != n_total:
                raise ValueError(f"Got {len(labels)} labels for {n_total} spectra.")
            colors = _line_colors(look, plt, n_total)
            chosen = _emphasized(emphasize, all_names, labels, n_total)
            if kind == "stack" and offset is None:
                # Automatic shift: 60 % of the typical (median) height of one spectrum:
                # neighbours overlap a little at their tallest bands, but each
                # spectrum stays large enough to read its shape.
                heights = [np.ptp(y) for _, Y, _ in rows for y in Y]
                offset = 0.6 * float(np.median(heights)) or 1.0
            k = 0                                                    # running spectrum number
            segments = []
            for x, Y, _ in rows:
                for y in Y:
                    base = k * offset if kind == "stack" else 0.0             # where this line's zero is
                    y = y + base
                    drawn.append((x, y))
                    if n_total > _HUGE and not chosen:
                        segments.append(np.column_stack([x, y]))      # drawn together below, much faster
                        spectra.append((x, y, colors[k]))
                    else:
                        line = _draw(ax, x, y, k, colors[k], look, chosen, base, label=labels[k])
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
            if kind == "stack":
                ax.set_yticks([])                                    # absolute values mean little once shifted
            n_lines = n_total
        if highlight == "spikes":
            # spikes outside the drawn x range (cut off by trim) would stretch the axis: skip them
            _shade(ax, _inside([r for item in data for r in _spike_ranges(item)], drawn), look)
        elif highlight:
            _shade(ax, highlight, look, spikes=False)
        if region:
            _zoom(ax, region, drawn)
        if peaks is not None:
            _label_peaks(ax, spectra, peaks, look, region)
        if marks:
            _marks(ax, marks, look, spectra)
        if highlight and highlight != "spikes":
            _highlight_labels(ax, highlight, look, spectra)
        _labels(ax, data[0], look, xlabel, ylabel if kind != "stack" else (ylabel or "Intensity (shifted)"),
                title, invert_x)
        legend(ax, look, n_lines)
        finish_axes(ax, look)
        _separate(ax, look)
        _save(ax, save, look)
    return ax


def _describe(step: dict) -> str:
    """One-line description of a history step, e.g. 'baseline: airpls, lam=1e+06'."""
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
            title: str | None = None, xlabel: str | None = None, invert_x: bool = False,
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
    style, save, xlabel, invert_x, **style_settings : as in ``plot``.

    Returns the matplotlib Axes of the top panel (the lower one is
    ``ax.figure.axes[1]`` when shown).
    """
    plt = _plt()
    look = get_style(style, **style_settings)
    b, a = _pick(before, index), _pick(after, index)
    step = a.history[-1] if len(a.history) > len(b.history) else {}
    rescaled = step.get("step") in ("normalize", "derivative")      # the y scale is different afterwards
    same_x = b.x.shape == a.x.shape and np.allclose(b.x, a.x)
    if removed == "auto":
        removed = same_x and not rescaled
    elif removed and not same_x:
        raise ValueError("Cannot show what was removed: before and after have different x (resample first).")
    with styled(look):
        palette = plt.rcParams["axes.prop_cycle"].by_key().get("color", ["tab:blue", "tab:red"])
        main, second = palette[0], palette[1 % len(palette)]
        if removed:
            w, h = plt.rcParams["figure.figsize"]
            fig, (ax, low) = plt.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [2.2, 1]},
                                          figsize=(w, max(h, w * 0.6)))
        else:
            fig, ax = plt.subplots()
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
        if removed:
            low.plot(b.x, b.y - a.y, color="k")
            low.axhline(0, color="0.6", lw=0.6, marker="None")
            low.set_ylabel("removed")
            _shade(low, spikes, look)
        if region:
            _zoom(ax, region, drawn)
            if removed:
                m = (b.x >= min(region)) & (b.x <= max(region))
                d = (b.y - a.y)[m]
                if d.size:
                    pad = 0.05 * (np.ptp(d) or 1)
                    low.set_ylim(d.min() - pad, d.max() + pad)
        title = title if title is not None else (_describe(step) if step else "")
        title = f"{a.name}: {title}" if a.name and title else (a.name or title)
        legend(ax, look, 2, force=True)
        ax.set_title(title, fontsize="medium")
        ax.set_ylabel(b.y_unit or "Intensity")
        bottom = low if removed else ax
        bottom.set_xlabel(xlabel if xlabel is not None else (b.x_unit or "x"))
        if invert_x and not ax.xaxis_inverted():
            ax.invert_xaxis()
        for axis in fig.axes:
            finish_axes(axis, look if axis is ax else ({**look, "aspect": None} if look else None))
        if rescaled:                                                    # the right axis label in the colour of its line
            target.yaxis.label.set_color(main)
        fig.tight_layout()
        _save(ax, save, look)
    return ax


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


__all__ = ["plot", "compare", "scatter", "KINDS"]
