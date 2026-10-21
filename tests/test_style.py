"""Tests for figure styles and export (src/spectrum_toolkit/style.py).

Checks that each setting reaches the figure (box, ticks, sides, colours,
sizes, aspect), that styles can be saved and reloaded, and that export
writes the requested file type, resolution and colour mode.
"""

import matplotlib

matplotlib.use("Agg")                                   # draw off-screen; must come before pyplot

import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.colors import to_rgb
from PIL import Image

import spectrum_toolkit as stk
from spectrum_toolkit import Spectrum, SpectrumCollection
from spectrum_toolkit.style import DEFAULTS, PALETTES, PRESETS, SETTINGS

X = np.linspace(100, 1800, 500)


@pytest.fixture(autouse=True)
def reset():
    """Close figures and restore the session default style after each test."""
    yield
    plt.close("all")
    stk.set_style()


def three():
    return SpectrumCollection(X, np.vstack([np.sin(X / 50) + k for k in range(3)]), x_unit="cm-1")


def test_presets_and_changes():
    """A preset fills every setting; changes on top win; unknown names are explained."""
    for name, preset in PRESETS.items():
        if preset is not None:
            assert set(stk.get_style(name)) == set(SETTINGS)
    look = stk.get_style("publication", box_width=3)
    assert look["box"] == "closed" and look["box_width"] == 3
    assert stk.get_style({"preset": "matlab", "colors": "colorblind"})["colors"] == "colorblind"
    assert stk.get_style("matplotlib") is None                   # leave matplotlib alone
    with pytest.raises(ValueError, match="Unknown style setting"):
        stk.get_style("clean", box_widht=2)
    with pytest.raises(ValueError, match="preset"):
        stk.get_style("fancy")


def test_box_ticks_and_sides_reach_the_axes():
    """Closed box with given width and colour; ticks inward on chosen sides; labels on chosen sides."""
    ax = three().plot(box="closed", box_width=2.5, box_color="red", ticks="in",
                      tick_sides=("bottom", "top", "left"), tick_label_sides=("top", "left"),
                      tick_label_color="blue", font_size=14)
    assert all(ax.spines[s].get_visible() for s in ("top", "right", "bottom", "left"))
    assert ax.spines["left"].get_linewidth() == 2.5 and to_rgb(ax.spines["left"].get_edgecolor()) == (1, 0, 0)
    tick = ax.xaxis.get_major_ticks()[0]
    assert tick.tick1line.get_visible() and tick.tick2line.get_visible()        # bottom and top
    assert not tick.label1.get_visible() and tick.label2.get_visible()          # labels only on top
    assert not ax.yaxis.get_major_ticks()[0].tick2line.get_visible()            # no right ticks
    assert tick._tickdir == "in"                                               # ticks point inward
    assert to_rgb(tick.label2.get_color()) == (0, 0, 1) and tick.label2.get_fontsize() == 14


def test_open_box_and_no_box():
    ax = three().plot(box="open")
    assert not ax.spines["top"].get_visible() and ax.spines["left"].get_visible()
    ax = three().plot(box="none")
    assert not any(ax.spines[s].get_visible() for s in ("top", "right", "bottom", "left"))


def test_lines_colours_and_dotted():
    """MATLAB colours in order, line width and dotted style reach the lines."""
    ax = three().plot(colors="matlab", line_width=2.2, line_style=":")
    lines = ax.get_lines()
    assert [to_rgb(l.get_color()) for l in lines] == [tuple(c) for c in PALETTES["matlab"][:3]]
    assert all(l.get_linewidth() == 2.2 and l.get_linestyle() == ":" for l in lines)
    ax = three().plot(line_style="none", marker="o")                            # markers only
    assert ax.get_lines()[0].get_marker() == "o" and ax.get_lines()[0].get_linestyle() == "None"


def test_size_aspect_grid_and_tick_step():
    """Figure size in cm, square plot area, grid off, tick spacing and format."""
    ax = three().plot(size=(12, 9), units="cm", aspect="square", grid=False, x_tick_step=250,
                      x_tick_format="%.1f")
    w, h = ax.figure.get_size_inches()
    assert np.isclose(w, 12 / 2.54) and np.isclose(h, 9 / 2.54)
    assert ax.get_box_aspect() == 1
    assert not any(l.get_visible() for l in ax.get_xgridlines())
    ax.figure.canvas.draw()
    ticks = ax.get_xticks()
    assert np.allclose(np.diff(ticks), 250)
    assert ax.get_xticklabels()[1].get_text().endswith(".0")


def test_session_default_and_json(tmp_path):
    """set_style changes every later plot; save_style / style="file.json" round-trip."""
    stk.set_style("publication", box_width=1.7)
    assert three().plot().spines["left"].get_linewidth() == 1.7
    path = stk.save_style("matlab", tmp_path / "mine", line_width=3)
    assert path.suffix == ".json"
    ax = three().plot(style=str(path))
    assert ax.get_lines()[0].get_linewidth() == 3 and ax.get_box_aspect() == 1


def test_scatter_groups_like_gscatter():
    """One colour and legend entry per group, in order of appearance; zero line drawn."""
    rng = np.random.default_rng(0)
    groups = ["CV"] * 5 + ["MB"] * 3 + ["RhB"] * 4
    ax = stk.scatter(rng.normal(size=12), rng.normal(size=12), groups, style="matlab", zero_lines="x")
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["CV", "MB", "RhB"]
    assert len(ax.collections) == 3 and ax.get_legend().get_texts()[0].get_fontweight() == "bold"
    assert any(np.allclose(l.get_ydata(), 0) for l in ax.get_lines())
    with pytest.raises(ValueError, match="names"):
        stk.scatter([1, 2], [3, 4], ["a", "b"], names=["only one"])


def test_peaks_and_marks_are_labelled():
    y = 100 + 1000 / (1 + ((X - 1000) / 8) ** 2) + 500 / (1 + ((X - 1500) / 8) ** 2)
    ax = Spectrum(X, y).plot(peaks=2, marks={600: "ref"})
    texts = sorted(t.get_text() for t in ax.texts)
    assert texts == ["1000", "1500", "ref"]                                    # the two bands and the mark


@pytest.mark.parametrize("fmt", ["png", "tiff", "jpg", "pdf", "svg", "eps"])
def test_export_formats(tmp_path, fmt):
    """Every file type is written, in a new folder, with the extension added."""
    ax = three().plot()
    path = stk.export(ax, "fig", folder=tmp_path / "out", format=fmt, dpi=150)
    assert path == tmp_path / "out" / f"fig.{fmt}" and path.stat().st_size > 500


def test_export_dpi_and_cmyk(tmp_path):
    """tiff at the requested dpi; CMYK for tiff and jpg; refused for png with a hint."""
    ax = three().plot(size=(10, 5))
    path = stk.export(ax, tmp_path / "a.tiff", dpi=600, color="cmyk")
    image = Image.open(path)
    assert image.mode == "CMYK" and round(image.info["dpi"][0]) == 600
    assert Image.open(stk.export(ax, tmp_path / "b.jpg", color="cmyk")).mode == "CMYK"
    assert Image.open(stk.export(ax, tmp_path / "c.tiff")).mode in ("RGB", "RGBA")
    with pytest.raises(ValueError, match="tiff"):
        stk.export(ax, tmp_path / "d.png", color="cmyk")
    with pytest.raises(ValueError, match="file type"):
        stk.export(ax, tmp_path / "e.bmp")


def test_matlab_preset_saves_tiff_at_1200_dpi(tmp_path):
    """save= uses the style: the matlab preset gives a 1200 dpi tiff like exportgraphics."""
    three().plot(style="matlab", size=(4, 4), save=tmp_path / "m")
    image = Image.open(tmp_path / "m.tiff")
    assert round(image.info["dpi"][0]) == 1200


# ------------------------------------------------------------------ per-side and per-axis settings
def saved(ax, tmp_path):
    """Save the figure (as a user would) and return the axes, so checks see the saved state."""
    stk.export(ax, tmp_path / "f", format="png", dpi=50)
    return ax


def test_ticks_per_side_and_per_axis(tmp_path):
    """Side beats axis beats general; the look survives saving (new ticks copy the first one)."""
    import matplotlib.lines as mlines
    ax = saved(three().plot(box="closed", tick_sides=("bottom", "top", "left", "right"), tick_length=5,
                            x_tick_direction="in", left_tick_direction="out", right_tick_direction="both",
                            top_tick_length=9, top_tick_color="red", right_tick_alpha=0.3), tmp_path)
    x, y = ax.xaxis.get_major_ticks(), ax.yaxis.get_major_ticks()
    assert all(t.tick2line.get_markersize() == 9 and t.tick1line.get_markersize() == 5 for t in x)
    assert to_rgb(x[0].tick2line.get_markeredgecolor()) == (1, 0, 0)
    assert y[0].tick2line.get_markeredgecolor()[3] == 0.3
    assert x[0].tick1line.get_marker() == mlines.TICKUP                  # bottom, inward
    assert y[0].tick1line.get_marker() == mlines.TICKLEFT                # left, outward
    assert y[0].tick2line.get_marker() == "_"                            # right, through the line


def test_tick_labels_per_side(tmp_path):
    ax = saved(three().plot(bottom_ticks=False, top_ticks=True, top_tick_labels=True, bottom_tick_labels=False,
                            left_tick_label_color="cmyk(0, 1, 1, 0)", y_tick_label_italic=True,
                            top_tick_label_weight="bold", x_tick_label_size=15, x_tick_label_rotation=45,
                            x_tick_label_pad=9), tmp_path)
    t, u = ax.xaxis.get_major_ticks()[0], ax.yaxis.get_major_ticks()[0]
    assert not t.tick1line.get_visible() and t.tick2line.get_visible()
    assert t.label2.get_visible() and not t.label1.get_visible()
    assert to_rgb(u.label1.get_color()) == (1, 0, 0) and u.label1.get_fontstyle() == "italic"
    assert t.label2.get_fontweight() in ("bold", 700) and t.label2.get_fontsize() == 15
    assert t.label2.get_rotation() == 45 and t.get_pad() == 9


def test_minor_ticks_per_axis(tmp_path):
    ax = saved(three().plot(x_minor_ticks=True, minor_tick_count=4, minor_tick_length=1.5), tmp_path)
    assert len(ax.xaxis.get_minorticklocs()) > 0 and len(ax.yaxis.get_minorticklocs()) == 0
    assert ax.xaxis.get_minor_ticks()[0].tick1line.get_markersize() == 1.5


def test_box_sides_and_backgrounds():
    ax = three().plot(box="open", top_box=True, top_box_color="blue", top_box_width=3, top_box_style="--",
                      left_box_alpha=0.5, bottom_box=False, plot_background="yellow", plot_background_alpha=0.5)
    top = ax.spines["top"]
    assert top.get_visible() and to_rgb(top.get_edgecolor()) == (0, 0, 1) and top.get_linewidth() == 3
    assert top.get_linestyle() == "--" and not ax.spines["bottom"].get_visible()
    assert ax.spines["left"].get_edgecolor()[3] == 0.5
    assert tuple(ax.get_facecolor()) == (1, 1, 0, 0.5)


def test_axis_labels_and_title_each_on_their_own():
    ax = three().plot(xlabel="X", ylabel="Y", title="T", xlabel_color="blue", xlabel_size=18, xlabel_pad=12,
                      ylabel_italic=True, ylabel_rotation=0, ylabel_alpha=0.5, title_location="right",
                      title_color="green", title_italic=True, title_weight="bold", title_size=16)
    assert to_rgb(ax.xaxis.label.get_color()) == (0, 0, 1) and ax.xaxis.label.get_fontsize() == 18
    assert ax.xaxis.labelpad == 12 and ax.yaxis.label.get_rotation() == 0
    assert ax.yaxis.label.get_fontstyle() == "italic" and ax.yaxis.label.get_color()[3] == 0.5
    assert ax.title.get_text() == "" and ax._right_title.get_text() == "T"
    assert ax._right_title.get_fontsize() == 16 and ax._right_title.get_fontweight() in ("bold", 700)


def test_legend_frame_text_title_and_layout():
    c = three()
    ax = c.plot(legend=True, legend_box=True, legend_box_color="red", legend_box_width=2, legend_box_alpha=0.5,
                legend_fill="cmyk(0, 0, 1, 0)", legend_fill_alpha=0.3, legend_columns=3, legend_order="reverse",
                legend_title="S", legend_title_size=14, legend_color="blue", legend_italic=True, legend_size=12,
                legend_position=[0.1, 0.5], legend_line_length=4, legend_spacing=1.5, legend_shadow=True)
    leg = ax.get_legend()
    frame = leg.get_frame()
    assert tuple(frame.get_edgecolor()) == (1, 0, 0, 0.5) and frame.get_linewidth() == 2
    assert tuple(frame.get_facecolor()) == (1, 1, 0, 0.3)
    assert leg._ncols == 3 and [t.get_text() for t in leg.get_texts()] == list(c.names[::-1])
    text = leg.get_texts()[0]
    assert to_rgb(text.get_color()) == (0, 0, 1) and text.get_fontstyle() == "italic" and text.get_fontsize() == 12
    assert leg.get_title().get_text() == "S" and leg.get_title().get_fontsize() == 14
    assert leg.handlelength == 4 and leg.labelspacing == 1.5 and leg.shadow


def test_colours_in_every_form():
    assert stk.to_rgba("cmyk(0, 1, 1, 0)") == (1, 0, 0, 1)
    assert stk.to_rgba("cmyk(0, 100, 100, 0)") == (1, 0, 0, 1)                 # percent
    assert stk.to_rgba([0, 0, 255]) == (0, 0, 1, 1)                            # 0-255
    assert stk.to_rgba([0, 0, 1, 0.5]) == (0, 0, 1, 0.5)
    assert stk.to_rgba("0.5", alpha=0.2) == (0.5, 0.5, 0.5, 0.2)
    ax = three().plot(colors=["cmyk(0, 1, 1, 0)", [0, 0, 255], "green"])
    assert to_rgb(ax.get_lines()[0].get_color()) == (1, 0, 0)


@pytest.mark.parametrize("wrong, message", [
    ({"top_tick_direction": "up"}, "top_tick_direction must be one of"),
    ({"tick_alpha": 2}, "transparency"),
    ({"title_color": "blu"}, "not a colour"),
    ({"left_box": "yes"}, "true or false"),
    ({"xlabel_weight": "heavy"}, '"normal" or "bold"'),
    ({"legend_order": "up"}, "legend_order must be one of"),
    ({"x_tick_length": "long"}, "must be a number"),
])
def test_wrong_values_are_explained(wrong, message):
    with pytest.raises(ValueError, match=message):
        stk.get_style("clean", **wrong)


def test_old_setting_name_still_works():
    assert stk.get_style("clean", ticks="in")["tick_direction"] == "in"
    assert stk.get_style({"preset": "clean", "ticks": "both"})["tick_direction"] == "both"


def test_every_setting_is_documented():
    """docs/plotting.md lists every setting (run scripts/make_plotting_docs.py after adding one)."""
    from pathlib import Path
    doc = (Path(__file__).parent.parent / "docs" / "plotting.md").read_text(encoding="utf-8")
    missing = [name for name in SETTINGS if f"`{name}`" not in doc]
    assert not missing, f"Not in docs/plotting.md: {missing}. Run: uv run python scripts/make_plotting_docs.py"
    assert all(meaning for _, meaning in SETTINGS.values())                     # every setting explained
