"""Tests for loading MATLAB .mat files (src/spectrum_toolkit/io/matlab.py).

Each test writes a small .mat file with scipy (the same library MATLAB files
are read with), using different variable names and arrangements, and checks
that ``stk.load`` finds the spectra without being told where they are.
"""

from pathlib import Path

import numpy as np
import pytest
import scipy.io

import spectrum_toolkit as stk
from spectrum_toolkit import Spectrum, SpectrumCollection

DATA = Path(__file__).parent.parent / "data"

# A made-up axis and 3 spectra: background 100 plus a peak at x = 1000 of
# height 1000, 2000 and 3000.
X = np.linspace(400, 1800, 200)
Y = np.vstack([100 + k * 1000 * np.exp(-((X - 1000) / 20) ** 2) for k in (1, 2, 3)])   # 3 x 200


def write(tmp_path, **variables):
    """Save the given variables to a .mat file and return its path."""
    f = tmp_path / "test.mat"
    scipy.io.savemat(f, variables)
    return f


def notes(r):
    """All load notes as one string."""
    return " | ".join(r.meta["load_notes"])


def test_axis_and_spectra_in_columns(tmp_path):
    """MATLAB's usual way: x as a column vector, spectra as columns (like W and wt)."""
    f = write(tmp_path, wavenumber=X[:, None], spectra=Y.T)       # 200x1 and 200x3
    c = stk.load(f, verbose=False)
    assert isinstance(c, SpectrumCollection) and c.Y.shape == (3, 200)   # 3 spectra found
    assert np.allclose(c.x, X) and np.allclose(c.Y, Y)                   # numbers unchanged
    assert c.names == ("spectra 1", "spectra 2", "spectra 3")            # named after the variable
    assert "one per column" in notes(c)                                  # the guess is reported


def test_spectra_in_rows_and_descending_axis(tmp_path):
    """Spectra stored as rows, x written high to low: turned around and reported."""
    f = write(tmp_path, ax=X[::-1], M=Y[:, ::-1])                  # 1x200 and 3x200
    c = stk.load(f, verbose=False)
    assert np.allclose(c.x, X) and np.allclose(c.Y, Y)             # back in ascending order
    assert "one per row" in notes(c) and "descending" in notes(c)


def test_biggest_matrix_wins_and_others_are_listed(tmp_path):
    """Several variables fit the axis: the biggest matrix is used, the others are offered."""
    f = write(tmp_path, x=X, single=Y[0], small=Y[:2].T, big=Y.T)
    c = stk.load(f, verbose=False)
    assert c.Y.shape == (3, 200)                                   # "big" was used
    assert "y='small'" in notes(c) and "y='single'" in notes(c)    # the others are offered


def test_choose_by_name(tmp_path):
    """x= and y= override the guess."""
    f = write(tmp_path, x=X, small=Y[:1].T, big=Y.T)
    s = stk.load(f, x="x", y="small", verbose=False)
    assert isinstance(s, Spectrum) and np.allclose(s.y, Y[0])      # one spectrum
    assert "chosen by hand" in notes(s)


def test_wrong_name_lists_the_real_ones(tmp_path):
    """A misspelt name gives an error listing the variables in the file."""
    f = write(tmp_path, x=X, big=Y.T)
    with pytest.raises(ValueError, match="'big'"):
        stk.load(f, y="Big", verbose=False)


def test_matrix_without_axis_vector_is_read_like_a_table(tmp_path):
    """One matrix with x in its first column, like a pasted spreadsheet."""
    f = write(tmp_path, data=np.c_[X, Y.T])                        # 200 x 4
    c = stk.load(f, verbose=False)
    assert np.allclose(c.x, X) and np.allclose(c.Y, Y)


def test_vectors_only(tmp_path):
    """Separate x and y vectors of the same length."""
    f = write(tmp_path, shift=X, counts=Y[0])
    s = stk.load(f, verbose=False)
    assert isinstance(s, Spectrum) and np.allclose(s.y, Y[0]) and s.x_unit == "shift"


def test_structures_are_searched(tmp_path):
    """Variables inside a structure (s.field) are found."""
    f = write(tmp_path, meas={"wn": X, "I": Y.T, "laser": 532})
    c = stk.load(f, verbose=False)
    assert c.x_unit == "meas.wn" and c.Y.shape == (3, 200)


def test_text_and_cubes_are_skipped_with_a_note(tmp_path):
    """Text and 3-D arrays cannot be spectra; they are listed as skipped."""
    f = write(tmp_path, x=X, y=Y.T, label="sample A", cube=np.zeros((2, 2, 2)))
    c = stk.load(f, verbose=False)
    assert "label (text" in notes(c) and "cube (2 x 2 x 2" in notes(c)


def test_v73_file_gives_clear_error(tmp_path):
    """A v7.3 file (HDF5 inside) is not supported yet and says how to re-save it."""
    f = tmp_path / "new.mat"
    f.write_bytes(b"MATLAB 7.3 MAT-file".ljust(512, b" ") + b"\x89HDF\r\n\x1a\n" + bytes(100))
    with pytest.raises(ValueError, match="-v7"):
        stk.load(f, verbose=False)


def test_variable_names_only_for_mat(tmp_path):
    """x=/y= on a text file is a mistake; the error points to x_col=/y_cols=."""
    f = tmp_path / "a.txt"
    f.write_text("1 2\n2 3\n")
    with pytest.raises(ValueError, match="x_col"):
        stk.load(f, y="a", verbose=False)


def test_mat_variables_lists_everything_with_sizes(tmp_path):
    """mat_variables: every variable with its size, the pairs that fit, the pair load uses, and what was skipped."""
    f = write(tmp_path, x=X, single=Y[0], big=Y.T, meas={"wn": X[::-1]}, label="sample A")
    info = stk.mat_variables(f)
    rows = {v["name"]: v for v in info["variables"]}
    assert list(rows) == ["big", "meas.wn", "single", "x"]          # sorted by name; structure fields as s.field
    assert rows["big"]["size"] == [200, 3] and rows["big"]["kind"] == "matrix"   # as MATLAB's size()
    assert rows["x"]["size"] == [200] and rows["x"]["can_be_x"] and rows["meas.wn"]["can_be_x"]  # falling counts too
    assert not rows["single"]["can_be_x"]                           # a spectrum goes up and down
    assert rows["x"]["min"] == pytest.approx(400) and rows["x"]["max"] == pytest.approx(1800)
    first = info["choices"][0]                                      # biggest first
    assert (first["x"], first["y"], first["spectra"], first["points"], first["spectra_in"]) == \
        (first["x"], "big", 3, 200, "columns")
    assert {"x": "x", "y": "single", "spectra": 1, "points": 200, "spectra_in": "vector"} in info["choices"]
    assert info["chosen"]["y"] == "big"                             # what load picks by itself
    assert any("label" in s for s in info["skipped"])


def test_chosen_follows_the_names_given(tmp_path):
    """Names given by hand are recorded as the choice; only y given means point number for x."""
    f = write(tmp_path, x=X, single=Y[0], big=Y.T)
    s = stk.load(f, x="x", y="single", verbose=False)
    assert s.meta["variables"]["chosen"] == {"x": "x", "y": "single"}
    s = stk.load(f, y="single", verbose=False)                     # "single" fits x, so x is found
    assert s.meta["variables"]["chosen"]["x"] == "x"
    f = write(tmp_path, counts=Y[0])
    s = stk.load(f, verbose=False)
    assert s.meta["variables"]["chosen"] == {"x": None, "y": "counts"} and s.x_unit == "Point number"


def test_mat_variables_still_lists_when_load_cannot_guess(tmp_path):
    """No numbers at all: a clear error. A file load cannot read by itself: the table plus the problem."""
    f = write(tmp_path, label="only text")
    with pytest.raises(ValueError, match="no numeric vectors or matrices"):
        stk.mat_variables(f)
    f = write(tmp_path, a=np.array([1.0, 2.0, 3.0]), b=np.array([[np.nan, np.nan], [np.nan, np.nan]]))
    info = stk.mat_variables(f)
    assert [v["name"] for v in info["variables"]] == ["a", "b"]
    assert info["variables"][1]["min"] is None                      # only missing values: no min or max
    assert "chosen" in info


def test_service_lists_variables_and_takes_x_and_y(tmp_path):
    """/load of a .mat file answers the variables; x and y choose another pair; wrong names say which exist."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from spectrum_toolkit.api import app
    client = TestClient(app)
    raw = write(tmp_path, x=X, single=Y[0], big=Y.T).read_bytes()
    r = client.post("/load", files={"file": ("a.mat", raw)}).json()
    assert r["variables"]["chosen"] == {"x": "x", "y": "big"} and r["data"]["n_spectra"] == 3
    assert [v["name"] for v in r["variables"]["variables"]] == ["big", "single", "x"]
    r = client.post("/load", files={"file": ("a.mat", raw)}, data={"x": "x", "y": "single"}).json()
    assert r["data"]["n_spectra"] == 1 and r["variables"]["chosen"] == {"x": "x", "y": "single"}
    r = client.post("/load", files={"file": ("a.mat", raw)}, data={"x": "", "y": ""}).json()
    assert r["variables"]["chosen"]["y"] == "big"                  # empty boxes: guessed as before
    r = client.post("/load", files={"file": ("a.mat", raw)}, data={"y": "Big"})
    assert r.status_code == 422 and "'big'" in r.json()["detail"]  # names the variables that exist
    text = b"1 2\n2 3\n3 5\n"
    r = client.post("/load", files={"file": ("a.txt", text)}, data={"y": "single"})
    assert r.status_code == 422 and ".mat" in r.json()["detail"]   # x and y are for .mat files only
    recipe = '{"steps": [{"step": "normalize", "method": "max"}]}'
    r = client.post("/process-file", files={"file": ("a.mat", raw)}, data={"recipe": recipe, "y": "single"}).json()
    assert r["data"]["n_spectra"] == 1 and max(r["data"]["Y"][0]) == pytest.approx(1)


# ---------------------------------------------------------------- real data
@pytest.mark.skipif(not (DATA / "wt_raw.mat").is_file(), reason="data/wt_raw.mat not present")
def test_real_mat():
    """wt_raw.mat: W (747 x 1) is x for wt (747 x 550), found without help."""
    c = stk.load(DATA / "wt_raw.mat", verbose=False)
    assert c.Y.shape == (550, 747) and c.x_unit == "W" and c.y_unit == "wt"
    assert np.isclose(c.x[0], 441.679688) and np.isclose(c.Y[0, 0], 1016.658752)   # first value of wt
    info = stk.mat_variables(DATA / "wt_raw.mat")                   # the table of what is inside
    assert [(v["name"], v["size"]) for v in info["variables"]] == [("W", [747]), ("data_wt", [410850, 4]),
                                                                    ("wt", [747, 550])]
    assert info["chosen"] == {"x": "W", "y": "wt"}
