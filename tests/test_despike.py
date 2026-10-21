"""Tests for cosmic-ray removal (src/spectrum_toolkit/despike.py).

Simulated spectra mimic the real data: step 1.19 cm-1, Lorentzian bands 8-20
cm-1 wide, photon (Poisson) noise plus read noise. Spikes of known position
and size are added, so we can check both that they are removed and that the
real bands are left alone. Real-data checks at the end use the cosmic rays
seen in CV10-4M.xlsx (spectra 4 and 11 by name).
"""

from pathlib import Path

import numpy as np
import pytest

import spectrum_toolkit as stk
from spectrum_toolkit import Spectrum, SpectrumCollection

DATA = Path(__file__).parent.parent / "data"
X = np.arange(100, 1800, 1.19)


def bands(rng, n=12, fwhm=(8, 20)):
    """A clean simulated Raman spectrum: sloping background plus n Lorentzian bands."""
    y = 300 + 0.2 * (X - 100) + 500 * np.exp(-((X - 900) / 600) ** 2)
    for _ in range(n):
        c, w, h = rng.uniform(300, 1750), rng.uniform(*fwhm), rng.uniform(200, 6000)
        y = y + h / (1 + ((X - c) / (w / 2)) ** 2)
    return y


def noisy(rng, clean):
    """Photon noise plus 15 counts of read noise."""
    return rng.poisson(clean).astype(float) + rng.normal(0, 15, clean.size)


def test_single_spike_on_a_band_flank_is_repaired():
    """A 2-point spike on the side of a band is removed and the flank restored within noise."""
    rng = np.random.default_rng(0)
    clean = 300 + 5000 / (1 + ((X - 1000) / 6) ** 2)               # one band, FWHM 12 cm-1
    y = noisy(rng, clean)
    i = int(np.argmin(np.abs(X - 1006)))                             # on the right flank
    y[i:i + 2] += [4000, 2500]
    out = Spectrum(X, y).despike(verbose=False)
    err = np.abs(out.y - clean) / np.sqrt(clean)                     # error in noise units
    assert err[i:i + 2].max() < 5                                     # spike gone
    assert abs(out.y[np.argmin(np.abs(X - 1000))] - y[np.argmin(np.abs(X - 1000))]) < 1   # band top untouched


def test_almost_no_false_alarms_on_clean_spectra():
    """50 clean simulated spectra with 12 bands each: at most 2 are changed at all
    (measured: 1 of 50, a noise point next to a band)."""
    rng = np.random.default_rng(1)
    changed = 0
    for _ in range(50):
        y = noisy(rng, bands(rng))
        changed += np.any(Spectrum(X, y).despike(verbose=False).y != y)
    assert changed <= 2


def test_detects_most_strong_spikes():
    """Over 100 spectra, at least 85 % of spikes 20-40 x noise are repaired (measured 94 %)."""
    rng = np.random.default_rng(2)
    ok = total = 0
    for _ in range(100):
        clean = bands(rng)
        y = noisy(rng, clean)
        i, w = rng.integers(10, X.size - 10), rng.integers(1, 4)
        y[i:i + w] += rng.uniform(20, 40) * np.sqrt(clean[i:i + w].mean()) * np.array([1, 0.7, 0.4][:w])
        out = Spectrum(X, y).despike(verbose=False)
        total += 1
        ok += np.max(np.abs(out.y - clean)[i:i + w] / np.sqrt(clean[i:i + w])) < 5
    assert ok / total >= 0.85


def test_report_and_history():
    """Each spike is listed with its x range and size; settings are recorded."""
    y = np.full(X.size, 1000.0) + np.random.default_rng(3).normal(0, 30, X.size)
    y[500] += 5000
    out = Spectrum(X, y, name="s").despike(threshold=6, verbose=False)
    h = out.history[-1]
    assert h["step"] == "despike" and h["method"] == "single" and h["threshold"] == 6
    assert len(h["spikes"]["s"]) == 1 and np.isclose(h["spikes"]["s"][0]["x_from"], X[500])
    assert h["spikes"]["s"][0]["change"] < -4000                     # about 5000 removed


def test_compare_needs_repeats_and_finds_spike():
    """'compare' uses the other spectra; it refuses a single spectrum."""
    rng = np.random.default_rng(4)
    clean = bands(rng)
    Y = np.vstack([noisy(rng, clean * f) for f in (0.9, 1.0, 1.1, 1.05, 0.95)])
    Y[2, 700:707] += 3000                                            # a broad 7-point cosmic ray
    out = SpectrumCollection(X, Y).despike("compare", verbose=False)
    assert np.max(np.abs(out.Y[2, 700:707] - 1.1 * clean[700:707]) / np.sqrt(clean[700:707])) < 6
    assert np.array_equal(out.Y[0], Y[0])                            # other spectra untouched
    with pytest.raises(ValueError, match="at least 3"):
        Spectrum(X, Y[0]).despike("compare")


def test_kalkan_port_removes_a_big_spike():
    """The MATLAB spikeRemoval.m port removes an obvious spike in the middle."""
    rng = np.random.default_rng(5)
    y = 1000 + rng.normal(0, 20, X.size)
    y[700] += 3000
    out = Spectrum(X, y).despike("kalkan", verbose=False)
    assert abs(out.y[700] - 1000) < 100
    assert out.history[-1]["nstd"] == 3.0


def test_unknown_method():
    """A wrong method name lists the choices."""
    with pytest.raises(ValueError, match="compare"):
        Spectrum(X, np.ones(X.size)).despike("median")


# ------------------------------------------------------------------ real data
real = pytest.mark.skipif(not (DATA / "CV10-4M.xlsx").is_file(), reason="data/ files not present")


@real
@pytest.mark.parametrize("method", ["single", "compare"])
def test_real_cosmic_rays_in_cv(method):
    """CV10-4M.xlsx: exactly the 3 cosmic rays seen by eye (spectrum 4 at 1635 and
    1696-1702, spectrum 11 at 313-315); RhB and MB files have none."""
    out = stk.load(DATA / "CV10-4M.xlsx", verbose=False).despike(method, verbose=False)
    spikes = out.history[-1]["spikes"]
    assert set(spikes) == {"Spectrum 4", "Spectrum 11"}
    assert [round(e["x_from"]) for e in spikes["Spectrum 4"]] == [1635, 1696]
    for f in ("RhB10-4M.xlsx", "MB 10-4M.xlsx"):
        assert stk.load(DATA / f, verbose=False).despike(method, verbose=False).history[-1]["spikes"] == {}
