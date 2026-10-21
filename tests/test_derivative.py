"""Tests for derivatives (src/spectrum_toolkit/derivative.py).

Simulated spectra of Lorentzian bands, whose exact derivatives are known
from the formula, are differentiated and compared. Limits are about 1.4 ×
what was measured in docs/benchmarks.md.
"""

import numpy as np
import pytest
from scipy.signal import savgol_filter

from spectrum_toolkit import Spectrum, SpectrumCollection
from spectrum_toolkit.derivative import METHODS

X = np.arange(100, 1800, 1.19)


def simulated(rng):
    """(noisy spectrum, exact 1st derivative, exact 2nd derivative)."""
    y, d1, d2 = np.full(X.size, 300.0), np.zeros(X.size), np.zeros(X.size)
    for _ in range(12):
        c, w, h = rng.uniform(150, 1750), rng.uniform(8, 20), rng.uniform(300, 4000)
        g = w / 2
        u = (X - c) / g
        L = 1 / (1 + u * u)
        y += h * L
        d1 += h * (-2 * u / g) * L ** 2
        d2 += h * (2 / g ** 2) * (3 * u * u - 1) * L ** 3
    return rng.poisson(y) + rng.normal(0, 15, X.size), d1, d2


# Largest median error in % of the exact derivative, for n = 1 and n = 2.
LIMITS = {"savgol": (19, 50), "gaussian": (22, 56), "spline": (20, 75), "gradient": (36, 90)}


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("n", [1, 2])
def test_each_method_matches_the_exact_derivative(method, n):
    rng = np.random.default_rng(0)
    errors = []
    for _ in range(10):
        y, d1, d2 = simulated(rng)
        exact = d1 if n == 1 else d2
        z = Spectrum(X, y).derivative(method, n=n).y
        errors.append(100 * np.sqrt(np.mean((z - exact) ** 2)) / np.sqrt(np.mean(exact ** 2)))
    assert np.median(errors) < LIMITS[method][n - 1]


def test_polynomials_are_exact():
    """A parabola: 1st derivative is a line, 2nd a constant, for every method (no noise)."""
    x = np.linspace(0, 10, 201)
    s = Spectrum(x, 3 * x ** 2 + 2 * x + 1)
    for m in ("savgol", "gradient"):
        assert np.allclose(s.derivative(m).y[2:-2], (6 * x + 2)[2:-2])
        assert np.allclose(s.derivative(m, n=2).y[3:-3], 6)


def test_savgol_equals_scipy_and_uses_tuned_defaults():
    rng = np.random.default_rng(1)
    y = simulated(rng)[0]
    step = X[1] - X[0]
    assert np.allclose(Spectrum(X, y).derivative().y, savgol_filter(y, 15, 5, deriv=1, delta=step, mode="interp"))
    d2 = Spectrum(X, y).derivative(n=2)
    assert np.allclose(d2.y, savgol_filter(y, 11, 4, deriv=2, delta=step, mode="interp"))
    assert d2.history[-1] == {"step": "derivative", "method": "savgol", "n": 2, "window": 11, "order": 4}
    assert Spectrum(X, y).derivative(window=21, order=3).history[-1]["window"] == 21


def test_uneven_spacing_and_descending_x():
    """Uneven points are regridded for savgol/gaussian (recorded); x high-to-low gives the same answer."""
    x = np.sort(np.random.default_rng(2).uniform(0, 100, 400))
    s = Spectrum(x, np.sin(x / 10))
    for m in ("savgol", "gaussian", "spline"):
        d = s.derivative(m)
        assert np.max(np.abs(d.y - np.cos(x / 10) / 10)[20:-20]) < 0.01
    assert s.derivative("savgol").history[-1]["regridded"] is True
    assert "regridded" not in s.derivative("spline").history[-1]
    y = simulated(np.random.default_rng(3))[0]
    assert np.allclose(Spectrum(X[::-1], y[::-1]).derivative().y[::-1], Spectrum(X, y).derivative().y)


def test_units_collection_and_errors():
    c = SpectrumCollection(X, np.vstack([np.sin(X / 50), np.cos(X / 50)]), x_unit="cm-1", y_unit="counts")
    d = c.derivative(n=2)
    assert d.Y.shape == c.Y.shape and d.y_unit == "d²(counts)/d(cm-1)²"
    with pytest.raises(ValueError, match="n must be 1"):
        c.derivative(n=3)
    with pytest.raises(ValueError, match="savgol needs"):
        c.derivative(order=1, n=2)
    with pytest.raises(ValueError, match="gradient"):
        c.derivative("finite")
