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
from spectrum_toolkit.style import AXIS_OF_SIDE, SETTINGS, SIDES

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "plotting.md"
PICTURES = ROOT / "docs" / "plotting"


# ------------------------------------------------------------------ example data
def example_data() -> SpectrumCollection:
    """Three made-up Raman-like spectra (so the pictures need no data files)."""
    x = np.linspace(400, 1800, 1400)
    rng = np.random.default_rng(1)
    bands = [(915, 0.7, 6), (1180, 0.7, 10), (1370, 0.6, 18), (1585, 0.75, 7), (1620, 1.0, 7)]
    Y = []
    for k in range(3):
        y = sum(h * (1 - 0.1 * k) / (1 + ((x - c) / w) ** 2) for c, h, w in bands)
        Y.append(y + rng.normal(0, 0.01, x.size))
    return SpectrumCollection(x, np.array(Y), names=["Sample A", "Sample B", "Sample C"], x_unit="Raman shift (cm⁻¹)",
                              y_unit="Intensity")


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
    ("legend.png", "Legend with a heading, three columns in reverse order, a green frame and a light "
                   "yellow, half see-through fill; italic purple entries.",
     dict(legend=True, legend_box=True, legend_title="Samples", legend_columns=3, legend_order="reverse",
          legend_box_color="green", legend_box_width=1.5, legend_fill="#ffffcc", legend_fill_alpha=0.6,
          legend_color="purple", legend_italic=True, legend_location="upper left")),
]


def make_pictures() -> None:
    """Draw every picture in PICTURE_LIST into docs/plotting/."""
    import matplotlib.pyplot as plt
    PICTURES.mkdir(parents=True, exist_ok=True)
    data = example_data()
    for name, _, settings in PICTURE_LIST:
        settings = dict(settings)
        extra = {k: settings.pop(k) for k in ("title",) if k in settings}
        ax = data.plot(size=(16, 8), **extra, **settings)
        stk.export(ax, PICTURES / name, dpi=110)
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
    website = json.dumps(settings, ensure_ascii=False)
    return (f"![{caption}](plotting/{name})\n\n*{caption}*\n\nPython:\n```python\nc.plot({python})\n```\n"
            f"Website (`/figure`): put the style settings in `\"settings\"` (title, xlabel and ylabel go at the "
            f"top level):\n```json\n{website}\n```\n")


def group(prefixes: tuple, keys) -> list[str]:
    """Every name prefix_key for the given prefixes and keys, if it is a setting."""
    return [f"{p}{k}" for p in prefixes for k in keys if f"{p}{k}" in SETTINGS]


def write_doc() -> None:
    general_ticks = ["tick_direction", "tick_length", "tick_width", "tick_color", "tick_alpha", "tick_sides",
                     "tick_label_sides", "tick_label_size", "tick_label_color", "tick_label_alpha",
                     "tick_label_weight", "tick_label_italic", "tick_label_font", "tick_label_rotation",
                     "tick_label_pad", "minor_ticks", "minor_tick_length", "minor_tick_count", "x_tick_step",
                     "y_tick_step", "x_tick_format", "y_tick_format"]
    tick_keys = ["tick_direction", "tick_length", "tick_width", "tick_color", "tick_alpha", "tick_label_size",
                 "tick_label_color", "tick_label_alpha", "tick_label_weight", "tick_label_italic",
                 "tick_label_font", "tick_label_rotation", "tick_label_pad", "minor_ticks", "minor_tick_length",
                 "minor_tick_count"]
    label_keys = ["label_size", "label_weight", "label_color", "label_alpha", "label_italic", "label_font",
                  "label_pad", "label_rotation"]
    box_keys = ["box", "box_width", "box_color", "box_alpha", "box_style"]
    used = set()

    def section(names):
        used.update(names)
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

A wrong name or value is an error that says what is allowed, for example
`tick_alpha is a transparency from 0 (invisible) to 1 (solid); got 2.`

## Presets

`clean` (default), `publication`, `matlab`, `matplotlib`; see the top of
`style.py` for what each sets. Every setting below can be changed on top.

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
| `_font` | font name | e.g. `"Arial"`, `"Times New Roman"`; falls back if not installed |
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

## Figure size and shape

{section(["size", "units", "aspect"])}

## Text: the base for all text

{section(["font", "font_size", "font_weight"])}

## Box (the frame around the plot)

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

{section(["legend", "legend_location", "legend_position", "legend_columns", "legend_order"])}

Entry text and heading:

{section(["legend_size", "legend_weight", "legend_color", "legend_alpha", "legend_italic", "legend_font",
          "legend_title", "legend_title_size", "legend_title_weight"])}

Frame:

{section(["legend_box", "legend_box_color", "legend_box_width", "legend_box_alpha", "legend_box_round",
          "legend_fill", "legend_fill_alpha", "legend_shadow"])}

Entry layout:

{section(["legend_line_length", "legend_marker_scale", "legend_spacing"])}

The names in the legend are the spectrum names, or `labels` (a list, one
per spectrum).

{picture("legend.png")}

## Spectra (data lines)

{section(["line_width", "line_style", "marker", "marker_size", "colors", "cmap"])}

More line settings (transparency, MATLAB-style codes such as `"o--"`, one
look per spectrum) are planned; see `docs/plotting_wishlist.md`.

## Reference lines at zero

{section(["zero_lines", "zero_line_style", "zero_line_width", "zero_line_color"])}

## Saving

{section(["dpi", "format", "color_mode"])}
"""]
    missing = set(SETTINGS) - used
    if missing:                                                      # every setting must appear somewhere
        raise SystemExit(f"Settings not placed in any section of the reference: {sorted(missing)}")
    DOC.write_text("".join(parts), encoding="utf-8")
    print(f"Wrote {DOC.relative_to(ROOT)} ({len(SETTINGS)} settings) and {len(PICTURE_LIST)} pictures.")


if __name__ == "__main__":
    make_pictures()
    write_doc()
