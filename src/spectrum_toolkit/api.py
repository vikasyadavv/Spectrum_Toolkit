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
                    With "panels": [...] instead of "data", several plots in
                    one figure. A missing font is named in the "X-Warning" header.
POST /groups        JSON {"data": ...}: proposes groups (which sample each
                    spectrum is) from the names, for the user to confirm;
                    with "groups" ({"CV": [0, 1, ...], ...}, "name", or one
                    label per spectrum) or "pattern", sets them. Answers
                    {"by", "groups" (one per spectrum), "counts", "message"};
                    the page then sends "groups" inside the data.
POST /style-check   JSON {"style": "publication" or {...settings...},
                    "settings": {...}}: checks a style (for example the
                    contents of a saved my_style.json) and returns every
                    setting, the ones that differ from the defaults, and
                    warnings (fonts not installed). A wrong setting gives 422.

Data in answers always has the same fields, in this order (one row of "Y"
per spectrum; sizes first, like MATLAB's size())::

    {"n_spectra": 14, "n_points": 1424, "size_Y": [14, 1424], "size_x": [1424],
     "x_range": [101.9, 1802.8], "names": ["Spectrum 1", ...], "groups": ["CV", ...] or [],
     "x_unit": "", "y_unit": "",
     "notes": [...what was assumed while reading...], "history": [...every step...],
     "x": [...], "Y": [[...], ...]}

/load answers {"data": ..., "separate": null, "message": null}; "separate"
and "message" are used only when the spectra have different x axes.
Requests need only "x" and "Y" (plus optional "names", units, "history").

Mistakes in a request (unknown method, wrong setting, unreadable file) give
HTTP 422 with the same plain-English message the library gives.

"style" in a request is a preset name or a dict of settings; the service
never opens a file named in a request (a style file is sent as its contents).

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
# expose_headers: lets the website's JavaScript read the file name and the font warning
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["GET", "POST"], allow_headers=["*"],
                   expose_headers=["Content-Disposition", "X-Warning"])


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


def to_json(data: Spectrum | SpectrumCollection, numbers: bool = True) -> dict:
    """A Spectrum or collection as the JSON data format (always with a list of rows).

    Every answer has the same fields in the same order. The sizes come first,
    like MATLAB's size(): "size_Y" is [spectra, points] (one row of Y per
    spectrum), "size_x" is [points]. With numbers=False, x and Y are left out
    (null): only the description, for a quick look at a big file.
    """
    if isinstance(data, Spectrum):
        Y, names, groups = data.y[None, :], [data.name], [data.group] if data.group else []
    else:
        Y, names, groups = data.Y, list(data.names), list(data.groups)
    notes = data.meta.get("load_notes") if isinstance(data.meta, dict) else None
    return {
        "n_spectra": int(Y.shape[0]),                            # rows of Y
        "n_points": int(Y.shape[1]),                             # values in each row, and in x
        "size_Y": [int(Y.shape[0]), int(Y.shape[1])],            # [spectra, points]
        "size_x": [int(data.x.size)],
        "x_range": [float(np.min(data.x)), float(np.max(data.x))] if data.x.size else None,
        "names": names,
        "groups": groups,                                        # one per spectrum ("" = none); [] = no groups
        "x_unit": data.x_unit,
        "y_unit": data.y_unit,
        "notes": list(notes or []),                              # what was assumed while reading
        "history": _plain(list(data.history)),                   # every processing step, with its settings
        "x": _numbers(data.x) if numbers else None,
        "Y": _numbers(Y) if numbers else None,
    }


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
                              y_unit=d.get("y_unit", ""), history=tuple(d.get("history") or ()),
                              groups=tuple(d.get("groups") or ()))


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


def _load_answer(result, numbers: bool = True) -> dict:
    """Answer of /load, always with the same three fields:
    "data" (one data set, or null), "separate" (a list of data sets when their
    x axes differ and cannot be joined, or null) and "message" (null, or why
    the spectra came back separately)."""
    if isinstance(result, list):
        from .edit import check_axes, combine
        notes = [n for n in result[0].meta.get("load_notes") or []        # what the reader assumed,
                 if not n.startswith("The pairs have different x values")]  # except the not-joined remark
        try:                                                    # same x values (gaps allowed): join, nothing changes
            joined = combine(*result, verbose=False)
            sizes = sorted({len(s.x) for s in result})            # points per spectrum before joining
            kept = joined.x.size
            if sizes == [kept]:
                how = f"all have the same {kept} x values"
            else:
                how = (f"they had {sizes[0]}-{sizes[-1]} points each; the {kept} x values they all share "
                       f"were kept, so up to {sizes[-1] - kept} points per spectrum were dropped")
            joined = joined.copy_with(meta={**joined.meta, "load_notes": notes + [
                f"The {len(result)} spectra lie on one x grid and were joined into one set without "
                f"changing any value: {how}."]})
            return {"data": to_json(joined, numbers), "separate": None, "message": None}
        except ValueError as e:
            report = check_axes(result)
            return {"data": None, "separate": [to_json(s, numbers) for s in result],
                    "message": f"The spectra have different x axes ({report.case}); "
                               f"choose how to put them on one axis. {e}"}
    return {"data": to_json(result, numbers), "separate": None, "message": None}


# ------------------------------------------------------------------ examples
# Shown ready-filled on the /docs page, so "Try it out" works without typing.
EXAMPLE_RECIPE = '{"steps": [{"step": "despike"}, {"step": "baseline"}, {"step": "normalize"}]}'
_TINY = {"x": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
         "Y": [[1, 2, 4, 9, 15, 9, 4, 2, 1, 1], [1, 1, 3, 7, 12, 8, 3, 2, 1, 1]],
         "names": ["a", "b"], "x_unit": "cm-1", "y_unit": "counts"}
EXAMPLE_PROCESS = {"data": _TINY, "recipe": {"steps": [{"step": "normalize", "method": "max"}]}, "all_steps": False}
EXAMPLE_STYLE = {"style": {"preset": "publication", "line_width": 1.5, "font": "Arial"},
                 "settings": {"legend_box": True}}
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
                        "then one y column per spectrum.")),
                    # False when left out: a form leaves out an unticked box, so a "yes" option must default to no
                    summary_only: bool = Form(False, description=(
                        "true: leave out the x and Y numbers (sizes, names and notes only), for a quick "
                        "look at a big file; the /docs page slows down with many numbers."))) -> dict:
    """Read an uploaded file: text, Excel or .mat (.mat files ignore sheet and layout)."""
    sheet = _blank_to_none(sheet)                                # an empty box means "not given"
    layout = None if layout == "auto" else layout                # None = let the reader detect it
    if sheet is not None and sheet.isdigit():                    # "2" from a form is sheet number 2
        sheet = int(sheet)
    with tempfile.TemporaryDirectory() as folder:               # deleted with everything in it afterwards
        path = await _save_upload(file, Path(folder))
        result = load(path, sheet=sheet, layout=layout, verbose=False)
    return _load_answer(result, numbers=not summary_only)


@app.post("/process")
def process(body: dict = Body(..., examples=[EXAMPLE_PROCESS])) -> dict:
    """Apply a recipe to data sent as JSON."""
    data = _single_or_all(from_json(body.get("data")))
    recipe = Recipe(body.get("recipe", {}).get("steps", []))
    if body.get("all_steps"):
        steps = recipe.run(data)
        return {"kind": "lines", "data": to_json(steps[-1][1]),
                "steps": [{"step": n, "data": to_json(d)} for n, d in steps]}
    return {"kind": "lines", "data": to_json(recipe.apply(data))}


@app.post("/process-file")
async def process_file(file: UploadFile = File(...), recipe: str = Form(..., examples=[EXAMPLE_RECIPE],
                       description="The processing steps as JSON text, e.g. " + EXAMPLE_RECIPE),
                       # False when left out, as in /load
                       summary_only: bool = Form(False, description=(
                           "true: leave out the x and Y numbers (sizes, names, notes and history only), "
                           "for a big file; the /docs page slows down with many numbers."))) -> dict:
    """Load an uploaded file and apply a recipe (JSON text) in one call."""
    try:
        steps = json.loads(recipe)
    except json.JSONDecodeError as e:
        raise ValueError(f"recipe must be JSON text such as {EXAMPLE_RECIPE} ({e}).") from e
    r = Recipe(steps.get("steps", []) if isinstance(steps, dict) else steps)
    with tempfile.TemporaryDirectory() as folder:
        path = await _save_upload(file, Path(folder))
        result = r.apply(path)
    # "kind" first: the whole answer can be pasted into /figure as it is (change "lines" to stack, mean or image)
    return {"kind": "lines", "data": to_json(result, numbers=not summary_only)}


_TYPES = {"png": "image/png", "tiff": "image/tiff", "jpg": "image/jpeg", "pdf": "application/pdf",
          "svg": "image/svg+xml", "eps": "application/postscript"}


def _style(body: dict):
    """The request's style: None, a preset name or a dict of settings.

    The library also takes a path to a .json file; the service does not, so a
    request can never make it open a file on the server.
    """
    from .style import PRESETS
    style = body.get("style")
    if style is None or isinstance(style, dict) or (isinstance(style, str) and style in PRESETS):
        return style
    raise ValueError(f'"style" must be a preset name ({", ".join(PRESETS)}) or a dict of settings, '
                     f"for example the contents of a style file saved with save_style; got {style!r}.")


def _font_warning(missing: list) -> str | None:
    """The plain-text warning for fonts that are not installed on the server (None when all are)."""
    if not missing:
        return None
    return f"Font(s) not installed on the server, another font was used: {', '.join(missing)}"


def _color_mode(body: dict) -> str:
    """RGB or CMYK for the saved file: "color_mode" (or its old name "color"), else the settings', else rgb."""
    mode = body.get("color_mode") or body.get("color") or (body.get("settings") or {}).get("color_mode") or "rgb"
    if str(mode).lower() not in ("rgb", "cmyk"):
        raise ValueError(f'color_mode must be "rgb" or "cmyk"; got {mode!r}. (Line colours go in "settings", '
                         'e.g. "line_color": "red".)')
    return str(mode).lower()


# Plot arguments a request may give next to "data" (the rest goes in "settings").
_PLOT_EXTRAS = {"region", "offset", "labels", "highlight", "emphasize", "color_by", "peaks", "marks", "title",
                "xlabel", "ylabel", "invert_x", "notes", "inset"}
# Arguments of a panel of kind "compare" (a before/after view): "after" is data like "data".
_COMPARE_EXTRAS = {"index", "removed"}


def _plot_extras(body: dict) -> dict:
    """The plot arguments of a request (or of one panel), with marks keys back to numbers."""
    extra = {k: v for k, v in body.items() if k in _PLOT_EXTRAS}
    if isinstance(extra.get("marks"), dict):                    # JSON keys are text: back to numbers
        extra["marks"] = {float(k): v for k, v in extra["marks"].items()}
    return extra


def _panel_items(body: dict) -> list:
    """The "panels" of a request as stk.panels entries: data, plot arguments, letter and own settings."""
    items = body.get("panels")
    if not isinstance(items, list) or not items:
        raise ValueError('"panels" must be a list of panels, each {"data": ..., "kind": ..., "settings": {...}}.')
    entries = []
    for i, panel in enumerate(items):
        if not isinstance(panel, dict) or "data" not in panel:
            raise ValueError(f'Panel {i + 1} must be a dict with "data".')
        entry = {"data": _single_or_all(from_json(panel["data"])), "kind": panel.get("kind", "lines"),
                 **_plot_extras(panel), **(panel.get("settings") or {})}
        if "after" in panel:                                         # kind "compare": the data after the step
            entry["after"] = _single_or_all(from_json(panel["after"]))
        entry.update({k: panel[k] for k in _COMPARE_EXTRAS if k in panel})
        if "letter" in panel:
            entry["letter"] = panel["letter"]
        entries.append(entry)
    return entries


@app.post("/figure")
def figure(body: dict = Body(..., examples=[EXAMPLE_FIGURE])) -> Response:
    """Draw data (or several panels) and return the figure file.

    With "panels": [{"data": ..., "kind": ..., "settings": {...}, ...}, ...]
    the figure has one panel per entry (kind "compare" takes "after", the
    data after a step, and optional "index" and "removed"); with "data" and
    "by": "group", one panel per group; "layout" ([rows, columns] or text
    such as "AA;BC"), "widths", "heights", "share_x", "share_y", "title"
    (over the whole figure), "xlabel" and "ylabel" (the shared labels) are
    optional.
    When a font asked for is not installed on the server, the answer has an
    "X-Warning" header saying which fonts were replaced.
    """
    import matplotlib
    matplotlib.use("Agg")                                       # no screen on a server
    import matplotlib.pyplot as plt

    from .plot import panels, plot
    from .style import export, get_style, missing_fonts

    fmt = str(body.get("format", "png")).lower()
    if fmt not in _TYPES:
        raise ValueError(f"Unknown format {fmt!r}. Choose one of: {', '.join(_TYPES)}.")
    settings = body.get("settings") or {}
    style = _style(body)
    with _FIGURE_LOCK, tempfile.TemporaryDirectory() as folder:
        try:
            if "panels" in body or "by" in body:
                entries = _panel_items(body) if "panels" in body else _single_or_all(from_json(body.get("data")))
                axes = panels(entries, body.get("layout"), by=body.get("by"),
                              kind=body.get("kind") if "by" in body else None,
                              widths=body.get("widths"), heights=body.get("heights"),
                              share_x=bool(body.get("share_x", False)), share_y=bool(body.get("share_y", False)),
                              title=body.get("title"), xlabel=body.get("xlabel"), ylabel=body.get("ylabel"),
                              style=style, **settings)
                ax = axes[0]
                own = [p.get("settings") or {} for p in body.get("panels") or [{}]]
            else:
                data = _single_or_all(from_json(body.get("data")))
                ax = plot(data, kind=body.get("kind", "lines"), style=style, **settings,
                          **_plot_extras(body))
                own = [{}]
            path = export(ax, Path(folder) / "figure", format=fmt, dpi=int(body.get("dpi", 300)),
                          color=_color_mode(body), transparent=bool(body.get("transparent", False)))
            content = path.read_bytes()
        finally:
            plt.close("all")
    missing = sorted({f for extra in own for f in missing_fonts(get_style(style, **{**settings, **extra}))})
    name = re.sub(r"[^A-Za-z0-9._-]", "_", str(body.get("name", "figure")))[:80] or "figure"
    headers = {"Content-Disposition": f'attachment; filename="{name}.{fmt}"'}
    if missing:                                                  # headers carry plain text only
        headers["X-Warning"] = _font_warning(missing).encode("ascii", "replace").decode()
    return Response(content, media_type=_TYPES[fmt], headers=headers)


@app.post("/groups")
def set_or_suggest_groups(body: dict = Body(..., examples=[{"data": _TINY, "groups": {"A": [0], "B": [1]}}])) -> dict:
    """Propose or set which group (sample) each spectrum belongs to.

    Without "groups" and "pattern": a proposal from the names, or none when
    the names only number the spectra ("Spectrum 1", "Spot2"), with a message
    to show the user. With "groups" (a dict of spectrum numbers or names per
    group, "name", or a list with one label per spectrum), "pattern" (a
    regular expression; the part in brackets is the group) and optional
    "rename": sets them. The answer is always {"by", "groups", "counts",
    "message"}; send "groups" inside the data afterwards (/process and
    /figure keep and use them).
    """
    from .groups import _counts, set_groups, suggest_groups
    data = from_json(body.get("data"))
    if body.get("groups") is None and body.get("pattern") is None:
        return _plain(suggest_groups(data))
    done = set_groups(data, body.get("groups"), pattern=body.get("pattern"), rename=body.get("rename"))
    labels = list(done.groups) or [""] * len(done)
    counts = _counts(labels)
    return {"by": "given", "groups": labels, "counts": counts,
            "message": "Groups: " + ", ".join(f"{g} ({n})" for g, n in counts.items()) + "."}


@app.post("/style-check")
def style_check(body: dict = Body(..., examples=[EXAMPLE_STYLE])) -> dict:
    """Check a style and return it in full, before it is used or saved.

    "style" is a preset name or a dict of settings (for example the contents
    of a style file the user saved earlier); "settings" are changes on top.
    The answer:
      "style"    every setting, as save_style writes it: ready to save as
                 my_style.json and load again here or in Python
                 (stk.get_style("my_style.json")).
      "changed"  only the settings that differ from the defaults, to show
                 what the style contains.
      "warnings" fonts the style asks for that are not installed on the server.
    A wrong setting name or value answers 422 with a message naming it.
    """
    from .style import DEFAULTS, get_style, missing_fonts
    settings = body.get("settings") or {}
    if not isinstance(settings, dict):
        raise ValueError('"settings" must be a dict of settings, e.g. {"line_width": 1.5}.')
    style = _style(body)
    full = get_style(style, **settings)
    if full is None:                                             # "matplotlib": matplotlib's own look, nothing set
        return {"style": {"preset": "matplotlib"}, "changed": {}, "warnings": []}
    changed = {k: v for k, v in full.items() if _plain(v) != _plain(DEFAULTS[k])}
    warning = _font_warning(missing_fonts(full))
    return {"style": _plain({"preset": "clean", **full}), "changed": _plain(changed),
            "warnings": [warning] if warning else []}
