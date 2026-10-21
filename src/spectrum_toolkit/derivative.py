"""Derivatives: the slope (first derivative) or curvature (second derivative)
of a spectrum.

Why: a derivative removes a constant offset (1st) or a straight-line
background (2nd), and makes overlapping bands easier to tell apart: a band
top becomes a zero crossing (1st) or a sharp minimum (2nd). The price is
noise: differentiating amplifies point-to-point noise, so every method
smooths at the same time. The settings control that trade, as in smoothing.

``s.derivative(method, n=1 or 2, **settings)``. The result is per x unit
(e.g. counts per cm-1), so it does not depend on the point spacing.

Methods
-------
"savgol"    Savitzky-Golay (1964): fit a polynomial of ``order`` in a moving
            ``window`` (points) and take its derivative at the centre. The
            standard choice in spectroscopy. Left as None, window and order
            are chosen for n: window 15 / order 5 for n=1, window 11 /
            order 4 for n=2 (best in our comparison).
"gaussian"  Derivative of a Gaussian-smoothed spectrum, width ``sigma``
            (points). One setting; smooth and differentiate in one step.
            Left as None: 1.25 for n=1, 1.5 for n=2.
"spline"    Derivative of a smoothing spline; ``lam`` None (default) picks
            the amount of smoothing automatically (cross-validation).
"gradient"  Plain finite differences (numpy.gradient), no smoothing. Exact
            for clean data, very noisy for measured data; smooth first.

Spacing: "savgol" and "gaussian" assume evenly spaced points. If the points
are not evenly spaced (more than 1 % variation), the spectrum is put on an
even grid by linear interpolation, differentiated, and put back on the
original points; history records ``regridded=True``. "spline" and
"gradient" use the real x values directly.

The automatic settings were chosen on bands 8-20 cm-1 wide sampled every
1.19 cm-1 (about 7-17 points per band). For much broader bands (or finer
sampling) a larger window or sigma removes more noise; for narrower bands,
a smaller one. How the methods compare is in docs/benchmarks.md.

Note on Savitzky-Golay orders: for a 1st derivative, orders 3 and 4 give
identical results (likewise 5 and 6); for a 2nd derivative, 2 and 3 (and 4
and 5) do. This is a property of the method, not a bug.

References
----------
Savitzky, A. & Golay, M. J. E. (1964). Smoothing and differentiation of data by simplified least squares procedures. Anal. Chem. 36, 1627.
Rinnan, Å., van den Berg, F. & Engelsen, S. B. (2009). Review of the most common pre-processing techniques for near-infrared spectra. TrAC 28, 1201.

>>> import numpy as np
>>> from spectrum_toolkit import Spectrum
>>> x = np.arange(0.0, 100.0)
>>> d = Spectrum(x, 3 * x + 7).derivative("gradient")
>>> bool(np.allclose(d.y, 3))                                   # slope of a straight line
True
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import savgol_filter

from .core import Spectrum, SpectrumCollection

Data = Spectrum | SpectrumCollection

DEFAULTS: dict[str, dict[str, Any]] = {
    "savgol": {"n": 1, "window": None, "order": None},
    "gaussian": {"n": 1, "sigma": None},
    "spline": {"n": 1, "lam": None},
    "gradient": {"n": 1},
}
METHODS = tuple(DEFAULTS)
_EVEN_ONLY = ("savgol", "gaussian")                 # methods that need evenly spaced points
# Settings used when left as None, per (method, n): the best in docs/benchmarks.md.
_AUTO = {("savgol", 1): {"window": 15, "order": 5}, ("savgol", 2): {"window": 11, "order": 4},
         ("gaussian", 1): {"sigma": 1.25}, ("gaussian", 2): {"sigma": 1.5}}


def _uneven(x: np.ndarray) -> bool:
    """True if the spacing between points varies by more than 1 %."""
    dx = np.diff(x)
    return bool(np.ptp(dx) > 0.01 * abs(np.mean(dx)))


def _on_even_grid(x: np.ndarray, y: np.ndarray, method: str, s: dict) -> np.ndarray:
    """Differentiate y (x ascending, evenly spaced) with savgol or gaussian."""
    n, step = s["n"], x[1] - x[0]
    if method == "savgol":
        w = min(int(s["window"]) | 1, y.size if y.size % 2 else y.size - 1)   # odd, not longer than the data
        if not n <= s["order"] < w:
            raise ValueError(f"savgol needs n ({n}) <= order ({s['order']}) < window ({w}).")
        # deriv=n differentiates the fitted polynomial; delta=step makes it per x unit.
        return savgol_filter(y, w, s["order"], deriv=n, delta=step, mode="interp")
    # gaussian: order=n convolves with the n-th derivative of the Gaussian (per point), / step^n per x unit
    return gaussian_filter1d(y, s["sigma"], order=n, mode="nearest") / step ** n


def _one(x: np.ndarray, y: np.ndarray, method: str, s: dict, regrid: bool) -> np.ndarray:
    """Differentiate one spectrum (x ascending)."""
    if method in _EVEN_ONLY:
        if not regrid:
            return _on_even_grid(x, y, method, s)
        xe = np.linspace(x[0], x[-1], x.size)                     # even grid, same number of points
        return np.interp(x, xe, _on_even_grid(xe, np.interp(xe, x, y), method, s))
    if method == "spline":
        from scipy.interpolate import make_smoothing_spline
        return make_smoothing_spline(x, y, lam=s["lam"]).derivative(s["n"])(x)
    d = np.gradient(y, x)                                         # gradient: central differences on real x
    return np.gradient(d, x) if s["n"] == 2 else d


def _settings(method: str, given: dict) -> dict:
    """Defaults of the method overridden by what was given; unknown names are an error."""
    if method not in DEFAULTS:
        raise ValueError(f"Unknown derivative method {method!r}. Choose one of: {', '.join(METHODS)}.")
    wrong = set(given) - set(DEFAULTS[method])
    if wrong:
        raise ValueError(f"{method!r} has no setting {sorted(wrong)}. Its settings and defaults: {DEFAULTS[method]}.")
    s = {**DEFAULTS[method], **given}
    if s["n"] not in (1, 2):
        raise ValueError("n must be 1 (first derivative) or 2 (second derivative).")
    for key, value in _AUTO.get((method, s["n"]), {}).items():
        if s[key] is None:                                        # not given: use the tuned value for this n
            s[key] = value
    return s


def derivative(data: Data, method: str = "savgol", **settings: Any) -> Data:
    """First (n=1) or second (n=2) derivative of a spectrum or of every
    spectrum of a collection.

    Parameters
    ----------
    method : one of ``METHODS``; default "savgol".
    **settings : n (1 or 2) and that method's settings; see ``DEFAULTS[method]``.

    Returns new data with y in units of y per x (per x² for n=2); the step
    and its settings are recorded in history.
    """
    s = _settings(method, settings)
    if data.x.size < 5:
        raise ValueError("A derivative needs at least 5 points.")
    order = np.argsort(data.x, kind="stable")                    # all methods expect ascending x
    undo = np.argsort(order)
    x = data.x[order]
    from .core import require_distinct_x
    require_distinct_x(x, "derivative")                           # slopes divide by the x spacing
    regrid = method in _EVEN_ONLY and _uneven(x)
    entry = {"step": "derivative", "method": method, **s, **({"regridded": True} if regrid else {})}
    label = data.y_unit or "y"
    unit = f"d{'²' if s['n'] == 2 else ''}({label})/d({data.x_unit or 'x'}){'²' if s['n'] == 2 else ''}"
    if isinstance(data, Spectrum):
        y = _one(x, data.y[order], method, s, regrid)[undo]
        return data.copy_with(y=y, y_unit=unit, history=data.history + (entry,))
    Y = np.vstack([_one(x, row[order], method, s, regrid)[undo] for row in data.Y])
    return data.copy_with(Y=Y, y_unit=unit, history=data.history + (entry,))


__all__ = ["derivative", "METHODS", "DEFAULTS"]
