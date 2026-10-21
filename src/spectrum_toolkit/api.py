"""Web service: lets the website (cheminations.com) use the toolkit.

The website sends files and settings; the service answers with numbers
(JSON) or a finished figure. It keeps nothing: every request carries what it
needs, and uploaded files are deleted as soon as they are read.

Endpoints
---------
GET  /health        "ok" and the toolkit version (for the server's health check).
GET  /options       every processing method with its default settings, every
                    style setting, preset, palette and size: what the website
                    needs to build its forms.
POST /load          upload a file (form field "file"); returns the spectra.
POST /process       JSON {"data": ..., "recipe": {"steps": [...]}}: applies
                    the steps; with "all_steps": true also returns the data
                    after every step (for before/after views).
POST /process-file  upload a file plus a recipe (form field "recipe", JSON
                    text): load and process in one call.
POST /figure        JSON {"data": ..., "kind": "lines", "style": "publication",
                    "settings": {...}, "format": "tiff", "dpi": 600, ...}:
                    returns the figure as a file (png, tiff, jpg, pdf, svg, eps).

Data in requests and answers looks like this (one row of "Y" per spectrum)::

    {"x": [...], "Y": [[...], ...], "names": ["Spectrum 1", ...],
     "x_unit": "", "y_unit": "", "history": [...]}

Mistakes in a request (unknown method, wrong setting, unreadable file) give
HTTP 422 with the same plain-English message the library gives.

Run locally::

    uv run --extra api --extra plot uvicorn spectrum_toolkit.api:app --reload
    # then open http://127.0.0.1:8000/docs for an interactive page of every endpoint

Settings (environment variables)
--------------------------------
STK_MAX_UPLOAD_MB      largest accepted upload, default 200.
STK_ALLOWED_ORIGINS    websites allowed to call the service from a browser,
                       comma separated; default the cheminations.com addresses.
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any, Literal

import numpy as np

try:
    from fastapi import Body, FastAPI, File, Form, HTTPException, Request, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, Response
except ImportError as e:                                         # only the web service needs FastAPI
    raise ImportError('The web service needs: pip install "spectrum-toolkit[api]"') from e

from . import __version__
from .core import Spectrum, SpectrumCollection
from .io import load
from .recipe import Recipe

MAX_UPLOAD = int(os.environ.get("STK_MAX_UPLOAD_MB", "200")) * 1024 * 1024
ORIGINS = [o.strip() for o in os.environ.get(
    "STK_ALLOWED_ORIGINS", "https://cheminations.com,https://www.cheminations.com").split(",") if o.strip()]

# matplotlib keeps global state (current figure, style settings), so only one
# request at a time may draw; processing requests run side by side.
_FIGURE_LOCK = threading.Lock()

app = FastAPI(title="Spectrum Toolkit", version=__version__,
              description="Load, process and plot spectroscopic data. See the module description of "
                          "spectrum_toolkit.api for the data format.")
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["GET", "POST"], allow_headers=["*"])


@app.exception_handler(ValueError)
async def _value_error(request: Request, exc: ValueError):
    """Library errors are the user's to fix: answer 422 with the message."""
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def _unexpected_error(request: Request, exc: Exception):
    """Anything else is a bug in the toolkit: answer 500 with what went wrong
    (instead of a bare "Internal Server Error"), so it can be reported and fixed."""
    return JSONResponse(status_code=500, content={
        "detail": f"Unexpected error, please report it: {type(exc).__name__}: {exc}"})


# ------------------------------------------------------------------ data <-> JSON
def _numbers(a: np.ndarray) -> list:
    """Array to a JSON list; missing or infinite values become null (JSON has no NaN)."""
    if np.all(np.isfinite(a)):
        return a.tolist()
    return [[None if not math.isfinite(v) else v for v in row] if isinstance(row, list)
            else (None if not math.isfinite(row) else row) for row in a.tolist()]


def _plain(value: Any) -> Any:
    """History entries to plain JSON values (numpy numbers, tuples, arrays)."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return _numbers(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def to_json(data: Spectrum | SpectrumCollection) -> dict:
    """A Spectrum or collection as the JSON data format (always with a list of rows)."""
    if isinstance(data, Spectrum):
        Y, names = data.y[None, :], [data.name]
    else:
        Y, names = data.Y, list(data.names)
    out = {"x": _numbers(data.x), "Y": _numbers(Y), "names": names, "x_unit": data.x_unit,
           "y_unit": data.y_unit, "history": _plain(list(data.history))}
    notes = data.meta.get("load_notes") if isinstance(data.meta, dict) else None
    if notes:
        out["notes"] = list(notes)
    return out


def from_json(d: dict) -> SpectrumCollection:
    """The JSON data format back to a collection (missing values must not be sent)."""
    if not isinstance(d, dict) or "x" not in d or "Y" not in d:
        raise ValueError('data must be {"x": [...], "Y": [[...], ...]} (one row of Y per spectrum).')
    Y = np.asarray(d["Y"], dtype=float)
    if Y.ndim == 1:
        Y = Y[None, :]
    if not np.all(np.isfinite(Y)):
        raise ValueError("data contains missing values (null); remove those points first.")
    return SpectrumCollection(d["x"], Y, names=d.get("names") or (), x_unit=d.get("x_unit", ""),
                              y_unit=d.get("y_unit", ""), history=tuple(d.get("history") or ()))


def _single_or_all(c: SpectrumCollection) -> Spectrum | SpectrumCollection:
    """One-spectrum collections are processed as a Spectrum (some methods differ, e.g. despike)."""
    return c[0] if len(c) == 1 else c


def _blank_to_none(value: str | None) -> str | None:
    """Form boxes left empty arrive as "" (or spaces): treat them as not given."""
    return value.strip() or None if value is not None else None


# ------------------------------------------------------------------ uploads
_SAFE = re.compile(r"[^A-Za-z0-9._+ -]")


async def _save_upload(file: UploadFile, folder: Path) -> Path:
    """Write an upload to a private temporary folder, refusing files that are too big.

    The file keeps its own name (made safe: no folders, no odd characters),
    because the name's extension helps to recognise the format and becomes
    the spectrum name.
    """
    name = _SAFE.sub("_", Path(file.filename or "upload").name)[:120] or "upload"
    path = folder / name
    size = 0
    with path.open("wb") as out:
        while chunk := await file.read(1024 * 1024):             # 1 MB at a time: big files never sit in memory
            size += len(chunk)
            if size > MAX_UPLOAD:
                raise HTTPException(413, f"File larger than {MAX_UPLOAD // (1024 * 1024)} MB.")
            out.write(chunk)
    if size == 0:
        raise ValueError("The uploaded file is empty.")
    return path


def _load_answer(result) -> dict:
    """Answer of /load: one data set, or separate spectra when their x axes differ."""
    if isinstance(result, list):
        from .edit import check_axes, combine
        try:                                                    # same x values (gaps allowed): join, nothing changes
            joined = combine(*result, verbose=False)
            return {"data": to_json(joined), "separate": None}
        except ValueError as e:
            report = check_axes(result)
            return {"data": None, "separate": [to_json(s) for s in result],
                    "message": f"The spectra have different x axes ({report.case}); "
                               f"choose how to put them on one axis. {e}"}
    return {"data": to_json(result), "separate": None}


# ------------------------------------------------------------------ examples
# Shown ready-filled on the /docs page, so "Try it out" works without typing.
EXAMPLE_RECIPE = '{"steps": [{"step": "despike"}, {"step": "baseline"}, {"step": "normalize"}]}'
_TINY = {"x": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
         "Y": [[1, 2, 4, 9, 15, 9, 4, 2, 1, 1], [1, 1, 3, 7, 12, 8, 3, 2, 1, 1]],
         "names": ["a", "b"], "x_unit": "cm-1", "y_unit": "counts"}
EXAMPLE_PROCESS = {"data": _TINY, "recipe": {"steps": [{"step": "normalize", "method": "max"}]}, "all_steps": False}
EXAMPLE_FIGURE = {"data": _TINY, "kind": "lines", "style": "publication", "settings": {"line_width": 1.5},
                  "title": "Example", "format": "png", "dpi": 300, "name": "example"}


# ------------------------------------------------------------------ endpoints
@app.get("/health")
def health() -> dict:
    """For the server's health check."""
    return {"status": "ok", "version": __version__}


@app.get("/options")
def options() -> dict:
    """Every method with its default settings, and every style setting."""
    import importlib
    import inspect

    from . import style
    from .recipe import _DESPIKE
    from .despike import despike as _despike_fn
    steps = {}
    for name in ("baseline", "smooth", "normalize", "derivative"):
        module = importlib.import_module(f"spectrum_toolkit.{name}")
        steps[name] = {"methods": _plain(module.DEFAULTS), "doc": (module.__doc__ or "").strip()}
    defaults = {k: p.default for k, p in inspect.signature(_despike_fn).parameters.items()}
    steps["despike"] = {"methods": {m: {k: defaults[k] for k in sorted(keys)} for m, keys in _DESPIKE.items()},
                        "doc": (importlib.import_module("spectrum_toolkit.despike").__doc__ or "").strip()}
    steps["trim"] = {"methods": {"": {"lo": None, "hi": None}}, "doc": "Keep lo <= x <= hi."}
    steps["cut"] = {"methods": {"": {"lo": None, "hi": None}}, "doc": "Remove lo <= x <= hi."}
    return {
        "version": __version__,
        "steps": steps,
        "style": {"settings": {k: {"default": _plain(v), "meaning": m} for k, (v, m) in style.SETTINGS.items()},
                  "presets": {k: _plain(v) for k, v in style.PRESETS.items()},
                  "palettes": _plain(style.PALETTES), "sizes_cm": _plain(style.SIZES)},
        "figure_kinds": ["lines", "stack", "mean", "image"],
        "figure_formats": ["png", "tiff", "jpg", "pdf", "svg", "eps"],
        "max_upload_mb": MAX_UPLOAD // (1024 * 1024),
    }


@app.post("/load")
async def load_file(file: UploadFile = File(...),
                    sheet: str | None = Form(None, examples=[""], description=(
                        "Excel files only; ignored for other files. Empty: the sheet with the most "
                        "numbers is read (the answer's notes say which). Or a sheet name (Sheet1) "
                        "or number (1 = first sheet).")),
                    layout: Literal["auto", "y", "xy", "pairs", "shared"] = Form("auto", description=(
                        "How the columns are arranged. auto: detected (the answer's notes say what "
                        "was found). y: one column of intensities. xy: x column, y column. "
                        "pairs: x, y, x, y, ... one pair per spectrum. shared: one x column, "
                        "then one y column per spectrum."))) -> dict:
    """Read an uploaded file: text, Excel or .mat (.mat files ignore sheet and layout)."""
    sheet = _blank_to_none(sheet)                                # an empty box means "not given"
    layout = None if layout == "auto" else layout                # None = let the reader detect it
    if sheet is not None and sheet.isdigit():                    # "2" from a form is sheet number 2
        sheet = int(sheet)
    with tempfile.TemporaryDirectory() as folder:               # deleted with everything in it afterwards
        path = await _save_upload(file, Path(folder))
        result = load(path, sheet=sheet, layout=layout, verbose=False)
    return _load_answer(result)


@app.post("/process")
def process(body: dict = Body(..., examples=[EXAMPLE_PROCESS])) -> dict:
    """Apply a recipe to data sent as JSON."""
    data = _single_or_all(from_json(body.get("data")))
    recipe = Recipe(body.get("recipe", {}).get("steps", []))
    if body.get("all_steps"):
        steps = recipe.run(data)
        return {"data": to_json(steps[-1][1]), "steps": [{"step": n, "data": to_json(d)} for n, d in steps]}
    return {"data": to_json(recipe.apply(data))}


@app.post("/process-file")
async def process_file(file: UploadFile = File(...), recipe: str = Form(..., examples=[EXAMPLE_RECIPE],
                       description="The processing steps as JSON text, e.g. " + EXAMPLE_RECIPE)) -> dict:
    """Load an uploaded file and apply a recipe (JSON text) in one call."""
    try:
        steps = json.loads(recipe)
    except json.JSONDecodeError as e:
        raise ValueError(f"recipe must be JSON text such as {EXAMPLE_RECIPE} ({e}).") from e
    r = Recipe(steps.get("steps", []) if isinstance(steps, dict) else steps)
    with tempfile.TemporaryDirectory() as folder:
        path = await _save_upload(file, Path(folder))
        result = r.apply(path)
    return {"data": to_json(result)}


_TYPES = {"png": "image/png", "tiff": "image/tiff", "jpg": "image/jpeg", "pdf": "application/pdf",
          "svg": "image/svg+xml", "eps": "application/postscript"}


@app.post("/figure")
def figure(body: dict = Body(..., examples=[EXAMPLE_FIGURE])) -> Response:
    """Draw data and return the figure file."""
    import matplotlib
    matplotlib.use("Agg")                                       # no screen on a server
    import matplotlib.pyplot as plt

    from .plot import plot
    from .style import export

    data = _single_or_all(from_json(body.get("data")))
    fmt = str(body.get("format", "png")).lower()
    if fmt not in _TYPES:
        raise ValueError(f"Unknown format {fmt!r}. Choose one of: {', '.join(_TYPES)}.")
    allowed = {"region", "offset", "labels", "highlight", "peaks", "marks", "title", "xlabel", "ylabel", "invert_x"}
    extra = {k: v for k, v in body.items() if k in allowed}
    if isinstance(extra.get("marks"), dict):                    # JSON keys are text: back to numbers
        extra["marks"] = {float(k): v for k, v in extra["marks"].items()}
    with _FIGURE_LOCK, tempfile.TemporaryDirectory() as folder:
        try:
            ax = plot(data, kind=body.get("kind", "lines"), style=body.get("style"),
                      **(body.get("settings") or {}), **extra)
            path = export(ax, Path(folder) / "figure", format=fmt, dpi=int(body.get("dpi", 300)),
                          color=body.get("color", "rgb"), transparent=bool(body.get("transparent", False)))
            content = path.read_bytes()
        finally:
            plt.close("all")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", str(body.get("name", "figure")))[:80] or "figure"
    return Response(content, media_type=_TYPES[fmt],
                    headers={"Content-Disposition": f'attachment; filename="{name}.{fmt}"'})
