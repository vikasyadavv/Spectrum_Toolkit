# Roadmap and decisions

Each feature moves through: proposed → agreed → built → approved.

## Decisions

| Date | Decision | Why |
|---|---|---|
| 2026-10-20 | Python library first; website later | Get the science right before any interface. |
| 2026-10-20 | Package name `spectrum_toolkit` | Plain and descriptive. |
| 2026-10-20 | uv for environments, with a lock file | Fast, installs Python itself, and the lock file makes the Docker image identical to the dev setup. |
| 2026-10-20 | Python 3.13 for development; library supports 3.11+ | Already installed on the Mac; all dependencies support it; tests pass on it. |
| 2026-10-20 | Jupyter notebooks for trying features | Tick options and see plots straight away on real data. |
| 2026-10-20 | Two core objects: `Spectrum` and `SpectrumCollection` | The data includes single spectra, multi-sample sheets and a 550-spectrum map. |
| 2026-10-20 | Processing never changes data in place; each step is recorded in `history` | Before/after comparison is always possible, and a recipe can be re-applied. |
| 2026-10-20 | Must run in Docker and be served from our VM | End goal: website front end talking to this library. |
| 2026-10-20 | Every dependency documented with its version; upgrades on a branch, tests must pass | Easy, safe upgrades later. See `dependencies.md`. |
| 2026-10-20 | Code commented line by line in plain English; every function documented | Anyone can read what each line does. See `conventions.md`. |

## Features

| # | Feature | Status |
|---|---|---|
| 0 | Project setup, core objects | built, waiting for approval |
| 1 | Loading data files (.asc/.txt/.csv, .xlsx, .mat, then others) | proposed |
| 2 | Trim range | proposed |
| 3 | Cosmic-ray removal | proposed |
| 4 | Baseline correction | proposed |
| 5 | Smoothing | proposed |
| 6 | Normalisation | proposed |
| 7 | Derivatives | proposed |
| 8 | Plotting and styling, before/after view | proposed |
| 9 | Recipes: save and re-apply a processing pipeline | proposed |
| 10 | Docker image | proposed |
| later | PCA, MCR, peak fitting, maps | parked |

## Real data we test with (`data/`)

- `A_A_1.asc`: one Raman spectrum, 1,024 points, 100–3,646 cm⁻¹, two space-separated columns, Windows line endings.
- `MB 10-4M.xlsx`: 5 spectra as x/y column pairs, "Sample" label row, x descending from 1,803.
- `wt_raw.mat`: Renishaw map, 550 spectra × 747 points (`wt`, `W`) plus an X, Y, wavenumber, intensity table (`data_wt`).
- `mcr_kd_wt.opju`: Origin project; closed format, export to CSV from Origin instead.
- `main.m`, `separation1.tiff`: existing MATLAB PCA workflow and its figure (reference for later PCA work).
