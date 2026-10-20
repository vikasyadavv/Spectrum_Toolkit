"""Read spreadsheets: .xlsx (Excel 2007 and later) and .xls (older Excel).

- .xlsx is read with ``openpyxl``; .xls with ``xlrd`` (version 2 reads only
  .xls, which is exactly what it is used for here).
- Formulas are read as their last saved values, not the formula text.
- If ``sheet`` is not given, the sheet with the most rows of numbers is used,
  so a workbook with an "Info" sheet before the data still works.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._table import Table, numeric_row


def _sheets_xlsx(path: Path) -> dict[str, list[list[Any]]]:
    """All sheets of an .xlsx file as {sheet name: rows of cells}."""
    import openpyxl  # imported here so the library loads even if openpyxl is missing

    # read_only streams the file (low memory for big sheets);
    # data_only returns the values of formulas instead of "=A1*2".
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return {ws.title: [list(r) for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets}
    finally:
        wb.close()                       # read-only workbooks keep the file open until closed


def _sheets_xls(path: Path) -> dict[str, list[list[Any]]]:
    """All sheets of an old .xls file as {sheet name: rows of cells}."""
    import xlrd

    book = xlrd.open_workbook(path, on_demand=True)   # on_demand loads sheets one at a time
    try:
        out = {}
        for name in book.sheet_names():
            sh = book.sheet_by_name(name)
            # xlrd gives "" for empty cells; turn them into None like openpyxl.
            out[name] = [[None if v == "" else v for v in sh.row_values(i)] for i in range(sh.nrows)]
        return out
    finally:
        book.release_resources()


def _count_numeric(rows: list[list[Any]], decimal_comma: bool) -> int:
    """How many rows of the sheet are data rows."""
    return sum(numeric_row(r, decimal_comma) is not None for r in rows)


def read_excel(path: str | Path, sheet: str | int | None = None) -> Table:
    """Read one sheet of a workbook into a Table.

    Parameters
    ----------
    sheet : sheet name, or its number (1 = first sheet). Default: the sheet
        with the most rows of numbers.
    """
    path = Path(path)
    sheets = _sheets_xls(path) if path.suffix.lower() == ".xls" else _sheets_xlsx(path)
    names = list(sheets)
    if not names:
        raise ValueError("The workbook has no sheets.")

    # Which sheets to consider, and which decimal mark: some exports store
    # numbers as text with decimal commas ("1001,5"), so both are tried.
    if sheet is None:
        candidates = names
    elif isinstance(sheet, int):
        if not 1 <= sheet <= len(names):
            raise ValueError(f"sheet={sheet} but the workbook has {len(names)} sheet(s): {names}.")
        candidates = [names[sheet - 1]]
    else:
        if sheet not in sheets:
            raise ValueError(f"No sheet named {sheet!r}. Sheets: {names}.")
        candidates = [sheet]
    count, chosen, decimal_comma = max(
        ((_count_numeric(sheets[s], dc), s, dc) for s in candidates for dc in (False, True)),
        key=lambda t: t[0],              # most data rows wins; first one on a tie
    )
    if count == 0:
        raise ValueError(f"No rows of numbers found in sheet(s) {candidates}.")

    table = Table(sheets[chosen], decimal_comma=decimal_comma)
    table.meta["sheet"] = chosen
    table.meta["sheets"] = names
    if len(names) > 1:
        table.notes.insert(0, f"Workbook has {len(names)} sheets {names}; read {chosen!r}.")
    return table
