import os
import re
import shutil
from pathlib import Path

# === MAPPINGS ===
REGION_TO_LANGUAGE = {
    "frFR": "French",
    "enUS": "English",
    "deDE": "German",
    "itIT": "Italian",
    "esES": "Spanish",
    "ruRU": "Russian",
    "zhCN": "Simpl. Chinese",
    "zhTW": "Trad. Chinese",
    "koKR": "Korean",
    "plPL": "Polish",
    "csCZ": "Czech",
    "ptBR": "Portuguese",
}

ROC_SCENARIO_MAPS = ["(1)TheDeathSheep.w3m", "(4)WarChasers.w3m"]
TFT_SCENARIO_MAPS = [
    "(4)Monolith.w3x", "(6)BlizzardTD.w3x", "(6)BomberCommand.w3x",
    "(8)AzerothGrandPrix.w3x", "(8)AzureTowerDefense.w3x",
    "(8)FunnyBunnysEggHunt.w3x", "(10)ExtremeCandyWar2004.w3x",
    "(10)Skibi'sCastleTD.w3x", "(12)WormWar.w3x"
]

# Highest priority last: a file in War3Patch.mpq overrides the same file elsewhere
MPQ_PRIORITY = {
    "war3.mpq": 0,
    "war3x.mpq": 1,
    "war3xlocal.mpq": 2,
    "war3patch.mpq": 3,
}

# Entries of structure.txt that are not game files
_IGNORED_STRUCTURE_ENTRIES = {"structure.txt", "file_structure.bat"}


def find_child_ci(folder: Path, name: str):
    """Case-insensitive child lookup (archive folders are named inconsistently,
    e.g. War3xlocal.mpq vs War3xLocal.mpq). Returns None if missing."""
    if not folder.exists():
        return None
    direct = folder / name
    if direct.exists():
        return direct
    low = name.lower()
    for child in folder.iterdir():
        if child.name.lower() == low:
            return child
    return None


def find_path_ci(base: Path, *parts):
    current = base
    for part in parts:
        current = find_child_ci(current, part)
        if current is None:
            return None
    return current


def load_structure(structure_file: Path):
    entries = []
    with open(structure_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip().replace("\\", "/")
            if line and line.lower() not in _IGNORED_STRUCTURE_ENTRIES:
                entries.append(line)
    return entries


def convert_mpq_to_casc(region_folder_path, progress_callback=None, structure_file=None):
    """
    Convert one extracted 1.27 region folder (MPQ_Data/xxXX-MPQ) to the CASC layout.

    Returns a result dict, or None when the conversion could not run.
    """
    progress_callback = progress_callback or print
    region_folder = Path(region_folder_path)

    region_code = region_folder.name.split('-')[0]
    language_name = REGION_TO_LANGUAGE.get(region_code, region_code)

    progress_callback(f"🚀 Starting patch creation for: {region_code}")
    progress_callback("  | 💱 Converting MPQ data to CASC format...")

    if not re.match(r'^[a-z]{2}[A-Z]{2}-MPQ$', region_folder.name):
        progress_callback(f"  - ⚠️ Folder path is incorrect: {region_folder}")
        progress_callback(f"⛔ Patching has stopped for region {region_code}")
        return None

    structure_file = Path(structure_file) if structure_file else Path(__file__).resolve().parent / "structure.txt"
    if not structure_file.exists():
        progress_callback(f'  | ⚠️ structure.txt not found, expected at: "{structure_file}"')
        progress_callback(f"⛔ Patching has stopped for region {region_code}")
        return None

    output_folder = region_folder.parent / f"{region_folder.name}-converted-to-CASC"
    if output_folder.exists():
        shutil.rmtree(output_folder)

    # Index every extracted file by lower-case name
    mpq_files = {}
    archives_found = 0
    for archive_name, priority in MPQ_PRIORITY.items():
        folder = find_child_ci(region_folder, archive_name)
        if folder is None or not folder.is_dir():
            progress_callback(f"  | ⚠️ {archive_name} folder not found in {region_folder.name}")
            continue
        archives_found += 1
        for root, _, files in os.walk(folder):
            rel_parts = [p.lower() for p in Path(root).relative_to(folder).parts]
            for file in files:
                if file == "placeholder.txt":
                    continue
                mpq_files.setdefault(file.lower(), []).append((Path(root) / file, rel_parts, priority))

    if archives_found == 0 or not mpq_files:
        progress_callback("  | ⛔ No extracted MPQ data found. Extract war3.mpq, War3x.mpq, "
                          "War3xlocal.mpq and War3Patch.mpq first (or use 'Import 1.27 install').")
        progress_callback(f"⛔ Patching has stopped for region {region_code}")
        return None

    required_paths = load_structure(structure_file)
    copied = 0
    missing = 0
    total_files = len(required_paths)

    progress_callback(f"  | 📝 Copying files... 0/{total_files} (0%)")

    for i, rel_path in enumerate(required_paths):
        if i % 10 == 0 or i == total_files - 1:
            percent = int((i + 1) / total_files * 100)
            progress_callback(f"  | 📝 Copying files... {i+1}/{total_files} ({percent}%)")

        target_path = Path(rel_path)
        filename = target_path.name.lower()
        parent_dirs = [p.lower() for p in target_path.parent.parts]
        output_path = output_folder / target_path

        best_candidate = None
        best_score = -1
        best_priority = -1
        for full_path, parts, priority in mpq_files.get(filename, []):
            score = 0
            for a, b in zip(parent_dirs, parts):
                if a != b:
                    break
                score += 1
            if score > best_score or (score == best_score and priority > best_priority):
                best_candidate, best_score, best_priority = full_path, score, priority

        if best_candidate:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(best_candidate, output_path)
            copied += 1
        else:
            missing += 1

    # === MAPS ===
    maps_copied = 0
    maps_dest = output_folder / "maps" / f"{language_name} Maps Patch (1.27 backup)"
    roc_scenario_dest = maps_dest / "Scenario"
    frozen_throne_dest = maps_dest / "FrozenThrone"
    tft_scenario_dest = frozen_throne_dest / "Scenario"
    for folder in [maps_dest, roc_scenario_dest, frozen_throne_dest, tft_scenario_dest]:
        folder.mkdir(parents=True, exist_ok=True)

    war3x_mpq_folder = find_child_ci(region_folder, "War3x.mpq")
    if war3x_mpq_folder:
        for map_file in war3x_mpq_folder.iterdir():
            suffix = map_file.suffix.lower()
            if suffix == ".w3m":
                dest = roc_scenario_dest if map_file.name in ROC_SCENARIO_MAPS else maps_dest
            elif suffix == ".w3x":
                dest = tft_scenario_dest if map_file.name in TFT_SCENARIO_MAPS else frozen_throne_dest
            else:
                continue
            shutil.copy2(map_file, dest / map_file.name)
            maps_copied += 1

    # 1. war3.mpq\Maps\Campaign\*.w3m -> maps/campaign/
    war3_campaign_folder = find_path_ci(region_folder, "war3.mpq", "Maps", "Campaign")
    if war3_campaign_folder:
        maps_dir = output_folder / "maps" / "campaign"
        maps_dir.mkdir(parents=True, exist_ok=True)
        for map_file in war3_campaign_folder.iterdir():
            if map_file.suffix.lower() == ".w3m":
                shutil.copy2(map_file, maps_dir / map_file.name)
                maps_copied += 1

    # 2. War3xlocal.mpq\Maps\FrozenThrone\Campaign\*.w3x -> maps/FrozenThrone/Campaign/
    tft_campaign_folder = find_path_ci(region_folder, "War3xlocal.mpq", "Maps", "FrozenThrone", "Campaign")
    if tft_campaign_folder:
        tft_campaign_dest = output_folder / "maps" / "FrozenThrone" / "Campaign"
        tft_campaign_dest.mkdir(parents=True, exist_ok=True)
        for map_file in tft_campaign_folder.iterdir():
            if map_file.suffix.lower() == ".w3x":
                shutil.copy2(map_file, tft_campaign_dest / map_file.name)
                maps_copied += 1

    progress_callback(f"  | ✅ MPQ data converted to CASC format "
                      f"({copied} files, {missing} not present in 1.27, {maps_copied} maps)")

    return {
        "region": region_folder.name,
        "copied_files": copied,
        "missing_files": missing,
        "copied_maps": maps_copied,
        "output_folder": str(output_folder),
    }
