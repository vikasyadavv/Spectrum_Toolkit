"""Normalisation: remove intensity differences that do not come from the
sample (laser power, focus, integration time, scattering, path length), so
spectra can be compared.

``s.normalize(method, **settings)``. Methods that compute one factor per
spectrum accept ``region=(lo, hi)``: the factor is computed from that x
range only (e.g. a band that should not change) and applied to the whole
spectrum.

One spectrum at a time
----------------------
"max"      divide by the maximum (or the maximum in ``region``). Simple; one
           noisy point or a spike decides the scale.
"minmax"   rescale to 0..1.
"area"     divide by the area under the curve (trapezoid rule over x).
"vector"   divide by the vector (L2) norm, so sum(y²) = 1.
"snv"      standard normal variate (Barnes et al. 1989): subtract the mean,
           divide by the standard deviation. Removes offset and scale.
"rsnv"     robust SNV: median and MAD instead of mean and standard
           deviation, so a few very tall bands or spikes do not dominate.
"band"     divide by one band's ``measure`` ("height" above a straight line
           under it, or "area"), the band given by ``region``. The
           internal-standard method: use a band that should be the same in
           every spectrum.

Several spectra together (collections; a single spectrum needs ``reference``)
-------------------------------------------------------------------------
"msc"      multiplicative scatter correction (Geladi et al. 1985): fit each
           spectrum as a + b × reference, then (y - a) / b. Reference: the
           mean spectrum unless given.
"emsc"     extended MSC (Martens & Stark 1991): as MSC plus a polynomial of
           ``order`` in x, so a sloping or curved background is removed too.
"pqn"      probabilistic quotient normalisation (Dieterle et al. 2006): area
           normalisation, then each spectrum is divided by the median of its
           point-by-point ratios to the reference (median spectrum). Robust
           when some bands really change between spectra.

How they compare is in docs/benchmarks.md.

References
----------
Barnes, R. J., Dhanoa, M. S. & Lister, S. J. (1989). Standard normal variate transformation and de-trending of near-infrared diffuse reflectance spectra. Appl. Spectrosc. 43, 772.
Geladi, P., MacDougall, D. & Martens, H. (1985). Linearization and scatter-correction for near-infrared reflectance spectra of meat. Appl. Spectrosc. 39, 491.
Martens, H. & Stark, E. (1991). Extended multiplicative signal correction and spectral interference subtraction. J. Pharm. Biomed. Anal. 9, 625.
Dieterle, F. et al. (2006). Probabilistic quotient normalization as robust method to account for dilution of complex biological mixtures. Anal. Chem. 78, 4281.

>>> from spectrum_toolkit import Spectrum
>>> Spectrum([1, 2, 3], [2, 4, 8]).normalize("max").y
array([0.25, 0.5 , 1.  ])
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .core import Spectrum, SpectrumCollection

Data = Spectrum | SpectrumCollection

DEFAULTS: dict[str, dict[str, Any]] = {
    "max": {"region": None},
    "minmax": {"region": None},
    "area": {"region": None},
    "vector": {"region": None},
    "snv": {"region": None},
    "rsnv": {"region": None},
    "band": {"region": None, "measure": "height"},
    "msc": {"reference": None},
    "emsc": {"reference": None, "order": 2},
    "pqn": {"reference": None},
}
METHODS = tuple(DEFAULTS)
_TOGETHER = ("msc", "emsc", "pqn")                 # methods that need a reference spectrum


def _mask(x: np.ndarray, region) -> np.ndarray:
    """True for the points inside region=(lo, hi); everything if region is None."""
    if region is None:
        return np.ones(x.size, bool)
    lo, hi = sorted(region)
    m = (x >= lo) & (x <= hi)
    if m.sum() < 2:
        raise ValueError(f"region {region} holds fewer than 2 points; x runs from {x.min():.6g} to {x.max():.6g}.")
    return m


def _area(x: np.ndarray, y: np.ndarray) -> float:
    """Area under y over x by the trapezoid rule (x may run either way)."""
    order = np.argsort(x)
    return float(np.trapezoid(y[order], x[order]))


def _safe(value: float, what: str) -> float:
    """Refuse to divide by zero (e.g. a flat spectrum has no standard deviation)."""
    if not np.isfinite(value) or abs(value) < 1e-300:
        raise ValueError(f"Cannot normalise: the {what} is zero.")
    return value


def _one(x: np.ndarray, y: np.ndarray, method: str, s: dict) -> np.ndarray:
    """Normalise one spectrum with a one-spectrum method."""
    m = _mask(x, s["region"])
    ym = y[m]
    if method == "max":
        return y / _safe(ym.max(), "maximum")
    if method == "minmax":
        return (y - ym.min()) / _safe(ym.max() - ym.min(), "range (max - min)")
    if method == "area":
        return y / _safe(_area(x[m], ym), "area")
    if method == "vector":
        return y / _safe(np.linalg.norm(ym), "vector norm")
    if method == "snv":
        return (y - ym.mean()) / _safe(ym.std(), "standard deviation")
    if method == "rsnv":
        med = np.median(ym)
        return (y - med) / _safe(1.4826 * np.median(np.abs(ym - med)), "median absolute deviation")
    # band: height above, or area above, a straight line joining the band's ends
    if s["region"] is None:
        raise ValueError('method "band" needs region=(lo, hi), the x range of the band to normalise to.')
    xb = x[m]
    order = np.argsort(xb)
    xb, yb = xb[order], ym[order]
    under = np.interp(xb, [xb[0], xb[-1]], [yb[0], yb[-1]])      # local baseline under the band
    above = yb - under
    if above.max() <= 0:
        raise ValueError(f"No band in region {s['region']}: nothing rises above the straight line joining "
                         "the region's ends. Choose a region that holds one whole band with some baseline on "
                         "both sides.")
    if s["measure"] == "height":
        return y / _safe(above.max(), "band height")
    if s["measure"] == "area":
        return y / _safe(np.trapezoid(above, xb), "band area")
    raise ValueError('measure must be "height" or "area".')


def _together(x: np.ndarray, Y: np.ndarray, method: str, s: dict, ref: np.ndarray) -> np.ndarray:
    """Normalise every row of Y against the reference spectrum ref."""
    if method == "pqn":
        # 1. area normalisation, 2. median of the point-by-point quotients to the reference.
        areas = np.array([_safe(_area(x, row), "area") for row in Y])
        Ya = Y / areas[:, None]
        ra = ref / _safe(_area(x, ref), "area of the reference")
        use = np.abs(ra) > 0.05 * np.abs(ra).max()               # skip near-zero points: their ratios are noise
        q = np.median(Ya[:, use] / ra[use], axis=1)
        return Ya / q[:, None]
    # msc / emsc: least-squares fit y = a + b·ref (+ c1·t + c2·t² ...), then (y - a - poly) / b
    t = (x - x.mean()) / (np.ptp(x) / 2)                         # x scaled to -1..1 for a stable fit
    cols = [np.ones_like(x), ref] + ([t ** k for k in range(1, s["order"] + 1)] if method == "emsc" else [])
    A = np.column_stack(cols)
    coef, *_ = np.linalg.lstsq(A, Y.T, rcond=None)              # one column of coefficients per spectrum
    background = A[:, [0] + list(range(2, A.shape[1]))] @ coef[[0] + list(range(2, A.shape[1]))]
    b = coef[1]
    if np.any(np.abs(b) < 1e-12):
        raise ValueError("A spectrum does not resemble the reference at all (scale ≈ 0); MSC cannot correct it.")
    return (Y - background.T) / b[:, None]


def _settings(method: str, given: dict) -> dict:
    """Defaults of the method overridden by what was given; unknown names are an error."""
    if method not in DEFAULTS:
        raise ValueError(f"Unknown normalisation method {method!r}. Choose one of: {', '.join(METHODS)}.")
    wrong = set(given) - set(DEFAULTS[method])
    if wrong:
        raise ValueError(f"{method!r} has no setting {sorted(wrong)}. Its settings and defaults: {DEFAULTS[method]}.")
    return {**DEFAULTS[method], **given}


def normalize(data: Data, method: str = "snv", **settings: Any) -> Data:
    """Normalise a spectrum or every spectrum of a collection.

    Parameters
    ----------
    method : one of ``METHODS``; default "snv".
    **settings : that method's settings; see ``DEFAULTS[method]``.
        region=(lo, hi) : compute the factor from this x range only.
        reference : for msc/emsc/pqn, a Spectrum or array on the same x;
            default the mean (msc, emsc) or median (pqn) of the collection.

    Returns new data; the step is recorded in history (a reference spectrum
    is recorded as "given", not copied).
    """
    s = _settings(method, settings)
    single = isinstance(data, Spectrum)
    Y = data.y[None, :] if single else data.Y
    x = data.x
    if method in _TOGETHER:
        ref = s["reference"]
        if ref is None:
            if single or len(Y) < 2:
                raise ValueError(f"{method!r} compares spectra with a reference; give reference=... "
                                 "for a single spectrum, or use a collection.")
            ref = np.median(Y, axis=0) if method == "pqn" else Y.mean(axis=0)
        else:
            ref = np.asarray(ref.y if isinstance(ref, Spectrum) else ref, dtype=float)
            if ref.shape != x.shape:
                raise ValueError(f"reference has {ref.size} points, the data {x.size}; resample it first.")
        out = _together(x, Y, method, s, ref)
    else:
        out = np.vstack([_one(x, row, method, s) for row in Y])
    record = {k: ("given" if k == "reference" and v is not None else v) for k, v in s.items()}
    entry = {"step": "normalize", "method": method, **record}
    if single:
        return data.copy_with(y=out[0], history=data.history + (entry,))
    return data.copy_with(Y=out, history=data.history + (entry,))


__all__ = ["normalize", "METHODS", "DEFAULTS"]
