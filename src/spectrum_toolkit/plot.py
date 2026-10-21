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
from .style import export, finish_axes, get_style, legend, styled

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


def _shade(ax, ranges, color="tab:red", alpha=0.15):
    """Shade x ranges (e.g. spikes or a region of interest) on the axes."""
    for lo, hi in ranges:
        if lo == hi:                                             # a 1-point range: make it visible
            lo, hi = lo - 0.5, hi + 0.5
        ax.axvspan(lo, hi, color=color, alpha=alpha, lw=0)


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


def _label_peaks(ax, x, y, peaks, look, region=None):
    """Write the position above the most prominent bands of one line.

    peaks : number of bands to label (the most prominent), or a list of x
        positions (each labelled at the highest point within 3 points).
    """
    from scipy.signal import find_peaks
    order = np.argsort(x)
    x, y = x[order], y[order]
    if region:
        keep = (x >= min(region)) & (x <= max(region))
        x, y = x[keep], y[keep]
    if isinstance(peaks, (int, np.integer)):
        # Prominence: how far a band stands out from the valleys on both sides,
        # so noise wiggles on a big band are not labelled.
        idx, props = find_peaks(y, prominence=0.02 * np.ptp(y), distance=3)
        idx = idx[np.argsort(props["prominences"])[::-1][:int(peaks)]]
    else:
        idx = [int(np.argmax(np.where(np.abs(np.arange(x.size) - np.argmin(np.abs(x - p))) <= 3, y, -np.inf)))
               for p in peaks]
    size = (look["font_size"] if look else 10) * 0.75
    pad = 0.02 * np.ptp(y)
    for i in idx:
        xp = x[i]
        if 0 < i < x.size - 1:
            # Position between the points: top of the parabola through the
            # highest point and its two neighbours (standard peak refinement).
            a, b, _ = np.polyfit(x[i - 1:i + 2], y[i - 1:i + 2], 2)
            if a < 0:
                xp = -b / (2 * a)
        ax.annotate(f"{xp:.0f}", (x[i], y[i] + pad), ha="center", va="bottom", rotation=90,
                    fontsize=size, annotation_clip=False)
    if len(idx):
        top = max(y[i] for i in idx) + 0.12 * np.ptp(y)          # room for the labels
        if top > ax.get_ylim()[1]:
            ax.set_ylim(ax.get_ylim()[0], top)


def _marks(ax, marks, look):
    """Vertical dashed lines at given x, labelled at the top (dict x -> label, or a list of x)."""
    items = marks.items() if isinstance(marks, dict) else [(m, f"{m:g}") for m in marks]
    size = (look["font_size"] if look else 10) * 0.75
    for xm, text in items:
        ax.axvline(xm, color="0.4", ls=":", lw=0.9, zorder=0.6, marker="None")
        ax.annotate(text, (xm, 1.0), xycoords=("data", "axes fraction"), ha="center", va="bottom",
                    rotation=90, fontsize=size, annotation_clip=False)


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


def plot(*data: Data, kind: str = "lines", ax=None, region: tuple[float, float] | None = None,
         offset: float | None = None, labels: list[str] | None = None, color=None, highlight=None,
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
    color : one colour for every line; default the style's colours.
    highlight : "spikes" shades the spikes removed by despike (from history);
        a list of (lo, hi) shades those x ranges; None (default) shades nothing.
    peaks : label band positions on the first line: a number (that many of
        the most prominent bands) or a list of x positions.
    marks : vertical reference lines: a list of x, or a dict x -> label.
    title, xlabel, ylabel : text; the labels default to the units.
    invert_x : draw x from high to low.
    style : a preset ("clean" default, "publication", "matlab", "matplotlib"),
        a dict, or a .json file; see ``spectrum_toolkit.style``.
    save : file name to save to (type from the extension; dpi and colour
        mode from the style).
    **style_settings : any style setting by name, e.g. aspect="square",
        box_width=2, line_width=1.5, colors="matlab", ticks="in", grid=False.

    Returns the matplotlib Axes.
    """
    if not data:
        raise ValueError("Nothing to plot: give at least one Spectrum or SpectrumCollection.")
    if kind not in KINDS:
        raise ValueError(f"Unknown kind {kind!r}. Choose one of: {', '.join(KINDS)}.")
    look = get_style(style, **style_settings)
    plt = _plt()
    with styled(look):
        if ax is None:
            _, ax = plt.subplots()
        rows = [_rows(item) for item in data]                       # (x, Y, names) per item
        n_total = sum(len(Y) for _, Y, _ in rows)
        drawn = []                                                   # (x, y) actually drawn, for zooming
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
            for i, (x, Y, _) in enumerate(rows):
                m, sd = Y.mean(axis=0), Y.std(axis=0)
                line, = ax.plot(x, m, label=f"{labels[i]} (n={len(Y)})", color=color)
                ax.fill_between(x, m - sd, m + sd, color=line.get_color(), alpha=0.25, lw=0)
                drawn += [(x, m - sd), (x, m + sd)]
            first_line = (rows[0][0], rows[0][1].mean(axis=0))
            n_lines = len(rows)
        else:
            all_names = [n for _, _, names in rows for n in names]
            labels = list(labels) if labels else all_names
            if len(labels) != n_total:
                raise ValueError(f"Got {len(labels)} labels for {n_total} spectra.")
            cmap = plt.get_cmap(look["cmap"] if look else "viridis")
            colors = cmap(np.linspace(0, 0.9, n_total)) if n_total > _MANY else [None] * n_total
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
                    y = y + (k * offset if kind == "stack" else 0)
                    drawn.append((x, y))
                    if n_total > _HUGE:
                        segments.append(np.column_stack([x, y]))      # drawn together below, much faster
                    else:
                        ax.plot(x, y, label=labels[k], color=color if color is not None else colors[k])
                    k += 1
            if segments:
                from matplotlib.collections import LineCollection
                width = (look["line_width"] if look else 1.0) * 0.4
                ax.add_collection(LineCollection(segments, colors=color if color is not None else colors,
                                                 linewidths=width, alpha=0.35))
                ax.autoscale_view()
            if kind == "stack":
                ax.set_yticks([])                                    # absolute values mean little once shifted
            first_line = drawn[0]
            n_lines = n_total
        if highlight == "spikes":
            _shade(ax, [r for item in data for r in _spike_ranges(item)])
        elif highlight:
            _shade(ax, highlight, color="tab:orange")
        if region:
            _zoom(ax, region, drawn)
        if peaks is not None:
            _label_peaks(ax, *first_line, peaks, look, region)
        if marks:
            _marks(ax, marks, look)
        _labels(ax, data[0], look, xlabel, ylabel if kind != "stack" else (ylabel or "Intensity (shifted)"),
                title, invert_x)
        legend(ax, look, n_lines)
        finish_axes(ax, look)
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
        _shade(ax, spikes)
        if removed:
            low.plot(b.x, b.y - a.y, color="k")
            low.axhline(0, color="0.6", lw=0.6, marker="None")
            low.set_ylabel("removed")
            _shade(low, spikes)
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
