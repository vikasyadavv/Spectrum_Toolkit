"""Figure styles: every visual setting of a plot in one plain dictionary,
and saving figures (name, folder, file type, DPI, RGB or CMYK).

A style is a dict of the settings in ``SETTINGS`` (below). Start from a
preset and change only what you want:

>>> import spectrum_toolkit as stk
>>> look = stk.get_style("publication", box_width=2, aspect="square")
>>> look["box_width"], look["tick_direction"]
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
#
# Naming rule: every element of a figure has its own settings, and the last
# word of a name always means the same thing:
#   _color  colour (see "Colours" in docs/plotting.md: names, hex, RGB, RGBA, grey, cmyk(...))
#   _alpha  transparency, 0 (invisible) to 1 (solid)
#   _width  line width in points          _style  line type: "-", "--", ":", "-."
#   _size   text or marker size in points  _weight "normal" or "bold"
#   _italic True or False                  _font   font name
# A default of None means "not set: use the more general setting" (see
# _GENERAL below), e.g. top_tick_length None -> x_tick_length -> tick_length.
SETTINGS: dict[str, tuple[Any, str]] = {
    # size and shape
    "size": ("screen", 'figure size: a name in SIZES or (width, height) in "units"'),
    "units": ("cm", '"cm" or "in" for size'),
    "aspect": (None, 'plot area shape: None (fills the figure), "square", or height/width e.g. 0.75'),
    # text: the base for every text in the figure
    "font": ("sans-serif", 'font name for all text, e.g. "Arial", "Times New Roman"; falls back if not installed'),
    "font_size": (10, "base text size in points (tick labels use it unless tick_label_size is set)"),
    "font_weight": ("normal", '"normal" or "bold": all text unless a more specific _weight is set'),
    # axis labels (x and y); xlabel_... and ylabel_... (below) set one of them
    "label_size": (11, "axis label size in points"),
    "label_weight": ("normal", '"normal" or "bold": axis labels'),
    "label_color": ("black", "axis label colour"),
    "label_alpha": (1.0, "axis label transparency, 0 to 1"),
    "label_italic": (False, "axis labels in italics"),
    "label_font": (None, "axis label font; None = font"),
    "label_pad": (4.0, "distance between the axis label and the tick labels, in points"),
    # title
    "title_size": (11, "title size in points"),
    "title_weight": (None, '"normal" or "bold"; None = font_weight'),
    "title_color": ("black", "title colour"),
    "title_alpha": (1.0, "title transparency, 0 to 1"),
    "title_italic": (False, "title in italics"),
    "title_font": (None, "title font; None = font"),
    "title_location": ("center", '"left", "center" or "right"'),
    "title_pad": (6.0, "distance between the title and the plot, in points"),
    # box (the frame around the plot); bottom_box_..., top_box_... (below) set one side
    "box": ("open", '"closed" (all four sides), "open" (left and bottom) or "none"'),
    "box_width": (0.8, "box line width in points"),
    "box_color": ("black", "box line colour"),
    "box_alpha": (1.0, "box line transparency, 0 to 1"),
    "box_style": ("-", 'box line type: "-", "--", ":" or "-."'),
    "background": ("white", 'figure background colour (around the plot); "none" for transparent'),
    "background_alpha": (1.0, "figure background transparency, 0 to 1"),
    "plot_background": (None, 'background colour inside the box; None = background'),
    "plot_background_alpha": (None, "transparency inside the box, 0 to 1; None = background_alpha"),
    # ticks; x_tick_... / y_tick_... set one axis and bottom_tick_... / top_tick_... /
    # left_tick_... / right_tick_... one side (below), each falling back to these
    "tick_direction": ("out", '"in", "out" or "both" (through the box line); old name: ticks'),
    "tick_length": (4.0, "tick length in points"),
    "tick_width": (None, "tick line width; None = box_width"),
    "tick_color": (None, "tick mark colour; None = box_color"),
    "tick_alpha": (1.0, "tick mark transparency, 0 to 1"),
    "tick_sides": (("bottom", "left"), 'sides with tick marks: any of "bottom", "top", "left", "right"'),
    "tick_label_sides": (("bottom", "left"), "sides with tick labels (numbers)"),
    "tick_label_size": (None, "tick label (number) size in points; None = font_size"),
    "tick_label_color": ("black", "tick label colour"),
    "tick_label_alpha": (1.0, "tick label transparency, 0 to 1"),
    "tick_label_weight": (None, '"normal" or "bold"; None = font_weight'),
    "tick_label_italic": (False, "tick labels in italics"),
    "tick_label_font": (None, "tick label font; None = font"),
    "tick_label_rotation": (0, "tick label rotation in degrees, e.g. 45 or 90"),
    "tick_label_pad": (3.5, "distance between tick and tick label, in points"),
    "minor_ticks": (False, "small ticks between the numbered ones"),
    "minor_tick_length": (None, "minor tick length in points; None = 0.55 x tick_length"),
    "minor_tick_count": (None, "number of minor ticks between two numbered ticks; None = automatic"),
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
    # legend: when and where
    "legend": ("auto", 'True, False or "auto" (shown for 2 to 10 lines)'),
    "legend_location": ("best", 'e.g. "best", "upper right", "lower left", "outside" (right of the plot)'),
    "legend_position": (None, "exact place of the legend's corner as [x, y], 0 to 1 of the plot; overrides legend_location"),
    "legend_columns": (1, "number of columns of legend entries"),
    "legend_order": ("normal", '"normal" (as drawn) or "reverse"'),
    # legend: entry text
    "legend_size": (9, "legend text size"),
    "legend_weight": ("normal", '"normal" or "bold"'),
    "legend_color": ("black", "legend text colour"),
    "legend_alpha": (1.0, "legend text transparency, 0 to 1"),
    "legend_italic": (False, "legend text in italics"),
    "legend_font": (None, "legend font; None = font"),
    # legend: title
    "legend_title": (None, "a heading above the legend entries"),
    "legend_title_size": (None, "legend heading size; None = legend_size"),
    "legend_title_weight": ("bold", '"normal" or "bold"'),
    # legend: frame
    "legend_box": (False, "frame around the legend"),
    "legend_box_color": ("#cccccc", "frame line colour"),
    "legend_box_width": (0.8, "frame line width"),
    "legend_box_alpha": (1.0, "frame line transparency, 0 to 1"),
    "legend_box_round": (True, "rounded frame corners"),
    "legend_fill": ("white", 'colour inside the legend frame; "none" for no fill'),
    "legend_fill_alpha": (0.8, "legend fill transparency, 0 to 1"),
    "legend_shadow": (False, "a shadow behind the legend frame"),
    # legend: entry layout
    "legend_line_length": (2.0, "length of the line sample, in font sizes"),
    "legend_marker_scale": (1.0, "marker size in the legend relative to the plot"),
    "legend_spacing": (0.5, "vertical space between entries, in font sizes"),
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

# Settings for one axis or one side. Each starts as None (use the general
# setting) and is built from the lists below, so every side has exactly the
# same settings and none can be forgotten.
SIDES = ("bottom", "top", "left", "right")
AXIS_OF_SIDE = {"bottom": "x", "top": "x", "left": "y", "right": "y"}
_TICK_KEYS = ("tick_direction", "tick_length", "tick_width", "tick_color", "tick_alpha",
              "tick_label_size", "tick_label_color", "tick_label_alpha", "tick_label_weight",
              "tick_label_italic", "tick_label_font", "tick_label_rotation")
_AXIS_ONLY_KEYS = ("tick_label_pad", "minor_ticks", "minor_tick_length", "minor_tick_count")
_BOX_KEYS = ("box_width", "box_color", "box_alpha", "box_style")
_LABEL_KEYS = ("label_size", "label_weight", "label_color", "label_alpha", "label_italic", "label_font",
               "label_pad")
for _axis in ("x", "y"):
    # x_tick_length, y_tick_color, ... : one axis (both of its sides)
    for _key in _TICK_KEYS + _AXIS_ONLY_KEYS:
        SETTINGS[f"{_axis}_{_key}"] = (None, f"{_key} for the {_axis} axis only; None = {_key}")
    # xlabel_size, ylabel_color, ... : one axis label
    for _key in _LABEL_KEYS:
        SETTINGS[f"{_axis}{_key}"] = (None, f"{_key} for the {_axis} axis label only; None = {_key}")
    SETTINGS[f"{_axis}label_rotation"] = (0 if _axis == "x" else 90, f"{_axis} axis label rotation in degrees")
for _side in SIDES:
    _a = AXIS_OF_SIDE[_side]
    # bottom_ticks, top_tick_labels: on/off for one side (None = tick_sides / tick_label_sides)
    SETTINGS[f"{_side}_ticks"] = (None, f"tick marks on the {_side} side: True/False; None = tick_sides")
    SETTINGS[f"{_side}_tick_labels"] = (None, f"tick labels on the {_side} side: True/False; "
                                              "None = tick_label_sides")
    # top_tick_length, right_tick_color, ... : one side
    for _key in _TICK_KEYS:
        SETTINGS[f"{_side}_{_key}"] = (None, f"{_key} for the {_side} side only; None = {_a}_{_key}")
    # left_box, top_box_color, ... : one side of the box
    SETTINGS[f"{_side}_box"] = (None, f"box line on the {_side} side: True/False; None = box")
    for _key in _BOX_KEYS:
        SETTINGS[f"{_side}_{_key}"] = (None, f"{_key} for the {_side} side only; None = {_key}")

# Allowed values of the settings that are a choice (checked in get_style).
CHOICES: dict[str, tuple] = {
    "box": ("closed", "open", "none"),
    "tick_direction": ("in", "out", "both"),
    "title_location": ("left", "center", "right"),
    "legend_order": ("normal", "reverse"),
}
_WEIGHTS = ("normal", "bold")
_LINE_STYLES = ("-", "--", ":", "-.")

DEFAULTS: dict[str, Any] = {k: v for k, (v, _) in SETTINGS.items()}

PRESETS: dict[str, dict[str, Any]] = {
    "clean": {},
    "publication": {"size": (16, 11), "box": "closed", "tick_direction": "in", "grid": False,
                    "tick_sides": ("bottom", "top", "left", "right"), "font_size": 12, "label_size": 13,
                    "box_width": 1.0, "line_width": 1.2, "legend_size": 11},
    "matlab": {"size": (14, 14), "aspect": "square", "font": "Arial", "font_size": 15, "font_weight": "bold",
               "label_size": 18, "label_weight": "bold", "box": "closed", "box_width": 2.0,
               "box_color": (0.7, 0.7, 0.7), "tick_label_color": "black", "tick_direction": "in", "tick_length": 6,
               "tick_sides": ("bottom", "top", "left", "right"), "grid": False, "colors": "matlab",
               "line_width": 1.5, "legend_size": 12, "legend_weight": "bold", "legend_box": False,
               "dpi": 1200, "format": "tiff"},
    "matplotlib": None,                                    # special: no changes at all
}

_session_default: dict[str, Any] = {"preset": "clean"}   # changed by set_style()

# Fonts tried after the chosen one, so a missing font never stops a plot.
_FALLBACK_FONTS = ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"]


# Older names still accepted in styles and saved .json files: old -> new.
_OLD_NAMES = {"ticks": "tick_direction"}


def _renamed(settings: dict) -> dict:
    """The same settings with older names replaced by the current ones."""
    return {_OLD_NAMES.get(k, k): v for k, v in settings.items()}


def _check(settings: dict) -> None:
    """Unknown setting names are an error, with the list of valid ones."""
    wrong = set(settings) - set(SETTINGS) - {"preset"}
    if wrong:
        raise ValueError(f"Unknown style setting(s) {sorted(wrong)}. Valid settings: {', '.join(SETTINGS)} "
                         "(see spectrum_toolkit.style.SETTINGS or docs/plotting.md for what each does).")


def _check_values(look: dict) -> None:
    """Every value that is set must make sense: choices, colours, 0-1 transparency, numbers.

    Checked once in get_style, so a wrong value gives one clear message naming
    the setting, instead of an error deep inside matplotlib (or no effect).
    """
    for name, value in look.items():
        if value is None:                                            # not set: nothing to check
            continue
        base = name
        for prefix in SIDES + ("x", "y"):                            # top_tick_direction -> tick_direction
            if name.startswith(prefix + "_") and name[len(prefix) + 1:] in SETTINGS \
                    and name != f"{prefix}_box":                     # left_box is on/off, not like "box"
                base = name[len(prefix) + 1:]
        if base in CHOICES and value not in CHOICES[base]:
            raise ValueError(f"{name} must be one of {', '.join(map(repr, CHOICES[base]))}; got {value!r}.")
        if name.endswith("_weight") and value not in _WEIGHTS:
            raise ValueError(f'{name} must be "normal" or "bold"; got {value!r}.')
        if name.endswith("box_style") and value not in _LINE_STYLES:
            raise ValueError(f"{name} must be one of {', '.join(map(repr, _LINE_STYLES))}; got {value!r}.")
        if name.endswith("_alpha"):
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 1:
                raise ValueError(f"{name} is a transparency from 0 (invisible) to 1 (solid); got {value!r}.")
        if (name.endswith("_color") or name in ("background", "plot_background", "legend_fill")) \
                and value != "none":
            to_rgba(value, name=name)                                # raises a clear error if not a colour
        if name.endswith(("_length", "_width", "_size", "_pad", "_rotation", "_spacing", "_scale")) \
                and name != "size" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            raise ValueError(f"{name} must be a number; got {value!r}.")
        if (name in ("legend_box", "legend_shadow", "legend_box_round", "minor_ticks")
                or name.endswith(("_italic", "_ticks", "_tick_labels", "_box", "minor_ticks"))) \
                and name != "box" and not isinstance(value, bool):
            raise ValueError(f"{name} must be true or false; got {value!r}.")


# ------------------------------------------------------------------ colours in any form
def to_rgba(value, alpha: float | None = None, name: str = "colour") -> tuple[float, float, float, float]:
    """A colour in any accepted form as (r, g, b, a), each 0 to 1.

    Accepted: a name ("red"), hex ("#1f77b4"), grey as text ("0.5"), RGB or
    RGBA as fractions ([0, 0.45, 0.74]) or as 0-255 ([0, 114, 189]), and CMYK
    as text "cmyk(c, m, y, k)" with 0-1 or 0-100 values. alpha, when given,
    replaces the colour's own transparency.

    >>> to_rgba("cmyk(0, 1, 1, 0)")
    (1.0, 0.0, 0.0, 1.0)
    >>> to_rgba([0, 114, 189], alpha=0.5)
    (0.0, 0.4470588235294118, 0.7411764705882353, 0.5)
    """
    from matplotlib.colors import to_rgba as mpl_rgba
    try:
        if isinstance(value, str) and value.strip().lower().startswith("cmyk(") and value.strip().endswith(")"):
            parts = [float(v) for v in value.strip()[5:-1].split(",")]
            if len(parts) != 4:
                raise ValueError
            if max(parts) > 1:                                       # given in percent, 0-100
                parts = [v / 100 for v in parts]
            c, m, y, k = parts
            rgba = ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k), 1.0)
        elif isinstance(value, (list, tuple)) and value and all(isinstance(v, (int, float)) for v in value):
            numbers = [float(v) for v in value]
            if len(numbers) not in (3, 4):
                raise ValueError
            if max(numbers[:3]) > 1:                                 # given as 0-255
                numbers[:3] = [v / 255 for v in numbers[:3]]
            rgba = mpl_rgba(numbers)
        else:
            rgba = mpl_rgba(value)
    except (ValueError, TypeError):
        raise ValueError(f'{name}: {value!r} is not a colour. Use a name ("red"), hex ("#1f77b4"), grey ("0.5"), '
                         'RGB ([0, 0.45, 0.74] or [0, 114, 189]) or "cmyk(0, 0.5, 1, 0)".') from None
    rgba = tuple(min(max(float(v), 0.0), 1.0) for v in rgba)
    return rgba[:3] + (float(alpha),) if alpha is not None else rgba


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
    style = _renamed(dict(style))
    changes = _renamed(changes)
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
    _check_values(full)
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
    return [to_rgba(v, name="colors") for v in c]                  # any colour form, also cmyk(...)


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


def setting(look: dict, key: str, axis: str | None = None, side: str | None = None):
    """The value of a setting for one side / axis, falling back to the general one.

    setting(look, "tick_length", "x", "top") looks at top_tick_length, then
    x_tick_length, then tick_length, and returns the first that is set.
    """
    for name in ([f"{side}_{key}"] if side else []) + ([f"{axis}_{key}"] if axis else []) + [key]:
        if look.get(name) is not None:
            return look[name]
    return None


def _direction(value: str) -> str:
    """Our tick direction words -> matplotlib's ("both" is "inout" there)."""
    return {"in": "in", "out": "out", "both": "inout"}[value]


def _fill(color, alpha):
    """A fill colour with its transparency; "none" stays "none" (no fill)."""
    return "none" if color == "none" else to_rgba(color, alpha)


def rc_settings(look: dict) -> dict[str, Any]:
    """Translate a style into matplotlib settings (rcParams).

    These are the starting values for everything matplotlib makes later
    (new ticks, legend, text). Settings for one side or one axis are applied
    afterwards to the finished axes, in finish_axes.
    """
    from cycler import cycler                                   # installed with matplotlib
    sides = set(look["tick_sides"])
    labels = set(look["tick_label_sides"])
    tick_w = look["tick_width"] if look["tick_width"] is not None else look["box_width"]
    tick_c = to_rgba(look["tick_color"] if look["tick_color"] is not None else look["box_color"], look["tick_alpha"])
    direction = _direction(look["tick_direction"])
    font = _fonts(look["font"])
    figure_bg = _fill(look["background"], look["background_alpha"])
    plot_bg = _fill(look["plot_background"] or look["background"],
                    look["plot_background_alpha"] if look["plot_background_alpha"] is not None
                    else look["background_alpha"])
    rc = {
        "figure.figsize": _size_inches(look),
        "font.family": font,
        "font.size": look["font_size"],
        "font.weight": look["font_weight"],
        "axes.labelsize": look["label_size"],
        "axes.labelweight": look["label_weight"],
        "axes.labelcolor": to_rgba(look["label_color"], look["label_alpha"]),
        "axes.labelpad": look["label_pad"],
        "axes.titlesize": look["title_size"],
        "axes.titleweight": look["title_weight"] or look["font_weight"],
        "axes.titlecolor": to_rgba(look["title_color"], look["title_alpha"]),
        "axes.titlelocation": look["title_location"],
        "axes.titlepad": look["title_pad"],
        "axes.linewidth": look["box_width"],
        "axes.edgecolor": to_rgba(look["box_color"], look["box_alpha"]),
        "axes.spines.top": look["box"] == "closed",
        "axes.spines.right": look["box"] == "closed",
        "axes.spines.left": look["box"] != "none",
        "axes.spines.bottom": look["box"] != "none",
        "axes.facecolor": plot_bg,
        "figure.facecolor": figure_bg,
        "savefig.facecolor": figure_bg,
        "axes.prop_cycle": cycler(color=_colors(look)),
        "axes.grid": bool(look["grid"]),
        "grid.color": to_rgba(look["grid_color"], look["grid_alpha"]),   # alpha inside the colour: an RGBA colour ignores grid.alpha
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
            f"{axis}.major.size": look["tick_length"],
            f"{axis}.minor.size": look["minor_tick_length"] or look["tick_length"] * 0.55,
            f"{axis}.major.width": tick_w, f"{axis}.minor.width": tick_w * 0.75,
            f"{axis}.major.pad": look["tick_label_pad"], f"{axis}.minor.pad": look["tick_label_pad"],
            f"{axis}.color": tick_c,
            f"{axis}.labelcolor": to_rgba(look["tick_label_color"], look["tick_label_alpha"]),
            f"{axis}.labelsize": look["tick_label_size"] or look["font_size"],
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


# Tick mark shapes per side and direction (matplotlib draws a tick as a marker).
# Side 1 is bottom / left, side 2 is top / right.
def _tick_marker(axis: str, number: int, direction: str):
    import matplotlib.lines as mlines
    if direction == "both":
        return "|" if axis == "x" else "_"                       # centred on the box line
    if axis == "x":
        out, inward = (mlines.TICKDOWN, mlines.TICKUP) if number == 1 else (mlines.TICKUP, mlines.TICKDOWN)
    else:
        out, inward = (mlines.TICKLEFT, mlines.TICKRIGHT) if number == 1 else (mlines.TICKRIGHT, mlines.TICKLEFT)
    return out if direction == "out" else inward


def _style_text(text, look: dict, size, weight, color, alpha, italic, font, rotation=None) -> None:
    """Apply size, weight, colour + transparency, italics, font and rotation to one text."""
    text.set_fontsize(size)
    text.set_fontweight(weight)
    text.set_color(to_rgba(color, alpha))
    text.set_fontstyle("italic" if italic else "normal")
    text.set_fontfamily(_fonts(font or look["font"]))
    if rotation is not None:
        text.set_rotation(rotation)


def _style_box(ax, look: dict, twin: bool) -> None:
    """Each side of the box: on/off, colour, transparency, width, line type."""
    for side in SIDES:
        spine = ax.spines[side]
        if twin:                                                 # a second y axis: the main axes draw the box
            spine.set_visible(False)
            continue
        on = look[f"{side}_box"]
        if on is None:                                           # from "box": closed / open / none
            on = look["box"] == "closed" or (look["box"] == "open" and side in ("bottom", "left"))
        spine.set_visible(on)
        spine.set_edgecolor(to_rgba(setting(look, "box_color", side=side), setting(look, "box_alpha", side=side)))
        spine.set_linewidth(setting(look, "box_width", side=side))
        spine.set_linestyle(setting(look, "box_style", side=side))


def _style_ticks(ax, look: dict, twin: bool) -> None:
    """Tick marks and tick labels, each side on its own.

    matplotlib sets most tick properties per axis (top and bottom alike), so
    the per-side values are put on each tick object: tick1line / label1 are
    the bottom (x) or left (y) side, tick2line / label2 the top or right side.
    New ticks that matplotlib makes later copy the first tick, so they keep
    the same look.
    """
    import matplotlib.ticker as mticker
    for axis, axis_obj, sides in (("x", ax.xaxis, ("bottom", "top")), ("y", ax.yaxis, ("left", "right"))):
        # minor ticks for this axis: on/off and how many between numbered ticks
        minor = setting(look, "minor_ticks", axis)
        if minor:
            count = setting(look, "minor_tick_count", axis)
            axis_obj.set_minor_locator(mticker.AutoMinorLocator(count + 1 if count else None))
        else:
            axis_obj.set_minor_locator(mticker.NullLocator())
        # on/off per side (a second y axis on the right keeps its ticks on the right)
        onoff = {}
        for side in sides:
            ticks_on = look[f"{side}_ticks"]
            labels_on = look[f"{side}_tick_labels"]
            onoff[side] = ticks_on if ticks_on is not None else side in look["tick_sides"]
            onoff[f"label{side}"] = labels_on if labels_on is not None else side in look["tick_label_sides"]
        if twin and axis == "y":
            onoff.update(left=False, labelleft=False, right=True, labelright=True)
        # Panels that share an axis (compare: the top panel above "removed")
        # show the numbers only once; keep them hidden where matplotlib hid them.
        shared = ax.get_shared_x_axes() if axis == "x" else ax.get_shared_y_axes()
        ticks_now = axis_obj.get_major_ticks()
        if len(shared.get_siblings(ax)) > 1 and ticks_now \
                and not any(t.label1.get_visible() or t.label2.get_visible() for t in ticks_now):
            onoff.update({f"label{sides[0]}": False, f"label{sides[1]}": False})
        # direction for the whole axis first (it also sets the label distance), then each side below
        ax.tick_params(axis=axis, which="both", direction=_direction(setting(look, "tick_direction", axis, sides[0])),
                       pad=setting(look, "tick_label_pad", axis), **onoff)
        major_ticks = axis_obj.get_major_ticks()
        minor_ticks = axis_obj.get_minor_ticks() if minor else []
        for is_major, ticks in ((True, major_ticks), (False, minor_ticks)):
            for tick in ticks:
                for number, line, label, side in ((1, tick.tick1line, tick.label1, sides[0]),
                                                  (2, tick.tick2line, tick.label2, sides[1])):
                    length = setting(look, "tick_length", axis, side)
                    width = setting(look, "tick_width", axis, side)
                    width = width if width is not None else setting(look, "box_width", side=side)
                    if not is_major:                             # minor ticks: shorter and thinner
                        length = setting(look, "minor_tick_length", axis) or length * 0.55
                        width = width * 0.75
                    color = setting(look, "tick_color", axis, side)
                    color = color if color is not None else setting(look, "box_color", side=side)
                    line.set_marker(_tick_marker(axis, number, setting(look, "tick_direction", axis, side)))
                    line.set_markersize(length)
                    line.set_markeredgewidth(width)
                    line.set_markeredgecolor(to_rgba(color, setting(look, "tick_alpha", axis, side)))
                    _style_text(label, look,
                                size=setting(look, "tick_label_size", axis, side) or look["font_size"],
                                weight=setting(look, "tick_label_weight", axis, side) or look["font_weight"],
                                color=setting(look, "tick_label_color", axis, side),
                                alpha=setting(look, "tick_label_alpha", axis, side),
                                italic=setting(look, "tick_label_italic", axis, side),
                                font=setting(look, "tick_label_font", axis, side),
                                rotation=setting(look, "tick_label_rotation", axis, side))


def _style_labels_and_title(ax, look: dict) -> None:
    """x and y axis labels (each on its own), and the title."""
    for axis, axis_obj in (("x", ax.xaxis), ("y", ax.yaxis)):
        def get(key):                                            # xlabel_size, then label_size
            value = look.get(f"{axis}{key}")
            return value if value is not None else look.get(key)
        _style_text(axis_obj.label, look, size=get("label_size"),
                    weight=get("label_weight") or look["font_weight"], color=get("label_color"),
                    alpha=get("label_alpha"), italic=get("label_italic"), font=get("label_font"),
                    rotation=look[f"{axis}label_rotation"])
        axis_obj.labelpad = get("label_pad")
    # The title can sit left, centre or right; matplotlib keeps three separate
    # title texts, so take whichever has text and put it where the style says.
    texts = [ax.title, ax._left_title, ax._right_title]
    text = next((t.get_text() for t in texts if t.get_text()), "")
    if text:
        for t in texts:
            t.set_text("")
        title = ax.set_title(text, loc=look["title_location"], pad=look["title_pad"])
        _style_text(title, look, size=look["title_size"], weight=look["title_weight"] or look["font_weight"],
                    color=look["title_color"], alpha=look["title_alpha"], italic=look["title_italic"],
                    font=look["title_font"])


def finish_axes(ax, look: dict | None) -> None:
    """Settings applied to the finished axes: square plot area, tick spacing
    and number format, zero lines, and every per-side / per-axis setting
    (box sides, ticks, tick labels, axis labels, title)."""
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
    kw = dict(color=to_rgba(look["zero_line_color"]), ls=look["zero_line_style"], lw=look["zero_line_width"],
              zorder=0.5, marker="None")
    if z in ("x", "both"):
        ax.axhline(0, **kw)
    if z in ("y", "both"):
        ax.axvline(0, **kw)
    # A second y axis on the right (compare, for normalize/derivative) shares
    # the box of the main axes and keeps its numbers on the right.
    twin = ax.yaxis.get_label_position() == "right"
    _style_box(ax, look, twin)
    _style_ticks(ax, look, twin)
    _style_labels_and_title(ax, look)


def legend(ax, look: dict | None, n_lines: int, force: bool | str | None = None) -> None:
    """Draw the legend according to the style ("auto": for 2 to 10 lines).

    Every part has its own settings: place, columns, order, entry text, title,
    frame (line and fill) and the size of the line and marker samples.
    """
    show = look["legend"] if look else "auto"
    if force is not None and force != "auto":
        show = force
    if not (show is True or (show == "auto" and 1 < n_lines <= 10)):
        return
    if look is None:
        ax.legend(loc="best")
        return
    from matplotlib.font_manager import FontProperties
    handles, labels = ax.get_legend_handles_labels()
    if look["legend_order"] == "reverse":
        handles, labels = handles[::-1], labels[::-1]
    where = {}
    if look["legend_position"] is not None:                      # exact corner, 0-1 of the plot
        where = {"loc": "lower left", "bbox_to_anchor": tuple(look["legend_position"])}
    elif look["legend_location"] == "outside":
        where = {"loc": "upper left", "bbox_to_anchor": (1.02, 1)}
    else:
        where = {"loc": look["legend_location"]}
    text_font = FontProperties(family=_fonts(look["legend_font"] or look["font"]), size=look["legend_size"],
                               weight=look["legend_weight"], style="italic" if look["legend_italic"] else "normal")
    title_font = FontProperties(family=_fonts(look["legend_font"] or look["font"]),
                                size=look["legend_title_size"] or look["legend_size"],
                                weight=look["legend_title_weight"])
    leg = ax.legend(handles, labels, **where, ncols=look["legend_columns"], prop=text_font,
                    labelcolor=[to_rgba(look["legend_color"], look["legend_alpha"])] * len(labels),
                    title=look["legend_title"], title_fontproperties=title_font,
                    frameon=bool(look["legend_box"]), fancybox=bool(look["legend_box_round"]),
                    shadow=bool(look["legend_shadow"]), handlelength=look["legend_line_length"],
                    markerscale=look["legend_marker_scale"], labelspacing=look["legend_spacing"])
    frame = leg.get_frame()
    frame.set_alpha(None)                                        # transparency comes from the two colours below
    frame.set_edgecolor(to_rgba(look["legend_box_color"], look["legend_box_alpha"]))
    frame.set_facecolor(_fill(look["legend_fill"], look["legend_fill_alpha"]))
    frame.set_linewidth(look["legend_box_width"])


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


__all__ = ["get_style", "set_style", "save_style", "export", "to_rgba", "SETTINGS", "PRESETS", "PALETTES", "SIZES"]
