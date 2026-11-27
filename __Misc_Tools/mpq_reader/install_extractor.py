"""Extract a Warcraft III 1.27 install into the layout the patcher expects:

    MPQ_Data/<region>-MPQ/war3.mpq/...
    MPQ_Data/<region>-MPQ/War3x.mpq/...
    MPQ_Data/<region>-MPQ/War3xlocal.mpq/...
    MPQ_Data/<region>-MPQ/War3Patch.mpq/...

This replaces the manual "open each archive in MPQ Editor and extract all" step.
"""
from __future__ import annotations

from pathlib import Path

from .mpq import extract_archive, MPQArchive

ARCHIVES = ["war3.mpq", "War3x.mpq", "War3xlocal.mpq", "War3Patch.mpq"]


def find_archives(install_dir) -> dict[str, Path]:
    install_dir = Path(install_dir)
    found = {}
    lower = {p.name.lower(): p for p in install_dir.iterdir() if p.is_file()}
    for name in ARCHIVES:
        p = lower.get(name.lower())
        if p:
            found[name] = p
    return found


def extract_install(install_dir, region_dir, log=print):
    """Returns a dict archive -> (extracted, failed list)."""
    region_dir = Path(region_dir)
    archives = find_archives(install_dir)
    missing = [a for a in ARCHIVES if a not in archives]
    if missing:
        raise FileNotFoundError(
            f"Missing archive(s) in {install_dir}: {', '.join(missing)}")

    # War3Patch.mpq has no (listfile): reuse the names of the other archives.
    known_names = []
    for name in ARCHIVES[:3]:
        with MPQArchive(archives[name]) as a:
            known_names.extend(a.listfile())

    results = {}
    for name in ARCHIVES:
        log(f"  | 📦 Extracting {name} ...")

        def progress(done, total, _n=name):
            log(f"  |   | {_n}: {done}/{total} ({int(done / max(total, 1) * 100)}%)")

        extra = known_names if name == "War3Patch.mpq" else ()
        ok, failed, _ = extract_archive(archives[name], region_dir / name,
                                        extra_names=extra, progress=progress)
        results[name] = (ok, failed)
        log(f"  |   ✅ {name}: {ok} files" + (f", {len(failed)} failed" if failed else ""))
    # remember the game version (shown next to "Open MPQ")
    # (only a label: never let it break an import)
    try:
        from __Misc_Tools.game_version import mpq_install_version, VERSION_FILE
        version = mpq_install_version(install_dir)
        if version:
            (region_dir / VERSION_FILE).write_text(version + "\n", encoding="utf-8")
    except Exception as e:
        log(f"  |   ⚠️ Game version not saved ({e}): the import itself is fine")
    return results
