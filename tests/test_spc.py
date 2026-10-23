"""Tests for Shimadzu UVProbe .spc files (src/spectrum_toolkit/io/shimadzu.py) and the compound-file
reader under them (src/spectrum_toolkit/io/cfb.py).

``write_cfb`` below writes a small compound file (the container UVProbe
uses), so the tests run without the data/ folder: one stream bigger than
4096 bytes (stored in ordinary sectors) and small ones (stored in mini
sectors), so both ways of storing a stream are read. Tests marked "real
data" use the UVProbe 2.70 files in data/ and are skipped without it.
"""

import struct
from pathlib import Path

import numpy as np
import pytest

import spectrum_toolkit as stk
from spectrum_toolkit import Spectrum, SpectrumCollection
from spectrum_toolkit.io.cfb import CompoundFile

DATA = Path(__file__).parent.parent / "data"
FREE, END, FAT_SECTOR = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD


def write_cfb(path, streams):
    """Write a version 3 compound file holding streams {"/folder/name": bytes}; return its path.

    Layout: sector 0 the FAT, then the directory, the mini FAT, the mini
    stream (all streams under 4096 bytes, in 64-byte pieces) and the big
    streams. Each folder's entries are joined through their "right" link
    (a valid, if unbalanced, tree).
    """
    # Every folder and stream as a directory entry; entry 0 is the root.
    entries = [{"name": "Root Entry", "kind": 5, "children": []}]
    index = {"": 0}
    for p in sorted(streams):
        parts = p.strip("/").split("/")
        for depth in range(1, len(parts) + 1):
            key = "/".join(parts[:depth])
            if key not in index:
                index[key] = len(entries)
                entries.append({"name": parts[depth - 1], "kind": 2 if depth == len(parts) else 1,
                                "children": [], "data": streams[p] if depth == len(parts) else b""})
                entries[index["/".join(parts[:depth - 1])]]["children"].append(index[key])
    small = [e for e in entries if e["kind"] == 2 and len(e["data"]) < 4096]
    big = [e for e in entries if e["kind"] == 2 and len(e["data"]) >= 4096]
    # Mini stream: the small streams in 64-byte mini sectors, chained in the mini FAT.
    mini, mini_fat = b"", []
    for e in small:
        e["start"] = len(mini) // 64 if e["data"] else END
        n = -(-len(e["data"]) // 64)                             # mini sectors needed (rounded up)
        mini_fat += [len(mini_fat) + k + 1 for k in range(n - 1)] + ([END] if n else [])
        mini += e["data"].ljust(n * 64, b"\0")
    pad = lambda b: b.ljust(-(-len(b) // 512) * 512, b"\0")      # fill up to whole 512-byte sectors
    fat = [FAT_SECTOR]                                           # sector 0 holds the FAT itself

    def place(data):
        """Put data in new sectors, chain them in the FAT, return the first sector number."""
        first, n = len(fat), len(pad(data)) // 512
        fat.extend([first + k + 1 for k in range(n - 1)] + [END])
        return first, pad(data)

    sectors = []
    # The directory is written after the streams are placed, so reserve its sectors first.
    dir_size = len(pad(bytes(128 * len(entries))))
    dir_start, _ = place(bytes(dir_size))
    mini_fat_start, mini_fat_bytes = place(struct.pack(f"<{len(mini_fat)}I", *mini_fat))
    mini_start, mini_bytes = place(mini)
    for e in big:
        e["start"], e["bytes"] = place(e["data"])
    entries[0].update(start=mini_start, data=mini)              # the root entry owns the mini stream
    directory = b""
    for i, e in enumerate(entries):
        kids = e["children"]
        for a, b in zip(kids, kids[1:]):                         # siblings joined through "right"
            entries[a]["right"] = b
        name = e["name"].encode("utf-16-le") + b"\0\0"
        directory += (name.ljust(64, b"\0") + struct.pack("<HBB", len(name), e["kind"], 1)
                      + struct.pack("<III", FREE, e.get("right", FREE), kids[0] if kids else FREE)
                      + bytes(36) + struct.pack("<II", e.get("start", END), len(e.get("data", b""))) + bytes(4))
    assert len(fat) <= 128, "write_cfb keeps everything in one FAT sector"
    head = bytearray(512)
    head[:8] = bytes.fromhex("d0cf11e0a1b11ae1")
    struct.pack_into("<HHHHH", head, 0x18, 0x3E, 3, 0xFFFE, 9, 6)   # version 3, 512-byte sectors, 64-byte mini
    struct.pack_into("<IIII", head, 0x2C, 1, dir_start, 0, 0)
    struct.pack_into("<IIIII", head, 0x38, 4096, mini_fat_start, 1, END, 0)
    struct.pack_into("<109I", head, 0x4C, 0, *[FREE] * 108)        # the FAT is sector 0
    body = struct.pack("<128I", *(fat + [FREE] * (128 - len(fat))))
    body += pad(directory) + mini_fat_bytes + mini_bytes + b"".join(e["bytes"] for e in big)
    Path(path).write_bytes(bytes(head) + body)
    return Path(path)


def text(s):
    """A text as UVProbe (an MFC program) stores it: 1 byte of length, then the letters."""
    return bytes([len(s)]) + s.encode("cp1252")


def page(heading, pairs, number=0):
    """One method page: two numbers, the heading, the number of pairs, then names and values."""
    out = struct.pack("<II", 1, number) + text(heading) + struct.pack("<I", len(pairs))
    return out + b"".join(text(k + ":") + text(v) for k, v in pairs.items())


# A made-up UV-Vis spectrum, 900 to 200 nm (stored falling, as UVProbe does), with a band at 520 nm.
WAVELENGTH = np.arange(900, 199.5, -0.5)                         # 1401 points: X Data is over 4096 bytes
ABSORBANCE = 0.05 + 0.5 * np.exp(-((WAVELENGTH - 520) / 40) ** 2)
DATASET = "/DataStorage1/DataSetGroup/DataSet1/"


def uvprobe_streams(mode="Absorbance"):
    """The streams of a one-spectrum UVProbe file."""
    return {
        DATASET + "DataSpectrumStorage/Data/X Data.1": WAVELENGTH.astype("<f8").tobytes(),
        DATASET + "DataSpectrumStorage/Data/Y Data.1": ABSORBANCE.astype("<f8").tobytes(),
        DATASET + "MethodStorage/PageTexts0": page("[Measurement Properties]",
                                                   {"Wavelength Range (nm.)": "200.00 to 900.00", "Scan Speed": "Fast"}),
        DATASET + "MethodStorage/PageTexts2": page("[Instrument Properties]",
                                                   {"Instrument Type": "UV-2400PC Series", "Measuring Mode": mode,
                                                    "Slit Width": "2.0 nm"}, 3),
        DATASET + "DataSetHeaderInfo": text("RawData") + bytes(12) + text("UVProbe") + text("2.70"),
        "/Version/File Format Version": b"\x20\x00\x00\x00",
    }


def test_compound_file_reader_reads_small_and_big_streams(tmp_path):
    """Streams under 4096 bytes (mini sectors) and over (ordinary sectors) come back byte for byte."""
    streams = {"/A/small": b"hello", "/A/B/big": bytes(range(256)) * 20, "/top": b"x" * 100}
    f = CompoundFile(write_cfb(tmp_path / "t.cfb", streams).read_bytes())
    assert f.streams() == sorted(streams)
    for p, data in streams.items():
        assert f.read(p) == data


def test_uvprobe_spectrum(tmp_path):
    """One UVProbe data set: a Spectrum named after the file, x rising, y unit from the Measuring Mode."""
    s = stk.load(write_cfb(tmp_path / "gold.spc", uvprobe_streams()), verbose=False)
    assert isinstance(s, Spectrum) and s.name == "gold" and len(s) == 1401
    assert np.all(np.diff(s.x) > 0) and s.x[0] == 200 and s.x[-1] == 900   # turned round to rising
    np.testing.assert_array_equal(s.y, ABSORBANCE[::-1])          # 8-byte numbers: exactly as written
    assert s.x[np.argmax(s.y)] == 520
    assert s.x_unit == "Wavelength (nm)" and s.y_unit == "Absorbance"
    assert s.meta["instrument"] == "UV-2400PC Series" and s.meta["software"] == "Shimadzu UVProbe 2.70"
    assert s.meta["method"]["Instrument Properties"]["Slit Width"] == "2.0 nm"   # every method setting by name
    assert s.meta["file_type"] == "shimadzu"


def test_two_data_sets_on_one_axis_give_a_collection(tmp_path):
    """Two data sets with the same x: one collection of 2 spectra."""
    streams = uvprobe_streams()
    for name, data in list(streams.items()):
        if name.startswith(DATASET):                             # a copy as DataSet2, twice as strong
            streams[name.replace("DataSet1", "DataSet2")] = data
    second = DATASET.replace("DataSet1", "DataSet2") + "DataSpectrumStorage/Data/Y Data.1"
    streams[second] = (2 * ABSORBANCE).astype("<f8").tobytes()
    c = stk.load(write_cfb(tmp_path / "two.spc", streams), verbose=False)
    assert isinstance(c, SpectrumCollection) and len(c) == 2
    np.testing.assert_allclose(c.Y[1], 2 * c.Y[0])


def test_wrong_spc_files_give_clear_errors(tmp_path):
    """A compound file without spectra, missing y values, and a non-Shimadzu .spc each say what is wrong."""
    with pytest.raises(ValueError, match="without UVProbe spectra"):
        stk.load(write_cfb(tmp_path / "empty.spc", {"/Version/CLSID": bytes(16)}), verbose=False)
    streams = uvprobe_streams()
    del streams[DATASET + "DataSpectrumStorage/Data/Y Data.1"]
    with pytest.raises(ValueError, match="no y values"):
        stk.load(write_cfb(tmp_path / "no_y.spc", streams), verbose=False)
    (tmp_path / "galactic.spc").write_bytes(b"\x00\x4b" + bytes(600))   # a Galactic-style .spc
    with pytest.raises(ValueError, match="Galactic"):
        stk.load(tmp_path / "galactic.spc", verbose=False)


def test_old_excel_files_still_load_as_spreadsheets():
    """.xls files use the same container: they must still go to the spreadsheet reader."""
    c = stk.load(Path(__file__).parent / "fixtures" / "23_old_excel.xls", verbose=False)
    assert c.meta["file_type"] == "spreadsheet"


real = pytest.mark.skipif(not DATA.is_dir(), reason="data/ folder not present")


@real
def test_real_gold_nanoparticles():
    """Gold nanoparticles in water: the surface plasmon band at 520 nm (UVProbe 2.70, UV-2450, 0.5 nm steps)."""
    f = DATA / "AuNP6_400ul_water_2.6ml.spc"
    if not f.exists():
        pytest.skip("AuNP6_400ul_water_2.6ml.spc not in data/")
    s = stk.load(f, verbose=False)
    assert len(s) == 1421 and s.x[0] == 190 and s.x[-1] == 900 and s.y_unit == "Absorbance"
    visible = (s.x > 400) & (s.x < 800)
    assert s.x[visible][np.argmax(s.y[visible])] == pytest.approx(520, abs=2)   # tolerance: 2 nm
