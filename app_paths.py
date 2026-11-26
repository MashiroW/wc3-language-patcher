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


# The user's folders, each with a placeholder.txt explaining what goes inside
# (so they exist and are easy to find, even before the first build).
WORKSPACE_FOLDERS = {
    "MPQ_Data": (
        "MPQ_Data - Warcraft III 1.27 source data (optional)\n"
        "\n"
        "You normally do not need to put anything here: click \"Open MPQ\" in the\n"
        "patcher and select your Warcraft III 1.27 install folder (the one with\n"
        "war3.mpq), the archives are read directly.\n"
        "\n"
        "Manual alternative: extract the 1.27 archives of a language here, e.g.\n"
        "  MPQ_Data/frFR-MPQ/war3.mpq/...\n"
        "  MPQ_Data/frFR-MPQ/War3x.mpq/...\n"
        "  MPQ_Data/frFR-MPQ/War3xlocal.mpq/...\n"
        "  MPQ_Data/frFR-MPQ/War3Patch.mpq/...\n"
    ),
    "CASC_Data": (
        "CASC_Data - files of the target version (1.30+, 1.31 recommended)\n"
        "\n"
        "Filled automatically: select the target game folder in \"Target Version\n"
        "(CASC)\" and the files of each language are extracted here at build time,\n"
        "e.g. CASC_Data/frfr.w3mod/...\n"
        "\n"
        "These files override the 1.27 ones in the patch. You can also place\n"
        "files here by hand (extracted with CascView, for example).\n"
    ),
    "merged": (
        "merged - the built patches\n"
        "\n"
        "After BUILD PATCH, each language ends up here as <lang>_patch.zip\n"
        "(e.g. frfr_patch.zip). Copy them with LANGUAGE_CHANGER.bat into the\n"
        "Warcraft III game folder and run the .bat.\n"
    ),
}
PLACEHOLDER = "placeholder.txt"


def ensure_workspace_folders(base) -> None:
    """Creates MPQ_Data, CASC_Data and merged with their placeholder.txt."""
    base = Path(base)
    for name, text in WORKSPACE_FOLDERS.items():
        folder = base / name
        try:
            folder.mkdir(parents=True, exist_ok=True)
            note = folder / PLACEHOLDER
            if not note.exists():
                note.write_text(text, encoding="utf-8")
        except OSError:
            pass


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
