"""Benchmark: derivatives.

30 simulated spectra with 12 Lorentzian bands, whose exact 1st and 2nd
derivatives are known from the formula. Error = root-mean-square difference
from the exact derivative, in % of the root-mean-square exact derivative.
Lower is better; differentiation amplifies noise, so 2nd derivatives are
always worse than 1st.
"""

import numpy as np

from spectrum_toolkit import Spectrum
from spectrum_toolkit.derivative import METHODS
from _simulate import X, add_noise, random_bands, table

SEED = 0
GRID = {"savgol": [{"window": w, "order": o} for w in (9, 11, 15, 21) for o in (2, 3, 4, 5, 6)],
        "gaussian": [{"sigma": v} for v in (0.75, 1, 1.25, 1.5, 2, 3)],
        "spline": [], "gradient": []}


def make(rng):
    """(measured, exact 1st derivative, exact 2nd derivative)."""
    y, d1, d2 = np.full(X.size, 300.0), np.zeros(X.size), np.zeros(X.size)
    for c, w, h in random_bands(rng):
        g = w / 2
        u = (X - c) / g
        L = 1 / (1 + u * u)
        y += h * L
        d1 += h * (-2 * u / g) * L ** 2                       # d/dx of h / (1 + u²)
        d2 += h * (2 / g ** 2) * (3 * u * u - 1) * L ** 3     # d²/dx²
    return add_noise(rng, y), d1, d2


def run(quick=False):
    rng = np.random.default_rng(SEED)
    data = [make(rng) for _ in range(10 if quick else 30)]

    def error(method, n, settings):
        e = []
        for y, d1, d2 in data:
            exact = d1 if n == 1 else d2
            z = Spectrum(X, y).derivative(method, n=n, **settings).y
            e.append(100 * np.sqrt(np.mean((z - exact) ** 2)) / np.sqrt(np.mean(exact ** 2)))
        return float(np.median(e))

    summary = [[f"**{m}**", f"{error(m, 1, {}):.1f}", f"{error(m, 2, {}):.1f}"] for m in METHODS]
    sweep = []
    for m, grid in GRID.items():
        for s in grid:
            cells = [f"{error(m, n, s):.1f}" if m != "savgol" or s["order"] >= n else "-" for n in (1, 2)]
            sweep.append([m, ", ".join(f"{k}={v}" for k, v in s.items())] + cells)
    return (f"Error in % with default settings ({len(data)} spectra, seed {SEED}).\n\n"
            + table(["method", "1st derivative", "2nd derivative"], summary)
            + "\n\nEffect of the settings:\n\n"
            + table(["method", "settings", "1st derivative", "2nd derivative"], sweep)
            + "\n\nRead: Savitzky-Golay is best for both; its defaults (window 15 / order 5 for n=1, "
              "window 11 / order 4 for n=2) are the best rows above. The spline is as good for a "
              "1st derivative but poor for a 2nd. Plain finite differences (gradient) only suit "
              "data that is already smooth.")
