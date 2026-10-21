"""Figure styles: every visual setting of a plot in one plain dictionary,
and saving figures (name, folder, file type, DPI, RGB or CMYK).

A style is a dict of the settings in ``SETTINGS`` (below). Start from a
preset and change only what you want:

>>> import spectrum_toolkit as stk
>>> look = stk.get_style("publication", box_width=2, aspect="square")
>>> look["box_width"], look["ticks"]
(2, 'in')

Use it in any plot, in four equivalent ways::

    c.plot(style="publication")                       # a preset
    c.plot(style="publication", box_width=2)          # a preset plus changes
    c.plot(style={"preset": "matlab", "colors": "colorblind"})
    c.plot(style="my_style.json")                     # saved with stk.save_style

``stk.set_style(...)`` makes a style the default for every later plot in
the session. Because a style is plain data (it can be stored as JSON), the
website can later send the same settings to the server.

Presets
-------
"clean"        default: light grid, open box (left and bottom lines only),
               ticks outward, wide figure for looking at spectra.
"publication"  closed box, ticks inward on all four sides, no grid.
"matlab"       like Vikas's MATLAB figures (main.m / separation1.tiff):
               MATLAB colours, square axes, bold Arial, thick grey box with
               black tick labels, ticks inward, no legend box.
"matplotlib"   matplotlib's own defaults.

Saving
------
``stk.export(ax, "name", folder=..., format="tiff", dpi=1200, color="cmyk")``.
Formats: png, tiff, jpg (pictures, need a dpi), pdf, svg, eps (vector:
sharp at any size). CMYK is possible for tiff and jpg (the colours are
converted with a simple formula, not a printer profile; journals usually
accept RGB and convert themselves).
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any

# ------------------------------------------------------------------ colours
# Named colour lists for successive lines.
PALETTES: dict[str, list] = {
    # MATLAB's default "colororder" (R2014b and later), as RGB fractions.
    "matlab": [(0, 0.4470, 0.7410), (0.8500, 0.3250, 0.0980), (0.9290, 0.6940, 0.1250),
               (0.4940, 0.1840, 0.5560), (0.4660, 0.6740, 0.1880), (0.3010, 0.7450, 0.9330),
               (0.6350, 0.0780, 0.1840)],
    # matplotlib's default ("tab10").
    "matplotlib": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2",
                   "#7f7f7f", "#bcbd22", "#17becf"],
    # Okabe & Ito (2008): distinguishable with every common kind of colour blindness.
    "colorblind": ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#F0E442", "#000000"],
    # Black and greys, for print in black and white.
    "black": ["#000000", "#555555", "#888888", "#bbbbbb"],
}

# Figure sizes by name, (width, height) in centimetres.
SIZES: dict[str, tuple[float, float]] = {
    "screen": (23, 11.5),        # wide, for looking at spectra on a monitor
    "single": (8.5, 6.4),        # one journal column (about 8.5 cm), 4:3
    "double": (17.8, 8.9),       # two journal columns (about 17.8 cm), 2:1
    "square": (12, 12),
    "slide": (25.4, 14.3),       # 16:9 presentation slide
}

# ------------------------------------------------------------------ settings
# Every setting, its default (the "clean" preset) and what it does.
SETTINGS: dict[str, tuple[Any, str]] = {
    # size and shape
    "size": ("screen", 'figure size: a name in SIZES or (width, height) in "units"'),
    "units": ("cm", '"cm" or "in" for size'),
    "aspect": (None, 'plot area shape: None (fills the figure), "square", or height/width e.g. 0.75'),
    # text
    "font": ("sans-serif", 'font name, e.g. "Arial", "Times New Roman"; falls back if not installed'),
    "font_size": (10, "tick label size in points"),
    "font_weight": ("normal", '"normal" or "bold": all text'),
    "label_size": (11, "axis label size in points"),
    "label_weight": ("normal", '"normal" or "bold": axis labels'),
    "label_color": ("black", "axis label colour"),
    "title_size": (11, "title size in points"),
    # box (the frame around the plot)
    "box": ("open", '"closed" (all four sides), "open" (left and bottom) or "none"'),
    "box_width": (0.8, "box line width in points"),
    "box_color": ("black", "box line colour"),
    "background": ("white", 'background colour; "none" for transparent'),
    # ticks
    "ticks": ("out", '"in", "out" or "both" (through the box line)'),
    "tick_length": (4.0, "tick length in points"),
    "tick_width": (None, "tick line width; None = same as box_width"),
    "tick_color": (None, "tick mark colour; None = same as box_color"),
    "tick_sides": (("bottom", "left"), 'sides with tick marks: any of "bottom", "top", "left", "right"'),
    "tick_label_sides": (("bottom", "left"), "sides with tick labels (numbers)"),
    "tick_label_color": ("black", "tick label colour"),
    "minor_ticks": (False, "small ticks between the numbered ones"),
    "x_tick_step": (None, "distance between x ticks, e.g. 200; None = automatic"),
    "y_tick_step": (None, "distance between y ticks; None = automatic"),
    "x_tick_format": (None, 'number format of x tick labels, e.g. "%.2f"; None = automatic'),
    "y_tick_format": (None, "number format of y tick labels"),
    # grid
    "grid": (True, "grid lines on or off"),
    "grid_color": ("#b0b0b0", "grid colour"),
    "grid_style": ("-", '"-", "--", ":" or "-."'),
    "grid_width": (0.6, "grid line width"),
    "grid_alpha": (0.4, "grid opacity 0 to 1"),
    # spectra (data lines)
    "line_width": (1.0, "spectrum line width in points"),
    "line_style": ("-", '"-" solid, "--" dashed, ":" dotted, "-." dash-dot, "none" (markers only)'),
    "marker": (None, 'point marker: None, "o", ".", "s", "^", "x" ...'),
    "marker_size": (3.0, "marker size in points"),
    "colors": ("matplotlib", "colours of successive lines: a name in PALETTES or a list of colours"),
    "cmap": ("viridis", "colour map for many spectra (more than 10) and images"),
    # legend
    "legend": ("auto", 'True, False or "auto" (shown for 2 to 10 lines)'),
    "legend_location": ("best", 'e.g. "best", "upper right", "outside" (right of the plot)'),
    "legend_size": (9, "legend text size"),
    "legend_weight": ("normal", '"normal" or "bold"'),
    "legend_box": (False, "frame around the legend"),
    # reference lines
    "zero_lines": (None, 'dashed lines at 0: None, "x" (horizontal y=0), "y" (vertical x=0) or "both"'),
    "zero_line_style": ("--", "style of the zero lines"),
    "zero_line_width": (1.0, "width of the zero lines"),
    "zero_line_color": ("black", "colour of the zero lines"),
    # saving
    "dpi": (300, "dots per inch for png, tiff and jpg"),
    "format": ("png", "file type when the name has no extension: png, tiff, jpg, pdf, svg, eps"),
    "color_mode": ("rgb", '"rgb" or "cmyk" (cmyk only for tiff and jpg)'),
}

DEFAULTS: dict[str, Any] = {k: v for k, (v, _) in SETTINGS.items()}

PRESETS: dict[str, dict[str, Any]] = {
    "clean": {},
    "publication": {"size": (16, 11), "box": "closed", "ticks": "in", "grid": False,
                    "tick_sides": ("bottom", "top", "left", "right"), "font_size": 12, "label_size": 13,
                    "box_width": 1.0, "line_width": 1.2, "legend_size": 11},
    "matlab": {"size": (14, 14), "aspect": "square", "font": "Arial", "font_size": 15, "font_weight": "bold",
               "label_size": 18, "label_weight": "bold", "box": "closed", "box_width": 2.0,
               "box_color": (0.7, 0.7, 0.7), "tick_label_color": "black", "ticks": "in", "tick_length": 6,
               "tick_sides": ("bottom", "top", "left", "right"), "grid": False, "colors": "matlab",
               "line_width": 1.5, "legend_size": 12, "legend_weight": "bold", "legend_box": False,
               "dpi": 1200, "format": "tiff"},
    "matplotlib": None,                                    # special: no changes at all
}

_session_default: dict[str, Any] = {"preset": "clean"}   # changed by set_style()

# Fonts tried after the chosen one, so a missing font never stops a plot.
_FALLBACK_FONTS = ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"]


def _check(settings: dict) -> None:
    """Unknown setting names are an error, with the list of valid ones."""
    wrong = set(settings) - set(SETTINGS) - {"preset"}
    if wrong:
        raise ValueError(f"Unknown style setting(s) {sorted(wrong)}. Valid settings: {', '.join(SETTINGS)} "
                         "(see spectrum_toolkit.style.SETTINGS for what each does).")


def get_style(style: str | dict | Path | None = None, **changes: Any) -> dict[str, Any] | None:
    """The complete style (every setting) for a preset, dict or JSON file, plus changes.

    Parameters
    ----------
    style : None (the session default, see set_style), a preset name, a path
        to a JSON file saved with save_style, or a dict of settings (with an
        optional "preset" key it starts from; otherwise from the session default).
    **changes : settings to change on top, e.g. box_width=2.

    Returns a dict with every setting, or None for the "matplotlib" preset
    without changes (meaning: leave matplotlib alone).
    """
    if style is None:
        style = dict(_session_default)
    if isinstance(style, Path) or (isinstance(style, str) and style.endswith(".json")):
        style = json.loads(Path(style).read_text(encoding="utf-8"))
    if isinstance(style, str):
        style = {"preset": style}
    style = dict(style)
    _check(style)
    _check(changes)
    preset = style.pop("preset", None)
    if preset is None:                                         # a dict without preset: build on the session default
        base = get_style(None) or {}
    else:
        if preset not in PRESETS:
            raise ValueError(f"Unknown style preset {preset!r}. Choose one of: {', '.join(PRESETS)}, "
                             "or give a dict or a .json file.")
        if PRESETS[preset] is None:
            if not style and not changes:
                return None
            base = dict(DEFAULTS)
        else:
            base = {**DEFAULTS, **PRESETS[preset]}
    full = {**base, **style, **changes}
    if full["box"] not in ("closed", "open", "none"):
        raise ValueError('box must be "closed", "open" or "none".')
    if full["ticks"] not in ("in", "out", "both"):
        raise ValueError('ticks must be "in", "out" or "both".')
    return full


def set_style(style: str | dict | Path | None = "clean", **changes: Any) -> None:
    """Make a style the default for all later plots in this session.

    >>> set_style("publication", box_width=1.5)   # every plot from now on
    >>> set_style()                                 # back to "clean"
    """
    global _session_default
    full = get_style(style if style is not None else "clean", **changes)
    _session_default = {"preset": "matplotlib"} if full is None else {"preset": "clean", **full}


def save_style(style: str | dict, path: str | Path, **changes: Any) -> Path:
    """Save a style (every setting) to a JSON file, to reuse with style="file.json"."""
    full = get_style(style, **changes) or {}
    path = Path(path).with_suffix(".json")
    path.write_text(json.dumps({"preset": "clean", **full}, indent=2, default=list), encoding="utf-8")
    return path


def _colors(look: dict) -> list:
    """The list of line colours of a style."""
    c = look["colors"]
    if isinstance(c, str):
        if c not in PALETTES:
            raise ValueError(f"Unknown colours {c!r}. Choose one of: {', '.join(PALETTES)}, or give a list.")
        return PALETTES[c]
    return list(c)


def _size_inches(look: dict) -> tuple[float, float]:
    """Figure size in inches from the style's size and units."""
    size = look["size"]
    if isinstance(size, str):
        if size not in SIZES:
            raise ValueError(f"Unknown size {size!r}. Choose one of: {', '.join(SIZES)}, or give (width, height).")
        return SIZES[size][0] / 2.54, SIZES[size][1] / 2.54
    w, h = size
    return (w / 2.54, h / 2.54) if look["units"] == "cm" else (w, h)


_warned_fonts: set = set()


def _fonts(wanted: str) -> list[str]:
    """The wanted font followed by fallbacks, keeping only fonts installed on
    this computer (so matplotlib does not print a warning for each one)."""
    from matplotlib import font_manager
    installed = {f.name for f in font_manager.fontManager.ttflist}
    if wanted in ("sans-serif", "serif", "monospace"):              # generic family names always work
        return [wanted, "DejaVu Sans"]
    # DejaVu Sans (always installed with matplotlib) comes last: it has symbols
    # such as ⁻ ¹ ° that some fonts lack, and matplotlib takes missing symbols
    # from the next font in the list.
    found = [f for f in [wanted] + _FALLBACK_FONTS if f in installed]
    if wanted not in installed and wanted not in _warned_fonts:
        _warned_fonts.add(wanted)
        import warnings
        warnings.warn(f"Font {wanted!r} is not installed here; using {(found or ['sans-serif'])[0]!r} instead.",
                      stacklevel=4)
    return found or ["sans-serif", "DejaVu Sans"]


def rc_settings(look: dict) -> dict[str, Any]:
    """Translate a style into matplotlib settings (rcParams)."""
    from cycler import cycler                                   # installed with matplotlib
    sides = set(look["tick_sides"])
    labels = set(look["tick_label_sides"])
    tick_w = look["tick_width"] if look["tick_width"] is not None else look["box_width"]
    tick_c = look["tick_color"] if look["tick_color"] is not None else look["box_color"]
    direction = {"in": "in", "out": "out", "both": "inout"}[look["ticks"]]
    font = _fonts(look["font"])
    rc = {
        "figure.figsize": _size_inches(look),
        "font.family": font,
        "font.size": look["font_size"],
        "font.weight": look["font_weight"],
        "axes.labelsize": look["label_size"],
        "axes.labelweight": look["label_weight"],
        "axes.labelcolor": look["label_color"],
        "axes.titlesize": look["title_size"],
        "axes.titleweight": look["font_weight"],
        "axes.linewidth": look["box_width"],
        "axes.edgecolor": look["box_color"],
        "axes.spines.top": look["box"] == "closed",
        "axes.spines.right": look["box"] == "closed",
        "axes.spines.left": look["box"] != "none",
        "axes.spines.bottom": look["box"] != "none",
        "axes.facecolor": look["background"],
        "figure.facecolor": look["background"],
        "savefig.facecolor": look["background"],
        "axes.prop_cycle": cycler(color=_colors(look)),
        "axes.grid": bool(look["grid"]),
        "grid.color": look["grid_color"],
        "grid.linestyle": look["grid_style"],
        "grid.linewidth": look["grid_width"],
        "grid.alpha": look["grid_alpha"],
        "lines.linewidth": look["line_width"],
        "lines.linestyle": "None" if look["line_style"] == "none" else look["line_style"],
        # "none" line style without a marker would draw nothing: use small dots then.
        "lines.marker": look["marker"] or ("." if look["line_style"] == "none" else "None"),
        "lines.markersize": look["marker_size"],
        "image.cmap": look["cmap"],
        "legend.fontsize": look["legend_size"],
        "legend.frameon": bool(look["legend_box"]),
        "savefig.dpi": look["dpi"],
        "savefig.format": look["format"],
    }
    for axis, (lo, hi) in (("xtick", ("bottom", "top")), ("ytick", ("left", "right"))):
        rc.update({
            f"{axis}.{lo}": lo in sides, f"{axis}.{hi}": hi in sides,
            f"{axis}.label{lo}": lo in labels, f"{axis}.label{hi}": hi in labels,
            f"{axis}.direction": direction,
            f"{axis}.major.size": look["tick_length"], f"{axis}.minor.size": look["tick_length"] * 0.55,
            f"{axis}.major.width": tick_w, f"{axis}.minor.width": tick_w * 0.75,
            f"{axis}.color": tick_c, f"{axis}.labelcolor": look["tick_label_color"],
            f"{axis}.labelsize": look["font_size"],
            f"{axis}.minor.visible": bool(look["minor_ticks"]),
        })
    return rc


@contextmanager
def styled(look: dict | None):
    """Apply a full style (from get_style) while a figure is drawn, then restore matplotlib."""
    import matplotlib as mpl
    if look is None:                                            # "matplotlib" preset: change nothing
        yield
        return
    with mpl.rc_context(rc_settings(look)):
        yield
        # Jupyter switches matplotlib to interactive mode when the first figure
        # is made, which can happen inside this block. Keep it on afterwards, or
        # later plots in the notebook would not be shown.
        interactive = mpl.is_interactive()
    mpl.interactive(interactive)


def finish_axes(ax, look: dict | None) -> None:
    """Settings that matplotlib cannot set in advance: square plot area, tick
    spacing and number format, zero lines, legend weight."""
    if look is None:
        return
    import matplotlib.ticker as mticker
    if look["aspect"] == "square":
        ax.set_box_aspect(1)
    elif look["aspect"] is not None:
        ax.set_box_aspect(float(look["aspect"]))
    for axis, step, fmt in ((ax.xaxis, look["x_tick_step"], look["x_tick_format"]),
                            (ax.yaxis, look["y_tick_step"], look["y_tick_format"])):
        if step:
            axis.set_major_locator(mticker.MultipleLocator(step))
        if fmt:
            axis.set_major_formatter(mticker.FormatStrFormatter(fmt))
    z = look["zero_lines"]
    kw = dict(color=look["zero_line_color"], ls=look["zero_line_style"], lw=look["zero_line_width"],
              zorder=0.5, marker="None")
    if z in ("x", "both"):
        ax.axhline(0, **kw)
    if z in ("y", "both"):
        ax.axvline(0, **kw)
    legend = ax.get_legend()
    if legend is not None:
        for text in legend.get_texts():
            text.set_fontweight(look["legend_weight"])


def legend(ax, look: dict | None, n_lines: int, force: bool | str | None = None) -> None:
    """Draw the legend according to the style ("auto": for 2 to 10 lines)."""
    show = look["legend"] if look else "auto"
    if force is not None and force != "auto":
        show = force
    if show is True or (show == "auto" and 1 < n_lines <= 10):
        where = look["legend_location"] if look else "best"
        if where == "outside":
            ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1))
        else:
            ax.legend(loc=where)


# ------------------------------------------------------------------ saving
_RASTER = ("png", "tiff", "tif", "jpg", "jpeg")
_VECTOR = ("pdf", "svg", "eps")


def export(fig_or_ax, name: str | Path = "figure", *, folder: str | Path | None = None, format: str | None = None,
           dpi: int | None = None, color: str | None = None, transparent: bool = False,
           style: str | dict | None = None) -> Path:
    """Save a figure.

    Parameters
    ----------
    fig_or_ax : the Axes a plot function returned, or a matplotlib Figure.
    name : file name, with or without extension (e.g. "fig2" or "fig2.tiff").
    folder : folder to save in (made if missing); default the current folder.
    format : png, tiff, jpg, pdf, svg or eps; default from the name's
        extension, else the style's "format".
    dpi : resolution for png/tiff/jpg; default the style's "dpi".
    color : "rgb" or "cmyk"; default the style's "color_mode".
    transparent : transparent background (png, tiff, pdf, svg).

    Returns the path of the saved file.
    """
    from io import BytesIO
    look = get_style(style) or dict(DEFAULTS)
    fig = getattr(fig_or_ax, "figure", fig_or_ax)
    path = Path(name)
    if folder is not None:
        path = Path(folder) / path
    fmt = (format or path.suffix.lstrip(".") or look["format"]).lower()
    if fmt not in _RASTER + _VECTOR:
        raise ValueError(f"Unknown file type {fmt!r}. Choose one of: png, tiff, jpg, pdf, svg, eps.")
    fmt = {"tif": "tiff", "jpeg": "jpg"}.get(fmt, fmt)
    path = path.with_suffix("." + fmt)
    path.parent.mkdir(parents=True, exist_ok=True)
    dpi = dpi or look["dpi"]
    color = (color or look["color_mode"]).lower()
    if color not in ("rgb", "cmyk"):
        raise ValueError('color must be "rgb" or "cmyk".')
    if color == "cmyk" and fmt not in ("tiff", "jpg"):
        raise ValueError(f"CMYK is possible for tiff and jpg files, not {fmt}. Use format='tiff', or color='rgb'.")
    if color == "rgb" and fmt != "tiff":
        fig.savefig(path, format=fmt, dpi=dpi, bbox_inches="tight", transparent=transparent)
        return path
    # tiff (any colour) and cmyk jpg: draw to a picture first, then let Pillow
    # write it, so we can convert colours and compress the tiff losslessly (LZW).
    from PIL import Image
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight", transparent=transparent and color == "rgb")
    buffer.seek(0)
    image = Image.open(buffer)
    image = image.convert("CMYK") if color == "cmyk" else image
    if fmt == "tiff":
        image.save(path, format="TIFF", dpi=(dpi, dpi), compression="tiff_lzw")
    else:
        image.save(path, format="JPEG", dpi=(dpi, dpi), quality=95)
    return path


__all__ = ["get_style", "set_style", "save_style", "export", "SETTINGS", "PRESETS", "PALETTES", "SIZES"]
