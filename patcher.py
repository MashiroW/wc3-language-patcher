# Standard Library
import sys
import os
import shutil
import traceback
from pathlib import Path

# A windowed (no console) executable has no stdout/stderr: print() would crash.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Third-party
import re

# PyQt5
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtMultimedia import QMediaPlayer, QMediaPlaylist, QMediaContent
from PyQt5.QtCore import QUrl

# Get current script's directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Add to Python path (insert at beginning for priority)
sys.path.insert(0, current_dir)

# Paths: from source, everything is next to this file. In the .exe, the bundled
# files are in PyInstaller's folder and the user's data goes next to the .exe.
FROZEN = getattr(sys, "frozen", False)


def resource_path(*parts):
    """Files shipped with the program (templates, translations, music...)."""
    return Path(getattr(sys, "_MEIPASS", current_dir)).joinpath(*parts)


def workspace_dir():
    """Where MPQ_Data, CASC_Data and merged live."""
    if os.environ.get("WC3_PATCHER_WORKSPACE"):
        return Path(os.environ["WC3_PATCHER_WORKSPACE"]).resolve()
    if not FROZEN:
        return Path(current_dir)
    exe_dir = Path(sys.executable).parent
    try:
        (exe_dir / ".write_test").write_text("ok")
        (exe_dir / ".write_test").unlink()
        return exe_dir
    except OSError:
        pass
    # not writable (e.g. under Program Files): use Documents instead
    fallback = Path.home() / "Documents" / "WC3 Language Patcher"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


# MPQ_Data and CASC_Data get a placeholder.txt saying what goes inside
PLACEHOLDERS = {
    "MPQ_Data": "Optional: 1.27 archives extracted by hand (e.g. frFR-MPQ/war3.mpq/...).\n"
                "Normally not needed: use \"Open MPQ\" to pick your 1.27 install folder.\n",
    "CASC_Data": "Files of the target version (e.g. frfr.w3mod/...), extracted automatically\n"
                 "from the selected target. They override the 1.27 files.\n",
}

# merged/README.txt: how to install the built patches
MERGED_README ="""Built patches end up in this folder.

ALWAYS take enus_patch.zip, whatever language you install.
LANGUAGE_CHANGER.bat extracts it first (English base), then your language
over it. Without it the language changer stops.

To install a language:
1. Copy these into the Warcraft III folder
   (1.30 / 1.31: next to "Warcraft III.exe" - Reforged: the _retail_ folder):
     enus_patch.zip         English base, always required
     <lang>_patch.zip       your language, e.g. frfr_patch.zip
     LANGUAGE_CHANGER.bat
2. Run LANGUAGE_CHANGER.bat and pick your language.

With "4 - Auto-patching" on (the default), step 1 is done for you after each
build: the patches are moved (not copied) to the target game folder, with
LANGUAGE_CHANGER.bat, so this folder stays empty of patches.

enus_patch.zip is made from the target version at every build
(section "1 - Target Version" must be set).
"""


def create_data_folders(base):
    for name, text in PLACEHOLDERS.items():
        try:
            (Path(base) / name).mkdir(parents=True, exist_ok=True)
            note = Path(base) / name / "placeholder.txt"
            if not note.exists():
                note.write_text(text, encoding="utf-8")
        except OSError:
            pass
    # next to the built patches: how to install them, and the language switcher
    merged = Path(base) / "merged"
    try:
        merged.mkdir(parents=True, exist_ok=True)
        (merged / "placeholder.txt").unlink(missing_ok=True)   # replaced by README.txt
        (merged / "README.txt").write_text(MERGED_README, encoding="utf-8")
        changer = merged / "LANGUAGE_CHANGER.bat"
        if not changer.exists():
            shutil.copy2(resource_path("__Misc_Tools", "LANGUAGE_CHANGER.bat"), changer)
    except OSError:
        pass


os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'

# Language codes list (ISO 639-1)
LANGUAGE_CODES = sorted([
    "enUS", "esES", "frFR", "deDE", "itIT", "plPL", "ruRU", "zhCN", "zhTW", "koKR", "csCZ"
])

# Numbered setup sections (1, 2, 3): green bold title over a light frame
# ({base} = the normal font size, so the contents of the box keep their usual look)
STEP_STYLE = """
    QGroupBox {{ border: 1px solid #b8b8b8; border-radius: 4px; margin-top: 14px; padding-top: 8px;
                font-weight: bold; font-size: 14px; }}
    QGroupBox * {{ font-weight: normal; font-size: {base}pt; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px;
                       color: #2e7d32; }}
"""

from PyQt5.QtCore import QThread, pyqtSignal

# The 3D background is optional: the patcher must still work on machines
# where OpenGL is unavailable (VMs, remote desktop, old drivers...).
try:
    from OpenGLWorldEditor import MainWindow as EditorMainWindow
    OPENGL_IMPORT_ERROR = None
    OPENGL_IMPORT_TRACE = ""
except Exception as _e:  # ImportError, OpenGL errors...
    EditorMainWindow = None
    OPENGL_IMPORT_ERROR = _e
    OPENGL_IMPORT_TRACE = traceback.format_exc()


def _log_startup(msg):
    print(msg)
    try:
        with open(workspace_dir() / "patcher.log", "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except OSError:
        pass

from __Misc_Tools.patches_maker.patches_maker import build_patch_for_region
from __Misc_Tools.mpq_to_casc_converter.mpq_to_casc_converter import convert_mpq_to_casc
from __Misc_Tools.mpq_reader.install_extractor import extract_install, find_archives, ARCHIVES
from __Misc_Tools.casc_reader.casc import extract_locale
from __Misc_Tools.casc_reader.target import (prepare_target, inspect_target, describe_locales,
                                             build_english_base, ENGLISH_BASE)
from __Misc_Tools.game_version import mpq_source_version


def run_region(mpq_path, lang, log, target_dir=None, allow_online=False, source_dir=None,
               missing_fallback="english", auto_patch=False):
    """Full pipeline for one language. Returns True on success.

    auto_patch: the patches are moved to the game folder afterwards, so the
                English base already there is reused instead of rebuilt.
    source_dir: 1.27 install folder (its .mpq archives are read directly);
                without it, the extracted files in mpq_path are used."""
    structure = resource_path("__Misc_Tools", "mpq_to_casc_converter", "structure.txt")
    templates = None
    if target_dir:
        prep = prepare_target(
            target_dir, lang, casc_locale_folder(lang),
            workspace_dir() / "_work" / lang,
            resource_path("__Misc_Tools"), structure, log=log)
        structure, templates = prep["structure_file"], prep["templates_dir"]
        # English base, needed by LANGUAGE_CHANGER.bat whatever the language
        if lang.lower() != "enus":
            try:
                build_english_base(target_dir, workspace_dir() / "merged", log=log,
                                   installed_dir=game_install_folder(target_dir) if auto_patch else None)
            except Exception as e:
                log(f"  | ⚠️ {ENGLISH_BASE} not created: {e}")
    else:
        log("  | ℹ️ No target CASC version selected: using CASC_Data and the bundled 1.31 references")
        log(f"  | ⚠️ {ENGLISH_BASE} is not created without a target: LANGUAGE_CHANGER.bat needs it")
    result = convert_mpq_to_casc(region_folder_path=mpq_path, progress_callback=log,
                                 structure_file=structure, install_dir=source_dir or None)
    if not result:
        return False
    ok = build_patch_for_region(
        progress_callback=log,
        mpq_to_casc_path=str(mpq_path) + "-converted-to-CASC",
        workspace_dir=workspace_dir(),
        resource_dir=resource_path(),
        allow_online_translation=allow_online,
        templates_dir=templates,
        missing_fallback=missing_fallback,
    )
    if target_dir:
        shutil.rmtree(workspace_dir() / "_work", ignore_errors=True)
    return ok


def game_install_folder(target_dir):
    """Where the patches go in a game install: _retail_ for Reforged, else its root."""
    retail = Path(target_dir) / "_retail_"
    return retail if retail.is_dir() else Path(target_dir)


def move_file(src, dst):
    """Move src over dst. Instant on the same drive; across drives it is a copy
    followed by the removal of the original."""
    try:
        os.replace(src, dst)
    except OSError:
        shutil.copy2(src, dst)
        os.unlink(src)


def install_patches(target_dir, log):
    """Auto-patching: move the built patches from merged/ into the game folder (no
    second copy is kept) and copy LANGUAGE_CHANGER.bat there. Returns True if done."""
    merged = workspace_dir() / "merged"
    dest = game_install_folder(target_dir)
    # one archive per language: its most recent build (a rebuild gets a time stamp)
    latest = {}
    for archive in merged.glob("*_patch*.zip"):
        lang = archive.name.lower().split("_patch")[0]
        if lang not in latest or archive.stat().st_mtime > latest[lang].stat().st_mtime:
            latest[lang] = archive
    files = [(archive, f"{lang}_patch.zip") for lang, archive in sorted(latest.items())]
    changer = merged / "LANGUAGE_CHANGER.bat"
    if not latest:
        log("🚚 Auto-patching: nothing to move, no new patch in the merged folder")
        return False
    log(f"🚚 Auto-patching: moving {len(files)} patch(es) to {dest}")
    try:
        for src, name in files:
            log(f"  | 📥 {name}")
            move_file(src, dest / name)
        if changer.exists():
            log(f"  | 📥 {changer.name}")
            shutil.copy2(changer, dest / changer.name)
    except OSError as e:
        log(f"  | ⛔ Could not move to the game folder: {e}")
        log("  |   Close the game, or move the files of the merged folder yourself "
            "(the game folder may need administrator rights).")
        return False
    log("✅ Game folder ready: run LANGUAGE_CHANGER.bat there and pick your language.")
    return True


def casc_locale_folder(lang):
    return workspace_dir() / "CASC_Data" / f"{lang.lower()}.w3mod"


def import_casc_locale(game_dir, lang, log):
    """Extract one locale of a modern (1.30+) install into CASC_Data/<lang>.w3mod."""
    out = casc_locale_folder(lang)
    if out.exists():
        shutil.rmtree(out)
    log(f"  | 📦 Reading CASC storage of {game_dir} ...")

    def progress(done, total):
        log(f"  |   | {lang}: {done}/{total} ({int(done / max(total, 1) * 100)}%)")

    ok, missing, failed = extract_locale(game_dir, lang, out, log=log, progress=progress)
    log(f"  |   ✅ {lang}: {ok} files extracted to CASC_Data/{out.name}"
        + (f", {missing} listed but not installed locally" if missing else "")
        + (f", {len(failed)} failed" if failed else ""))
    if missing:
        log(f"  |   ℹ️ Only the languages installed with the game are stored locally. "
            f"Install the game in {lang} to get its missing files.")
    return ok > 0


class RegionProcessor(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, mpq_path, lang, allow_online=False, target_dir=None, source_dir=None,
                 missing_fallback="english", auto_patch=False):
        super().__init__()
        self.auto_patch = auto_patch
        self.mpq_path = mpq_path
        self.lang = lang
        self.allow_online = allow_online
        self.target_dir = target_dir
        self.source_dir = source_dir
        self.missing_fallback = missing_fallback
        self.last_progress = ""

    def run(self):
        def progress_callback(message):
            self.progress.emit(message)
            self.last_progress = message

        try:
            run_region(self.mpq_path, self.lang, progress_callback,
                       target_dir=self.target_dir, allow_online=self.allow_online,
                       source_dir=self.source_dir, missing_fallback=self.missing_fallback,
                       auto_patch=self.auto_patch)
        except Exception as e:
            self.error.emit(f"  | ⛔ Unexpected error for {self.lang}: {e}")
            self.error.emit(traceback.format_exc())
        finally:
            self.finished.emit()


class PatchInstaller(QThread):
    """Auto-patching in the background (the archives are large)."""
    progress = pyqtSignal(str)

    def __init__(self, target_dir):
        super().__init__()
        self.target_dir = target_dir

    def run(self):
        try:
            install_patches(self.target_dir, self.progress.emit)
        except Exception as e:
            self.progress.emit(f"  | ⛔ Auto-patching failed: {e}")


class CustomMainWindow(QMainWindow):
    def __init__(self, EditorOpenGLwidget):
        super().__init__()
        self.setWindowTitle("WC3 Localization Patcher")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(800, 600)  # Prevent window from becoming too small
        
        self.settings = QSettings("Mashiro", "WC3LocalizationPatcher")
        self.sources = self.load_sources()   # lang -> 1.27 install folder
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create splitter with proper configuration
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(8)
        
        # OpenGL Widget setup
        self.opengl_widget = EditorOpenGLwidget
        self.opengl_widget.setMinimumSize(400, 400)
        self.splitter.addWidget(self.opengl_widget)
        
        # Right panel setup
        right_panel = QWidget()
        right_panel.setMinimumWidth(300)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_layout.setSpacing(10)
        
        # Target version (CASC install the patch is built for)
        target_group = QGroupBox("1 · Target Version (CASC)")
        target_layout = QVBoxLayout()
        target_row = QHBoxLayout()
        self.target_edit = QLineEdit()
        self.target_edit.setReadOnly(True)
        self.target_edit.setPlaceholderText("Warcraft III 1.30+ folder (contains .build.info) - 1.31 recommended")
        self.target_browse = QPushButton("...")
        self.target_browse.setFixedSize(25, 25)
        self.target_browse.setToolTip("Select the target Warcraft III install")
        self.target_clear = QPushButton("x")
        self.target_clear.setFixedSize(25, 25)
        self.target_clear.setToolTip("No target: use CASC_Data and the bundled 1.31 references")
        target_row.addWidget(self.target_edit, 1)
        target_row.addWidget(self.target_browse)
        target_row.addWidget(self.target_clear)
        target_layout.addLayout(target_row)
        self.target_info = QLabel("")
        self.target_info.setWordWrap(True)
        target_layout.addWidget(self.target_info)
        target_group.setLayout(target_layout)
        right_layout.addWidget(target_group)

        # Language Selection Group
        lang_group = QGroupBox("2 · Languages (MPQ sources)")
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("Language:"), 0)
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(LANGUAGE_CODES)
        lang_layout.addWidget(self.lang_combo, 1)  # Stretch factor 1
        self.add_button = QPushButton("+")
        self.add_button.setFixedSize(25, 25)
        lang_layout.addWidget(self.add_button)
        lang_group.setLayout(lang_layout)
        right_layout.addWidget(lang_group)

        # Language Table
        self.lang_table = QTableWidget()
        self.lang_table.setColumnCount(5)
        self.lang_table.setHorizontalHeaderLabels(["Language", "Skip", "Source (MPQ)", "Target (CASC)", ""])
        self.lang_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.lang_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.lang_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.lang_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.lang_table.verticalHeader().setVisible(False)
        self.lang_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.lang_table.setSelectionMode(QTableWidget.SingleSelection)
        right_layout.addWidget(self.lang_table)
        
        # Translation of the strings the 1.27 version never had
        tr_group = QGroupBox("3 · Missing Strings")
        tr_layout = QVBoxLayout()
        self.online_checkbox = QCheckBox("Translate online if needed (recommended, keep it on)")
        self.online_checkbox.setToolTip(
            "Original texts are always kept. Strings that did not exist in 1.27 use the bundled\n"
            "translations; the few left are translated online. Turning this off is not recommended.")
        tr_layout.addWidget(self.online_checkbox)
        fallback_row = QHBoxLayout()
        fallback_row.setContentsMargins(20, 0, 0, 0)
        self.fallback_label = QLabel("If not translated:")
        self.fallback_english = QRadioButton("Use the target's English text")
        self.fallback_empty = QRadioButton("Leave empty (may break texts)")
        self.fallback_english.setChecked(True)
        self.fallback_group = QButtonGroup(self)
        self.fallback_group.addButton(self.fallback_english)
        self.fallback_group.addButton(self.fallback_empty)
        fallback_row.addWidget(self.fallback_label)
        fallback_row.addWidget(self.fallback_english)
        fallback_row.addWidget(self.fallback_empty)
        fallback_row.addStretch(1)
        tr_layout.addLayout(fallback_row)
        tr_group.setLayout(tr_layout)
        right_layout.addWidget(tr_group)

        # Auto-patching: put the result straight into the target game folder
        auto_group = QGroupBox("4 · Auto-patching")
        auto_layout = QVBoxLayout()
        self.autopatch_checkbox = QCheckBox("Move the patches into the game folder (recommended)")
        self.autopatch_checkbox.setToolTip(
            "On: after the build, every <lang>_patch.zip is moved (not copied) to the root of the target\n"
            "version (section 1), with LANGUAGE_CHANGER.bat. You only have to run the .bat there.\n"
            "Off: the files stay in the merged folder and you copy them yourself.")
        auto_layout.addWidget(self.autopatch_checkbox)
        auto_group.setLayout(auto_layout)
        right_layout.addWidget(auto_group)

        # steps 1-2-3: green numbered titles so the order is obvious
        for group in (target_group, lang_group, tr_group, auto_group):
            group.setStyleSheet(STEP_STYLE.format(base=QApplication.font().pointSize()))

        # Patch Button
        self.patch_button = QPushButton("BUILD PATCH")
        self.patch_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; 
                color: white; 
                font-weight: bold; 
                font-size: 16px;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        right_layout.addWidget(self.patch_button)

        # Where the patch zips end up (merged/ next to the exe)
        self.output_button = QPushButton("Open output folder")
        self.output_button.setIcon(self.style().standardIcon(QStyle.SP_DirOpenIcon))
        self.output_button.clicked.connect(self.open_output_folder)
        right_layout.addWidget(self.output_button)

        # Console Log
        self.console_log = QTextEdit()
        self.console_log.setReadOnly(True)
        self.console_log.setMinimumHeight(100)
        right_layout.addWidget(self.console_log)
        
        # Add right panel to splitter
        self.splitter.addWidget(right_panel)
        
        # Configure splitter stretch factors
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        
        # Add splitter to main layout
        main_layout.addWidget(self.splitter)
        
        # Initialize paths and data (writable folder: next to the .exe when frozen)
        self.base_path = workspace_dir()
        self.mpq_base_path = self.base_path / "MPQ_Data"
        self.casc_base_path = self.base_path / "CASC_Data"
        
        # Create the folders (with a placeholder.txt explaining each one)
        create_data_folders(self.base_path)
        self.update_output_button()
        
        # Load saved settings
        self.selected_languages = self.detect_existing_languages()
        saved_langs = self.settings.value("selected_languages", [])
        for lang_data in saved_langs or []:
            lang_data = list(lang_data)
            lang = lang_data[0]
            if isinstance(lang_data[1], str):
                lang_data[1] = lang_data[1].lower() == "true"
            if lang not in [item[0] for item in self.selected_languages]:
                self.selected_languages.append(tuple(lang_data))
        
        self.update_lang_table()
        
        # Connect signals
        self.add_button.clicked.connect(self.add_language)
        self.patch_button.clicked.connect(self.patch_languages)
        self.online_checkbox.setChecked(self.settings.value("online_translation", True, type=bool))
        self.autopatch_checkbox.setChecked(self.settings.value("auto_patching", True, type=bool))
        self.autopatch_checkbox.toggled.connect(lambda on: self.settings.setValue("auto_patching", on))
        self.autopatch_checkbox.toggled.connect(lambda _: self.update_output_button())
        if self.settings.value("missing_fallback", "english", type=str) == "empty":
            self.fallback_empty.setChecked(True)
        self.online_checkbox.toggled.connect(self.save_translation_options)
        self.fallback_english.toggled.connect(self.save_translation_options)
        self.update_fallback_state(True)
        self.target_browse.clicked.connect(self.browse_target)
        self.target_clear.clicked.connect(lambda: self.set_target(""))
        self.set_target(self.settings.value("target_casc", "", type=str), quiet=True)

        # Add this after initializing the settings
        self.media_player = None
        self.playlist = None
        
        # Add this in the UI setup (after language configuration group)
        # Volume Control Group ################################################################
        volume_group = QGroupBox("Volume Control")
        volume_layout = QHBoxLayout()
        
        # Volume icon
        self.volume_icon = QLabel()
        self.volume_icon.setPixmap(QIcon.fromTheme("audio-volume-medium").pixmap(24, 24))
        volume_layout.addWidget(self.volume_icon)
        
        # Volume slider
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.settings.value("volume", 50, type=int))
        self.volume_slider.valueChanged.connect(self.update_volume)
        volume_layout.addWidget(self.volume_slider)
        
        # Volume percentage label
        self.volume_label = QLabel(f"{self.volume_slider.value()}%")
        volume_layout.addWidget(self.volume_label)
        
        volume_group.setLayout(volume_layout)
        right_layout.addWidget(volume_group)  # at the very bottom, under the console
        
        # Initialize media player
        self.init_background_music()

    def init_background_music(self):
        """Initialize dual players with synchronized playback"""
        self.intro_player = None
        self.loop_player = None
        try:
            # Create two media players
            self.intro_player = QMediaPlayer()
            self.loop_player = QMediaPlayer()
            
            # Load audio files
            intro_path = str(resource_path("music", "COE33 OST Flying Waters - Goblu part01.mp3"))
            loop_path = str(resource_path("music", "COE33 OST Flying Waters - Goblu part02.mp3"))
            
            # Check files exist
            if not os.path.exists(intro_path) or not os.path.exists(loop_path):
                self.log_message("Missing audio files")
                return
                
            # Load media content
            self.intro_player.setMedia(QMediaContent(QUrl.fromLocalFile(intro_path)))
            self.loop_player.setMedia(QMediaContent(QUrl.fromLocalFile(loop_path)))
            
            # Configure players
            self.loop_player.setVolume(self.volume_slider.value())
            self.loop_player.stateChanged.connect(self.handle_loop_state)
            self.intro_player.positionChanged.connect(self.handle_intro_position)
            
            # Pre-buffer both tracks
            self.intro_player.play()
            self.loop_player.play()
            self.loop_player.pause()  # Pause immediately after pre-buffering
            
            # Start intro playback
            self.intro_player.setVolume(self.volume_slider.value())
            self.intro_player.play()
            
            self.log_message("Playing: COE33 OST Flying Waters - Goblu")

        except Exception as e:
            self.log_message(f"Audio error: {str(e)}")

    def handle_intro_position(self, position):
        """Start loop player 500ms before intro ends"""
        if self.intro_player.duration() - position <= 500:
            if self.loop_player.state() != QMediaPlayer.PlayingState:
                # Get exact sync position
                sync_pos = max(0, self.loop_player.duration() - 500)
                self.loop_player.setPosition(sync_pos)
                self.loop_player.setVolume(self.volume_slider.value())
                self.loop_player.play()

    def handle_loop_state(self, state):
        """Maintain continuous loop playback"""
        if state == QMediaPlayer.StoppedState:
            self.loop_player.play()

    def handle_track_change(self, index):
        """Handle transition from intro to loop track"""
        if index == 1:  # When loop track starts
            # Change to loop mode for endless repetition
            self.playlist.setPlaybackMode(QMediaPlaylist.CurrentItemInLoop)
            #self.log_message("Transitioning to looped background music")

    def update_volume(self, value):
        """Update volume and icon based on slider value"""
        for player in (self.intro_player, self.loop_player):
            if player is not None:
                player.setVolume(value)

        if self.media_player:
            self.media_player.setVolume(value)
            
        # Update label
        self.volume_label.setText(f"{value}%")
        
        # Update icon
        if value == 0:
            icon = "audio-volume-muted"
        elif value < 33:
            icon = "audio-volume-low"
        elif value < 66:
            icon = "audio-volume-medium"
        else:
            icon = "audio-volume-high"
            
        self.volume_icon.setPixmap(QIcon.fromTheme(icon).pixmap(24, 24))
        
        # Save setting
        self.settings.setValue("volume", value)

    def resizeEvent(self, event):
        """Handle window resizing while maintaining proportions"""
        super().resizeEvent(event)
        # Maintain 70/30 split ratio
        total_width = self.splitter.width()
        self.splitter.setSizes([
            int(total_width * 0.7), 
            int(total_width * 0.3)
        ])

    def detect_existing_languages(self):
        # Create a set of lowercase language codes for matching
        
        detected_languages = []
        
        # Scan MPQ base path for folders in "xxXX-MPQ" format
        if os.path.exists(self.mpq_base_path):
            for item in os.listdir(self.mpq_base_path):
                # Check for folders ending with "-MPQ"
                if item.endswith("-MPQ"):
                    # Extract language code part (first 4 characters)
                    lang_code = item[:4]
                    # Only proceed if it's a valid language code
                    if lang_code in LANGUAGE_CODES:
                        mpq_path = os.path.join(self.mpq_base_path, item)
                        required_subdirs = {"war3.mpq", "war3x.mpq", "war3xlocal.mpq", "War3Patch.mpq"}
                        # Check if all required subdirectories exist
                        if all(os.path.exists(os.path.join(mpq_path, subdir)) for subdir in required_subdirs):
                            rel_mpq_path = os.path.relpath(mpq_path, self.base_path)
                            # CASC directory name should be lowercase
                            casc_dir = f"{lang_code.lower()}.w3mod"
                            casc_path = os.path.join(self.casc_base_path, casc_dir)
                            if os.path.exists(casc_path):
                                rel_casc_path = os.path.relpath(casc_path, self.base_path)
                                detected_languages.append((lang_code, False, rel_mpq_path, rel_casc_path))
        
        # Scan CASC base path for folders in "xxXX.w3mod" format
        if os.path.exists(self.casc_base_path):
            for item in os.listdir(self.casc_base_path):
                # Check for folders ending with ".w3mod"
                if item.endswith(".w3mod"):
                    # Extract language code from filename (remove .w3mod extension)
                    lang_code_lower = item[:-6]  # Remove ".w3mod" (6 characters)
                    # Find matching language code in original case
                    lang_code_match = next((code for code in LANGUAGE_CODES if code.lower() == lang_code_lower), None)
                    
                    if lang_code_match and lang_code_match not in [x[0] for x in detected_languages]:
                        casc_path = os.path.join(self.casc_base_path, item)
                        rel_casc_path = os.path.relpath(casc_path, self.base_path)
                        # MPQ directory name should be in "xxXX-MPQ" format
                        mpq_dir = f"{lang_code_match}-MPQ"
                        mpq_path = os.path.join(self.mpq_base_path, mpq_dir)
                        rel_mpq_path = os.path.relpath(mpq_path, self.base_path)
                        detected_languages.append((lang_code_match, False, rel_mpq_path, rel_casc_path))
        
        return detected_languages

    def add_language(self):
        lang = self.lang_combo.currentText()
        if lang not in [item[0] for item in self.selected_languages]:
            mpq_path = os.path.join(self.mpq_base_path, f"{lang}-MPQ")
            casc_path = os.path.join(self.casc_base_path, f"{lang.lower()}.w3mod")
            rel_mpq_path = os.path.relpath(mpq_path, self.base_path)
            rel_casc_path = os.path.relpath(casc_path, self.base_path)

            self.selected_languages.append((lang, False, rel_mpq_path, rel_casc_path))
            self.log_message(f"Added language: {lang}")
            self.save_settings()
            # always ask which MPQ install this language comes from, never reuse an old one
            self.sources.pop(lang, None)
            self.save_sources()
            if not self.choose_source(lang, start_dir=""):
                self.log_message(f"  No MPQ source selected for {lang} yet (use Open MPQ)")
            self.update_lang_table()

    # ------------------------------------------------ translation options ---
    def update_fallback_state(self, ui_enabled=True):
        """The fallback choice only matters when online translation is off."""
        active = ui_enabled and not self.online_checkbox.isChecked()
        for w in (self.fallback_label, self.fallback_english, self.fallback_empty):
            w.setEnabled(active)

    def save_translation_options(self, *_):
        self.settings.setValue("online_translation", self.online_checkbox.isChecked())
        self.settings.setValue("missing_fallback", "empty" if self.fallback_empty.isChecked() else "english")
        self.update_fallback_state(self.patch_button.isEnabled())

    # ------------------------------------------------------- 1.27 sources ---
    def load_sources(self):
        import json
        try:
            return json.loads(self.settings.value("sources_127", "{}", type=str) or "{}")
        except ValueError:
            return {}

    def save_sources(self):
        import json
        self.settings.setValue("sources_127", json.dumps(self.sources))

    def extracted_folder(self, lang):
        """MPQ_Data/<lang>-MPQ filled by hand (original workflow), or None."""
        folder = self.mpq_base_path / f"{lang}-MPQ"
        if not folder.is_dir():
            return None
        has_files = any(p.is_file() and p.name != "placeholder.txt" for p in folder.rglob("*"))
        return folder if has_files else None

    def source_ok(self, lang):
        folder = self.sources.get(lang)
        return bool(folder) and len(find_archives(folder)) == len(ARCHIVES) if folder and Path(folder).is_dir() else False

    def has_source(self, lang):
        return self.source_ok(lang) or self.extracted_folder(lang) is not None

    def choose_source(self, lang, start_dir=None):
        folder = QFileDialog.getExistingDirectory(
            self, f"Select the Warcraft III MPQ install for {lang} (contains war3.mpq, 1.27 recommended)",
            self.sources.get(lang, "") if start_dir is None else start_dir)
        if not folder:
            return False
        found = find_archives(folder)
        missing = [a for a in ARCHIVES if a not in found]
        if missing:
            QMessageBox.warning(self, "Archives not found",
                                "These archives are missing in the selected folder:\n" + ", ".join(missing))
            return False
        self.sources[lang] = folder
        self.save_sources()
        self.log_message(f"MPQ source for {lang}: {folder}")
        self.update_lang_table()
        return True

    def remove_language(self, selected_row):
        if 0 <= selected_row < len(self.selected_languages):
            lang, _, rel_mpq_path, rel_casc_path = self.selected_languages[selected_row]
            mpq_path = os.path.join(self.base_path, rel_mpq_path)
            casc_path = os.path.join(self.base_path, rel_casc_path)
            
            reply = QMessageBox.question(
                self, 'Confirm Removal',
                f"Delete all files and folders for {lang}?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                try:
                    # Delete the converted CASC folder if it exists
                    converted_casc_path = os.path.join(self.base_path, "MPQ_Data", f"{lang}-MPQ-converted-to-CASC")
                    if os.path.exists(converted_casc_path):
                        shutil.rmtree(converted_casc_path)
                        #self.log_message(f"Deleted converted CASC folder: {converted_casc_path}")
                    
                    # Delete the MPQ folder
                    if os.path.exists(mpq_path):
                        shutil.rmtree(mpq_path)
                        #self.log_message(f"Deleted MPQ folder: {mpq_path}")
                    
                    # Delete the CASC folder
                    if os.path.exists(casc_path):
                        shutil.rmtree(casc_path)
                        #self.log_message(f"Deleted CASC folder: {casc_path}")
                    
                    #self.log_message(f"Deleted all files for language: {lang}")
                except Exception as e:
                    self.log_message(f"Error deleting files: {str(e)}")
            
            self.selected_languages.pop(selected_row)
            self.update_lang_table()
            self.log_message(f"Removed language: {lang}")
            self.save_settings()

    def update_lang_table(self):
        self.lang_table.setRowCount(len(self.selected_languages))
        
        for i, (lang, ignore, rel_mpq_path, rel_casc_path) in enumerate(self.selected_languages):
            lang_item = QTableWidgetItem(lang)
            casc_item = QTableWidgetItem(rel_casc_path)

            casc_path = os.path.join(self.base_path, rel_casc_path)
            casc_exists = os.path.exists(casc_path)
            has_missing_path = not self.has_source(lang)

            if has_missing_path:
                orange_color = QColor(255, 165, 0)
                for item in [lang_item, casc_item]:
                    item.setBackground(orange_color)

            self.lang_table.setItem(i, 0, lang_item)

            chk = QCheckBox()
            chk.setChecked(ignore)
            chk.stateChanged.connect(lambda state, row=i: self.toggle_ignore(row, state))
            chk_cell = QWidget()
            chk_layout = QHBoxLayout(chk_cell)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk_layout.addWidget(chk)
            if has_missing_path:
                chk_cell.setStyleSheet("background-color: rgb(255, 165, 0);")
            self.lang_table.setCellWidget(i, 1, chk_cell)

            # source: the install folder (read directly) or MPQ_Data filled by hand
            if self.source_ok(lang):
                tip = f"{self.sources[lang]}\nClick to change"
            elif self.extracted_folder(lang) is not None:
                tip = f"MPQ_Data/{lang}-MPQ (extracted files)\nClick to choose an install folder instead"
            else:
                tip = "No source yet: select the Warcraft III install of this language (contains war3.mpq)"
            # game version next to the button text, when it can be read
            # (install: game.dll; MPQ_Data: version.txt written at import)
            if self.source_ok(lang):
                mpq_version = mpq_source_version(self.sources[lang]) or "?"
            elif self.extracted_folder(lang) is not None:
                mpq_version = mpq_source_version(self.extracted_folder(lang)) or "?"
                if mpq_version == "?":
                    tip += "\nVersion unknown: add a version.txt (e.g. 1.27b) in this folder"
            else:
                mpq_version = ""
            label = f"Open MPQ ({mpq_version})" if mpq_version else "Open MPQ"
            src_btn = QPushButton(label)
            src_btn.setToolTip(tip)
            if has_missing_path:
                src_btn.setStyleSheet("background-color: rgb(255, 165, 0);")
            src_btn.clicked.connect(lambda _, l=lang: self.choose_source(l))
            self.lang_table.setCellWidget(i, 2, src_btn)
            
            casc_btn = QPushButton("Open CASC")  # its version is shown in Target Version
            casc_btn.setToolTip(casc_path)
            casc_btn.setEnabled(casc_exists)
            if not casc_exists:
                casc_btn.setStyleSheet("color: gray;")
            casc_btn.clicked.connect(lambda _, path=casc_path: self.show_in_explorer(path))
            self.lang_table.setCellWidget(i, 3, casc_btn)

            del_btn = QPushButton("✕")
            del_btn.setFixedWidth(30)
            del_btn.setStyleSheet("color: #d32f2f; font-weight: bold; font-size: 14px;")
            del_btn.setToolTip(f"Remove {lang} from the list")
            del_btn.clicked.connect(lambda _, row=i: self.remove_language(row))
            self.lang_table.setCellWidget(i, 4, del_btn)
        
        self.lang_table.resizeColumnsToContents()
        self.lang_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.lang_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)

    def toggle_ignore(self, row, state):
        lang, _, rel_mpq_path, rel_casc_path = self.selected_languages[row]
        self.selected_languages[row] = (lang, state == Qt.Checked, rel_mpq_path, rel_casc_path)
        self.save_settings()

    def show_in_explorer(self, path):
        system = os.name
        path = os.path.normpath(path)
        
        if system == 'nt':  # Windows
            os.startfile(path)
        elif system == 'posix':  # macOS/Linux
            if os.uname().sysname == 'Darwin':  # macOS
                os.system(f'open "{path}"')
            else:  # Linux
                os.system(f'xdg-open "{path}"')

    def patch_languages(self):
        if not self.selected_languages:
            self.log_message("No languages selected for patching!")
            return

        # one button does everything: ask now for any missing MPQ source
        for lang, ignore, _, _ in self.selected_languages:
            if not ignore and not self.has_source(lang):
                QMessageBox.information(self, "MPQ source needed",
                                        f"Select the Warcraft III MPQ install folder for {lang} (1.27 recommended).")
                if not self.choose_source(lang):
                    self.log_message(f"⛔ No MPQ source for {lang}: build cancelled")
                    return
        self.log_message("Starting patch process...")
        self.log_message(f"🎯 Target: {self.target_dir or 'none (CASC_Data + bundled 1.31 references)'}")
        for lang, ignore, _, _ in self.selected_languages:
            if ignore:
                self.log_message(f"  ⏭️ {lang} skipped (Skip is checked)")
        
        # Disable UI during processing
        self.set_ui_enabled(False)
        
        # Prepare languages to process
        self.languages_to_process = [
            (lang, rel_mpq_path) 
            for lang, ignore, rel_mpq_path, rel_casc_path in self.selected_languages 
            if not ignore
        ]
        
        if not self.languages_to_process:
            self.log_message("No languages to process (all ignored)")
            self.set_ui_enabled(True)
            return
        
        # Start processing
        self.process_next_language()

    def set_ui_enabled(self, enabled):
        """Enable/disable UI elements during processing and update styles"""
        self.patch_button.setEnabled(enabled)
        self.online_checkbox.setEnabled(enabled)
        self.autopatch_checkbox.setEnabled(enabled)
        self.update_fallback_state(enabled)
        self.target_browse.setEnabled(enabled)
        self.target_clear.setEnabled(enabled)
        self.add_button.setEnabled(enabled)
        self.lang_table.setEnabled(enabled)

        # Update the BUILD PATCH button's style
        if enabled:
            self.patch_button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50; 
                    color: white; 
                    font-weight: bold; 
                    font-size: 16px;
                    padding: 10px;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #45a049; }
            """)
        else:
            self.patch_button.setStyleSheet("""
                QPushButton {
                    background-color: #cccccc;  /* Gray when disabled */
                    color: #666666;            /* Darker gray text */
                    font-weight: bold; 
                    font-size: 16px;
                    padding: 10px;
                    border-radius: 5px;
                }
                /* No hover effect when disabled */
            """)

    def process_next_language(self):
        if not self.languages_to_process:
            self.log_message("Patch completed for selected languages!")
            if self.autopatch_checkbox.isChecked() and self.target_dir:
                self.installer = PatchInstaller(self.target_dir)
                self.installer.progress.connect(self.log_message)
                self.installer.finished.connect(self.finish_build)
                self.installer.start()
                return
            if self.autopatch_checkbox.isChecked():
                self.log_message("ℹ️ Auto-patching skipped: no target version selected (section 1)")
            self.log_message(f"📁 Output folder: {self.base_path / 'merged'}")
            self.finish_build()
            return
        
        lang, rel_mpq_path = self.languages_to_process.pop(0)
        mpq_path = os.path.join(self.base_path, rel_mpq_path)
        
        source = self.sources.get(lang) if self.source_ok(lang) else None
        self.log_message(f"\nProcessing language: {lang}")
        self.log_message(f"MPQ source: {source or rel_mpq_path}")

        # Create and start worker
        self.worker = RegionProcessor(mpq_path, lang, allow_online=self.online_checkbox.isChecked(),
                                      target_dir=self.target_dir or None, source_dir=source,
                                      missing_fallback="empty" if self.fallback_empty.isChecked() else "english",
                                      auto_patch=self.autopatch_checkbox.isChecked())
        self.worker.progress.connect(self.log_message)
        self.worker.error.connect(self.log_message)
        self.worker.finished.connect(self.process_next_language)
        self.worker.start()

    def finish_build(self):
        self.set_ui_enabled(True)
        self.log_message("")
        self.update_output_button()

    def set_target(self, folder, quiet=False):
        self.target_dir = ""
        self.target_edit.setText("")
        self.target_info.setText("No target selected: CASC_Data and the bundled 1.31 references are used.")
        if folder:
            try:
                info = inspect_target(folder)
            except Exception as e:
                if not quiet:
                    QMessageBox.warning(self, "Cannot read install",
                                        f"This folder is not a readable Warcraft III 1.30+ install:\n{e}")
                self.settings.setValue("target_casc", "")
                return False
            self.target_dir = folder
            self.target_edit.setText(folder)
            self.target_info.setText(f"Warcraft III {info['version']} - installed languages: "
                                     f"{describe_locales(info['locales'])}")
            if not quiet:
                self.log_message(f"🎯 Target set: Warcraft III {info['version']} ({folder})")
        self.settings.setValue("target_casc", self.target_dir)
        if hasattr(self, "lang_table"):
            self.update_lang_table()  # the CASC version shown on each row may change
        self.update_output_button()
        return True

    def browse_target(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select the target Warcraft III install (1.30+, contains .build.info and Data)",
            self.target_dir or "")
        if not folder:
            return False
        if not (Path(folder) / ".build.info").exists():
            QMessageBox.warning(self, "Not a CASC install",
                                "This folder has no .build.info file.\n"
                                "Select the main folder of a Warcraft III 1.30+ install.")
            return False
        return self.set_target(folder)

    def output_folder(self):
        """Where the patches are: the game folder once auto-patching moved them
        there, otherwise merged/ next to the program."""
        merged = self.base_path / "merged"
        target = getattr(self, "target_dir", "")
        if target and self.autopatch_checkbox.isChecked():
            game = game_install_folder(target)
            if any(game.glob("*_patch*.zip")) or not any(merged.glob("*_patch*.zip")):
                return game
        return merged

    def update_output_button(self):
        folder = self.output_folder()
        zips = sorted(folder.glob("*_patch*.zip")) if folder.exists() else []
        self.output_button.setEnabled(bool(zips))
        self.output_button.setText(
            f"Open output folder - {len(zips)} patch(es)" if zips
            else "Open output folder - build a patch first")
        self.output_button.setToolTip(f"Opens the folder containing the <lang>_patch.zip files:\n{folder}")

    def open_output_folder(self):
        folder = self.output_folder()
        if folder.exists():
            self.show_in_explorer(str(folder))

    def save_settings(self):
        serializable = [(lang, ignore, mpq, casc) for lang, ignore, mpq, casc in self.selected_languages]
        self.settings.setValue("selected_languages", serializable)

    def log_message(self, message):
        cursor = self.console_log.textCursor()
        
        # Check if this is a progress message (ends with NUMBER/NUMBER (NUMBER%))
        is_progress = re.search(r'\d+/\d+\s+\(\d+%\)$', message) is not None
        
        if is_progress:
            # Extract prefix from current message (remove progress part)
            current_prefix = re.sub(r'\s*\d+/\d+\s+\(\d+%\)$', '', message)
            
            # Move to end and get last line
            cursor.movePosition(QTextCursor.End)
            cursor.select(QTextCursor.LineUnderCursor)
            last_line = cursor.selectedText()
            
            # Check if last line is progress with matching prefix
            last_progress_match = re.search(r'\d+/\d+\s+\(\d+%\)$', last_line)
            if last_progress_match:
                last_prefix = re.sub(r'\s*\d+/\d+\s+\(\d+%\)$', '', last_line)
                if last_prefix == current_prefix:
                    # Replace last line with new progress
                    cursor.removeSelectedText()
                    cursor.insertText(message)
                    self.console_log.setTextCursor(cursor)
                    self.console_log.ensureCursorVisible()
                    return  # Exit after handling matched progress update
            
            # If no match, append as new line
            self.console_log.append(message)
        else:
            # For regular messages, just append
            self.console_log.append(message)
            
        self.console_log.setTextCursor(cursor)
        self.console_log.ensureCursorVisible()

def run_headless(args):
    """Command-line mode (no window), also used to test the frozen build:
        WC3LanguagePatcher.exe --import <lang> <1.27 folder>
        WC3LanguagePatcher.exe --import-casc <modern game folder> <lang>
        WC3LanguagePatcher.exe --build <lang> [--source <1.27 folder>] [--target <modern game folder>]
                               [--no-online] [--empty] [--install]
      --source     read the 1.27 .mpq archives directly (otherwise MPQ_Data/<lang>-MPQ)
      --no-online  no online translation for strings without a bundled translation
      --empty      with --no-online: leave those strings empty instead of English
      --install    auto-patching: move the patches into the target game folder
    Output goes to patcher.log in the workspace folder."""
    create_data_folders(workspace_dir())
    log_path = workspace_dir() / "patcher.log"
    with open(log_path, "a", encoding="utf-8") as log_file:
        def log(msg):
            log_file.write(msg + "\n")
            log_file.flush()
            try:
                print(msg)
            except Exception:
                pass
        try:
            if args[0] == "--import" and len(args) >= 3:
                region_dir = workspace_dir() / "MPQ_Data" / f"{args[1]}-MPQ"
                extract_install(args[2], region_dir, log=log)
                return 0
            if args[0] == "--import-casc" and len(args) >= 3:
                return 0 if import_casc_locale(args[1], args[2], log) else 1
            if args[0] == "--build" and len(args) >= 2:
                lang = args[1]
                mpq_path = str(workspace_dir() / "MPQ_Data" / f"{lang}-MPQ")
                target = args[args.index("--target") + 1] if "--target" in args else None
                source = args[args.index("--source") + 1] if "--source" in args else None
                online = "--no-online" not in args
                ok = run_region(mpq_path, lang, log, target_dir=target, allow_online=online,
                                source_dir=source,
                                missing_fallback="empty" if ("--empty" in args and not online) else "english",
                                auto_patch="--install" in args)
                if ok and target and "--install" in args:
                    ok = install_patches(target, log)
                return 0 if ok else 1
            log(run_headless.__doc__)
            return 2
        except Exception:
            log(traceback.format_exc())
            return 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].startswith("--"):
        sys.exit(run_headless(sys.argv[1:]))
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)

    scene_widget = None
    if EditorMainWindow is not None and os.environ.get("WC3_PATCHER_NO_3D") != "1":
        try:
            # Initialize editor window FIRST
            Editorwindow = EditorMainWindow()
            # Force OpenGL context activation
            Editorwindow.opengl_widget.makeCurrent()
            # Load scene with built-in progress dialog
            Editorwindow.opengl_widget.load_scene(str(resource_path("test_scene.json")), parent=Editorwindow)
            scene_widget = Editorwindow.opengl_widget
        except Exception:
            _log_startup("3D scene disabled:\n" + traceback.format_exc())
            scene_widget = None
    elif EditorMainWindow is None:
        _log_startup(f"3D engine import failed: {OPENGL_IMPORT_ERROR!r}\n{OPENGL_IMPORT_TRACE}")

    if scene_widget is None:
        hint = ""
        err = f"{OPENGL_IMPORT_ERROR}" if OPENGL_IMPORT_ERROR else ""
        if "206" in err or "trop long" in err or "too long" in err or len(str(resource_path())) > 150:
            hint = ("\n\n3D background unavailable: the folder path is too long for Windows.\n"
                    "Move the WC3LanguagePatcher folder somewhere shorter (e.g. C:\\WC3Patcher).")
        scene_widget = QLabel("WC3 Localization Patcher" + hint)
        scene_widget.setAlignment(Qt.AlignCenter)
        scene_widget.setStyleSheet("background-color: #10131a; color: #c8a24a; font-size: 28px; font-weight: bold;")

    # Create patcher window
    window = CustomMainWindow(EditorOpenGLwidget=scene_widget)
    window.show()

    # Never fail silently: unexpected errors go to the console and patcher.log
    def _excepthook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        _log_startup("Unexpected error:\n" + text)
        try:
            window.log_message(f"⛔ Unexpected error: {exc}\n{text}")
            window.set_ui_enabled(True)
        except Exception:
            pass
    sys.excepthook = _excepthook

    sys.exit(app.exec_())