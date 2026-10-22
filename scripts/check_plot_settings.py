"""Check every plotting setting, one at a time: does changing it change the
saved figure, and does a wrong value give a clear error?

    uv run python scripts/check_plot_settings.py

For each setting in SETTINGS (src/spectrum_toolkit/style.py) this draws the
same figure twice, once as the "context" and once with only that setting
changed, saves both as pictures and compares them pixel by pixel. The
context shows every part of a figure (closed box, ticks and numbers on all
four sides, minor ticks, grid, title, axis labels, legend with legend box and
heading, zero lines, markers), so every setting has something to act on.
Settings that do not change the picture itself (file type, dpi, colour mode)
are checked on the saved file instead.

Run it after adding or changing any plotting setting. It ends with a list
of settings that had no visible effect or gave an error (should be none).
"""
import io
import sys

import matplotlib
matplotlib.use("Agg")                                      # draw without a window
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

import spectrum_toolkit as stk
from spectrum_toolkit import SpectrumCollection
from spectrum_toolkit.style import PER_SPECTRUM, SETTINGS, SIDES, TEXTS, get_style

# ------------------------------------------------------------------ the figure used for every check
X = np.linspace(400, 1800, 300)
Y = np.array([0.1 * k + np.exp(-((X - c) / 25) ** 2) - 0.3 * np.exp(-((X - 900) / 60) ** 2)
              for k, c in enumerate((1000, 1200, 1400))])                     # dips below zero: zero lines show
DATA = SpectrumCollection(X, Y, names=["A", "B", "C"], x_unit="x unit", y_unit="y unit")
TEXT = dict(title="Title", xlabel="x label", ylabel="y label")
_spiky = Y.copy()
_spiky[1, 150] += 3                                                            # one spike, removed by despike
SPIKED = SpectrumCollection(X, _spiky, names=["A", "B", "C"]).despike()

# Arguments of plot itself (not style settings): peak labels, marks and a labelled range are always shown.
PLOT_ARGUMENTS = dict(peaks=2, marks={1000: "M", 1400: "N"},
                      highlight=[{"range": [1150, 1250], "label": "H"}])
PLOT_KEYS = ("peaks", "marks", "highlight", "emphasize", "notes", "inset")

# Everything visible, so each setting has something to act on.
CONTEXT = dict(box="closed", tick_sides=["bottom", "top", "left", "right"],
               tick_label_sides=["bottom", "top", "left", "right"], minor_ticks=True, grid=True,
               legend=True, legend_box=True, legend_title="Legend", zero_lines="both", marker="o",
               marker_size=3, size=(14, 9), legend_location="upper right")

# Settings checked on the saved file, not on the picture's pixels.
FILE_CHECKS = {"dpi", "format", "color_mode", "tight"}

# Settings that act on another kind of plot than lines.
KIND_OF = {"mean_band": "mean", "mean_band_color": "mean", "mean_band_alpha": "mean", "cmap": "image",
           "color_limits": "image", "colorbar": "image", "colorbar_label": "image", "colorbar_ticks_at": "image",
           "colorbar_length": "image", "colorbar_fraction": "image", "image_y": "image"}


def changed_value(name: str, current):
    """A value different from the current one, of the right kind for the setting."""
    special = {
        "size": "single", "units": "in", "aspect": "square", "font": "DejaVu Serif", "box": "open",
        "tick_sides": ["bottom", "left"], "tick_label_sides": ["bottom"], "title_location": "left",
        "legend": False, "legend_location": "lower left", "legend_position": [0.05, 0.05],
        "legend_columns": 3, "legend_order": "reverse", "legend_title": "Other heading", "grid": False,
        "line_style": "--", "marker": "s", "colors": "colorblind", "cmap": "magma", "zero_lines": "x",
        "x_tick_step": 300, "y_tick_step": 0.25, "x_tick_format": "%.1f", "y_tick_format": "%.3f",
        "minor_ticks": False, "minor_tick_count": 1, "legend_box": False, "legend_shadow": True,
        "legend_box_round": False, "legend_fill": "yellow", "background": "lightblue",
        "plot_background": "yellow", "line_format": "s--", "marker_fill": "none", "marker_every": 10,
        "mark_span": "peak", "peak_label_format": "{:.2f} cm", "peak_sensitivity": 0.9,
        "peak_spectra": "all", "highlight_hatch": "//", "label_overlap": "keep",
        "x_ticks_at": [500, 1000, 1500], "y_ticks_at": [0, 0.5], "x_tick_count": 3, "y_tick_count": 2,
        "legend_hide": [1],
        "top_axis": "wavelength", "top_axis_laser": 785, "top_axis_offset": 100, "top_axis_label": "Top label",
        "right_axis": "scale", "right_axis_offset": 5, "right_axis_label": "Right label",
        "line_name_position": "left", "scale_bar": 0.5, "scale_bar_label": "Bar", "scale_bar_position": "left",
        "mean_band": "minmax", "color_limits": [0, 0.5], "colorbar_label": "Bar label",
        "colorbar_ticks_at": [0, 0.5], "colorbar_length": 0.5, "colorbar_fraction": 0.3, "image_y": "name",
        "note_arrow_head": "-|>", "inset_position": "lower left", "inset_scale": 0.6,
        "panel_letter_format": "{}.", "panel_letter_case": "upper", "panel_letter_position": "inside",
        "panel_spacing": 0.2, "x_range": [600, 1500], "y_range": [None, 0.8],
    }
    base = name
    for prefix in SIDES + ("x", "y"):                       # top_tick_length -> tick_length
        if name.startswith(prefix + "_") and name[len(prefix) + 1:] in SETTINGS and name != f"{prefix}_box":
            base = name[len(prefix) + 1:]
    if name.startswith(("xlabel_", "ylabel_")):
        base = "label_" + name.split("_", 1)[1]
    if base in special:
        return special[base]
    if name.endswith(("_ticks", "_tick_labels", "_box")) and current is None:
        return False                                        # on in the context (all sides): turn it off
    if name.endswith(("_ticks", "_tick_labels", "_box")) or name.endswith("_italic") or isinstance(current, bool):
        return not bool(current)
    if name.endswith("tick_direction"):
        return "both"
    if name.endswith("_position"):
        return "top" if current == "peak" else "peak"
    if name.endswith("_fill"):
        return "yellow"
    if name.endswith("_color"):
        return "blue" if current in ("red",) else "red"
    if name.endswith("_alpha"):
        return 0.15 if current != 0.15 else 0.6
    if name.endswith("_weight"):
        return "normal" if current == "bold" else "bold"
    if name.endswith("_font"):
        return "DejaVu Serif"
    if name.endswith("_style"):
        return ":" if current != ":" else "--"
    if name.endswith("_rotation"):
        return 45 if current != 45 else 0
    if name.endswith("_pad"):
        return 25
    if name.endswith(("_width", "_length")):
        return 6
    if name.endswith(("_size", "_scale")):
        return 22 if not name.startswith("marker") else 9
    if name.endswith("_spacing"):
        return 2.5
    if name.endswith("_count"):
        return 1
    if name.endswith("_margin"):
        return 0.3
    raise ValueError(f"no test value for {name}")


def picture(settings: dict, kind: str = "lines") -> np.ndarray:
    """Draw, save as png in memory and return the pixels.

    Two keys are not settings: "_cut" draws the data with a range cut out,
    "_panels" draws two panels with stk.panels.
    """
    settings = {**PLOT_ARGUMENTS, **settings}
    cut, as_panels = settings.pop("_cut", False), settings.pop("_panels", False)
    data = SPIKED if settings["highlight"] == "spikes" else DATA
    data = data.cut(1250, 1300) if cut else data
    if as_panels:
        arguments = {k: settings.pop(k) for k in list(settings) if k in PLOT_ARGUMENTS}
        ax = stk.panels([{"data": data, **arguments, **TEXT}, data], **settings)[0]
    else:
        ax = stk.plot(data, kind=kind, **TEXT, **settings)
    buffer = io.BytesIO()
    ax.figure.savefig(buffer, format="png", dpi=50)
    plt.close("all")
    buffer.seek(0)
    return np.asarray(Image.open(buffer).convert("RGB")).astype(int)


def differs(a: np.ndarray, b: np.ndarray) -> int:
    """Number of pixels that changed (any size change counts as a change)."""
    if a.shape != b.shape:
        return a.size
    return int((np.abs(a - b).sum(axis=2) > 0).sum())


def context_for(name: str) -> dict:
    """The context, plus what one setting needs to have an effect."""
    ctx = dict(CONTEXT)
    if name == "plot_background_alpha":
        ctx["plot_background"] = "yellow"
    if name == "background_alpha":
        ctx["background"] = "lightblue"
    if name == "legend_fill_alpha":
        ctx["legend_fill"] = "yellow"
    if name == "legend_position":
        ctx.pop("legend_location")
    if name in ("tick_label_sides",):
        ctx["tick_label_sides"] = ["bottom", "top", "left", "right"]
    if "minor" in name:
        ctx["minor_ticks"] = True
    if name.endswith("_box_alpha") or name.endswith("box_alpha"):
        ctx["box_width"] = 3
        ctx["legend_box_width"] = 3
    if name.endswith("tick_alpha") or name.endswith("tick_width"):
        ctx["tick_length"] = 8
        ctx["tick_width"] = 2
    if name.endswith("_box_style") or name == "box_style":
        ctx["box_width"] = 2
    if name == "legend_marker_scale":
        ctx["marker_size"] = 6
    if name in ("emphasize_width", "faded_alpha"):
        ctx["emphasize"] = [1]
    if name in ("fill_color", "fill_alpha"):
        ctx["fill"] = True
    if name.startswith("peak_line_"):
        ctx["peak_line"] = True
    if name.startswith("highlight_edge_"):
        ctx["highlight_edge_color"] = "black"
    if name.startswith("spike_"):
        ctx["highlight"] = "spikes"
    what = next((w for w in TEXTS if name.startswith(w + "_")), None)
    if what and name.endswith(("_box_color", "_fill", "_fill_alpha")):  # a text box: only seen when it is on
        ctx[f"{what}_box"] = True
        if name.endswith("_fill_alpha"):
            ctx[f"{what}_fill"] = "yellow"
    if name.startswith("top_axis_"):
        ctx["top_axis"] = "wavelength" if name in ("top_axis_laser", "top_axis_label") else "scale"
    if name.startswith("right_axis_"):
        ctx["right_axis"] = "scale"
    if name.startswith("cut_mark"):
        ctx["_cut"] = True
        if name != "cut_marks":
            ctx["cut_marks"] = True
    if name.startswith("line_name"):
        ctx["legend"] = False
        if name != "line_names":
            ctx["line_names"] = True
    if name.startswith("scale_bar_"):
        ctx["scale_bar"] = 0.5
    if name.startswith("note_"):
        ctx["notes"] = [{"text": "Note", "x": 700, "y": 0.6, "arrow": [1000, 0.9]}]
        if name in ("note_box_color", "note_fill", "note_fill_alpha"):
            ctx["note_box"] = True
            ctx["note_box_color"] = ctx.get("note_box_color", "black")
    if name.startswith("inset_"):
        ctx["inset"] = [950, 1050]
    if name.startswith("panel_"):
        ctx["_panels"] = True
    if name == "label_overlap":
        ctx["marks"] = {1000: "AAAA", 1004: "BBBB"}            # two labels on top of each other
    return ctx


def line_looks(settings: dict) -> list:
    """What each of the three spectrum lines looks like, after saving."""
    ax = stk.plot(DATA, **TEXT, **settings)
    ax.figure.savefig(io.BytesIO(), format="png", dpi=40)
    looks = [(tuple(matplotlib.colors.to_rgba(line.get_color())), line.get_linestyle(), line.get_linewidth(),
              str(line.get_marker()), line.get_markersize(), str(line.get_markeredgecolor()),
              str(line.get_markerfacecolor())) for line in ax.get_lines()[:3]]
    plt.close("all")
    return looks


def check_per_spectrum() -> list[str]:
    """Each setting that takes a list: a list changing only spectrum B changes line B only."""
    problems = []
    for name in PER_SPECTRUM:
        current = CONTEXT.get(name, get_style("clean", **CONTEXT)[name])
        value = changed_value(name, current)
        base = line_looks(CONTEXT)
        got = line_looks({**CONTEXT, name: [current, value, current]})
        changed = [a != b for a, b in zip(base, got)]
        ok = changed == [False, True, False]
        print(f"{'ok' if ok else 'WRONG':9s} {name} = [{current!r}, {value!r}, {current!r}] changes spectrum B only")
        if not ok:
            problems.append(f"{name} as a list changed lines {changed}")
    return problems


def check_files() -> list[str]:
    """dpi, format and colour mode: checked on the saved file."""
    problems = []
    ax = stk.plot(DATA, **TEXT, **CONTEXT)
    for dpi in (50, 100):
        buffer = io.BytesIO()
        ax.figure.savefig(buffer, format="png", dpi=dpi)
        buffer.seek(0)
        width = Image.open(buffer).size[0]
        if dpi == 100 and width < 1.9 * previous:
            problems.append("dpi: doubling dpi did not double the picture width")
        previous = width
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as folder:
        path = stk.export(ax, Path(folder) / "f", style={"preset": "clean", "format": "svg"})
        if path.suffix != ".svg":
            problems.append("format: the style's format was not used")
        path = stk.export(ax, Path(folder) / "g.tiff", style={"preset": "clean", "color_mode": "cmyk"})
        if Image.open(path).mode != "CMYK":
            problems.append("color_mode: cmyk tiff is not CMYK")
        sizes = [Image.open(stk.export(ax, Path(folder) / f"t{tight}.png",
                                       style={"preset": "clean", "tight": tight, "dpi": 50})).size
                 for tight in (True, False)]
        if sizes[0] == sizes[1]:
            problems.append("tight: the saved picture has the same size with and without tight")
    plt.close("all")
    return problems


# What to read back from a tick for each per-side setting.
_READ = {
    "tick_direction": lambda line, label: line.get_marker(),
    "tick_length": lambda line, label: line.get_markersize(),
    "tick_width": lambda line, label: line.get_markeredgewidth(),
    "tick_color": lambda line, label: tuple(line.get_markeredgecolor())[:3],
    "tick_alpha": lambda line, label: tuple(line.get_markeredgecolor())[3],
    "tick_label_size": lambda line, label: label.get_fontsize(),
    "tick_label_color": lambda line, label: matplotlib.colors.to_rgb(label.get_color()),
    "tick_label_alpha": lambda line, label: matplotlib.colors.to_rgba(label.get_color())[3],
    "tick_label_weight": lambda line, label: label.get_fontweight(),
    "tick_label_italic": lambda line, label: label.get_fontstyle(),
    "tick_label_font": lambda line, label: tuple(label.get_fontfamily()),
    "tick_label_rotation": lambda line, label: label.get_rotation(),
}
_SIDE_PART = {"bottom": ("xaxis", 1), "top": ("xaxis", 2), "left": ("yaxis", 1), "right": ("yaxis", 2)}


def read_sides(settings: dict, key: str) -> dict:
    """The value of one tick property on each side, for every tick, after saving."""
    ax = stk.plot(DATA, **TEXT, **settings)
    ax.figure.savefig(io.BytesIO(), format="png", dpi=40)    # read back what was saved
    values = {}
    for side, (axis, number) in _SIDE_PART.items():
        ticks = getattr(ax, axis).get_major_ticks()
        values[side] = {_READ[key](getattr(t, f"tick{number}line"), getattr(t, f"label{number}")) for t in ticks}
    plt.close("all")
    return values


def check_sides() -> list[str]:
    """Each per-side setting changes its own side only; each per-axis setting both sides of its axis only."""
    problems = []
    for key in _READ:
        base = read_sides(CONTEXT, key)
        for prefix in SIDES + ("x", "y"):
            name = f"{prefix}_{key}"
            value = changed_value(name, None)
            got = read_sides({**CONTEXT, name: value}, key)
            should_change = [prefix] if prefix in SIDES else [s for s in SIDES if _SIDE_PART[s][0][0] == prefix]
            for side in SIDES:
                changed = got[side] != base[side]
                if changed != (side in should_change):
                    problems.append(f"{name}={value!r}: {side} side {'changed' if changed else 'did not change'}")
            print(f"{'ok' if not any(p.startswith(name + '=') for p in problems) else 'WRONG':9s} {name} acts on "
                  f"{', '.join(should_change)} only")
    for side in SIDES:                                         # box lines
        for key, value, read in (("box_color", "red", lambda sp: tuple(sp.get_edgecolor())[:3]),
                                 ("box_width", 6, lambda sp: sp.get_linewidth()),
                                 ("box_alpha", 0.2, lambda sp: sp.get_edgecolor()[3]),
                                 ("box_style", ":", lambda sp: sp.get_linestyle()),
                                 ("box", False, lambda sp: sp.get_visible())):
            ax0 = stk.plot(DATA, **CONTEXT)
            ax1 = stk.plot(DATA, **CONTEXT, **{f"{side}_{key}": value})
            wrong = [s for s in SIDES if (read(ax0.spines[s]) != read(ax1.spines[s])) != (s == side)]
            plt.close("all")
            print(f"{'ok' if not wrong else 'WRONG':9s} {side}_{key} acts on the {side} line only")
            if wrong:
                problems.append(f"{side}_{key}: wrong sides {wrong}")
    return problems


def main() -> int:
    no_effect, errors = [], []
    for name, (default, _) in SETTINGS.items():
        if name in FILE_CHECKS:
            continue
        ctx = context_for(name)
        current = ctx.get(name, get_style("clean", **{k: v for k, v in ctx.items()
                                                      if k not in PLOT_KEYS and not k.startswith("_")})[name])
        value = changed_value(name, current)
        kind = KIND_OF.get(name, "lines")
        try:
            before = picture(ctx, kind)
            after = picture({**ctx, name: value}, kind)
        except Exception as e:                              # noqa: BLE001 - report every failure
            errors.append(f"{name}={value!r}: {type(e).__name__}: {e}")
            print(f"ERROR     {name} = {value!r}: {e}")
            continue
        n = differs(before, after)
        print(f"{'ok' if n else 'NO EFFECT':9s} {name} = {value!r}  ({n} pixels changed)")
        if not n:
            no_effect.append(f"{name}={value!r}")
    # The other direction for the per-side on/off settings: everything off, then one side on.
    off = {**CONTEXT, "box": "none", "tick_sides": [], "tick_label_sides": []}
    for side in SIDES:
        for what in ("ticks", "tick_labels", "box"):
            name = f"{side}_{what}"
            n = differs(picture(off), picture({**off, name: True}))
            print(f"{'ok' if n else 'NO EFFECT':9s} {name} = True on a figure with no box and no ticks  ({n} pixels changed)")
            if not n:
                no_effect.append(f"{name}=True")
    problems = check_files() + check_sides() + check_per_spectrum()
    for p in problems:
        print("FILE     ", p)
    # A wrong value of each kind must give a clear error naming the setting.
    wrong = {"top_tick_length": "long", "left_tick_alpha": 3, "xlabel_color": "notacolour", "right_box": "yes",
             "title_weight": "heavy", "bottom_tick_direction": "up", "legend_order": "sideways",
             "box_style": "~", "legend_box": "maybe", "line_format": "o-q", "line_style": "dashed",
             "marker": "smiley", "marker_every": 0, "line_alpha": [1, 2], "line_color": ["red", "nocolour"],
             "fill": "yes", "zero_line_alpha": -1, "x_ticks_at": "400", "y_tick_count": 0,
             "legend_location": "outside left", "legend_hide": 1, "mark_span": "half", "mark_style": "dotted",
             "peak_label_format": "{:.0q}", "peak_spectra": "some", "highlight_hatch": "#",
             "peak_label_position": "middle", "highlight_label_box": "yes", "peak_sensitivity": 2,
             "label_overlap": "hide", "peak_label_color": "notacolour", "top_axis": "left", "x_log": "yes",
             "top_axis_laser": 0, "inset_scale": 2, "color_limits": 5, "colorbar_length": 0,
             "panel_letter_format": "x", "panel_spacing": 0.9, "mean_band": "var", "scale_bar": -1,
             "image_y": "letter", "note_arrow_head": "=>", "line_name_color": "nocolour", "x_range": [1, 2, 3], "y_range": [1, 1],
             "x_margin": -0.1}
    for name, value in wrong.items():
        try:
            get_style("clean", **{name: value})
            errors.append(f"{name}={value!r} was accepted")
        except ValueError as e:
            ok = name in str(e)
            print(f"{'ok' if ok else 'UNCLEAR':9s} wrong {name}={value!r}: {e}")
            if not ok:
                errors.append(f"unclear message for {name}: {e}")
    print(f"\nChecked {len(SETTINGS)} settings.")
    print("No visible effect:", no_effect or "none")
    print("Errors:", errors + problems or "none")
    return 1 if (no_effect or errors or problems) else 0


if __name__ == "__main__":
    sys.exit(main())
