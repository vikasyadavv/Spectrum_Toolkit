"""Benchmark: smoothing.

30 simulated spectra with 12 bands on a flat background. Two numbers:
error = root-mean-square difference from the clean spectrum in noise units
(the raw data scores about 1.2); height lost = how much of a narrow band's
height (FWHM < 11 cm-1) the smoother removed, in %. A good smoother has both
low.
"""

import numpy as np

from spectrum_toolkit import Spectrum
from spectrum_toolkit.smooth import METHODS
from _simulate import X, add_noise, lorentz, random_bands, table

SEED = 0
GRID = {"savgol": [{"window": w, "order": o} for w in (7, 11, 15, 21) for o in (2, 4)],
        "whittaker": [{"lam": v} for v in (1, 3, 10, 30, 100)],
        "spline": [{"lam": None}],
        "gaussian": [{"sigma": v} for v in (1, 1.5, 2, 3)],
        "moving": [{"window": w} for w in (3, 5, 7, 9)],
        "median": [{"window": w} for w in (3, 5, 7)],
        "fourier": [{"cutoff": c} for c in (0.1, 0.15, 0.25, 0.4)]}


def make(rng):
    """(clean, measured, bands)."""
    bands = random_bands(rng)
    clean = 300 + sum(lorentz(*b) for b in bands)
    return clean, add_noise(rng, clean), bands


def run(quick=False):
    rng = np.random.default_rng(SEED)
    data = [make(rng) for _ in range(10 if quick else 30)]

    def score(method, settings):
        err, lost = [], []
        for clean, y, bands in data:
            z = Spectrum(X, y).smooth(method, **settings).y
            err.append(np.sqrt(np.mean((z - clean) ** 2 / clean)))
            for c, w, h in bands:
                if w < 11:
                    i = np.argmin(np.abs(X - c))
                    lost.append((clean[i] - z[i]) / (clean[i] - 300))
        return float(np.median(err)), 100 * float(np.median(lost))

    raw = np.median([np.sqrt(np.mean((y - c) ** 2 / c)) for c, y, _ in data])
    summary, sweep = [], []
    for m in METHODS:
        e, l = score(m, {})
        summary.append([f"**{m}**", f"{e:.2f}", f"{l:.1f}"])
        for s in GRID[m]:
            e, l = score(m, s)
            sweep.append([m, ", ".join(f"{k}={v}" for k, v in s.items()), f"{e:.2f}", f"{l:.1f}"])
    return (f"Default settings ({len(data)} spectra, seed {SEED}; raw data error {raw:.2f}).\n\n"
            + table(["method", "error (noise units)", "narrow-band height lost %"], summary)
            + "\n\nEffect of the settings:\n\n"
            + table(["method", "settings", "error", "height lost %"], sweep)
            + "\n\nRead: more smoothing lowers the error until bands start to lose height; "
              "Savitzky-Golay keeps band height best for the noise it removes.")
