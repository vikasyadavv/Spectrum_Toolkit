"""Write docs/plotting.md (the plotting reference) and its example pictures
in docs/plotting/, from the settings in src/spectrum_toolkit/style.py.

    uv run python scripts/make_plotting_docs.py

Run it after adding or changing any plotting setting. The tables are made
from SETTINGS itself, so the reference always lists every setting with its
default and meaning; tests/test_style.py fails when a setting is missing
from docs/plotting.md, as a reminder to run this script.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                                      # draw without a window
import numpy as np

import spectrum_toolkit as stk
from spectrum_toolkit import SpectrumCollection
from spectrum_toolkit.style import AXIS_OF_SIDE, PALETTES, PER_SPECTRUM, SETTINGS, SIDES, TEXTS

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "plotting.md"
PICTURES = ROOT / "docs" / "plotting"
USED: set = set()                    # settings already placed in a section (each must be placed once)


# ------------------------------------------------------------------ example data
# Three made-up Raman-like spectra (so the pictures need no data files); the
# website shows the same ones before a file is loaded (GET /example).
example_data = stk.example


# ------------------------------------------------------------------ pictures
# Each picture: (file name, caption, settings). Same settings as the example
# shown in the text, so the picture is exactly what the example gives.
PICTURE_LIST = [
    ("ticks_per_side.png", "Ticks set per side: x inward, y outward; long red ticks on top with rotated red "
                           "numbers; right ticks blue and see-through; minor ticks on x only.",
     dict(box="closed", tick_sides=["bottom", "top", "left", "right"], tick_label_sides=["bottom", "top", "left"],
          x_tick_direction="in", y_tick_direction="out", top_tick_length=9, top_tick_color="red",
          top_tick_label_color="red", top_tick_label_rotation=45, right_tick_color="cmyk(1, 0.5, 0, 0)",
          right_tick_alpha=0.5, right_tick_length=7, x_minor_ticks=True, minor_tick_count=3, grid=False)),
    ("box_sides.png", "Box set per side: thick left line, dashed red top line, no right line; light grey "
                      "inside the box.",
     dict(box="closed", left_box_width=2.5, top_box_color="red", top_box_style="--", right_box=False,
          plot_background="0.94", grid=False)),
    ("labels_and_title.png", "Axis labels and title each set on their own: blue italic x label, large bold "
                             "y label, title on the left in dark red italics.",
     dict(xlabel_color="blue", xlabel_italic=True, ylabel_size=15, ylabel_weight="bold",
          title="Three samples", title_location="left", title_color=[160, 0, 0], title_italic=True,
          title_size=14)),
    ("legend.png", "Legend with a heading, three columns in reverse order, a green legend box and a light "
                   "yellow, half see-through fill; italic purple entries.",
     dict(legend=True, legend_box=True, legend_title="Samples", legend_columns=3, legend_order="reverse",
          legend_box_color="green", legend_box_width=1.5, legend_fill="#ffffcc", legend_fill_alpha=0.6,
          legend_color="purple", legend_italic=True, legend_location="upper left")),
    ("lines_format.png", "One look per spectrum with MATLAB codes: circles and a line, asterisks and dashes, "
                         "hollow squares and dots; a marker on every 60th point only (stacked).",
     dict(kind="stack", line_format=["o-", "*--", "s:"], marker_every=60, marker_size=6, marker_fill=[None, None, "none"],
          line_width=1.2, legend=True)),
    ("lines_emphasize.png", "Spectrum B emphasized: on top, thicker and solid, with the other two faded.",
     dict(emphasize=["Sample B"], colors="dark", faded_alpha=0.25, legend=True)),
    ("lines_fill.png", "Own colour per spectrum (one in CMYK), half see-through lines and a light fill under "
                       "each line, down to its own zero (stacked).",
     dict(kind="stack", line_color=["navy", "cmyk(0, 0.8, 1, 0)", "#2ca02c"], line_alpha=[1, 0.8, 0.6], fill=True,
          fill_alpha=0.15, legend=True)),
    ("marks_and_peaks.png", "Peak labels of the first and third spectrum in the colour of their line, with a "
                            "line up to each label (labels that would overlap are moved apart); marks from the "
                            "bottom up to the spectrum, one in red and dashed; mark labels in a box.",
     dict(peaks=4, marks={1180: {"label": "ν(C-O)", "color": "red", "style": "--"}, 1370: "D"},
          peak_spectra=[0, 2], peak_label_color="line", peak_line=True, peak_label_pad=22, mark_span="peak",
          mark_label_box=True, mark_label_rotation=0, mark_label_weight="bold", colors="dark")),
    ("highlight.png", "Two highlighted ranges, each with its own label and look: a blue range with a solid "
                      "line around it, and a striped range for black and white print.",
     dict(highlight=[{"range": [1560, 1640], "label": "G band", "color": "blue", "edge_color": "blue"},
                     {"range": [1330, 1410], "label": "D band", "hatch": "//", "color": "0.5", "alpha": 0.1}],
          highlight_label_weight="bold", highlight_label_size=10)),
    ("axis_limits.png", "y_range [0, 0.5] cuts off the tall bands so the small ones show; their peak labels "
                        "stay at the top of the box. x_margin 0: the spectra touch the box left and right.",
     dict(y_range=[0, 0.5], x_margin=0, peaks=4)),
    ("second_axes.png", "A second x axis on top (absolute wavelength for a 532 nm laser) and a second y axis "
                        "on the right (counts per second at 10 s exposure).",
     dict(top_axis="wavelength", top_axis_laser=532, right_axis="scale", right_axis_scale=0.1,
          right_axis_label="Counts per second", box="closed")),
    ("cut_marks.png", "The range 1250 to 1300 removed with cut: the lines break there and // marks show the gap "
                      "on the box.",
     dict(cut_marks=True, box="closed")),
    ("names_scale_bar.png", "Stacked spectra with each name next to its line (no legend) and a scale bar "
                            "showing the size of 0.5 intensity units.",
     dict(kind="stack", line_names=True, legend=False, scale_bar=0.5)),
    ("mean_band.png", "The mean of the three spectra with a band from the lowest to the highest value.",
     dict(kind="mean", mean_band="minmax", mean_band_alpha=0.3)),
    ("image.png", "The spectra as an image, with their names on the y axis, fixed colour limits and chosen "
                  "colour bar ticks.",
     dict(kind="image", image_y="name", color_limits=[0, 0.8], colorbar_ticks_at=[0, 0.4, 0.8],
          colorbar_label="Intensity")),
    ("notes_inset.png", "A note in a box with an arrow to a band, a bold note placed by its share of the box, "
                        "and an inset zoomed on 1550 to 1650 at the upper left.",
     dict(notes=[{"text": "G band", "x": 1350, "y": 0.9, "arrow": [1585, 0.78], "color": "red", "box": True},
                 {"text": "Sample set 1", "x": 0.5, "y": 0.4, "coords": "axes", "weight": "bold"}],
          inset={"region": [1550, 1650], "position": "upper left"}, inset_scale=0.35)),
]

# Pictures drawn from other data than the example spectra as they are.
PICTURE_DATA = {"cut_marks.png": lambda d: d.cut(1250, 1300)}

# Arguments of plot itself (not style settings): passed apart from the settings.
PLOT_ARGUMENTS = ("kind", "title", "emphasize", "peaks", "marks", "highlight", "region", "notes", "inset")


def make_pictures() -> None:
    """Draw every picture in PICTURE_LIST into docs/plotting/."""
    import matplotlib.pyplot as plt
    PICTURES.mkdir(parents=True, exist_ok=True)
    data = example_data()
    for name, _, settings in PICTURE_LIST:
        settings = dict(settings)
        extra = {k: settings.pop(k) for k in PLOT_ARGUMENTS if k in settings}
        shown = PICTURE_DATA.get(name, lambda d: d)(data)
        ax = shown.plot(size=(16, 8), **extra, **settings)
        stk.export(ax, PICTURES / name, dpi=110)
        plt.close("all")
    # several plots in one figure (stk.panels)
    axes = stk.panels([data, {"data": data, "kind": "stack", "peaks": 3}, {"data": data, "kind": "mean"},
                       {"data": data, "kind": "image"}], layout=[2, 2], size=(12, 7))
    stk.export(axes[0], PICTURES / "panels.png", dpi=90)
    plt.close("all")
    # panels: text layout, sizes, one legend and shared labels; then one colour bar for two images
    axes = stk.panels([data, {"data": data, "region": [880, 950]}, {"data": data, "region": [1550, 1650]}],
                      layout="AA;BC", heights=[1.3, 1], panel_legend="figure top", panel_shared_labels="y",
                      size=(12, 6))
    stk.export(axes[0], PICTURES / "panels_layout.png", dpi=90)
    half = SpectrumCollection(data.x, data.Y * 0.5, names=data.names, x_unit=data.x_unit, y_unit=data.y_unit)
    axes = stk.panels([{"data": data, "kind": "image", "title": "full"}, {"data": half, "kind": "image", "title": "half"}],
                      layout=[1, 2], panel_colorbar="shared", panel_spacing_x=0.06, size=(12, 7))
    stk.export(axes[0], PICTURES / "panels_colorbar.png", dpi=90)
    plt.close("all")
    # before/after views as panels: a sloping background removed, then the scale changed
    raw = data.copy_with(Y=data.Y + np.linspace(0.3, 0.05, data.x.size))
    flat = raw.baseline()
    axes = stk.panels([{"data": raw, "after": flat, "kind": "compare"},
                       {"data": flat, "after": flat.normalize("max"), "kind": "compare"}], layout=[1, 2], size=(12, 7))
    stk.export(axes[0], PICTURES / "panels_compare.png", dpi=90)
    plt.close("all")
    # groups: one colour per group, and one mean per group
    many = SpectrumCollection(data.x, np.vstack([data.Y, data.Y * 0.9 + 0.02, data.Y[::-1] * 0.8]),
                              names=[f"{g} {k}" for g in ("CV", "MB", "RhB") for k in (1, 2, 3)],
                              x_unit=data.x_unit, y_unit=data.y_unit).set_groups("name")
    axes = stk.panels([{"data": many, "color_by": "group", "title": "color_by=\"group\""},
                       {"data": many, "kind": "mean", "color_by": "group", "title": "kind=\"mean\", color_by=\"group\""}],
                      layout=[1, 2], size=(12, 7))
    stk.export(axes[0], PICTURES / "groups.png", dpi=90)
    plt.close("all")


# ------------------------------------------------------------------ text
def show(value) -> str:
    """A default value as it is written in JSON (None -> empty: 'not set')."""
    if value is None:
        return "*(not set)*"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, tuple):
        return "[" + ", ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in value) + "]"
    return f'"{value}"' if isinstance(value, str) else str(value)


def table(names) -> str:
    """A markdown table of settings: name, default, meaning."""
    rows = ["| Setting | Default | What it does |", "|---|---|---|"]
    for n in names:
        default, meaning = SETTINGS[n]
        rows.append(f"| `{n}` | {show(default)} | {meaning.replace('|', '/')} |")
    return "\n".join(rows)


def picture(name: str) -> str:
    """The picture with its caption and the settings that made it (Python and website)."""
    import json
    _, caption, settings = next(p for p in PICTURE_LIST if p[0] == name)
    python = ", ".join(f"{k}={v!r}" for k, v in settings.items())
    start = "c.cut(1250, 1300).plot" if name in PICTURE_DATA else "c.plot"
    body = {k: v for k, v in settings.items() if k in PLOT_ARGUMENTS}
    style = {k: v for k, v in settings.items() if k not in PLOT_ARGUMENTS}
    website = json.dumps({**body, "settings": style} if style else body, ensure_ascii=False)
    return (f"![{caption}](plotting/{name})\n\n*{caption}*\n\nPython:\n```python\n{start}({python})\n```\n"
            f"Website (`/figure`), next to `\"data\"`:\n```json\n{website}\n```\n")


def table_of_texts() -> str:
    """One row per text setting, one column per kind of text (mark, peak, highlight label)."""
    keys = [n[len("mark_label_"):] for n in SETTINGS if n.startswith("mark_label_")]
    rows = ["| Setting (after `mark_label_` ...) | Default: mark / peak / highlight label | What it does |",
            "|---|---|---|"]
    for key in keys:
        names = [f"{what}_{key}" for what in TEXTS]
        USED.update(names)
        defaults = " / ".join(show(SETTINGS[n][0]) for n in names)
        meaning = SETTINGS[names[0]][1].replace("mark label", "label").replace("|", "/")
        if key == "color":
            meaning += '; for peak labels also "line": the colour of its spectrum'
        rows.append(f"| {', '.join(f'`{n}`' for n in names)} | {defaults} | {meaning} |")
    return "\n".join(rows)


def group(prefixes: tuple, keys) -> list[str]:
    """Every name prefix_key for the given prefixes and keys, if it is a setting."""
    return [f"{p}{k}" for p in prefixes for k in keys if f"{p}{k}" in SETTINGS]


def write_doc() -> None:
    general_ticks = ["tick_direction", "tick_length", "tick_width", "tick_color", "tick_alpha", "tick_sides",
                     "tick_label_sides", "tick_label_size", "tick_label_color", "tick_label_alpha",
                     "tick_label_weight", "tick_label_italic", "tick_label_font", "tick_label_rotation",
                     "tick_label_pad", "minor_ticks", "minor_tick_length", "minor_tick_count", "x_ticks_at",
                     "y_ticks_at", "x_tick_step", "y_tick_step", "x_tick_count", "y_tick_count", "x_tick_format",
                     "y_tick_format"]
    tick_keys = ["tick_direction", "tick_length", "tick_width", "tick_color", "tick_alpha", "tick_label_size",
                 "tick_label_color", "tick_label_alpha", "tick_label_weight", "tick_label_italic",
                 "tick_label_font", "tick_label_rotation", "tick_label_pad", "minor_ticks", "minor_tick_length",
                 "minor_tick_count"]
    label_keys = ["label_size", "label_weight", "label_color", "label_alpha", "label_italic", "label_font",
                  "label_pad", "label_rotation"]
    box_keys = ["box", "box_width", "box_color", "box_alpha", "box_style"]
    USED.clear()

    def section(names):
        USED.update(names)
        return table(names)

    parts = [f"""# Plotting reference

Everything a figure can show and every setting that changes how it looks.
This file is written by `scripts/make_plotting_docs.py` from the settings in
`src/spectrum_toolkit/style.py`, so it always lists every setting
({len(SETTINGS)} today). Edit the script, not this file.

## How to use settings

**Python:** give any setting by name to a plot, on top of a style preset:
```python
c.plot(style="publication", top_tick_length=8, xlabel_color="blue")
stk.set_style("matlab", legend_box=True)      # default for every later plot
stk.save_style("matlab", "my_style", box_width=2)   # reuse with style="my_style.json"
```

**Website (`/figure`):** the same names go in `"settings"`:
```json
{{"kind": "lines", "style": "publication", "settings": {{"top_tick_length": 8, "xlabel_color": "blue"}}, "data": {{...}}}}
```
`/options` lists every setting with its default and meaning, so the website
can build its controls from it.

**Style files:** `stk.save_style` writes only the settings that differ from
the preset, plus what the file is, so the file stays short and readable:
```json
{{"type": "spectrum-toolkit style", "version": 1, "name": "my_style", "saved": "2026-10-22",
 "toolkit": "0.0.1", "preset": "matlab", "settings": {{"box_width": 2}}}}
```
Settings added later get their default, and an improved default reaches the
file too. `stk.save_style(..., only_changed=False)` writes every setting;
`stk.style_file(...)` gives the same contents as a dict without saving.
Older files (every setting, no `"type"`) and older setting names (`ticks`,
now `tick_direction`) still load. A file from a newer toolkit version says so
and asks for an update.

**Saved styles on the website (`/style-check`):** a style file is sent as its
contents, never as a file name: the service opens no files. `"style"` is a
preset name, a dict, or a style file's contents:
```json
{{"style": {{"preset": "publication", "line_width": 1.5}}, "settings": {{"legend_box": true}}, "name": "My paper style"}}
```
The answer has `"style"` (every setting: the style as it will be drawn),
`"file"` (the style file to download as `my_style.json`, to load again on the
website or in Python with `style="my_style.json"`), `"changed"` (only the
settings that differ from the defaults), `"renamed"` (older setting names and
their new names) and `"warnings"` (fonts not installed on the server, renamed
and skipped settings). A wrong setting gives the same message as in Python.
With `"lenient": true`, setting names this toolkit does not know (a typo, or a
file from a newer version) are left out and listed in `"skipped"` instead.

**Live preview on the website:** the page asks `/figure` for the same figure
at a low `"dpi"` (for example 60, `"format": "png"`). The size in cm stays the
same, so the preview has exactly the layout of the download. Before a file is
loaded, `GET /example` gives the three example spectra used in the pictures
here.

**No spectra:** with every spectrum left out (on the website: all hidden, so
the page sends `"Y": []`), any kind draws an empty frame: the box, title and
axis labels, the x axis over the same range as with the lines, no numbers on
y. It can be downloaded like any figure, for example as a template. Only
`/figure` accepts `"Y": []`; the other requests need at least one spectrum.

A wrong name or value is an error that says what is allowed, for example
`tick_alpha is a transparency from 0 (invisible) to 1 (solid); got 2.`

## Presets

`clean` (default), `publication`, `matlab`, `matplotlib`, `cheminations`; see
the top of `style.py` for what each sets. Every setting below can be changed on
top. `cheminations` is the website's default: `publication` with Arial, larger
text (20 pt numbers, 24 pt axis titles), a 3 pt grey box (`#ACADAC`) with ticks
on the bottom and left only, 5 and 4 ticks, no white space left and right, 3 pt
lines in the `classic` colours (black, red, blue, green, violet, orange, indigo,
brown, teal, grey) and a legend for 2 to 5 spectra (12 pt, short lines).

**Fonts not installed:** a font in `FONT_TWINS` that is not installed is drawn
with its free twin, made with exactly the same letter widths, so the layout does
not change: Arial and Helvetica with Liberation Sans, Times New Roman with
Liberation Serif, Courier New with Liberation Mono. The website's server has
only the twins; `/options` lists the ones in use (`"font_twins"`), and only a
font with no twin installed gives the "not installed" warning.

## The naming rule

The last word of a setting name always means the same:

| Ending | Meaning | Values |
|---|---|---|
| `_color` | colour | see **Colours** below |
| `_alpha` | transparency | 0 (invisible) to 1 (solid) |
| `_width` | line width | points (1 point = 1/72 inch) |
| `_style` | line type | `"-"` solid, `"--"` dashed, `":"` dotted, `"-."` dash-dot |
| `_size` | text or marker size | points |
| `_weight` | text thickness | `"normal"` or `"bold"` |
| `_italic` | slanted text | true / false |
| `_font` | font name | e.g. `"Arial"`, `"Times New Roman"`; if not installed, its twin (see **Presets**) |
| `_length` | tick length | points |
| `_pad` | distance to the next element | points |
| `_rotation` | text angle | degrees, e.g. 45 or 90 |

## From general to specific

Many settings exist at three levels. The most specific one that is set wins:

1. **one side**: `top_tick_length`, `left_box_color`, `right_tick_label_color` ...
2. **one axis**: `x_tick_length` (bottom and top), `y_tick_color` (left and right), `xlabel_size` ...
3. **everything**: `tick_length`, `box_color`, `label_size` ...

A setting that is *(not set)* uses the next level. So `tick_length: 6` makes
every tick 6 points long, `x_tick_length: 8` then changes the bottom and top
ticks, and `top_tick_length: 10` only the top ones.

## Colours

Every colour setting accepts any of these:

| Form | Example |
|---|---|
| name | `"red"`, `"navy"`, `"tab:blue"` |
| hex | `"#1f77b4"` |
| grey (0 black to 1 white) | `"0.5"` |
| RGB, fractions 0-1 | `[0, 0.45, 0.74]` |
| RGB, 0-255 | `[0, 114, 189]` |
| RGBA (with transparency) | `[0, 0.45, 0.74, 0.5]` |
| CMYK, fractions or percent | `"cmyk(0, 0.5, 1, 0)"`, `"cmyk(0, 50, 100, 0)"` |
| no colour (backgrounds, fills) | `"none"` |

CMYK colours are converted to RGB for drawing; to save the whole figure as a
CMYK file use `color_mode="cmyk"` with tiff or jpg (see **Saving**).

Which colour each spectrum gets: `stk.line_colors(n, style, groups=...)` gives
the colour (`"#rrggbb"`) the plot draws each of n spectra in: the palette
(`colors`) in order, the colour map (`cmap`) for more than 10 spectra, one
colour per group with `color_by="group"`, then `line_color` and colour letters
in `line_format`. The website asks the same through `POST /colors`, so it shows
each spectrum's colour before drawing.

## Figure size and shape

{section(["size", "units", "aspect"])}

## Axis limits

`x_range` and `y_range` fix the ends of an axis; `null` (None) on one side
leaves that end automatic, e.g. `"y_range": [0, null]` starts at zero. Use
them to give several figures the same scale, or to cut off one huge band so
the small ones show. The order of the two numbers does not matter, and
`invert_x` still decides the direction. `region` (a plot argument) picks an
x part and fits y to the data inside it; `y_range`, when set, wins over that
fit. A band cut off by `y_range` keeps its peak label, moved down to the top
of the box. The margins set the white space where an end is automatic.

{section(["x_range", "y_range", "x_margin", "y_margin"])}

{picture("axis_limits.png")}

## Text: the base for all text

{section(["font", "font_size", "font_weight"])}

## Box (the lines around the plot)

General:

{section(box_keys + ["background", "background_alpha", "plot_background", "plot_background_alpha"])}

One side (`bottom`, `top`, `left`, `right`); each falls back to the general setting:

{section(group(tuple(s + "_" for s in SIDES), ["box", "box_width", "box_color", "box_alpha", "box_style"]))}

{picture("box_sides.png")}

## Ticks and tick labels

**Which sides** have tick marks and numbers: `tick_sides` and
`tick_label_sides` (lists), or one side at a time with `bottom_ticks`,
`top_tick_labels` ... (true / false).

General:

{section(general_ticks)}

One axis (`x_` = bottom and top, `y_` = left and right); each falls back to the general setting:

{section(group(("x_", "y_"), tick_keys))}

One side; each falls back to the axis setting, then the general one:

{section(group(tuple(s + "_" for s in SIDES), ["ticks", "tick_labels"] + tick_keys))}

{picture("ticks_per_side.png")}

Notes:
- `tick_direction` "both" draws the tick through the box line, half in and half out.
- Minor ticks are shorter (0.55 x) and thinner (0.75 x) than the numbered
  ticks unless `minor_tick_length` is set; they take the colour, direction
  and transparency of their side.
- The distance of the numbers (`tick_label_pad`) is per axis, not per side.
- The old name `ticks` (for `tick_direction`) still works in saved styles.

## Grid

{section(["grid", "grid_color", "grid_style", "grid_width", "grid_alpha"])}

## Axis labels

General (both axes):

{section(label_keys[:-1])}

One axis; each falls back to the general setting:

{section(group(("x", "y"), label_keys))}

The label text itself is set with `xlabel` and `ylabel` (default: the units
of the data, else "x" and "Intensity").

## Title

The text is set with `title`.

{section(["title_size", "title_weight", "title_color", "title_alpha", "title_italic", "title_font",
          "title_location", "title_pad"])}

{picture("labels_and_title.png")}

## Legend

When and where:

{section(["legend", "legend_auto_max", "legend_location", "legend_position", "legend_columns", "legend_order",
          "legend_hide"])}

Entry text and heading:

{section(["legend_size", "legend_weight", "legend_color", "legend_alpha", "legend_italic", "legend_font",
          "legend_title", "legend_title_size", "legend_title_weight"])}

Legend box:

{section(["legend_box", "legend_box_color", "legend_box_width", "legend_box_alpha", "legend_box_round",
          "legend_fill", "legend_fill_alpha", "legend_shadow"])}

Entry layout:

{section(["legend_line_length", "legend_marker_scale", "legend_spacing"])}

The names in the legend are the spectrum names, or `labels` (a list, one
per spectrum).

{picture("legend.png")}

## Spectra (data lines)

Colours:

{section(["colors", "cmap", "line_color"])}

Palettes for `colors`: {", ".join(f"`{p}`" for p in PALETTES)}; or any
matplotlib colour map name, such as `"viridis"`, `"plasma"` or `"coolwarm"`,
whose colours are spread evenly over the spectra (useful for a series, e.g.
increasing temperature). With more than 10 spectra the colours always come
from `cmap`, unless `line_color` is set.

Line:

{section(["line_width", "line_style", "line_alpha", "line_format"])}

Markers (the points on a line):

{section(["marker", "marker_size", "marker_color", "marker_fill", "marker_alpha", "marker_edge_width",
          "marker_every"])}

Emphasized spectra and fill:

{section(["emphasize_width", "faded_alpha", "fill", "fill_color", "fill_alpha"])}

**One value or one per spectrum.** {", ".join(f"`{n}`" for n in PER_SPECTRUM)}
take either one value for every spectrum or a list with one value per
spectrum. A shorter list starts again from its beginning, so
`"line_style": ["-", "--"]` gives solid, dashed, solid, dashed ... One colour
written as numbers (`[0, 114, 189]`) is one colour, not a list.

**MATLAB codes** (`line_format`), exactly as in MATLAB's `plot(x, y, "o--")`.
A code joins up to three parts in any order: a line type, a marker and a
colour letter. A marker without a line type draws markers only (no line),
as in MATLAB.

| Part | Codes |
|---|---|
| line type | `-` solid, `--` dashed, `:` dotted, `-.` dash-dot |
| marker | `o` circle, `+` plus, `*` asterisk, `.` point, `x` cross, `s` square, `d` diamond, `^` `v` `>` `<` triangles, `p` five-pointed star, `h` hexagon, `_` `\\|` short lines |
| colour | `r` red, `g` green, `b` blue, `c` cyan, `m` magenta, `y` yellow, `k` black, `w` white (MATLAB's pure colours) |

Examples: `"o-"` circles joined by a line; `"*--"` asterisks on a dashed
line; `"."` points only; `"r:"` red dotted line; `"ks-"` black squares on a
line. `line_format` replaces `marker` and `line_style`, and `line_color`
when it has a colour letter. `marker_every` is worth setting with markers:
a spectrum has hundreds of points, and a marker on each one hides the line.

**Emphasize** is an argument of `plot`, not a style setting:
`c.plot(emphasize=[0, 2])` or `emphasize=["Sample B"]` (numbers count from 0;
names are the spectrum names or `labels`). On the website it goes at the top
level of the body: `"emphasize": [1]`.

{picture("lines_format.png")}
{picture("lines_emphasize.png")}
{picture("lines_fill.png")}

## Marks, peak labels and highlighted ranges

These are arguments of `plot` (`marks=`, `peaks=`, `highlight=`); on the
website they go at the top level of the body, next to `"data"`. Their look
is set by the settings below.

**Mark lines** (`marks=[1585, 1620]`, or `marks={{1620: "C=C"}}` with labels):

{section(["mark_color", "mark_style", "mark_width", "mark_alpha", "mark_span"])}

One mark can have its own look: `marks={{1620: {{"label": "C=C", "color": "red", "style": "--"}}}}`.
The keys are the setting names without `mark_`: {", ".join(f"`{k}`" for k in ("label", "color", "style", "width", "alpha", "span"))}.

**Peak labels** (`peaks=5`: the 5 most prominent bands; or `peaks=[1000, 1600]`: those positions):

{section(["peak_label_format", "peak_sensitivity", "peak_spectra", "peak_line", "peak_line_color",
          "peak_line_style", "peak_line_width", "peak_line_alpha"])}

**Highlighted ranges** (`highlight=[[1570, 1640]]`, or `highlight="spikes"` for the spikes removed by despike):

{section(["highlight_color", "highlight_alpha", "highlight_hatch", "highlight_edge_color",
          "highlight_edge_width", "highlight_edge_style", "spike_color", "spike_alpha"])}

One range can have its own label and look:
`highlight=[{{"range": [1570, 1640], "label": "G band", "color": "blue"}}]`. The keys
are `range`, `label` and the setting names without `highlight_`:
{", ".join(f"`{k}`" for k in ("color", "alpha", "hatch", "edge_color", "edge_width", "edge_style"))}.

{picture("marks_and_peaks.png")}
{picture("highlight.png")}

## Text on the plot

Mark labels (`C=C`), peak labels (`1585`) and highlight labels (`G band`)
each have the same settings, starting with `mark_label_`, `peak_label_` or
`highlight_label_`:

{table_of_texts()}

{section(["label_overlap"])}

Special characters: write them directly (cm⁻¹, ν(C=C), I₀, δ), or as math
text between dollar signs, e.g. `"$\\nu_{{as}}$(CH$_2$)"` for ν with "as" below
and CH with a small 2.

## Scale and extra axes

{section(["x_log", "y_log"])}

A second axis shows the same data in another unit. On top: the absolute
wavelength of each Raman shift for your laser (`"wavelength"`), or the x
values times a factor plus an offset (`"scale"`). On the right: the y values
times a factor plus an offset. Their ticks and numbers follow the `top_...`
and `right_...` tick settings (e.g. `top_tick_label_color`), their labels
the `xlabel_...` and `ylabel_...` settings.

{section(["top_axis", "top_axis_laser", "top_axis_scale", "top_axis_offset", "top_axis_label", "right_axis",
          "right_axis_scale", "right_axis_offset", "right_axis_label"])}

{picture("second_axes.png")}

## Gaps where data was cut

After `cut` (removing a range such as the silicon band), the line would be
drawn straight across the gap. With `cut_marks` the line breaks there and
// marks on the box show the gap (also on the top line when the box is closed).

{section(["cut_marks", "cut_mark_size", "cut_mark_color", "cut_mark_width"])}

{picture("cut_marks.png")}

## Line names and scale bar

Each spectrum's name can be written next to its line, with the legend, or
instead of it (`legend=False`): the two are set apart. A scale bar shows the
size of the y unit when the y numbers are hidden, as in stacked plots. When
both are on the same side, the bar stands past the names.

{section(["line_names", "line_name_position", "line_name_color", "line_name_alpha", "line_name_size",
          "line_name_weight", "line_name_italic", "line_name_font", "line_name_pad"])}

{section(["scale_bar", "scale_bar_label", "scale_bar_position", "scale_bar_color", "scale_bar_alpha",
          "scale_bar_width", "scale_bar_label_size", "scale_bar_label_weight", "scale_bar_label_italic",
          "scale_bar_label_font"])}

{picture("names_scale_bar.png")}

## Mean with a band (kind "mean")

{section(["mean_band", "mean_band_color", "mean_band_alpha"])}

{picture("mean_band.png")}

## Image of many spectra (kind "image")

{section(["color_limits", "colorbar", "colorbar_label", "colorbar_ticks_at", "colorbar_length",
          "colorbar_fraction", "image_y"])}

{picture("image.png")}

## Notes and arrows

Free text anywhere on the plot, an argument of `plot` (on the website at the
top level of the body): `notes=[{{"text": "D band", "x": 1350, "y": 0.8}}]`.
`x` and `y` are data values, or 0 to 1 of the box with `"coords": "axes"`.
`"arrow": [x, y]` draws an arrow from the note to that point (data values).
One note can change any of these for itself, with the names without
`note_`, e.g. `"color": "red"`:

{section(["note_color", "note_alpha", "note_size", "note_weight", "note_italic", "note_font", "note_rotation",
          "note_box", "note_box_color", "note_fill", "note_fill_alpha", "note_arrow_color", "note_arrow_alpha",
          "note_arrow_width", "note_arrow_style", "note_arrow_head"])}

## Inset (a zoomed view)

A small copy of the plot, zoomed on an x range, inside the box: an argument
of `plot`, `inset=[1550, 1650]` or `inset={{"region": [1550, 1650],
"position": "upper left", "scale": 0.35, "lines": false}}`. A legend at
`"best"` keeps clear of the inset.

{section(["inset_position", "inset_scale", "inset_lines", "inset_line_color", "inset_line_alpha",
          "inset_line_width", "inset_line_style", "inset_tick_label_size", "inset_tick_count"])}

{picture("notes_inset.png")}

## Panels (several plots in one figure)

`stk.panels` puts several plots in one figure, each with a letter. Every
entry is a Spectrum or collection, or a dict with `"data"`, any plot argument
(`"kind"`, `"title"`, `"peaks"` ...) and its own settings:

```python
stk.panels([c, {{"data": c, "kind": "stack", "peaks": 3}}, {{"data": c, "kind": "mean"}},
            {{"data": c, "kind": "image"}}], layout=[2, 2], size=(12, 7), save="figure.png")
```

`layout` is `[rows, columns]` (default one column for up to 3 panels, else
two columns); `share_x` / `share_y` give the panels one x (or y) range and
write the numbers only on the outer panels; `title` goes over the whole
figure; `"letter": "(z)"` (or `false`) in an entry replaces its letter. The
figure is `size` times the layout, so each panel has the size of one plot.
On the website: `{{"panels": [{{"data": ..., "kind": "stack", "settings": {{...}}}}, ...],
"layout": [2, 2], "share_x": true}}` in place of `"data"`.

{section(["panel_letters", "panel_letter_format", "panel_letter_case", "panel_letter_position",
          "panel_letter_size", "panel_letter_weight", "panel_letter_color", "panel_letter_alpha",
          "panel_letter_italic", "panel_letter_font"])}

![Four panels: lines, stacked with peak labels, mean, and image.](plotting/panels.png)

*Four panels: lines, stacked with peak labels, mean, and image.*

**Layout and sizes.** `layout` can also be text: rows split by `;`, one
letter per panel (in the order of the entries), the same letter in several
places for a panel across them, and `.` for an empty place: `"AA;BC"` is one
wide panel over two, `"AB;AC"` one tall panel beside two. `widths=[2, 1]`
and `heights=[1.3, 1]` give columns and rows their relative sizes (default all
equal). On the website: `"layout": "AA;BC", "widths": [2, 1]`.

**Shared parts.** Each of these is off by default, so a figure looks as
before unless you turn it on: `panel_legend` gives one legend for the whole
figure (each name once, so it suits panels that show the same spectra; the
legend settings still apply; on top it goes under the figure title); `panel_shared_labels` gives one x and/or y label for the
whole figure, with the text of `xlabel` / `ylabel` given to `panels`, else the
first panel's, styled by the `xlabel_...` / `ylabel_...` settings;
`panel_colorbar` gives all image panels one colour scale (`color_limits`,
else the 1st and 99th percentile of all of them) and one colour bar.

{section(["panel_spacing", "panel_spacing_x", "panel_spacing_y", "panel_legend", "panel_shared_labels",
          "panel_colorbar"])}

![The full range over two zooms (layout "AA;BC", heights [1.3, 1]), one legend on top and one y label.](plotting/panels_layout.png)

*The full range over two zooms (layout "AA;BC", heights [1.3, 1]), one legend on top and one y label.*

![Two image panels with one colour bar and one colour scale, and more space between the columns.](plotting/panels_colorbar.png)

*Two image panels with one colour bar and one colour scale, and more space between the columns.*

**Before/after views as panels (kind "compare").** A panel can be the view
`stk.compare` draws: `{{"data": before, "after": after, "kind": "compare"}}`
with optional `"index"` (which spectrum, by number or name), `"region"`,
`"removed"` and `"labels"`, as in `stk.compare`. The "removed" strip hangs
under its panel, so the boxes of a column still line up and `share_x` works
across ordinary and compare panels. The default title is the step and its
method, e.g. "baseline (airpls)" (`stk.compare` on its own figure also lists
the settings). On the website the panel is the same, with `"after"` as data.

```python
raw = stk.load("CV10-4M.xlsx"); clean = raw.despike()
stk.panels([{{"data": raw, "after": clean, "kind": "compare", "index": 3, "region": [1550, 1750]}},
            {{"data": clean, "after": clean.baseline(), "kind": "compare", "index": 3}}], layout=[1, 2])
```

![Two before/after panels: the baseline removed (with what was removed under it), then normalized (own scale on the right).](plotting/panels_compare.png)

*Two before/after panels: the baseline removed (with what was removed under it), then normalized (own scale on the right).*

## Groups (which sample each spectrum is)

Groups are stored with the data, one label per spectrum (`c.groups`), and
follow the spectra through every step. Set them in one of five ways:

| Way | Python | Website (`/groups`) |
|---|---|---|
| spectrum numbers or names | `c.set_groups({{"CV": range(0, 14), "MB": range(14, 19)}})` | `"groups": {{"CV": [0, 1, ...], "MB": [...]}}` |
| one label per spectrum | `c.set_groups(["CV", "CV", "MB", ...])` | `"groups": ["CV", "CV", "MB", ...]` |
| from the names | `c.set_groups("name")`: "CV 1", "CV_2" → CV | `"groups": "name"` |
| your own rule | `c.set_groups(pattern=r"^(\\w+)_")`: the part in brackets | `"pattern": "^(\\\\w+)_"` |
| the file | `stk.combine("CV.txt", "MB.txt", groups="file")` | (several files: later) |

`rename={{"CV10-4M": "CV"}}` renames groups. Nothing is guessed silently:
`c.suggest_groups()` (website: `/groups` with only `"data"`) proposes groups
with the reason, for the user to confirm, and names that only number the
spectra ("Spectrum 1", "Spot2") give no proposal. `c.by_group()` gives one
collection per group.

In plots: `color_by="group"` gives one colour and one legend entry per group
(`labels` then name the groups); with `kind="mean"`, one mean per group;
`stk.panels(c, by="group", kind="stack")` gives one panel per group, titled
with its name and number of spectra. Spectra in no group show as "(no group)".
On the website: `"color_by": "group"` next to `"data"`, or `"by": "group"`
with `"data"` and `"kind"` for panels; the data carries `"groups"`.

![Nine spectra in three groups: one colour per group, and one mean per group.](plotting/groups.png)

*Nine spectra in three groups: one colour per group, and one mean per group.*

## Reference lines at zero

{section(["zero_lines", "zero_line_style", "zero_line_width", "zero_line_color", "zero_line_alpha"])}

## Saving

{section(["tight", "dpi", "format", "color_mode"])}

Fonts: a font that is not installed is replaced by a similar one. Python
gives a warning; the website's answer has an `X-Warning` header naming it.
"""]
    missing = set(SETTINGS) - USED
    if missing:                                                      # every setting must appear somewhere
        raise SystemExit(f"Settings not placed in any section of the reference: {sorted(missing)}")
    DOC.write_text("".join(parts), encoding="utf-8")
    print(f"Wrote {DOC.relative_to(ROOT)} ({len(SETTINGS)} settings) and {len(PICTURE_LIST) + 5} pictures.")


if __name__ == "__main__":
    make_pictures()
    write_doc()
