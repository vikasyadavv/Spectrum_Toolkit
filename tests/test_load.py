"""Tests for loading files (src/spectrum_toolkit/io/).

tests/fixtures/ holds small, deliberately awkward files. Each one copies a
quirk seen in real exports. They all contain the same made-up spectrum:
50 points, x = 200, 202, ... 298, a background of 100 and a peak of 1100 at
x = 260. So for every file we can check the same three numbers.

Tests marked "real data" use the files in data/ and are skipped when that
folder is missing (e.g. inside the Docker image).
"""

from pathlib import Path

import numpy as np
import pytest

import spectrum_toolkit as stk
from spectrum_toolkit import Spectrum, SpectrumCollection

FIX = Path(__file__).parent / "fixtures"
DATA = Path(__file__).parent.parent / "data"


def is_reference(s, n=50):
    """True if s holds the reference spectrum described above."""
    i = int(np.argmin(np.abs(s.x - 260)))                 # index of x = 260
    return len(s.x) == n and np.isclose(s.x[0], 200) and np.isclose(s.y[0], 100, atol=0.01) and np.isclose(s.y[i], 1100, atol=0.01)


def notes(s):
    """All load notes as one string, for easy "in" checks."""
    return " | ".join(s.meta["load_notes"])


# Each case: file name, and an extra check beyond is_reference().
CASES = {
    "01_tab_header.txt":         lambda s: s.x_unit == "Raman Shift (cm-1)" and s.y_unit == "Intensity (counts)",
    "02_horiba_meta.txt":        lambda s: s.meta["metadata"]["Laser (nm)"] == "532" and s.x_unit == "",
    "03_euro_semicolon.csv":     lambda s: s.meta["decimal"] == "," and s.y_unit == "Intensität",
    "04_euro_space.txt":         lambda s: s.meta["decimal"] == ",",
    "05_descending_renishaw.txt": lambda s: "descending" in notes(s) and (s.x_unit, s.y_unit) == ("Wave", "Intensity"),
    "09_footer.txt":             lambda s: s.meta["metadata"]["Operator"] == "VY",
    "10_utf16_bom.txt":          lambda s: s.y_unit == "Abs",
    "11_mac_cr.txt":             lambda s: True,
    "12_scientific.dat":         lambda s: True,
    "13_quoted.csv":             lambda s: s.x_unit == "Raman shift",
    "14_comma_space.csv":        lambda s: True,
    "21_meta_rows.xlsx":         lambda s: s.meta["sheet"] == "Data" and s.x_unit == "Raman shift",
    "22_text_decimal_comma.xlsx": lambda s: True,
    "23_old_excel.xls":          lambda s: True,
}


@pytest.mark.parametrize("name", CASES)          # runs the test once per file
def test_awkward_single_spectrum(name):
    s = stk.load(FIX / name, verbose=False)
    assert isinstance(s, Spectrum)
    assert is_reference(s), f"wrong numbers from {name}"
    assert CASES[name](s), f"extra check failed for {name}"


def test_missing_values_are_dropped_and_reported():
    s = stk.load(FIX / "06_missing_values.csv", verbose=False)
    assert is_reference(s, n=47)                 # 3 of 50 rows had a gap
    assert "Dropped 3 row(s)" in notes(s)


def test_multi_column_gives_collection_on_shared_x():
    c = stk.load(FIX / "07_multi_column.csv", verbose=False)
    assert isinstance(c, SpectrumCollection)
    assert c.names == ("sample A", "sample B", "sample C")
    assert np.allclose(c.Y[2], 3 * c.Y[0])       # sample C was written as 3 × sample A


def test_choose_columns_by_hand():
    s = stk.load(FIX / "07_multi_column.csv", x_col=1, y_cols=[4], verbose=False)
    assert isinstance(s, Spectrum) and s.y_unit == "sample C"
    assert "chosen by hand" in notes(s)


def test_single_column_uses_point_number():
    s = stk.load(FIX / "08_single_column.txt", verbose=False)
    assert s.x[0] == 0 and s.x[-1] == 49 and s.x_unit == "Point number"


@pytest.mark.parametrize("name", ["19_no_numbers.txt", "20_unknown_binary.wdf"])
def test_unreadable_files_give_clear_errors(name):
    with pytest.raises(ValueError):
        stk.load(FIX / name, verbose=False)


def test_large_file_is_fast(tmp_path):
    """200,000 rows with a header load correctly and quickly (fast path)."""
    import time
    x = np.linspace(100, 4000, 200_000)
    f = tmp_path / "big.txt"
    np.savetxt(f, np.c_[x, np.sin(x)], fmt="%.6f", delimiter="\t", header="Wavenumber\tIntensity", comments="")
    t0 = time.perf_counter()
    s = stk.load(f, verbose=False)
    assert time.perf_counter() - t0 < 5           # generous limit for slow machines
    assert len(s) == 200_000 and s.x_unit == "Wavenumber"
    assert np.allclose(s.y, np.round(np.sin(s.x), 6), atol=2e-6)


# ---------------------------------------------------------------- real data
real = pytest.mark.skipif(not DATA.is_dir(), reason="data/ folder not present")


@real
def test_real_asc():
    s = stk.load(DATA / "A_A_1.asc", verbose=False)
    assert len(s) == 1024 and np.isclose(s.x[0], 100.01566) and s.y[0] == 2673


@real
def test_real_xlsx_pairs():
    c = stk.load(DATA / "MB 10-4M.xlsx", verbose=False)
    assert isinstance(c, SpectrumCollection)
    assert len(c) == 5 and c.n_points == 1425
    assert c.names == ("1", "2", "3", "4", "5")              # from the "Sample" row
    assert np.all(np.diff(c.x) > 0)                          # turned to ascending
    assert np.isclose(c.x[-1], 1802.94727) and np.isclose(c.Y[0, -1], 194.10625)


@real
def test_real_xlsx_35_pairs():
    """CV+RhB+MB: 35 x/y pairs, clipped to 1600-1700, all on the same x."""
    c = stk.load(DATA / "CV+RhB+MB_data cliped from 1600 to 1700.xlsx", verbose=False)
    assert isinstance(c, SpectrumCollection) and c.Y.shape == (35, 40)   # 35 spectra, 40 points
    assert 1600 <= c.x[0] and c.x[-1] <= 1700 and np.all(np.diff(c.x) > 0)
