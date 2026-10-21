# Testing every feature through the web page (/docs)

We test one item at a time on the VM through http://127.0.0.1:8100/docs
(ssh tunnel open). Tick an item when the result looks right; write what was
wrong next to it otherwise.

How to use the page, for every test:
- **Upload tests** (A, B): open the endpoint, "Try it out", choose the file,
  fill the boxes as written, "Execute", read "Server response".
- **Recipe tests** (C to H): `/process-file`, choose the file, put the recipe
  text in the recipe box, "Execute". Code 200 = it ran; the numbers are in
  the response, and the last entry of "history" shows the step and every
  setting it used.
- **Figure tests** (I to L): after a recipe test, copy its Response body,
  paste it into `/figure` (replacing everything), add the line given at the
  top after `{`, "Execute", "Download file".
- The default file for every test is `CV10-4M.xlsx` (14 spectra) unless said.

## A. Loading files (`/load`)

Every answer starts with the sizes: `n_spectra`, `n_points`, `size_Y` [spectra, points]
and `size_x`, then names, notes and history, and the numbers last. Set
`summary_only` to true for big files (wt_raw.mat) so the page does not freeze.

- [ ] A1 `A_A_1.asc` → 1 spectrum, 1024 points
- [ ] A2 `CV10-4M.xlsx` → 14 spectra, 1424 points
- [ ] A3 `MB 10-4M.xlsx` → 5 spectra; `RhB10-4M.xlsx` → 11 spectra
- [ ] A4 `CV+RhB+MB.xlsx` → 35 spectra, 618 points
- [ ] A5 `CV+RhB+MB_data cliped from 1600 to 1700.xlsx` → 35 spectra, 40 points
- [ ] A6 `wt_raw.mat` with summary_only = true → size_Y [550, 747]; "notes" says which variables were used
- [ ] A7 `baseline.m` → code 422, "No numeric data found"
- [ ] A8 the SINGLECELL map file → code 422, "looks like a map" (takes a few seconds)
- [ ] A9 an empty text file → 422 "The uploaded file is empty"

## B. Information (`/health`, `/options`)

- [ ] B1 `/health` → `{"status":"ok","version":"0.0.1"}`
- [ ] B2 `/options` → every method of every step with its default settings and explanation

## C. Editing: trim and cut

- [ ] C1 `{"steps":[{"step":"trim","lo":400,"hi":1800}]}` → x from 400 to 1800 only
- [ ] C2 `{"steps":[{"step":"cut","lo":1000,"hi":1100}]}` → the 1000-1100 region is gone

## D. Spike removal (despike), 3 methods

- [ ] D1 `{"steps":[{"step":"despike"}]}` (single, the default)
- [ ] D2 `{"steps":[{"step":"despike","method":"compare"}]}` (needs several spectra)
- [ ] D3 `{"steps":[{"step":"despike","method":"kalkan"}]}`
- [ ] D4 a setting: `{"steps":[{"step":"despike","threshold":5}]}` (more sensitive)
- [ ] D5 D1 on CV10-4M.xlsx: the last "history" entry lists the spikes it removed (in Spectrum 4 and Spectrum 11). wt_raw.mat has none.

## E. Baseline, 8 methods

Recipe: `{"steps":[{"step":"baseline","method":"NAME"}]}` with NAME =

- [ ] E1 airpls (the default; `{"step":"baseline"}` alone does the same)
- [ ] E2 asls  - [ ] E3 iasls  - [ ] E4 arpls
- [ ] E5 modpoly  - [ ] E6 imodpoly  - [ ] E7 rollingball  - [ ] E8 snip
- [ ] E9 a setting: `{"step":"baseline","method":"asls","lam":1e6,"p":0.01}`
- [ ] E10 a wrong name: `"method":"magic"` → 422 listing the 8 methods

## F. Smoothing, 7 methods

Recipe: `{"steps":[{"step":"smooth","method":"NAME"}]}` with NAME =

- [ ] F1 savgol (default)  - [ ] F2 whittaker  - [ ] F3 spline  - [ ] F4 gaussian
- [ ] F5 moving  - [ ] F6 median  - [ ] F7 fourier
- [ ] F8 a setting: `{"step":"smooth","method":"savgol","window":25,"order":3}`

## G. Normalisation, 10 methods

Recipe: `{"steps":[{"step":"normalize","method":"NAME"}]}` with NAME =

- [ ] G1 snv (default)  - [ ] G2 max  - [ ] G3 minmax  - [ ] G4 area
- [ ] G5 vector  - [ ] G6 rsnv  - [ ] G7 msc  - [ ] G8 emsc  - [ ] G9 pqn
- [ ] G10 band: `{"step":"normalize","method":"band","region":[1600,1640]}` (pick a band of your sample)
- [ ] G11 region for one-factor methods: `{"step":"normalize","method":"max","region":[1500,1700]}`

## H. Derivatives, 4 methods, 1st and 2nd

- [ ] H1 `{"steps":[{"step":"derivative"}]}` (savgol, 1st)
- [ ] H2 `{"steps":[{"step":"derivative","n":2}]}` (2nd)
- [ ] H3 `"method":"gaussian"`  - [ ] H4 `"method":"spline"`  - [ ] H5 `"method":"gradient"`

## H+. A full recipe

- [ ] H6 `{"steps":[{"step":"despike"},{"step":"trim","lo":400,"hi":1800},{"step":"baseline"},{"step":"smooth"},{"step":"normalize"}]}`
- [ ] H7 the same on `wt_raw.mat` (550 spectra)
- [ ] H8 `/process` with `"all_steps": true` → the data after every step

## I. Figure kinds (add at the top of /figure)

- [ ] I1 `"kind": "lines",`
- [ ] I2 `"kind": "stack",`
- [ ] I3 `"kind": "mean",` (mean ± spread)
- [ ] I4 `"kind": "image",` (all spectra as a colour map; best with wt_raw.mat)

## J. Styles

- [ ] J1 `"style": "clean",`
- [ ] J2 `"style": "publication",`
- [ ] J3 `"style": "matlab",` (MATLAB colours, square, bold)
- [ ] J4 one setting changed: `"settings": {"line_width": 2.5, "box_width": 2},`
- [ ] J5 colours and line type: `"settings": {"colors": "colorblind", "line_style": "--"},`
- [ ] J6 axes: `"settings": {"aspect": "square", "ticks": "out", "grid": true},`
- [ ] J7 size: `"settings": {"size": "single"},` (8.5 cm journal column)

## K. Labels and marks

- [ ] K1 `"title": "CV 10-4 M", "xlabel": "Raman shift (cm⁻¹)", "ylabel": "Intensity",`
- [ ] K2 `"region": [1000, 1700],` (zoom)
- [ ] K3 `"peaks": 5,` (labels the 5 strongest peaks)
- [ ] K4 `"marks": {"1620": "C=C"},`
- [ ] K5 `"highlight": 0,` (first spectrum stands out)
- [ ] K6 `"invert_x": true,`

## L. File formats and quality

- [ ] L1 `"format": "png", "dpi": 300,`
- [ ] L2 `"format": "tiff", "dpi": 600,`
- [ ] L3 `"format": "tiff", "dpi": 1200, "color": "cmyk",` (journal print)
- [ ] L4 `"format": "pdf",`  - [ ] L5 `"format": "svg",`  - [ ] L6 `"format": "eps",`
- [ ] L7 `"format": "jpg",`
- [ ] L8 `"transparent": true, "format": "png",`
- [ ] L9 `"name": "my_figure",` → the downloaded file is my_figure.png

## Not reachable from the page yet

These work in Python (notebooks) but have no endpoint yet. Say which ones
the website needs and they get added:

- combining several files into one set; selecting or dropping spectra by name; resample
- before/after view of one step (`stk.compare`), grouped scatter (`stk.scatter`)
- saving a recipe or a style to a file (the website would keep these itself)
