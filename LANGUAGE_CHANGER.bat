@echo off
setlocal ENABLEEXTENSIONS
color 0A

:: Always work in the folder of this .bat (when started "as administrator",
:: Windows starts it in C:\Windows\System32 instead)
cd /d "%~dp0"

:: The game folder must be writable (e.g. installed under Program Files):
:: if not, restart this script elevated, in the same folder
set "probe=%~dp0.write_test.tmp"
(echo test> "%probe%") 2>nul
if not exist "%probe%" (
    echo This folder is not writable, asking for administrator rights...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -WorkingDirectory '%~dp0' -Verb RunAs"
    exit /b
)
del "%probe%" >nul 2>&1

echo === Warcraft III Language Patch Switcher ===
echo.
echo Select your language/region:
echo [1] English (enUS)
echo [2] French (frFR)
echo [3] German (deDE)
echo [4] Spanish (esES)
echo [5] Russian (ruRU)
echo [6] Korean (koKR)
echo [7] Chinese Traditional (zhTW)
echo [8] Polish (plPL)
echo [9] Italian (itIT)
echo [10] Czech (csCZ)
set /p langChoice=Enter a number (1-10):

:: Default to English
set "lang=enUS"

if "%langChoice%"=="1" set "lang=enUS"
if "%langChoice%"=="2" set "lang=frFR"
if "%langChoice%"=="3" set "lang=deDE"
if "%langChoice%"=="4" set "lang=esES"
if "%langChoice%"=="5" set "lang=ruRU"
if "%langChoice%"=="6" set "lang=koKR"
if "%langChoice%"=="7" set "lang=zhTW"
if "%langChoice%"=="8" set "lang=plPL"
if "%langChoice%"=="9" set "lang=itIT"
if "%langChoice%"=="10" set "lang=csCZ"

set "basePatch=enUS_patch.zip"
set "regionPatch=%lang%_patch.zip"

echo.
echo Checking patches in: %CD%
if not exist "%basePatch%" (
    echo Error: %basePatch% not found in this folder.
    echo Put LANGUAGE_CHANGER.bat and the *_patch.zip files in the Warcraft III root folder.
    goto :end
)
if not "%lang%"=="enUS" if not exist "%regionPatch%" (
    echo Error: %regionPatch% not found in this folder.
    goto :end
)

echo.
echo Removing old Warcraft III folders...

for %%D in (_balance abilities buildings campaign custom_v0 custom_v1 doodads fonts maps melee_v0 movies sound ui units) do (
    if exist "%%D" (
        echo Deleting %%D...
        rmdir /s /q "%%D"
    ) else (
        echo Skipping %%D (not found^)
    )
)

echo.
echo Extracting base English patch...
powershell -NoProfile -Command "Expand-Archive -Force -LiteralPath '%CD%\%basePatch%' -DestinationPath '%CD%'"
if %errorlevel% neq 0 (
    echo Error during English patch extraction.
    goto :end
)

:: Apply region override if it's not English
if not "%lang%"=="enUS" (
    echo.
    echo Extracting region override patch: %regionPatch%...
    powershell -NoProfile -Command "Expand-Archive -Force -LiteralPath '%CD%\%regionPatch%' -DestinationPath '%CD%'"
    if errorlevel 1 (
        echo Error during %lang% patch extraction.
        goto :end
    )
)

echo.
echo Enabling 'Allow Local Files' and setting the language in the registry...
set "regOK=1"
reg add "HKCU\Software\Blizzard Entertainment\Warcraft III" /v "Allow Local Files" /t REG_DWORD /d 1 /f >nul 2>&1 || set "regOK=0"
reg add "HKCU\Software\Blizzard Entertainment\Warcraft III" /v "Locale" /t REG_SZ /d %lang% /f >nul 2>&1 || set "regOK=0"
reg add "HKCU\Software\Blizzard Entertainment\Classic Launcher\w3" /v "Locale" /t REG_SZ /d %lang% /f >nul 2>&1 || set "regOK=0"
reg add "HKCU\Software\Blizzard Entertainment\Classic Launcher\w3" /v "Region" /t REG_SZ /d EU /f >nul 2>&1 || set "regOK=0"
if "%regOK%"=="0" (
    echo reg.exe was refused, trying with PowerShell...
    powershell -NoProfile -Command ^
      "$a='HKCU:\Software\Blizzard Entertainment\Warcraft III'; $b='HKCU:\Software\Blizzard Entertainment\Classic Launcher\w3';" ^
      "New-Item -Path $a -Force | Out-Null; New-Item -Path $b -Force | Out-Null;" ^
      "New-ItemProperty -Path $a -Name 'Allow Local Files' -PropertyType DWord -Value 1 -Force | Out-Null;" ^
      "New-ItemProperty -Path $a -Name 'Locale' -PropertyType String -Value '%lang%' -Force | Out-Null;" ^
      "New-ItemProperty -Path $b -Name 'Locale' -PropertyType String -Value '%lang%' -Force | Out-Null;" ^
      "New-ItemProperty -Path $b -Name 'Region' -PropertyType String -Value 'EU' -Force | Out-Null"
)

:: The Classic launcher also reads the language from Launcher.db (4 bytes, e.g. frFR)
powershell -NoProfile -Command "[IO.File]::WriteAllText('%CD%\Launcher.db', '%lang%')" >nul 2>&1

echo.
echo Cleaning up leftover folders in .\ui\framedef...
if exist ".\ui\framedef\glue" (
    echo Deleting .\ui\framedef\glue
    rmdir /s /q ".\ui\framedef\glue"
)
if exist ".\ui\framedef\ui" (
    echo Deleting .\ui\framedef\ui
    rmdir /s /q ".\ui\framedef\ui"
)

echo.
echo Checking the registry:
reg query "HKCU\Software\Blizzard Entertainment\Warcraft III" /v "Allow Local Files" 2>nul | findstr /i "Allow" || echo   ERROR: 'Allow Local Files' is not set
reg query "HKCU\Software\Blizzard Entertainment\Warcraft III" /v "Locale" 2>nul | findstr /i "%lang%" || echo   ERROR: Warcraft III 'Locale' is not %lang%
reg query "HKCU\Software\Blizzard Entertainment\Classic Launcher\w3" /v "Locale" 2>nul | findstr /i "%lang%" || echo   ERROR: Classic Launcher 'Locale' is not %lang%
echo   Launcher.db: & type Launcher.db & echo.

echo.
echo === Patch applied successfully for %lang%! ===
echo.
echo ===============================================================================
echo ^|                                                                            ^|
echo ^|  Reverse Engineering, Data collection and repacking by Mashiro             ^|
echo ^|                                                                            ^|
echo ^|  Discord:   https://discord.com/invite/nqcnrWwF35                          ^|
echo ^|  Youtube:   https://www.youtube.com/channel/UCshPTJuIwm_Ld8GhIg_rbjg       ^|
echo ^|  Secondary: https://www.youtube.com/@MashMash/videos                       ^|
echo ^|  Instagram: https://www.instagram.com/nrg_mash/                            ^|
echo ^|  TikTok:    https://www.tiktok.com/@_mashiro                               ^|
echo ^|                                                                            ^|
echo ^|  I hate media getting lost. This took a few full days to complete.         ^|
echo ^|  Thanks to everyone on HiveWorkshop and Reddit for preserving and sharing  ^|
echo ^|  files and info. This repack wouldn't be possible without you.             ^|
echo ^|                                                                            ^|
echo ^|  Enjoy your game - may this help preserve a masterpiece's legacy.          ^|
echo ===============================================================================

:end
echo.
pause
