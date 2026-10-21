# Changelog

All notable changes, newest first. Versions follow `MAJOR.MINOR.PATCH`:
until 1.0, MINOR goes up for each approved feature.

## Unreleased

- Feature 10: web service `spectrum_toolkit.api` (FastAPI: health, options, load, process, process-file, figure; `summary_only` on load and process-file leaves out the numbers for big files; the process answers start with `"kind": "lines"` so they can be pasted into figure as they are) as the optional extra `[api]`, and a `Dockerfile` that runs it. Tested in the built image on every file in data/. 20 new tests (`tests/test_api.py`); `conftest.py` skips the module's doctests when FastAPI is not installed.
- Feature 9: recipes (`stk.Recipe`, `stk.apply`, `.apply()` methods): from history or step by step, saved as JSON with every setting, re-applied to data or files; `run` keeps each step. 11 new tests, notebook 11.
- Bug fixes from running everything on all real data (`scripts/check_all_data.py`): files are closed after loading; long-format map files are recognised with a clear message instead of being misread; repeated x values give a clear error in derivative, spline smoothing, rollingball and snip; clearer message for `normalize("band")` without a band.

- Feature 8, round 2: figure styles (`spectrum_toolkit.style`): 40 named settings, presets clean / publication / matlab, `stk.set_style`, `stk.save_style` (JSON), `stk.get_style`; `stk.export` (png, tiff, jpg, pdf, svg, eps; dpi; RGB or CMYK; folder and name); `stk.scatter` (grouped points like gscatter); `peaks=` and `marks=` labels. 18 new tests, notebook 10 with a style editor.

- Feature 8: `stk.plot` (kinds lines, stack, mean, image; region, styles "clean"/"publication", save) and `stk.compare` (before/after view of a step with a "removed" panel; spikes shaded, baseline drawn). Also as `.plot()` methods. matplotlib is now an optional extra: `spectrum-toolkit[plot]`. 10 new tests, notebook 09.

- Benchmarks: `benchmarks/` scripts compare the methods of every feature on simulated spectra (and the real repeats in data/) and write `docs/benchmarks.md`. Rerun with `uv run python benchmarks/run_all.py`. The comparison tables moved there from the roadmap.

- Feature 7: `derivative` (1st and 2nd) with 4 methods (savgol default, gaussian, smoothing spline, gradient); default window/order/sigma chosen per n from the benchmark; uneven x handled. 13 new tests, notebook 08.

- Feature 6: `normalize` with 10 methods (snv default, max, minmax, area, vector, robust snv, band/internal standard, msc, emsc, pqn); `region=` for one-factor methods; `reference=` for msc/emsc/pqn. 16 new tests, notebook 07.

- Feature 5: `smooth` with 7 methods (savgol default, whittaker, automatic smoothing spline, gaussian, moving, median, fourier); 11 new tests.

- Feature 4: `baseline` and `find_baseline` with 8 methods (asls as in baseline.m, iasls, arpls, airpls, modpoly, imodpoly, rollingball, snip); 14 new tests.

- Feature 3: `despike` with methods "single" (default), "compare" (repeats) and "kalkan" (port of spikeRemoval.m); every spike reported. 10 new tests, including the real cosmic rays in CV10-4M.xlsx.

- Feature 2: `trim`, `cut`, `select`, `drop` (also as methods), `stk.combine` for many files with an x-axis check (`stk.check_axes`); interpolation only with `interpolate=True`. interpolation methods linear, quadratic, cubic, pchip, akima; `stk.resample`. 24 new tests.
- Loader: axis titles like "wavenumber" or "Intensity" are no longer used as spectrum names.

- Feature 1b: `stk.load()` reads MATLAB .mat files, finding the x axis and spectra by shape (any variable names); `x=`/`y=` to choose by name. 12 new tests.
- Feature 1: `stk.load()` for text files and Excel (.xlsx, .xls), with layout detection, decimal commas, headers, metadata and a fast path for large files.
- New dependencies: openpyxl, xlrd.
- Notebook `01_loading.ipynb`; 23 new tests (awkward files, large file, real data).

## 0.0.1 (2026-10-20)

- Project setup: uv environment with lock file, src layout, pytest, notebooks.
- Core objects `Spectrum` and `SpectrumCollection`.
- Documentation: README, roadmap and decisions, dependencies and upgrade guide, code conventions.
