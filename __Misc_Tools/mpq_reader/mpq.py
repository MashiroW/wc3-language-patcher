"""Minimal pure-Python MPQ reader (format v0/v1, as used by Warcraft III 1.27).

Supports: header search, encrypted hash/block tables, encrypted files
(incl. FIX_KEY), single-unit and sectored files, zlib, bzip2, PKWARE DCL
implode, Huffman and IMA ADPCM (mono/stereo) compression.

No native dependency: it is meant to let the patcher read the player's
war3.mpq / War3x.mpq / War3xlocal.mpq / War3Patch.mpq directly, without
MPQ Editor.
"""
from __future__ import annotations

import bz2
import os
import struct
import zlib
from pathlib import Path

from .explode import explode
from .huffman import decompress_huffman
from .adpcm import decompress_adpcm

M32 = 0xFFFFFFFF

# ---------------------------------------------------------------- crypto ---
def _build_crypt_table():
    table = [0] * 0x500
    seed = 0x00100001
    for index1 in range(0x100):
        index2 = index1
        for _ in range(5):
            seed = (seed * 125 + 3) % 0x2AAAAB
            temp1 = (seed & 0xFFFF) << 16
            seed = (seed * 125 + 3) % 0x2AAAAB
            temp2 = seed & 0xFFFF
            table[index2] = temp1 | temp2
            index2 += 0x100
    return table


CRYPT = _build_crypt_table()
_CRYPT_400 = CRYPT[0x400:0x500]

HASH_OFFSET, HASH_A, HASH_B, HASH_KEY = 0, 1, 2, 3


def hash_string(name: str, hash_type: int) -> int:
    seed1, seed2 = 0x7FED7FED, 0xEEEEEEEE
    base = hash_type << 8
    for ch in name.upper().encode("latin-1", "replace"):
        seed1 = (CRYPT[base + ch] ^ (seed1 + seed2)) & M32
        seed2 = (ch + seed1 + seed2 + (seed2 << 5) + 3) & M32
    return seed1


def decrypt(data: bytes, key: int) -> bytes:
    n = len(data) // 4
    if n == 0:
        return data
    values = struct.unpack_from(f"<{n}I", data)
    out = [0] * n
    seed1, seed2 = key & M32, 0xEEEEEEEE
    c400 = _CRYPT_400
    for i, v in enumerate(values):
        seed2 = (seed2 + c400[seed1 & 0xFF]) & M32
        r = v ^ ((seed1 + seed2) & M32)
        out[i] = r
        seed1 = ((((~seed1) << 0x15) + 0x11111111) & M32) | (seed1 >> 0x0B)
        seed2 = (r + seed2 + (seed2 << 5) + 3) & M32
    return struct.pack(f"<{n}I", *out) + data[n * 4:]


# ----------------------------------------------------------------- flags ---
FILE_IMPLODE = 0x00000100
FILE_COMPRESS = 0x00000200
FILE_ENCRYPTED = 0x00010000
FILE_FIX_KEY = 0x00020000
FILE_SINGLE_UNIT = 0x01000000
FILE_DELETE_MARKER = 0x02000000
FILE_SECTOR_CRC = 0x04000000
FILE_EXISTS = 0x80000000

COMP_HUFFMAN = 0x01
COMP_ZLIB = 0x02
COMP_PKWARE = 0x08
COMP_BZIP2 = 0x10
COMP_SPARSE = 0x20
COMP_ADPCM_MONO = 0x40
COMP_ADPCM_STEREO = 0x80
COMP_LZMA = 0x12


class MPQError(Exception):
    pass


def _decompress(data: bytes, expected: int) -> bytes:
    mask = data[0]
    data = data[1:]
    if mask == COMP_LZMA:
        raise MPQError("LZMA compression is not supported")
    if mask & COMP_BZIP2:
        data = bz2.decompress(data)
    if mask & COMP_PKWARE:
        data = explode(data, expected)
    if mask & COMP_ZLIB:
        data = zlib.decompress(data)
    if mask & COMP_HUFFMAN:
        data = decompress_huffman(data)
    if mask & COMP_ADPCM_STEREO:
        data = decompress_adpcm(data, 2, expected)
    elif mask & COMP_ADPCM_MONO:
        data = decompress_adpcm(data, 1, expected)
    unknown = mask & ~(COMP_BZIP2 | COMP_PKWARE | COMP_ZLIB | COMP_HUFFMAN |
                       COMP_ADPCM_MONO | COMP_ADPCM_STEREO)
    if unknown:
        raise MPQError(f"Unsupported compression mask 0x{mask:02X}")
    return data


class MPQArchive:
    def __init__(self, path):
        self.path = Path(path)
        self.f = open(self.path, "rb")
        self._read_header()
        self._read_tables()
        self._listfile = None

    def close(self):
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ------------------------------------------------------------ header ---
    def _read_header(self):
        size = os.fstat(self.f.fileno()).st_size
        offset = 0
        while offset < size:
            self.f.seek(offset)
            magic = self.f.read(4)
            if magic == b"MPQ\x1a":
                break
            if magic == b"MPQ\x1b":  # user data header
                self.f.seek(offset + 8)
                (hdr_off,) = struct.unpack("<I", self.f.read(4))
                offset += hdr_off
                continue
            offset += 0x200
        else:
            raise MPQError(f"Not an MPQ archive: {self.path}")
        self.archive_offset = offset
        self.f.seek(offset)
        hdr = self.f.read(32)
        (_, header_size, archive_size, format_version, sector_shift,
         hash_pos, block_pos, hash_count, block_count) = struct.unpack("<4sIIHHIIII", hdr)
        self.format_version = format_version
        self.sector_size = 512 << sector_shift
        self.hash_pos, self.block_pos = hash_pos, block_pos
        self.hash_count, self.block_count = hash_count, block_count
        self.hash_pos_hi = self.block_pos_hi = 0
        self.hi_block_pos = 0
        if format_version >= 1 and header_size >= 44:
            ext = self.f.read(12)
            self.hi_block_pos, self.hash_pos_hi, self.block_pos_hi = struct.unpack("<QHH", ext)

    def _read_table(self, pos, count, key):
        self.f.seek(self.archive_offset + pos)
        raw = self.f.read(count * 16)
        raw = raw.ljust(count * 16, b"\0")
        return decrypt(raw, key)

    def _read_tables(self):
        hpos = self.hash_pos | (self.hash_pos_hi << 32)
        bpos = self.block_pos | (self.block_pos_hi << 32)
        h = self._read_table(hpos, self.hash_count, hash_string("(hash table)", HASH_KEY))
        b = self._read_table(bpos, self.block_count, hash_string("(block table)", HASH_KEY))
        self.hash_table = [struct.unpack_from("<IIHHI", h, i * 16) for i in range(self.hash_count)]
        self.block_table = [list(struct.unpack_from("<IIII", b, i * 16)) for i in range(self.block_count)]
        hi = None
        if self.hi_block_pos:
            self.f.seek(self.archive_offset + self.hi_block_pos)
            hi = struct.unpack(f"<{self.block_count}H", self.f.read(self.block_count * 2))
        for i, entry in enumerate(self.block_table):
            entry.append(hi[i] if hi else 0)

    # ------------------------------------------------------------ lookup ---
    def _find_block(self, name: str):
        if not self.hash_count:
            return None
        start = hash_string(name, HASH_OFFSET) % self.hash_count
        ha, hb = hash_string(name, HASH_A), hash_string(name, HASH_B)
        i = start
        best = None
        while True:
            e_a, e_b, locale, _platform, block = self.hash_table[i]
            if block == 0xFFFFFFFF:
                break
            if e_a == ha and e_b == hb and block < self.block_count:
                # prefer neutral locale, but accept any
                if best is None or locale == 0:
                    best = block
                    if locale == 0:
                        break
            i = (i + 1) % self.hash_count
            if i == start:
                break
        return best

    def has_file(self, name: str) -> bool:
        b = self._find_block(name)
        return b is not None and bool(self.block_table[b][3] & FILE_EXISTS)

    # -------------------------------------------------------------- read ---
    def read_file(self, name: str) -> bytes | None:
        b = self._find_block(name)
        if b is None:
            return None
        offset, csize, fsize, flags, hi = self.block_table[b]
        if not flags & FILE_EXISTS or flags & FILE_DELETE_MARKER:
            return None
        if fsize == 0:
            return b""
        pos = self.archive_offset + offset + (hi << 32)
        key = 0
        if flags & FILE_ENCRYPTED:
            key = hash_string(name.replace("/", "\\").split("\\")[-1], HASH_KEY)
            if flags & FILE_FIX_KEY:
                key = ((key + offset) ^ fsize) & M32

        self.f.seek(pos)
        if flags & FILE_SINGLE_UNIT:
            data = self.f.read(csize)
            if flags & FILE_ENCRYPTED:
                data = decrypt(data, key)
            if csize < fsize:
                data = _decompress(data, fsize) if flags & FILE_COMPRESS else explode(data, fsize)
            return data[:fsize]

        compressed = bool(flags & (FILE_COMPRESS | FILE_IMPLODE))
        nsectors = (fsize + self.sector_size - 1) // self.sector_size
        if compressed:
            count = nsectors + 1 + (1 if flags & FILE_SECTOR_CRC else 0)
            table = self.f.read(count * 4)
            if flags & FILE_ENCRYPTED:
                table = decrypt(table, (key - 1) & M32)
            offsets = struct.unpack(f"<{count}I", table)
        else:
            offsets = [i * self.sector_size for i in range(nsectors)] + [csize]

        self.f.seek(pos)
        blob = self.f.read(offsets[nsectors] if compressed else csize)
        out = []
        remaining = fsize
        for i in range(nsectors):
            sector = blob[offsets[i]:offsets[i + 1]]
            expected = min(self.sector_size, remaining)
            if flags & FILE_ENCRYPTED:
                sector = decrypt(sector, (key + i) & M32)
            if compressed and len(sector) < expected:
                if flags & FILE_COMPRESS:
                    sector = _decompress(sector, expected)
                else:
                    sector = explode(sector, expected)
            out.append(sector[:expected])
            remaining -= expected
        return b"".join(out)

    # ---------------------------------------------------------- listfile ---
    def listfile(self) -> list[str]:
        if self._listfile is None:
            names = []
            try:
                data = self.read_file("(listfile)")
            except Exception:
                data = None
            if data:
                for line in data.decode("latin-1").replace(";", "\n").splitlines():
                    line = line.strip()
                    if line:
                        names.append(line)
            self._listfile = names
        return self._listfile


def extract_archive(mpq_path, out_dir, extra_names=(), progress=None, skip_errors=True):
    """Extract every known file of an archive to out_dir.

    Names come from the archive's (listfile) plus extra_names (useful for
    War3Patch.mpq which ships without a listfile). Returns (ok, failed, names).
    """
    out_dir = Path(out_dir)
    ok, failed = 0, []
    with MPQArchive(mpq_path) as a:
        names = list(dict.fromkeys(list(a.listfile()) + list(extra_names)))
        names = [n for n in names if not n.startswith("(")]
        present = [n for n in names if a.has_file(n)]
        total = len(present)
        for i, name in enumerate(present):
            try:
                data = a.read_file(name)
            except Exception as e:
                failed.append((name, str(e)))
                if not skip_errors:
                    raise
                continue
            if data is None:
                continue
            target = out_dir.joinpath(*name.replace("\\", "/").split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "wb") as f:
                f.write(data)
            ok += 1
            if progress and (i % 100 == 0 or i == total - 1):
                progress(i + 1, total)
    return ok, failed, present
