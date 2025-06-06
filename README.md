# WarCraft 3 Legacy Voice & Localization Patcher  
*Restore original voices and texts in modern WC3 versions (1.30+)*  

## Why This Tool?  
- 🗣️ **Restore Classic Voices**: Replaces Reforged's controversial voice lines with original MPQ-era audio  
- 🌍 **Preserve Lost Localizations**: Rescues translations from pre-1.30 versions no longer available  
- 🧩 **Hybrid Game Experience**: Mixes classic voices with modern gameplay  
- ⚙️ **Campaign Fixes**: Includes critical fixes for broken maps like the infamous "The Purge" mission

https://github.com/user-attachments/assets/90b132c0-647a-48bd-b335-416470b41c62

## Setup Guide  
### Highly recommended tools for everyone  
1. **Get Required Tools**  
- [MPQ Editor](https://www.zezula.net/en/mpq/download.html)  (⚠️Your browser might warn you because this website is http)
- [CASC View](http://www.zezula.net/en/casc/main.html)
  
### Build from Source  
1. **Install Requirements**  
`pip install -r requirements.txt`  

2. **Prepare UI Engine**  
Place [OpenGLWorldEditor.py](https://github.com/MashiroW/openGL-WorldEditor/blob/main/OpenGLWorldEditor.py) in project root  

## Project Structure  
```
War3-Legacy-Patcher/
├── MPQ_Data/            # Source MPQ language data
│   └── [REGION_CODE]-MPQ/  # e.g. frFR-MPQ, esES-MPQ
│       ├── war3.mpq/        # Extracted game assets
│       ├── War3Patch.mpq/   # Patch assets
│       ├── War3x.mpq/       # TFT expansion assets
│       └── War3xlocal.mpq/  # Localized expansion assets
├── CASC_Data/           # Target CASC language data
│   └── [REGION_CODE].w3mod/  # e.g. enus.w3mod, frfr.w3mod
│       ├── abilities/       # Game abilities
│       ├── sound/           # Voice lines
│       └── ...              # Other game assets
├── _HomeMade_Data/      # Custom fixes & additions
│   ├── [REGION_CODE]/       # Region-specific overrides
│   │   ├── maps/            # Fixed campaign maps
│   │   └── Movies/          # Converted cutscene audio
│   └── ...                  
├── merged/              # Output patch zips
│   ├── [REGION_CODE]_path.zip # The final patch archive
│   └── LANGUAGE_CHANGER.bat # Final installer
└── OpenGLWorldEditor.py # 3D UI Engine (required)
```

## Usage Guide  
### Step 1: Add Language Sources  
1. Launch patcher  
2. Select language code (e.g. `frFR`, `esES`)  
3. Click `+` to create template folders  

### Step 2: Prepare MPQ Data (Source of your localization files)  
Extract these from pre-1.30 WC3:  
- `war3.mpq` → `./MPQ_Data/[REGION]-MPQ/war3.mpq/`  
- `War3Patch.mpq` → `./MPQ_Data/[REGION]-MPQ/War3Patch.mpq/`  
- `War3x.mpq` → `./MPQ_Data/[REGION]-MPQ/War3x.mpq/`  
- `War3xlocal.mpq` → `./MPQ_Data/[REGION]-MPQ/War3xlocal.mpq/`  

### Step 3: Prepare CASC Data (Optional)  
From modern WC3 (1.30+):  
1. Find either:  
   - Direct: `enus.w3mod`  
   - Nested: `war3.war3mod/_locales/enus.w3mod`  
2. Copy to `CASC_Data/[REGION].w3mod/`  

### Step 4: Add Custom Content  
Place in `_HomeMade_Data/[REGION]/`:  
- **Converted Cutscenes**: MP3s in `Movies/` (convert with VLC)  
- **Fixed Campaign Maps**: e.g. `maps/campaign/human06.w3m` (with Mal'Ganis AI fix)  

### Step 5: Build & Apply Patch  
1. Click `Build Patch`  
2. Copy from `merged/`:  
   - `[REGION]_Patch.zip`  
   - `LANGUAGE_CHANGER.bat`  
3. Place these in your Warcraft III installation:  
   - **Reforged (v1.32+)**: Place in `[WC3 Folder]/_retail_/`  
   - **Legacy CASC (v1.30-v1.31)**: Place in `[WC3 Folder]/`  
4. Run `LANGUAGE_CHANGER.bat` and select language  

## Important Notes  
- **Map Locations**:  
  - MPQ version's balancing: `./Maps/[LANGUAGE] Maps Patch/`  
  - CASC version's balancing: `./Maps/`  
- **Avoid Spoilers**: Don't launch campaign maps from menu!  

## Troubleshooting  
**Mal'Ganis won't attack**: Use fixed `human06.w3m` from `_HomeMade_Data`  
**Cutscene audio missing**: Verify MP3 files in `Movies/` folder  
**UI not loading**: Ensure `OpenGLWorldEditor.py` is in root  

# Technical Details (for the nerds)
A significant amount of reverse engineering was required throughout this project.

This includes in-depth analysis of the structure of the game's files—both MPQ and CASC formats. MPQ archives often contain duplicated or overlapping files, making it difficult to track authoritative data. CASC, on the other hand, is a much more modern and complex format. Unlike MPQ, CASC allows files to be referenced that may not physically exist on disk, and its internal structure has changed between different game versions, requiring careful adaptation and version-aware handling.

Reverse engineering was also done to locate and understand how the game's localizations are stored. Unlike many other games, Warcraft III fragments its localization files heavily. Many dialogue lines are embedded directly in map files rather than in centralized text files. This made it necessary to scan map archives and extract scattered strings manually.

Regarding maps, I investigated the differences between .w3m and .w3x formats and also analyzed the structure of maps exported from the World Editor when saved in decomposed formats. These generate numerous files like war3map.w3e, war3map.wtg, war3map.wct, war3map.j, war3map.wts, and more.

Notably, I had never worked with the code side of the Warcraft III World Editor before this project. Significant reverse engineering was required to understand how it compiles and handles AI scripts and triggers.

For example, the campaign map The Purge was broken due to deprecated JASS AI scripting related to Mal'Ganis. Fixing this involved manually identifying legacy syntax that recent versions of the World Editor compiler no longer support, and restructuring the code accordingly.

On the localization side, reverse engineering was also necessary because new keys and variables have been added over the years across patches, while others have been removed (especially those used by the World Editor UI). To handle these inconsistencies, I used Machine Learning models (such as some from HuggingFace) to automatically translate newly added strings into the target language while keeping formatting and context intact.

Additionally, the internal file structure used for campaign and menu localization has changed across versions. This meant that older configuration formats had to be converted into newer formats compatible with the latest game builds—another aspect that required careful inspection and tooling.

## Credits  
- MPQ Editor & CASC Viewer by Ladislav Zezula  
- The 2003 Blizzard Entertainment team for Warcraft III  

> "The dead shall serve me now... in *proper* audio quality!"  
> – Kel'Thuzad  

**Happy patching!** 🧙‍♂️🎧
