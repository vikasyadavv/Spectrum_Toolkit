"""Read Shimadzu UVProbe .spc files (UV-Vis spectra).

UVProbe saves a .spc file as a Microsoft compound file (see ``cfb.py``):
folders and streams inside one file. Not to be confused with Galactic
(GRAMS) .spc files, a different format with the same extension.

Each spectrum is a "data set"::

    /DataStorage1/DataSetGroup/DataSet1/
        DataSpectrumStorage/Data/X Data.1    x values, 8-byte numbers (wavelength in nm)
        DataSpectrumStorage/Data/Y Data.1    y values, 8-byte numbers (absorbance, %T, ...)
        MethodStorage/PageTexts0 ... 4       the method, as pages of "name: value" pairs
                                             (wavelength range, scan speed, slit width,
                                             measuring mode, ...)
        DataSetHeaderInfo                    data set name, software and instrument

The y unit comes from the method's "Measuring Mode" (e.g. Absorbance);
the x axis is the wavelength in nm, as UVProbe always stores it. Written
from the file layout (no Shimadzu software or extra package needed);
checked against UVProbe 2.70 files from a UV-2450.

>>> import spectrum_toolkit as stk                      # doctest: +SKIP
>>> s = stk.load("data/AuNP6_400ul_water_2.6ml.spc")    # doctest: +SKIP
Loaded AuNP6_400ul_water_2.6ml.spc: 1 spectrum, 1421 points, x 190 to 900
  - Shimadzu UVProbe 2.70 file: 1 spectrum of 1421 points, UV-2400PC Series, Absorbance.
  ...
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

from ..core import Spectrum, SpectrumCollection
from .cfb import CompoundFile

# Where each data set keeps its numbers, below its own folder.
_X, _Y = "DataSpectrumStorage/Data/X Data.1", "DataSpectrumStorage/Data/Y Data.1"


def is_shimadzu(cfb: CompoundFile) -> bool:
    """True if a compound file holds UVProbe spectra (at least one X Data / Y Data pair)."""
    return any(p.endswith("/" + _X) for p in cfb.streams())


def _text(raw: bytes, at: int) -> tuple[str, int]:
    """One text as MFC programs store it: its length (1 byte; 0xFF means 2 more bytes follow), then the
    letters. Returns the text and where the next value starts."""
    n = raw[at]
    at += 1
    if n == 0xFF:                                                # long text: the length is in the next 2 bytes
        n = struct.unpack_from("<H", raw, at)[0]
        at += 2
    if at + n > len(raw):
        raise ValueError("text runs past the end of its stream")
    return raw[at:at + n].decode("cp1252", "replace"), at + n


def _method_page(raw: bytes) -> tuple[str, dict[str, str]]:
    """One method page: two 4-byte numbers, the heading ("[Instrument Properties]"),
    the number of pairs (4 bytes), then each name ("Slit Width:") and value ("2.0 nm")."""
    heading, at = _text(raw, 8)
    count = struct.unpack_from("<I", raw, at)[0]
    at += 4
    pairs = {}
    for _ in range(count):
        key, at = _text(raw, at)
        value, at = _text(raw, at)
        pairs[key.rstrip(":").strip()] = value.strip()
    return heading.strip("[] "), pairs


def _header_texts(raw: bytes) -> list[str]:
    """The readable texts of DataSetHeaderInfo, in order (data set name, user, software, version,
    instrument, ...). Only texts of 2 or more printable letters are kept; their meaning is not stated
    in the file, so they are kept as found."""
    found, at = [], 0
    while at < len(raw):
        n = raw[at]
        piece = raw[at + 1:at + 1 + n]
        if n >= 2 and len(piece) == n and all(32 <= c < 127 for c in piece):
            found.append(piece.decode("ascii"))
            at += 1 + n
        else:
            at += 1
    return found


def read_spc_shimadzu(path: str | Path, cfb: CompoundFile | None = None) -> Spectrum | SpectrumCollection | list:
    """Read a Shimadzu UVProbe .spc file.

    One data set gives a Spectrum named after the file. Several data sets on
    the same x give a SpectrumCollection (named after each data set); on
    different x, a list of Spectrum, as for text files of x/y pairs.
    x always comes back rising (UVProbe stores it from high to low).

    ``meta`` keeps ``instrument`` (e.g. "UV-2400PC Series"), ``software``
    ("Shimadzu UVProbe 2.70"), ``measuring_mode`` (Absorbance, ...),
    ``method`` (every page of the method: {"Measurement Properties":
    {"Scan Speed": "Fast", ...}, ...}) and ``header_texts`` (the texts of the
    data set header, as found). ``load_notes`` says what was read.

    Parameters
    ----------
    path : the .spc file.
    cfb : the file already opened as a compound file (load opens it to
        recognise the format); opened here when not given.
    """
    path = Path(path)
    cfb = cfb or CompoundFile(path.read_bytes(), path.name)
    sets = sorted(p[:-len(_X)] for p in cfb.streams() if p.endswith("/" + _X))   # each data set's folder
    if not sets:
        raise ValueError(f"{path.name} is a compound file without UVProbe spectra (no 'X Data' stream); "
                         "if it is an old Excel file, give it the .xls extension.")
    spectra = []
    for folder in sets:
        try:
            x = np.frombuffer(cfb.read(folder + _X), "<f8").astype(float)
            y = np.frombuffer(cfb.read(folder + _Y), "<f8").astype(float)
        except KeyError:
            raise ValueError(f"{path.name}: data set {folder} has x values but no y values; "
                             "the file may be damaged.") from None
        if x.size != y.size or x.size == 0:
            raise ValueError(f"{path.name}: data set {folder} has {x.size} x values and {y.size} y values; "
                             "the file may be damaged.")
        # The method pages ("[Measurement Properties]", "[Instrument Properties]", ...).
        method = {}
        for p in cfb.streams():
            if p.startswith(folder + "MethodStorage/PageTexts"):
                try:
                    heading, pairs = _method_page(cfb.read(p))
                    method[heading] = pairs
                except (ValueError, struct.error, IndexError):   # an unreadable page: keep the others
                    continue
        info = folder + "DataSetHeaderInfo"
        texts = _header_texts(cfb.read(info)) if info in cfb.entries else []
        spectra.append((folder, x, y, method, texts))

    # What the method says (the same keys in every UVProbe file we have seen).
    folder, x, y, method, texts = spectra[0]
    instrument = method.get("Instrument Properties", {}).get("Instrument Type", "")
    mode = method.get("Instrument Properties", {}).get("Measuring Mode", "")
    version = texts[texts.index("UVProbe") + 1] if "UVProbe" in texts[:-1] else ""
    software = f"Shimadzu UVProbe {version}".strip()
    notes = [f"{software} file: {len(spectra)} spectr{'um' if len(spectra) == 1 else 'a'} of {x.size} points"
             + (f", {instrument}" if instrument else "") + (f", {mode}" if mode else "") + "."]
    if not mode:
        notes.append("The method does not say what y is (no Measuring Mode); y has no unit.")
    meta = {"instrument": instrument, "software": software, "measuring_mode": mode, "method": method,
            "header_texts": texts}

    # UVProbe stores x from high to low; turn each spectrum round so x rises as everywhere else.
    rising = []
    for folder, x, y, _m, t in spectra:
        if x.size > 1 and x[0] > x[-1]:
            x, y = x[::-1].copy(), y[::-1].copy()
        rising.append((folder, x, y, t))
    if spectra[0][1].size > 1 and spectra[0][1][0] > spectra[0][1][-1]:
        notes.append("x was stored from high to low; reversed so it rises.")
    meta["load_notes"] = notes
    x_unit, y_unit = "Wavelength (nm)", mode

    if len(rising) == 1:
        _folder, x, y, _t = rising[0]
        return Spectrum(x, y, name=path.stem, x_unit=x_unit, y_unit=y_unit, meta=meta)
    # Several data sets: named after each one (its first header text), e.g. "RawData".
    names = [t[0] if t else folder.strip("/").split("/")[-1] for folder, _x, _y, t in rising]
    if all(r[1].size == rising[0][1].size and np.array_equal(r[1], rising[0][1]) for r in rising):
        return SpectrumCollection(rising[0][1], np.vstack([r[2] for r in rising]), names=names,
                                  x_unit=x_unit, y_unit=y_unit, meta=meta)
    meta["load_notes"] = notes + ["The data sets have different x values, so they come back as separate spectra."]
    return [Spectrum(x, y, name=n, x_unit=x_unit, y_unit=y_unit, meta=dict(meta)) for n, (_f, x, y, _t)
            in zip(names, rising)]


__all__ = ["read_spc_shimadzu", "is_shimadzu"]
