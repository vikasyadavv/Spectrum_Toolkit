# Dependencies and upgrading

## How versions are managed

- `pyproject.toml` states the **minimum** versions we support (e.g. `numpy>=1.26`).
- `uv.lock` records the **exact** version of every package, including indirect
  ones, for every platform. `uv sync` installs exactly these, so your Mac, the
  Docker image and the VM all run identical code.
- `.python-version` pins the Python version for development (3.13). The library
  itself supports Python 3.11 and newer.

Never edit `uv.lock` by hand. Change it only with the commands below.

## Current direct dependencies (locked 2026-10-20)

pandas is deliberately not used: our objects hold numpy arrays, and editing
rows (trim, add, delete) will be methods on `Spectrum`/`SpectrumCollection`.
Revisit if table editing grows beyond that.

| Package | Locked | Minimum | Used for | Needed at runtime? |
|---|---|---|---|---|
| numpy | 2.5.4 | 1.26 | arrays, all numerical work | yes |
| scipy | 1.18.1 | 1.11 | filters, sparse solvers, `.mat` files | yes |
| openpyxl | 3.1.5 | 3.1 | reading `.xlsx` spreadsheets | yes |
| xlrd | 2.0.2 | 2.0 | reading old `.xls` spreadsheets (v2 reads only .xls) | yes |
| pytest | 9.1.1 | 8 | automatic tests | dev only |
| jupyterlab | 4.6.4 | 4 | notebooks for trying features | dev only |
| matplotlib | 3.11.2 | 3.8 | `stk.plot`, `stk.compare`, `stk.scatter`, `stk.export`, notebooks; brings Pillow (tiff, jpg, CMYK) and cycler with it | optional extra `[plot]` (and dev); the library works without it |
| ipywidgets | 8.1.9 | 8 | tick boxes and sliders in notebooks | dev only |

Python: 3.13 for development (matches the Mac setup), 3.11+ supported.

To see the full tree, including indirect packages: `uv tree`.
To see what could be upgraded: `uv tree --outdated`.

## Adding a dependency

Every new dependency is agreed first and recorded in the table above with its reason.

```bash
uv add pandas            # runtime dependency
uv add --dev ruff        # development-only tool
```

## Upgrading

Upgrade on a separate git branch, run the tests, then merge.

```bash
git switch -c upgrade-deps
uv lock --upgrade                    # everything to the newest allowed versions
# or one package only:
uv lock --upgrade-package numpy
uv sync
uv run pytest                        # must pass before merging
git commit -am "Upgrade dependencies"
```

Then update the "Locked" column above and add a line to `CHANGELOG.md`.

To upgrade Python itself: change `.python-version` (e.g. to `3.14`), run
`uv sync`, run the tests.

If something breaks: `git switch main` and `uv sync` puts the previous exact
versions back.
