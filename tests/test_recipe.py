"""Tests for recipes (src/spectrum_toolkit/recipe.py) and for the fixes found
by running every feature on all the real data files (2026-10-21)."""

import json
import warnings
from pathlib import Path

import numpy as np
import pytest

import spectrum_toolkit as stk
from spectrum_toolkit import Recipe, Spectrum, SpectrumCollection

DATA = Path(__file__).parent.parent / "data"
X = np.arange(100, 1800, 1.19)


def noisy(rng, n=4):
    """n spectra: sloping background, two bands, photon noise, one cosmic ray in the first."""
    clean = 300 + 0.3 * X + 3000 / (1 + ((X - 1000) / 6) ** 2) + 1500 / (1 + ((X - 1500) / 8) ** 2)
    Y = rng.poisson(clean, (n, X.size)).astype(float)
    Y[0, 700] += 6000
    return SpectrumCollection(X, Y, names=[f"s{i}" for i in range(n)])


def test_from_history_repeats_exactly():
    """A recipe made from processed data gives the same result on the raw data."""
    raw = noisy(np.random.default_rng(0))
    done = raw.despike(verbose=False).trim(200, 1700).baseline().smooth().normalize().derivative(n=2)
    recipe = Recipe.from_history(done)
    assert [s["step"] for s in recipe.steps] == ["despike", "trim", "baseline", "smooth", "normalize", "derivative"]
    assert "spikes" not in recipe.steps[0] and "regridded" not in recipe.steps[-1]    # results, not settings
    again = recipe.apply(raw)
    assert np.allclose(again.Y, done.Y) and again.history == done.history


def test_build_step_by_step_and_check_settings():
    """Builder calls return new recipes; wrong methods or settings fail at once with a clear message."""
    r0 = Recipe()
    r1 = r0.despike().baseline("asls", lam=1e5).smooth("whittaker", lam=5)
    assert len(r0) == 0 and len(r1) == 3                       # the original is unchanged
    assert r1.steps[1] == {"step": "baseline", "method": "asls", "lam": 1e5, "p": 0.005, "max_iter": 10, "tol": 0.0}
    assert r1.steps[0]["threshold"] == 8.0                       # defaults are stored too
    with pytest.raises(ValueError, match="lam"):
        Recipe().baseline("airpls", lamda=1e5)
    with pytest.raises(ValueError, match="Unknown"):
        Recipe().smooth("wavelet")
    with pytest.raises(ValueError, match="threshold"):
        Recipe().despike("kalkan", threshold=5)                # kalkan has no threshold
    with pytest.raises(ValueError, match="can hold"):
        Recipe([{"step": "fly"}])


def test_save_load_and_apply_from_file(tmp_path):
    """Saved as readable JSON; loading gives an equal recipe; stk.apply takes a path to either."""
    r = Recipe(name="my SERS", description="for 10-4 M dyes").despike().trim(200, 1750).baseline().normalize("max")
    path = r.save(tmp_path / "sers")
    assert path.suffix == ".json"
    d = json.loads(path.read_text())
    assert d["recipe"] == "my SERS" and d["spectrum_toolkit"] == stk.__version__ and len(d["steps"]) == 4
    assert Recipe.load(path) == r
    data = noisy(np.random.default_rng(1))
    assert np.allclose(stk.apply(data, path).Y, r.apply(data).Y)
    assert np.allclose(data.apply(r).Y, r.apply(data).Y)       # also as a method


def test_steps_that_cannot_be_repeated_are_listed():
    """select/drop by name and combine are left out, with the reason."""
    c = noisy(np.random.default_rng(2)).select("s1", "s2").baseline()
    r = Recipe.from_history(c)
    assert [s["step"] for s in r.steps] == ["baseline"]
    assert r.skipped and r.skipped[0].startswith("select")
    assert "not kept" in str(r)


def test_reference_spectrum_is_stored_as_numbers():
    """normalize with a reference: the builder stores the numbers, so the recipe can be replayed;
    a reference only recorded as "given" in history cannot."""
    data = noisy(np.random.default_rng(3))
    ref = data[1]
    r = Recipe().normalize("msc", reference=ref)
    assert len(r.steps[0]["reference"]) == X.size
    assert np.allclose(r.apply(data[0]).y, data[0].normalize("msc", reference=ref).y)
    r2 = Recipe.from_history(data[0].normalize("msc", reference=ref))
    assert len(r2) == 0 and "reference" in r2.skipped[0]


def test_run_keeps_every_step_and_errors_name_the_step():
    data = noisy(np.random.default_rng(4))
    steps = Recipe().trim(200, 1700).smooth().run(data)
    assert [name for name, _ in steps] == ["start", "trim", "smooth"]
    with pytest.raises(ValueError, match=r"step 1 \(trim"):
        Recipe().trim(5000, 6000).apply(data)


real = pytest.mark.skipif(not (DATA / "CV10-4M.xlsx").is_file(), reason="data/ files not present")


@real
def test_recipe_on_real_files():
    """A recipe from CV works on the MB file by path, and on a file of x/y pairs with gaps."""
    cv = stk.load(DATA / "CV10-4M.xlsx", verbose=False)
    r = Recipe.from_history(cv.despike(verbose=False).trim(200, 1750).baseline().smooth().normalize())
    mb = r.apply(DATA / "MB 10-4M.xlsx")
    assert len(mb) == 5 and mb.x.min() >= 200 and np.all(np.isfinite(mb.Y))
    mix = r.apply(DATA / "CV+RhB+MB.xlsx")                     # loaded as separate spectra, joined automatically
    assert len(mix) == 35


# ----------------------------------------------------------- bug-hunt fixes
def test_loading_closes_the_file(tmp_path):
    """No 'unclosed file' warning when loading (found on every real file)."""
    p = tmp_path / "s.txt"
    p.write_text("\n".join(f"{x} {x * 2}" for x in range(20)))
    with warnings.catch_warnings():
        warnings.simplefilter("error", ResourceWarning)
        stk.load(p, verbose=False)


def test_long_format_map_is_recognised(tmp_path):
    """X, Y, wavenumber, intensity rows (like the SINGLECELL map) give a clear message, not 3 wrong spectra."""
    rows = [f"{px}\t{py}\t{w}\t{100 + w}" for px in range(4) for py in range(3) for w in range(1800, 1700, -2)]
    p = tmp_path / "map.txt"
    p.write_text("#X\t#Y\t#Wave\t#Intensity\n" + "\n".join(rows))
    with pytest.raises(ValueError, match=r"looks like a map.*12 positions × 50 points"):
        stk.load(p, verbose=False)
    assert len(stk.load(p, layout="shared", verbose=False)) == 3    # still readable as a plain table


def test_repeated_x_values_give_a_clear_error():
    """Derivatives, spline smoothing and window baselines explain repeated x instead of failing oddly."""
    x = np.r_[np.arange(100.0), 50.0]
    s = Spectrum(x, np.sin(x / 10))
    for call in (lambda: s.derivative(), lambda: s.smooth("spline"), lambda: s.baseline("snip")):
        with pytest.raises(ValueError, match="more than once"):
            call()


def test_band_without_a_band_is_explained():
    s = Spectrum(X, 300 + 0.1 * X)
    with pytest.raises(ValueError, match="No band in region"):
        s.normalize("band", region=(900, 950))
