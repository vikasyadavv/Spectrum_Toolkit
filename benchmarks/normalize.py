"""Benchmark: normalisation.

Groups of 10 replicates of the same simulated spectrum, each multiplied by
a random factor 0.5-2 (laser power, focus), in four scenarios:
  scale     only the factor
  offset    factor plus a random constant offset 0-800 counts
  slope     factor, offset and a random sloping background
  changing  factor, plus one band (600 cm-1) whose height really changes
            (e.g. a concentration series); spread is measured away from it
Spread = how different the normalised replicates still are: root-mean-square
standard deviation across replicates divided by the standard deviation of
the mean spectrum, in %. Lower is better; noise alone gives about 3.4 %.
A band at 1000 cm-1 is the same in every replicate (internal standard).

Real data: the repeat spectra in data/ (local only) after despiking.
"""

from pathlib import Path

import numpy as np

import spectrum_toolkit as stk
from spectrum_toolkit import SpectrumCollection
from _simulate import X, add_noise, lorentz, random_bands, table

SEED = 0
DATA = Path(__file__).resolve().parent.parent / "data"
KINDS = ("scale", "offset", "slope", "changing")
CONFIGS = [("none (raw)", None, {}), ("max", "max", {}), ("minmax", "minmax", {}), ("area", "area", {}),
           ("vector", "vector", {}), ("snv (default)", "snv", {}), ("rsnv", "rsnv", {}),
           ("band, region 985-1015", "band", {"region": (985, 1015)}),
           ("max, region 985-1015", "max", {"region": (985, 1015)}),
           ("msc", "msc", {}), ("emsc, order 1", "emsc", {"order": 1}), ("emsc (order 2)", "emsc", {}),
           ("pqn", "pqn", {})]


def make(rng, kind, k=10):
    """(replicates, mask of points where the spread is measured)."""
    base = 50 + sum(lorentz(*b) for b in random_bands(rng)) + lorentz(1000, 12, 3000)
    keep = np.abs(X - 600) > 60 if kind == "changing" else np.ones(X.size, bool)
    Y = []
    for _ in range(k):
        y = base + (lorentz(600, 15, rng.uniform(0, 20000)) if kind == "changing" else 0)
        y = y * rng.uniform(0.5, 2)
        if kind in ("offset", "slope"):
            y = y + rng.uniform(0, 800)
        if kind == "slope":
            y = y + rng.uniform(-1, 1) * (X - 950)
        Y.append(add_noise(rng, y))
    return np.array(Y), keep


def spread(Y, keep=None):
    """Spread of replicates in % of the signal variation."""
    keep = np.ones(Y.shape[1], bool) if keep is None else keep
    return 100 * np.sqrt(np.mean(Y[:, keep].var(axis=0))) / np.std(Y.mean(axis=0)[keep])


def run(quick=False):
    rng = np.random.default_rng(SEED)
    data = {k: [make(rng, k) for _ in range(5 if quick else 20)] for k in KINDS}
    rows = []
    for label, method, settings in CONFIGS:
        row = [label]
        for k in KINDS:
            v = [spread(Y if method is None else SpectrumCollection(X, Y).normalize(method, **settings).Y, keep)
                 for Y, keep in data[k]]
            row.append(f"{np.median(v):.1f}")
        rows.append(row)
    out = (f"Spread of replicates in % (lower is better; noise floor about 3.4; median of "
           f"{len(data['scale'])} groups, seed {SEED}).\n\n"
           + table(["method", "scale", "offset", "slope", "changing band"], rows)
           + "\n\nRead: every method fixes a pure scale change. Offsets need snv/msc/emsc (or baseline "
             "correction first); a sloping background needs emsc. When some bands really change, "
             "one-factor methods are pulled by them; pqn or an internal-standard band (band, or max "
             "with a region) stay right.")
    files = ["CV10-4M.xlsx", "RhB10-4M.xlsx", "MB 10-4M.xlsx"]
    if not all((DATA / f).is_file() for f in files):
        return out + "\n\nReal data: skipped (data/ files not present on this computer)."
    methods = ["max", "area", "vector", "snv", "rsnv", "msc", "emsc", "pqn"]
    real = []
    for f in files:
        c = stk.load(DATA / f, verbose=False).despike(verbose=False).baseline()
        real.append([f"{f} ({len(c.Y)} spectra)", f"{spread(c.Y):.1f}"]
                    + [f"{spread(c.normalize(m).Y):.1f}" for m in methods])
    return (out + "\n\nReal repeats (despiked, airpls baseline, then normalised): spread in %.\n\n"
            + table(["file", "none"] + methods, real)
            + "\n\nRead: normalising removes most of the spot-to-spot intensity difference in CV; "
              "what is left in RhB is a real change in band ratios, which "
              "normalisation cannot (and should not) remove.")
