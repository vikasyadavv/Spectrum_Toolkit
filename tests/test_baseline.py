"""Tests for baseline correction (src/spectrum_toolkit/baseline.py).

Simulated spectra with a KNOWN baseline (curved polynomial, fluorescence
decay, broad humps) plus Lorentzian bands and photon noise, so the error of
each method can be measured. The limits below are about 1.5 × the errors
measured when the methods were compared (docs/roadmap.md, feature 4).
"""

import numpy as np
import pytest
import scipy.sparse as sp
import scipy.sparse.linalg as spl

import spectrum_toolkit as stk
from spectrum_toolkit import Spectrum, SpectrumCollection
from spectrum_toolkit.baseline import DEFAULTS, METHODS

X = np.arange(100, 1800, 1.19)


def simulated(rng, kind):
    """(true baseline, noisy spectrum) of the given kind."""
    t = (X - X[0]) / np.ptp(X)
    if kind == "poly":
        b = 800 + 600 * t - 900 * t ** 2 + rng.uniform(-200, 200) * t ** 3
    elif kind == "fluor":
        b = 300 + 3000 * np.exp(-t / rng.uniform(0.3, 0.8))
    else:
        b = 400 + sum(rng.uniform(500, 2000) * np.exp(-((t - rng.uniform(0, 1)) / rng.uniform(0.15, 0.4)) ** 2)
                      for _ in range(2))
    y = b.copy()
    for _ in range(12):                                    # 12 bands, 8-20 cm-1 wide
        y += rng.uniform(200, 4000) / (1 + ((X - rng.uniform(150, 1750)) / (rng.uniform(8, 20) / 2)) ** 2)
    return b, rng.poisson(np.clip(y, 0, None)).astype(float) + rng.normal(0, 15, X.size)


def test_asls_matches_the_matlab_function():
    """Our "asls" gives the same baseline as baseline.m (written the MATLAB way, with sparse matrices)."""
    rng = np.random.default_rng(0)
    _, y = simulated(rng, "fluor")
    m = y.size
    D = sp.diags([1, -2, 1], [0, 1, 2], shape=(m - 2, m), dtype=float)          # diff(speye(m), 2)
    w = np.ones(m)
    for _ in range(10):                                            # for it = 1:10
        z = spl.spsolve((sp.diags(w) + 1e5 * (D.T @ D)).tocsc(), w * y)
        w = 0.005 * (y > z) + (1 - 0.005) * (y < z)
    ours = stk.find_baseline(Spectrum(X, y), "asls").y             # defaults = lam 1e5, p 0.005, 10 rounds
    assert np.max(np.abs(ours - z)) < 1e-6 * np.max(np.abs(y))


# Largest median error allowed, in noise units (sqrt of the mean baseline).
LIMITS = {"asls": 5, "iasls": 10, "arpls": 4, "airpls": 3, "modpoly": 4,
          "imodpoly": 5.5, "rollingball": 4.5, "snip": 7}


@pytest.mark.parametrize("method", METHODS)
def test_each_method_recovers_a_known_baseline(method):
    """With default settings, every method finds the true baseline within a few noise units."""
    rng = np.random.default_rng(1)
    errors = []
    for kind in ("poly", "fluor", "humps"):
        for _ in range(5):
            b, y = simulated(rng, kind)
            z = stk.find_baseline(Spectrum(X, y), method).y
            errors.append(np.sqrt(np.mean((z - b) ** 2)) / np.sqrt(np.mean(b)))
    assert np.median(errors) < LIMITS[method]


def test_baseline_subtracts_find_baseline_and_records_settings():
    """baseline() = data - find_baseline(); the settings used are in history."""
    rng = np.random.default_rng(2)
    _, y = simulated(rng, "poly")
    s = Spectrum(X, y)
    corrected = s.baseline("arpls", lam=1e7)
    assert np.allclose(corrected.y, y - stk.find_baseline(s, "arpls", lam=1e7).y)
    assert corrected.history[-1] == {"step": "baseline", "method": "arpls", **DEFAULTS["arpls"], "lam": 1e7}


def test_collection_and_descending_x():
    """Works on a whole collection, and on x written high to low."""
    rng = np.random.default_rng(3)
    Y = np.vstack([simulated(rng, "fluor")[1] for _ in range(3)])
    c = SpectrumCollection(X, Y).baseline()
    flipped = Spectrum(X[::-1], Y[0][::-1]).baseline()
    assert c.Y.shape == (3, X.size)
    assert np.allclose(flipped.y[::-1], c.Y[0])                    # same answer either way round


def test_wrong_method_or_setting_explains():
    """Unknown method lists the methods; unknown setting lists that method's settings."""
    s = Spectrum(X, np.ones(X.size))
    with pytest.raises(ValueError, match="airpls"):
        s.baseline("als")
    with pytest.raises(ValueError, match="'lam'"):
        s.baseline("airpls", lambda_=1e5)
