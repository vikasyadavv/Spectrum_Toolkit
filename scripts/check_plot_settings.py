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
from spectrum_toolkit.style import PER_SPECTRUM, SETTINGS, SIDES, get_style

# ------------------------------------------------------------------ the figure used for every check
X = np.linspace(400, 1800, 300)
Y = np.array([0.1 * k + np.exp(-((X - c) / 25) ** 2) - 0.3 * np.exp(-((X - 900) / 60) ** 2)
              for k, c in enumerate((1000, 1200, 1400))])                     # dips below zero: zero lines show
DATA = SpectrumCollection(X, Y, names=["A", "B", "C"], x_unit="x unit", y_unit="y unit")
TEXT = dict(title="Title", xlabel="x label", ylabel="y label")

# Everything visible, so each setting has something to act on.
CONTEXT = dict(box="closed", tick_sides=["bottom", "top", "left", "right"],
               tick_label_sides=["bottom", "top", "left", "right"], minor_ticks=True, grid=True,
               legend=True, legend_box=True, legend_title="Legend", zero_lines="both", marker="o",
               marker_size=3, size=(14, 9), legend_location="upper right")

# Settings checked on the saved file, not on the picture's pixels.
FILE_CHECKS = {"dpi", "format", "color_mode"}


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
        "x_ticks_at": [500, 1000, 1500], "y_ticks_at": [0, 0.5], "x_tick_count": 3, "y_tick_count": 2,
        "legend_hide": [1],
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
    if name.endswith("_color"):
        return "blue" if current in ("red",) else "red"
    if name.endswith("_alpha"):
        return 0.15
    if name.endswith("_weight"):
        return "normal" if current == "bold" else "bold"
    if name.endswith("_font"):
        return "DejaVu Serif"
    if name.endswith("_style"):
        return ":"
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
    raise ValueError(f"no test value for {name}")


def picture(settings: dict, kind: str = "lines") -> np.ndarray:
    """Draw, save as png in memory and return the pixels."""
    ax = stk.plot(DATA, kind=kind, **TEXT, **settings)
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
        current = ctx.get(name, get_style("clean", **{k: v for k, v in ctx.items() if k != "emphasize"})[name])
        value = changed_value(name, current)
        kind = "image" if name == "cmap" else "lines"
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
             "legend_location": "outside left", "legend_hide": 1}
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
