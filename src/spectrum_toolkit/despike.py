"""Cosmic-ray (spike) removal.

A cosmic ray hitting the detector adds a very narrow, very tall feature,
usually 1 to 3 points wide (sometimes a jagged group of up to ~10). Real
Raman bands are several points wide and smooth. Three methods are offered:

"single" (default) — each spectrum on its own
    1. Noise is made equal everywhere with the Anscombe transform
       (2·sqrt(y + 3/8)): photon-counting noise grows with the signal, so
       without this a tall band looks "noisier" than the baseline.
    2. A point is a spike candidate when it is far above a running median
       (``threshold`` × noise), its curvature is far above the noise, and it
       is sharp for its height: curvature / height above the running
       median > ``sharpness``. A real band several points wide has a small
       curvature for its height; a 1-3 point spike has a large one
       (≈ 2 for a single point). This shape test is what keeps real bands
       safe.
    3. Around each candidate, a quadratic is fitted through the neighbours
       outside ±``width`` points. Points above that curve by more than
       ``grow`` × noise belong to the spike.
    4. The spike points are replaced by the quadratic, which follows the
       slope or curvature underneath (a spike on a band's flank is repaired
       along the flank, not flattened).
    Steps 2-4 run ``passes`` times, so a spike hidden next to a bigger one
    is found on the second pass.

"compare" — collections of repeated measurements of one sample
    Each spectrum is compared with the median of the others, scaled to it.
    Points above that by more than ``threshold`` × noise (from the spread
    among the repeats and photon noise), in runs no wider than 4 × ``width``
    points, are spikes and are replaced by the scaled median. Catches broad
    cosmic rays that the shape test may miss, but only makes sense when the
    spectra really are repeats (not different samples).

"kalkan" — the MATLAB function spikeRemoval.m (E. Kalkan, rev. 2.1.0, 2019)
    Ported line by line for comparison. It was written for time series:
    candidates from a histogram of the first derivative, then each checked
    against mean ± ``nstd`` standard deviations of a ``window``-point
    neighbourhood, and replaced by linear interpolation of ``ndata``
    neighbours each side. Note: like the original, it always replaces
    candidates within 2 × ``ndata`` points of either end.

How they compare (docs/roadmap.md, feature 3): on 200 simulated Raman
spectra, "single" repaired 94 % of strong spikes with almost no false
alarms; "kalkan" repaired 61 % and changed points in 8 % of clean spectra.
On the real data, "single" and "compare" find exactly the three cosmic rays
in CV10-4M.xlsx (spectra 3 and 10) and nothing in RhB, MB or the 550-spectrum
map.

References
----------
Whitaker, D. A. & Hayes, K. (2018). A simple algorithm for despiking Raman
spectra. Chemometrics and Intelligent Laboratory Systems 179, 82-84.
(Robust z-scores of point-to-point changes; the idea behind step 2.)
Anscombe, F. J. (1948). The transformation of Poisson, binomial and
negative-binomial data. Biometrika 35, 246-254.

>>> import numpy as np
>>> from spectrum_toolkit import Spectrum
>>> x = np.arange(200.0)
>>> y = 1000 + 500 * np.exp(-((x - 100) / 8) ** 2)    # one smooth band
>>> y[50] += 3000                                      # one cosmic ray
>>> clean = despike(Spectrum(x, y), verbose=False)
>>> round(clean.y[50]), round(clean.y[100])            # spike gone, band kept
(1000, 1500)
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import median_filter

from .core import Spectrum, SpectrumCollection

Data = Spectrum | SpectrumCollection
METHODS = ("single", "compare", "kalkan")


# ------------------------------------------------------------------ helpers
def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """(start, stop) of every run of True values: [F,T,T,F,T] -> [(1,3), (4,5)]."""
    edges = np.diff(np.r_[0, mask.astype(int), 0])       # +1 where a run starts, -1 after it ends
    return list(zip(np.where(edges == 1)[0], np.where(edges == -1)[0]))


def _quadratic_fill(y: np.ndarray, bad: np.ndarray, n_fit: int = 5) -> np.ndarray:
    """Replace each run of bad points by a quadratic through n_fit good points on each side.

    At the ends of the spectrum, where one side is missing, a straight line
    through the good points on the other side is used.
    """
    out = y.copy()
    idx = np.arange(y.size)
    for start, stop in _runs(bad):
        left = idx[:start][~bad[:start]][-n_fit:]           # nearest good points to the left
        right = idx[stop:][~bad[stop:]][:n_fit]             # ... and to the right
        pts = np.r_[left, right]
        if pts.size == 0:
            continue                                        # nothing good to fit to
        order = 2 if (left.size and right.size and pts.size >= 4) else min(1, pts.size - 1)
        coef = np.polyfit(pts - start, y[pts], order)       # x shifted to keep the fit well-conditioned
        out[start:stop] = np.polyval(coef, idx[start:stop] - start)
    return out


# ----------------------------------------------------------------- "single"
def _single(y: np.ndarray, threshold: float, width: int, sharpness: float,
            grow: float, passes: int) -> tuple[np.ndarray, np.ndarray]:
    """Spike removal for one spectrum (method "single", see module docstring)."""
    out = y.astype(float).copy()
    found = np.zeros(y.size, bool)
    k = 2 * width + 1                                       # running-median window
    for _ in range(passes):
        # --- step 1: Anscombe transform, so noise is about 1 everywhere
        offset = out.min()                                  # the transform needs values >= 0
        ans = lambda v: 2 * np.sqrt(np.clip(v - offset, 0, None) + 3 / 8)   # noqa: E731
        a = ans(out)
        d2a = np.zeros_like(a)
        d2a[1:-1] = a[:-2] - 2 * a[1:-1] + a[2:]            # second difference = curvature
        # Robust noise of one point: spread (MAD) of the curvature / sqrt(6).
        noise = (1.4826 * np.median(np.abs(d2a - np.median(d2a))) or 1.0) / np.sqrt(6)

        # --- step 2: candidates
        med = median_filter(out, size=k, mode="reflect")    # running median: ignores narrow spikes
        excess = (a - ans(med)) / noise                     # height above it, in noise units
        d2y = np.zeros_like(out)
        d2y[1:-1] = out[:-2] - 2 * out[1:-1] + out[2:]
        height = out - med
        with np.errstate(divide="ignore", invalid="ignore"):
            sharp = np.where(height > 0, -d2y / height, 0.0)   # curvature for its height
        seed = (excess > threshold) & (sharp > sharpness) & (-d2a / (noise * np.sqrt(6)) > threshold / 2)
        seed[[0, -1]] = False                               # the end points have no curvature
        if not seed.any():
            break

        # --- step 3: extent of each spike, against a quadratic through its surroundings
        bad = np.zeros(out.size, bool)
        for i in np.where(seed)[0]:
            lo, hi = max(0, i - width), min(out.size, i + width + 1)
            gap = np.zeros(out.size, bool)
            gap[lo:hi] = True
            under = _quadratic_fill(out, gap)[lo:hi]        # what the curve would be without the spike
            above = (a[lo:hi] - ans(np.maximum(under, offset))) / noise > grow
            s = e = i - lo                                  # grow from the candidate both ways
            while s > 0 and above[s - 1]:
                s -= 1
            while e < above.size - 1 and above[e + 1]:
                e += 1
            bad[lo + s: lo + e + 1] = True

        # --- step 4: repair
        out = _quadratic_fill(out, bad)
        found |= bad
    return out, found


# ---------------------------------------------------------------- "compare"
def _compare(Y: np.ndarray, threshold: float, width: int, grow: float) -> tuple[np.ndarray, np.ndarray]:
    """Spike removal by comparison with the other spectra (method "compare")."""
    out, found = Y.copy(), np.zeros(Y.shape, bool)
    max_run = 4 * width                                     # longer excursions are real differences
    for i in range(len(Y)):
        others = np.delete(Y, i, axis=0)
        ref = np.median(others, axis=0)                     # typical spectrum without this one
        # Scale and offset of the reference to this spectrum (y ≈ a·ref + b),
        # refitted without outliers so a spike does not pull the fit.
        use = np.ones(ref.size, bool)
        for _ in range(3):
            a, b = np.polyfit(ref[use], Y[i, use], 1)
            resid = Y[i] - (a * ref + b)
            spread = 1.4826 * np.median(np.abs(resid[use] - np.median(resid[use])))
            use = np.abs(resid) < 4 * spread
        # Noise at each point: how much the repeats differ there, plus photon noise.
        between = 1.4826 * np.median(np.abs(others - ref), axis=0) * abs(a)
        photon = np.sqrt(np.clip(a * ref + b, 1, None))
        z = resid / np.maximum(np.hypot(between, photon), spread)
        bad = np.zeros(ref.size, bool)
        for start, stop in _runs(z > grow):                 # runs above the lower level ...
            if (z[start:stop] > threshold).any() and stop - start <= max_run:   # ... with a real spike in them
                bad[start:stop] = True
        out[i, bad] = (a * ref + b)[bad]                    # replace with the scaled median
        found[i] = bad
    return out, found


# ----------------------------------------------------------------- "kalkan"
def _statelevel(v: np.ndarray, nbins: int) -> float:
    """Lower state level of a histogram (statelevel in spikeRemoval.m)."""
    vmax, vmin = v.max(), v.min() - np.finfo(float).eps
    idx = np.ceil(nbins * (v - vmin) / (vmax - vmin)).astype(int)
    idx = idx[(idx >= 1) & (idx <= nbins)]
    hist = np.bincount(idx, minlength=nbins + 1)[1:]        # counts in bins 1..nbins
    vmin = v.min()
    dy = (vmax - vmin) / nbins
    nonzero = np.nonzero(hist)[0] + 1                       # 1-based bin numbers, as in MATLAB
    low, high = nonzero[0], nonzero[-1]
    lower = hist[low - 1: low + (high - low) // 2]          # lower half of the histogram
    imax = (np.argmax(lower[1:]) + 1) if lower.size > 1 else 1
    return vmin + dy * (low + imax - 1.5)


def _kalkan(y: np.ndarray, window: int, nstd: float, ndata: int, nbins: int,
            passes: int) -> tuple[np.ndarray, np.ndarray]:
    """Port of spikeRemoval.m (method "linear"). 0-based indices throughout."""
    x = y.astype(float).copy()
    n = x.size
    found = np.zeros(n, bool)
    for _ in range(passes):
        xdot = np.gradient(x)                               # 3-point central difference, as cent_diff_n
        level = _statelevel(np.abs(xdot), nbins)
        for idx in np.where(np.abs(xdot) > level)[0]:
            w, nd = window, ndata
            if idx < 2 * nd:                                # near the start: mean of the next nd points
                x[idx] = np.mean(x[idx + 1: idx + nd + 1]); found[idx] = True
                continue
            if idx >= n - 2 * nd - 1:                       # near the end: mean of the previous nd points
                x[idx] = np.mean(x[idx - nd: idx]); found[idx] = True
                continue
            arr = np.arange(idx - 1, idx + 2)
            i = arr[np.argmax(np.abs(x[arr]))]              # largest of the 3 points around the candidate
            if i + 1 <= w // 2:                             # shrink the window near the ends
                w = i * 2
            elif i + 1 >= n - w // 2:
                w = n - (i + 1)
            if nd > w // 2:
                nd = w // 2 - 1
            h = w // 2
            around = np.r_[x[i - h: i], x[i + 1: i + h + 1]]    # window without the point itself
            mu, sd = around.mean(), around.std(ddof=1)
            if x[i] >= mu + nstd * sd or x[i] <= mu - nstd * sd:
                fit = np.r_[np.arange(i - nd - 1, i - 1), np.arange(i + 2, i + nd + 2)]
                x[i - 1: i + 2] = np.interp(np.arange(i - 1, i + 2), fit, x[fit])
                found[i] = True
    return x, found


# ------------------------------------------------------------------- public
def despike(data: Data, method: str = "single", *, threshold: float = 8.0, width: int = 3,
            sharpness: float = 1.0, grow: float = 3.0, passes: int = 2,
            window: int = 25, nstd: float = 3.0, ndata: int = 5, nbins: int = 4,
            verbose: bool = True) -> Data:
    """Remove cosmic-ray spikes. See the module description for how each method works.

    Parameters
    ----------
    method : "single" (default), "compare" (collections of repeats) or "kalkan".

    Settings for "single" and "compare":

    threshold : how far above the surroundings a spike must be, in noise
        units. Lower finds weaker spikes but risks touching real bands.
        Default 8; 6 is more sensitive.
    width : about the widest spike in points (default 3). Real bands must be
        clearly wider than this. "compare" accepts runs up to 4 × width.
    sharpness : ("single") curvature / height a spike must exceed. A single
        point spike is about 2, a band 5 points wide about 0.5. Default 1.
    grow : neighbouring points above this many noise units join the spike.
    passes : ("single", "kalkan") how many times to search again.

    Settings for "kalkan" (names as in spikeRemoval.m):

    window (wnsz), nstd, ndata, nbins.

    Returns
    -------
    A new Spectrum or SpectrumCollection. Every spike found is listed in the
    history entry (``["spikes"]``: spectrum name -> list of x ranges).
    """
    if method not in METHODS:
        raise ValueError(f"Unknown method {method!r}. Choose one of {METHODS}.")
    single = isinstance(data, Spectrum)
    Y = data.y[None, :] if single else data.Y
    names = [data.name] if single else list(data.names)

    if method == "compare":
        if single or len(Y) < 3:
            raise ValueError("method='compare' needs a collection of at least 3 repeated spectra; "
                             "use method='single' for one spectrum.")
        out, found = _compare(Y, threshold, width, grow)
    else:
        rows = [_single(y, threshold, width, sharpness, grow, passes) if method == "single"
                else _kalkan(y, window, nstd, ndata, nbins, passes) for y in Y]
        out = np.vstack([r[0] for r in rows])
        found = np.vstack([r[1] for r in rows])

    # Report: for each spectrum, the x ranges replaced and the largest change.
    x = data.x
    spikes = {}
    for name, f, before, after in zip(names, found, Y, out):
        events = []
        for start, stop in _runs(f):
            diff = after[start:stop] - before[start:stop]
            events.append({"x_from": float(x[start]), "x_to": float(x[stop - 1]), "points": int(stop - start),
                           "change": float(diff[np.argmax(np.abs(diff))])})   # largest change, e.g. -2725
        if events:
            spikes[name] = events
    # The settings that matter for the method used, kept so the step can be repeated.
    settings = {
        "single": {"threshold": threshold, "width": width, "sharpness": sharpness, "grow": grow, "passes": passes},
        "compare": {"threshold": threshold, "width": width, "grow": grow},
        "kalkan": {"window": window, "nstd": nstd, "ndata": ndata, "nbins": nbins, "passes": passes},
    }[method]
    entry = {"step": "despike", "method": method, **settings, "spikes": spikes}

    if verbose:
        n_events = sum(len(v) for v in spikes.values())
        lines = [f"despike ({method}): {n_events} spike(s) in {len(spikes)} of {len(names)} spectra."]
        for name, events in list(spikes.items())[:20]:
            ranges = ", ".join(f"{e['x_from']:.6g}" + (f"-{e['x_to']:.6g}" if e["points"] > 1 else "")
                               + f" ({e['change']:+.4g})" for e in events[:6])
            lines.append(f"  - {name}: {ranges}" + (" ..." if len(events) > 6 else ""))
        if len(spikes) > 20:
            lines.append(f"  ... and {len(spikes) - 20} more spectra (see history).")
        print("\n".join(lines))

    if single:
        return data.copy_with(y=out[0], history=data.history + (entry,))
    return data.copy_with(Y=out, history=data.history + (entry,))


__all__ = ["despike", "METHODS"]
