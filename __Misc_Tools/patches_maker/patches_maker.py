import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

from __Misc_Tools.translation.translator import StringTranslator
from __Misc_Tools.translation.string_merge import (
    merge_ini_strings, merge_fdf_strings, convert_campaign_strings)


def build_patch_for_region(progress_callback, mpq_to_casc_path, workspace_dir=None,
                           resource_dir=None, allow_online_translation=False):
    """Create the patch zip for one region.

    workspace_dir: writable folder holding MPQ_Data, CASC_Data and merged/
    resource_dir:  read-only folder holding __Misc_Tools templates,
                   _HomeMade_Data and translations/ (inside the .exe when frozen)
    """
    progress_callback = progress_callback or print
    try:
        MPQ_DATA_TO_CASC = Path(mpq_to_casc_path)
        base_dir = Path(workspace_dir) if workspace_dir else MPQ_DATA_TO_CASC.parent.parent
        res_dir = Path(resource_dir) if resource_dir else base_dir

        MPQ_DATA = base_dir / "MPQ_Data"
        CASC_DATA = base_dir / "CASC_Data"
        MERGED = base_dir / "merged"
        HOMEMADE_DATA = res_dir / "_HomeMade_Data"
        TEMPLATES = res_dir / "__Misc_Tools"

        for directory in (MPQ_DATA, CASC_DATA, MERGED):
            directory.mkdir(exist_ok=True)

        if not MPQ_DATA_TO_CASC.exists():
            progress_callback(f"  | ⛔ Converted data not found: {MPQ_DATA_TO_CASC}")
            return False

        region_code = extract_region_code(MPQ_DATA_TO_CASC, progress_callback)
        if not region_code:
            return False

        region_patch_folder = MERGED / f"{region_code}_patch"
        if region_patch_folder.exists():
            shutil.rmtree(region_patch_folder)
        region_patch_folder.mkdir()

        # Step 1: MPQ_converted_to_CASC data (excluding sound)
        copy_contents(MPQ_DATA_TO_CASC, region_patch_folder, skip_sound=True,
                      label="  | 📝 Copying MPQ_to_CASC files ...", progress_callback=progress_callback)

        # Step 2: CASC data (including sound, excluding maps)
        casc_region_folder = find_casc_folder(CASC_DATA, region_code)
        has_casc = casc_region_folder is not None and any(
            p.name != "placeholder.txt" for p in casc_region_folder.rglob("*") if p.is_file())
        if has_casc:
            copy_contents(casc_region_folder, region_patch_folder, skip_w3x=True,
                          label="  | 📝 Copying CASC files ...", progress_callback=progress_callback)
        else:
            progress_callback(f"  | ⚠️ CASC data not found for {region_code} in {CASC_DATA}")
            progress_callback("  | ℹ️ Proceeding without CASC data (1.27 texts will be converted)...")

        # Step 3: MPQ sound files override CASC ones (original voices)
        copy_contents(MPQ_DATA_TO_CASC, region_patch_folder, only_sound=True,
                      label=f"  | 🔊 Overriding Sound with MPQ's for ({region_code})",
                      progress_callback=progress_callback)

        # Step 4: homemade overrides (region specific; _HomeMade_Data/_general is
        # not applied automatically, as in the original tool)
        homemade_folder = find_homemade_folder(region_code, HOMEMADE_DATA)
        if homemade_folder:
            copy_contents(homemade_folder, region_patch_folder,
                          label=f"  | 🛠️ HomeMade ({region_code})", progress_callback=progress_callback)
        else:
            progress_callback(f"  | ℹ️ No HomeMade data found for {region_code}")

        # Step 5: clean unnecessary files
        clean_folder(region_patch_folder, progress_callback)

        # Step 6: bring 1.27 text files to the 1.31 layout
        translator = StringTranslator(region_code, res_dir / "translations", progress_callback,
                                      allow_online=allow_online_translation)
        update_text_files(region_patch_folder, TEMPLATES, translator, has_casc, progress_callback)
        progress_callback(f"  | 🌍 Missing strings: {translator.summary()}")

        # Step 7: remove the temporary converted folder
        shutil.rmtree(MPQ_DATA_TO_CASC, ignore_errors=True)
        progress_callback(f"  | ✅ Removed temporary folder: {MPQ_DATA_TO_CASC.name}")

        # Step 8: package
        zip_and_remove(region_patch_folder, progress_callback)
        progress_callback(f"✅ Successfully created patch for: {region_code}")
        return True

    except Exception as e:
        progress_callback(f"  | ⛔ Critical error creating patch: {e}")
        logging.exception("Patch creation failed")
        return False


def find_file_ci(folder: Path, *parts):
    current = folder
    for part in parts:
        if current is None or not current.is_dir():
            return None
        low = part.lower()
        current = next((c for c in current.iterdir() if c.name.lower() == low), None)
    return current


def update_text_files(patch_folder, templates_dir, translator, has_casc, log):
    ui = find_file_ci(patch_folder, "ui")
    if ui is None:
        log(f"  | ⚠️ UI folder not found in {patch_folder.name}")
        return

    jobs = [
        ("worldeditor_translator/worldeditstrings_template.txt", ("WorldEditStrings.txt",), merge_ini_strings),
        ("worldeditor_translator/worldeditgamestrings_template.txt", ("WorldEditGameStrings.txt",), merge_ini_strings),
        ("wc3keys_translater/globalstrings_template.fdf", ("framedef", "GlobalStrings.fdf"), merge_fdf_strings),
    ]
    for template_rel, target_parts, func in jobs:
        template = templates_dir / template_rel
        target = find_file_ci(ui, *target_parts)
        if not template.exists():
            log(f"  | ⚠️ Template file not found: {template}")
            continue
        if target is None:
            log(f"  | ⚠️ Target file not found: ui/{'/'.join(target_parts)}")
            continue
        log(f"  | 🌍 Updating {target.name} for {translator.region_code}")
        try:
            func(template, target, translator, log)
        except Exception as e:
            log(f"  | ⛔ Failed to update {target.name}: {e}")

    # Campaign menus: only needed when the files come from 1.27 (no CASC data)
    if not has_casc:
        for template_rel, name in (("campaignstrings_translator/template_1.31.txt", "CampaignStrings.txt"),
                                   ("campaignstrings_translator/template_exp_1.31.txt", "CampaignStrings_exp.txt")):
            target = find_file_ci(ui, name)
            if target is None:
                log(f"  | ⚠️ {name} not found, campaign menu left untouched")
                continue
            try:
                convert_campaign_strings(target, templates_dir / template_rel, log)
            except Exception as e:
                log(f"  | ⛔ Failed to convert {name}: {e}")


def extract_region_code(MPQ_DATA_TO_CASC, progress_callback):
    """Extract region code from MPQ folder path in aaBB format"""
    match = re.match(r"([a-z]{2}[A-Z]{2})[-_]", Path(MPQ_DATA_TO_CASC).name)
    if match:
        return match.group(1)
    progress_callback(f"  | ⚠️ Could not extract region code from: {MPQ_DATA_TO_CASC}")
    return None


def find_casc_folder(casc_data: Path, region_code: str):
    if not casc_data.exists():
        return None
    wanted = f"{region_code}.w3mod".lower()
    for folder in casc_data.iterdir():
        if folder.is_dir() and folder.name.lower() == wanted:
            return folder
    return None


def skip_w3m_w3x_folder(path: Path):
    """Check if path should be skipped as map folder"""
    return any(part.lower().endswith((".w3x", ".w3m")) for part in path.parts)


def _has_part(rel_path: Path, name: str):
    return any(p.lower() == name for p in rel_path.parts)


def copy_contents(src_dir, dest_dir, skip_w3x=False, skip_sound=False,
                  only_sound=False, label="Copying", progress_callback=None):
    """Copy files with progress reporting"""
    progress_callback = progress_callback or print
    src_dir = Path(src_dir)
    if not src_dir.is_dir():
        progress_callback(f"  | ⚠️ Source directory not found: {src_dir}")
        return

    all_files = [p for p in src_dir.rglob("*") if p.is_file() and p.name != "placeholder.txt"]
    if not all_files:
        progress_callback(f"  | ⚠️ No files found in: {src_dir}")
        return

    total_files = len(all_files)
    for processed, item in enumerate(all_files, 1):
        rel_path = item.relative_to(src_dir)
        if skip_sound and _has_part(rel_path, "sound"):
            continue
        if only_sound and not _has_part(rel_path, "sound"):
            continue
        if skip_w3x and skip_w3m_w3x_folder(rel_path):
            continue
        dest_path = dest_dir / rel_path
        try:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest_path)
        except Exception as e:
            progress_callback(f"  - ⚠️ Error copying {item}: {e}")
        if processed % 50 == 0 or processed == total_files:
            progress_callback(f"{label}: {processed}/{total_files} ({int(processed / total_files * 100)}%)")


def clean_folder(folder_path, progress_callback):
    """Remove top-level entries the game does not need"""
    if not folder_path.exists():
        return
    progress_callback(f"  | 🧹 Cleaning temporary folder: {folder_path.name}")

    allowed_dirs = {"maps", "movies", "sound", "ui", "units", "campaign", "fonts"}
    allowed_files = {"war3patch.txt"}
    removed_dirs = removed_files = 0

    for item in folder_path.iterdir():
        name = item.name.lower()
        if name in allowed_dirs or name in allowed_files:
            continue
        try:
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
                removed_dirs += 1
                progress_callback(f"  |   |  🗑️ Removed directory: {item.name}")
            else:
                item.unlink()
                removed_files += 1
        except Exception as e:
            progress_callback(f"  | ⚠️ Error removing {item.name}: {e}")

    progress_callback(f"  | 🧹 Cleanup complete | Dirs: {removed_dirs}, Files: {removed_files}")


def zip_and_remove(folder_path, progress_callback):
    """Create zip archive and remove original folder"""
    if not folder_path.exists():
        progress_callback(f"  | ⚠️ Nothing to zip: {folder_path} not found")
        return

    zip_path = folder_path.with_suffix(".zip")
    if zip_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = zip_path.with_name(f"{zip_path.stem}_{timestamp}.zip")

    progress_callback(f"  | 📦 Creating archive: {zip_path.name}")
    all_files = [p for p in folder_path.rglob("*") if p.is_file()]
    if not all_files:
        progress_callback("  | ⚠️ Nothing to zip | folder is empty")
        return

    total_files = len(all_files)
    try:
        with ZipFile(zip_path, "w") as zipf:
            for processed, file in enumerate(all_files, 1):
                zipf.write(file, file.relative_to(folder_path))
                if processed % 50 == 0 or processed == total_files:
                    progress_callback(f"  |   |   Zipping: {processed}/{total_files} ({int(processed / total_files * 100)}%)")

        if zip_path.stat().st_size == 0:
            progress_callback("⛔ Created zip file is empty!")
            zip_path.unlink()
            return

        shutil.rmtree(folder_path, ignore_errors=True)
        progress_callback(f"  | ✅ Removed temporary folder: {folder_path.name}")
        progress_callback(f"  | 📦 Archive created: {zip_path.name} ({zip_path.stat().st_size // 1024} KB)")
        progress_callback(f"  | 📁 Saved to: {zip_path.resolve()}")
    except Exception as e:
        progress_callback(f"  | ⛔ Zip creation failed: {e}")


def find_homemade_folder(region_code, HOMEMADE_DATA):
    """Find matching homemade folder with case-insensitive search"""
    if not HOMEMADE_DATA.exists():
        return None
    region_lower = region_code.lower()
    for folder in HOMEMADE_DATA.iterdir():
        if folder.is_dir() and folder.name.lower().startswith(region_lower):
            return folder
    return None
