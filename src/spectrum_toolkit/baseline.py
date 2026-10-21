"""Baseline correction: estimate the slowly varying background (fluorescence,
detector offset, glass) under the bands and subtract it.

``s.baseline(method, **settings)`` returns the corrected data;
``find_baseline(s, method, **settings)`` returns the baseline itself, so it
can be plotted over the original.

Methods
-------
Whittaker-smoother family: the baseline z balances "close to the data"
against "smooth", with weights w that ignore points on bands. ``lam``
sets the smoothness: larger = stiffer baseline. Rule of thumb: make it
large enough that the baseline cannot follow your widest band.

    "asls"    Asymmetric least squares (Eilers & Boelens 2005). Your
              baseline.m. Points above the baseline get weight ``p``,
              points below get 1 - p.
    "iasls"   Improved AsLS (He et al. 2014): adds a first-derivative
              penalty, fits curved baselines better.
    "arpls"   Asymmetrically reweighted PLS (Baek et al. 2015). Weights come
              from the noise level of points below the baseline, so no ``p``
              to tune; less biased under noise than AsLS.
    "airpls"  Adaptive iteratively reweighted PLS (Zhang et al. 2010).
              Weights grow for points that stay below the baseline.

Polynomial family: a polynomial is fitted, then the data are clipped to it
so bands stop pulling it up, and repeated.

    "modpoly"   Modified polynomial (Lieber & Mahadevan-Jansen 2003).
    "imodpoly"  Improved ModPoly (Zhao et al. 2007): clips at fit + noise,
                better with noisy data.

Window (morphological) family: ``window`` is in x units (e.g. cm-1) and
must be wider than the widest band.

    "rollingball"  Morphological opening (erosion then dilation), then
                   smoothed; like rolling a ball under the spectrum.
    "snip"         Statistics-sensitive non-linear iterative peak clipping
                   (Ryan et al. 1988; Morháč et al. 1997), on a
                   log-log-sqrt scale to handle large intensity ranges.

How they compare on simulated spectra is in docs/roadmap.md (feature 4).

References
----------
Eilers, P. H. C. & Boelens, H. F. M. (2005). Baseline correction with asymmetric least squares smoothing.
He, S. et al. (2014). Baseline correction for Raman spectra using an improved asymmetric least squares method. Anal. Methods 6, 4402.
Baek, S.-J. et al. (2015). Baseline correction using asymmetrically reweighted penalized least squares smoothing. Analyst 140, 250.
Zhang, Z.-M., Chen, S. & Liang, Y.-Z. (2010). Baseline correction using adaptive iteratively reweighted penalized least squares. Analyst 135, 1138.
Lieber, C. A. & Mahadevan-Jansen, A. (2003). Automated method for subtraction of fluorescence from biological Raman spectra. Appl. Spectrosc. 57, 1363.
Zhao, J. et al. (2007). Automated autofluorescence background subtraction algorithm for biomedical Raman spectroscopy. Appl. Spectrosc. 61, 1225.
Ryan, C. G. et al. (1988). SNIP, a statistics-sensitive background treatment for the quantitative analysis of PIXE spectra. NIM B 34, 396.
Morháč, M. et al. (1997). Background elimination methods for multidimensional coincidence γ-ray spectra. NIM A 401, 113.

>>> import numpy as np
>>> from spectrum_toolkit import Spectrum
>>> x = np.linspace(0, 1000, 1001)
>>> background = 500 + 0.5 * x                                 # a sloping background
>>> s = Spectrum(x, background + 1000 * np.exp(-((x - 500) / 10) ** 2))
>>> c = s.baseline()
>>> bool(abs(c.y[100]) < 5), bool(abs(c.y[500] - 1000) < 5)               # background gone, band kept
(True, True)
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.linalg import solveh_banded
from scipy.ndimage import grey_closing, grey_opening, uniform_filter1d

from .core import Spectrum, SpectrumCollection

Data = Spectrum | SpectrumCollection

# Default settings of every method, shown in errors and stored in history.
DEFAULTS: dict[str, dict[str, Any]] = {
    "asls": {"lam": 1e5, "p": 0.005, "max_iter": 10, "tol": 0.0},     # as baseline.m: always 10 rounds
    "iasls": {"lam": 1e4, "p": 0.005, "lam1": 1e-4, "max_iter": 30, "tol": 1e-3},
    "arpls": {"lam": 1e6, "max_iter": 50, "tol": 1e-3},
    "airpls": {"lam": 1e6, "max_iter": 50, "tol": 1e-3},
    "modpoly": {"order": 5, "max_iter": 250, "tol": 1e-3},
    "imodpoly": {"order": 5, "max_iter": 250, "tol": 1e-3, "num_std": 1.0},
    "rollingball": {"window": 100.0, "smooth": None},
    "snip": {"window": 100.0, "decreasing": True},
}
METHODS = tuple(DEFAULTS)


# ---------------------------------------------------------- Whittaker family
def _penalty_bands(n: int, lam: float, lam1: float = 0.0) -> np.ndarray:
    """lam·D2ᵀD2 (+ lam1·D1ᵀD1) as the upper bands of a symmetric banded matrix.

    D2 is the second-difference matrix (curvature). Stored in the "upper
    form" scipy.linalg.solveh_banded expects: row 2 = main diagonal, row 1 =
    first super-diagonal, row 0 = second super-diagonal. Solving a banded
    system takes time proportional to n, so 100,000 points are fine.
    """
    ab = np.zeros((3, n))
    # Diagonals of D2ᵀD2: main 1,5,6,...,6,5,1; first off -2,-4,...,-4,-2; second off 1.
    main = np.full(n, 6.0); main[[0, -1]] = 1; main[[1, -2]] = 5
    off1 = np.full(n - 1, -4.0); off1[[0, -1]] = -2
    ab[2] = lam * main
    ab[1, 1:] = lam * off1
    ab[0, 2:] = lam
    if lam1:
        # D1ᵀD1: main 1,2,...,2,1; first off -1.
        m1 = np.full(n, 2.0); m1[[0, -1]] = 1
        ab[2] += lam1 * m1
        ab[1, 1:] += -lam1
    return ab


def _solve(ab: np.ndarray, w: np.ndarray, rhs: np.ndarray) -> np.ndarray:
    """Solve (W + penalty) z = rhs, where W is diagonal with weights w."""
    a = ab.copy()
    a[2] += w                                       # add the weights to the main diagonal
    return solveh_banded(a, rhs, check_finite=False)


def _asls(y, lam, p, max_iter, tol):
    ab = _penalty_bands(y.size, lam)
    w = np.ones(y.size)
    for _ in range(max_iter):
        z = _solve(ab, w, w * y)
        new = np.where(y > z, p, 1 - p)              # above the baseline: small weight
        if np.mean(np.abs(new - w)) < tol:            # weights stopped changing
            break
        w = new
    return z


def _iasls(y, lam, p, lam1, max_iter, tol):
    # He et al. 2014: start from a polynomial fit, then AsLS with an extra
    # first-difference penalty on the residual (y - z).
    x = np.linspace(-1, 1, y.size)
    w = np.where(y > np.polyval(np.polyfit(x, y, 2), x), p, 1 - p)
    ab = _penalty_bands(y.size, lam)
    a1 = _penalty_bands(y.size, 0.0, lam1)          # lam1·D1ᵀD1 only
    # (WᵀW + lam1 D1ᵀD1 + lam D2ᵀD2) z = (WᵀW + lam1 D1ᵀD1) y
    d1y = np.zeros_like(y)                          # lam1·D1ᵀD1·y, computed directly
    d1y[1:-1] = lam1 * (2 * y[1:-1] - y[:-2] - y[2:])
    d1y[0], d1y[-1] = lam1 * (y[0] - y[1]), lam1 * (y[-1] - y[-2])
    for _ in range(max_iter):
        a = ab.copy(); a[2] += w ** 2 + a1[2]; a[1] += a1[1]
        z = solveh_banded(a, w ** 2 * y + d1y, check_finite=False)
        new = np.where(y > z, p, 1 - p)
        if np.mean(np.abs(new - w)) < tol:
            break
        w = new
    return z


def _arpls(y, lam, max_iter, tol):
    ab = _penalty_bands(y.size, lam)
    w = np.ones(y.size)
    for _ in range(max_iter):
        z = _solve(ab, w, w * y)
        d = y - z
        neg = d[d < 0]                               # points below the baseline = noise only
        if neg.size < 2:
            break
        m, s = neg.mean(), neg.std()
        # Logistic weight: ~1 for points within the noise, ~0 well above it.
        with np.errstate(over="ignore"):
            new = 1 / (1 + np.exp(np.clip(2 * (d - (2 * s - m)) / s, -500, 500)))
        if np.linalg.norm(w - new) / np.linalg.norm(w) < tol:
            break
        w = new
    return z


def _airpls(y, lam, max_iter, tol):
    ab = _penalty_bands(y.size, lam)
    w = np.ones(y.size)
    total = np.abs(y).sum()
    for t in range(1, max_iter + 1):
        z = _solve(ab, w, w * y)
        d = y - z
        neg = d[d < 0]
        if neg.size == 0 or np.abs(neg).sum() < tol * total:
            break
        # Points above the baseline get weight 0; below, weight grows with
        # how far below and with the iteration number t.
        w = np.where(d >= 0, 0.0, np.exp(np.clip(t * np.abs(d) / np.abs(neg).sum(), None, 50)))
        w[[0, -1]] = np.exp(np.clip(t * np.abs(neg).max() / np.abs(neg).sum(), None, 50))   # anchor the ends
    return z


# --------------------------------------------------------- polynomial family
def _modpoly(y, x, order, max_iter, tol, num_std=None):
    xs = (x - x.mean()) / (np.ptp(x) / 2)            # scale x to -1..1: stable fits
    work = y.copy()
    fit = np.polyval(np.polyfit(xs, work, order), xs)
    dev = None
    for _ in range(max_iter):
        if num_std is not None:                        # IModPoly: clip at fit + noise
            new_dev = np.std(work - fit)
            work = np.minimum(work, fit + num_std * new_dev)
            if dev is not None and abs(new_dev - dev) / max(dev, 1e-12) < tol:
                break
            dev = new_dev
        else:
            work = np.minimum(work, fit)               # ModPoly: clip at the fit
        new = np.polyval(np.polyfit(xs, work, order), xs)
        if np.linalg.norm(new - fit) / max(np.linalg.norm(fit), 1e-12) < tol:
            fit = new
            break
        fit = new
    return fit


# ------------------------------------------------------------- window family
def _points(window: float, x: np.ndarray) -> int:
    """A window in x units (e.g. 100 cm-1) as a number of points (at least 3)."""
    return max(3, int(round(window / np.median(np.abs(np.diff(x))))))


def _rollingball(y, x, window, smooth):
    k = _points(window, x)
    # Opening = erosion (running minimum) then dilation (running maximum):
    # removes every feature narrower than k points, keeping the background.
    z = grey_opening(y, size=k, mode="nearest")
    # The opening is blocky; a running mean of half the window smooths it.
    ks = _points(smooth, x) if smooth else max(3, k // 2)
    return np.minimum(uniform_filter1d(z, ks, mode="nearest"), y)


def _snip(y, x, window, decreasing):
    k = _points(window, x) // 2                     # half-width in points
    offset = y.min()
    # Log-log-sqrt transform compresses tall bands so small ones are clipped too.
    v = np.log(np.log(np.sqrt(y - offset + 1) + 1) + 1)
    widths = range(k, 0, -1) if decreasing else range(1, k + 1)
    n = v.size
    for m in widths:
        if 2 * m >= n:
            continue
        avg = np.empty_like(v)
        avg[m:n - m] = (v[:n - 2 * m] + v[2 * m:]) / 2   # mean of points m to the left and right
        avg[:m], avg[n - m:] = v[:m], v[n - m:]
        v = np.minimum(v, avg)                       # clip anything above that mean
    return (np.exp(np.exp(v) - 1) - 1) ** 2 - 1 + offset


# ------------------------------------------------------------------- public
def _one(y: np.ndarray, x: np.ndarray, method: str, s: dict) -> np.ndarray:
    """Baseline of one spectrum (x ascending)."""
    if method == "asls":
        return _asls(y, s["lam"], s["p"], s["max_iter"], s["tol"])
    if method == "iasls":
        return _iasls(y, s["lam"], s["p"], s["lam1"], s["max_iter"], s["tol"])
    if method == "arpls":
        return _arpls(y, s["lam"], s["max_iter"], s["tol"])
    if method == "airpls":
        return _airpls(y, s["lam"], s["max_iter"], s["tol"])
    if method == "modpoly":
        return _modpoly(y, x, s["order"], s["max_iter"], s["tol"])
    if method == "imodpoly":
        return _modpoly(y, x, s["order"], s["max_iter"], s["tol"], s["num_std"])
    if method == "rollingball":
        return _rollingball(y, x, s["window"], s["smooth"])
    return _snip(y, x, s["window"], s["decreasing"])


def _settings(method: str, given: dict) -> dict:
    """The defaults of a method, overridden by what was given; unknown names are an error."""
    if method not in DEFAULTS:
        raise ValueError(f"Unknown baseline method {method!r}. Choose one of: {', '.join(METHODS)}.")
    wrong = set(given) - set(DEFAULTS[method])
    if wrong:
        raise ValueError(f"{method!r} has no setting {sorted(wrong)}. Its settings and defaults: {DEFAULTS[method]}.")
    return {**DEFAULTS[method], **given}


def find_baseline(data: Data, method: str = "airpls", **settings: Any) -> Data:
    """The estimated baseline, as the same kind of object as ``data``.

    Parameters
    ----------
    method : one of ``METHODS``; default "airpls" (the most accurate with
        default settings in our comparison, docs/roadmap.md feature 4).
    **settings : that method's settings; see ``DEFAULTS[method]``.
    """
    s = _settings(method, settings)
    order = np.argsort(data.x, kind="stable")       # all methods expect ascending x
    undo = np.argsort(order)
    x = data.x[order]
    if isinstance(data, Spectrum):
        z = _one(data.y[order], x, method, s)[undo]
        return data.copy_with(y=z, name=f"{data.name} baseline".strip())
    Z = np.vstack([_one(row[order], x, method, s)[undo] for row in data.Y])
    return data.copy_with(Y=Z, names=tuple(f"{n} baseline" for n in data.names))


def baseline(data: Data, method: str = "airpls", **settings: Any) -> Data:
    """Subtract the baseline. Returns new data; the step is recorded in history.

    >>> import numpy as np
    >>> from spectrum_toolkit import Spectrum
    >>> s = Spectrum(np.arange(100.0), np.full(100, 50.0))
    >>> float(s.baseline("modpoly", order=1).y.max()) < 1e-6
    True
    """
    s = _settings(method, settings)
    z = find_baseline(data, method, **settings)
    entry = {"step": "baseline", "method": method, **s}
    if isinstance(data, Spectrum):
        return data.copy_with(y=data.y - z.y, history=data.history + (entry,))
    return data.copy_with(Y=data.Y - z.Y, history=data.history + (entry,))


__all__ = ["baseline", "find_baseline", "METHODS", "DEFAULTS"]
