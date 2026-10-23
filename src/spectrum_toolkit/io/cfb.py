"""Open Microsoft compound files (also called OLE2 or CFB files) and read the streams inside.

A compound file is a small file system inside one file: "storages" (folders)
hold "streams" (files). Old Excel files (.xls) use it, and so does Shimadzu's
UVProbe for its .spc spectra. This module only reads.

How it is laid out (Microsoft's [MS-CFB] specification):

- a 512-byte header, then the file cut into equal "sectors" (512 bytes in
  version 3 files, 4096 in version 4);
- the FAT (file allocation table): for each sector, the number of the next
  sector of the same stream, so a stream is a chain of sectors;
- the directory: 128-byte entries (name, kind, where the stream starts, its
  size, and the entries left, right and below it in a tree);
- streams smaller than 4096 bytes sit in 64-byte "mini sectors" inside one
  big stream of the root entry, with their own table (the mini FAT).

>>> from spectrum_toolkit.io.cfb import CompoundFile    # doctest: +SKIP
>>> f = CompoundFile(open("data/L_cys_1mM_3ml_1.spc", "rb").read())  # doctest: +SKIP
>>> f.read("/DataStorage1/DataSetGroup/DataSet1/DataSpectrumStorage/Data/X Data.1")[:8]  # doctest: +SKIP
"""

from __future__ import annotations

import struct

# The first 8 bytes of every compound file.
CFB_MAGIC = bytes.fromhex("d0cf11e0a1b11ae1")
_FREE, _END = 0xFFFFFFFF, 0xFFFFFFFE                          # "no sector" and "end of chain"
_STORAGE, _STREAM, _ROOT = 1, 2, 5                             # kinds of directory entries


def is_cfb(head: bytes) -> bool:
    """True if the first bytes of a file say it is a compound file."""
    return head.startswith(CFB_MAGIC)


class CompoundFile:
    """The streams of a compound file, by path (e.g. "/Version/CLSID").

    Parameters
    ----------
    raw : the whole file as bytes.
    name : the file name, for error messages.
    """

    def __init__(self, raw: bytes, name: str = "the file"):
        if not is_cfb(raw) or len(raw) < 512:
            raise ValueError(f"{name} is not a Microsoft compound file (OLE2).")
        self._raw, self._name = raw, name
        major = struct.unpack_from("<H", raw, 0x1A)[0]                  # format version: 3 or 4
        self._sector = 1 << struct.unpack_from("<H", raw, 0x1E)[0]      # sector size: 512 or 4096
        self._mini = 1 << struct.unpack_from("<H", raw, 0x20)[0]        # mini sector size: 64
        n_fat, dir_start = struct.unpack_from("<II", raw, 0x2C)
        self._cutoff, mini_fat_start, _, difat_start, n_difat = struct.unpack_from("<IIIII", raw, 0x38)

        # The FAT's own sectors are listed in the header (first 109), then in extra "DIFAT" sectors.
        fat_sectors = list(struct.unpack_from("<109I", raw, 0x4C))
        per_sector = self._sector // 4                                   # sector numbers per sector
        s, seen = difat_start, set()
        while s not in (_FREE, _END) and n_difat > 0 and s not in seen:
            seen.add(s)
            values = struct.unpack(f"<{per_sector}I", self._sector_bytes(s))
            fat_sectors += values[:-1]                                   # the last number points to the next DIFAT sector
            s, n_difat = values[-1], n_difat - 1
        self._fat: list[int] = []
        for n in fat_sectors[:n_fat]:
            self._fat += struct.unpack(f"<{per_sector}I", self._sector_bytes(n))

        # The directory: one 128-byte entry per storage or stream.
        directory = self._chain_bytes(dir_start, self._fat, self._sector, self._sector_bytes)
        entries = []
        for k in range(len(directory) // 128):
            e = directory[k * 128:(k + 1) * 128]
            name_length = struct.unpack_from("<H", e, 64)[0]            # in bytes, with the closing zero
            entries.append({
                "name": e[:max(min(name_length, 64) - 2, 0)].decode("utf-16-le", "replace"),
                "kind": e[66],
                "left": struct.unpack_from("<I", e, 68)[0], "right": struct.unpack_from("<I", e, 72)[0],
                "child": struct.unpack_from("<I", e, 76)[0], "start": struct.unpack_from("<I", e, 116)[0],
                # version 3 files keep only the lower 4 bytes of the size
                "size": struct.unpack_from("<Q" if major == 4 else "<I", e, 120)[0],
            })
        if not entries or entries[0]["kind"] != _ROOT:
            raise ValueError(f"{name}: the compound file has no root entry; it may be damaged.")
        root = entries[0]
        # Small streams live in the root entry's stream, cut into mini sectors.
        self._mini_stream = self._chain_bytes(root["start"], self._fat, self._sector, self._sector_bytes)[:root["size"]]
        mini_fat_bytes = self._chain_bytes(mini_fat_start, self._fat, self._sector, self._sector_bytes)
        self._mini_fat = list(struct.unpack(f"<{len(mini_fat_bytes) // 4}I", mini_fat_bytes))

        # Paths of every entry, found by walking the directory tree.
        self.entries: dict[str, dict] = {}
        self._walk(entries, root["child"], "", set())

    # ---- sectors and chains ----------------------------------------------------
    def _sector_bytes(self, n: int) -> bytes:
        """The bytes of sector n (sector 0 starts one sector size into the file, after the header)."""
        start = (n + 1) * self._sector
        if start >= len(self._raw):                               # the last sector may be cut short, but must start
            raise ValueError(f"{self._name}: points to sector {n}, past the end of the file; it may be damaged.")
        return self._raw[start:start + self._sector]

    def _chain_bytes(self, start: int, table: list[int], size: int, get) -> bytes:
        """Follow a chain of sectors through a table (FAT or mini FAT) and join their bytes."""
        parts, n, seen = [], start, set()
        while n not in (_FREE, _END):
            if n in seen or n >= len(table):                     # a loop or a number outside the table
                raise ValueError(f"{self._name}: a broken sector chain; the file may be damaged.")
            seen.add(n)
            parts.append(get(n))
            n = table[n]
        return b"".join(parts)

    def _mini_bytes(self, n: int) -> bytes:
        """The bytes of mini sector n."""
        return self._mini_stream[n * self._mini:(n + 1) * self._mini]

    def _walk(self, entries: list[dict], i: int, folder: str, seen: set) -> None:
        """Add entry i, its left and right neighbours, and (for storages) everything below it."""
        if i in (_FREE, _END) or i >= len(entries) or i in seen:
            return
        seen.add(i)
        e = entries[i]
        self._walk(entries, e["left"], folder, seen)
        self._walk(entries, e["right"], folder, seen)
        path = f"{folder}/{e['name']}"
        self.entries[path] = e
        if e["kind"] == _STORAGE:
            self._walk(entries, e["child"], path, seen)

    # ---- reading ---------------------------------------------------------------
    def streams(self) -> list[str]:
        """Paths of every stream, sorted."""
        return sorted(p for p, e in self.entries.items() if e["kind"] == _STREAM)

    def read(self, path: str) -> bytes:
        """The contents of one stream, by path."""
        e = self.entries.get(path)
        if e is None or e["kind"] != _STREAM:
            raise KeyError(path)
        if e["size"] < self._cutoff:                              # a small stream: in mini sectors
            data = self._chain_bytes(e["start"], self._mini_fat, self._mini, self._mini_bytes)
        else:
            data = self._chain_bytes(e["start"], self._fat, self._sector, self._sector_bytes)
        if len(data) < e["size"]:
            raise ValueError(f"{self._name}: stream {path} is shorter than its stated size; the file may be damaged.")
        return data[:e["size"]]


__all__ = ["CompoundFile", "is_cfb"]
