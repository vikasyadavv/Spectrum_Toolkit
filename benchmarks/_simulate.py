"""Simulated Raman spectra shared by all benchmarks.

They imitate the real data in data/: points every 1.19 cm-1 from 100 to
1800 cm-1, Lorentzian bands 8-20 cm-1 wide (full width at half maximum),
photon (Poisson) noise plus 15 counts of detector read noise. Because the
clean spectrum is known, the error of every method can be measured.
"""

import numpy as np

X = np.arange(100, 1800, 1.19)                     # Raman shift axis, cm-1


def lorentz(center, fwhm, height):
    """One Lorentzian band on X."""
    return height / (1 + ((X - center) / (fwhm / 2)) ** 2)


def random_bands(rng, n=12, fwhm=(8, 20), height=(300, 4000), lo=150, hi=1750):
    """List of n random bands as (center, fwhm, height)."""
    return [(rng.uniform(lo, hi), rng.uniform(*fwhm), rng.uniform(*height)) for _ in range(n)]


def add_noise(rng, clean):
    """Photon noise (Poisson) plus 15 counts of read noise."""
    return rng.poisson(np.clip(clean, 0, None)).astype(float) + rng.normal(0, 15, clean.size)


def baseline_shape(rng, kind):
    """A background of the given kind: "poly" (curved), "fluor" (fluorescence decay) or "humps" (broad bumps)."""
    t = (X - X[0]) / np.ptp(X)
    if kind == "poly":
        return 800 + 600 * t - 900 * t ** 2 + rng.uniform(-200, 200) * t ** 3
    if kind == "fluor":
        return 300 + 3000 * np.exp(-t / rng.uniform(0.3, 0.8))
    return 400 + sum(rng.uniform(500, 2000) * np.exp(-((t - rng.uniform(0, 1)) / rng.uniform(0.15, 0.4)) ** 2)
                     for _ in range(2))


def table(header, rows):
    """A Markdown table from a header list and a list of row lists."""
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)
