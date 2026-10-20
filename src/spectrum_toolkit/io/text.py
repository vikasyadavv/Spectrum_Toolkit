"""Read text data files: .txt .csv .tsv .dat .asc .xy .prn and similar.

The reader works out by itself:

- the text encoding (UTF-8, UTF-16 as written by some Windows software, or
  Windows-1252 for older files with accented characters);
- the line endings (Windows, Unix or old Mac);
- the column separator (tab, semicolon, comma, pipe or spaces);
- whether numbers use a decimal comma (1001,5) instead of a decimal point.

Both separator and decimal mark can be forced with ``delimiter=`` and
``decimal=`` when the guess is wrong.
"""

from __future__ import annotations

import warnings
from collections import Counter
from pathlib import Path

import numpy as np

from ._table import Table, numeric_row

# Separators to try, with the function that splits a line by them.
# "space" means one or more spaces/tabs, as in A_A_1.asc.
DELIMITERS = {
    "tab": lambda line: line.split("\t"),
    "semicolon": lambda line: line.split(";"),
    "comma": lambda line: line.split(","),
    "pipe": lambda line: line.split("|"),
    "space": lambda line: line.split(),
}


def decode(raw: bytes) -> str:
    """Bytes from the file -> text, choosing the right encoding."""
    # A byte-order mark at the start says exactly which UTF-16 variant it is.
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    # UTF-16 without a mark: every other byte is zero for plain text.
    sample = raw[:400]
    if sample and sample.count(0) > len(sample) / 4:
        return raw.decode("utf-16-le" if sample[1::2].count(0) > sample[::2].count(0) else "utf-16-be")
    try:
        # utf-8-sig also removes the invisible mark some Windows tools add.
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Older Windows files (e.g. "Intensität" saved by Excel) use this.
        return raw.decode("cp1252", errors="replace")


def detect_format(lines: list[str]) -> tuple[str, bool]:
    """Pick the separator and decimal mark that read the most lines as data.

    Every combination is tried on the first 400 non-empty lines. The winner is
    the one giving the most data rows with the same number of columns, with a
    bonus for 2+ columns (spectra need x and y).
    """
    sample = [ln for ln in lines if ln.strip()][:400]
    best, best_score = ("space", False), -1.0
    for name, split in DELIMITERS.items():
        # A decimal comma cannot be combined with comma as separator.
        for decimal_comma in ([False] if name == "comma" else [False, True]):
            widths = Counter()
            for line in sample:
                row = numeric_row(split(line), decimal_comma)
                if row is not None:
                    widths[len(row)] += 1
            if not widths:
                continue
            width, count = widths.most_common(1)[0]       # most common row width
            score = count * (2 if width >= 2 else 1)
            if score > best_score:                        # ties keep the earlier, simpler option
                best, best_score = (name, decimal_comma), score
    return best


def read_text(path: str | Path, delimiter: str | None = None, decimal: str | None = None) -> Table:
    """Read a text file into a Table (see ``_table.Table``).

    Parameters
    ----------
    delimiter : "tab", "semicolon", "comma", "pipe" or "space" to skip detection.
    decimal : "." or "," to skip detection.
    """
    text = decode(Path(path).read_bytes())
    # splitlines handles \\r\\n (Windows), \\n (Unix) and \\r (old Mac) alike.
    lines = text.splitlines()
    name, decimal_comma = detect_format(lines)
    if delimiter is not None:
        if delimiter not in DELIMITERS:
            raise ValueError(f"delimiter must be one of {list(DELIMITERS)}, got {delimiter!r}.")
        name = delimiter
    if decimal is not None:
        decimal_comma = decimal == ","
    split = DELIMITERS[name]
    fast = _fast_block(lines, name, decimal_comma)
    if fast is not None:
        # Only the lines around the data need splitting into cells; the data
        # rows themselves were parsed in one go. Data rows are left as empty
        # placeholders because Table will not look at them.
        start, stop, _ = fast
        rows = [split(line) if (i < start or i >= stop) else [] for i, line in enumerate(lines)]
    else:
        rows = [split(line) for line in lines]
    table = Table(rows, decimal_comma=decimal_comma, raw_lines=lines, fast=fast)
    table.meta["delimiter"] = name
    table.meta["decimal"] = "," if decimal_comma else "."
    return table


# numpy's separator for each named delimiter (None = any run of whitespace).
_NUMPY_SEP = {"tab": "\t", "semicolon": ";", "comma": ",", "pipe": "|", "space": None}


def _fast_block(lines: list[str], delimiter: str, decimal_comma: bool) -> tuple[int, int, np.ndarray] | None:
    """Parse a clean numeric block in one fast numpy call.

    Big files (a million rows) are slow to read one cell at a time, so for
    the common case of "some header lines, then a clean table of numbers,
    then maybe some footer lines", the table is handed to numpy's C parser.

    Returns (start, stop, data), or None when the block is not clean (missing
    values, label rows in the middle, ragged rows); the careful cell-by-cell
    reader then takes over.
    """
    split = DELIMITERS[delimiter]

    def is_data(line: str) -> bool:
        return numeric_row(split(line), decimal_comma) is not None

    # First data line from the top, last data line from the bottom.
    start = next((i for i, ln in enumerate(lines) if is_data(ln)), None)
    if start is None:
        return None
    stop = next(i for i in range(len(lines) - 1, -1, -1) if is_data(lines[i])) + 1
    block = [ln for ln in lines[start:stop] if ln.strip()]           # drop blank lines
    if decimal_comma:
        block = [ln.replace(",", ".") for ln in block]                # 1001,5 -> 1001.5
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")                            # treat numpy warnings as failure
            data = np.loadtxt(block, delimiter=_NUMPY_SEP[delimiter], ndmin=2, dtype=float)
    except (ValueError, UserWarning):
        return None                                                   # not clean: use the careful path
    return start, stop, data


def looks_like_text(raw: bytes) -> bool:
    """True if the bytes are text rather than a binary instrument file."""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return True
    sample = raw[:2048]
    if sample.count(0) > len(sample) / 4:                 # UTF-16 text has many zero bytes
        return True
    # Control characters other than tab/newline/carriage return mean binary.
    control = sum(1 for b in sample if b < 9 or 13 < b < 32)
    return control <= len(sample) * 0.05


__all__ = ["read_text", "decode", "detect_format", "looks_like_text", "DELIMITERS"]
