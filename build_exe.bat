@echo off
REM Builds dist\WC3LanguagePatcher\WC3LanguagePatcher.exe and a release zip.
REM Requires Python 3.12 (64-bit) on PATH as "py -3.12".
setlocal
cd /d "%~dp0"
if not exist .venv (
    py -3.12 -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat || goto :error
python -m pip install --upgrade pip || goto :error
python -m pip install -r requirements-dev.txt || goto :error
python tools\build_translation_cache.py check || goto :error
python -m PyInstaller --noconfirm wc3_language_patcher.spec || goto :error
REM ship MPQ_Data, CASC_Data and merged with their placeholder.txt
python -c "import app_paths; app_paths.ensure_workspace_folders(r'dist\WC3LanguagePatcher')" || goto :error
powershell -NoProfile -Command "Compress-Archive -Force -Path 'dist\WC3LanguagePatcher' -DestinationPath 'dist\WC3LanguagePatcher-windows.zip'" || goto :error
echo.
echo Done: dist\WC3LanguagePatcher-windows.zip
exit /b 0
:error
echo Build failed.
exit /b 1
