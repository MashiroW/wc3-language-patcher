@echo off
REM Builds dist\WC3LanguagePatcher\WC3LanguagePatcher.exe and dist\WC3LanguagePatcher-windows.zip.
REM Requires Python 3.12 (64-bit) known to the "py" launcher (python.org, uv...).
REM Everything the build needs or creates (venv, work files) stays in _build\.
setlocal
REM no __pycache__ folders left in the source tree
set PYTHONDONTWRITEBYTECODE=1
cd /d "%~dp0.."
if exist _build\.venv goto :have_venv
call :find_python || goto :error
"%PYEXE%" -m venv _build\.venv || goto :error
:have_venv
call _build\.venv\Scripts\activate.bat || goto :error
python -m pip install --upgrade pip || goto :error
python -m pip install -r _build\requirements-dev.txt || goto :error
python _build\tools\build_translation_cache.py check || goto :error
REM 3D background: separate project, bundled into the exe only
if not exist OpenGLWorldEditor.py (
    echo Downloading OpenGLWorldEditor.py from github.com/MashiroW/openGL-WorldEditor ...
    curl -fsSL -o OpenGLWorldEditor.py https://raw.githubusercontent.com/MashiroW/openGL-WorldEditor/main/OpenGLWorldEditor.py || goto :error
)
python -m PyInstaller --noconfirm --workpath _build\work --distpath dist _build\wc3_language_patcher.spec || goto :error
REM ship MPQ_Data, CASC_Data and merged (placeholders + LANGUAGE_CHANGER.bat)
python -c "import patcher; patcher.create_data_folders(r'dist\WC3LanguagePatcher')" || goto :error
powershell -NoProfile -Command "Compress-Archive -Force -Path 'dist\WC3LanguagePatcher' -DestinationPath 'dist\WC3LanguagePatcher-windows.zip'" || goto :error
REM leave no temporary files behind
rmdir /s /q _build\work 2>nul
echo.
echo Done: dist\WC3LanguagePatcher-windows.zip
exit /b 0
:error
echo Build failed.
exit /b 1

:find_python
REM Sets PYEXE to a Python 3.12 listed by "py -0p" (any distributor).
set "PYEXE="
for /f "tokens=1,*" %%a in ('py -0p 2^>nul ^| findstr /c:"3.12"') do if not defined PYEXE set "PYEXE=%%b"
if defined PYEXE if "%PYEXE:~0,1%"=="*" for /f "tokens=1,*" %%a in ("%PYEXE%") do set "PYEXE=%%b"
if not defined PYEXE (
    echo Python 3.12 not found. Install it, e.g. "py install 3.12" or from python.org.
    exit /b 1
)
exit /b 0
