import shutil
from pathlib import Path
from zipfile import ZipFile
import os
import re
import logging
from datetime import datetime

# Import translator functions directly
from __Misc_Tools.campaignstrings_translator.campaign_strings_translator import *
from __Misc_Tools.worldeditor_translator.worldeditor_translator import *
from __Misc_Tools.wc3keys_translater.wc3keys_translater import *

def build_patch_for_region(progress_callback, mpq_to_casc_path):
    """Create patch for a single region with enhanced region code handling"""
    try:
        # Convert to Path object and get base directory
        MPQ_DATA_TO_CASC = Path(mpq_to_casc_path)
        base_dir = MPQ_DATA_TO_CASC.parent.parent

        # Define key paths
        MPQ_DATA = base_dir / "MPQ_Data"
        CASC_DATA = base_dir / "CASC_Data"
        HOMEMADE_DATA = base_dir / "_HomeMade_Data"
        MERGED = base_dir / "merged"
     
        # Ensure directories exist
        required_dirs = [MPQ_DATA, CASC_DATA, HOMEMADE_DATA, MERGED]
        for directory in required_dirs:
            directory.mkdir(exist_ok=True)

        if not directory.exists():
            progress_callback("  | ⛔ Missing required directories:")
            progress_callback(f"  |   | ℹ️ Creating: {directory}")

        # Set working directory to base_dir
        os.chdir(base_dir)

        # Extract region code from path (in aaBB format)
        region_code = extract_region_code(MPQ_DATA_TO_CASC, progress_callback)
        if not region_code:
            return False
        
        # Create region-specific patch folder
        region_patch_folder = MERGED / f"{region_code}_patch"
        region_patch_folder.mkdir(exist_ok=True)
        
        # Step 1: Copy MPQ_converted_to_CASC data (excluding sound)
        copy_contents(
            MPQ_DATA_TO_CASC, region_patch_folder, 
            skip_sound=True, 
            label=f"  | 📝 Copying MPQ_to_CASC files ...",
            progress_callback=progress_callback
        )
        
        # Step 2: Copy CASC data (including sound, excluding maps)
        casc_region_folder = CASC_DATA / f"{region_code}.w3mod"
        if casc_region_folder.exists() and casc_region_folder.is_dir():
            copy_contents(
                casc_region_folder, region_patch_folder, 
                skip_w3x=True, 
                label=f"  | 📝 Copying CASC files ...",
                progress_callback=progress_callback
            )
        else:
            progress_callback(f"  | ⚠️ CASC data not found for {region_code} at: {casc_region_folder}")
            progress_callback("  | ℹ️ Proceeding without CASC data...")

        
        # Step 3: Copy MPQ_converted_to_CASC sound files (to override CASC)
        copy_contents(
            MPQ_DATA_TO_CASC, region_patch_folder, 
            only_sound=True, 
            label=f"  | 🔊 Overriding Sound with MPQ's for ({region_code})",
            progress_callback=progress_callback
        )
        
        # Step 4: Apply homemade overrides
        homemade_folder = find_homemade_folder(region_code, HOMEMADE_DATA)
        if homemade_folder:
            copy_contents(
                homemade_folder, region_patch_folder, 
                label=f"HomeMade ({region_code})",
                progress_callback=progress_callback
            )
        else:
            progress_callback(f"  | ℹ️ No HomeMade data found for {region_code}")
        
        # Step 5: Clean unnecessary files
        clean_folder(region_patch_folder, progress_callback)
                
        # Step 7: Process world editor UI files
        run_worldeditor_translator(region_patch_folder, region_code, base_dir, progress_callback)

        # New Step 8: Translate globalstrings.fdf
        try:
            progress_callback("  | 🔤 Translating globalstrings.fdf...")
            
            # Path to the English template
            english_fdf_template = base_dir / "__Misc_Tools" / "wc3keys_translater" / "globalstrings_template.fdf"
            
            # Path to the language-specific FDF in the patch
            language_fdf = region_patch_folder / "ui" / "framedef" / "globalstrings.fdf"
            
            # Only process if both files exist
            if english_fdf_template.exists() and language_fdf.exists():
              
                # Perform the translation
                translate_fdf(
                    english_fdf_template_path=english_fdf_template,
                    language_fdf_path=language_fdf,
                    output_path=language_fdf  # overwrite the original
                )
                progress_callback("  | ✅ Translated globalstrings.fdf")
            else:
                if not english_fdf_template.exists():
                    progress_callback(f"  | ⚠️ English template not found: {english_fdf_template}")
                if not language_fdf.exists():
                    progress_callback(f"  | ⚠️ Language FDF not found: {language_fdf}")
        except Exception as e:
            progress_callback(f"  | ❌ Error translating globalstrings.fdf: {str(e)}")

        # Step 9 Deleted the "converted-to-CASC" folder
        shutil.rmtree(MPQ_DATA_TO_CASC)
        progress_callback(f"  | ✅ Removed temporary folder: {MPQ_DATA_TO_CASC.name}")

        # Step 10: Package final patch
        zip_and_remove(region_patch_folder, progress_callback)
        
        progress_callback(f"✅ Successfully created patch for: {region_code}")
        return True
        
    except Exception as e:
        progress_callback(f"  | ⛔ Critical error creating patch: {str(e)}")
        logging.exception("Patch creation failed")
        return False

def extract_region_code(MPQ_DATA_TO_CASC, progress_callback):
    """Extract region code from MPQ folder path in aaBB format"""
    pattern = r"[\\/]([a-zA-Z]{4})[-_]"
    match = re.search(pattern, str(MPQ_DATA_TO_CASC))
    
    if match:
        region_code = match.group(1)
        return region_code
    else:
        progress_callback(f"  | ⚠️ Could not extract region code from: {MPQ_DATA_TO_CASC}")
        return None

def skip_w3m_w3x_folder(path: Path):
    """Check if path should be skipped as map folder"""
    return any(part.endswith((".w3x", ".w3m")) for part in path.parts)

def copy_contents(src_dir, dest_dir, skip_w3x=False, skip_sound=False, 
                 only_sound=False, label="Copying", progress_callback=None):
    """Copy files with detailed progress reporting"""
    if not progress_callback:
        progress_callback = print
    
    # Check if source directory exists
    if not src_dir.exists() or not src_dir.is_dir():
        progress_callback(f"  | ⚠️ Source directory not found: {src_dir}")
        return
    
    # Prepare file list
    all_files = list(src_dir.rglob("*"))
    if not all_files:
        progress_callback(f"  | ⚠️ No files found in: {src_dir}")
        return
        
    total_files = len(all_files)
    processed = 0
    copied_count = 0
    skipped_count = 0
    
    for item in all_files:
        if item.is_dir():
            continue
            
        rel_path = item.relative_to(src_dir)
        dest_path = dest_dir / rel_path

        # Apply skip/only filters
        skip = False
        if skip_sound and 'sound' in rel_path.parts:
            skip = True
        elif only_sound and 'sound' not in rel_path.parts:
            skip = True
        elif skip_w3x and skip_w3m_w3x_folder(rel_path):
            skip = True

        if skip:
            skipped_count += 1
            processed += 1
            continue

        try:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest_path)
            copied_count += 1
            processed += 1
            
            # Update progress periodically
            if processed % 50 == 0 or processed == total_files:
                progress = f"{label}: {processed}/{total_files} ({int(processed/total_files*100)}%)"
                progress_callback(progress)
                
        except Exception as e:
            progress_callback(f"  - ⚠️ Error copying {item}: {str(e)}")
    
    # sleep(1.0)
    # progress_callback(f"  - ✅ Completed {label} - Copied: {copied_count}, Skipped: {skipped_count}")

def clean_folder(folder_path, progress_callback):
    """Clean unnecessary files and folders"""
    if not folder_path.exists():
        return
    
    progress_callback(f"  | 🧹 Cleaning temporary folder: {folder_path.name}")
    
    allowed_dirs = {"maps", "movies", "sound", "ui", "units", "campaign", "fonts"}
    allowed_files = {"war3patch.txt"}
    
    removed_dirs = 0
    removed_files = 0
    
    for item in folder_path.iterdir():
        name = item.name
        keep = name in allowed_dirs or name in allowed_files
        
        if not keep:
            try:
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                    removed_dirs += 1
                    progress_callback(f"  |   |  🗑️ Removed directory: {name}")
                else:
                    item.unlink()
                    removed_files += 1
            except Exception as e:
                progress_callback(f"  | ⚠️ Error removing {name}: {str(e)}")
    
    progress_callback(f"  | 🧹 Cleanup complete | Dirs: {removed_dirs}, Files: {removed_files}")

def zip_and_remove(folder_path, progress_callback):

    """Create zip archive and remove original folder"""
    if not folder_path.exists():
        progress_callback(f"  | ⚠️ Nothing to zip: {folder_path} not found")
        return
        
    zip_path = folder_path.with_suffix(".zip")
    
    # Check if zip already exists
    if zip_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = zip_path.with_name(f"{zip_path.stem}_{timestamp}.zip")
    
    progress_callback(f"  | 📦 Creating archive: {zip_path.name}")
    
    all_files = list(folder_path.rglob("*"))
    if not all_files:
        progress_callback("  | ⚠️ Nothing to zip | folder is empty")
        return
        
    total_files = len(all_files)
    processed = 0
    
    try:
        with ZipFile(zip_path, 'w') as zipf:
            for file in all_files:
                if file.is_file():
                    arcname = file.relative_to(folder_path)
                    zipf.write(file, arcname)
                    processed += 1
                    
                    if processed % 50 == 0 or processed == total_files:
                        progress = f"  |   |   Zipping: {processed}/{total_files} ({int(processed/total_files*100)}%)"
                        progress_callback(progress)
        
        # Verify zip creation
        if zip_path.stat().st_size == 0:
            progress_callback("⛔ Created zip file is empty!")
            zip_path.unlink()
            return
            
        # Remove original folder
        try:
            shutil.rmtree(folder_path)
            progress_callback(f"  | ✅ Removed temporary folder: {folder_path.name}")
        except Exception as e:
            progress_callback(f"  | ⚠️ Error removing temp folder: {str(e)}")

        progress_callback(f"  | 📦 Archive created: {Path(zip_path).name} ({zip_path.stat().st_size//1024} KB)")
            
    except Exception as e:
        progress_callback(f"  | ⛔ Zip creation failed: {str(e)}")

def find_homemade_folder(region_code, HOMEMADE_DATA):
    """Find matching homemade folder with case-insensitive search"""
    if not HOMEMADE_DATA.exists():
        return None
        
    region_lower = region_code.lower()
    for folder in HOMEMADE_DATA.iterdir():
        if folder.is_dir():
            folder_name_lower = folder.name.lower()
            if folder_name_lower.startswith(region_lower):
                return folder
    return None

def handle_campaign_strings(casc_region_folder, patch_folder, region_code, base_dir, progress_callback):
    """Convert campaignstrings.txt files if needed"""
    # Define paths to campaign string files
    casc_campaignstrings = casc_region_folder / "ui" / "campaignstrings.txt"
    casc_campaignstrings_exp = casc_region_folder / "ui" / "campaignstrings_exp.txt"
    patch_campaignstrings = patch_folder / "ui" / "campaignstrings.txt"
    patch_campaignstrings_exp = patch_folder / "ui" / "campaignstrings_exp.txt"
    
    # Get template path
    template_file = base_dir / "__Misc_Tools" / "campaignstrings_translator" / "template_1.31.txt"
    
    # Ensure template exists
    if not template_file.exists():
        progress_callback(f"❌ Error: Template file not found at {template_file}")
        return
    
    # Process base campaign strings if it doesn't exist in CASC
    if not casc_campaignstrings.exists():
        if patch_campaignstrings.exists():
            # Create backup
            backup_file = f"{patch_campaignstrings}.bak"
            shutil.copy2(patch_campaignstrings, backup_file)
            progress_callback(f"Created backup: {backup_file}")
            
            # Convert campaign strings
            progress_callback(f"Converting campaign strings for {region_code}")
            convert_campaign_strings(
                str(template_file), 
                str(patch_campaignstrings),
                progress_callback
            )
            progress_callback(f"✅ Converted campaign strings for {region_code}")
        else:
            progress_callback(f"⚠️ Warning: No campaignstrings.txt found in CASC or patch for {region_code}")
    else:
        progress_callback("ℹ️ Using CASC campaignstrings.txt - no conversion needed")
    
    # Process expansion campaign strings if it doesn't exist in CASC
    if not casc_campaignstrings_exp.exists():
        if patch_campaignstrings_exp.exists():
            # Create backup
            backup_file_exp = f"{patch_campaignstrings_exp}.bak"
            shutil.copy2(patch_campaignstrings_exp, backup_file_exp)
            progress_callback(f"Created backup: {backup_file_exp}")
            
            # Convert expansion campaign strings
            progress_callback(f"Converting expansion campaign strings for {region_code}")
            convert_campaign_strings(
                str(template_file), 
                str(patch_campaignstrings_exp),
                progress_callback
            )
            progress_callback(f"✅ Converted expansion campaign strings for {region_code}")
        else:
            progress_callback(f"⚠️ Warning: No campaignstrings_exp.txt found in CASC or patch for {region_code}")
    else:
        progress_callback("ℹ️ Using CASC campaignstrings_exp.txt - no conversion needed")

def run_worldeditor_translator(region_patch_folder, region_code, base_dir, progress_callback):
    """Run worldeditor translator on UI files with single translator initialization"""
    template_dir = base_dir / "__Misc_Tools" / "worldeditor_translator"
    
    # Files to process
    ui_files = [
        ("worldeditgamestrings_template.txt", "worldeditgamestrings.txt"),
        ("worldeditstrings_template.txt", "worldeditstrings.txt")
    ]
    
    ui_folder = region_patch_folder / "ui"
    if not ui_folder.exists():
        progress_callback(f"  | ⚠️ UI folder not found: {ui_folder}")
        return
    
    # Create translator instance for this region
    translator = WorldEditorTranslator(region_code, progress_callback)
    
    for template_file, target_file in ui_files:
        ui_file_path = ui_folder / target_file
        template_path = template_dir / template_file
        
        # Validate files exist
        if not template_path.exists():
            progress_callback(f"  | ⚠️ Template file not found: {template_path}")
            continue
            
        if not ui_file_path.exists():
            progress_callback(f"  | ⚠️ Target file not found: {ui_file_path}")
            continue
            
        try:
            # Process file using translator instance
            progress_callback(f"  | 🌍 Translating {target_file} for {region_code}")
            translator.process_file(
                str(template_path), 
                str(ui_file_path)
            )
            progress_callback(f"  | ✅ Translated {target_file} for {region_code}")
        except Exception as e:
            progress_callback(f"  | ⛔ Failed to translate {target_file}: {str(e)}")