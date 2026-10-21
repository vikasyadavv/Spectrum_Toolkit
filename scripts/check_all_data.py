"""Run every feature with every method on every file in data/, and report
anything that fails, warns, is slow (> 20 s) or gives non-finite numbers.

    uv run python scripts/check_all_data.py

Run it after any change, and whenever a new kind of file is added to data/.
Expected messages: files that are not spectra (e.g. .m scripts, .opju) and
map files in long format give a clear "not supported" error.
"""
import sys, time, traceback, warnings, tempfile, io, contextlib
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import spectrum_toolkit as stk
from spectrum_toolkit import Spectrum, SpectrumCollection, Recipe
import importlib
B, S, N, D, DS = (importlib.import_module("spectrum_toolkit." + m) for m in ("baseline", "smooth", "normalize", "derivative", "despike"))

D_ = Path(__file__).resolve().parent.parent / "data"
files = sorted(p for p in D_.iterdir() if p.is_file() and not p.name.startswith("."))
problems = []
def bad(where, msg): problems.append(f"{where}: {msg}"); print("  !!", where, msg)
def check(where, d, ref=None):
    arr = d.y if isinstance(d, Spectrum) else d.Y
    if not np.all(np.isfinite(arr)): bad(where, f"non-finite values ({np.sum(~np.isfinite(arr))})")
    if ref is not None and arr.shape != (ref.y.shape if isinstance(ref, Spectrum) else ref.Y.shape):
        bad(where, f"shape changed {arr.shape}")
def run(where, f):
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            t = time.time(); r = f(); dt = time.time() - t
            for x in w:
                if "Font" not in str(x.message): bad(where, f"warning: {x.category.__name__}: {str(x.message)[:150]}")
        if dt > 20: bad(where, f"slow: {dt:.0f} s")
        return r
    except Exception as e:
        bad(where, f"{type(e).__name__}: {str(e)[:300]}")
        return None

for f in files:
    print(f"\n=== {f.name}")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        data = run(f"{f.name} load", lambda: stk.load(f))
    print("  load printed:", buf.getvalue().strip().replace("\n", " | ")[:400])
    if data is None: continue
    if isinstance(data, list):
        print("  list of", len(data)); data = run(f"{f.name} combine", lambda: stk.combine(*data, interpolate=True, verbose=False))
        if data is None: continue
    print("  ", data)
    if isinstance(data, SpectrumCollection) and len(data) > 60:
        data = data.select(*range(0, len(data), max(1, len(data) // 60)))   # keep the hunt fast
        print("   subset", data)
    x0, x1 = float(data.x.min()), float(data.x.max())
    for m in DS.METHODS:
        if m == "compare" and (isinstance(data, Spectrum) or len(data) < 3): continue
        r = run(f"{f.name} despike {m}", lambda: data.despike(m, verbose=False)); r is not None and check(f"{f.name} despike {m}", r, data)
    base = run(f"{f.name} despike default", lambda: data.despike(verbose=False)) or data
    for m in B.METHODS:
        r = run(f"{f.name} baseline {m}", lambda: base.baseline(m)); r is not None and check(f"{f.name} baseline {m}", r, data)
    bl = run(f"{f.name} baseline default", lambda: base.baseline()) or base
    for m in S.METHODS:
        r = run(f"{f.name} smooth {m}", lambda: bl.smooth(m)); r is not None and check(f"{f.name} smooth {m}", r, data)
    for m in N.METHODS:
        mean = bl.y if isinstance(bl, Spectrum) else bl.Y.mean(0); xp = bl.x[np.argmax(mean)]
        kw = {"region": (xp - 15, xp + 15)} if m == "band" else {}
        if m in N._TOGETHER and (isinstance(bl, Spectrum) or len(bl) < 2): kw["reference"] = (bl.y if isinstance(bl, Spectrum) else bl.Y[0]) * 1.1
        r = run(f"{f.name} normalize {m}", lambda: bl.normalize(m, **kw)); r is not None and check(f"{f.name} normalize {m}", r, data)
    for m in D.METHODS:
        for n in (1, 2):
            r = run(f"{f.name} derivative {m} n={n}", lambda: bl.derivative(m, n=n)); r is not None and check(f"{f.name} derivative {m}{n}", r, data)
    # plots
    for kind in ("lines", "stack", "mean", "image"):
        if kind == "image" and (isinstance(bl, Spectrum)): continue
        for style in ("clean", "publication", "matlab"):
            run(f"{f.name} plot {kind} {style}", lambda: bl.plot(kind, style=style, peaks=3)); plt.close("all")
    after = {"despike": base, "baseline": bl, "smooth": bl.smooth(), "normalize": bl.normalize(), "derivative": bl.derivative(n=2)}
    prev = {"despike": data, "baseline": base, "smooth": bl, "normalize": bl, "derivative": bl}
    for step in after:
        run(f"{f.name} compare {step}", lambda: stk.compare(prev[step], after[step], region=(x0 + 100, x0 + 400))); plt.close("all")
    # recipes: from history, save, load, apply again -> identical
    processed = run(f"{f.name} chain", lambda: data.despike(verbose=False).trim(x0 + 20, x1 - 20).baseline().smooth().normalize())
    if processed is not None:
        rec = Recipe.from_history(processed)
        tmp = Path(tempfile.mkdtemp())
        p = run(f"{f.name} recipe save", lambda: rec.save(tmp / "r"))
        rec2 = run(f"{f.name} recipe load", lambda: Recipe.load(p))
        if rec2 is not None and rec2 != rec: bad(f"{f.name} recipe", "loaded recipe differs")
        again = run(f"{f.name} recipe apply", lambda: rec2.apply(data))
        if again is not None:
            a1 = again.y if isinstance(again, Spectrum) else again.Y
            a0 = processed.y if isinstance(processed, Spectrum) else processed.Y
            if a1.shape != a0.shape or not np.allclose(a1, a0): bad(f"{f.name} recipe apply", "result differs from the original processing")
        if f.suffix in (".xlsx", ".asc", ".mat") and len(data.Y if isinstance(data, SpectrumCollection) else [1]) < 100:
            fromfile = run(f"{f.name} recipe on file", lambda: stk.apply(f, p))
# ---------------- edge cases: tiny, flat, one-spectrum collection, descending x
X = np.linspace(100, 200, 10)
edge = {"10 points": Spectrum(X, 100 + np.exp(-((X - 150) / 5) ** 2) * 50),
        "flat": Spectrum(np.linspace(100, 1800, 500), np.full(500, 300.0)),
        "1-spectrum collection": SpectrumCollection(np.linspace(100, 1800, 500), [np.random.default_rng(0).poisson(500, 500)]),
        "descending": Spectrum(np.linspace(1800, 100, 500), np.random.default_rng(1).poisson(500, 500).astype(float))}
for nm, d in edge.items():
    print("=== edge", nm)
    for mod, meths in (("despike", DS.METHODS), ("baseline", B.METHODS), ("smooth", S.METHODS), ("normalize", [m for m in N.METHODS if m not in N._TOGETHER and m != "band"]), ("derivative", D.METHODS)):
        for m in meths:
            if mod == "despike" and m == "compare": continue
            kw = {"verbose": False} if mod == "despike" else {}
            def f(): return getattr(d, mod)(m, **kw)
            try:
                r = f(); check(f"edge {nm} {mod} {m}", r, d)
            except ValueError as e:
                print(f"   clear error {mod} {m}: {str(e)[:120]}")
            except Exception as e:
                bad(f"edge {nm} {mod} {m}", f"{type(e).__name__}: {str(e)[:200]}")
    for kind in ("lines", "stack", "mean"):
        run(f"edge {nm} plot {kind}", lambda: d.plot(kind, peaks=3)); plt.close("all")
print("\n\n==== PROBLEMS", len(problems)); print("\n".join(problems))
