"""Read MATLAB .mat files.

A .mat file is a bag of named variables, and the names change from file to
file (``W`` and ``wt`` in one, ``wavenumber`` and ``spectra`` in another). So
the reader does not look for particular names. Instead it looks at the
*shapes*:

1. A vector that only goes up (or only down) is a possible x axis.
2. A matrix with one side as long as that vector holds spectra on that axis:
   one spectrum per column if the rows match (MATLAB's usual way), one per
   row if the columns match.
3. If several pairs fit, the biggest matrix wins, and the other choices are
   listed in the notes so they can be picked with ``x=`` and ``y=``.
4. A matrix with no matching vector is read like a table in a text file
   (x in the first column, then y columns; see ``_table.build``).
5. Only vectors: a rising vector is x, the vectors of the same length are y.

Structures (``s.field``) are searched too. Text, cell arrays, complex numbers
and arrays with 3 or more dimensions are skipped, with a note.

Files saved with ``save -v7.3`` are HDF5 files inside and need the extra
package h5py, which is not installed yet; they give a clear error.

>>> import spectrum_toolkit as stk                      # doctest: +SKIP
>>> c = stk.load("data/wt_raw.mat")                     # doctest: +SKIP
Loaded wt_raw.mat: 550 spectra, 747 points each, x 441.68 to 1821.58
  - Variables: W (747), data_wt (410850 x 4), wt (747 x 550).
  - Used W as x and wt as y (550 spectra, one per column).
  ...
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from ..core import Spectrum, SpectrumCollection
from ._table import Table, _ascending, _is_monotonic, build

# Every .mat file from MATLAB 5 onwards starts with this text.
MAT_MAGIC = b"MATLAB"
# HDF5 files start with these 8 bytes; v7.3 .mat files put them at byte 512.
_HDF5_MAGIC = b"\x89HDF\r\n\x1a\n"


def is_mat(head: bytes) -> bool:
    """True if the first bytes of a file say it is a MATLAB .mat file."""
    return head.startswith(MAT_MAGIC)


def _shape_text(a: np.ndarray) -> str:
    """Shape as people write it: "747" for a vector, "747 x 550" for a matrix."""
    return " x ".join(str(n) for n in a.shape)


def read_variables(path: str | Path) -> tuple[dict[str, np.ndarray], list[str]]:
    """All numeric vectors and matrices in a .mat file.

    Returns
    -------
    variables : {name: array}; vectors are 1-D, matrices 2-D, all float.
        Fields of a structure are named "struct.field".
    skipped : one line for each variable that could not be used, and why.
    """
    import scipy.io  # imported here so the library loads even without scipy

    path = Path(path)
    with path.open("rb") as f:                       # "with" closes the file again straight away
        head = f.read(520)                           # enough to see both kinds of header
    if head[:10] == b"MATLAB 7.3" or head[512:520] == _HDF5_MAGIC:
        raise ValueError(
            f"{path.name} was saved in MATLAB's v7.3 format (an HDF5 file), which is not supported yet. "
            "In MATLAB, re-save it with: save('file.mat', '-v7')"
        )
    try:
        # simplify_cells turns structures into dicts and squeezes away
        # dimensions of length 1, so a 747x1 column becomes a plain vector.
        raw = scipy.io.loadmat(path, simplify_cells=True)
    except NotImplementedError as err:              # scipy's message for v7.3 files
        raise ValueError(f"{path.name}: {err}. In MATLAB, re-save it with: save('file.mat', '-v7')") from err
    except Exception as err:                        # not a .mat file after all, or damaged
        raise ValueError(f"{path.name} could not be read as a MATLAB file: {err}") from err

    variables: dict[str, np.ndarray] = {}
    skipped: list[str] = []

    def walk(name: str, value: Any) -> None:
        """Collect usable arrays from one variable, going into structures."""
        if isinstance(value, dict):                  # a structure: look at every field
            for field, inner in value.items():
                walk(f"{name}.{field}", inner)
            return
        if not isinstance(value, np.ndarray):        # text, single numbers, cell arrays (lists)
            if isinstance(value, (list, str)):
                skipped.append(f"{name} (text or cell array)")
            return
        if value.dtype == bool or not np.issubdtype(value.dtype, np.number):
            skipped.append(f"{name} (not numbers)")
            return
        if np.iscomplexobj(value):
            skipped.append(f"{name} (complex numbers)")
            return
        if value.ndim > 2:
            skipped.append(f"{name} ({_shape_text(value)}: 3 or more dimensions, e.g. an image cube)")
            return
        if value.size < 2:                           # a single number is a setting, not data
            return
        variables[name] = value.astype(float)        # integers (e.g. counts) -> float

    for name, value in raw.items():
        if not name.startswith("__"):                # __header__, __version__ ... are file info
            walk(name, value)
    return variables, skipped


def _candidates(variables: dict[str, np.ndarray], vectors_too: bool = False) -> list[tuple[str, str, str]]:
    """Every (x name, y name, orientation) where a rising/falling vector fits a matrix.

    orientation is "columns" (one spectrum per column) or "rows".
    vectors_too : also list other vectors of the same length as single
        spectra (orientation "vector").
    """
    vectors = {n: v for n, v in variables.items() if v.ndim == 1 and _is_monotonic(v)}
    found = []
    for yn, m in variables.items():
        if m.ndim != 2:
            if vectors_too:                          # a vector as one spectrum on another vector
                found += [(xn, yn, "vector") for xn, v in vectors.items() if xn != yn and len(v) == len(m)]
            continue
        for xn, v in vectors.items():
            if len(v) == m.shape[0]:
                found.append((xn, yn, "columns"))    # MATLAB's usual way: spectra in columns
            elif len(v) == m.shape[1]:
                found.append((xn, yn, "rows"))
    # Biggest matrix first; on a tie, keep the order found (alphabetical names).
    found.sort(key=lambda c: -variables[c[1]].size)
    return found


def describe(variables: dict[str, np.ndarray], skipped: list[str]) -> dict:
    """What a .mat file holds, as a table for choosing what to plot (see ``mat_variables``).

    Returns {"variables": [...], "choices": [...], "chosen": None, "skipped": [...]}:
    one row per variable (name, size as in MATLAB's size(), vector or
    matrix, smallest and largest value, whether it can be an x axis), and
    every x / y pair that fits (how many spectra, how many points, whether
    the spectra are the matrix's columns or rows). "chosen" is filled in by
    read_mat with the pair it used.
    """
    table = []
    for name, v in sorted(variables.items()):
        finite = v[np.isfinite(v)]                               # MATLAB NaN left out of min and max
        table.append({"name": name, "size": [int(n) for n in v.shape],
                      "kind": "vector" if v.ndim == 1 else "matrix",
                      "min": float(finite.min()) if finite.size else None,
                      "max": float(finite.max()) if finite.size else None,
                      "can_be_x": bool(v.ndim == 1 and _is_monotonic(v))})   # only rising or falling vectors
    choices = []
    for xn, yn, how in _candidates(variables, vectors_too=True):
        m = variables[yn]
        spectra = 1 if how == "vector" else m.shape[1] if how == "columns" else m.shape[0]
        choices.append({"x": xn, "y": yn, "spectra": int(spectra), "points": int(len(variables[xn])),
                        "spectra_in": how})                     # "columns", "rows" or "vector"
    return {"variables": table, "choices": choices, "chosen": None, "skipped": list(skipped)}


def _spectra(x: np.ndarray, Y: np.ndarray, x_name: str, y_name: str, file_name: str,
             notes: list[str], meta: dict) -> Spectrum | SpectrumCollection:
    """Make the result from x and Y (rows = spectra), cleaning it like the text reader does."""
    # Drop points where x or any spectrum is missing (NaN in MATLAB).
    ok = np.isfinite(x) & np.all(np.isfinite(Y), axis=0)
    if not ok.all():
        notes.append(f"Dropped {int((~ok).sum())} point(s) with a missing value.")
    x, Y = _ascending(x[ok], Y[:, ok], notes)
    meta = dict(meta, load_notes=notes)
    if Y.shape[0] == 1:                              # one spectrum
        return Spectrum(x, Y[0], name=file_name, x_unit=x_name, y_unit=y_name, meta=meta)
    names = [f"{y_name} {i + 1}" for i in range(Y.shape[0])]     # "wt 1", "wt 2", ...
    return SpectrumCollection(x, Y, names=names, x_unit=x_name, y_unit=y_name, meta=meta)


def _orient(x: np.ndarray, m: np.ndarray, y_name: str, notes: list[str]) -> np.ndarray:
    """Return the matrix with one spectrum per row, given which side matches x."""
    if m.ndim == 1:
        return m[None, :]                            # a single spectrum
    if m.shape[0] == len(x) and m.shape[1] == len(x):
        notes.append(f"{y_name} is square; assumed one spectrum per column (MATLAB's usual way).")
        return m.T
    if m.shape[0] == len(x):
        return m.T                                   # spectra were columns
    if m.shape[1] == len(x):
        return m                                     # spectra were rows already
    raise ValueError(f"{y_name} is {_shape_text(m)}, but the x axis has {len(x)} points; neither side matches.")


def _matrix_as_table(m: np.ndarray, y_name: str, file_name: str, notes: list[str], meta: dict):
    """Read a matrix with no separate x vector, as if it were a table in a text file."""
    if not _is_monotonic(m[:, 0]) and _is_monotonic(m[0, :]):
        m = m.T                                      # x runs along the first row: turn it into a column
        notes.append(f"{y_name}: x found in the first row; read with one spectrum per column.")
    elif not _is_monotonic(m[:, 0]):
        # No x anywhere: spectra along the longer side, against point number.
        if m.shape[1] > m.shape[0]:
            m = m.T
        notes.append(f"{y_name}: no x axis found; each column is a spectrum against point number.")
        n = m.shape[0]
        Y = m.T
        return _spectra(np.arange(n, dtype=float), Y, "Point number", y_name, file_name, notes, meta)
    # Hand the matrix to the table reader (fast path: the numbers are ready).
    table = Table([[] for _ in range(m.shape[0])], fast=(0, m.shape[0], m))
    table.notes = notes + table.notes
    result = build(table, name=file_name)
    for item in (result if isinstance(result, list) else [result]):
        item.meta.update(meta)
        item.meta["load_notes"] = table.notes
    return result


def read_mat(path: str | Path, x: str | None = None, y: str | None = None):
    """Load spectra from a .mat file.

    Parameters
    ----------
    x : name of the variable to use as x axis. Default: guessed.
    y : name of the variable holding the spectra. Default: guessed.

    Returns
    -------
    Spectrum, SpectrumCollection, or a list of Spectrum (see ``load``).
    """
    path = Path(path)
    variables, skipped = read_variables(path)
    if not variables:
        raise ValueError(f"{path.name} has no numeric vectors or matrices." +
                         (f" Skipped: {', '.join(skipped)}." if skipped else ""))

    notes = ["Variables: " + ", ".join(f"{n} ({_shape_text(v)})" for n, v in sorted(variables.items())) + "."]
    if skipped:
        notes.append("Skipped: " + ", ".join(skipped) + ".")
    # The table of variables travels with the result, so a page can offer other choices.
    info = describe(variables, skipped)
    meta = {"variables": info}

    def get(name: str) -> np.ndarray:
        """A variable by name, with a helpful error listing the names that exist."""
        if name not in variables:
            raise ValueError(f"No usable variable {name!r} in {path.name}. Variables: {sorted(variables)}.")
        return variables[name]

    # ----- names chosen by hand ---------------------------------------
    if x is not None or y is not None:
        if y is None:                                # x given: biggest matrix that fits it
            fits = [c for c in _candidates(variables) if c[0] == x]
            if not fits:
                raise ValueError(f"No matrix in {path.name} has a side as long as {x} ({len(get(x))}).")
            y = fits[0][1]
        Ym = get(y)
        found_x = x is None                          # x not given: look for one that fits y
        if x is None:                                # y given: find an x that fits it (matrix or vector), if any
            fits = [c for c in _candidates(variables, vectors_too=True) if c[1] == y]
            if fits:
                x = fits[0][0]
            elif Ym.ndim == 1:
                x_vals = np.arange(len(Ym), dtype=float)
                notes.append(f"Variables chosen by hand: y = {y}; no x given, so x is the point number.")
                info["chosen"] = {"x": None, "y": y}
                return _spectra(x_vals, Ym[None, :], "Point number", y, path.stem, notes, meta)
            else:
                notes.append(f"Variable chosen by hand: y = {y}.")
                info["chosen"] = {"x": None, "y": y}
                return _matrix_as_table(Ym, y, path.stem, notes, meta)
        x_vals = get(x)
        if x_vals.ndim != 1:
            raise ValueError(f"x must be a vector, but {x} is {_shape_text(x_vals)}.")
        Y = _orient(x_vals, Ym, y, notes)
        notes.append(f"Variable chosen by hand: y = {y}; x = {x}, the vector that fits it." if found_x
                     else f"Variables chosen by hand: x = {x}, y = {y}.")
        info["chosen"] = {"x": x, "y": y}
        return _spectra(x_vals, Y, x, y, path.stem, notes, meta)

    # ----- guess: a vector that fits a matrix --------------------------
    found = _candidates(variables)
    if found:
        xn, yn, how = found[0]
        Y = _orient(variables[xn], variables[yn], yn, notes)
        notes.append(f"Used {xn} as x and {yn} as y ({Y.shape[0]} spectra, one per {how[:-1]}).")
        info["chosen"] = {"x": xn, "y": yn}
        others = [f"x={a!r}, y={b!r}" for a, b, _ in _candidates(variables, vectors_too=True)[1:]]
        if others:
            notes.append("Other possible choices: " + "; ".join(others) + ".")
        return _spectra(variables[xn], Y, xn, yn, path.stem, notes, meta)

    # ----- guess: a matrix on its own ----------------------------------
    matrices = {n: v for n, v in variables.items() if v.ndim == 2}
    if matrices:
        yn = max(matrices, key=lambda n: matrices[n].size)       # the biggest one
        notes.append(f"No x vector fits any matrix; read {yn} like a table.")
        info["chosen"] = {"x": None, "y": yn}
        return _matrix_as_table(matrices[yn], yn, path.stem, notes, meta)

    # ----- guess: vectors only -----------------------------------------
    rising = [n for n, v in variables.items() if _is_monotonic(v)]
    for xn in rising:
        ys = [n for n, v in variables.items() if n != xn and len(v) == len(variables[xn])]
        if ys:
            notes.append(f"Used {xn} as x and {', '.join(ys)} as y.")
            info["chosen"] = {"x": xn, "y": ys[0] if len(ys) == 1 else ys}   # several vectors: a list
            Y = np.vstack([variables[n] for n in ys])
            result = _spectra(variables[xn], Y, xn, ys[0] if len(ys) == 1 else "", path.stem, notes, meta)
            if isinstance(result, SpectrumCollection):
                result = SpectrumCollection(result.x, result.Y, names=ys, x_unit=xn, meta=result.meta)
            return result
    yn = max(variables, key=lambda n: variables[n].size)          # one lone vector
    notes.append(f"No x axis found; {yn} used as y against point number.")
    info["chosen"] = {"x": None, "y": yn}
    return _spectra(np.arange(variables[yn].size, dtype=float), variables[yn][None, :],
                    "Point number", yn, path.stem, notes, meta)


def mat_variables(path: str | Path) -> dict:
    """Every variable in a .mat file with its size, and which ones can be plotted against which.

    For choosing what to load: ``stk.load(path, x=..., y=...)`` with names
    from this table.

    Returns
    -------
    dict with
      "variables"  one row per numeric vector or matrix: "name" (fields of a
                   structure as "s.field"), "size" (as MATLAB's size(); a
                   vector has one number), "kind" ("vector" or "matrix"),
                   "min" and "max" (missing values left out), "can_be_x"
                   (a vector that only rises or only falls).
      "choices"    every x / y pair that fits: "x", "y", "spectra" (how many),
                   "points" (in each), "spectra_in" ("columns", "rows", or
                   "vector" for one spectrum); biggest first.
      "chosen"     the pair ``load`` uses when no names are given, e.g.
                   {"x": "W", "y": "wt"}; "x" None means point number (or,
                   for a matrix read like a table, its first column); "y" is
                   a list when several vectors become spectra. None when
                   ``load`` cannot guess (then "problem" says why).
      "skipped"    variables that cannot be spectra, and why (text, cell
                   arrays, complex numbers, 3-D arrays).

    >>> import spectrum_toolkit as stk                  # doctest: +SKIP
    >>> info = stk.mat_variables("data/wt_raw.mat")     # doctest: +SKIP
    >>> [(v["name"], v["size"]) for v in info["variables"]]   # doctest: +SKIP
    [('W', [747]), ('data_wt', [410850, 4]), ('wt', [747, 550])]
    >>> info["chosen"]                                  # doctest: +SKIP
    {'x': 'W', 'y': 'wt'}
    """
    path = Path(path)
    variables, skipped = read_variables(path)
    if not variables:
        raise ValueError(f"{path.name} has no numeric vectors or matrices." +
                         (f" Skipped: {', '.join(skipped)}." if skipped else ""))
    try:                                                        # what load would choose by itself
        result = read_mat(path)
        first = result[0] if isinstance(result, list) else result
        return first.meta["variables"]
    except ValueError as e:                                      # it cannot guess: still list everything
        return {**describe(variables, skipped), "problem": str(e)}


__all__ = ["read_mat", "read_variables", "mat_variables", "describe", "is_mat"]
