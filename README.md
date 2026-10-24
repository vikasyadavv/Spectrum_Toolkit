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
s = stk.load("data/A_A_1.asc")       # text, Excel, .mat, Renishaw .wdf, Shimadzu .spc; prints what it read
s = s.trim(200, 1800)                # keep 200-1800 cm-1
stk.mat_variables("data/wt_raw.mat") # what a .mat file holds: every variable, its size, what fits
c = stk.combine("a.txt", "b.xlsx")   # several files -> one collection on one x axis
print(stk.about(c)["text"])          # file, facts, measurement, instrument settings, what was done
c = c.despike().baseline().smooth().normalize()   # defaults: single, airpls, savgol, snv
d = c.derivative(n=2)                # 2nd derivative (Savitzky-Golay)
c.plot("stack", xlabel="Raman shift (cm⁻¹)")       # also "lines", "mean", "image"
stk.line_colors(3, groups=["CV", "CV", "MB"])       # the colour each spectrum is drawn in: #1f77b4, ...
stk.compare(c, c.baseline(), 0)      # before/after of one step, with what was removed
ax = c.plot(style="matlab", aspect="square", box_width=2)       # any style setting by name
stk.export(ax, "fig1", folder="figures", format="tiff", dpi=1200, color="cmyk")
recipe = stk.Recipe.from_history(c)  # the processing chain above, as a recipe
recipe.save("my_recipe")             # -> my_recipe.json
new = stk.apply("new_file.xlsx", "my_recipe.json")    # load and process a new file in one line
```

See `notebooks/` for worked examples.

## Web service and Docker image

The website uses the toolkit through a small web service (`src/spectrum_toolkit/api.py`).

```bash
uv sync --extra api --extra plot
uv run uvicorn spectrum_toolkit.api:app --reload    # then open http://127.0.0.1:8000/docs
```

The same service in Docker (needs Docker Desktop on the Mac, or Docker on the VM):

```bash
docker build -t spectrum-toolkit .
openssl rand -hex 32 > key.txt                      # the secret key (on the VM: see docs/website.md)
docker run -d --name stk -p 127.0.0.1:8000:8000 -v "$PWD/key.txt:/run/secrets/stk_api_key:ro" \
    --restart unless-stopped spectrum-toolkit
curl http://127.0.0.1:8000/health                   # {"status":"ok","version":"0.0.1"} (no key needed)
curl -H "X-STK-Key: $(cat key.txt)" -F "file=@data/A_A_1.asc" http://127.0.0.1:8000/load
```

Settings: `-e STK_MAX_UPLOAD_MB=95`, `-e STK_ALLOWED_ORIGINS=https://cheminations.com,...`. The image
needs a secret key file (`-v key.txt:/run/secrets/stk_api_key:ro`) and refuses to start without one;
only the website's Cloudflare Worker (`worker/stk-worker.js`) knows the key. How the website reaches
the service, and how to set it up: `docs/website.md`.

## Layout

```
src/spectrum_toolkit/   the library (api.py: the web service)
Dockerfile              the Docker image of the web service
tests/                  automatic tests (pytest)
notebooks/              hands-on trials of each feature with real data
benchmarks/             scripts comparing the methods (fixed seeds)
scripts/                check_all_data.py: run everything on every file in data/
data/                   our real data files (local only, not in git)
worker/                 the Cloudflare Worker between the website and the service, and its tests
docs/website.md         how the website reaches the service, and how to set it up
docs/roadmap.md         features: proposed, agreed, done; decisions
docs/benchmarks.md      how the methods compare, and why the defaults (generated)
docs/dependencies.md    every dependency, its version, how to upgrade
docs/conventions.md     how code is commented and organised
CHANGELOG.md            what changed in each version
```

## How we work

One feature at a time: discuss → agree → build → test on real data → approve
→ commit. Each approved feature is recorded in `docs/roadmap.md`.
