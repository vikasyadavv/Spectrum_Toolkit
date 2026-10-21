# Spectrum Toolkit

A Python library to load, process and plot spectroscopic data. Raman is the
first use case, but nothing is Raman-only.

End goal: the library runs in a Docker container on our VM, and a web page on
cheminations.com talks to it. For now we build and test the library itself,
one feature at a time.

## Setup (once)

Needs [uv](https://docs.astral.sh/uv/). On a Mac:

```bash
brew install uv          # or: curl -LsSf https://astral.sh/uv/install.sh | sh
cd ~/Downloads/VSCode/Spectrum_Toolkit
uv sync                  # creates .venv with Python 3.13 and every dependency
```

## Everyday commands

```bash
uv run pytest            # run all tests
uv run jupyter lab       # open the notebooks to try features on real data
uv run python benchmarks/run_all.py   # rerun the method comparisons -> docs/benchmarks.md
```

In VS Code, pick `.venv/bin/python` as the interpreter / notebook kernel.

## Quick start

```python
import spectrum_toolkit as stk
s = stk.load("data/A_A_1.asc")       # text, Excel or .mat; prints what it read
s = s.trim(200, 1800)                # keep 200-1800 cm-1
c = stk.combine("a.txt", "b.xlsx")   # several files -> one collection on one x axis
c = c.despike().baseline().smooth().normalize()   # defaults: single, airpls, savgol, snv
d = c.derivative(n=2)                # 2nd derivative (Savitzky-Golay)
```

See `notebooks/` for worked examples.

## Layout

```
src/spectrum_toolkit/   the library
tests/                  automatic tests (pytest)
notebooks/              hands-on trials of each feature with real data
benchmarks/             scripts comparing the methods (fixed seeds)
data/                   our real data files (local only, not in git)
docs/roadmap.md         features: proposed, agreed, done; decisions
docs/benchmarks.md      how the methods compare, and why the defaults (generated)
docs/dependencies.md    every dependency, its version, how to upgrade
docs/conventions.md     how code is commented and organised
CHANGELOG.md            what changed in each version
```

## How we work

One feature at a time: discuss → agree → build → test on real data → approve
→ commit. Each approved feature is recorded in `docs/roadmap.md`.
