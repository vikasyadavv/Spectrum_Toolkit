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
| 2026-10-20 | `data/` stays local, never in git | Files can be large or unpublished. |
| 2026-10-21 | Combining files never interpolates unless asked (`interpolate=True`) | Interpolation changes the numbers; the user decides. Same-grid data is combined without changing any value. |
| 2026-10-20 | Code commented line by line in plain English; every function documented | Anyone can read what each line does. See `conventions.md`. |

## Features

| # | Feature | Status |
|---|---|---|
| 0 | Project setup, core objects | approved 2026-10-20 |
| 1 | Loading data files, round 1: text and Excel (.xlsx, .xls) | approved 2026-10-20 |
| 1b | Loading .mat files (many variables, any names) | approved 2026-10-20 |
| 1d | Loading JCAMP-DX, SPC, JSON | proposed |
| 1c | Instrument files: Renishaw .wdf and others | later |
| 2 | Editing: trim, cut, select/drop spectra, combine files | built, waiting for approval |
| 3 | Cosmic-ray removal | proposed |
| 4 | Baseline correction | proposed |
| 5 | Smoothing | proposed |
| 6 | Normalisation | proposed |
| 7 | Derivatives | proposed |
| 8 | Plotting and styling, before/after view (`stk.plot`) | proposed |
| 9 | Recipes: save and re-apply a processing pipeline | proposed |
| 10 | Docker image | proposed |
| later | PCA, MCR, peak fitting | parked |
| later | Map files (X, Y, wavenumber, intensity tables) as a map with positions | postponed 2026-10-20 |

## Feature 1 notes

- `stk.load(path)` returns `Spectrum`, `SpectrumCollection` or a list of `Spectrum` (x/y pairs with different x).
- Detects: encoding, line endings, separator, decimal comma, header row, metadata lines, footer, empty columns, layout (`xy`, `shared`, `pairs`, `y`).
- Always ascending x; rows with a missing value dropped; every assumption printed and kept in `meta["load_notes"]`.
- Files can be any size: clean text blocks are parsed by numpy in one call (1 million rows in under 1 s; 2,000 spectra × 1,000 points in 0.6 s). Messy files fall back to careful cell-by-cell reading.
- Overrides: `sheet=`, `layout=`, `x_col=`, `y_cols=`, `delimiter=`, `decimal=`.
- Decided: text and Excel first; `.mat` later (files hold many variables with varying names); `.wdf` later; no pandas.

## Feature 1b notes (.mat)

- Goal: a user uploads a file and gets spectra, with no settings. Variable names are never assumed.
- The guess goes by shape: a rising (or falling) vector is x; a matrix with a side of that length holds the spectra (per column if rows match, per row if columns match). Biggest matrix wins; other possible pairs are listed in the notes.
- No fitting vector: the biggest matrix is read like a text table. Vectors only: rising vector is x, same-length vectors are y.
- Structures are searched (`s.field`); text, cell arrays, complex and 3-D arrays are skipped with a note.
- Override by name: `stk.load(f, x="W", y="wt")`.
- Uses scipy (already a dependency). v7.3 files (HDF5) give a clear error asking to re-save with `-v7`; supporting them needs h5py, to be added when such a file turns up.
- Map tables such as `data_wt` are not yet read as maps (postponed).

## Feature 2 notes (editing)

- `s.trim(lo, hi)`, `s.cut(lo, hi)` on a spectrum or a whole collection; `c.select(...)`, `c.drop(...)` by number (0 = first) or name. Each step is recorded in `history`.
- `stk.combine(*files_or_objects)` puts spectra from many files into one collection. Inputs can be file paths, spectra, collections, or a mix.
  1. Same x everywhere: stacked.
  2. Same x values but some spectra longer or with points missing (e.g. `CV+RhB+MB.xlsx`, where two columns have rows deleted): only x values present in all are kept; no value changes.
  3. Different x (shifted calibration, e.g. CV/RhB/MB files, shift up to 0.57 cm⁻¹): refused with a table of the axes unless `interpolate=True`. Then linear interpolation onto one reference axis, inside the common range only; refused if any spectrum has under 90 % of its range in common (`min_overlap`).
- Interpolation methods: `interpolate=True` (linear) or a name: "linear", "quadratic", "cubic" (or "spline"), "pchip", "akima" (all pass through the measured points). A single global polynomial is refused with an explanation (it oscillates badly over hundreds of points). `stk.resample(data, new_x, method=)` does the same for one spectrum or collection, and never extrapolates. On CV/RhB/MB the methods differ from linear by a median of 6-10 counts (noise level) and at most about 190 counts at the sharpest peaks (about 2 % of the peak height).
- Reference axis: the first spectrum, unless another has a clearly coarser step (> 5 %), then that one, so no detail is invented. Choose with `reference=`.
- `stk.check_axes(spectra)` gives the comparison table on its own (for a future "do you want to interpolate?" screen).
- Names: with several files, each name gets its file name in front ("CV10-4M: Spectrum 1"). Loader no longer uses axis titles such as "wavenumber" as spectrum names.

## Real data we test with (`data/`)

- `A_A_1.asc`: one Raman spectrum, 1,024 points, 100–3,646 cm⁻¹, two space-separated columns, Windows line endings.
- `MB 10-4M.xlsx`: 5 spectra as x/y column pairs, "Sample" label row, x descending from 1,803.
- `wt_raw.mat`: Renishaw map, 550 spectra × 747 points (`wt`, `W`) plus an X, Y, wavenumber, intensity table (`data_wt`).
- `mcr_kd_wt.opju`: Origin project; closed format, export to CSV from Origin instead.
- `CV+RhB+MB_data cliped from 1600 to 1700.xlsx`: 35 spectra as x/y pairs, 40 points, 1,600–1,700 cm⁻¹.
- `CV10-4M.xlsx`, `RhB10-4M.xlsx`: 14 and 11 spectra as x/y pairs; x axes shifted against each other and against `MB 10-4M.xlsx` by up to 0.57 cm⁻¹.
- `CV+RhB+MB.xlsx`: 35 x/y pairs, step 2.74 cm⁻¹, same grid but two columns have rows deleted in the middle.
- `SINGLECELL-KD_5_100mW_1-map_Copy.txt`: map, 1,116 spectra × 1,015 points as X, Y, Wave, Intensity rows (31 × 36 grid, 1.2 µm step). Map reading postponed.
- `main.m`, `separation1.tiff`: existing MATLAB PCA workflow and its figure (reference for later PCA work).
