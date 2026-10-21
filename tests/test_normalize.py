"""Tests for normalisation (src/spectrum_toolkit/normalize.py).

Replicates of one simulated spectrum are multiplied by random factors (and
in some tests given an offset or slope); after normalising they should be
the same again, within noise. Limits are about 1.5 × what was measured in
docs/benchmarks.md (noise floor about 3.4 %).
"""

from pathlib import Path

import numpy as np
import pytest

import spectrum_toolkit as stk
from spectrum_toolkit import Spectrum, SpectrumCollection
from spectrum_toolkit.normalize import DEFAULTS, METHODS

DATA = Path(__file__).parent.parent / "data"
X = np.arange(100, 1800, 1.19)


def lorentz(c, w, h):
    return h / (1 + ((X - c) / (w / 2)) ** 2)


def replicates(rng, offset=False, slope=False, changing=False, k=10):
    """k noisy copies of one spectrum with random scale (and offset/slope/changing band)."""
    base = 50 + lorentz(1000, 12, 3000)                               # 1000 cm-1: internal standard
    for _ in range(12):
        base = base + lorentz(rng.uniform(150, 1750), rng.uniform(8, 20), rng.uniform(300, 4000))
    Y = []
    for _ in range(k):
        y = (base + (lorentz(600, 15, rng.uniform(0, 20000)) if changing else 0)) * rng.uniform(0.5, 2)
        y = y + (rng.uniform(0, 800) if offset else 0) + (rng.uniform(-1, 1) * (X - 950) if slope else 0)
        Y.append(rng.poisson(np.clip(y, 0, None)) + rng.normal(0, 15, X.size))
    return np.array(Y)


def spread(Y, keep=slice(None)):
    """Remaining difference between replicates, in % of the signal variation."""
    return 100 * np.sqrt(np.mean(Y[:, keep].var(axis=0))) / np.std(Y.mean(axis=0)[keep])


def test_simple_methods_on_known_numbers():
    """Each one-spectrum method gives the textbook result."""
    s = Spectrum([0.0, 1, 2, 3], [1.0, 2, 3, 6])
    assert np.allclose(s.normalize("max").y, [1 / 6, 2 / 6, 3 / 6, 1])
    assert np.allclose(s.normalize("minmax").y, [0, 0.2, 0.4, 1])
    assert np.isclose(np.trapezoid(s.normalize("area").y, s.x), 1)
    assert np.isclose(np.linalg.norm(s.normalize("vector").y), 1)
    z = s.normalize("snv").y
    assert np.isclose(z.mean(), 0) and np.isclose(z.std(), 1)
    assert np.isclose(np.median(s.normalize("rsnv").y), 0)


@pytest.mark.parametrize("method", [m for m in METHODS if m != "band"])
def test_every_method_removes_a_scale_factor(method):
    """Replicates that differ only by a factor are equal again (benchmark: 3.4-6.2 %)."""
    Y = replicates(np.random.default_rng(0))
    assert spread(Y) > 15                                              # clearly different before
    assert spread(SpectrumCollection(X, Y).normalize(method).Y) < 9.5


def test_offsets_need_snv_msc_or_emsc_and_slopes_need_emsc():
    rng = np.random.default_rng(1)
    Y = replicates(rng, offset=True)
    for m in ("snv", "msc", "emsc"):
        assert spread(SpectrumCollection(X, Y).normalize(m).Y) < 6.5          # benchmark 4.3
    assert spread(SpectrumCollection(X, Y).normalize("max").Y) > 15           # max cannot remove an offset
    Y = replicates(rng, offset=True, slope=True)
    assert spread(SpectrumCollection(X, Y).normalize("emsc").Y) < 8.5         # benchmark 5.5
    assert spread(SpectrumCollection(X, Y).normalize("msc").Y) > 20


def test_pqn_and_internal_standard_ignore_a_band_that_really_changes():
    """With one band changing a lot, pqn and normalising to a constant band stay right (benchmark ~4 %)."""
    Y = replicates(np.random.default_rng(2), changing=True)
    keep = np.abs(X - 600) > 60
    c = SpectrumCollection(X, Y)
    assert spread(c.normalize("pqn").Y, keep) < 6.5
    assert spread(c.normalize("band", region=(985, 1015)).Y, keep) < 7.5
    assert spread(c.normalize("snv").Y, keep) > 15                             # pulled by the changing band


def test_band_measures_height_above_local_line():
    """band height is measured above a straight line under the band, so a background does not count."""
    y = 500 + 0.5 * X + lorentz(1000, 12, 2000)
    out = Spectrum(X, y).normalize("band", region=(940, 1060))
    i = np.argmin(np.abs(X - 1000))
    height = (y[i] - np.interp(X[i], [X[X >= 940][0], X[X <= 1060][-1]],
                               [y[X >= 940][0], y[X <= 1060][-1]]))
    assert np.isclose(out.y[i], y[i] / height)
    with pytest.raises(ValueError, match="region"):
        Spectrum(X, y).normalize("band")


def test_reference_methods_on_a_single_spectrum():
    """msc/emsc/pqn need a reference for one spectrum; with one, the scale is undone."""
    rng = np.random.default_rng(3)
    Y = replicates(rng, k=2)
    with pytest.raises(ValueError, match="reference"):
        Spectrum(X, Y[0]).normalize("msc")
    ref = Spectrum(X, Y[1])
    out = Spectrum(X, Y[0]).normalize("msc", reference=ref)
    assert spread(np.vstack([out.y, Y[1]])) < 6
    assert out.history[-1]["reference"] == "given"
    with pytest.raises(ValueError, match="resample"):
        Spectrum(X, Y[0]).normalize("pqn", reference=Y[1][:-1])


def test_region_history_and_errors():
    s = Spectrum(X, lorentz(1000, 12, 2000) + 100)
    out = s.normalize("max", region=(1200, 1300))
    assert np.isclose(out.y[(X >= 1200) & (X <= 1300)].max(), 1)
    assert out.history[-1] == {"step": "normalize", "method": "max", **DEFAULTS["max"], "region": (1200, 1300)}
    with pytest.raises(ValueError, match="fewer than 2"):
        s.normalize("area", region=(5000, 6000))
    with pytest.raises(ValueError, match="snv"):
        s.normalize("l2")
    with pytest.raises(ValueError, match="'order'"):
        s.normalize("snv", order=2)
    with pytest.raises(ValueError, match="zero"):
        Spectrum(X, np.ones(X.size)).normalize("snv")


def test_descending_x_gives_the_same_answer():
    y = lorentz(1000, 12, 2000) + 100
    a = Spectrum(X, y).normalize("area").y
    b = Spectrum(X[::-1], y[::-1]).normalize("area").y
    assert np.allclose(a, b[::-1])


real = pytest.mark.skipif(not (DATA / "CV10-4M.xlsx").is_file(), reason="data/ files not present")


@real
def test_real_cv_repeats_become_much_more_alike():
    """CV10-4M.xlsx (14 spots): spread 42 % before, about 16 % after SNV."""
    c = stk.load(DATA / "CV10-4M.xlsx", verbose=False).despike(verbose=False).baseline()
    assert spread(c.Y) > 35
    assert spread(c.normalize().Y) < 20
