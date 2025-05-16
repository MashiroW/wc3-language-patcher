import sys
import os
import math
import numpy as np
import time
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QComboBox, QTableWidget, QTableWidgetItem, 
                             QTextEdit, QSplitter, QCheckBox, QMessageBox, QFileDialog, QHeaderView)
from PyQt5.QtCore import Qt, QTimer, QSettings, QTime
from PyQt5.QtGui import QSurfaceFormat, QColor
from OpenGL.GL import *
from OpenGL.GLU import *
from PyQt5.QtOpenGL import QGLWidget
from OpenGL.arrays import vbo

# Language codes list (ISO 639-1)
LANGUAGE_CODES = [
    "en", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ko",
    "ar", "hi", "bn", "pa", "ta", "te", "mr", "ur", "tr", "nl"
]

class TextModel:
    def __init__(self):
        self.vbo = None
        self.nbo = None
        self.ibo = None
        self.num_indices = 0
        
    def load_from_obj(self, obj_content):
        vertices = []
        normals = []
        faces = []
        
        lines = obj_content.split('\n')
        for line in lines:
            if line.startswith('v '):
                vertices.append(list(map(float, line[2:].strip().split())))
            elif line.startswith('vn '):
                normals.append(list(map(float, line[3:].strip().split())))
            elif line.startswith('f '):
                face = []
                for v in line[2:].strip().split():
                    parts = v.split('/')
                    vertex_index = int(parts[0]) - 1 if parts[0] else -1
                    normal_index = int(parts[2]) - 1 if len(parts) > 2 and parts[2] else -1
                    face.append((vertex_index, normal_index))
                faces.append(face)
        
        # Convert to numpy arrays
        vertices = np.array(vertices, dtype='float32')
        normals = np.array(normals, dtype='float32')
        
        # Create index array
        indices = []
        for face in faces:
            for vertex_idx, normal_idx in face:
                indices.append(vertex_idx)
        indices = np.array(indices, dtype='uint32')
        
        # Create VBOs
        self.vbo = vbo.VBO(vertices)
        self.nbo = vbo.VBO(normals)
        self.ibo = vbo.VBO(indices, target=GL_ELEMENT_ARRAY_BUFFER)
        self.num_indices = len(indices)
    
    def render(self):
        if not self.vbo or not self.nbo or not self.ibo:
            return
            
        self.vbo.bind()
        glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointer(3, GL_FLOAT, 0, self.vbo)
        
        self.nbo.bind()
        glEnableClientState(GL_NORMAL_ARRAY)
        glNormalPointer(GL_FLOAT, 0, self.nbo)
        
        self.ibo.bind()
        glDrawElements(GL_TRIANGLES, self.num_indices, GL_UNSIGNED_INT, None)
        
        self.ibo.unbind()
        self.nbo.unbind()
        self.vbo.unbind()
        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_NORMAL_ARRAY)

class OpenGLWidget(QGLWidget):
    def __init__(self, parent=None):
        super(OpenGLWidget, self).__init__(parent)
        self.rotation = 0
        self.text_rotation = 0
        self.text_offset = 0
        self.text_direction = 0.01
        self.wc3_model = TextModel()
        self.mashiro_model = TextModel()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(16)  # ~60 FPS
        self.last_time = time.time()
        self.frame_count = 0
        self.fps = 0
        self.cube_dl = None

    def initializeGL(self):
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LEQUAL)
        glEnable(GL_CULL_FACE)
        glCullFace(GL_BACK)
        
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glLightfv(GL_LIGHT0, GL_POSITION, [1, 1, 1, 0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [1.0, 1.0, 1.0, 1.0])
        glMaterialfv(GL_FRONT, GL_AMBIENT_AND_DIFFUSE, [0.2, 0.5, 0.8, 1.0])
        glClearColor(0.1, 0.1, 0.2, 1.0)
        
        # Load WC3 model
        wc3_obj = """
v 0.0 0.0 0.0
v 0.3 1.0 0.0
v 0.7 1.0 0.0
v 1.0 0.0 0.0
v 0.0 0.0 0.1
v 0.3 1.0 0.1
v 0.7 1.0 0.1
v 1.0 0.0 0.1
vn 0.0 0.0 -1.0
vn 0.0 0.0 1.0
vn -0.8 -0.6 0.0
vn 0.8 -0.6 0.0
f 1//1 2//1 3//1
f 1//1 3//1 4//1
f 5//2 6//2 7//2
f 5//2 7//2 8//2
f 1//3 5//3 2//3
f 2//3 6//3 3//3
f 3//3 7//3 4//3
f 4//3 8//3 1//3
v 1.5 0.0 0.0
v 1.8 0.0 0.0
v 1.8 1.0 0.0
v 1.5 1.0 0.0
v 1.5 0.0 0.1
v 1.8 0.0 0.1
v 1.8 1.0 0.1
v 1.5 1.0 0.1
vn 0.0 0.0 -1.0
vn 0.0 0.0 1.0
vn -1.0 0.0 0.0
vn 1.0 0.0 0.0
f 9//1 10//1 11//1
f 9//1 11//1 12//1
f 13//2 14//2 15//2
f 13//2 15//2 16//2
f 9//3 13//3 10//3
f 10//3 14//3 11//3
f 11//3 15//3 12//3
f 12//3 16//3 9//3
v 2.1 0.0 0.0
v 2.4 0.0 0.0
v 2.4 1.0 0.0
v 2.1 1.0 0.0
v 2.1 0.0 0.1
v 2.4 0.0 0.1
v 2.4 1.0 0.1
v 2.1 1.0 0.1
vn 0.0 0.0 -1.0
vn 0.0 0.0 1.0
f 17//1 18//1 19//1
f 17//1 19//1 20//1
f 21//2 22//2 23//2
f 21//2 23//2 24//2
f 17//3 21//3 18//3
f 18//3 22//3 19//3
f 19//3 23//3 20//3
f 20//3 24//3 17//3
"""
        self.wc3_model.load_from_obj(wc3_obj)

        # Load Mashiro model from file
        obj_path = os.path.join(os.path.dirname(__file__), "models", "by_mashiro.obj")
        if os.path.exists(obj_path):
            try:
                with open(obj_path, 'r') as f:
                    obj_content = f.read()
                self.mashiro_model.load_from_obj(obj_content)
            except Exception as e:
                print(f"Error loading OBJ file: {e}")
                self._create_fallback_mashiro_model()
        else:
            print(f"OBJ file not found at: {obj_path}")
            self._create_fallback_mashiro_model()

        # Create display list for cube
        self.cube_dl = glGenLists(1)
        glNewList(self.cube_dl, GL_COMPILE)
        self._draw_cube_geometry()
        glEndList()

    def _create_fallback_mashiro_model(self):
        """Create a simple fallback model if OBJ file is missing"""
        mashiro_obj = """
v 0.0 0.0 0.0
v 0.3 0.0 0.0
v 0.3 1.0 0.0
v 0.0 1.0 0.0
v 0.0 0.0 0.1
v 0.3 0.0 0.1
v 0.3 1.0 0.1
v 0.0 1.0 0.1
vn 0.0 0.0 -1.0
vn 0.0 0.0 1.0
vn -1.0 0.0 0.0
vn 1.0 0.0 0.0
f 1//1 2//1 3//1
f 1//1 3//1 4//1
f 5//2 6//2 7//2
f 5//2 7//2 8//2
f 1//3 5//3 2//3
f 2//3 6//3 3//3
f 3//3 7//3 4//3
f 4//3 8//3 1//3
"""
        self.mashiro_model.load_from_obj(mashiro_obj)

    def _draw_cube_geometry(self):
        vertices = [
            [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],  # Front
            [-1, -1, -1], [-1, 1, -1], [1, 1, -1], [1, -1, -1],  # Back
            [-1, 1, -1], [-1, 1, 1], [1, 1, 1], [1, 1, -1],  # Top
            [-1, -1, -1], [1, -1, -1], [1, -1, 1], [-1, -1, 1],  # Bottom
            [1, -1, -1], [1, 1, -1], [1, 1, 1], [1, -1, 1],  # Right
            [-1, -1, -1], [-1, -1, 1], [-1, 1, 1], [-1, 1, -1]  # Left
        ]
        
        normals = [
            [0, 0, 1], [0, 0, 1], [0, 0, 1], [0, 0, 1],  # Front
            [0, 0, -1], [0, 0, -1], [0, 0, -1], [0, 0, -1],  # Back
            [0, 1, 0], [0, 1, 0], [0, 1, 0], [0, 1, 0],  # Top
            [0, -1, 0], [0, -1, 0], [0, -1, 0], [0, -1, 0],  # Bottom
            [1, 0, 0], [1, 0, 0], [1, 0, 0], [1, 0, 0],  # Right
            [-1, 0, 0], [-1, 0, 0], [-1, 0, 0], [-1, 0, 0]  # Left
        ]
        
        indices = [
            0,1,2, 0,2,3,  # Front
            4,5,6, 4,6,7,  # Back
            8,9,10, 8,10,11,  # Top
            12,13,14, 12,14,15,  # Bottom
            16,17,18, 16,18,19,  # Right
            20,21,22, 20,22,23  # Left
        ]
        
        glBegin(GL_TRIANGLES)
        for i in indices:
            glNormal3fv(normals[i])
            glVertex3fv(vertices[i])
        glEnd()

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, w/h, 0.1, 100.0)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        current_time = time.time()
        self.frame_count += 1
        
        # Calculate FPS every second
        if current_time - self.last_time >= 1.0:
            self.fps = self.frame_count
            self.frame_count = 0
            self.last_time = current_time
            print(f"FPS: {self.fps}")
            
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        gluLookAt(3, 3, 3, 0, 0, 0, 0, 1, 0)
        
        glPushMatrix()
        glRotatef(self.rotation, 1, 1, 1)
        glCallList(self.cube_dl)
        glPopMatrix()
        
        glPushMatrix()
        glTranslatef(0, 1.5, 0)
        glRotatef(self.text_rotation, 0, 1, 0)
        glTranslatef(0, self.text_offset, 0)
        self.render_wc3_text(-1.5, 0, 0, 0.2)
        
        glPushMatrix()
        glTranslatef(0.5, -0.3, 0.5)
        glRotatef(45, 0, 1, 0)
        glScalef(0.5, 0.5, 0.5)
        self.render_mashiro_text(0, 0, 0, 0.01)
        glPopMatrix()
        glPopMatrix()

    def render_wc3_text(self, x, y, z, scale):
        glPushMatrix()
        glTranslatef(x, y, z)
        glScalef(scale, scale, scale)
        glColor3f(0.8, 0.8, 0.2)
        self.wc3_model.render()
        glPopMatrix()

    def render_mashiro_text(self, x, y, z, scale):
        glPushMatrix()
        glTranslatef(x, y, z)
        glScalef(scale, scale, scale)
        glColor3f(0.8, 0.8, 0.2)
        self.mashiro_model.render()
        glPopMatrix()

    def update_animation(self):
        self.rotation = (self.rotation + 1) % 360
        self.text_rotation = (self.text_rotation + 0.5) % 360
        
        self.text_offset += self.text_direction
        if abs(self.text_offset) > 0.2:
            self.text_direction *= -1
            
        self.update()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WC3 Localization Patcher")
        self.setGeometry(100, 100, 1200, 800)
        
        self.settings = QSettings("Mashiro", "WC3LocalizationPatcher")
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        splitter = QSplitter(Qt.Horizontal)
        
        self.gl_widget = OpenGLWidget()
        splitter.addWidget(self.gl_widget)
        
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
    # Set OpenGL format
    fmt = QSurfaceFormat()
    fmt.setSamples(4)  # 4x MSAA
    fmt.setSwapInterval(1)  # Enable VSync for smoother rendering
    QSurfaceFormat.setDefaultFormat(fmt)
    
    # Suppress QT_DEVICE_PIXEL_RATIO warning
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
