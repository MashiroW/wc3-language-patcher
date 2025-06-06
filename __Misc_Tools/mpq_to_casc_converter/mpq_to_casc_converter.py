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
    "zhCN": "Trad. Chinese",
    "koKR": "Korean",
    "plPL": "Polish",
    "ptBR": "Portuguese",
}

ROC_SCENARIO_MAPS = ["(1)TheDeathSheep.w3m", "(4)WarChasers.w3m"]
TFT_SCENARIO_MAPS = [
    "(4)Monolith.w3x", "(6)BlizzardTD.w3x", "(6)BomberCommand.w3x",
    "(8)AzerothGrandPrix.w3x", "(8)AzureTowerDefense.w3x",
    "(8)FunnyBunnysEggHunt.w3x", "(10)ExtremeCandyWar2004.w3x",
    "(10)Skibi'sCastleTD.w3x", "(12)WormWar.w3x"
]

def convert_mpq_to_casc(region_folder_path, progress_callback=None):
    """
    Process a single region folder to convert MPQ files to CASC format
    
    Args:
        region_folder_path: Full path to the region folder
        progress_callback: Function to call with progress updates (optional)

    Returns:
        Dictionary with processing results
    """
    region_folder = Path(region_folder_path)

    region_code = region_folder.name.split('-')[0]
    language_name = REGION_TO_LANGUAGE.get(region_code, region_code)

    progress_callback(f"🚀 Starting patch creation for: {region_code}")
    progress_callback("  | 💱 Converting MPQ data to CASC format...")
    
    # Validate folder name format
    if not re.match(r'^[a-z]{2}[A-Z]{2}-MPQ$', region_folder.name):
        error_msg = f"Invalid folder format: {region_folder.name}"
        progress_callback(f"  - ⚠️ Folder path is incorrect: {region_folder}")
        progress_callback(f"⛔ Patching has stopped for region {region_code}")
        return False

    script_dir = Path(__file__).resolve().parent
    output_folder = region_folder.parent / f"{region_folder.name}-converted-to-CASC"
    
    mpq_folders = [
        region_folder / "war3.mpq",
        region_folder / "War3x.mpq",
        region_folder / "War3xlocal.mpq",
        region_folder / "War3Patch.mpq"
    ]

    MPQ_PRIORITY = {
        "war3.mpq": 0,
        "War3x.mpq": 1,
        "War3xlocal.mpq": 2,
        "War3Patch.mpq": 3
    }
    
    mpq_files = {}
    for folder in mpq_folders:
        if not folder.exists():
            continue
        
        priority = MPQ_PRIORITY.get(folder.name, 0)
        
        for root, _, files in os.walk(folder):
            for file in files:
                file_lower = file.lower()
                rel_path = Path(root).relative_to(folder)
                path_parts = [p.lower() for p in rel_path.parts]
                
                if file_lower not in mpq_files:
                    mpq_files[file_lower] = []
                mpq_files[file_lower].append((Path(root) / file, path_parts, priority))

    casc_structure_file = script_dir / "structure.txt"
    if not casc_structure_file.exists():
        progress_callback(f'  | ⚠️ structure.txt not found and expected at: ".\__Misc_Tools\mpq_to_casc_converter\structure.txt"')
        progress_callback(f"⛔ Patching has stopped for region {region_code}")
        return False
    
    with open(casc_structure_file, 'r', encoding='utf-8') as f:
        required_paths = [line.strip() for line in f if line.strip()]

    copied = 0
    missing = 0
    total_files = len(required_paths)
    
    progress_callback(f"  | 📝 Copying files... 0/{total_files} (0%)")
    
    for i, rel_path in enumerate(required_paths):
        if progress_callback and (i % 10 == 0 or i == total_files - 1):
            percent = int((i + 1) / total_files * 100)
            progress_callback(f"  | 📝 Copying files... {i+1}/{total_files} ({percent}%)")
        
        target_path = Path(rel_path)
        filename = target_path.name.lower()
        parent_dirs = [p.lower() for p in target_path.parent.parts]
        output_path = output_folder / rel_path
        
        candidates = mpq_files.get(filename, [])
        best_candidate = None
        best_score = -1
        best_priority = -1
        
        for full_path, parts, priority in candidates:
            score = 0
            for i, (a, b) in enumerate(zip(parent_dirs, parts)):
                if a == b:
                    score += 1
                else:
                    break
                    
            if (score > best_score or 
                (score == best_score and priority > best_priority)):
                best_candidate = (full_path, parts, priority)
                best_score = score
                best_priority = priority
                
        if best_candidate:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(best_candidate[0], output_path)
            copied += 1
        else:
            missing += 1

    maps_copied = 0
    war3x_mpq_folder = region_folder / "war3x.mpq"
    
    maps_dest = output_folder / "maps" / f"{language_name} Maps Patch (1.27 backup)"
    roc_scenario_dest = maps_dest / "Scenario"
    frozen_throne_dest = maps_dest / "FrozenThrone"
    tft_scenario_dest = frozen_throne_dest / "Scenario"
    
    for folder in [maps_dest, roc_scenario_dest, frozen_throne_dest, tft_scenario_dest]:
        folder.mkdir(parents=True, exist_ok=True)
    
    for map_file in war3x_mpq_folder.glob("*.w3m"):
        map_name = map_file.name
        dest_path = roc_scenario_dest / map_name if map_name in ROC_SCENARIO_MAPS else maps_dest / map_name
        shutil.copy2(map_file, dest_path)
        maps_copied += 1
    
    for map_file in war3x_mpq_folder.glob("*.w3x"):
        map_name = map_file.name
        dest_path = tft_scenario_dest / map_name if map_name in TFT_SCENARIO_MAPS else frozen_throne_dest / map_name
        shutil.copy2(map_file, dest_path)
        maps_copied += 1

    # === COPY EXTRA CAMPAIGN MAPS ===

    # 1. From war3.mpq\Maps\Campaign\*.w3m to maps/
    war3_campaign_folder = region_folder / "war3.mpq" / "Maps" / "Campaign"
    if war3_campaign_folder.exists():
        maps_dir = output_folder / "maps" / "campaign"
        maps_dir.mkdir(parents=True, exist_ok=True)
        for map_file in war3_campaign_folder.glob("*.w3m"):
            shutil.copy2(map_file, maps_dir / map_file.name)
            maps_copied += 1

    # 2. From War3xlocal.mpq\Maps\FrozenThrone\Campaign\*.w3x to maps/FrozenThrone/Campaign/
    tft_campaign_folder = region_folder / "War3xlocal.mpq" / "Maps" / "FrozenThrone" / "Campaign"
    tft_campaign_dest = output_folder / "maps" / "FrozenThrone" / "Campaign"
    if tft_campaign_folder.exists():
        tft_campaign_dest.mkdir(parents=True, exist_ok=True)
        for map_file in tft_campaign_folder.glob("*.w3x"):
            shutil.copy2(map_file, tft_campaign_dest / map_file.name)
            maps_copied += 1

    result = {
        "region": region_folder.name,
        "copied_files": copied,
        "missing_files": missing,
        "copied_maps": maps_copied,
        "output_folder": str(output_folder)
    }
    
    progress_callback(f"  | ✅ MPQ data converted to CASC format")
    
    return result