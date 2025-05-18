# Standard Library
import sys
import os
import json
import math
import random
import time
from pathlib import Path
from collections import OrderedDict

# Third-party
import numpy as np
from PIL import Image

# PyQt5
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtOpenGL import QGLWidget

# OpenGL
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.arrays import vbo

# Get current script's directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Add to Python path (insert at beginning for priority)
sys.path.insert(0, current_dir)

try:
    from OpenGLWorldEditor import OpenGLWidget, ModelObject, LightObject, StarBackground, MainWindow
    print("Successfully imported all classes!")
except ImportError as e:
    print(f"Import failed: {e}")
    print(f"Current sys.path: {sys.path}")
    print(f"Files in directory: {os.listdir(current_dir)}")

os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'

# Language codes list (ISO 639-1)
LANGUAGE_CODES = [
    "en", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ko",
    "ar", "hi", "bn", "pa", "ta", "te", "mr", "ur", "tr", "nl"
]

class CustomMainWindow(QMainWindow):
    def __init__(self, EditorOpenGLwidget):
        super().__init__()
        # Keep reference to original parent window
        self.editor_window = EditorOpenGLwidget.parent().window()  
        # Reparent while maintaining context
        EditorOpenGLwidget.setParent(self)  


        self.setWindowTitle("WC3 Localization Patcher")
        self.setGeometry(100, 100, 1200, 800)
        
        self.settings = QSettings("Mashiro", "WC3LocalizationPatcher")
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        splitter = QSplitter(Qt.Horizontal)
        
        self.opengl_widget = EditorOpenGLwidget
        splitter.addWidget(self.opengl_widget)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        
        lang_layout = QHBoxLayout()
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(LANGUAGE_CODES)
        lang_layout.addWidget(self.lang_combo)
        
        self.add_button = QPushButton("+")
        self.add_button.clicked.connect(self.add_language)
        lang_layout.addWidget(self.add_button)
        
        self.remove_button = QPushButton("-")
        self.remove_button.clicked.connect(self.remove_language)
        lang_layout.addWidget(self.remove_button)
        
        right_layout.addLayout(lang_layout)
        
        self.lang_table = QTableWidget()
        self.lang_table.setColumnCount(4)
        self.lang_table.setHorizontalHeaderLabels(["Language", "Ignore", "MPQ Path", "CASC Path"])
        self.lang_table.horizontalHeader().setStretchLastSection(True)
        self.lang_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.lang_table.setSelectionMode(QTableWidget.SingleSelection)
        right_layout.addWidget(self.lang_table)
        
        self.patch_button = QPushButton("BUILD PATCH")
        self.patch_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; font-size: 16px;")
        self.patch_button.clicked.connect(self.patch_languages)
        right_layout.addWidget(self.patch_button)
        
        self.console_log = QTextEdit()
        self.console_log.setReadOnly(True)
        right_layout.addWidget(self.console_log)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([700, 500])
        
        main_layout = QVBoxLayout()
        main_layout.addWidget(splitter)
        main_widget.setLayout(main_layout)
        
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.mpq_base_path = os.path.join(self.base_path, "MPQ_Data")
        self.casc_base_path = os.path.join(self.base_path, "CASC_Data")
        
        os.makedirs(self.mpq_base_path, exist_ok=True)
        os.makedirs(self.casc_base_path, exist_ok=True)
        
        self.selected_languages = self.detect_existing_languages()
        saved_langs = self.settings.value("selected_languages", [])
        for lang_data in saved_langs:
            lang = lang_data[0]
            if lang not in [item[0] for item in self.selected_languages]:
                self.selected_languages.append(tuple(lang_data))
        
        self.update_lang_table()

    def detect_existing_languages(self):
        detected_languages = []
        
        if os.path.exists(self.mpq_base_path):
            for item in os.listdir(self.mpq_base_path):
                if len(item) >= 4 and item.endswith("-mpq"):
                    lang_code = item[:2]
                    if lang_code in LANGUAGE_CODES:
                        mpq_path = os.path.join(self.mpq_base_path, item)
                        required_subdirs = {"war3.mpq", "war3x.mpq", "war3local.mpq", "War3Path.mpq"}
                        if all(os.path.exists(os.path.join(mpq_path, subdir)) for subdir in required_subdirs):
                            rel_mpq_path = os.path.relpath(mpq_path, self.base_path)
                            casc_dir = f"{lang_code}{lang_code}.war3mod"
                            casc_path = os.path.join(self.casc_base_path, casc_dir)
                            if os.path.exists(casc_path):
                                rel_casc_path = os.path.relpath(casc_path, self.base_path)
                                detected_languages.append((lang_code, False, rel_mpq_path, rel_casc_path))
        
        if os.path.exists(self.casc_base_path):
            for item in os.listdir(self.casc_base_path):
                if len(item) >= 4 and item.endswith(".war3mod"):
                    lang_code = item[:2]
                    if lang_code in LANGUAGE_CODES and lang_code not in [x[0] for x in detected_languages]:
                        casc_path = os.path.join(self.casc_base_path, item)
                        rel_casc_path = os.path.relpath(casc_path, self.base_path)
                        mpq_dir = f"{lang_code}{lang_code}-mpq"
                        mpq_path = os.path.join(self.mpq_base_path, mpq_dir)
                        rel_mpq_path = os.path.relpath(mpq_path, self.base_path)
                        detected_languages.append((lang_code, False, rel_mpq_path, rel_casc_path))
        
        return detected_languages

    def add_language(self):
        lang = self.lang_combo.currentText()
        if lang not in [item[0] for item in self.selected_languages]:
            mpq_path = os.path.join(self.mpq_base_path, f"{lang}{lang}-mpq")
            casc_path = os.path.join(self.casc_base_path, f"{lang}{lang}.war3mod")
            
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
                    if os.path.exists(mpq_path):
                        for root, dirs, files in os.walk(mpq_path):
                            for file in files:
                                os.remove(os.path.join(root, file))
                        for root, dirs, _ in os.walk(mpq_path, topdown=False):
                            for dir in dirs:
                                os.rmdir(os.path.join(root, dir))
                        os.rmdir(mpq_path)
                    
                    if os.path.exists(casc_path):
                        for root, dirs, files in os.walk(casc_path):
                            for file in files:
                                os.remove(os.path.join(root, file))
                        for root, dirs, _ in os.walk(casc_path, topdown=False):
                            for dir in dirs:
                                os.rmdir(os.path.join(root, dir))
                        os.rmdir(casc_path)
                    
                    self.log_message(f"Deleted all files for language: {lang}")
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
        for lang, ignore, rel_mpq_path, rel_casc_path in self.selected_languages:
            if ignore:
                self.log_message(f"Ignoring language: {lang} (marked to ignore)")
                continue
                
            mpq_path = os.path.join(self.base_path, rel_mpq_path)
            casc_path = os.path.join(self.base_path, rel_casc_path)
            
            self.log_message(f"Patching language: {lang}")
            self.log_message(f"  - MPQ Path: {rel_mpq_path}")
            self.log_message(f"  - CASC Path: {rel_casc_path}")
            
            QApplication.processEvents()
        
        self.log_message("Patch completed for selected languages!")
        self.log_message("")

    def save_settings(self):
        serializable = [(lang, ignore, mpq, casc) for lang, ignore, mpq, casc in self.selected_languages]
        self.settings.setValue("selected_languages", serializable)

    def log_message(self, message):
        self.console_log.append(message)
        self.console_log.ensureCursorVisible()

if __name__ == "__main__":
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    
    # Initialize editor window FIRST
    Editorwindow = MainWindow()
    #Editorwindow.show()
    
    # Force OpenGL context activation
    Editorwindow.opengl_widget.makeCurrent()
    Editorwindow.opengl_widget.load_scene("test_scene.json")
    #Editorwindow.hide()  # Optional
    
    # Create patcher window with proper context handling
    window = CustomMainWindow(EditorOpenGLwidget=Editorwindow.opengl_widget)
    window.show()
    
    sys.exit(app.exec_())