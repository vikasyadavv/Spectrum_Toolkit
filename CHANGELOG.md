# Changelog

All notable changes, newest first. Versions follow `MAJOR.MINOR.PATCH`:
until 1.0, MINOR goes up for each approved feature.

## Unreleased

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
