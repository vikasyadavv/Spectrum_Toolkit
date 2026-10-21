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
| 2026-10-21 | Method comparisons kept as scripts in `benchmarks/` that write `docs/benchmarks.md` | The numbers behind every default are saved, dated and can be rerun after any change. |
| 2026-10-21 | Recipes store every setting, defaults included | A saved recipe gives the same result even if a later version changes a default. |
| 2026-10-21 | Map files in long format are recognised and refused with a clear message until map loading is built | Before, the SINGLECELL map was silently read as 3 wrong spectra of 1.1 million points. |
| 2026-10-21 | Figure look = a style: a plain dict of named settings (presets clean, publication, matlab), storable as JSON | One place for every visual choice; users keep their own style file; the website can send the same JSON later. |
| 2026-10-21 | matplotlib only for plotting, as the optional extra `[plot]` | The web server will draw plots in the browser from the numbers; it should not need matplotlib. |
| 2026-10-21 | The Docker image runs a web service (FastAPI) that the website calls | The website stays a static page; all science runs in the container. Chosen over an image with notebooks only. |
| 2026-10-21 | The service keeps nothing: each request carries its data; uploads are deleted once read | No storage, no logins, nothing private left on the VM; any number of copies can run. |
| 2026-10-21 | Only cheminations.com may call the service from a browser (CORS); the container listens on 127.0.0.1 behind the VM's web server | Other websites cannot use our server; HTTPS stays with the existing web server. |
| 2026-10-21 | The image includes matplotlib, so the website can offer publication figures (tiff, CMYK, 1200 dpi) | Browser plots are for looking; exported figures need the same look as `stk.export`. |
| 2026-10-20 | Code commented line by line in plain English; every function documented | Anyone can read what each line does. See `conventions.md`. |

## Features

| # | Feature | Status |
|---|---|---|
| 0 | Project setup, core objects | approved 2026-10-20 |
| 1 | Loading data files, round 1: text and Excel (.xlsx, .xls) | approved 2026-10-20 |
| 1b | Loading .mat files (many variables, any names) | approved 2026-10-20 |
| 1d | Loading JCAMP-DX, SPC, JSON | proposed |
| 1c | Instrument files: Renishaw .wdf and others | later |
| 2 | Editing: trim, cut, select/drop spectra, combine files | approved 2026-10-21 |
| 3 | Cosmic-ray (spike) removal: `despike` | approved 2026-10-21 |
| 4 | Baseline correction: `baseline`, `find_baseline` (8 methods) | approved 2026-10-21 |
| 5 | Smoothing: `smooth` (7 methods) | approved 2026-10-21 |
| 6 | Normalisation: `normalize` (10 methods) | approved 2026-10-21 |
| 7 | Derivatives: `derivative` (4 methods, 1st and 2nd) | approved 2026-10-21 |
| - | Benchmarks: `benchmarks/run_all.py` → `docs/benchmarks.md` | approved 2026-10-21 |
| 8 | Plotting: `stk.plot` (lines, stack, mean, image), `stk.compare` (before/after) | approved 2026-10-21 (more options can be added later) |
| 9 | Recipes: `stk.Recipe`, `stk.apply` (save a processing chain as JSON, re-apply in one line) | approved 2026-10-21 |
| 10 | Docker image with a web service (`spectrum_toolkit.api`, `Dockerfile`) | built 2026-10-21, waiting for approval |
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

## Feature 3 notes (despike)

- `s.despike()` / `c.despike(method=...)`. Methods: "single" (default, each spectrum alone), "compare" (collections of repeats), "kalkan" (port of Vikas's MATLAB `spikeRemoval.m`, E. Kalkan 2019).
- "single": Anscombe transform (equal noise), candidates far above a running median AND sharp for their height (curvature / height > `sharpness`; a 1-point spike ≈ 2, a 5-point band ≈ 0.5), extent and repair from a quadratic through the neighbours, 2 passes. Builds on Whitaker & Hayes (2018).
- Settings: `threshold` (8), `width` (3), `sharpness` (1.0), `grow` (3), `passes` (2); kalkan: `window` 25, `nstd` 3, `ndata` 5, `nbins` 4.
- Comparison on simulated spectra: [benchmarks.md](benchmarks.md#cosmic-ray-removal-despike). "single" repairs 94 % of strong spikes with false alarms in 1 % of spectra; kalkan 59 % with 7 %.

- Real data: "single" and "compare" find exactly the cosmic rays in CV10-4M.xlsx (spectrum 4 at 1635 and 1696-1702, spectrum 11 at 313-315) and one in CV+RhB+MB.xlsx (spectrum 25 at 1026-1028); nothing in RhB, MB, A_A_1 or the 550-spectrum map. "kalkan" changes 50 places in the 14 CV spectra, mostly noise and the last 10 points of each spectrum (it always replaces points near the ends), misses the spike at 1635 and leaves part of the one at 1700.
- Limit: a spike as wide as a real band cannot be told apart in a single spectrum; use "compare" with repeats.

## Feature 4 notes (baseline)

- Written ourselves with numpy/scipy (decided 2026-10-21: no pybaselines), every method referenced in `baseline.py`.
- `s.baseline(method, **settings)` subtracts; `stk.find_baseline(...)` returns the baseline to plot. Default "airpls".
- Methods and defaults: asls (lam 1e5, p 0.005, 10 rounds: identical to `baseline.m`, checked to 1e-6), iasls (lam 1e4), arpls (lam 1e6), airpls (lam 1e6), modpoly / imodpoly (order 5), rollingball / snip (window 100, in x units).
- Comparison on simulated spectra, with the effect of each method's main setting: [benchmarks.md](benchmarks.md#baseline-correction). airpls has the lowest error on all three background types.

- `lam` depends on point spacing: denser points need a larger `lam` for the same stiffness.
- Data quirk: in `wt_raw.mat` the last 2 points of every spectrum are about 0 (detector edge); trim them (`c.trim(441, 1818)`) before baseline, otherwise the baseline is pulled down at the end.

## Feature 5 notes (smoothing)

- `s.smooth(method, **settings)`; default "savgol" (window 15, order 4). Windows are in points.
- Methods and defaults: savgol (15, 4), whittaker (lam 3), spline (lam None = automatic, by generalised cross-validation), gaussian (sigma 1), moving (5), median (5), fourier (cutoff 0.25).
- Comparison on simulated spectra, with the effect of the settings: [benchmarks.md](benchmarks.md#smoothing).

- Savitzky-Golay with window 11, order 3 (a common choice) gave 0.65 and 6.8 %; window 15, order 4 is better on both, so it is the default.
- "spline" adapts to each spectrum: it smooths the noisy map spectra more and the clean CV spectra less, with no setting.

## Feature 6 notes (normalisation)

- `s.normalize(method, **settings)`; default "snv". Usually after despike and baseline.
- One spectrum at a time: max, minmax, area, vector, snv, rsnv (robust SNV: median and MAD), band (height or area of one band above a local straight line, `region=` required: the internal-standard method). All take `region=(lo, hi)` to compute the factor from that range only.
- Several spectra together: msc, emsc (MSC plus a polynomial background, `order` 2), pqn (probabilistic quotient). Reference: mean (msc, emsc) or median (pqn) of the collection, or `reference=` (needed for a single spectrum).
- Comparison on simulated replicates (scale, offset, slope, one band really changing) and on the CV/RhB/MB repeats: [benchmarks.md](benchmarks.md#normalisation). Summary: all fix a pure scale change; offsets need snv/msc/emsc; sloping backgrounds need emsc; when some bands change, use pqn or an internal-standard band. On real CV repeats every method brings the spread from 42 % to 16-19 %.
- Default kept as snv: works on one spectrum, handles offsets, and is never far from the best. emsc is the best choice for a set of spectra with backgrounds.

## Feature 7 notes (derivatives)

- `s.derivative(method, n=1 or 2, **settings)`; default "savgol". Result in y per x unit (y_unit becomes e.g. `d(counts)/d(cm-1)`).
- Methods: savgol, gaussian, spline (automatic smoothing), gradient (plain finite differences).
- Defaults depend on n, chosen from the comparison against exact derivatives of Lorentzian bands: savgol window 15 / order 5 (n=1), window 11 / order 4 (n=2); gaussian sigma 1.25 / 1.5. Any setting given by the user is used instead. Tuned for bands of about 7-17 points.
- Unevenly spaced points (> 1 % variation): savgol/gaussian work on an even grid and map back (`regridded=True` in history); spline and gradient use the real x.
- Comparison: [benchmarks.md](benchmarks.md#derivatives). savgol is best (13 % error for n=1, 35 % for n=2); spline matches it for n=1 but not n=2.

## Feature 8 notes (plotting)

- `stk.plot(*data, kind=...)` or `s.plot()` / `c.plot()`: kinds "lines" (default), "stack" (automatic offset, 60 % of the median spectrum height), "mean" (mean ± 1 SD per collection), "image" (one row per spectrum; colour limits at the 1st/99th percentile so one bright spectrum does not hide the rest).
- Many spectra: above 10 no legend and colours from a colour map; above 200 drawn as one LineCollection (550-spectrum map in well under a second).
- `stk.compare(before, after, index)`: one spectrum before and after the last step, with a "removed" panel (before - after). Spikes removed by despike are shaded; for baseline the baseline is drawn; for normalize and derivative the result goes on its own right-hand y axis and there is no removed panel. Title = the step and its settings from history.
- Shared settings: `region=(lo, hi)` (y follows the data in view), `xlabel`, `title`, `invert_x`, `style` ("clean" default, "publication", "matplotlib" or a dict), `save=` (300 dpi), `ax=` to draw into an existing figure. Every call returns the Axes.
- Axis labels come from `x_unit` / `y_unit`; text and Excel files carry no units, so pass `xlabel="Raman shift (cm⁻¹)"`. (Possible later: remember a default x label.)
- Round 2 (Vikas, 2026-10-21: customisation is user to user; likes "publication"; wants MATLAB colours, square axes, export options; see `main.m`, `separation1.tiff`):
  - `spectrum_toolkit/style.py`: 40 named settings (`stk.style.SETTINGS`) for size (cm or inches, or "screen", "single" and "double" column, "square", "slide"), aspect ("square" or a ratio), font, sizes and weights, box ("closed", "open", "none") with width and colour, ticks (in/out/both, length, width, colour, which sides have ticks and which have numbers, minor ticks, spacing, number format), grid, line width and style (solid, dashed, dotted, markers only), colours ("matlab", "matplotlib", "colorblind", "black" or a list), legend (location incl. outside, size, bold, box), zero lines, dpi, file type and colour mode.
  - Presets "clean", "publication", "matlab" (from main.m: bold Arial 15/18, grey box width 2 with black tick labels, ticks in, square, MATLAB colours, legend without box, 1200 dpi tiff), "matplotlib".
  - Any plot call takes `style=` plus any setting by name; `stk.set_style` sets the session default; `stk.save_style` writes a JSON file to reuse.
  - `stk.export(ax, name, folder=, format=, dpi=, color="rgb"|"cmyk", transparent=)`: png, tiff (LZW-compressed), jpg, pdf, svg, eps. CMYK for tiff and jpg, converted with a simple formula (no printer profile).
  - `stk.scatter(x, y, groups)`: like MATLAB's gscatter, for PCA scores later; the separation1 figure is rebuilt in notebook 10.
  - Extras: `peaks=N` labels the N most prominent bands (position refined between points), `marks={1585: "C=C"}` labelled reference lines, missing fonts fall back quietly (Arial → Liberation Sans on Linux).
  - Notebook 10: a style editor (tabs for figure, box and ticks, text, lines, grid and legend, export) with Export and Save style buttons.
- Not yet: map images by X/Y position (waits for map loading), interactive plots for the website (those will be drawn in the browser).

## Feature 9 notes (recipes)

- `Recipe.from_history(data)`: everything done to data that can be repeated elsewhere (trim, cut, despike, baseline, smooth, normalize, derivative). select/drop (by name), combine and resample are left out and listed in `recipe.skipped`, with the reason.
- `Recipe().despike().trim(200, 1750).baseline("asls", lam=1e5)...`: step by step; settings are checked at once, and every setting is stored with its default filled in.
- `recipe.save("name")` writes readable JSON (name, description, date, toolkit version, steps); `Recipe.load`. `recipe.apply(data or file path)`, `stk.apply(data, "recipe.json")`, `data.apply(recipe)`. A file of x/y pairs with gaps is joined automatically; different x axes ask for `stk.combine(..., interpolate=True)` first.
- `recipe.run(data)` returns the data after each step, for `stk.compare` plots. An error names the step that failed.
- normalize with a reference spectrum: the builder stores the reference numbers; from history it cannot (only "given" is recorded), so it is skipped.

## Feature 10 notes (Docker image and web service)

- `src/spectrum_toolkit/api.py`: GET `/health`, GET `/options` (every method with defaults and explanation, every style setting, preset, palette, size: what the website needs to build its forms), POST `/load` (upload a file), POST `/process` (data + recipe steps as JSON; `all_steps` returns the data after each step for before/after views), POST `/process-file` (upload + recipe in one call), POST `/figure` (data + kind + style + settings → png, tiff, jpg, pdf, svg or eps file). Interactive description of every endpoint at `/docs` while it runs.
- Data format (requests and answers): `{"x": [...], "Y": [[...], ...], "names": [...], "x_unit", "y_unit", "history"}`. Missing values come back as `null`.
- Mistakes (unknown method, wrong setting, unreadable file, a map file) answer HTTP 422 with the library's own message; uploads over `STK_MAX_UPLOAD_MB` (default 200) answer 413. Files with different x axes come back as separate spectra with a message, never interpolated silently.
- `Dockerfile`: two stages; the exact versions from `uv.lock`, without dev tools; Liberation fonts (Arial-compatible, for the matlab style); runs as an ordinary user; 2 worker processes; Docker health check on `/health`. Image ≈ 530 MB on disk (124 MB download).
- Tested 2026-10-21 in the built image: every file in `data/` through `/load` (the .m files and the map answer 422 with clear messages; the 51 MB map in 5 s), a 4-step recipe on all 550 spectra of `wt_raw.mat` in 0.6 s, figures of every kind (600 dpi CMYK tiff 1.8 s). 20 tests in `tests/test_api.py`.
- Seen on real data: the last 2 points of every spectrum in `wt_raw.mat` are near 0 (the raw counts are about 960), which makes a cliff at 1820 cm⁻¹ after processing. Trim them (`trim(None, 1818)`) until an automatic dead-point check is agreed.
- Not yet: putting it on the VM and the website page (each needs approval); map files.

## Bug hunt on all real data (2026-10-21)

`scripts/check_all_data.py` runs every method of every feature, every plot kind and style, before/after views and recipes (save, load, re-apply, compare) on every file in `data/`, plus edge cases (10 points, flat, one-spectrum collection, descending x). Found and fixed:

- Loading left the file open (a ResourceWarning on every file): fixed.
- The SINGLECELL map (X, Y, Wave, Intensity rows) was read as 3 spectra of 1.1 million points; derivatives then gave infinities and two baseline methods crashed. Now recognised as a map with a clear message (1116 positions × 1015 points).
- Repeated x values made derivatives, spline smoothing and rollingball/snip fail with unclear errors: now one clear message.
- `normalize("band")` on a region without a band said "band height is zero": now explains how to choose the region.
- Peak labels could warn on repeated x: fixed.
- Recipe on a file of x/y pairs failed: such files are now joined automatically when they share x values.

After the fixes: no failures, warnings or non-finite results; only the expected "not a spectrum file" messages (.m, .opju) and the map message.

## Real data we test with (`data/`)

- `A_A_1.asc`: one Raman spectrum, 1,024 points, 100–3,646 cm⁻¹, two space-separated columns, Windows line endings.
- `MB 10-4M.xlsx`: 5 spectra as x/y column pairs, "Sample" label row, x descending from 1,803.
- `wt_raw.mat`: Renishaw map, 550 spectra × 747 points (`wt`, `W`) plus an X, Y, wavenumber, intensity table (`data_wt`).
- `mcr_kd_wt.opju`: Origin project; closed format, export to CSV from Origin instead.
- `CV+RhB+MB_data cliped from 1600 to 1700.xlsx`: 35 spectra as x/y pairs, 40 points, 1,600–1,700 cm⁻¹.
- `CV10-4M.xlsx`, `RhB10-4M.xlsx`: 14 and 11 spectra as x/y pairs; x axes shifted against each other and against `MB 10-4M.xlsx` by up to 0.57 cm⁻¹.
- `CV+RhB+MB.xlsx`: 35 x/y pairs, step 2.74 cm⁻¹, same grid but two columns have rows deleted in the middle.
- `SINGLECELL-KD_5_100mW_1-map_Copy.txt`: map, 1,116 spectra × 1,015 points as X, Y, Wave, Intensity rows (31 × 36 grid, 1.2 µm step). Map reading postponed.
- `spikeRemoval.m` (E. Kalkan, histogram despiking) and `baseline.m` (asymmetric least squares, Eilers & Boelens 2005): the MATLAB methods in use so far.
- `main.m`, `separation1.tiff`: existing MATLAB PCA workflow and its figure (reference for later PCA work).
