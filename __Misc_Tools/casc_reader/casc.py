"""Minimal read-only CASC reader for local Warcraft III (1.30+) installs.

Supports local storage (Data/data/*.idx + data.###), the encoding file and
BLTE frames with 'N' (raw) and 'Z' (zlib) chunks, which is what Warcraft III
uses. Encrypted ('E') chunks are not supported.
"""
from __future__ import annotations

import os
import re
import struct
import zlib
from pathlib import Path


class CASCError(Exception):
    pass


def blte_decode(data: bytes) -> bytes:
    if data[:4] != b"BLTE":
        raise CASCError("not a BLTE stream")
    (header_size,) = struct.unpack(">I", data[4:8])
    chunks = []
    if header_size == 0:
        chunks.append(data[8:])
    else:
        count = int.from_bytes(data[9:12], "big")
        pos = 12
        infos = []
        for _ in range(count):
            csize, dsize = struct.unpack(">II", data[pos:pos + 8])
            infos.append((csize, dsize))
            pos += 24
        pos = header_size
        for csize, _ in infos:
            chunks.append(data[pos:pos + csize])
            pos += csize
    out = []
    for c in chunks:
        mode = c[:1]
        if mode == b"N":
            out.append(c[1:])
        elif mode == b"Z":
            out.append(zlib.decompress(c[1:]))
        elif mode == b"F":
            out.append(blte_decode(c[1:]))
        else:
            raise CASCError(f"unsupported BLTE chunk mode {mode!r}")
    return b"".join(out)


class CASCStorage:
    def __init__(self, game_dir):
        self.game_dir = Path(game_dir)
        self.data_dir = self.game_dir / "Data"
        self._read_build_info()
        self._read_indices()
        self._read_encoding()
        self.root = None

    # ------------------------------------------------------------ config ---
    def _read_build_info(self):
        lines = (self.game_dir / ".build.info").read_text(encoding="utf-8").splitlines()
        header = [h.split("!")[0] for h in lines[0].split("|")]
        rows = [dict(zip(header, l.split("|"))) for l in lines[1:] if l.strip()]
        row = next((r for r in rows if r.get("Active") == "1"), rows[0])
        self.version = row.get("Version", "")
        self.tags = row.get("Tags", "")
        key = row["Build Key"]
        cfg = self.data_dir / "config" / key[:2] / key[2:4] / key
        self.build_config = {}
        for line in cfg.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                self.build_config[k.strip()] = v.split()

    def _read_indices(self):
        latest = {}
        for p in (self.data_dir / "data").glob("*.idx"):
            m = re.match(r"([0-9a-f]{2})([0-9a-f]{8})\.idx$", p.name)
            if m:
                b, v = m.group(1), int(m.group(2), 16)
                if b not in latest or v > latest[b][0]:
                    latest[b] = (v, p)
        self.index = {}
        for _, p in latest.values():
            raw = p.read_bytes()
            (hh_size,) = struct.unpack_from("<I", raw, 0)
            size_bytes, offs_bytes, key_bytes, offset_bits = raw[12], raw[13], raw[14], raw[15]
            pos = (8 + hh_size + 0x0F) & ~0x0F
            (entries_size,) = struct.unpack_from("<I", raw, pos)
            pos += 8
            entry_len = key_bytes + offs_bytes + size_bytes
            mask = (1 << offset_bits) - 1
            for off in range(pos, pos + entries_size, entry_len):
                key = raw[off:off + key_bytes]
                loc = int.from_bytes(raw[off + key_bytes:off + key_bytes + offs_bytes], "big")
                size = int.from_bytes(raw[off + key_bytes + offs_bytes:off + entry_len], "little")
                self.index.setdefault(key, (loc >> offset_bits, loc & mask, size))
        self._key_len = key_bytes
        self._files = {}

    def read_ekey(self, ekey: bytes) -> bytes:
        entry = self.index.get(ekey[:self._key_len])
        if entry is None:
            raise CASCError(f"ekey {ekey.hex()} not in local storage")
        archive, offset, size = entry
        f = self._files.get(archive)
        if f is None:
            f = self._files[archive] = open(self.data_dir / "data" / f"data.{archive:03d}", "rb")
        f.seek(offset + 30)
        return blte_decode(f.read(size - 30))

    # ---------------------------------------------------------- encoding ---
    def _read_encoding(self):
        ekey = bytes.fromhex(self.build_config["encoding"][1])
        data = self.read_ekey(ekey)
        if data[:2] != b"EN":
            raise CASCError("bad encoding file")
        ckey_size, ekey_size = data[3], data[4]
        cpage_kb = struct.unpack(">H", data[5:7])[0]
        cpage_count = struct.unpack(">I", data[9:13])[0]
        espec_size = struct.unpack(">I", data[18:22])[0]
        pos = 22 + espec_size + cpage_count * 32
        self.ckey_to_ekey = {}
        page = cpage_kb * 1024
        for p in range(cpage_count):
            start = pos + p * page
            i = start
            while i < start + page:
                count = data[i]
                if count == 0:
                    break
                ckey = data[i + 6:i + 6 + ckey_size]
                ek = data[i + 6 + ckey_size:i + 6 + ckey_size + ekey_size]
                self.ckey_to_ekey[ckey] = ek
                i += 6 + ckey_size + ekey_size * count

    def read_ckey(self, ckey: bytes) -> bytes:
        ek = self.ckey_to_ekey.get(ckey)
        if ek is None:
            raise CASCError(f"ckey {ckey.hex()} not in encoding table")
        return self.read_ekey(ek)

    # -------------------------------------------------------------- root ---
    def root_entries(self) -> dict[str, bytes]:
        """Warcraft III's root file is text: 'path|ckeyhex|flags' lines."""
        if self.root is None:
            data = self.read_ckey(bytes.fromhex(self.build_config["root"][0]))
            self.root = {}
            for line in data.decode("utf-8", "replace").splitlines():
                parts = line.split("|")
                if len(parts) >= 2 and re.fullmatch(r"[0-9a-fA-F]{32}", parts[1]):
                    self.root[parts[0]] = bytes.fromhex(parts[1])
        return self.root

    def read_file(self, name: str) -> bytes:
        root = self.root_entries()
        ckey = root.get(name)
        if ckey is None:
            low = name.lower()
            ckey = next((v for k, v in root.items() if k.lower() == low), None)
        if ckey is None:
            raise CASCError(f"{name} not found")
        return self.read_ckey(ckey)

    def close(self):
        for f in self._files.values():
            f.close()


# ------------------------------------------------------------ extraction ---
LOCALE_PREFIX = "War3.w3mod:_Locales/{}.w3mod:"


def present_locales(storage: CASCStorage) -> dict:
    """locale code -> (files present locally, files listed in the root)."""
    stats = {}
    rx = re.compile(r"^War3\.w3mod:_Locales/([A-Za-z]{4})\.w3mod:", re.I)
    for name, ckey in storage.root_entries().items():
        m = rx.match(name)
        if not m:
            continue
        loc = m.group(1)
        present, total = stats.get(loc, (0, 0))
        stats[loc] = (present + (1 if storage.is_present(ckey) else 0), total + 1)
    return stats


def _is_present(self, ckey: bytes) -> bool:
    ek = self.ckey_to_ekey.get(ckey)
    return ek is not None and ek[:self._key_len] in self.index


CASCStorage.is_present = _is_present


def is_reforged_layout(storage: CASCStorage, locale: str) -> bool:
    """Reforged 2.0+ stores voices as .ogg (1.30-1.32: .mp3/.wav) and adds Strings/*.fdf."""
    prefix = LOCALE_PREFIX.format(locale).lower()
    return any(k.lower().startswith(prefix) and k.lower().endswith(".ogg") for k in storage.root_entries())


def extract_locale(game_dir, locale: str, out_dir, log=print, progress=None):
    """Extract War3.w3mod:_Locales/<locale>.w3mod:* into out_dir (CascView layout).

    Files listed in the root but not installed locally are skipped and counted.
    Returns (extracted, missing, failed list)."""
    storage = CASCStorage(game_dir)
    try:
        prefix = LOCALE_PREFIX.format(locale).lower()
        entries = [(n, c) for n, c in storage.root_entries().items() if n.lower().startswith(prefix)]
        if not entries:
            raise CASCError(f"locale {locale} not found in this install (version {storage.version})")
        if is_reforged_layout(storage, locale):
            log(f"  | ⚠️ Warcraft III {storage.version}: Reforged 2.0+ layout (voices in .ogg, "
                "Strings/*.fdf). Text files are compatible, but the sound files differ from 1.31.")
        out_dir = Path(out_dir)
        extracted, missing, failed = 0, 0, []
        total = len(entries)
        for i, (name, ckey) in enumerate(entries, 1):
            rel = name[len(prefix):].replace(":", "/")
            if not storage.is_present(ckey):
                missing += 1
            else:
                try:
                    data = storage.read_ckey(ckey)
                    target = out_dir.joinpath(*rel.split("/"))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    extracted += 1
                except Exception as e:
                    failed.append((rel, str(e)))
            if progress and (i % 100 == 0 or i == total):
                progress(i, total)
        return extracted, missing, failed
    finally:
        storage.close()
