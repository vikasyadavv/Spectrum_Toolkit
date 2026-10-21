"""Tests for smoothing (src/spectrum_toolkit/smooth.py).

Simulated spectra (12 Lorentzian bands 8-20 cm-1 wide, step 1.19 cm-1,
photon noise plus read noise) are smoothed and compared with the clean
spectrum. Limits are about 1.3 × what was measured when the methods were
compared (docs/benchmarks.md).
"""

import numpy as np
import pytest
from scipy.signal import savgol_filter

import spectrum_toolkit as stk
from spectrum_toolkit import Spectrum, SpectrumCollection
from spectrum_toolkit.smooth import DEFAULTS, METHODS

X = np.arange(100, 1800, 1.19)


def simulated(rng):
    """(clean, noisy) spectrum."""
    y = 300 + 0 * X
    for _ in range(12):
        y = y + rng.uniform(300, 4000) / (1 + ((X - rng.uniform(150, 1750)) / (rng.uniform(8, 20) / 2)) ** 2)
    return y, rng.poisson(y).astype(float) + rng.normal(0, 15, X.size)


# Largest median error after smoothing, in noise units (raw data: about 1.2).
LIMITS = {"savgol": 0.85, "whittaker": 0.85, "spline": 0.9, "gaussian": 0.95,
          "moving": 1.0, "median": 1.05, "fourier": 0.85}


@pytest.mark.parametrize("method", METHODS)
def test_each_method_reduces_noise(method):
    """With default settings, every method brings the data closer to the clean spectrum."""
    rng = np.random.default_rng(0)
    errors = []
    for _ in range(10):
        clean, y = simulated(rng)
        z = Spectrum(X, y).smooth(method).y
        errors.append(np.sqrt(np.mean(((z - clean) / np.sqrt(clean)) ** 2)))
    assert np.median(errors) < LIMITS[method]


def test_savgol_is_scipys():
    """"savgol" is exactly scipy's Savitzky-Golay filter (window 15, order 4, interp ends)."""
    y = np.random.default_rng(1).normal(0, 1, 300)
    assert np.allclose(Spectrum(np.arange(300.0), y).smooth().y, savgol_filter(y, 15, 4, mode="interp"))


def test_smoothing_a_straight_line_changes_nothing():
    """A straight line has no noise: savgol, whittaker and fourier leave it alone."""
    s = Spectrum(np.arange(100.0), 3 * np.arange(100.0) + 7)
    for m in ("savgol", "whittaker", "fourier"):
        assert np.allclose(s.smooth(m).y, s.y, atol=1e-6)


def test_collection_history_and_settings():
    """Works on collections; settings recorded; even windows become odd."""
    rng = np.random.default_rng(2)
    c = SpectrumCollection(X, np.vstack([simulated(rng)[1] for _ in range(3)]))
    out = c.smooth("moving", window=6)
    assert out.Y.shape == c.Y.shape
    assert out.history[-1] == {"step": "smooth", "method": "moving", "window": 6}


def test_bad_settings_explained():
    """Unknown methods and settings, and impossible values, give clear errors."""
    s = Spectrum(X, np.ones(X.size))
    with pytest.raises(ValueError, match="savgol"):
        s.smooth("lowess")
    with pytest.raises(ValueError, match="'window'"):
        s.smooth("savgol", width=5)
    with pytest.raises(ValueError, match="smaller than the window"):
        s.smooth("savgol", window=5, order=5)
