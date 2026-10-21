"""Benchmark: cosmic-ray (spike) removal.

300 simulated spectra (12 bands each) get 1-3 spikes, 1-3 points wide, of
known size (5-40 x the local noise). A spike counts as repaired when every
spike point ends within 5 noise units of the clean spectrum. A false alarm
is any changed point more than 3 points away from a spike. A published
method (Whitaker & Hayes 2018) is included for reference.
"""

import numpy as np
from scipy.ndimage import median_filter

from spectrum_toolkit import Spectrum
from _simulate import X, add_noise, lorentz, table

SEED = 1


def whitaker_hayes(y, threshold=6.0, width=3):
    """Reference method (not in the toolkit): modified z-score of the first
    differences above threshold = spike; replaced by the median around it."""
    d = np.diff(y)
    z = 0.6745 * (d - np.median(d)) / np.median(np.abs(d - np.median(d)))
    bad = np.zeros(y.size, bool)
    bad[1:] = np.abs(z) > threshold
    out = y.copy()
    fill = median_filter(y, size=2 * width + 1, mode="nearest")
    out[bad] = fill[bad]
    return out


def make(rng):
    """(clean, measured with spikes, list of (index, width, size in noise units))."""
    clean = 300 + 0.2 * (X - 100) + 500 * np.exp(-((X - 900) / 600) ** 2)
    for _ in range(12):
        clean = clean + lorentz(rng.uniform(300, 1750), rng.uniform(8, 20), rng.uniform(200, 6000))
    y = add_noise(rng, clean)
    spikes = []
    for _ in range(rng.integers(1, 4)):
        i, w, size = rng.integers(5, X.size - 8), rng.integers(1, 4), rng.uniform(5, 40)
        y[i:i + w] += size * np.sqrt(clean[i:i + w].mean()) * np.array([1, 0.7, 0.4][:w])
        spikes.append((i, w, size))
    return clean, y, spikes


def run(quick=False):
    rng = np.random.default_rng(SEED)
    data = [make(rng) for _ in range(100 if quick else 300)]
    methods = [
        ("single (default, threshold 8)", lambda y: Spectrum(X, y).despike(verbose=False).y),
        ("single, threshold 6", lambda y: Spectrum(X, y).despike(threshold=6, verbose=False).y),
        ("single, threshold 12", lambda y: Spectrum(X, y).despike(threshold=12, verbose=False).y),
        ("single, sharpness 0.5", lambda y: Spectrum(X, y).despike(sharpness=0.5, verbose=False).y),
        ("kalkan (MATLAB spikeRemoval.m)", lambda y: Spectrum(X, y).despike("kalkan", verbose=False).y),
        ("Whitaker-Hayes 2018 (reference only)", whitaker_hayes),
    ]
    rows = []
    for label, f in methods:
        hit = {"weak": [0, 0], "mid": [0, 0], "strong": [0, 0]}
        spectra_with_fa = fa_points = 0
        for clean, y, spikes in data:
            out = f(y)
            near = np.zeros(y.size, bool)
            for i, w, size in spikes:
                near[max(i - 3, 0):i + w + 3] = True
                key = "weak" if size < 10 else "mid" if size < 20 else "strong"
                hit[key][1] += 1
                hit[key][0] += np.max(np.abs(out - clean)[i:i + w] / np.sqrt(clean[i:i + w])) < 5
            false = (out != y) & ~near
            fa_points += false.sum()
            spectra_with_fa += false.any()
        rows.append([label] + [f"{a / max(n, 1):.0%}" for a, n in hit.values()]
                    + [f"{spectra_with_fa / len(data):.0%}", f"{fa_points / len(data):.2f}"])
    return ("Spikes repaired, by spike size in noise units, and false alarms "
            f"({len(data)} spectra, seed {SEED}).\n\n"
            + table(["method", "weak <10", "medium 10-20", "strong >20", "spectra with a false alarm",
                     "false points per spectrum"], rows)
            + "\n\nRead: \"single\" repairs most medium and strong spikes and almost never touches a "
              "real band. Lower threshold = more weak spikes caught but more false alarms. "
              "Weak spikes (<10x noise) are hard to tell from noise for every method.")
