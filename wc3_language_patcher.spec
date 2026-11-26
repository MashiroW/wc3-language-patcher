# PyInstaller spec for the WC3 Language Patcher.
# Build:  pyinstaller --noconfirm wc3_language_patcher.spec
# Output: dist/WC3LanguagePatcher/WC3LanguagePatcher.exe (+ _internal/)
# The whole dist/WC3LanguagePatcher folder is what gets zipped for a release.
from pathlib import Path

ROOT = Path(SPECPATH)

datas = []


def add_tree(folder, patterns=("*",)):
    base = ROOT / folder
    for pattern in patterns:
        for f in base.rglob(pattern):
            if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".py":
                datas.append((str(f), str(f.parent.relative_to(ROOT))))


add_tree("__Misc_Tools")          # templates, structure.txt
add_tree("_HomeMade_Data")        # fixed maps, converted cinematic audio...
add_tree("translations")          # bundled AI translations of post-1.27 strings
add_tree("models")                # 3D background scene
add_tree("music")
datas.append((str(ROOT / "test_scene.json"), "."))

a = Analysis(
    ["patcher.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "OpenGLWorldEditor",
        "OpenGL.platform.win32",
        "OpenGL.arrays.numpymodule",
        "OpenGL.arrays.ctypesarrays",
        "OpenGL.arrays.numbers",
        "OpenGL.arrays.strings",
        "PyQt5.QtMultimedia",
        "PyQt5.QtOpenGL",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "torch", "transformers", "matplotlib", "scipy", "pandas", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WC3LanguagePatcher",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="WC3LanguagePatcher",
)
