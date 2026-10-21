"""Smoothing: reduce noise while keeping the shape of the bands.

Every smoother trades noise against band shape: smoothing more removes more
noise but makes narrow bands lower and wider. The settings control that
trade. Windows are in POINTS (at 1.19 cm-1 per point, 15 points ≈ 18 cm-1);
a band should span clearly more points than the window.

Methods
-------
"savgol"     Savitzky-Golay (1964): fits a polynomial of ``order`` in a
             moving ``window`` and keeps its centre value. Keeps band height
             and width best for a given amount of smoothing; the standard
             choice in spectroscopy. Default window 15, order 4 (best of
             the windows/orders tried in our comparison).
"whittaker"  Whittaker smoother (Eilers 2003): the smoothest curve that stays
             close to the data, stiffness ``lam``. No window, handles the
             ends well.
"spline"     Smoothing spline (scipy make_smoothing_spline). With ``lam``
             None (default) the amount of smoothing is chosen automatically
             by generalised cross-validation.
"gaussian"   Gaussian-weighted moving average, width ``sigma`` (points).
"moving"     Plain moving average over ``window`` points. Simple, but lowers
             and widens bands the most.
"median"     Moving median over ``window`` points. Removes isolated outliers
             but flattens band tops; better used for spikes (see despike).
"fourier"    Removes high frequencies above ``cutoff`` (fraction of the
             highest frequency, 0-1) with a smooth roll-off.

How they compare on simulated spectra is in docs/benchmarks.md (rerun: benchmarks/run_all.py).

References
----------
Savitzky, A. & Golay, M. J. E. (1964). Smoothing and differentiation of data by simplified least squares procedures. Anal. Chem. 36, 1627.
Eilers, P. H. C. (2003). A perfect smoother. Anal. Chem. 75, 3631.
Craven, P. & Wahba, G. (1979). Smoothing noisy data with spline functions. Numer. Math. 31, 377 (choosing the amount of smoothing by GCV).

>>> import numpy as np
>>> from spectrum_toolkit import Spectrum
>>> x = np.arange(200.0)
>>> rng = np.random.default_rng(0)
>>> s = Spectrum(x, 1000 * np.exp(-((x - 100) / 10) ** 2) + rng.normal(0, 30, 200))
>>> bool(np.std(s.smooth().y - s.y) > 15)                      # noise reduced
True
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.ndimage import gaussian_filter1d, median_filter, uniform_filter1d
from scipy.signal import savgol_filter

from .baseline import _penalty_bands, _solve
from .core import Spectrum, SpectrumCollection

Data = Spectrum | SpectrumCollection

DEFAULTS: dict[str, dict[str, Any]] = {
    "savgol": {"window": 15, "order": 4},
    "whittaker": {"lam": 3.0},
    "spline": {"lam": None},
    "gaussian": {"sigma": 1.0},
    "moving": {"window": 5},
    "median": {"window": 5},
    "fourier": {"cutoff": 0.25},
}
METHODS = tuple(DEFAULTS)


def _odd(window: int, n: int) -> int:
    """A window must be odd (a centre point) and not longer than the data."""
    window = int(window) | 1                         # 10 -> 11, 11 -> 11
    return min(window, n if n % 2 else n - 1)


def _one(y: np.ndarray, x: np.ndarray, method: str, s: dict) -> np.ndarray:
    """Smooth one spectrum (x ascending)."""
    if method == "savgol":
        w = _odd(s["window"], y.size)
        if s["order"] >= w:
            raise ValueError(f"savgol order ({s['order']}) must be smaller than the window ({w}).")
        # mode="interp": near the ends, the polynomial fitted to the first/last
        # window is used, instead of padding the data with invented values.
        return savgol_filter(y, w, s["order"], mode="interp")
    if method == "whittaker":
        return _solve(_penalty_bands(y.size, s["lam"]), np.ones(y.size), y)
    if method == "spline":
        from scipy.interpolate import make_smoothing_spline
        return make_smoothing_spline(x, y, lam=s["lam"])(x)
    if method == "gaussian":
        return gaussian_filter1d(y, s["sigma"], mode="nearest")
    if method == "moving":
        return uniform_filter1d(y, _odd(s["window"], y.size), mode="nearest")
    if method == "median":
        return median_filter(y, size=_odd(s["window"], y.size), mode="nearest")
    # fourier: remove a straight line first so the ends meet (no ringing), filter, add it back
    if not 0 < s["cutoff"] <= 1:
        raise ValueError("fourier cutoff must be between 0 and 1 (fraction of the highest frequency).")
    line = np.linspace(y[0], y[-1], y.size)
    spec = np.fft.rfft(y - line)
    f = np.linspace(0, 1, spec.size)                 # 0 = constant, 1 = highest frequency
    spec *= 1 / (1 + (f / s["cutoff"]) ** 8)          # smooth roll-off (Butterworth-like), no sharp edge
    return np.fft.irfft(spec, n=y.size) + line


def _settings(method: str, given: dict) -> dict:
    """Defaults of the method overridden by what was given; unknown names are an error."""
    if method not in DEFAULTS:
        raise ValueError(f"Unknown smoothing method {method!r}. Choose one of: {', '.join(METHODS)}.")
    wrong = set(given) - set(DEFAULTS[method])
    if wrong:
        raise ValueError(f"{method!r} has no setting {sorted(wrong)}. Its settings and defaults: {DEFAULTS[method]}.")
    return {**DEFAULTS[method], **given}


def smooth(data: Data, method: str = "savgol", **settings: Any) -> Data:
    """Smooth a spectrum or every spectrum of a collection.

    Parameters
    ----------
    method : one of ``METHODS``; default "savgol".
    **settings : that method's settings; see ``DEFAULTS[method]``.

    Returns new data; the step and its settings are recorded in history.
    """
    s = _settings(method, settings)
    order = np.argsort(data.x, kind="stable")       # all methods expect ascending x
    undo = np.argsort(order)
    x = data.x[order]
    entry = {"step": "smooth", "method": method, **s}
    if isinstance(data, Spectrum):
        y = _one(data.y[order], x, method, s)[undo]
        return data.copy_with(y=y, history=data.history + (entry,))
    Y = np.vstack([_one(row[order], x, method, s)[undo] for row in data.Y])
    return data.copy_with(Y=Y, history=data.history + (entry,))


__all__ = ["smooth", "METHODS", "DEFAULTS"]
