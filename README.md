# WarCraft 3 Legacy Voice & Localization Patcher  
_Restore original voices and texts in modern WC3 versions (1.30+)_
<img width="2000" height="601" alt="Comp 2_00000" src="https://github.com/user-attachments/assets/1ba6303e-2257-4189-ab41-17715a30a6c7" />

---

## Why This Tool?

🗣️ **Restore Classic Voices:** Replaces Reforged’s controversial voice lines with original MPQ-era audio  
🌍 **Preserve Lost Localizations:** Rescues translations from pre-1.30 versions no longer available  
🧩 **Hybrid Game Experience:** Mixes classic voices with modern gameplay  
⚙️ **Campaign Fixes:** Includes critical fixes for broken maps like the infamous “The Purge” mission  

https://github.com/user-attachments/assets/a23cb941-a369-4feb-b027-e22366cd5baf

---

## Youtube Presentation of this Project (dubbed in English and French)
[![Comment j’ai empêché Warcraft 3 de devenir un Lost Media](https://img.youtube.com/vi/pX56LJcSL8Y/maxresdefault.jpg)](https://youtu.be/pX56LJcSL8Y)
- [Click this link or the picture to watch the video](https://youtu.be/pX56LJcSL8Y) 

## Setup Guide

### Highly recommended tools for everyone
(⚠️ Your browser might warn you because these two websites are http)
- [MPQ Editor](http://www.zezula.net/en/mpq/download.html)
- [CASCView](http://www.zezula.net/en/casc/main.html)

### Build from Source
1. **Install Python**
   - Download and install [Python 3.10 or higher](https://www.python.org/downloads/)
   - During installation, check "Add Python to PATH"
2. **Install Requirements**
   - ```pip install -r requirements.txt```
   
3. **Prepare UI Engine**
  Place [OpenGLWorldEditor.py](https://github.com/MashiroW/openGL-WorldEditor/blob/main/OpenGLWorldEditor.py) in the project root.

## Project Structure
```
War3-Legacy-Patcher/
├── MPQ_Data/                     # Source MPQ language data
│   ├── [REGION_CODE]/            # e.g. frFR-MPQ, esES-MPQ
│   │   ├── War3.mpq/             # Extracted game assets
│   │   ├── War3x.mpq/            # Patch assets
│   │   ├── War3xlocal.mpq/       # Localized expansion assets
├── CASC_Data/                    # Target CASC language data
│   ├── [REGION_CODE]/.w3mod/     # e.g. enUS.w3mod, frFR.w3mod
│   │   ├── abilities/            # Game abilities
│   │   ├── sound/                # Voice lines
│   │   └── ...                   # Other game assets
├── _HomeMade_Data/               # Custom fixes & additions
│   ├── [REGION_CODE]/            # Region-specific overrides
│   │   ├── Maps/                 # Fixed campaign maps
│   │   ├── Movies/               # Converted cutscene audio
├── merged/                       # Output patch zips
│   ├── [REGION_CODE]_patch.zip   # Final patch archive
│   ├── LANGUAGE_CHANGER.bat      # Final installer
└── OpenGLWorldEditor.py          # 3D UI engine (required)
```

## Usage Guide
### Step 1: Add Language Sources
1. Launch patcher
2. Select language code (e.g. `frFR`, `esES`)
3. Click to create template folders

### Step 2: Prepare MPQ Data (Source of your localization files)
Extract these from pre-1.30 WC3:
- `war3.mpq` → `./MPQ_Data/[REGION]/MPQ/War3.mpq`
- `War3Patch.mpq` → `./MPQ_Data/[REGION]/MPQ/War3Patch.mpq`
- `War3x.mpq` → `./MPQ_Data/[REGION]/MPQ/War3x.mpq`
- `War3xlocal.mpq` → `./MPQ_Data/[REGION]/MPQ/War3xlocal.mpq`

### Step 3: Prepare CASC Data (Optional)
From modern WC3 (1.30+):
1. Find either:
    - Direct: `enUS.w3mod`
    - Nested: `war3.w3mod/Locales/enUS.w3mod`
2. Then copy to `CASC_Data/[REGION]/.w3mod/`

### Step 4: Add Custom Content
Place in `_HomeMade_Data/[REGION]/`:
- Converted cutscenes MP3s in Movies/ (convert with VLC)
- Fixed campaign maps, e.g. maps/campaign/human06.w3m (Mal'Ganis AI fix)

### Step 5: Build & Apply Patch
1. Click **Build Patch**
2. Copy from `merged/`:
   * `[REGION]_Patch.zip`
   * `LANGUAGE_CHANGER.bat`
3. Place these in your Warcraft III installation:
   * **Reforged (v1.32+):** place in `[WC3 Folder]/_retail_/`

## Important Notes
* **Map Locations:**
  * MPQ version’s balancing → `/Maps/[LANGUAGE]/Maps Patch/`
  * CASC version’s balancing → `/Maps/`
* **Avoid Spoilers:** Don’t launch campaign maps from menu

## Troubleshooting
**Mal’Ganis won’t attack:** Use fixed `human06.w3m` from `_HomeMade_Data/`  
**Cutscene audio missing:** Verify MP3s in `Movies/` folder  
**UI not loading:** Ensure `OpenGLWorldEditor.py` is in root

# Technical Details (for the nerds)

A significant amount of reverse engineering was required throughout this project.

This includes in-depth analysis of the structure of the game's files—both MPQ and CASC formats. MPQ archives often contain duplicated or overlapping files, making it difficult to track authoritative data. CASC, on the other hand, is a much more modern and complex format. Unlike MPQ, CASC allows files to be referenced that may not physically exist on disk, and its internal structure has changed between different game versions, requiring careful adaptation and version-aware handling.

Reverse engineering was also done to locate and understand how the game's localizations are stored. Unlike many other games, Warcraft III fragments its localization files heavily. Many dialogue lines are embedded directly in map files rather than in centralized text files. This made it necessary to scan map archives and extract scattered strings manually.

Regarding maps, we investigated the differences between .w3m and .w3x formats and also analyzed the structure of maps exported from the World Editor when saved in decomposed formats. These generate numerous files like war3map.w3e, war3map.wtg, war3map.wct, war3map.j, war3map.wts, war3mapUnits.doo, and more. Understanding their purpose and interaction required thorough binary analysis.

Notably, I had never worked with the code side of the Warcraft III World Editor before this project. Significant reverse engineering was required to understand how it compiles and handles AI scripts and triggers.

For example, the campaign map The Purge was broken due to deprecated AI scripting related to Mal'Ganis. Fixing this involved manually identifying legacy syntax that recent versions of the World Editor compiler no longer support, and restructuring the code accordingly.

On the localization side, reverse engineering was also necessary because new keys and variables have been added over the years across patches, while others have been removed (especially those used by the World Editor UI). To handle these inconsistencies, I used Machine Learning models (such as some from HuggingFace like MarianMT and M2M100) to automatically translate newly added strings into the target language while keeping formatting and context intact.

Additionally, the internal file structure used for campaign and menu localization has changed across versions. This meant that older configuration formats had to be converted into newer formats compatible with the latest game builds—another aspect that required careful inspection and tooling.

## Credits
- MPQ Editor & CASCView by Ladislav Zeluza
- The 2003 Blizzard Entertainment team for Warcraft III

> "The dead shall serve me now... in *proper* audio quality!"
> -Kel'Thuzad

Happy patching! 🧙‍♂️🎧
