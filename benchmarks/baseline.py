"""Benchmark: baseline correction.

30 simulated spectra of each background kind (curved polynomial,
fluorescence decay, broad humps) with 12 bands. Error = root-mean-square
difference between the found and the true baseline, divided by the noise
(square root of the mean baseline). 1 = as good as the noise allows.
"""

import numpy as np

import spectrum_toolkit as stk
from spectrum_toolkit import Spectrum
from spectrum_toolkit.baseline import DEFAULTS, METHODS
from _simulate import X, add_noise, baseline_shape, lorentz, random_bands, table

SEED = 0
GRID = {"asls": ("lam", [1e3, 1e4, 1e5, 1e6, 1e7]), "iasls": ("lam", [1e3, 1e4, 1e5, 1e6, 1e7]),
        "arpls": ("lam", [1e3, 1e4, 1e5, 1e6, 1e7]), "airpls": ("lam", [1e3, 1e4, 1e5, 1e6, 1e7]),
        "modpoly": ("order", [2, 3, 4, 5, 6]), "imodpoly": ("order", [2, 3, 4, 5, 6]),
        "rollingball": ("window", [50, 100, 150, 200, 300]), "snip": ("window", [50, 100, 150, 200, 300])}
KINDS = ("poly", "fluor", "humps")


def make(rng, kind):
    """(true baseline, measured spectrum)."""
    b = baseline_shape(rng, kind)
    y = b + sum(lorentz(*band) for band in random_bands(rng, fwhm=(8, 20), height=(200, 4000)))
    return b, add_noise(rng, y)


def run(quick=False):
    rng = np.random.default_rng(SEED)
    data = {k: [make(rng, k) for _ in range(10 if quick else 30)] for k in KINDS}

    def error(method, settings, kind):
        e = [np.sqrt(np.mean((stk.find_baseline(Spectrum(X, y), method, **settings).y - b) ** 2)) / np.sqrt(np.mean(b))
             for b, y in data[kind]]
        return float(np.median(e))

    summary, sweep = [], []
    for m in METHODS:
        name, values = GRID[m]
        per_value = {v: [error(m, {name: v}, k) for k in KINDS] for v in values}
        default = [error(m, {}, k) for k in KINDS]
        summary.append([f"**{m}**", f"{name}={DEFAULTS[m][name]:g}"] + [f"{e:.1f}" for e in default])
        for v, errs in per_value.items():
            sweep.append([m, f"{name}={v:g}"] + [f"{e:.1f}" for e in errs])
    return ("Error in noise units with default settings (lower is better; median of "
            f"{len(data['poly'])} spectra per kind, seed {SEED}).\n\n"
            + table(["method", "default", "polynomial", "fluorescence", "humps"], summary)
            + "\n\nEffect of the main setting:\n\n"
            + table(["method", "setting", "polynomial", "fluorescence", "humps"], sweep))
