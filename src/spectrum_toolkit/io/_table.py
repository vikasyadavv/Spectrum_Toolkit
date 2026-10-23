"""Turn a grid of cells into spectra.

Text files and spreadsheets both end up as a grid: a list of rows, each row a
list of cells (strings from text files; numbers, strings or None from Excel).
This module does everything that is the same for both:

1. find the block of numeric rows (the data) and keep the rows above it as
   column headers and metadata;
2. drop columns that are empty in the data;
3. work out the layout of the columns (see ``detect_layout``);
4. build a ``Spectrum`` or ``SpectrumCollection``, putting x in ascending order
   and dropping rows with missing values.

Every assumption made along the way is written to a list of notes, which
``load`` prints and stores in ``meta["load_notes"]``. Nothing is guessed
silently.
"""

from __future__ import annotations

import json
import re
from typing import Any, Sequence

import numpy as np

from ..core import Spectrum, SpectrumCollection

# A number as written in data files: optional sign, digits with an optional
# decimal point, and an optional exponent. The exponent letter may be e/E or
# d/D, because Fortran-based instrument software writes 1.5D+03.
_NUMBER = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eEdD][+-]?\d+)?$")

# Cell texts that mean "no value here".
_MISSING = {"", "nan", "na", "n/a", "-", "--", "null", "none"}


def parse_number(cell: Any, decimal_comma: bool = False) -> float | None:
    """Read one cell as a number.

    Returns
    -------
    float : the value; ``nan`` for an empty or "missing" cell.
    None : the cell holds text (it is a label, not data).

    Examples
    --------
    >>> parse_number("1001,5", decimal_comma=True)
    1001.5
    >>> parse_number("Intensity") is None
    True
    """
    # Excel cells often arrive as numbers already; bool is excluded because
    # True/False are technically ints in Python but are not data.
    if isinstance(cell, (int, float)) and not isinstance(cell, bool):
        return float(cell)
    # An empty Excel cell arrives as None.
    if cell is None:
        return float("nan")
    # Strip spaces and surrounding quotes: "1001.5" -> 1001.5
    text = str(cell).strip().strip("\"'").strip()
    if text.lower() in _MISSING:
        return float("nan")
    # European files write a decimal comma: 1001,5 means 1001.5.
    if decimal_comma:
        text = text.replace(",", ".", 1)
    if not _NUMBER.match(text):
        return None
    # Python understands 1.5e3 but not 1.5D3, so swap the Fortran letter.
    return float(text.replace("D", "e").replace("d", "e"))


def numeric_row(cells: Sequence[Any], decimal_comma: bool = False) -> list[float] | None:
    """Return the row as numbers if it is a data row, else None.

    A data row has at least one number and no text cells (empty cells are
    allowed; they become nan).
    """
    values = []
    for cell in cells:
        v = parse_number(cell, decimal_comma)
        if v is None:          # one text cell makes it a label row
            return None
        values.append(v)
    # A row of only empty cells is a blank line, not data.
    if all(np.isnan(v) for v in values):
        return None
    return values


def _is_blank(cells: Sequence[Any]) -> bool:
    """True if every cell in the row is empty."""
    return all(c is None or str(c).strip() == "" for c in cells)


def find_data_block(rows: list[list[Any]], decimal_comma: bool) -> tuple[int, int]:
    """Return (start, stop) of the longest run of data rows.

    Blank rows inside the run are allowed (some exports leave gaps). Anything
    before ``start`` is header/metadata, anything from ``stop`` is footer.
    """
    best = (0, 0, 0)                 # (count, start, stop) of the best run so far
    start, count = -1, 0             # current run: first row index, data rows in it
    for i, row in enumerate(rows + [["<end>"]]):    # sentinel row closes the last run
        is_data = numeric_row(row, decimal_comma) is not None
        if is_data or (start >= 0 and _is_blank(row)):
            if start < 0:
                start = i                # a new run begins
            count += is_data
            continue
        # A label row ends the current run; keep it if it is the longest.
        if start >= 0 and count > best[0]:
            best = (count, start, i)
        start, count = -1, 0
    if best[0] == 0:
        raise ValueError("No numeric data found: the file has no rows of numbers.")
    return best[1], best[2]


def _cell_text(cell: Any) -> str:
    """A cell as clean text for use as a label ('' for empty)."""
    if cell is None:
        return ""
    if isinstance(cell, float) and cell.is_integer():
        cell = int(cell)                         # 1.0 -> "1", nicer as a name
    return str(cell).strip().strip("\"'").lstrip("#").strip()


def _looks_like_metadata(cells: list[str]) -> bool:
    """True for rows like "Laser (nm)= 532" or "Acq. time: 10" (key and value).

    A first cell with "=" in it is a setting even when the line splits into
    many cells, e.g. '#proc_cfg={"base_fit": 0, ...}' in EnSpectr .esp files:
    column titles never contain "=".
    """
    filled = [c for c in cells if c]
    if not filled:
        return False
    return "=" in filled[0] or (len(filled) <= 2 and filled[0].endswith(":"))


def parse_metadata(lines: list[str]) -> dict[str, Any]:
    """Collect "key: value" / "key = value" / "key<tab>value" lines into a dict.

    Values are kept as text, except a value written as a JSON object
    ('exp_cfg={"exp": 1000.0, ...}', as in .esp files), which becomes a dict
    so each setting can be read by name.
    """
    fields: dict[str, Any] = {}
    for line in lines:
        # Drop comment marks at the start (#, %, ;, !, *).
        text = re.sub(r"^[#%;!*\s]+", "", line)
        m = re.match(r"^([^:=\t]{1,60}?)\s*[:=\t]\s*(.+)$", text)
        if m:
            value = m.group(2).strip()
            if value.startswith("{") and value.endswith("}"):    # a JSON object: read it as one
                try:
                    value = json.loads(value)
                except ValueError:                               # not valid JSON after all: keep the text
                    pass
            fields[m.group(1).strip()] = value
    return fields


class Table:
    """The numeric block of a file plus everything found around it.

    Attributes
    ----------
    data : 2-D float array, one column per kept column of the file.
    columns : original column number (0-based) of each kept column.
    headers : header text of each kept column ('' if none).
    meta : metadata found above/below the data.
    notes : what was assumed or changed while reading.
    """

    def __init__(self, rows: list[list[Any]], decimal_comma: bool = False, raw_lines: list[str] | None = None,
                 fast: tuple[int, int, np.ndarray] | None = None):
        """Build the table.

        ``fast`` = (start, stop, data) lets a reader that already parsed the
        numeric block quickly (see ``text.read_text``) skip the slow,
        cell-by-cell parsing below. Headers and metadata are found the same way.
        """
        notes: list[str] = []
        if fast is not None:
            start, stop, data = fast
            width = data.shape[1]
        else:
            start, stop = find_data_block(rows, decimal_comma)

            # --- the numbers, one cell at a time (handles any mess) --------
            block = [numeric_row(r, decimal_comma) for r in rows[start:stop]]
            block = [r for r in block if r is not None]             # skip blank rows
            width = max(len(r) for r in block)                      # widest row
            short = sum(len(r) < width for r in block)
            if short:
                notes.append(f"{short} row(s) were shorter than the others; missing cells treated as empty.")
            # Pad short rows with nan so the block is a proper rectangle.
            data = np.array([r + [np.nan] * (width - len(r)) for r in block], dtype=float)

        # --- drop columns that hold no data at all ----------------------
        keep = [c for c in range(width) if not np.all(np.isnan(data[:, c]))]
        if len(keep) < width:
            notes.append(f"Ignored {width - len(keep)} empty column(s): {[c + 1 for c in range(width) if c not in keep]}.")

        # --- headers: the label row right above the data ----------------
        headers = [""] * width
        header_row = None
        for i in range(start - 1, -1, -1):
            if _is_blank(rows[i]):
                continue                         # skip blank lines between header and data
            cells = [_cell_text(c) for c in rows[i]]
            if not _looks_like_metadata(cells):
                header_row = i
                # A tab-separated header like "#Wave<tab><tab>#Intensity" has an
                # empty cell in the middle; if dropping empties gives exactly
                # the right count, use that instead.
                filled = [c for c in cells if c]
                if len(cells) != width and len(filled) == len(keep):
                    cells = [""] * width
                    for c, text in zip(keep, filled):
                        cells[c] = text
                headers = (cells + [""] * width)[:width]
            break

        # --- metadata: every other line outside the data block ----------
        source = raw_lines if raw_lines is not None else ["\t".join(_cell_text(c) for c in r) for r in rows]
        outside = [source[i].strip() for i in range(len(rows))
                   if (i < start or i >= stop) and i != header_row and source[i].strip()]
        self.meta = {"metadata": parse_metadata(outside), "extra_lines": outside[:200]}
        if outside:
            notes.append(f"Kept {len(outside)} non-data line(s) as metadata.")
        if decimal_comma:
            notes.append("Read decimal commas (e.g. 1001,5 as 1001.5).")

        self.data = data[:, keep]
        self.columns = keep
        self.headers = [headers[c] for c in keep]
        self.notes = notes

    @property
    def n_columns(self) -> int:
        return self.data.shape[1]


def _is_monotonic(col: np.ndarray) -> bool:
    """True if the finite values only go up, or only go down (an x axis)."""
    v = col[np.isfinite(col)]
    d = np.diff(v)
    return v.size > 1 and (np.all(d > 0) or np.all(d < 0))


def detect_layout(table: Table) -> str:
    """Guess how spectra are arranged in the columns.

    - "y"      : one column; y against point number.
    - "xy"     : two columns; x then y.
    - "pairs"  : x, y, x, y, ... (several spectra side by side, each with its x),
                 e.g. MB 10-4M.xlsx.
    - "shared" : x then several y columns (several spectra on one x axis).
    """
    n = table.n_columns
    if n == 1:
        return "y"
    if n == 2:
        return "xy"
    # Pairs: an even number of columns where every 1st, 3rd, 5th ... column
    # looks like an x axis (always rising or always falling).
    if n % 2 == 0 and all(_is_monotonic(table.data[:, c]) for c in range(0, n, 2)):
        return "pairs"
    if _map_shape(table) is not None:
        return "map"
    return "shared"


def _map_shape(table: Table) -> tuple[int, int] | None:
    """(positions, points per spectrum) if the table is a map in long format,
    i.e. rows of X, Y, wavenumber, intensity (or X, wavenumber, intensity for a
    line scan) with the same wavenumbers repeated for every position; else None."""
    n, rows = table.n_columns, table.data.shape[0]
    if n not in (3, 4) or rows < 100:
        return None
    pos = table.data[:, :n - 2]                                 # X (and Y) columns
    wave = table.data[:, n - 2]
    n_pos = len(np.unique(pos, axis=0))
    n_wave = len(np.unique(wave))
    if n_pos < 2 or n_wave < 10 or n_pos * n_wave != rows:
        return None
    return n_pos, n_wave


def _ascending(x: np.ndarray, Y: np.ndarray, notes: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Return x and Y (rows = spectra) ordered by increasing x, noting any change."""
    d = np.diff(x)
    if np.all(d > 0):
        return x, Y                                   # already ascending
    if np.all(d < 0):
        notes.append("x was descending; reversed to ascending order.")
        return x[::-1], Y[:, ::-1]
    order = np.argsort(x, kind="stable")              # mixed order: sort by x
    notes.append("x values were not in order; sorted by x.")
    if np.any(d == 0):
        notes.append(f"{int(np.sum(np.diff(np.sort(x)) == 0))} repeated x value(s) found.")
    return x[order], Y[:, order]


def build(table: Table, name: str, layout: str | None = None,
          x_col: int | None = None, y_cols: Sequence[int] | None = None) -> Spectrum | SpectrumCollection | list[Spectrum]:
    """Make spectra from a Table.

    Parameters
    ----------
    name : used for a single spectrum (usually the file name).
    layout : force a layout instead of detecting it ("y", "xy", "pairs", "shared").
    x_col, y_cols : choose columns by their number in the FILE (1 = first
        column), overriding the layout. ``x_col=0`` means "use point number".

    Returns
    -------
    Spectrum : one spectrum.
    SpectrumCollection : several spectra on one x axis.
    list[Spectrum] : several spectra whose x axes differ (layout "pairs").
    """
    notes = table.notes
    # Map a 1-based file column number to our position in table.data.
    def pos(file_col: int) -> int:
        if file_col - 1 not in table.columns:
            raise ValueError(f"Column {file_col} has no data. Columns with data: {[c + 1 for c in table.columns]}.")
        return table.columns.index(file_col - 1)

    # ----- explicit column choice wins over any detection ---------------
    if x_col is not None or y_cols is not None:
        x_col = 1 if x_col is None else x_col            # default x: first column
        if x_col == 0:                                   # 0 = use point number as x
            x, x_label, x_pos = np.arange(table.data.shape[0], dtype=float), "Point number", None
        else:
            x_pos = pos(x_col)
            x, x_label = table.data[:, x_pos], table.headers[x_pos]
        # Default y: every other column that has data.
        ys = [pos(c) for c in y_cols] if y_cols else [p for p in range(table.n_columns) if p != x_pos]
        notes.append(f"Columns chosen by hand: x = {x_col or 'point number'}, y = {[table.columns[p] + 1 for p in ys]}.")
        return _shared(table, x, ys, name, x_label=x_label, notes=notes)

    if layout is not None and layout not in ("y", "xy", "pairs", "shared"):   # check before using it
        raise ValueError(f"Unknown layout {layout!r}; use 'y', 'xy', 'pairs' or 'shared' (or leave it empty).")
    layout = layout or detect_layout(table)
    notes.append({
        "y": "One column: used as y against point number.",
        "xy": "Two columns: read as x, y.",
        "pairs": f"{table.n_columns} columns read as {table.n_columns // 2} x/y pairs (one spectrum per pair).",
        "shared": f"{table.n_columns} columns read as x plus {table.n_columns - 1} y columns on the same x.",
        "map": "Map in long format (position, wavenumber, intensity rows).",
    }[layout])

    if layout == "y":
        x = np.arange(table.data.shape[0], dtype=float)
        return _shared(table, x, [0], name, x_label="Point number", notes=notes)
    if layout in ("xy", "shared"):
        return _shared(table, table.data[:, 0], list(range(1, table.n_columns)), name, x_label=table.headers[0], notes=notes)
    if layout == "pairs":
        return _pairs(table, name, notes)
    if layout == "map":
        n_pos, n_wave = _map_shape(table) or (0, 0)
        raise ValueError(
            f"{name} looks like a map: rows of {', '.join(table.headers[:table.n_columns]) or 'X, Y, wavenumber, intensity'} "
            f"({n_pos} positions × {n_wave} points). Reading maps in this long format is planned but not "
            "supported yet (docs/roadmap.md, map files). To read the columns as a plain table anyway, "
            "give layout='shared'.")
    raise ValueError(f"Unknown layout {layout!r}; use 'y', 'xy', 'pairs' or 'shared'.")


def _shared(table: Table, x: np.ndarray, ys: list[int], name: str, x_label: str, notes: list[str]):
    """One x axis with one or more y columns."""
    Y = table.data[:, ys].T                                  # rows = spectra
    # Drop rows (points) where x or any y is missing.
    ok = np.isfinite(x) & np.all(np.isfinite(Y), axis=0)
    if not ok.all():
        notes.append(f"Dropped {int((~ok).sum())} row(s) with a missing value.")
    x, Y = _ascending(x[ok], Y[:, ok], notes)
    meta = dict(table.meta, load_notes=notes)
    if len(ys) == 1:                                         # a single spectrum
        return Spectrum(x, Y[0], name=name, x_unit=x_label, y_unit=table.headers[ys[0]], meta=meta)
    names = [table.headers[p] or f"Column {table.columns[p] + 1}" for p in ys]
    return SpectrumCollection(x, Y, names=names, x_unit=x_label, meta=meta)


# Words that make a header an axis title rather than a sample name.
_AXIS_WORDS = ("wavenumber", "wave number", "raman shift", "shift", "wavelength", "cm-1", "cm⁻¹",
               "intensity", "counts", "absorbance", "transmittance", "energy", "frequency")


def _is_axis_title(text: str) -> bool:
    """True for headers like "Wavenumber (cm-1)" or "Intensity", or a bare "x"/"y"."""
    t = text.strip().lower()
    return t in ("x", "y") or any(w in t for w in _AXIS_WORDS)


def _pairs(table: Table, name: str, notes: list[str]):
    """x, y, x, y, ... columns: one spectrum per pair."""
    spectra = []
    for k, c in enumerate(range(0, table.n_columns - 1, 2)):
        x, y = table.data[:, c], table.data[:, c + 1]
        ok = np.isfinite(x) & np.isfinite(y)                 # each pair can have its own length
        pair_notes: list[str] = []
        xs, ys = _ascending(x[ok], y[ok][None, :], pair_notes)
        # Name: the header above the x column (e.g. "1"), else above y, else a
        # number. Axis titles such as "Wavenumber" or "Intensity" are not names.
        heads = [h for h in (table.headers[c], table.headers[c + 1]) if h and not _is_axis_title(h)]
        label = heads[0] if heads else f"Spectrum {k + 1}"
        spectra.append(Spectrum(xs, ys[0], name=label, meta={"pair_notes": pair_notes}))
    # Report each distinct ordering note once, not once per pair.
    for n in dict.fromkeys(n for s in spectra for n in s.meta["pair_notes"]):
        notes.append(n)
    meta = dict(table.meta, load_notes=notes)
    same_x = all(s.x.shape == spectra[0].x.shape and np.allclose(s.x, spectra[0].x) for s in spectra)
    if same_x:
        notes.append("All pairs share the same x values; combined into one collection.")
        return SpectrumCollection(spectra[0].x, np.vstack([s.y for s in spectra]),
                                  names=[s.name for s in spectra], meta=meta)
    notes.append("The pairs have different x values; returned as a list of spectra.")
    return [s.copy_with(meta=meta) for s in spectra]
