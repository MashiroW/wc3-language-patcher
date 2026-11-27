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


def load_structure(structure_file: Path):
    entries = []
    with open(structure_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip().replace("\\", "/")
            if not line or line.lower() in _IGNORED_STRUCTURE_ENTRIES:
                continue
            # Reforged-style map folders (maps/.../x.w3x/war3map.j): 1.31 uses map
            # files, and matching their content would create a folder named x.w3x
            if any(p.lower().endswith((".w3m", ".w3x")) for p in line.split("/")[:-1]):
                continue
            entries.append(line)
    return entries




def convert_mpq_to_casc(region_folder_path, progress_callback=None, structure_file=None, install_dir=None):
    """
    Convert one language's 1.27 files to the CASC layout.

    region_folder_path: MPQ_Data/xxXX-MPQ (the output goes next to it, in
                        xxXX-MPQ-converted-to-CASC)
    install_dir:        a 1.27 install folder; when given, the .mpq archives are
                        read directly and nothing needs to be extracted first.
                        Otherwise region_folder_path must hold the extracted
                        archives (original workflow).

    Returns a result dict, or None when the conversion could not run.
    """
    from .sources import FolderSource, ArchiveSource

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

    try:
        source = ArchiveSource(install_dir, progress_callback) if install_dir else FolderSource(region_folder, progress_callback)
    except Exception as e:
        progress_callback(f"  | ⛔ Cannot read the 1.27 files: {e}")
        progress_callback(f"⛔ Patching has stopped for region {region_code}")
        return None

    try:
        if not source.index:
            progress_callback("  | ⛔ No 1.27 data found. Choose the 1.27 install folder of this language "
                              "in the '1.27 Source' column.")
            progress_callback(f"⛔ Patching has stopped for region {region_code}")
            return None

        region_folder.parent.mkdir(parents=True, exist_ok=True)
        output_folder = region_folder.parent / f"{region_folder.name}-converted-to-CASC"
        if output_folder.exists():
            shutil.rmtree(output_folder)

        required_paths = load_structure(structure_file)
        copied = missing = 0
        total_files = len(required_paths)
        progress_callback(f"  | 📝 Copying files... 0/{total_files} (0%)")

        for i, rel_path in enumerate(required_paths):
            if i % 10 == 0 or i == total_files - 1:
                percent = int((i + 1) / total_files * 100)
                progress_callback(f"  | 📝 Copying files... {i+1}/{total_files} ({percent}%)")

            target_path = Path(rel_path)
            filename = target_path.name.lower()
            parent_dirs = [p.lower() for p in target_path.parent.parts]

            # rank: common leading folders, then folders shared anywhere
            # (_balance/custom_v0.w3mod/units -> Custom_V0/Units), then archive priority
            wanted = {d[:-6] if d.endswith(".w3mod") else d for d in parent_dirs}
            best, best_rank = None, None
            for handle, parts, priority in source.index.get(filename, []):
                score = 0
                for a, b in zip(parent_dirs, parts):
                    if a != b:
                        break
                    score += 1
                shared = sum(1 for part in parts if part in wanted)
                extra = len(parts) - shared
                rank = (score, shared, -extra, priority)
                if best_rank is None or rank > best_rank:
                    best, best_rank = handle, rank

            if best is not None:
                output_path = output_folder / target_path
                output_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    source.write(best, output_path)
                    copied += 1
                except Exception as e:
                    progress_callback(f"  | ⚠️ Could not read {rel_path}: {e}")
                    missing += 1
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

        # Loose maps of the 1.27 install (Maps/, Maps/Scenario, Maps/FrozenThrone, ...):
        # the localized melee/scenario maps, kept as the "1.27 backup" set
        if install_dir:
            maps_root = find_child_ci(Path(install_dir), "Maps")
            if maps_root is not None:
                for f in maps_root.rglob("*"):
                    if not f.is_file() or f.suffix.lower() not in (".w3m", ".w3x"):
                        continue
                    rel = f.relative_to(maps_root)
                    if any(p.lower() in ("campaign", "download") for p in rel.parts[:-1]):
                        continue
                    dest = maps_dest.joinpath(*rel.parts)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dest)
                    maps_copied += 1

        # War3x.mpq root: melee / scenario maps (1.27 balance backup)
        for name, handle in source.children("War3x.mpq"):
            low = name.lower()
            if low.endswith(".w3m"):
                dest = roc_scenario_dest if name in ROC_SCENARIO_MAPS else maps_dest
            elif low.endswith(".w3x"):
                dest = tft_scenario_dest if name in TFT_SCENARIO_MAPS else frozen_throne_dest
            else:
                continue
            source.write(handle, dest / name)
            maps_copied += 1

        # war3.mpq\Maps\Campaign\*.w3m -> maps/campaign/
        roc = [(n, h) for n, h in source.children("war3.mpq", "Maps", "Campaign") if n.lower().endswith(".w3m")]
        if roc:
            maps_dir = output_folder / "maps" / "campaign"
            maps_dir.mkdir(parents=True, exist_ok=True)
            for name, handle in roc:
                source.write(handle, maps_dir / name)
                maps_copied += 1

        # War3xlocal.mpq\Maps\FrozenThrone\Campaign\*.w3x. The 1.31 campaign menu points to
        # "Campaign\FrozenThrone\X.w3x" (same convention as RoC's "Campaign\Human01.w3m" ->
        # maps/campaign/), so they go to maps/campaign/FrozenThrone/; the old 1.27-style
        # location is kept as well.
        tft = [(n, h) for n, h in source.children("War3xlocal.mpq", "Maps", "FrozenThrone", "Campaign")
               if n.lower().endswith(".w3x")]
        if tft:
            destinations = [output_folder / "maps" / "campaign" / "FrozenThrone",
                            output_folder / "maps" / "FrozenThrone" / "Campaign"]
            for dest in destinations:
                dest.mkdir(parents=True, exist_ok=True)
            for name, handle in tft:
                source.write(handle, destinations[0] / name)
                shutil.copy2(destinations[0] / name, destinations[1] / name)
                maps_copied += 1

        # Cinematic audio (movies/audio/*.mp3) from the 1.27 Movies/*.mpq videos;
        # hand-made files in _HomeMade_Data still override them later
        if install_dir:
            from __Misc_Tools.mpq_reader.avi_audio import extract_cinematic_audio
            extract_cinematic_audio(install_dir, output_folder / "movies" / "audio", progress_callback)

        progress_callback(f"  | ✅ MPQ data converted to CASC format "
                          f"({copied} files, {missing} not present in 1.27, {maps_copied} maps)")
        return {
            "region": region_folder.name,
            "copied_files": copied,
            "missing_files": missing,
            "copied_maps": maps_copied,
            "output_folder": str(output_folder),
        }
    finally:
        source.close()
