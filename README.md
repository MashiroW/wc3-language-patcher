# WarCraft 3 Legacy Voice & Localization Patcher  
_Restore original voices and texts in modern WC3 versions (1.30+)_
![Comp 2_00000](https://github.com/user-attachments/assets/1ba6303e-2257-4189-ab41-17715a30a6c7)

[![Version](https://img.shields.io/badge/version-1.0-2ea44f?style=for-the-badge)](https://github.com/MashiroW/wc3-language-patcher/releases/latest) [![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=data:image/svg%2bxml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0wIDBoMTF2MTFIMHpNMTMgMGgxMXYxMUgxM3pNMCAxM2gxMXYxMUgwek0xMyAxM2gxMXYxMUgxM3oiLz48L3N2Zz4=&logoColor=white)](#) [![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)](#) [![macOS](https://img.shields.io/badge/macOS-000000?style=for-the-badge&logo=apple&logoColor=white)](#) [![Stars](https://img.shields.io/github/stars/MashiroW/wc3-language-patcher?style=for-the-badge&logo=github&color=e3b341)](https://github.com/MashiroW/wc3-language-patcher/stargazers) [![Sponsor](https://img.shields.io/badge/Sponsor-%E2%9D%A4-EA4AAA?style=for-the-badge&logo=githubsponsors&logoColor=white)](https://github.com/sponsors/MashiroW)

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

### Option A: Windows executable (recommended)
1. Download `WC3LanguagePatcher-windows.zip` from the [Releases page](https://github.com/MashiroW/wc3-language-patcher/releases/latest) and unzip it in a short path you can write to (e.g. `C:\WC3LanguagePatcher`).
2. Run `WC3LanguagePatcher.exe`. Nothing else to install: no Python, no MPQ Editor, no API key.

The folders `MPQ_Data`, `CASC_Data` and `merged` next to the executable each contain a `placeholder.txt` explaining what goes inside.

### Option B: run from source (Windows, Linux, macOS)
1. Install Python 3.12 (64-bit).
2. `pip install -r requirements.txt`
3. `python patcher.py`

To build the executable yourself: run `build_exe.bat` (creates `dist/WC3LanguagePatcher-windows.zip`).

### Optional tools
(⚠️ Your browser might warn you because this website is http)
- [MPQ Editor and CASCView](http://www.zezula.net/en/mpq/download.html) are no longer required: the patcher reads 1.27 MPQ archives and modern CASC installs itself. They remain useful to inspect files.

## Usage Guide
### Step 1: Add Language Sources
1. Launch patcher
2. Select language code (e.g. `frFR`, `esES`) and click **+**
3. Pick the Warcraft III **1.27 install of that language** (the folder containing `war3.mpq`).
   It can be changed later with the **Open MPQ** button of the **Source (MPQ)** column, which also shows
   the detected game version (e.g. `Open MPQ (1.27b)`, read from `game.dll`).

### Step 2: MPQ Data (Source of your localization files)
Nothing to do: at build time the `.mpq` archives of the 1.27 folder are read directly, no extraction needed.

Manual alternative (original workflow, still supported): extract these with MPQ Editor:
- `war3.mpq` → `./MPQ_Data/[REGION]/MPQ/War3.mpq`
- `War3Patch.mpq` → `./MPQ_Data/[REGION]/MPQ/War3Patch.mpq`
- `War3x.mpq` → `./MPQ_Data/[REGION]/MPQ/War3x.mpq`
- `War3xlocal.mpq` → `./MPQ_Data/[REGION]/MPQ/War3xlocal.mpq`

### Step 3: Select the Target Version (CASC)
In **Target Version (CASC)**, click **...** and pick the Warcraft III install the patch is for
(1.30+, 1.31 recommended; the folder containing `.build.info` and `Data`). You are asked to confirm it before every build.

At build time the patcher reads the target directly:
- its **original files in the selected language** (those installed locally) override the 1.27 files and are never modified,
- its **English texts** define which strings this exact version expects; strings missing from 1.27 are added with AI translations,
- its file layout is used to place the 1.27 files.

Without a target, the patcher uses `CASC_Data/xxxx.w3mod` (if you filled it) and the bundled 1.31 references.

Manual alternative with CascView, from modern WC3 (1.30+):
1. Find either:
    - Direct: `enUS.w3mod`
    - Nested: `war3.w3mod/Locales/enUS.w3mod`
2. Then copy to `CASC_Data/[REGION]/.w3mod/`

### Missing Strings (translation options)
Strings that did not exist in 1.27 use the bundled AI translations; the few left are translated
online (**Translate online if needed**, on by default, recommended). If you turn it off, choose what
those strings become: the target's English text (safe) or empty (may break some texts).
Original texts (1.27 and target) are always kept.

### Step 4: Custom Content (optional)
The audio of the 9 cinematics is extracted automatically from the 1.27 `Movies` folder.
Anything else can be placed in `_HomeMade_Data/[REGION]/`, e.g. fixed campaign maps such as
`maps/campaign/human06.w3m` (Mal'Ganis AI fix).

### Step 5: Build & Apply Patch
1. Click **BUILD PATCH** and confirm the target version
2. Click **Open output folder (merged)** (the full path is also shown in the console). It contains:
   * `[region]_patch.zip` (e.g. `frfr_patch.zip`)
   * `LANGUAGE_CHANGER.bat`
3. Copy them, with `enus_patch.zip` (the English base), into your Warcraft III installation:
   * **1.30 / 1.31:** the game root folder (next to `Warcraft III.exe`)
   * **Reforged (v1.32+):** `[WC3 Folder]/_retail_/`
4. Run `LANGUAGE_CHANGER.bat` and pick your language. It extracts the patch, enables
   *Allow Local Files* and sets the game language in the registry (it asks for administrator
   rights if the game folder is not writable).

## Important Notes
* **Map Locations:**
  * MPQ version’s balancing → `/Maps/[LANGUAGE] Maps Patch (1.27 backup)/`
  * CASC version’s balancing → `/Maps/`
* **Avoid Spoilers:** Don’t launch campaign maps from menu

## Troubleshooting
**Mal’Ganis won’t attack:** Use fixed `human06.w3m` from `_HomeMade_Data/`  
**Cutscene audio missing:** check that the 1.27 install has its `Movies` folder (9 `.mpq` cinematics)  
**Language not applied in game:** run `LANGUAGE_CHANGER.bat` again and check its *Checking the registry* lines  
**No 3D background:** OpenGL is unavailable on this machine (or the path is too long); the patcher still works normally  
**Something failed:** see `patcher.log` next to the executable, or run `WC3LanguagePatcher.exe --build frFR` to get a log without the window

# Technical Details (for the nerds)

A significant amount of reverse engineering was required throughout this project.

This includes in-depth analysis of the structure of the game's files—both MPQ and CASC formats. MPQ archives often contain duplicated or overlapping files, making it difficult to track authoritative data. CASC, on the other hand, is a much more modern and complex format. Unlike MPQ, CASC allows files to be referenced that may not physically exist on disk, and its internal structure has changed between different game versions, requiring careful adaptation and version-aware handling.

Reverse engineering was also done to locate and understand how the game's localizations are stored. Unlike many other games, Warcraft III fragments its localization files heavily. Many dialogue lines are embedded directly in map files rather than in centralized text files. This made it necessary to scan map archives and extract scattered strings manually.

Regarding maps, we investigated the differences between .w3m and .w3x formats and also analyzed the structure of maps exported from the World Editor when saved in decomposed formats. These generate numerous files like war3map.w3e, war3map.wtg, war3map.wct, war3map.j, war3map.wts, war3mapUnits.doo, and more. Understanding their purpose and interaction required thorough binary analysis.

Notably, I had never worked with the code side of the Warcraft III World Editor before this project. Significant reverse engineering was required to understand how it compiles and handles AI scripts and triggers.

For example, the campaign map The Purge was broken due to deprecated AI scripting related to Mal'Ganis. Fixing this involved manually identifying legacy syntax that recent versions of the World Editor compiler no longer support, and restructuring the code accordingly.

On the localization side, reverse engineering was also necessary because new keys and variables have been added over the years across patches, while others have been removed (especially those used by the World Editor UI). To handle these inconsistencies, the 1,231 strings added after 1.27 (identical for every language) were translated once with context-aware AI translation, using each language's official 1.27 terminology, and are shipped in `translations/`. The patcher therefore needs no online API, no GPU and no large ML model. The few strings left are translated online (on by default, can be turned off in the UI). Maintainers can regenerate or review them with `tools/build_translation_cache.py`.

Additionally, the internal file structure used for campaign and menu localization has changed across versions. This meant that older configuration formats had to be converted into newer formats compatible with the latest game builds—another aspect that required careful inspection and tooling.

## Credits
- MPQ Editor & CASCView by Ladislav Zeluza
- The 2003 Blizzard Entertainment team for Warcraft III

> "The dead shall serve me now... in *proper* audio quality!"
> -Kel'Thuzad

Happy patching! 🧙‍♂️🎧

## License

Copyright (C) 2025-2026 MashiroW

wc3-language-patcher is free software, released under the [GNU General Public License v3.0](LICENSE). You may use, modify and redistribute it, in whole or in part (snippets included), as long as anything you distribute that is based on it is also released under the GPL-3.0 with its source code, and keeps this copyright notice. Third-party assets and libraries included in or used by this project remain under their own licenses.

**Commercial or closed-source use:** if you want to use this project, or any part of it, in a proprietary or closed-source product without the GPL obligations, you need a separate commercial license. Contact me on Discord to get one: https://discord.gg/zZzfEDrqsU
