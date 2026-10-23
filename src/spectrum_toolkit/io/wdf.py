"""Read Renishaw WiRE data files (.wdf): single spectra, series and maps.

A .wdf file is a row of blocks. Each block starts with a 16-byte header:
its name (4 letters, e.g. "DATA"), a number, and its size in bytes (the
header included), so the reader can step from one block to the next and
skip the ones it does not need. The blocks used here:

- ``WDF1``  the file header (512 bytes): points per spectrum, number of
            spectra, laser, times, title, the WiRE version.
- ``DATA``  every spectrum, one after the other, as 4-byte numbers.
- ``XLST``  the x axis (Raman shift, wavenumber or wavelength) and its unit.
- ``YLST``  the detector rows per spectrum (1 for ordinary spectra).
- ``ORGN``  one value per spectrum for each "origin": X, Y and Z position
            in a map, time of each spectrum, and a few others.
- ``WMAP``  the map grid: start, step and number of points along X, Y, Z.
- ``WHTL``  the white-light (camera) image of the sample, a JPEG picture.

The other blocks (``WXDA``, ``WXDM``, ``WXCS``, ``WXIS``, ``ZLDC``, ``BKXL``)
hold WiRE's own settings and are skipped. Written from the block layout
(no Renishaw software or extra package needed); checked against WiRE 5.6
files (silicon at 520.7 cm⁻¹, maps of 340 and 378 positions).

>>> import spectrum_toolkit as stk                      # doctest: +SKIP
>>> c = stk.load("data/pga-stem_map.wdf")               # doctest: +SKIP
Loaded pga-stem_map.wdf: 378 spectra, 1006 points each, x 565.16 to 1697.35
  - Renishaw WiRE 5.6.0.30846 file, map: 378 spectra of 1006 points, laser 632.8 nm, ...
  - Map of 21 x 18 positions (step 1 x 1 µm); positions (X, Y in µm) are in .positions.
  ...
"""

from __future__ import annotations

import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from ..core import Spectrum, SpectrumCollection

# Every .wdf file starts with these 4 bytes.
WDF_MAGIC = b"WDF1"
# Size of the header in front of every block: name (4), number (4), size (8).
_BLOCK_HEAD = 16

# Units, as numbered in WiRE files (the unit codes of XLST, ORGN and the header).
_UNITS = {0: "", 1: "Raman shift (cm⁻¹)", 2: "Wavenumber (cm⁻¹)", 3: "Wavelength (nm)", 4: "Energy (eV)",
          5: "µm", 6: "counts", 7: "electrons", 8: "mm", 9: "m", 10: "K", 11: "Pa", 12: "s", 13: "ms",
          14: "hours", 15: "days", 16: "pixels", 17: "intensity", 18: "relative intensity", 19: "degrees",
          20: "radians", 21: "°C", 22: "°F", 23: "K/min", 24: "date and time", 25: "µs"}
# What the origin values mean, as numbered in WiRE files (only the ones read here).
_SPATIAL = {3: "X", 4: "Y", 5: "Z"}                    # stage positions: become .positions
_WHOLE_NUMBERS = {11, 16, 17}                           # time (Windows FILETIME), checksum, flags: whole numbers
_TIME = 11
# How the spectra were measured (header field "measurement type").
_MEASUREMENTS = {0: "unspecified", 1: "single", 2: "series", 3: "map"}
# How the detector was used (header field "scan type").
_SCANS = {0: "unspecified", 1: "static", 2: "continuous (extended)", 3: "step and repeat", 4: "filter scan",
          5: "filter image", 6: "StreamLine", 7: "StreamLine HR", 8: "point detector"}


def is_wdf(head: bytes) -> bool:
    """True if the first bytes of a file say it is a WiRE .wdf file."""
    return head.startswith(WDF_MAGIC)


def _filetime(value: int) -> datetime | None:
    """Windows time (100-nanosecond steps since 1 January 1601) to a date and time in UTC."""
    if not value:
        return None
    try:
        return datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=value // 10)
    except OverflowError:                                        # not a real time: leave it out
        return None


def _text(raw: bytes, start: int, length: int) -> str:
    """A fixed-length text field: up to the first zero byte, as UTF-8."""
    return raw[start:start + length].split(b"\0")[0].decode("utf-8", "replace").strip()


def _blocks(raw: bytes, name: str) -> dict[str, tuple[int, int]]:
    """Where each block starts and how big it is: {"DATA": (start, size), ...} (first of each name)."""
    found: dict[str, tuple[int, int]] = {}
    pos = 0
    while pos + _BLOCK_HEAD <= len(raw):
        tag, _number, size = struct.unpack_from("<4sIQ", raw, pos)
        if size < _BLOCK_HEAD or pos + size > len(raw):          # a block cannot be smaller than its header
            raise ValueError(f"{name} is damaged or incomplete: block {tag.decode('latin-1')!r} at byte {pos} "
                             f"says it is {size} bytes long, but the file ends at byte {len(raw)}.")
        found.setdefault(tag.decode("latin-1"), (pos, size))
        pos += size
    return found


def _axis(raw: bytes, block: tuple[int, int], length: int) -> tuple[np.ndarray, int]:
    """An XLST or YLST block: (values, unit code). After the block header come type and unit (4 bytes each)."""
    start, size = block
    _kind, unit = struct.unpack_from("<II", raw, start + _BLOCK_HEAD)
    n = min(length, (size - _BLOCK_HEAD - 8) // 4)               # never read past the block
    return np.frombuffer(raw, "<f4", n, start + _BLOCK_HEAD + 8).astype(float), unit


def _origins(raw: bytes, block: tuple[int, int], count: int) -> list[dict]:
    """The ORGN block: one entry per origin with its name, meaning, unit and one value per spectrum.

    Layout: the number of origins (4 bytes), then for each origin its type
    (4 bytes; the top bit marks the "primary" origins, e.g. X and Y of a
    map), unit (4), name (16 bytes of text), and 8 bytes per spectrum.
    The block has room for every planned spectrum, so the step from one
    origin to the next is worked out from the block size.
    """
    start, size = block
    n = struct.unpack_from("<I", raw, start + _BLOCK_HEAD)[0]
    if n == 0:
        return []
    stride = (size - _BLOCK_HEAD - 4) // n                       # bytes per origin: 24 + 8 per planned spectrum
    found = []
    for k in range(n):
        at = start + _BLOCK_HEAD + 4 + k * stride
        kind, unit = struct.unpack_from("<II", raw, at)
        meaning = kind & 0x7FFFFFFF                              # without the "primary" bit
        dtype = "<u8" if meaning in _WHOLE_NUMBERS else "<f8"    # times, flags, checksums are whole numbers
        values = np.frombuffer(raw, dtype, min(count, (stride - 24) // 8), at + 24)
        found.append({"name": _text(raw, at + 8, 16), "type": meaning, "primary": bool(kind & 0x80000000),
                      "unit": _UNITS.get(unit, f"unit {unit}"), "values": values})
    return found


def read_wdf(path: str | Path) -> Spectrum | SpectrumCollection:
    """Read a Renishaw WiRE .wdf file.

    One spectrum gives a Spectrum named after the file; several (a series or
    a map) give a SpectrumCollection, with the stage positions of a map in
    ``.positions`` (one row per spectrum: X, Y and Z if measured, in µm).
    x always comes back rising (WiRE stores it falling).

    What the file says about the measurement is kept in ``meta``:
    ``instrument`` (WiRE version), ``title``, ``measurement`` (single,
    series or map), ``scan`` (static, continuous, ...), ``laser_nm``,
    ``accumulations``, ``start`` and ``end`` (UTC), ``operator``,
    ``position_labels`` (e.g. ["X (µm)", "Y (µm)"]), ``map`` (start, step and
    number of points of the grid), ``origins`` (every per-spectrum value,
    e.g. the time of each spectrum) and ``white_light`` (the camera image
    as JPEG bytes, when the file has one). ``load_notes`` says what was read.

    Parameters
    ----------
    path : the .wdf file.
    """
    path = Path(path)
    raw = path.read_bytes()
    name = path.name
    if not is_wdf(raw):
        raise ValueError(f"{name} does not start like a Renishaw WiRE file (the first 4 bytes should be WDF1). "
                         "It may be damaged, or another format with the same extension.")
    if len(raw) < 512:
        raise ValueError(f"{name} is too short to be a WiRE file ({len(raw)} bytes; the header alone is 512).")

    # ---- the file header (fixed places in the first 512 bytes) ------------
    u32 = lambda at: struct.unpack_from("<I", raw, at)[0]       # one 4-byte whole number
    u64 = lambda at: struct.unpack_from("<Q", raw, at)[0]       # one 8-byte whole number
    points = u32(0x3C)                                           # values in each spectrum
    count = u64(0x48)                                            # spectra measured (may be fewer than planned)
    accumulations = u32(0x50)
    y_rows = u32(0x54)                                           # detector rows per spectrum (1 = a spectrum)
    x_length = u32(0x58)
    version = ".".join(str(v) for v in struct.unpack_from("<4H", raw, 0x78))
    measurement = _MEASUREMENTS.get(u32(0x84), f"type {u32(0x84)}")
    scan = _SCANS.get(u32(0x80), f"type {u32(0x80)}")
    start, end = _filetime(u64(0x88)), _filetime(u64(0x90))
    y_unit = _UNITS.get(u32(0x98), "")
    laser_wavenumber = struct.unpack_from("<f", raw, 0x9C)[0]   # the laser line in cm⁻¹ (15802.8 = 632.8 nm)
    laser_nm = round(1e7 / laser_wavenumber, 3) if laser_wavenumber > 0 else None
    application = _text(raw, 0x60, 24) or "WiRE"

    # ---- the blocks ----------------------------------------------------------
    blocks = _blocks(raw, name)
    for needed in ("DATA", "XLST"):
        if needed not in blocks:
            raise ValueError(f"{name} has no {needed} block, so it holds no spectra to read "
                             f"(blocks found: {', '.join(blocks)}).")
    if count == 0:
        raise ValueError(f"{name} holds no spectra: the measurement was stopped before the first one finished.")
    if y_rows > 1:
        raise ValueError(f"{name} holds detector images ({y_rows} rows per measurement), not spectra; "
                         "such files are not supported yet. In WiRE, save the spectra as a normal .wdf or as text.")
    x, x_unit_code = _axis(raw, blocks["XLST"], x_length)
    if x.size != points:
        raise ValueError(f"{name}: the x axis has {x.size} values but each spectrum has {points}; "
                         "the file may be damaged.")
    data_start, data_size = blocks["DATA"]
    available = (data_size - _BLOCK_HEAD) // (4 * points)        # whole spectra stored in the DATA block
    if available < count:
        raise ValueError(f"{name}: the header says {count} spectra but the data block holds only {available}; "
                         "the file may be damaged or still being written.")
    Y = np.frombuffer(raw, "<f4", count * points, data_start + _BLOCK_HEAD).astype(float).reshape(count, points)
    if not np.all(np.isfinite(x)):
        raise ValueError(f"{name}: the x axis has missing values; the file may be damaged.")

    notes = [f"Renishaw {application} {version} file, {measurement}: {count} spectr{'um' if count == 1 else 'a'} "
             f"of {points} points" + (f", laser {laser_nm:g} nm" if laser_nm else "")
             + f", {accumulations} accumulation(s)."]
    # WiRE stores x from high to low; turn both x and the spectra round, so x rises as everywhere else.
    if x.size > 1 and x[0] > x[-1]:
        x, Y = x[::-1].copy(), Y[:, ::-1].copy()
        notes.append("x was stored from high to low; reversed so it rises.")

    # ---- per-spectrum values: positions, times, ... --------------------------
    origins = _origins(raw, blocks["ORGN"], count) if "ORGN" in blocks else []
    spatial = [o for o in origins if o["type"] in _SPATIAL and o["values"].size == count]
    positions = np.column_stack([o["values"] for o in spatial]) if spatial else None
    labels = [f"{o['name'] or _SPATIAL[o['type']]} ({o['unit']})" for o in spatial]
    kept = {}
    for o in origins:
        if o["type"] == _TIME:                                   # times as text, e.g. "2023-11-22T06:36:44Z"
            kept[o["name"] or "Time"] = [t.isoformat(timespec="seconds").replace("+00:00", "Z") if t else None
                                         for t in (_filetime(int(v)) for v in o["values"])]
        else:
            kept[o["name"] or f"type {o['type']}"] = o["values"].tolist()

    # ---- the map grid ---------------------------------------------------------
    grid = None
    if "WMAP" in blocks:
        at = blocks["WMAP"][0] + _BLOCK_HEAD
        flags = u32(at)
        grid = {"start": [round(v, 4) for v in struct.unpack_from("<3f", raw, at + 8)],
                "step": [round(v, 4) for v in struct.unpack_from("<3f", raw, at + 20)],
                "points": list(struct.unpack_from("<3I", raw, at + 32)),   # along X, Y, Z
                "flags": flags}
        nx, ny, nz = grid["points"]
        sx, sy, _ = grid["step"]
        shape = f"{nx} x {ny}" + (f" x {nz}" if nz > 1 else "")
        notes.append(f"Map of {shape} positions (step {sx:g} x {sy:g} µm); positions "
                     f"({', '.join(o['name'] for o in spatial)} in µm) are in .positions.")
        if nx * ny * max(nz, 1) != count:
            notes.append(f"The grid has room for {nx * ny * max(nz, 1)} spectra but {count} were measured "
                         "(the map was stopped early, or it is not a full rectangle).")
    elif positions is not None:
        notes.append(f"Each spectrum has a stage position ({', '.join(labels)}), kept in .positions.")

    white_light = None
    if "WHTL" in blocks:
        at, size = blocks["WHTL"]
        white_light = raw[at + _BLOCK_HEAD:at + size]            # a JPEG picture, as stored
        notes.append("Has a white-light image of the sample (meta['white_light'], JPEG).")

    meta = {"instrument": f"Renishaw {application} {version}", "title": _text(raw, 0xF0, 160),
            "measurement": measurement, "scan": scan, "laser_nm": laser_nm, "accumulations": accumulations,
            "start": start.isoformat(timespec="seconds").replace("+00:00", "Z") if start else None,
            "end": end.isoformat(timespec="seconds").replace("+00:00", "Z") if end else None,
            "operator": _text(raw, 0xD0, 32), "position_labels": labels, "map": grid, "origins": kept,
            "white_light": white_light, "load_notes": notes}
    x_unit = _UNITS.get(x_unit_code, "")
    if count == 1:
        return Spectrum(x, Y[0], name=path.stem, x_unit=x_unit, y_unit=y_unit, meta=meta)
    return SpectrumCollection(x, Y, names=[f"Spectrum {k + 1}" for k in range(count)], x_unit=x_unit,
                              y_unit=y_unit, positions=positions, meta=meta)


__all__ = ["read_wdf", "is_wdf"]
