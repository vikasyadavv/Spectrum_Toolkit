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


def _bands():
    """Three spectra with bands at 1000 and 1400 (the second band taller)."""
    x = np.linspace(400, 1800, 700)
    y = np.exp(-((x - 1000) / 15) ** 2) + 2 * np.exp(-((x - 1400) / 15) ** 2)
    return SpectrumCollection(x, np.array([y, 0.8 * y, 0.6 * y]), names=["a", "b", "c"])


def test_marks_with_own_settings_and_span():
    from matplotlib.colors import to_rgb
    c = _bands()
    ax = c.plot(marks={1000: {"label": "A", "color": "red", "style": "--"}, 1400: "B"}, mark_span="peak")
    lines = [line for line in ax.get_lines() if list(line.get_xdata()) in ([1000, 1000], [1400, 1400])]
    assert len(lines) == 2
    first, second = sorted(lines, key=lambda line: line.get_xdata()[0])
    assert to_rgb(first.get_color()) == (1, 0, 0) and first.get_linestyle() == "--"
    assert second.get_linestyle() == ":"                                # the style's mark_style
    assert abs(max(second.get_ydata()) - 2.0) < 0.05                    # up to the spectrum, not the top
    ax = c.plot(marks=[1000], mark_span="tick")
    tick = [line for line in ax.get_lines() if list(line.get_xdata()) == [1000, 1000]][0]
    assert min(tick.get_ydata()) > 1.0                                  # a short line above the band
    with pytest.raises(ValueError, match="marks: unknown key"):
        c.plot(marks={1000: {"label": "A", "colour": "red"}})
    with pytest.raises(ValueError, match="mark_style"):
        c.plot(marks={1000: {"style": "dotted"}})
    with pytest.raises(ValueError, match="marks must be"):
        c.plot(marks="1000")


def test_peak_labels_settings():
    from matplotlib.colors import to_rgb
    c = _bands()
    ax = c.plot(peaks=2, peak_spectra="all", peak_label_color="line", peak_label_format="{:.1f} cm⁻¹",
                label_overlap="keep")
    texts = ax.texts
    assert len(texts) == 6 and texts[0].get_text().endswith(" cm⁻¹")    # 2 bands x 3 spectra
    assert {to_rgb(t.get_color()) for t in texts} == {to_rgb(line.get_color()) for line in ax.get_lines()[:3]}
    ax = c.plot(peaks=2, peak_line=True, peak_label_pad=20, peak_line_color="red")
    assert all(t.arrow_patch is not None for t in ax.texts)
    assert len(c.plot(peaks=5, peak_sensitivity=0.9).texts) == 1        # only the tall band stands out enough
    ax = c.plot(peaks=[1400], peak_label_position="top", peak_label_box=True, peak_label_fill="yellow")
    assert ax.texts[0].get_bbox_patch() is not None
    assert ax.texts[0].xycoords == ("data", "axes fraction")            # above the box


def test_overlapping_labels_are_moved_apart():
    c = _bands()
    ax = c.plot(marks={1000: "AAAA", 1003: "BBBB"})
    r = ax.figure.canvas.get_renderer()
    from matplotlib.text import Text
    for t in ax.texts:
        t.update_positions(r)
    a, b = (Text.get_window_extent(t, r) for t in ax.texts)
    assert not a.overlaps(b)
    ax = c.plot(marks={1000: "AAAA", 1003: "BBBB"}, label_overlap="keep")
    assert all(t.xyann == (0, 0) for t in ax.texts)


def test_highlight_ranges_with_own_settings_and_labels():
    from matplotlib.colors import to_rgba
    c = _bands()
    ax = c.plot(highlight=[[900, 950], {"range": [1350, 1450], "label": "B band", "color": "blue", "alpha": 0.3,
                                        "hatch": "//", "edge_color": "black"}],
                highlight_color="green")
    first, second = ax.patches[-2:]
    assert first.get_facecolor() == to_rgba("green", 0.15)
    assert second.get_facecolor() == to_rgba("blue", 0.3) and second.get_hatch() == "//"
    assert second.get_edgecolor() == to_rgba("black")
    assert [t.get_text() for t in ax.texts] == ["B band"]
    for bad in ([{"range": [1, 2], "colour": "red"}], [{"label": "x"}], [{"range": [1, 2], "hatch": "#"}]):
        with pytest.raises(ValueError, match="highlight"):
            c.plot(highlight=bad)


def test_math_text_in_labels():
    ax = _bands().plot(marks={1000: r"$\nu_{as}$(CH$_2$)"})
    ax.figure.canvas.draw()                                             # math text is drawn without error


# ------------------------------------------------------------------ wish list section 7
def test_log_scales_and_second_axes():
    c = _bands()
    ax = c.plot(x_log=True, y_log=True)
    assert ax.get_xscale() == "log" and ax.get_yscale() == "log"
    ax = c.plot(top_axis="wavelength", top_axis_laser=532, right_axis="scale", right_axis_scale=0.1,
                right_axis_label="cps")
    top, right = ax.child_axes
    assert top.get_xlabel() == "Wavelength (nm)" and right.get_ylabel() == "cps"
    # 1000 cm⁻¹ from a 532 nm laser is at 1e7 / (1e7/532 - 1000) = 561.89 nm
    forward = top._functions[0]
    assert forward(1000) == pytest.approx(561.89, abs=0.01)
    assert not ax.xaxis.get_tick_params(which="major").get("labeltop", False)


def test_cut_breaks_the_line_and_marks_the_gap():
    c = _bands().cut(1200, 1300)
    ax = c.plot(cut_marks=True, box="closed")
    y = ax.get_lines()[0].get_ydata()
    assert np.isnan(y).sum() == 1                                        # one break, where the cut was
    marks = [l for l in ax.get_lines() if l.get_label() == "_cut mark"]
    assert len(marks) == 2                                               # bottom and (closed box) top
    ax = c.plot()                                                        # off by default: no break
    assert not np.isnan(ax.get_lines()[0].get_ydata()).any()


def test_line_names_with_or_without_legend_and_scale_bar_beside_them():
    c = _bands()
    ax = c.plot(kind="stack", line_names=True, legend=False, scale_bar=500)
    assert ax.get_legend() is None
    names = [t for t in ax.texts if t.get_text() in c.names]
    assert len(names) == len(c.names)
    ax = c.plot(kind="stack", line_names=True, legend=True, scale_bar=500)
    assert ax.get_legend() is not None                                   # both, when asked
    r = ax.figure.canvas.get_renderer()
    bar_text = next(t for t in ax.texts if t.get_text().startswith("500"))
    for t in ax.texts:
        t.update_positions(r)
    reach = max(t.get_window_extent(r).x1 for t in ax.texts if t.get_text() in c.names)
    assert bar_text.get_window_extent(r).x0 > reach                      # the bar's text is past the names


def test_mean_band_kinds():
    c = _bands()
    for kind in ("std", "2std", "minmax", "ci95"):
        ax = c.plot(kind="mean", mean_band=kind)
        assert len(ax.collections) == 1
    assert not c.plot(kind="mean", mean_band="none").collections


def test_image_limits_names_and_colorbar():
    c = _bands()
    ax = c.plot(kind="image", color_limits=[0, 1000], image_y="name", colorbar_ticks_at=[0, 500, 1000])
    mesh = ax.collections[0]
    assert mesh.get_clim() == (0, 1000)
    assert [t.get_text() for t in ax.get_yticklabels()] == list(c.names)
    assert len(ax.figure.axes) == 2                                      # the plot and its colour bar
    ax = c.plot(kind="image", colorbar=False)
    assert len(ax.figure.axes) == 1
    assert all(float(v).is_integer() for v in ax.get_yticks())           # whole spectrum numbers


def test_notes_with_arrow_and_own_settings():
    c = _bands()
    ax = c.plot(notes=[{"text": "band", "x": 1100, "y": 2000, "arrow": [1000, 3000], "color": "red", "box": True},
                       {"text": "corner", "x": 0.1, "y": 0.9, "coords": "axes"}])
    band, corner = ax.texts
    assert band.arrow_patch is not None and corner.arrow_patch is None
    assert band.get_bbox_patch() is not None
    from matplotlib.colors import to_rgba
    assert to_rgba(band.get_color()) == to_rgba("red")
    for bad in ([{"x": 1, "y": 2}], [{"text": "a", "x": 1, "y": 2, "colour": "red"}], "text"):
        with pytest.raises(ValueError, match="notes"):
            c.plot(notes=bad)


def test_inset_zooms_and_keeps_clear_of_the_legend():
    c = _bands()
    ax = c.plot(inset={"region": [950, 1050], "position": "upper left"})
    small = ax.child_axes[0]
    assert small.get_xlim() == pytest.approx((950, 1050))
    assert len(small.get_lines()) == len(c.names)
    r = ax.figure.canvas.get_renderer()
    assert not ax.get_legend().get_window_extent(r).overlaps(small.get_tightbbox(r))
    with pytest.raises(ValueError, match="inset"):
        c.plot(inset={"region": [950, 1050], "size": 2})


def test_panels_layout_letters_and_sharing():
    c = _bands()
    axes = stk.panels([c, {"data": c, "kind": "stack", "peaks": 2, "line_width": 2}, {"data": c, "kind": "mean"}])
    assert len(axes) == 3 and len(axes[0].figure.axes) == 3              # one column of three
    assert [t.get_text() for ax in axes for t in ax.texts if t.get_text().startswith("(")] == ["(a)", "(b)", "(c)"]
    assert axes[1].get_lines()[0].get_linewidth() == 2                    # the panel's own setting
    axes = stk.panels([c, c, c], layout=[2, 2], share_x=True, share_y=True, panel_letter_case="upper",
                      panel_letter_format="{}", title="All")
    assert len(axes[0].figure.axes) == 3                                  # the empty fourth place is removed
    assert axes[0].figure.get_suptitle() == "All"
    assert "A" in [t.get_text() for t in axes[0].texts]
    axes[0].figure.canvas.draw()
    labelled = [any(t.get_visible() and t.get_text() for t in ax.get_xticklabels()) for ax in axes]
    assert labelled == [False, True, True]                               # numbers only under the bottom panels
    assert axes[1].get_ylabel() == "" and axes[0].get_ylabel()
    axes = stk.panels([c, {"data": c, "letter": False}, {"data": c, "letter": "(z)"}], panel_letters=False)
    assert [t.get_text() for ax in axes for t in ax.texts] == ["(z)"]
    for bad, match in (([], "panels"), ([{"kind": "mean"}], "data")):
        with pytest.raises(ValueError, match=match):
            stk.panels(bad)
    with pytest.raises(ValueError, match="layout"):
        stk.panels([c] * 5, layout=[2, 2])
    with pytest.raises(ValueError, match="Panel 2"):
        stk.panels([c, {"data": c, "nonsense": 1}])


def test_panels_save(tmp_path):
    c = _bands()
    stk.panels([c, c], save=str(tmp_path / "two.png"))
    assert (tmp_path / "two.png").exists()
