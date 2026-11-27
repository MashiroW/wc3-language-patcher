"""Short game version labels shown next to the Open MPQ / Open CASC buttons."""
from __future__ import annotations

import ctypes
import sys
from pathlib import Path

# files of a 1.2x install that carry the game version
_VERSIONED_FILES = ("game.dll", "Warcraft III.exe", "war3.exe", "Frozen Throne.exe")


def _file_version(path: Path) -> tuple[int, int, int, int] | None:
    if sys.platform != "win32" or not path.is_file():
        return None
    try:
        ver = ctypes.windll.version
        size = ver.GetFileVersionInfoSizeW(str(path), None)
        if not size:
            return None
        buf = ctypes.create_string_buffer(size)
        if not ver.GetFileVersionInfoW(str(path), 0, size, buf):
            return None
        ptr, length = ctypes.c_void_p(), ctypes.c_uint()
        if not ver.VerQueryValueW(buf, "\\", ctypes.byref(ptr), ctypes.byref(length)):
            return None
        # VS_FIXEDFILEINFO: signature, struct version, then FileVersionMS / LS
        ms, ls = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_uint32))[2:4]
        return ms >> 16, ms & 0xFFFF, ls >> 16, ls & 0xFFFF
    except Exception:
        return None


def mpq_install_version(folder) -> str:
    """'1.27b' for a 1.27.1 install, '' when unknown."""
    if not folder:
        return ""
    folder = Path(folder)
    for name in _VERSIONED_FILES:
        v = _file_version(folder / name)
        if v and v[0] == 1:
            # classic patches: 1.27.0 = 1.27a, 1.27.1 = 1.27b
            return f"{v[0]}.{v[1]}{chr(ord('a') + v[2])}" if v[2] < 26 else f"{v[0]}.{v[1]}"
    return ""


VERSION_FILE = "version.txt"


def mpq_source_version(folder) -> str:
    """Version of a 1.27 source: an install folder (read from game.dll), or an
    MPQ_Data/<lang>-MPQ folder (version.txt written when it was imported)."""
    if not folder:
        return ""
    version = mpq_install_version(folder)
    if version:
        return version
    try:
        return (Path(folder) / VERSION_FILE).read_text(encoding="utf-8").strip().splitlines()[0][:16]
    except (OSError, IndexError):
        return ""


def short_casc_version(version: str) -> str:
    """'1.31.1.12164' -> '1.31.1'."""
    parts = (version or "").strip().split(".")
    return ".".join(parts[:3]) if len(parts) >= 3 else (version or "").strip()
