"""Tests for plotting (src/spectrum_toolkit/plot.py).

Plots are drawn without a window (Agg backend) and checked by what is on
the axes: number and labels of lines, limits, panels, shaded spike ranges,
and that a file is saved. How the plots look is checked by eye in
notebooks/09_plotting.ipynb.
"""

import matplotlib

matplotlib.use("Agg")                                   # draw off-screen; must come before pyplot

import matplotlib.pyplot as plt
import numpy as np
import pytest

import spectrum_toolkit as stk
from spectrum_toolkit import Spectrum, SpectrumCollection

X = np.arange(100, 1800, 1.19)


@pytest.fixture(autouse=True)
def close_figures():
    """Close every figure after each test so memory does not grow."""
    yield
    plt.close("all")


def peaks(rng, n):
    """n noisy spectra with two bands, as a collection."""
    clean = 200 + 3000 / (1 + ((X - 1000) / 6) ** 2) + 1500 / (1 + ((X - 1500) / 8) ** 2)
    return SpectrumCollection(X, rng.poisson(clean, (n, X.size)).astype(float), x_unit="cm-1", y_unit="counts")


def test_lines_labels_and_units():
    """One line per spectrum, legend with names for a few spectra, axis labels from the units."""
    c = peaks(np.random.default_rng(0), 3)
    ax = c.plot()
    assert [l.get_label() for l in ax.get_lines()] == list(c.names)
    assert ax.get_legend() is not None
    assert ax.get_xlabel() == "cm-1" and ax.get_ylabel() == "counts"


def test_many_spectra_no_legend_and_huge_drawn_together():
    """More than 10 spectra: no legend; more than 200: one LineCollection instead of 250 lines."""
    rng = np.random.default_rng(1)
    assert peaks(rng, 20).plot().get_legend() is None
    ax = peaks(rng, 250).plot()
    assert len(ax.get_lines()) == 0 and len(ax.collections) == 1
    assert len(ax.collections[0].get_segments()) == 250


def test_overlay_of_several_items_with_own_x():
    """Spectra with different x can be drawn together; labels can be given."""
    a = Spectrum(X, np.sin(X / 50), name="a")
    b = Spectrum(X[::2] + 0.3, np.cos(X[::2] / 50), name="b")
    ax = stk.plot(a, b, labels=["first", "second"])
    assert [l.get_label() for l in ax.get_lines()] == ["first", "second"]
    with pytest.raises(ValueError, match="labels"):
        stk.plot(a, b, labels=["only one"])


def test_stack_shifts_each_spectrum_up():
    """kind="stack": each next spectrum is higher by the offset."""
    c = peaks(np.random.default_rng(2), 4)
    ax = c.plot("stack", offset=1000)
    y = [l.get_ydata() for l in ax.get_lines()]
    assert np.allclose([y[i][0] - c.Y[i][0] for i in range(4)], [0, 1000, 2000, 3000])


def test_mean_band_and_image():
    """kind="mean" draws the mean with a ±1 SD band; kind="image" a picture with a colour bar."""
    c = peaks(np.random.default_rng(3), 6)
    ax = c.plot("mean")
    assert np.allclose(ax.get_lines()[0].get_ydata(), c.Y.mean(axis=0))
    assert ax.get_lines()[0].get_label() == "set 1 (n=6)" and len(ax.collections) == 1
    ax = c.plot("image")
    assert ax.collections[0].get_array().size == c.Y.size and len(ax.figure.axes) == 2
    with pytest.raises(ValueError, match="one collection"):
        stk.plot(c, c, kind="image")


def test_region_zooms_x_and_y():
    """region sets the x limits, and the y limits follow the data inside it."""
    c = peaks(np.random.default_rng(4), 2)
    ax = c.plot(region=(1400, 1600))
    assert ax.get_xlim() == (1400, 1600)
    inside = c.Y[:, (X >= 1400) & (X <= 1600)]
    assert ax.get_ylim()[0] < inside.min() and ax.get_ylim()[1] > inside.max()
    assert ax.get_ylim()[1] < c.Y.max()                          # the 1000 cm-1 band is not in view


def test_compare_despike_shows_removed_panel_and_shades_spikes():
    """compare after despike: two panels, the removed spike in the lower one, spike range shaded."""
    rng = np.random.default_rng(5)
    y = 1000 + rng.normal(0, 20, X.size)
    y[700] += 5000
    s = Spectrum(X, y, name="s")
    after = s.despike(verbose=False)
    ax = stk.compare(s, after)
    low = ax.figure.axes[1]
    assert np.isclose(low.get_lines()[0].get_ydata()[700], y[700] - after.y[700])
    assert len(ax.patches) == 1                                   # one shaded spike range
    assert ax.get_title().startswith("s: despike: single")


def test_compare_baseline_draws_the_baseline_and_rescaled_steps_get_their_own_axis():
    c = peaks(np.random.default_rng(6), 2)
    ax = stk.compare(c, c.baseline(), 1)
    assert "baseline" in [l.get_label() for l in ax.get_lines()]
    ax = stk.compare(c, c.normalize(), "Spectrum 2")
    assert len(ax.figure.axes) == 2 and len(ax.figure.axes[1].get_lines()) == 1      # "after" on the right axis
    assert not np.allclose(ax.figure.axes[1].get_ylim(), ax.get_ylim())   # a second y axis, own scale
    with pytest.raises(ValueError, match="different x"):
        stk.compare(c, c.trim(500, 1500), removed=True)


def test_save_style_and_errors(tmp_path):
    """save= writes the file; unknown kind or style is explained."""
    s = Spectrum(X, np.sin(X / 50))
    s.plot(style="publication", save=tmp_path / "s.png")
    assert (tmp_path / "s.png").stat().st_size > 1000
    with pytest.raises(ValueError, match="stack"):
        s.plot("bars")
    with pytest.raises(ValueError, match="publication"):
        s.plot(style="fancy")
    with pytest.raises(TypeError, match="Spectrum"):
        stk.plot(np.ones(3))


def test_highlight_ranges_spikes_and_wrong_values():
    """highlight: x ranges are shaded; spikes cut off by trim are skipped; a wrong value is an error."""
    c = peaks(np.random.default_rng(7), 2)
    ax = c.plot(highlight=[[990, 1010], [1490, 1510]])
    assert len(ax.patches) == 2
    rng = np.random.default_rng(8)
    y = 1000 + rng.normal(0, 20, X.size)
    y[50] += 5000                                                 # a spike near 160, then trimmed away
    s = Spectrum(X, y, name="s").despike(verbose=False).trim(400, None)
    ax = s.plot(highlight="spikes")
    assert len(ax.patches) == 0 and ax.get_xlim()[0] > 300       # the axis is not stretched to the spike
    for wrong in (0, "peaks", [1, 2], [[1, "a"]]):
        with pytest.raises(ValueError, match="highlight must be"):
            c.plot(highlight=wrong)


def test_emphasize_and_fill():
    c = SpectrumCollection(X[:200], np.random.default_rng(0).random((3, 200)), names=["a", "b", "c"])
    ax = c.plot(emphasize=["b"], line_width=1, faded_alpha=0.2)
    a, b, cc = ax.get_lines()[:3]
    assert b.get_linewidth() == 2 and b.get_zorder() > a.get_zorder()  # thicker and on top
    assert a.get_color()[3] == 0.2 and b.get_color()[3] == 1.0
    ax = c.plot(kind="stack", fill=True, fill_alpha=0.3)
    assert len(ax.collections) == 3                                     # one fill per spectrum
    for bad in ("x", 3, [True]):
        with pytest.raises(ValueError, match="emphasize"):
            c.plot(emphasize=bad)


def test_line_settings_on_many_spectra():
    c = SpectrumCollection(X[:50], np.random.default_rng(0).random((250, 50)))
    lines = c.plot().collections[0]
    assert lines.get_alpha() == 0.35                                    # default: see-through
    lines = c.plot(line_color="red", line_alpha=0.8).collections[0]
    assert lines.get_alpha() is None and tuple(lines.get_edgecolor()[0]) == (1, 0, 0, 0.8)
    assert len(c.plot(emphasize=0).get_lines()) == 250                  # emphasize draws each line
