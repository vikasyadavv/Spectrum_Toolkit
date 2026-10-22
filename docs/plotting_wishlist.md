# Plotting: wish list for discussion (2026-10-21)

**Status:** agreed 2026-10-21 (naming rule yes; full per-side customisation for everything;
MATLAB codes yes; order as suggested; section 7 discussed later, line by line).
Built: **4 (box, ticks)**, **6 (labels, title, legend)**, **1 (spectral lines)** and **2 + 3 (marks, peak
labels, highlights, text on the plot)** and **7, items 1 to 14** (axis limits, log scales, second axes, cut
marks, line names, scale bar, mean band, image options, notes, inset, panels, tight, font warning), see
`docs/plotting.md`. Item 12, panels a to f, built too (layout text such as "AA;BC", `widths` / `heights`,
`panel_spacing_x` / `panel_spacing_y`, one figure legend, shared axis titles, one shared colour bar; all off by
default). Item 15, the service part (`POST /style-check`), built too. Item 12 g (before/after views as panels) and h
(groups stored with the data: set five ways, suggested but never guessed, colour / mean / panel per group) built
too. Waiting in `docs/bucket_list.md`: saved styles on the website (15 A), item 16, and uploading several files at once.

This list is **for discussion only**. No code has changed. Each item says:
- what the code **already does** (with the setting name, so you can try it today);
- what is **missing**;
- the setting I **propose**.

We agree on the list first, then build it section by section. After each
section, the full check (A to L plus the new tests) runs again so nothing breaks.

Points 1 to 6 are yours, in your order. Point 7 holds my additions. The
questions we must settle first are at the end.

---

## 0. One rule for every feature (proposal)

Every element of a figure gets its **own** group of settings, with the same
endings everywhere. Once you know one element, you know them all:

| Ending | Meaning | Example |
|---|---|---|
| `_color` | colour | `mark_color` |
| `_alpha` | transparency, 0 (invisible) to 1 (solid) | `mark_alpha` |
| `_width` | line width in points | `mark_width` |
| `_style` | line type: `-` `--` `:` `-.` | `mark_style` |
| `_size` | text or marker size in points | `peak_label_size` |
| `_weight` | `normal` or `bold` | `title_weight` |
| `_italic` | true / false | `xlabel_italic` |
| `_font` | font name | `legend_font` |

Every setting has one default. Leaving it empty means "use the default", so
simple plots stay simple. Each one is also listed in `/options` with its
meaning, so the website can build its controls from that list automatically.

**Colours, everywhere.** Every colour setting accepts the same forms:
- a name (`"red"`);
- hex (`"#1f77b4"`);
- RGB as 0–1 or 0–255 (`[0, 0.45, 0.74]`, `[0, 114, 189]`);
- RGBA (with transparency);
- grey as one number (`"0.5"`);
- **CMYK** written as `"cmyk(0, 0.5, 1, 0)"`.

The plotting library only understands RGB, so CMYK input is converted to RGB
for drawing. Saving as CMYK TIFF/JPG (which already works) converts the whole
picture back to CMYK.

---

## 1. Spectral lines

| What | Now | Missing → proposal |
|---|---|---|
| One colour for all lines | `color` (Python only; not reachable from /figure, where `color` means rgb/cmyk) | rename the save option to `color_mode` on /figure, and allow `line_color` |
| A colour per spectrum | palette (`colors`: matplotlib, matlab, colorblind, black, or a list of colours) | ✓ exists; add more palettes (e.g. tab20, a dark set, colour maps by name) |
| Transparency | only automatic for >200 spectra | `line_alpha` (all) or a list (one per spectrum) |
| Line type | `line_style`: `-` `--` `:` `-.` `none` | ✓ exists; also allow a list, one per spectrum |
| Markers | `marker`: `o` `.` `s` `^` `x` …; `marker_size` | ✓ exists; add `marker_color` (edge) and `marker_fill` (inside, or `none` for hollow), `marker_alpha`, `marker_edge_width`, and `marker_every` (a marker every n points, since 1 400 markers on one line is a solid blob) |
| MATLAB-style short codes `o-`, `o--`, `*-`, `*--`, `.`, `*` | no | `line_format: "o--"`: one setting that sets marker + line type together, exactly like MATLAB; also a list, one per spectrum |
| Different looks per spectrum | no | `line_color`, `line_style`, `line_width`, `line_alpha`, `marker`, `line_format` each accept one value **or** a list (one per spectrum, repeating if shorter) |
| Highlighted spectrum | no (K5 `highlight: 0` was my wrong guess) | `emphasize: [0, 3]`: those spectra drawn on top, thicker and solid, with the rest faded (`emphasize_width`, `faded_alpha`) |
| Fill under a line | no | `fill: true`, `fill_alpha` (useful for one spectrum or the mean) |

## 2. Peak lines (marks), peak labels and highlighted ranges

**Mark lines** (`marks={1620: "C=C"}`) are now fixed: grey, dotted, width 0.9, label 75 % of font size.
Proposal: `mark_color`, `mark_style` (`-` `--` `:` `-.`), `mark_width`, `mark_alpha`.
The extent becomes `mark_span`: full height (now), from the axis up to the peak, or a short tick above the peak.
Each mark can also override these individually, e.g. `{"1620": {"label": "C=C", "color": "red", "style": "--"}}`.

**Peak position labels** (`peaks=5`) are now fixed: black, rotated 90°, 75 % size.
Proposal:
- `peak_label_color`, `peak_label_alpha`, `peak_label_size`, `peak_label_weight`, `peak_label_italic`, `peak_label_font`, `peak_label_rotation` (0 or 90);
- `peak_label_format` (e.g. `"{:.0f}"` or `"{:.1f} cm⁻¹"`);
- `peak_line`: an optional short line from the label to the peak, with its own `_color`, `_width`, `_style`, `_alpha`;
- `peak_sensitivity`: how prominent a band must be to count (fixed at 2 % now);
- `peaks` from all spectra or only one (now: the first line only).

**Highlighted ranges** (`highlight=[[1570, 1640]]`) are now fixed: orange, 15 %.
Proposal:
- `highlight_color`, `highlight_alpha`;
- `highlight_edge_color`, `highlight_edge_width`, `highlight_edge_style` (a frame around the box);
- `highlight_hatch` (stripes, for black-and-white print);
- per-range override, e.g. `[{"range": [1570, 1640], "color": "blue", "label": "G band"}]`, with an optional label at the top.
- Spikes (`"spikes"`) get the same settings via `spike_color` and `spike_alpha`.

## 3. Labels and band assignments (text on the plot)

This covers the text of the mark labels (`C=C`) and the peak labels.
Proposal for both: `_color`, `_alpha`, `_size`, `_weight` (bold), `_italic`, `_font`, `_rotation`.
Other additions:
- `_position`: top of the axes, or just above the peak;
- `_box`: a small background box behind the text so it stays readable over lines, with `_box_color` and `_box_alpha`;
- labels that would overlap are moved apart automatically.

Superscripts and subscripts (cm⁻¹, ν(C=C), I₀) already work as plain Unicode.
Proposal: also allow `$...$` math text, e.g. `"$\nu_{as}$(CH$_2$)"`.

## 4. Box (axes frame) and ticks

**Now**
- `box` (closed / open / none), `box_width`, `box_color`, `background` (whole figure).
- `ticks` (in / out / both, **same for x and y**), `tick_length`, `tick_width`, `tick_color`.
- `tick_sides`, `tick_label_sides`, `tick_label_color`, `minor_ticks`, `x_tick_step`, `y_tick_step`, `x_tick_format`, `y_tick_format`.

So "ticks on top but not on the right" already works today: `tick_sides: ["bottom", "top", "left"]`.

**Missing → proposal**

*Each side of the box on its own:* `box_sides` (e.g. `["left", "bottom", "top"]`), plus per-side `box_color`, `box_width` and `box_alpha` if wanted (`box_left_color` …).

*Plot area fill (inside the box):* `plot_background`, `plot_background_alpha`, separate from `figure_background`.

*x and y ticks separate*, which is your main point. Every tick setting gets an `x_` and a `y_` version, falling back to the shared one when empty:
- `x_ticks: "in"`, `y_ticks: "out"` (direction);
- `x_tick_length`, `y_tick_length`, `x_tick_width`, `y_tick_width`;
- `x_tick_color`, `y_tick_color`, `x_tick_alpha`, `y_tick_alpha`.

*Per side, for full freedom* (e.g. top ticks different from bottom): `tick_top_*`, `tick_right_*` … I suggest x/y first and per-side only if you want it. See the questions at the end.

*Minor ticks:* `minor_ticks` per axis (`x_minor_ticks`, `y_minor_ticks`), `minor_tick_length`, `minor_tick_count` (how many between numbered ticks).

*Tick labels (numbers):*
- `x_tick_label_size` / `y_tick_label_size`;
- `_color`, `_alpha`, `_weight`, `_italic`, `_font`;
- `_rotation`;
- `_pad` (distance from the box).

*Number of ticks:* `x_tick_count` (approximate) as an alternative to `x_tick_step`. Also fixed positions (`x_ticks_at: [400, 800, 1200, 1600]`) and hiding tick labels on one axis (`y_tick_labels: false`, common for stacked spectra).

## 5. Documentation

A new **`docs/plotting.md`**, a complete reference, with one section per element (lines, markers, marks, peak labels, highlight, box, ticks, labels, title, legend, colour bar, saving). Each section has:
- every setting: name, default, allowed values, what it does;
- a short example, both Python (`c.plot(...)`) and website/API (the JSON line);
- a small picture showing the effect, made by a script (`scripts/plot_gallery.py`) so pictures always match the code and can be remade after any change.

Plus **a gallery page**: one figure per feature (before / after), for you to check by eye and later to show on the website.

The settings table in the reference is **generated from the code** (`SETTINGS` in `style.py`), so the documentation can never fall out of date with the code. A test fails if a setting has no explanation or no example.

## 6. Axis labels, title, legend

**Now**
- Axis labels: `label_size`, `label_weight`, `label_color`, shared by x and y.
- Title: `title_size` (weight follows `font_weight`).
- Legend: `legend` (auto/on/off), `legend_location`, `legend_size`, `legend_weight`, `legend_box`.

**Missing → proposal**

*Axis labels, x and y separately:* `xlabel_size`, `xlabel_color`, `xlabel_alpha`, `xlabel_weight`, `xlabel_italic`, `xlabel_font`, `xlabel_pad` (distance from the numbers); the same for `ylabel_*`. The y label also gets `ylabel_rotation`.

*Title:* `title_color`, `title_alpha`, `title_weight`, `title_italic`, `title_font`, `title_location` (left/centre/right), `title_pad`.

*Legend box:* `legend_box` (exists), `legend_box_color` (edge), `legend_box_width`, `legend_box_alpha`, `legend_fill` and `legend_fill_alpha`, `legend_box_round` (rounded or square corners), `legend_shadow`.

*Legend items:*
- `legend_color` (text colour);
- `legend_font`, `legend_italic`;
- `legend_columns`;
- `legend_title` and its size/weight;
- `legend_line_length` (the line sample);
- `legend_marker_scale`;
- `legend_spacing`;
- `legend_order` (reverse, or as given).

*Legend placement:* exact place `legend_position: [x, y]` (0–1 of the plot), plus `outside` right/top/bottom.

*Legend content:* rename entries (`labels`, already works on /figure too: a list of names, one per spectrum), and hide entries for chosen spectra.

---

## 7. My additions

**Axes and scale**
- `x_range`, `y_range`: fixed limits (now only `region`, which picks x and fits y).
- `y_log` and `x_log`: a logarithmic scale.
- A second x axis on top in another unit (e.g. cm⁻¹ below, nm on top for a chosen laser line), which is common in Raman papers.
- Break marks for a cut-out region (the `cut` step leaves a gap; draw `//` marks there).

**Stack plots**
- `offset` is in the API but not documented for the page. Add `stack_labels` (the spectrum name written at the right end of each line instead of a legend) and `stack_scale_bar` (a vertical bar showing e.g. "1000 counts", since the y numbers are hidden).

**Mean plots:** `band` = std (now), 2×std, min–max, or 95 % confidence; plus `mean_band_alpha`.

**Image (colour map) plots**
- `cmap` (exists): list the choices in /options.
- `color_limits` (min, max), and `colorbar` on/off with its `colorbar_label`, `colorbar_size` and `colorbar_ticks`.
- y as spectrum names instead of numbers.

**Text and arrows:** `notes`, free text at any position with its own colour/size/box, and arrows pointing to a feature.

**Inset:** a small zoomed view of a region inside the main plot (`inset: {"region": [1550, 1650], "position": "upper left"}`).

**Several panels:** two or more plots side by side or above each other in one figure (e.g. CV / MB / RhB), sharing an axis, with panel letters (a), (b), (c) and their font settings.

**Saving**
- `width`/`height` exactly in cm (exists as `size`, but add it to the page).
- `tight` margins on/off.
- A font list check: a warning when the font is missing (now in the log only; add it to the answer).

**Reusable styles on the website:** a user saves their own style (all the settings above) and reloads it. The Python side already exists (`save_style`); the website would store the JSON.

**One `/style-preview` endpoint:** draws a small sample figure with the current settings in a fraction of a second, so the website can show changes live while a user drags a slider.

**Validation:** every new setting is checked (wrong name, colour, number or choice → a clear 422 message naming the setting and its allowed values), as we did for `highlight`.

---

## Questions to settle before building

1. **Naming:** do you like the endings rule in section 0 (`_color`, `_alpha`, `_width`, `_style`, `_size`, `_weight`, `_italic`, `_font`)?
2. **Ticks:** are x/y separate enough, or do you want all four sides separate (top ≠ bottom, right ≠ left)?
3. **Short codes:** should `line_format` use MATLAB's codes exactly (`o-`, `*--`, `.`, `s:`)?
4. **Order of building:** my suggestion is
   - 4 (box/ticks) and 6 (labels/title/legend) first, because they apply to every figure;
   - then 1 (lines);
   - then 2 and 3 (marks, labels, highlight);
   - then section 7;
   - with 5 (documentation and gallery) growing with each section, not at the end.
5. **Section 7:** which of my additions do you want, and which should wait?
