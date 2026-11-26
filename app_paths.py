"""Path helpers that work both from source and from a PyInstaller build.

- resource_dir(): read-only files shipped with the program (templates,
  translation caches, _HomeMade_Data, 3D models, music...). In a frozen build
  this is PyInstaller's extraction folder (sys._MEIPASS).
- workspace_dir(): writable folder where the user's data lives
  (MPQ_Data, CASC_Data, merged). Next to the .exe when frozen, the project
  root when run from source.
"""
import os
import sys
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parent


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> Path:
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return _SOURCE_ROOT


def resource_path(*parts) -> Path:
    return resource_dir().joinpath(*parts)


def _is_writable(folder: Path) -> bool:
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe = folder / ".write_test"
        probe.write_text("ok")
        probe.unlink()
        return True
    except OSError:
        return False


def workspace_dir() -> Path:
    override = os.environ.get("WC3_PATCHER_WORKSPACE")
    if override:
        return Path(override).resolve()
    if is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        if _is_writable(exe_dir):
            return exe_dir
        # e.g. installed under Program Files: use Documents instead
        fallback = Path.home() / "Documents" / "WC3 Language Patcher"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
    return _SOURCE_ROOT
