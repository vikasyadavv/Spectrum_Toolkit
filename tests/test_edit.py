"""Tests for editing data (src/spectrum_toolkit/edit.py): trim, cut, select,
drop and combine.

Made-up spectra are used so every expected number is known exactly; the
real files in data/ are checked at the end (skipped when data/ is missing).
"""

from pathlib import Path

import numpy as np
import pytest

import spectrum_toolkit as stk
from spectrum_toolkit import Spectrum, SpectrumCollection

DATA = Path(__file__).parent.parent / "data"
X = np.arange(100.0, 200.0, 1.0)                    # 100 points: 100, 101, ... 199


def peak(x, centre=150.0, height=1000.0):
    """A smooth peak on a background of 10, so interpolation is easy to check."""
    return 10 + height * np.exp(-((x - centre) / 8) ** 2)


# ------------------------------------------------------------------ trim / cut
def test_trim_keeps_range_and_records_it():
    """trim keeps lo..hi (both ends included), leaves the original alone, notes the step."""
    s = Spectrum(X, peak(X))
    t = s.trim(120, 130)
    assert t.x[0] == 120 and t.x[-1] == 130 and len(t) == 11      # 120..130 inclusive
    assert len(s) == 100                                           # original untouched
    assert t.history[-1] == {"step": "trim", "lo": 120, "hi": 130, "points_removed": 89}


def test_trim_accepts_reversed_limits_and_collections():
    """trim(130, 120) is the same as trim(120, 130), and works on all spectra at once."""
    c = SpectrumCollection(X, np.vstack([peak(X), 2 * peak(X)]))
    t = c.trim(130, 120)
    assert t.Y.shape == (2, 11) and np.allclose(t.Y[1], 2 * t.Y[0])


def test_cut_removes_a_region():
    """cut removes lo..hi and keeps both sides."""
    t = Spectrum(X, peak(X)).cut(140.5, 160.5)
    assert 140 in t.x and 161 in t.x and 150 not in t.x            # gap from 141 to 160
    assert len(t) == 80


def test_trim_outside_the_data_gives_clear_error():
    """Trimming to a range with no data says where the data is."""
    with pytest.raises(ValueError, match="x runs from 100 to 199"):
        Spectrum(X, peak(X)).trim(500, 600)


# --------------------------------------------------------------- select / drop
def test_select_and_drop_by_name_and_number():
    """Spectra are picked by name or number (0 = first, -1 = last); positions follow."""
    c = SpectrumCollection(X, np.vstack([peak(X, height=h) for h in (1, 2, 3)]),
                           names=["a", "b", "c"], positions=[[0, 0], [1, 0], [2, 0]])
    assert c.select("c", 0).names == ("c", "a")                   # order as asked
    d = c.drop("b")
    assert d.names == ("a", "c") and np.allclose(d.positions[:, 0], [0, 2])   # map positions kept
    assert c.drop(-1).names == ("a", "b")                         # -1 = last
    assert d.history[-1] == {"step": "drop", "spectra": ["b"]}


def test_select_unknown_name_lists_real_names():
    """A wrong name gives an error listing the names that exist."""
    c = SpectrumCollection(X, np.ones((2, 100)), names=["a", "b"])
    with pytest.raises(ValueError, match="'a', 'b'"):
        c.select("A")


# --------------------------------------------------------------------- combine
def test_combine_same_x_stacks_and_names_by_file():
    """Case 1: single-spectrum files on the same x are stacked; each is named after its file."""
    a = Spectrum(X, peak(X), meta={"source": "data/sample A.txt"})
    b = Spectrum(X, 2 * peak(X), meta={"source": "data/sample B.txt"})
    c = stk.combine(a, b, verbose=False)
    assert c.names == ("sample A", "sample B") and np.allclose(c.Y[1], 2 * c.Y[0])
    assert c.meta["axis_report"].case == "same"


def test_combine_same_grid_keeps_shared_points_without_changing_values():
    """Case 2a: same x values, but one spectrum is shorter and one has a gap.

    Only the x values present in every spectrum are kept; no number changes.
    """
    a = Spectrum(X, peak(X), name="full")
    b = Spectrum(X[5:], peak(X[5:]), name="short")                 # starts at 105
    keep = np.ones(100, bool)
    keep[50:52] = False                                            # 150, 151 missing
    g = Spectrum(X[keep], peak(X[keep]), name="gap")
    c = stk.combine(a, b, g, verbose=False)
    assert c.meta["axis_report"].case == "same grid"
    assert c.x[0] == 105 and 150 not in c.x and c.n_points == 93   # 100 - 5 - 2
    assert np.allclose(c.Y, peak(c.x))                             # values untouched


def test_combine_different_x_needs_permission():
    """Case 2b: shifted x values are refused unless interpolate=True; the error shows the table."""
    a = Spectrum(X, peak(X), name="a")
    b = Spectrum(X + 0.4, peak(X + 0.4), name="b")                # same peak, x shifted by 0.4
    with pytest.raises(ValueError, match="interpolate=True"):
        stk.combine(a, b, verbose=False)
    c = stk.combine(a, b, interpolate=True, verbose=False)
    assert c.x[0] == 101 and c.x[-1] == 199                         # common range, on a's x
    # Linear interpolation of a smooth peak: error under 1 % of the peak height.
    assert np.max(np.abs(c.Y[1] - peak(c.x))) < 10
    assert c.history[0]["interpolation"] == "linear"


@pytest.mark.parametrize("method", ["linear", "quadratic", "cubic", "spline", "pchip", "akima"])
def test_every_interpolation_method_reproduces_a_smooth_peak(method):
    """Each method, on points 0.4 apart from the measured ones, stays close to the true peak.

    The peak is 1000 high and 16 points wide; tolerance 1 % of the height
    for linear (it cuts corners at the top) and 0.5 % for the curved methods.
    """
    b = Spectrum(X + 0.4, peak(X + 0.4), name="b")
    c = stk.combine(Spectrum(X, peak(X), name="a"), b, interpolate=method, verbose=False)
    tol = 10 if method == "linear" else 5
    assert np.max(np.abs(c.Y[1] - peak(c.x))) < tol
    assert c.history[0]["interpolation"] == method


def test_unknown_or_polynomial_method_explained():
    """A wrong method name lists the choices; 'polynomial' explains why it is not offered."""
    a, b = Spectrum(X, peak(X), name="a"), Spectrum(X + 0.4, peak(X + 0.4), name="b")
    with pytest.raises(ValueError, match="pchip"):
        stk.combine(a, b, interpolate="splien", verbose=False)
    with pytest.raises(ValueError, match="Runge"):
        stk.combine(a, b, interpolate="polynomial", verbose=False)


def test_resample_refuses_to_extrapolate():
    """resample onto x outside the measured range is refused."""
    with pytest.raises(ValueError, match="outside"):
        stk.resample(Spectrum(X, peak(X)), [90, 100, 110])


def test_combine_refuses_ranges_that_barely_overlap():
    """Interpolation is refused when a spectrum would lose more than 10 % of its range."""
    a = Spectrum(X, peak(X), name="a")
    b = Spectrum(X[:40] + 0.5, peak(X[:40]), name="b")             # 100.5 to 139.5 only
    with pytest.raises(ValueError, match="too different"):
        stk.combine(a, b, interpolate=True, verbose=False)


def test_combine_reference_defaults_to_coarsest_step():
    """With a coarse and a fine axis, the coarse one is the reference (no invented detail)."""
    fine = Spectrum(X, peak(X), name="fine")                      # step 1
    coarse = Spectrum(X[::2] + 0.3, peak(X[::2] + 0.3), name="coarse")   # step 2, shifted
    c = stk.combine(fine, coarse, interpolate=True, verbose=False)
    assert c.history[0]["reference"] == "coarse" and np.allclose(np.diff(c.x), 2)
    c2 = stk.combine(fine, coarse, interpolate=True, reference="fine", verbose=False)
    assert np.allclose(np.diff(c2.x), 1)                          # chosen by hand


def test_combine_mix_of_collections_and_spectra():
    """Case 3: a collection plus single spectra, from different files."""
    col = SpectrumCollection(X, np.vstack([peak(X), peak(X)]), names=["1", "2"], meta={"source": "multi.xlsx"})
    one = Spectrum(X, peak(X), name="x", meta={"source": "single.txt"})
    c = stk.combine([col, one], verbose=False)                     # a list works too
    assert c.names == ("multi: 1", "multi: 2", "single: x")


# ------------------------------------------------------------------ real data
real = pytest.mark.skipif(not (DATA / "CV10-4M.xlsx").is_file(), reason="data/ files not present")


@real
def test_real_pairs_with_gaps_combine_without_interpolation():
    """CV+RhB+MB.xlsx: 35 pairs on one x grid; two have points missing in the middle."""
    c = stk.combine(stk.load(DATA / "CV+RhB+MB.xlsx", verbose=False), verbose=False)
    assert len(c) == 35 and c.meta["axis_report"].case == "same grid"
    assert c.n_points == 618                                       # 621 minus 3 missing points


@real
def test_real_three_files_interpolated():
    """CV, RhB and MB files: x axes shifted by up to 0.57 cm-1, so interpolation is needed."""
    files = [DATA / f for f in ("CV10-4M.xlsx", "RhB10-4M.xlsx", "MB 10-4M.xlsx")]
    with pytest.raises(ValueError, match="interpolate=True"):
        stk.combine(*files, verbose=False)
    c = stk.combine(*files, interpolate=True, verbose=False)
    assert len(c) == 30 and c.names[-1] == "MB 10-4M: 5"           # 14 + 11 + 5 spectra
    # Spectra on the reference axis (CV) come through unchanged.
    cv = stk.load(files[0], verbose=False)
    i = np.searchsorted(cv.x, c.x)
    assert np.allclose(c.Y[0], cv.Y[0, i])
