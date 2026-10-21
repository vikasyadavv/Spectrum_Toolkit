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
