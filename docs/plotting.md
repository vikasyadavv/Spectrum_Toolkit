# Plotting reference

Everything a figure can show and every setting that changes how it looks.
This file is written by `scripts/make_plotting_docs.py` from the settings in
`src/spectrum_toolkit/style.py`, so it always lists every setting
(219 today). Edit the script, not this file.

## How to use settings

**Python:** give any setting by name to a plot, on top of a style preset:
```python
c.plot(style="publication", top_tick_length=8, xlabel_color="blue")
stk.set_style("matlab", legend_box=True)      # default for every later plot
stk.save_style("matlab", "my_style", box_width=2)   # reuse with style="my_style.json"
```

**Website (`/figure`):** the same names go in `"settings"`:
```json
{"kind": "lines", "style": "publication", "settings": {"top_tick_length": 8, "xlabel_color": "blue"}, "data": {...}}
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

| Setting | Default | What it does |
|---|---|---|
| `size` | "screen" | figure size: a name in SIZES or (width, height) in "units" |
| `units` | "cm" | "cm" or "in" for size |
| `aspect` | *(not set)* | plot area shape: None (fills the figure), "square", or height/width e.g. 0.75 |

## Text: the base for all text

| Setting | Default | What it does |
|---|---|---|
| `font` | "sans-serif" | font name for all text, e.g. "Arial", "Times New Roman"; falls back if not installed |
| `font_size` | 10 | base text size in points (tick labels use it unless tick_label_size is set) |
| `font_weight` | "normal" | "normal" or "bold": all text unless a more specific _weight is set |

## Box (the frame around the plot)

General:

| Setting | Default | What it does |
|---|---|---|
| `box` | "open" | "closed" (all four sides), "open" (left and bottom) or "none" |
| `box_width` | 0.8 | box line width in points |
| `box_color` | "black" | box line colour |
| `box_alpha` | 1.0 | box line transparency, 0 to 1 |
| `box_style` | "-" | box line type: "-", "--", ":" or "-." |
| `background` | "white" | figure background colour (around the plot); "none" for transparent |
| `background_alpha` | 1.0 | figure background transparency, 0 to 1 |
| `plot_background` | *(not set)* | background colour inside the box; None = background |
| `plot_background_alpha` | *(not set)* | transparency inside the box, 0 to 1; None = background_alpha |

One side (`bottom`, `top`, `left`, `right`); each falls back to the general setting:

| Setting | Default | What it does |
|---|---|---|
| `bottom_box` | *(not set)* | box line on the bottom side: True/False; None = box |
| `bottom_box_width` | *(not set)* | box_width for the bottom side only; None = box_width |
| `bottom_box_color` | *(not set)* | box_color for the bottom side only; None = box_color |
| `bottom_box_alpha` | *(not set)* | box_alpha for the bottom side only; None = box_alpha |
| `bottom_box_style` | *(not set)* | box_style for the bottom side only; None = box_style |
| `top_box` | *(not set)* | box line on the top side: True/False; None = box |
| `top_box_width` | *(not set)* | box_width for the top side only; None = box_width |
| `top_box_color` | *(not set)* | box_color for the top side only; None = box_color |
| `top_box_alpha` | *(not set)* | box_alpha for the top side only; None = box_alpha |
| `top_box_style` | *(not set)* | box_style for the top side only; None = box_style |
| `left_box` | *(not set)* | box line on the left side: True/False; None = box |
| `left_box_width` | *(not set)* | box_width for the left side only; None = box_width |
| `left_box_color` | *(not set)* | box_color for the left side only; None = box_color |
| `left_box_alpha` | *(not set)* | box_alpha for the left side only; None = box_alpha |
| `left_box_style` | *(not set)* | box_style for the left side only; None = box_style |
| `right_box` | *(not set)* | box line on the right side: True/False; None = box |
| `right_box_width` | *(not set)* | box_width for the right side only; None = box_width |
| `right_box_color` | *(not set)* | box_color for the right side only; None = box_color |
| `right_box_alpha` | *(not set)* | box_alpha for the right side only; None = box_alpha |
| `right_box_style` | *(not set)* | box_style for the right side only; None = box_style |

![Box set per side: thick left line, dashed red top line, no right line; light grey inside the box.](plotting/box_sides.png)

*Box set per side: thick left line, dashed red top line, no right line; light grey inside the box.*

Python:
```python
c.plot(box='closed', left_box_width=2.5, top_box_color='red', top_box_style='--', right_box=False, plot_background='0.94', grid=False)
```
Website (`/figure`): put the style settings in `"settings"` (title, xlabel and ylabel go at the top level):
```json
{"box": "closed", "left_box_width": 2.5, "top_box_color": "red", "top_box_style": "--", "right_box": false, "plot_background": "0.94", "grid": false}
```


## Ticks and tick labels

**Which sides** have tick marks and numbers: `tick_sides` and
`tick_label_sides` (lists), or one side at a time with `bottom_ticks`,
`top_tick_labels` ... (true / false).

General:

| Setting | Default | What it does |
|---|---|---|
| `tick_direction` | "out" | "in", "out" or "both" (through the box line); old name: ticks |
| `tick_length` | 4.0 | tick length in points |
| `tick_width` | *(not set)* | tick line width; None = box_width |
| `tick_color` | *(not set)* | tick mark colour; None = box_color |
| `tick_alpha` | 1.0 | tick mark transparency, 0 to 1 |
| `tick_sides` | ["bottom", "left"] | sides with tick marks: any of "bottom", "top", "left", "right" |
| `tick_label_sides` | ["bottom", "left"] | sides with tick labels (numbers) |
| `tick_label_size` | *(not set)* | tick label (number) size in points; None = font_size |
| `tick_label_color` | "black" | tick label colour |
| `tick_label_alpha` | 1.0 | tick label transparency, 0 to 1 |
| `tick_label_weight` | *(not set)* | "normal" or "bold"; None = font_weight |
| `tick_label_italic` | false | tick labels in italics |
| `tick_label_font` | *(not set)* | tick label font; None = font |
| `tick_label_rotation` | 0 | tick label rotation in degrees, e.g. 45 or 90 |
| `tick_label_pad` | 3.5 | distance between tick and tick label, in points |
| `minor_ticks` | false | small ticks between the numbered ones |
| `minor_tick_length` | *(not set)* | minor tick length in points; None = 0.55 x tick_length |
| `minor_tick_count` | *(not set)* | number of minor ticks between two numbered ticks; None = automatic |
| `x_tick_step` | *(not set)* | distance between x ticks, e.g. 200; None = automatic |
| `y_tick_step` | *(not set)* | distance between y ticks; None = automatic |
| `x_tick_format` | *(not set)* | number format of x tick labels, e.g. "%.2f"; None = automatic |
| `y_tick_format` | *(not set)* | number format of y tick labels |

One axis (`x_` = bottom and top, `y_` = left and right); each falls back to the general setting:

| Setting | Default | What it does |
|---|---|---|
| `x_tick_direction` | *(not set)* | tick_direction for the x axis only; None = tick_direction |
| `x_tick_length` | *(not set)* | tick_length for the x axis only; None = tick_length |
| `x_tick_width` | *(not set)* | tick_width for the x axis only; None = tick_width |
| `x_tick_color` | *(not set)* | tick_color for the x axis only; None = tick_color |
| `x_tick_alpha` | *(not set)* | tick_alpha for the x axis only; None = tick_alpha |
| `x_tick_label_size` | *(not set)* | tick_label_size for the x axis only; None = tick_label_size |
| `x_tick_label_color` | *(not set)* | tick_label_color for the x axis only; None = tick_label_color |
| `x_tick_label_alpha` | *(not set)* | tick_label_alpha for the x axis only; None = tick_label_alpha |
| `x_tick_label_weight` | *(not set)* | tick_label_weight for the x axis only; None = tick_label_weight |
| `x_tick_label_italic` | *(not set)* | tick_label_italic for the x axis only; None = tick_label_italic |
| `x_tick_label_font` | *(not set)* | tick_label_font for the x axis only; None = tick_label_font |
| `x_tick_label_rotation` | *(not set)* | tick_label_rotation for the x axis only; None = tick_label_rotation |
| `x_tick_label_pad` | *(not set)* | tick_label_pad for the x axis only; None = tick_label_pad |
| `x_minor_ticks` | *(not set)* | minor_ticks for the x axis only; None = minor_ticks |
| `x_minor_tick_length` | *(not set)* | minor_tick_length for the x axis only; None = minor_tick_length |
| `x_minor_tick_count` | *(not set)* | minor_tick_count for the x axis only; None = minor_tick_count |
| `y_tick_direction` | *(not set)* | tick_direction for the y axis only; None = tick_direction |
| `y_tick_length` | *(not set)* | tick_length for the y axis only; None = tick_length |
| `y_tick_width` | *(not set)* | tick_width for the y axis only; None = tick_width |
| `y_tick_color` | *(not set)* | tick_color for the y axis only; None = tick_color |
| `y_tick_alpha` | *(not set)* | tick_alpha for the y axis only; None = tick_alpha |
| `y_tick_label_size` | *(not set)* | tick_label_size for the y axis only; None = tick_label_size |
| `y_tick_label_color` | *(not set)* | tick_label_color for the y axis only; None = tick_label_color |
| `y_tick_label_alpha` | *(not set)* | tick_label_alpha for the y axis only; None = tick_label_alpha |
| `y_tick_label_weight` | *(not set)* | tick_label_weight for the y axis only; None = tick_label_weight |
| `y_tick_label_italic` | *(not set)* | tick_label_italic for the y axis only; None = tick_label_italic |
| `y_tick_label_font` | *(not set)* | tick_label_font for the y axis only; None = tick_label_font |
| `y_tick_label_rotation` | *(not set)* | tick_label_rotation for the y axis only; None = tick_label_rotation |
| `y_tick_label_pad` | *(not set)* | tick_label_pad for the y axis only; None = tick_label_pad |
| `y_minor_ticks` | *(not set)* | minor_ticks for the y axis only; None = minor_ticks |
| `y_minor_tick_length` | *(not set)* | minor_tick_length for the y axis only; None = minor_tick_length |
| `y_minor_tick_count` | *(not set)* | minor_tick_count for the y axis only; None = minor_tick_count |

One side; each falls back to the axis setting, then the general one:

| Setting | Default | What it does |
|---|---|---|
| `bottom_ticks` | *(not set)* | tick marks on the bottom side: True/False; None = tick_sides |
| `bottom_tick_labels` | *(not set)* | tick labels on the bottom side: True/False; None = tick_label_sides |
| `bottom_tick_direction` | *(not set)* | tick_direction for the bottom side only; None = x_tick_direction |
| `bottom_tick_length` | *(not set)* | tick_length for the bottom side only; None = x_tick_length |
| `bottom_tick_width` | *(not set)* | tick_width for the bottom side only; None = x_tick_width |
| `bottom_tick_color` | *(not set)* | tick_color for the bottom side only; None = x_tick_color |
| `bottom_tick_alpha` | *(not set)* | tick_alpha for the bottom side only; None = x_tick_alpha |
| `bottom_tick_label_size` | *(not set)* | tick_label_size for the bottom side only; None = x_tick_label_size |
| `bottom_tick_label_color` | *(not set)* | tick_label_color for the bottom side only; None = x_tick_label_color |
| `bottom_tick_label_alpha` | *(not set)* | tick_label_alpha for the bottom side only; None = x_tick_label_alpha |
| `bottom_tick_label_weight` | *(not set)* | tick_label_weight for the bottom side only; None = x_tick_label_weight |
| `bottom_tick_label_italic` | *(not set)* | tick_label_italic for the bottom side only; None = x_tick_label_italic |
| `bottom_tick_label_font` | *(not set)* | tick_label_font for the bottom side only; None = x_tick_label_font |
| `bottom_tick_label_rotation` | *(not set)* | tick_label_rotation for the bottom side only; None = x_tick_label_rotation |
| `top_ticks` | *(not set)* | tick marks on the top side: True/False; None = tick_sides |
| `top_tick_labels` | *(not set)* | tick labels on the top side: True/False; None = tick_label_sides |
| `top_tick_direction` | *(not set)* | tick_direction for the top side only; None = x_tick_direction |
| `top_tick_length` | *(not set)* | tick_length for the top side only; None = x_tick_length |
| `top_tick_width` | *(not set)* | tick_width for the top side only; None = x_tick_width |
| `top_tick_color` | *(not set)* | tick_color for the top side only; None = x_tick_color |
| `top_tick_alpha` | *(not set)* | tick_alpha for the top side only; None = x_tick_alpha |
| `top_tick_label_size` | *(not set)* | tick_label_size for the top side only; None = x_tick_label_size |
| `top_tick_label_color` | *(not set)* | tick_label_color for the top side only; None = x_tick_label_color |
| `top_tick_label_alpha` | *(not set)* | tick_label_alpha for the top side only; None = x_tick_label_alpha |
| `top_tick_label_weight` | *(not set)* | tick_label_weight for the top side only; None = x_tick_label_weight |
| `top_tick_label_italic` | *(not set)* | tick_label_italic for the top side only; None = x_tick_label_italic |
| `top_tick_label_font` | *(not set)* | tick_label_font for the top side only; None = x_tick_label_font |
| `top_tick_label_rotation` | *(not set)* | tick_label_rotation for the top side only; None = x_tick_label_rotation |
| `left_ticks` | *(not set)* | tick marks on the left side: True/False; None = tick_sides |
| `left_tick_labels` | *(not set)* | tick labels on the left side: True/False; None = tick_label_sides |
| `left_tick_direction` | *(not set)* | tick_direction for the left side only; None = y_tick_direction |
| `left_tick_length` | *(not set)* | tick_length for the left side only; None = y_tick_length |
| `left_tick_width` | *(not set)* | tick_width for the left side only; None = y_tick_width |
| `left_tick_color` | *(not set)* | tick_color for the left side only; None = y_tick_color |
| `left_tick_alpha` | *(not set)* | tick_alpha for the left side only; None = y_tick_alpha |
| `left_tick_label_size` | *(not set)* | tick_label_size for the left side only; None = y_tick_label_size |
| `left_tick_label_color` | *(not set)* | tick_label_color for the left side only; None = y_tick_label_color |
| `left_tick_label_alpha` | *(not set)* | tick_label_alpha for the left side only; None = y_tick_label_alpha |
| `left_tick_label_weight` | *(not set)* | tick_label_weight for the left side only; None = y_tick_label_weight |
| `left_tick_label_italic` | *(not set)* | tick_label_italic for the left side only; None = y_tick_label_italic |
| `left_tick_label_font` | *(not set)* | tick_label_font for the left side only; None = y_tick_label_font |
| `left_tick_label_rotation` | *(not set)* | tick_label_rotation for the left side only; None = y_tick_label_rotation |
| `right_ticks` | *(not set)* | tick marks on the right side: True/False; None = tick_sides |
| `right_tick_labels` | *(not set)* | tick labels on the right side: True/False; None = tick_label_sides |
| `right_tick_direction` | *(not set)* | tick_direction for the right side only; None = y_tick_direction |
| `right_tick_length` | *(not set)* | tick_length for the right side only; None = y_tick_length |
| `right_tick_width` | *(not set)* | tick_width for the right side only; None = y_tick_width |
| `right_tick_color` | *(not set)* | tick_color for the right side only; None = y_tick_color |
| `right_tick_alpha` | *(not set)* | tick_alpha for the right side only; None = y_tick_alpha |
| `right_tick_label_size` | *(not set)* | tick_label_size for the right side only; None = y_tick_label_size |
| `right_tick_label_color` | *(not set)* | tick_label_color for the right side only; None = y_tick_label_color |
| `right_tick_label_alpha` | *(not set)* | tick_label_alpha for the right side only; None = y_tick_label_alpha |
| `right_tick_label_weight` | *(not set)* | tick_label_weight for the right side only; None = y_tick_label_weight |
| `right_tick_label_italic` | *(not set)* | tick_label_italic for the right side only; None = y_tick_label_italic |
| `right_tick_label_font` | *(not set)* | tick_label_font for the right side only; None = y_tick_label_font |
| `right_tick_label_rotation` | *(not set)* | tick_label_rotation for the right side only; None = y_tick_label_rotation |

![Ticks set per side: x inward, y outward; long red ticks on top with rotated red numbers; right ticks blue and see-through; minor ticks on x only.](plotting/ticks_per_side.png)

*Ticks set per side: x inward, y outward; long red ticks on top with rotated red numbers; right ticks blue and see-through; minor ticks on x only.*

Python:
```python
c.plot(box='closed', tick_sides=['bottom', 'top', 'left', 'right'], tick_label_sides=['bottom', 'top', 'left'], x_tick_direction='in', y_tick_direction='out', top_tick_length=9, top_tick_color='red', top_tick_label_color='red', top_tick_label_rotation=45, right_tick_color='cmyk(1, 0.5, 0, 0)', right_tick_alpha=0.5, right_tick_length=7, x_minor_ticks=True, minor_tick_count=3, grid=False)
```
Website (`/figure`): put the style settings in `"settings"` (title, xlabel and ylabel go at the top level):
```json
{"box": "closed", "tick_sides": ["bottom", "top", "left", "right"], "tick_label_sides": ["bottom", "top", "left"], "x_tick_direction": "in", "y_tick_direction": "out", "top_tick_length": 9, "top_tick_color": "red", "top_tick_label_color": "red", "top_tick_label_rotation": 45, "right_tick_color": "cmyk(1, 0.5, 0, 0)", "right_tick_alpha": 0.5, "right_tick_length": 7, "x_minor_ticks": true, "minor_tick_count": 3, "grid": false}
```


Notes:
- `tick_direction` "both" draws the tick through the box line, half in and half out.
- Minor ticks are shorter (0.55 x) and thinner (0.75 x) than the numbered
  ticks unless `minor_tick_length` is set; they take the colour, direction
  and transparency of their side.
- The distance of the numbers (`tick_label_pad`) is per axis, not per side.
- The old name `ticks` (for `tick_direction`) still works in saved styles.

## Grid

| Setting | Default | What it does |
|---|---|---|
| `grid` | true | grid lines on or off |
| `grid_color` | "#b0b0b0" | grid colour |
| `grid_style` | "-" | "-", "--", ":" or "-." |
| `grid_width` | 0.6 | grid line width |
| `grid_alpha` | 0.4 | grid opacity 0 to 1 |

## Axis labels

General (both axes):

| Setting | Default | What it does |
|---|---|---|
| `label_size` | 11 | axis label size in points |
| `label_weight` | "normal" | "normal" or "bold": axis labels |
| `label_color` | "black" | axis label colour |
| `label_alpha` | 1.0 | axis label transparency, 0 to 1 |
| `label_italic` | false | axis labels in italics |
| `label_font` | *(not set)* | axis label font; None = font |
| `label_pad` | 4.0 | distance between the axis label and the tick labels, in points |

One axis; each falls back to the general setting:

| Setting | Default | What it does |
|---|---|---|
| `xlabel_size` | *(not set)* | label_size for the x axis label only; None = label_size |
| `xlabel_weight` | *(not set)* | label_weight for the x axis label only; None = label_weight |
| `xlabel_color` | *(not set)* | label_color for the x axis label only; None = label_color |
| `xlabel_alpha` | *(not set)* | label_alpha for the x axis label only; None = label_alpha |
| `xlabel_italic` | *(not set)* | label_italic for the x axis label only; None = label_italic |
| `xlabel_font` | *(not set)* | label_font for the x axis label only; None = label_font |
| `xlabel_pad` | *(not set)* | label_pad for the x axis label only; None = label_pad |
| `xlabel_rotation` | 0 | x axis label rotation in degrees |
| `ylabel_size` | *(not set)* | label_size for the y axis label only; None = label_size |
| `ylabel_weight` | *(not set)* | label_weight for the y axis label only; None = label_weight |
| `ylabel_color` | *(not set)* | label_color for the y axis label only; None = label_color |
| `ylabel_alpha` | *(not set)* | label_alpha for the y axis label only; None = label_alpha |
| `ylabel_italic` | *(not set)* | label_italic for the y axis label only; None = label_italic |
| `ylabel_font` | *(not set)* | label_font for the y axis label only; None = label_font |
| `ylabel_pad` | *(not set)* | label_pad for the y axis label only; None = label_pad |
| `ylabel_rotation` | 90 | y axis label rotation in degrees |

The label text itself is set with `xlabel` and `ylabel` (default: the units
of the data, else "x" and "Intensity").

## Title

The text is set with `title`.

| Setting | Default | What it does |
|---|---|---|
| `title_size` | 11 | title size in points |
| `title_weight` | *(not set)* | "normal" or "bold"; None = font_weight |
| `title_color` | "black" | title colour |
| `title_alpha` | 1.0 | title transparency, 0 to 1 |
| `title_italic` | false | title in italics |
| `title_font` | *(not set)* | title font; None = font |
| `title_location` | "center" | "left", "center" or "right" |
| `title_pad` | 6.0 | distance between the title and the plot, in points |

![Axis labels and title each set on their own: blue italic x label, large bold y label, title on the left in dark red italics.](plotting/labels_and_title.png)

*Axis labels and title each set on their own: blue italic x label, large bold y label, title on the left in dark red italics.*

Python:
```python
c.plot(xlabel_color='blue', xlabel_italic=True, ylabel_size=15, ylabel_weight='bold', title='Three samples', title_location='left', title_color=[160, 0, 0], title_italic=True, title_size=14)
```
Website (`/figure`): put the style settings in `"settings"` (title, xlabel and ylabel go at the top level):
```json
{"xlabel_color": "blue", "xlabel_italic": true, "ylabel_size": 15, "ylabel_weight": "bold", "title": "Three samples", "title_location": "left", "title_color": [160, 0, 0], "title_italic": true, "title_size": 14}
```


## Legend

When and where:

| Setting | Default | What it does |
|---|---|---|
| `legend` | "auto" | True, False or "auto" (shown for 2 to 10 lines) |
| `legend_location` | "best" | e.g. "best", "upper right", "lower left", "outside" (right of the plot) |
| `legend_position` | *(not set)* | exact place of the legend's corner as [x, y], 0 to 1 of the plot; overrides legend_location |
| `legend_columns` | 1 | number of columns of legend entries |
| `legend_order` | "normal" | "normal" (as drawn) or "reverse" |

Entry text and heading:

| Setting | Default | What it does |
|---|---|---|
| `legend_size` | 9 | legend text size |
| `legend_weight` | "normal" | "normal" or "bold" |
| `legend_color` | "black" | legend text colour |
| `legend_alpha` | 1.0 | legend text transparency, 0 to 1 |
| `legend_italic` | false | legend text in italics |
| `legend_font` | *(not set)* | legend font; None = font |
| `legend_title` | *(not set)* | a heading above the legend entries |
| `legend_title_size` | *(not set)* | legend heading size; None = legend_size |
| `legend_title_weight` | "bold" | "normal" or "bold" |

Frame:

| Setting | Default | What it does |
|---|---|---|
| `legend_box` | false | frame around the legend |
| `legend_box_color` | "#cccccc" | frame line colour |
| `legend_box_width` | 0.8 | frame line width |
| `legend_box_alpha` | 1.0 | frame line transparency, 0 to 1 |
| `legend_box_round` | true | rounded frame corners |
| `legend_fill` | "white" | colour inside the legend frame; "none" for no fill |
| `legend_fill_alpha` | 0.8 | legend fill transparency, 0 to 1 |
| `legend_shadow` | false | a shadow behind the legend frame |

Entry layout:

| Setting | Default | What it does |
|---|---|---|
| `legend_line_length` | 2.0 | length of the line sample, in font sizes |
| `legend_marker_scale` | 1.0 | marker size in the legend relative to the plot |
| `legend_spacing` | 0.5 | vertical space between entries, in font sizes |

The names in the legend are the spectrum names, or `labels` (a list, one
per spectrum).

![Legend with a heading, three columns in reverse order, a green frame and a light yellow, half see-through fill; italic purple entries.](plotting/legend.png)

*Legend with a heading, three columns in reverse order, a green frame and a light yellow, half see-through fill; italic purple entries.*

Python:
```python
c.plot(legend=True, legend_box=True, legend_title='Samples', legend_columns=3, legend_order='reverse', legend_box_color='green', legend_box_width=1.5, legend_fill='#ffffcc', legend_fill_alpha=0.6, legend_color='purple', legend_italic=True, legend_location='upper left')
```
Website (`/figure`): put the style settings in `"settings"` (title, xlabel and ylabel go at the top level):
```json
{"legend": true, "legend_box": true, "legend_title": "Samples", "legend_columns": 3, "legend_order": "reverse", "legend_box_color": "green", "legend_box_width": 1.5, "legend_fill": "#ffffcc", "legend_fill_alpha": 0.6, "legend_color": "purple", "legend_italic": true, "legend_location": "upper left"}
```


## Spectra (data lines)

| Setting | Default | What it does |
|---|---|---|
| `line_width` | 1.0 | spectrum line width in points |
| `line_style` | "-" | "-" solid, "--" dashed, ":" dotted, "-." dash-dot, "none" (markers only) |
| `marker` | *(not set)* | point marker: None, "o", ".", "s", "^", "x" ... |
| `marker_size` | 3.0 | marker size in points |
| `colors` | "matplotlib" | colours of successive lines: a name in PALETTES or a list of colours |
| `cmap` | "viridis" | colour map for many spectra (more than 10) and images |

More line settings (transparency, MATLAB-style codes such as `"o--"`, one
look per spectrum) are planned; see `docs/plotting_wishlist.md`.

## Reference lines at zero

| Setting | Default | What it does |
|---|---|---|
| `zero_lines` | *(not set)* | dashed lines at 0: None, "x" (horizontal y=0), "y" (vertical x=0) or "both" |
| `zero_line_style` | "--" | style of the zero lines |
| `zero_line_width` | 1.0 | width of the zero lines |
| `zero_line_color` | "black" | colour of the zero lines |

## Saving

| Setting | Default | What it does |
|---|---|---|
| `dpi` | 300 | dots per inch for png, tiff and jpg |
| `format` | "png" | file type when the name has no extension: png, tiff, jpg, pdf, svg, eps |
| `color_mode` | "rgb" | "rgb" or "cmyk" (cmyk only for tiff and jpg) |
