"""Loading data files.

Use ``load``; it picks the right reader from the file's content and extension.

>>> import spectrum_toolkit as stk                      # doctest: +SKIP
>>> s = stk.load("data/A_A_1.asc")                      # doctest: +SKIP
Loaded A_A_1.asc: 1 spectrum, 1024 points, x 100.016 to 3645.92
  - Two columns: read as x, y.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from ..core import Spectrum, SpectrumCollection
from ._table import Table, build
from .excel import read_excel
from .matlab import is_mat, read_mat
from .text import looks_like_text, read_text

# Extensions handled by each reader. Unknown extensions are tried as text if
# the content looks like text, since instruments invent their own extensions.
EXCEL = {".xlsx", ".xlsm", ".xls"}
MATLAB = {".mat"}
TEXT = {".txt", ".csv", ".tsv", ".dat", ".asc", ".xy", ".prn", ".spec", ".text"}

Loaded = Spectrum | SpectrumCollection | list[Spectrum]


def load(
    path: str | Path,
    *,
    sheet: str | int | None = None,
    layout: str | None = None,
    x_col: int | None = None,
    y_cols: Sequence[int] | None = None,
    delimiter: str | None = None,
    decimal: str | None = None,
    x: str | None = None,
    y: str | None = None,
    verbose: bool = True,
) -> Loaded:
    """Load a data file into spectra.

    Parameters
    ----------
    path : the file.
    sheet : spreadsheets only; sheet name or number (1 = first).
    layout : force how columns are read: "xy", "shared" (x + many y),
        "pairs" (x, y, x, y ...) or "y" (y only). Default: detected.
    x_col, y_cols : choose columns by number in the file (1 = first column);
        ``x_col=0`` uses the point number as x.
    delimiter : text only; "tab", "semicolon", "comma", "pipe" or "space".
    decimal : text only; "." or ",".
    x, y : .mat only; names of the variables to use as x axis and as
        spectra, e.g. ``x="W", y="wt"``. Default: guessed from their shapes.
    verbose : print a summary of what was read and assumed.

    Returns
    -------
    Spectrum, SpectrumCollection, or a list of Spectrum (pairs with different x).
    What was assumed while reading is in ``result.meta["load_notes"]``.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"No file at {path}.")
    ext = path.suffix.lower()

    # ---- pick the reader -------------------------------------------------
    with path.open("rb") as f:                     # "with" closes the file again straight away
        head = f.read(4096)                        # first bytes, to recognise the format
    mat = ext in MATLAB or is_mat(head)            # .mat files start with the text "MATLAB"
    if (x is not None or y is not None) and not mat:
        raise ValueError("x= and y= name variables in a .mat file; for other files use x_col= and y_cols=.")
    if mat:
        # A .mat file holds named variables, not a table, so it has its own reader.
        result = read_mat(path, x=x, y=y)
        kind = "matlab"
    elif ext in EXCEL or head[:2] == b"PK" or head[:4] == b"\xd0\xcf\x11\xe0":
        # "PK" starts every .xlsx (it is a zip file); D0 CF 11 E0 starts old .xls.
        table: Table = read_excel(path, sheet=sheet)
        kind = "spreadsheet"
    elif ext in TEXT or looks_like_text(head):
        table = read_text(path, delimiter=delimiter, decimal=decimal)
        kind = "text"
    else:
        raise ValueError(
            f"{path.name}: this looks like a binary instrument file ({ext or 'no extension'}), "
            "which is not supported yet. Export it as text or Excel from the instrument software."
        )

    # ---- turn the table into spectra --------------------------------------
    if not mat:
        result = build(table, name=path.stem, layout=layout, x_col=x_col, y_cols=y_cols)

    # Record where the data came from on every spectrum returned.
    for item in (result if isinstance(result, list) else [result]):
        item.meta.update(source=str(path), file_type=kind)

    if verbose:
        print(summary(result, path.name))
    return result


def summary(result: Loaded, file_name: str) -> str:
    """A short human-readable report of a load."""
    if isinstance(result, Spectrum):
        what, x, notes = "1 spectrum", result.x, result.meta.get("load_notes", [])
        size = f"{len(result)} points"
    elif isinstance(result, SpectrumCollection):
        what, x, notes = f"{len(result)} spectra", result.x, result.meta.get("load_notes", [])
        size = f"{result.n_points} points each"
    else:
        what, x, notes = f"{len(result)} spectra (different x axes)", result[0].x, result[0].meta.get("load_notes", [])
        size = f"{min(len(s) for s in result)}–{max(len(s) for s in result)} points"
    lines = [f"Loaded {file_name}: {what}, {size}, x {x.min():.6g} to {x.max():.6g}"]
    lines += [f"  - {n}" for n in notes]
    return "\n".join(lines)


__all__ = ["load", "summary"]
