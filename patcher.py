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

from app_paths import resource_path, resource_dir, workspace_dir

os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'

# Language codes list (ISO 639-1)
LANGUAGE_CODES = sorted([
    "enUS", "esES", "frFR", "deDE", "itIT", "plPL", "ruRU", "zhCN", "zhTW", "koKR", "csCZ"
])

from PyQt5.QtCore import QThread, pyqtSignal
from io import StringIO

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
from __Misc_Tools.casc_reader.casc import CASCStorage, extract_locale, present_locales


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

    def __init__(self, mpq_path, lang, allow_online=False):
        super().__init__()
        self.mpq_path = mpq_path
        self.lang = lang
        self.allow_online = allow_online
        self.last_progress = ""

    def run(self):
        def progress_callback(message):
            self.progress.emit(message)
            self.last_progress = message

        try:
            result = convert_mpq_to_casc(
                region_folder_path=self.mpq_path,
                progress_callback=progress_callback,
                structure_file=resource_path("__Misc_Tools", "mpq_to_casc_converter", "structure.txt"),
            )
            if result:
                build_patch_for_region(
                    progress_callback=progress_callback,
                    mpq_to_casc_path=self.mpq_path + "-converted-to-CASC",
                    workspace_dir=workspace_dir(),
                    resource_dir=resource_dir(),
                    allow_online_translation=self.allow_online,
                )
        except Exception as e:
            self.error.emit(f"  | ⛔ Unexpected error for {self.lang}: {e}")
            self.error.emit(traceback.format_exc())
        finally:
            self.finished.emit()


class CascImporter(QThread):
    """Extracts one locale of a modern install into CASC_Data/<lang>.w3mod."""
    progress = pyqtSignal(str)
    done = pyqtSignal(bool)

    def __init__(self, game_dir, lang):
        super().__init__()
        self.game_dir = game_dir
        self.lang = lang

    def run(self):
        ok = False
        try:
            ok = import_casc_locale(self.game_dir, self.lang, self.progress.emit)
        except Exception as e:
            self.progress.emit(f"  | ⛔ CASC import failed: {e}")
        self.done.emit(ok)


class InstallImporter(QThread):
    """Extracts the 4 archives of a 1.27 install into MPQ_Data/<lang>-MPQ."""
    progress = pyqtSignal(str)
    done = pyqtSignal(bool)

    def __init__(self, install_dir, region_dir):
        super().__init__()
        self.install_dir = install_dir
        self.region_dir = region_dir

    def run(self):
        ok = False
        try:
            for name in ARCHIVES:
                target = Path(self.region_dir) / name
                if target.exists():
                    shutil.rmtree(target)
            results = extract_install(self.install_dir, self.region_dir, log=self.progress.emit)
            failed = sum(len(f) for _, f in results.values())
            if failed:
                self.progress.emit(f"  | ⚠️ {failed} file(s) could not be extracted")
            ok = True
        except Exception as e:
            self.progress.emit(f"  | ⛔ Import failed: {e}")
        self.done.emit(ok)

class CustomMainWindow(QMainWindow):
    def __init__(self, EditorOpenGLwidget):
        super().__init__()
        self.setWindowTitle("WC3 Localization Patcher")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(800, 600)  # Prevent window from becoming too small
        
        self.settings = QSettings("Mashiro", "WC3LocalizationPatcher")
        
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
        
        # Language Selection Group
        lang_group = QGroupBox("Language Configuration")
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("Language:"), 0)
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(LANGUAGE_CODES)
        lang_layout.addWidget(self.lang_combo, 1)  # Stretch factor 1
        self.add_button = QPushButton("+")
        self.add_button.setFixedSize(25, 25)
        self.remove_button = QPushButton("-")
        self.remove_button.setFixedSize(25, 25)
        lang_layout.addWidget(self.add_button)
        lang_layout.addWidget(self.remove_button)
        lang_group.setLayout(lang_layout)
        right_layout.addWidget(lang_group)

        # Import a 1.27 install directly (replaces the manual MPQ Editor step)
        self.import_button = QPushButton("Import 1.27 install folder for selected language...")
        self.import_button.setToolTip(
            "Pick a Warcraft III 1.27 folder containing war3.mpq, War3x.mpq, War3xlocal.mpq "
            "and War3Patch.mpq.\nThe archives are extracted to MPQ_Data automatically.")
        right_layout.addWidget(self.import_button)

        # Import a modern (1.30+) install directly (replaces the manual CascView step)
        self.casc_button = QPushButton("Import modern install folder (CASC) for selected language...")
        self.casc_button.setToolTip(
            "Pick a Warcraft III 1.30+ / Reforged folder (the one containing .build.info and Data).\n"
            "The selected language's locale is extracted to CASC_Data automatically.\n"
            "Only languages installed with the game are available.")
        right_layout.addWidget(self.casc_button)

        self.online_checkbox = QCheckBox("Online translation for strings without a bundled translation")
        self.online_checkbox.setToolTip(
            "Bundled translations are used first. If enabled, remaining strings are sent to free online\n"
            "translation services (may be rate-limited). If disabled, they stay in English.")
        right_layout.addWidget(self.online_checkbox)
        
        # Language Table
        self.lang_table = QTableWidget()
        self.lang_table.setColumnCount(4)
        self.lang_table.setHorizontalHeaderLabels(["Language", "Skip", "MPQ Path", "CASC Path"])
        self.lang_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.lang_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.lang_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.lang_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.lang_table.verticalHeader().setVisible(False)
        self.lang_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.lang_table.setSelectionMode(QTableWidget.SingleSelection)
        right_layout.addWidget(self.lang_table)
        
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
        
        # Create directories if needed
        self.mpq_base_path.mkdir(exist_ok=True)
        self.casc_base_path.mkdir(exist_ok=True)
        
        # Load saved settings
        self.selected_languages = self.detect_existing_languages()
        saved_langs = self.settings.value("selected_languages", [])
        for lang_data in saved_langs:
            lang = lang_data[0]
            if lang not in [item[0] for item in self.selected_languages]:
                self.selected_languages.append(tuple(lang_data))
        
        self.update_lang_table()
        
        # Connect signals
        self.add_button.clicked.connect(self.add_language)
        self.remove_button.clicked.connect(self.remove_language)
        self.patch_button.clicked.connect(self.patch_languages)
        self.import_button.clicked.connect(self.import_install)
        self.casc_button.clicked.connect(self.import_casc)

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
        right_layout.insertWidget(1, volume_group)  # Insert after language group
        
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
        lang_codes_lower = {code.lower() for code in LANGUAGE_CODES}
        
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
            
            mpq_subdirs = ["war3.mpq", "war3x.mpq", "war3xlocal.mpq", "War3Patch.mpq"]
            for subdir in mpq_subdirs:
                full_path = os.path.join(mpq_path, subdir)
                os.makedirs(full_path, exist_ok=True)
                dummy_file = os.path.join(full_path, "placeholder.txt")
                if not os.path.exists(dummy_file):
                    with open(dummy_file, 'w') as f:
                        f.write("This directory is for Warcraft 3 localization files")
            
            os.makedirs(casc_path, exist_ok=True)
            dummy_file = os.path.join(casc_path, "placeholder.txt")
            if not os.path.exists(dummy_file):
                with open(dummy_file, 'w') as f:
                    f.write("This directory is for Warcraft 3 CASC files")
            
            rel_mpq_path = os.path.relpath(mpq_path, self.base_path)
            rel_casc_path = os.path.relpath(casc_path, self.base_path)
            
            self.selected_languages.append((lang, False, rel_mpq_path, rel_casc_path))
            self.update_lang_table()
            self.log_message(f"Added language: {lang}")
            self.log_message(f"Created MPQ structure at: {rel_mpq_path}")
            self.log_message(f"Created CASC structure at: {rel_casc_path}")
            self.save_settings()

    def remove_language(self):
        selected_row = self.lang_table.currentRow()
        if selected_row >= 0:
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
            mpq_item = QTableWidgetItem(rel_mpq_path)
            casc_item = QTableWidgetItem(rel_casc_path)
            
            mpq_path = os.path.join(self.base_path, rel_mpq_path)
            casc_path = os.path.join(self.base_path, rel_casc_path)
            mpq_exists = os.path.exists(mpq_path)
            casc_exists = os.path.exists(casc_path)
            has_missing_path = not (mpq_exists and casc_exists)
            
            if has_missing_path:
                orange_color = QColor(255, 165, 0)
                for item in [lang_item, mpq_item, casc_item]:
                    item.setBackground(orange_color)
            
            self.lang_table.setItem(i, 0, lang_item)
            
            chk = QCheckBox()
            chk.setChecked(ignore)
            chk.stateChanged.connect(lambda state, row=i: self.toggle_ignore(row, state))
            if has_missing_path:
                chk.setStyleSheet("background-color: rgb(255, 165, 0);")
            self.lang_table.setCellWidget(i, 1, chk)
            
            mpq_btn = QPushButton("Open MPQ")
            mpq_btn.setEnabled(mpq_exists)
            if not mpq_exists:
                mpq_btn.setStyleSheet("color: gray;")
            mpq_btn.clicked.connect(lambda _, path=mpq_path: self.show_in_explorer(path))
            self.lang_table.setCellWidget(i, 2, mpq_btn)
            self.lang_table.setItem(i, 2, mpq_item)
            
            casc_btn = QPushButton("Open CASC")
            casc_btn.setEnabled(casc_exists)
            if not casc_exists:
                casc_btn.setStyleSheet("color: gray;")
            casc_btn.clicked.connect(lambda _, path=casc_path: self.show_in_explorer(path))
            self.lang_table.setCellWidget(i, 3, casc_btn)
            self.lang_table.setItem(i, 3, casc_item)
        
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
            
        self.log_message("Starting patch process...")
        
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
        self.import_button.setEnabled(enabled)
        self.casc_button.setEnabled(enabled)
        self.add_button.setEnabled(enabled)
        self.remove_button.setEnabled(enabled)
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
            self.set_ui_enabled(True)
            self.log_message("Patch completed for selected languages!")
            self.log_message("")
            return
        
        lang, rel_mpq_path = self.languages_to_process.pop(0)
        mpq_path = os.path.join(self.base_path, rel_mpq_path)
        
        self.log_message(f"\nProcessing language: {lang}")
        self.log_message(f"MPQ Path: {rel_mpq_path}")
        
        # Create and start worker
        self.worker = RegionProcessor(mpq_path, lang, allow_online=self.online_checkbox.isChecked())
        self.worker.progress.connect(self.log_message)
        self.worker.error.connect(self.log_message)
        self.worker.finished.connect(self.process_next_language)
        self.worker.start()

    def import_install(self):
        lang = self.lang_combo.currentText()
        folder = QFileDialog.getExistingDirectory(
            self, f"Select the Warcraft III 1.27 folder for {lang} (contains war3.mpq)")
        if not folder:
            return
        found = find_archives(folder)
        missing = [a for a in ARCHIVES if a not in found]
        if missing:
            QMessageBox.warning(self, "Archives not found",
                                "These archives are missing in the selected folder:\n" + ", ".join(missing))
            return
        if lang not in [item[0] for item in self.selected_languages]:
            self.add_language()
        region_dir = self.mpq_base_path / f"{lang}-MPQ"
        for leftover in region_dir.glob("*/placeholder.txt"):
            leftover.unlink()
        self.log_message(f"\nImporting 1.27 archives for {lang} from: {folder}")
        self.set_ui_enabled(False)
        self.importer = InstallImporter(folder, region_dir)
        self.importer.progress.connect(self.log_message)
        self.importer.done.connect(self.import_finished)
        self.importer.start()

    def import_casc(self):
        lang = self.lang_combo.currentText()
        folder = QFileDialog.getExistingDirectory(
            self, "Select the modern Warcraft III folder (contains .build.info and Data)")
        if not folder:
            return
        if not (Path(folder) / ".build.info").exists() or not (Path(folder) / "Data").is_dir():
            QMessageBox.warning(self, "Not a CASC install",
                                "This folder has no .build.info / Data folder.\n"
                                "Select the Warcraft III folder of a 1.30+ or Reforged install.")
            return
        try:
            storage = CASCStorage(folder)
            stats = present_locales(storage)
            version = storage.version
            storage.close()
        except Exception as e:
            QMessageBox.warning(self, "Cannot read install", f"Could not read this install:\n{e}")
            return
        match = next((k for k in stats if k.lower() == lang.lower()), None)
        installed = [k for k, (present, total) in stats.items() if total and present / total > 0.9]
        if match is None or stats[match][0] == 0:
            QMessageBox.warning(self, "Language not installed",
                                f"{lang} is not stored in this install (version {version}).\n"
                                f"Fully installed language(s): {', '.join(installed) or 'none'}")
            return
        present, total = stats[match]
        if present < total:
            reply = QMessageBox.question(
                self, "Partial language data",
                f"Only {present} of {total} {lang} files are installed locally "
                f"(fully installed: {', '.join(installed) or 'none'}).\nImport the available files anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
        if lang not in [item[0] for item in self.selected_languages]:
            self.add_language()
        placeholder = casc_locale_folder(lang) / "placeholder.txt"
        if placeholder.exists():
            placeholder.unlink()
        self.log_message(f"\nImporting {lang} locale from Warcraft III {version}: {folder}")
        self.set_ui_enabled(False)
        self.casc_importer = CascImporter(folder, match)
        self.casc_importer.progress.connect(self.log_message)
        self.casc_importer.done.connect(self.import_finished)
        self.casc_importer.start()

    def import_finished(self, ok):
        self.set_ui_enabled(True)
        self.update_lang_table()
        self.log_message("✅ Import finished, you can now build the patch." if ok else "⛔ Import failed.")

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
        WC3LanguagePatcher.exe --build <lang> [--online]
    Output goes to patcher.log in the workspace folder."""
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
                result = convert_mpq_to_casc(
                    mpq_path, log,
                    structure_file=resource_path("__Misc_Tools", "mpq_to_casc_converter", "structure.txt"))
                if not result:
                    return 1
                ok = build_patch_for_region(log, mpq_path + "-converted-to-CASC",
                                            workspace_dir=workspace_dir(), resource_dir=resource_dir(),
                                            allow_online_translation="--online" in args)
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
        if "206" in err or "trop long" in err or "too long" in err or len(str(resource_dir())) > 150:
            hint = ("\n\n3D background unavailable: the folder path is too long for Windows.\n"
                    "Move the WC3LanguagePatcher folder somewhere shorter (e.g. C:\\WC3Patcher).")
        scene_widget = QLabel("WC3 Localization Patcher" + hint)
        scene_widget.setAlignment(Qt.AlignCenter)
        scene_widget.setStyleSheet("background-color: #10131a; color: #c8a24a; font-size: 28px; font-weight: bold;")

    # Create patcher window
    window = CustomMainWindow(EditorOpenGLwidget=scene_widget)
    window.show()
    
    sys.exit(app.exec_())