# Standard Library
import sys
import os
import shutil
from pathlib import Path

# Third-party
import re

# PyQt5
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtMultimedia import QMediaPlayer, QMediaPlaylist, QMediaContent
from PyQt5.QtCore import QUrl

# OpenGL
from OpenGL.GL import *
from OpenGL.GLU import *

# Get current script's directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Add to Python path (insert at beginning for priority)
sys.path.insert(0, current_dir)

# Create __init__.py files if missing
misc_tools_dirs = [
    os.path.join(current_dir, "__Misc_Tools"),
    os.path.join(current_dir, "__Misc_Tools", "patches_maker"),
    os.path.join(current_dir, "__Misc_Tools", "mpq_to_casc_converter"),
    os.path.join(current_dir, "__Misc_Tools", "campaignstrings_translator"),
    os.path.join(current_dir, "__Misc_Tools", "worldeditor_translator")
]

for directory in misc_tools_dirs:
    init_path = os.path.join(directory, "__init__.py")
    # Create directory if it doesn't exist
    if not os.path.exists(directory):
        os.makedirs(directory)
    # Create __init__.py if it doesn't exist
    if not os.path.exists(init_path):
        with open(init_path, 'w') as f:
            pass  # create empty file

os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'

# Language codes list (ISO 639-1)
LANGUAGE_CODES = sorted([
    "enUS", "esES", "frFR", "deDE", "itIT", "plPL", "ruRU", "zhCN", "koKR", "csCZ"
])

from PyQt5.QtCore import QThread, pyqtSignal
from io import StringIO

from OpenGLWorldEditor import OpenGLWidget, ModelObject, LightObject, StarBackground, MainWindow

# Import patches_maker with correct path
sys.path.append(os.path.join(current_dir, "__Misc_Tools", "patches_maker"))
from __Misc_Tools.patches_maker.patches_maker import build_patch_for_region

# Import mpq_to_casc_converter
sys.path.append(os.path.join(current_dir, "__Misc_Tools", "mpq_to_casc_converter"))
from __Misc_Tools.mpq_to_casc_converter.mpq_to_casc_converter import convert_mpq_to_casc

class RegionProcessor(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, mpq_path, lang):
        super().__init__()
        self.mpq_path = mpq_path
        self.lang = lang
        self.last_progress = ""

    def run(self):
        # Define progress callback that emits to main thread
        def progress_callback(message):
            self.progress.emit(message)
            self.last_progress = message

        # Process the region with our callback
        convert_mpq_to_casc(
            region_folder_path=self.mpq_path,
            progress_callback=progress_callback
        )

        # Create patch for this region
        build_patch_for_region(
            progress_callback=progress_callback,
            mpq_to_casc_path=self.mpq_path + "-converted-to-CASC",
        )

        # Emit final result
        self.finished.emit()

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
        
        # Initialize paths and data
        self.base_path = Path(__file__).parent.absolute()
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
        try:
            # Create two media players
            self.intro_player = QMediaPlayer()
            self.loop_player = QMediaPlayer()
            
            # Load audio files
            intro_path = os.path.join(current_dir, "./music/COE33 OST Flying Waters - Goblu part01.mp3")
            loop_path = os.path.join(current_dir, "./music/COE33 OST Flying Waters - Goblu part02.mp3")
            
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
        self.intro_player.setVolume(value)
        self.loop_player.setVolume(value)

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
                        required_subdirs = {"war3.mpq", "war3x.mpq", "war3local.mpq", "War3Path.mpq"}
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
            
            mpq_subdirs = ["war3.mpq", "war3x.mpq", "war3local.mpq", "War3Path.mpq"]
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

    def launch_other_script(self, path, name, args):

        # Run Script B and capture its output
        process = subprocess.Popen(
            ["python", os.path.join(path, name), args],   # Command to run Script B
            stdout=subprocess.PIPE,      # Capture stdout
            stderr=subprocess.PIPE,      # Capture stderr
            universal_newlines=True,     # Ensure text mode
            shell=False,                 # Avoid shell (prevents extra console on Windows)
            creationflags=subprocess.CREATE_NO_WINDOW if subprocess.sys.platform == "win32" else 0  # Hide console on Windows
        )

        # Read and print Script B's output in real-time
        while True:
            stdout_line = process.stdout.readline()
            if stdout_line:
                self.log_message(f"[{name}] {stdout_line.strip()}")
            stderr_line = process.stderr.readline()
            if stderr_line:
                self.log_message(f"[{name} ERROR] {stderr_line.strip()}")
            if process.poll() is not None:  # Check if process has finished
                break

        # Optional: Get remaining output after process exits
        remaining_stdout, remaining_stderr = process.communicate()
        if remaining_stdout:
            self.log_message(f"[patches_maker] {remaining_stdout.strip()}")
        if remaining_stderr:
            self.log_message(f"[patches_maker ERROR] {remaining_stderr.strip()}")

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
        self.worker = RegionProcessor(mpq_path, lang)
        self.worker.progress.connect(self.log_message)
        self.worker.error.connect(self.log_message)
        self.worker.finished.connect(self.process_next_language)
        self.worker.start()

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

if __name__ == "__main__":
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    
    # Initialize editor window FIRST
    Editorwindow = MainWindow()
    
    # Force OpenGL context activation
    Editorwindow.opengl_widget.makeCurrent()
    
    # Load scene with built-in progress dialog
    Editorwindow.opengl_widget.load_scene("test_scene.json", parent=Editorwindow)
    
    # Create patcher window
    window = CustomMainWindow(EditorOpenGLwidget=Editorwindow.opengl_widget)
    window.show()
    
    sys.exit(app.exec_())