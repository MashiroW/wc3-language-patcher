"""Read everything the patcher needs from the TARGET install (CASC, 1.30+).

For one language, prepare_target():
  1. extracts the target's own files of that language (only those installed
     locally) into CASC_Data/<lang>.w3mod; they override the 1.27 files,
  2. extracts the target's English UI text files, used as templates: they
     define which keys this exact version expects (missing ones get
     translated),
  3. writes a structure list (file layout of this version's locale).
Anything not available locally falls back to the bundled 1.31 data.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from .casc import CASCStorage, LOCALE_PREFIX, present_locales, is_reforged_layout

# target English file (inside the locale) -> bundled template it replaces
TEMPLATE_FILES = {
    "UI/WorldEditStrings.txt": "worldeditor_translator/worldeditstrings_template.txt",
    "UI/WorldEditGameStrings.txt": "worldeditor_translator/worldeditgamestrings_template.txt",
    "UI/FrameDef/GlobalStrings.fdf": "wc3keys_translater/globalstrings_template.fdf",
    "UI/CampaignStrings.txt": "campaignstrings_translator/template_1.31.txt",
    "UI/CampaignStrings_exp.txt": "campaignstrings_translator/template_exp_1.31.txt",
}
MARKER = ".extracted_from_target"


def inspect_target(game_dir):
    storage = CASCStorage(game_dir)
    try:
        return {"version": storage.version, "locales": present_locales(storage)}
    finally:
        storage.close()


def describe_locales(locales: dict) -> str:
    full = sorted(k for k, (p, t) in locales.items() if t and p / t > 0.9)
    return ", ".join(full) if full else "none"


def _locale_entries(storage, locale):
    prefix = LOCALE_PREFIX.format(locale).lower()
    return prefix, [(n, c) for n, c in storage.root_entries().items() if n.lower().startswith(prefix)]


def _folder_is_manual(folder: Path) -> bool:
    """True if the user put their own CASC files there (keep them)."""
    if not folder.exists() or (folder / MARKER).exists():
        return False
    return any(p.is_file() and p.name != "placeholder.txt" for p in folder.rglob("*"))


def prepare_target(game_dir, lang, casc_folder, work_dir, bundled_templates, bundled_structure, log=print):
    """Returns dict(version, templates_dir, structure_file, locale_files)."""
    casc_folder, work_dir = Path(casc_folder), Path(work_dir)
    storage = CASCStorage(game_dir)
    try:
        log(f"  | 🎯 Target: Warcraft III {storage.version} ({game_dir})")
        root = storage.root_entries()
        actual = next((k[len("War3.w3mod:_Locales/"):].split(".")[0] for k in root
                       if k.lower().startswith(LOCALE_PREFIX.format(lang).lower())), lang)

        # 1. the target's original files in this language
        locale_files = 0
        if _folder_is_manual(casc_folder):
            log(f"  |   ℹ️ Using the files already placed in CASC_Data/{casc_folder.name}")
            locale_files = sum(1 for p in casc_folder.rglob("*") if p.is_file())
        else:
            if casc_folder.exists():
                shutil.rmtree(casc_folder)
            prefix, entries = _locale_entries(storage, actual)
            present = [(n, c) for n, c in entries if storage.is_present(c)]
            # A text file of this language identical to the English one is just English
            # (typical when the language is not installed: only the files shared with
            # enUS are present). Those are not kept as "originals": the localized 1.27
            # text, completed with the newer keys, is preferred.
            if actual.lower() != "enus":
                en_pref = LOCALE_PREFIX.format("enUS").lower()
                en_ckeys = {k.lower()[len(en_pref):]: c for k, c in root.items() if k.lower().startswith(en_pref)}
                english_texts = [(n, c) for n, c in present
                                 if n.lower().endswith((".txt", ".fdf"))
                                 and en_ckeys.get(n.lower()[len(prefix):]) == c]
                if english_texts:
                    skip = set(n for n, _ in english_texts)
                    present = [(n, c) for n, c in present if n not in skip]
                    log(f"  |   ℹ️ {len(english_texts)} {lang} text file(s) of the target are identical to English: "
                        f"the 1.27 localized versions are used instead")
            if entries and is_reforged_layout(storage, actual):
                log("  |   ⚠️ Reforged 2.0+ target: voices are .ogg there; 1.27 voices are added as .mp3/.wav")
            unreadable = []
            for i, (name, ckey) in enumerate(present, 1):
                rel = name[len(prefix):].replace(":", "/")
                # A file can be listed as installed but stored incomplete (interrupted
                # download): it is skipped and the 1.27 version is used instead.
                try:
                    data = storage.read_ckey(ckey)
                except Exception:
                    unreadable.append(rel)
                else:
                    target = casc_folder.joinpath(*rel.split("/"))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                if i % 200 == 0 or i == len(present):
                    log(f"  |   | 📥 Original {lang} files from target: {i}/{len(present)} ({int(i / len(present) * 100)}%)")
            if unreadable:
                log(f"  |   ⚠️ {len(unreadable)} {lang} file(s) of the target are incomplete on disk, "
                    f"the 1.27 versions are used: " + ", ".join(Path(r).name for r in unreadable[:5])
                    + (" ..." if len(unreadable) > 5 else ""))
                present = [(n, c) for n, c in present if n[len(prefix):].replace(":", "/") not in unreadable]
            casc_folder.mkdir(parents=True, exist_ok=True)
            (casc_folder / MARKER).write_text(storage.version, encoding="utf-8")
            locale_files = len(present)
            if entries:
                log(f"  |   ✅ {len(present)}/{len(entries)} original {lang} files available in the target"
                    + ("" if len(present) == len(entries) else " (the rest is not installed locally)"))
            else:
                log(f"  |   ℹ️ The target has no {lang} locale: everything comes from 1.27 + translations")

        # 2. English templates of this exact version
        templates_dir = work_dir / "templates"
        if templates_dir.exists():
            shutil.rmtree(templates_dir)
        shutil.copytree(bundled_templates, templates_dir,
                        ignore=shutil.ignore_patterns("*.py", "__pycache__"))
        en_prefix = LOCALE_PREFIX.format("enUS")
        from_target = []
        for name, rel in TEMPLATE_FILES.items():
            ckey = next((c for k, c in root.items() if k.lower() == (en_prefix + name).lower()), None)
            if ckey is not None and storage.is_present(ckey):
                try:
                    data = storage.read_ckey(ckey)
                except Exception:
                    continue  # incomplete on disk: the bundled 1.31 reference is kept
                (templates_dir / rel).write_bytes(data)
                from_target.append(name.split("/")[-1])
        # every other English ui/ and units/ text file of this version (to complete
        # the 1.27 files with the keys added since)
        refs = 0
        for k, c in root.items():
            if not k.lower().startswith(en_prefix.lower()):
                continue
            rel = k[len(en_prefix):].replace(":", "/").lower()
            if rel.endswith((".txt", ".fdf")) and rel.startswith(("ui/", "units/")) and storage.is_present(c):
                try:
                    data = storage.read_ckey(c)
                except Exception:
                    continue  # incomplete on disk: the bundled reference (if any) is kept
                dest = templates_dir / "locale_templates" / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                refs += 1
        if refs:
            from_target.append(f"{refs} ui/units reference files")
        if from_target:
            log(f"  |   ✅ English reference texts read from the target: {', '.join(from_target)}")
        if len(from_target) < len(TEMPLATE_FILES):
            log("  |   ℹ️ English texts not installed in the target: bundled 1.31 references used for the rest")

        # 3. file layout of this version (union with the bundled list, which
        #    also carries the map layout and the 1.31 sound names)
        lines = []
        seen = set()
        for line in Path(bundled_structure).read_text(encoding="utf-8").splitlines():
            key = line.strip().replace("\\", "/").lower()
            if key and key not in seen:
                seen.add(key)
                lines.append(line.strip())
        added = 0
        for k in root:
            if k.lower().startswith(en_prefix.lower()):
                rel = k[len(en_prefix):].replace(":", "/")
                if rel.lower() not in seen:
                    seen.add(rel.lower())
                    lines.append(rel)
                    added += 1
        structure_file = work_dir / "structure.txt"
        structure_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if added:
            log(f"  |   ℹ️ {added} file path(s) specific to this version added to the layout")

        return {"version": storage.version, "templates_dir": templates_dir,
                "structure_file": structure_file, "locale_files": locale_files}
    finally:
        storage.close()


ENGLISH_BASE = "enus_patch.zip"
_MAPS_PREFIX = "war3.w3mod:maps/"


def build_english_base(game_dir, merged_dir, log=print):
    """Write merged/enus_patch.zip: the target's own maps, untouched.

    LANGUAGE_CHANGER.bat always extracts it first (it resets the maps folder),
    then the chosen language over it, so it is needed whatever the language.
    Nothing is translated: these are the files of the target version itself.
    Returns True if the archive is there (already up to date or just written)."""
    from zipfile import ZipFile, BadZipFile

    zip_path = Path(merged_dir) / ENGLISH_BASE
    storage = CASCStorage(game_dir)
    try:
        version = storage.version.encode("utf-8")
        try:
            with ZipFile(zip_path) as existing:
                if existing.comment == version:
                    log(f"  | 🗺️ {ENGLISH_BASE} already built for this target ({storage.version})")
                    return True
        except (OSError, BadZipFile):
            pass
        root = storage.root_entries()
        maps = sorted((k, c) for k, c in root.items()
                      if k.lower().startswith(_MAPS_PREFIX) and k.count(":") == 1)
        if not maps:
            log(f"  | ⚠️ {ENGLISH_BASE} not created: no maps found in the target")
            return False
        Path(merged_dir).mkdir(parents=True, exist_ok=True)
        tmp = zip_path.with_suffix(".zip.tmp")
        written, skipped = 0, 0
        with ZipFile(tmp, "w") as zipf:
            zipf.comment = version
            for name, ckey in maps:
                try:
                    data = storage.read_ckey(ckey)
                except Exception:
                    skipped += 1    # not installed or incomplete on disk
                    continue
                zipf.writestr(name.split(":", 1)[1].lower(), data)
                written += 1
        if not written:
            tmp.unlink()
            log(f"  | ⚠️ {ENGLISH_BASE} not created: the target's maps are not installed locally")
            return False
        tmp.replace(zip_path)
        log(f"  | 🗺️ {ENGLISH_BASE} created from the target: {written} maps"
            + (f" ({skipped} not readable, skipped)" if skipped else ""))
        return True
    finally:
        storage.close()
