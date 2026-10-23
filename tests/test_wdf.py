"""Tests for reading Renishaw WiRE .wdf files (src/spectrum_toolkit/io/wdf.py).

Most tests write a small .wdf file themselves (``write_wdf`` below builds the
same blocks WiRE writes: WDF1, DATA, XLST, YLST, ORGN, WMAP), so they run
without the data/ folder. Tests marked "real data" use the WiRE 5.6 files in
data/ and are skipped when that folder is not present.
"""

import struct
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

import spectrum_toolkit as stk
from spectrum_toolkit import Spectrum, SpectrumCollection

DATA = Path(__file__).parent.parent / "data"

# A made-up axis stored falling, as WiRE stores it, and spectra with a band at 1000.
X = np.linspace(1700, 500, 300)


def filetime(when):
    """A date and time (UTC) as Windows stores it: 100-nanosecond steps since 1 January 1601."""
    return int((when - datetime(1601, 1, 1, tzinfo=timezone.utc)).total_seconds() * 10_000_000)


def band(height):
    """A spectrum: background 100 plus a band at x = 1000 of the given height."""
    return 100 + height * np.exp(-((X - 1000) / 15) ** 2)


def block(name, body, number=0):
    """One block: its 16-byte header (name, number, size including the header), then its contents."""
    return struct.pack("<4sIQ", name, number, 16 + len(body)) + body


def write_wdf(path, Y, positions=None, grid=None, y_rows=1, count=None, title="Test measurement"):
    """Write a .wdf file with the spectra Y (one row each) on the axis X, as WiRE does.

    positions: one (X, Y) row per spectrum, written as the ORGN origins X and Y.
    grid: (nx, ny) for the WMAP block of a map. count: the number of spectra
    the header says were measured (default: all rows of Y).
    """
    Y = np.atleast_2d(Y)
    n = len(Y) if count is None else count
    head = bytearray(512)                                        # the 512-byte file header
    head[0:4] = b"WDF1"
    struct.pack_into("<I", head, 4, 1)
    struct.pack_into("<Q", head, 8, 512)                         # its own size
    struct.pack_into("<I", head, 0x3C, X.size)                   # points per spectrum
    struct.pack_into("<QQ", head, 0x40, len(Y), n)               # planned and measured spectra
    struct.pack_into("<IIII", head, 0x50, 2, y_rows, X.size, 0 if positions is None else 2)
    head[0x60:0x64] = b"WiRE"
    struct.pack_into("<4H", head, 0x78, 5, 6, 0, 30846)          # WiRE version 5.6.0.30846
    struct.pack_into("<II", head, 0x80, 1, 3 if grid else 1)     # static scan; map or single
    struct.pack_into("<QQ", head, 0x88, filetime(datetime(2023, 11, 22, 6, 36, 44, tzinfo=timezone.utc)),
                     filetime(datetime(2023, 11, 22, 6, 36, 50, tzinfo=timezone.utc)))      # start, end
    struct.pack_into("<If", head, 0x98, 6, 1e7 / 632.8)          # counts; laser line in cm⁻¹
    head[0xD0:0xD5] = b"admin"
    head[0xF0:0xF0 + len(title)] = title.encode()
    out = bytes(head)
    out += block(b"DATA", Y.astype("<f4").tobytes())
    out += block(b"YLST", struct.pack("<II", 4, 16) + np.ones(y_rows, "<f4").tobytes())
    out += block(b"XLST", struct.pack("<II", 1, 1) + X.astype("<f4").tobytes())   # Raman shift, cm⁻¹
    if positions is not None:
        body = struct.pack("<I", 2)                              # two origins: X and Y
        for k, (kind, label) in enumerate(((3, b"X"), (4, b"Y"))):
            body += struct.pack("<II", kind | 0x80000000, 5) + label.ljust(16, b"\0")   # primary, µm
            body += np.asarray(positions, dtype="<f8")[:, k].tobytes()
        out += block(b"ORGN", body)
    if grid:
        body = struct.pack("<II3f3f3I", 0, 0, positions[0][0], positions[0][1], 0, 1, 1, 1, grid[0], grid[1], 1)
        out += block(b"WMAP", body + bytes(64 - 16 - len(body)))
    Path(path).write_bytes(out)
    return Path(path)


def test_single_spectrum(tmp_path):
    """One spectrum: a Spectrum named after the file, x turned to rising, the instrument details kept."""
    s = stk.load(write_wdf(tmp_path / "one.wdf", band(1000)), verbose=False)
    assert isinstance(s, Spectrum) and s.name == "one"
    assert np.all(np.diff(s.x) > 0)                              # x rises
    assert s.x[np.argmax(s.y)] == pytest.approx(1000, abs=4)     # the band is still at 1000 after the flip
    np.testing.assert_allclose(s.y, band(1000)[::-1], rtol=1e-6)  # values as written (4-byte numbers)
    assert s.x_unit == "Raman shift (cm⁻¹)" and s.y_unit == "counts"
    assert s.meta["laser_nm"] == 632.8 and s.meta["accumulations"] == 2 and s.meta["measurement"] == "single"
    assert s.meta["instrument"] == "Renishaw WiRE 5.6.0.30846" and s.meta["title"] == "Test measurement"
    assert s.meta["start"] == "2023-11-22T06:36:44Z" and s.meta["file_type"] == "wdf"


def test_map_has_positions_and_grid(tmp_path):
    """A 3 x 2 map: a collection of 6 spectra, with X and Y of each in .positions and the grid in meta."""
    pos = [(x, y) for y in (10.0, 11.0) for x in (-5.0, -4.0, -3.0)]   # X changes fastest, as in WiRE maps
    Y = np.vstack([band(100 * (k + 1)) for k in range(6)])
    c = stk.load(write_wdf(tmp_path / "map.wdf", Y, positions=pos, grid=(3, 2)), verbose=False)
    assert isinstance(c, SpectrumCollection) and len(c) == 6 and c.names[0] == "Spectrum 1"
    np.testing.assert_array_equal(c.positions, pos)             # one row per spectrum, in measuring order
    assert c.meta["position_labels"] == ["X (µm)", "Y (µm)"]
    assert c.meta["map"]["points"] == [3, 2, 1] and c.meta["measurement"] == "map"
    assert c.Y[5].max() == pytest.approx(band(600).max(), rel=1e-6)   # the last spectrum, as written
    assert any("Map of 3 x 2 positions" in n for n in c.meta["load_notes"])
    sub = c.select(1, 4)                                         # positions follow their spectra
    np.testing.assert_array_equal(sub.positions, [pos[1], pos[4]])


def test_stopped_measurement_reads_only_the_measured_spectra(tmp_path):
    """Room for 4 spectra but only 2 measured (stopped early): only those 2 come back."""
    Y = np.vstack([band(h) for h in (100, 200, 0, 0)])
    c = stk.load(write_wdf(tmp_path / "stopped.wdf", Y, count=2), verbose=False)
    assert len(c) == 2 and c.Y[1].max() == pytest.approx(band(200).max(), rel=1e-6)


def test_wrong_files_give_clear_errors(tmp_path):
    """Damaged, empty or unsupported .wdf files give a message saying what is wrong."""
    good = write_wdf(tmp_path / "good.wdf", band(1000)).read_bytes()
    (tmp_path / "cut.wdf").write_bytes(good[:1000])               # file ends inside the DATA block
    with pytest.raises(ValueError, match="damaged or incomplete"):
        stk.load(tmp_path / "cut.wdf", verbose=False)
    with pytest.raises(ValueError, match="holds no spectra"):
        stk.load(write_wdf(tmp_path / "none.wdf", band(1000), count=0), verbose=False)
    with pytest.raises(ValueError, match="detector images"):
        stk.load(write_wdf(tmp_path / "image.wdf", band(1000), y_rows=4), verbose=False)
    (tmp_path / "other.wdf").write_bytes(b"XXXX" + bytes(600))   # .wdf name, but not a WiRE file
    with pytest.raises(ValueError, match="does not start like a Renishaw WiRE file"):
        stk.load(tmp_path / "other.wdf", verbose=False)


def test_service_sends_map_positions(tmp_path):
    """/load of a map answers the positions and their labels; /process keeps them."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from spectrum_toolkit.api import app
    client = TestClient(app)
    pos = [(0.0, 0.0), (1.0, 0.0)]
    f = write_wdf(tmp_path / "map.wdf", np.vstack([band(100), band(200)]), positions=pos, grid=(2, 1))
    r = client.post("/load", files={"file": ("map.wdf", f.read_bytes())}).json()["data"]
    assert r["positions"] == [[0.0, 0.0], [1.0, 0.0]] and r["position_labels"] == ["X (µm)", "Y (µm)"]
    done = client.post("/process", json={"data": r, "recipe": {"steps": [{"step": "baseline"}]}}).json()
    assert done["data"]["positions"] == r["positions"]           # processing keeps where each spectrum was


real = pytest.mark.skipif(not DATA.is_dir(), reason="data/ folder not present")


@real
def test_real_silicon_after_calibration():
    """The calibrated silicon file has its band at 520.7 cm⁻¹ (the silicon reference), the other at 521.7."""
    for name, expected in (("silicon quick caliberation_2.wdf", 520.7), ("silicon quick caliberation.wdf", 521.7)):
        f = DATA / name
        if not f.exists():
            pytest.skip(f"{name} not in data/")
        s = stk.load(f, verbose=False)
        i = int(np.argmax(s.y))
        a, b, c = s.y[i - 1:i + 2]                               # parabola through the top 3 points
        peak = s.x[i] + 0.5 * (a - c) / (a - 2 * b + c) * (s.x[i + 1] - s.x[i])
        assert peak == pytest.approx(expected, abs=0.1)          # tolerance: 0.1 cm⁻¹ (points are 1.24 apart)


@real
def test_real_maps():
    """The two WiRE maps: 17 x 20 and 21 x 18 positions, 1 µm apart, every grid place measured once."""
    for name, (nx, ny) in (("con-stem_map_later.wdf", (17, 20)), ("pga-stem_map.wdf", (21, 18))):
        f = DATA / name
        if not f.exists():
            pytest.skip(f"{name} not in data/")
        c = stk.load(f, verbose=False)
        assert len(c) == nx * ny and c.positions.shape == (nx * ny, 2)
        assert len(np.unique(c.positions[:, 0])) == nx and len(np.unique(c.positions[:, 1])) == ny
        assert np.allclose(np.diff(np.unique(c.positions[:, 0])), 1.0)   # 1 µm steps
        assert c.meta["white_light"][:2] == b"\xff\xd8"           # the camera image is a JPEG
