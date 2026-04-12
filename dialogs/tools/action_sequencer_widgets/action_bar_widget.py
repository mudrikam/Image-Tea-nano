from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QFileDialog, QApplication, QMessageBox
from PySide6.QtCore import Signal
import qtawesome as qta
import os
import subprocess
import platform

from ui.theme_system import theme


class ActionBarWidget(QWidget):
    load_from_database_requested = Signal()
    select_source_requested = Signal()
    select_file_requested = Signal()
    settings_requested = Signal()
    output_path_changed = Signal(str)
    source_path_changed = Signal(str)
    file_path_changed = Signal(str)
    reset_requested = Signal()
    clear_source_requested = Signal()
    get_free_presets_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.files_count = 0
        self.output_path = ""
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)
        
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        self.load_db_button = QPushButton(qta.icon('fa6s.database'), " Load Database")
        self.load_db_button.clicked.connect(self.on_load_from_database)
        buttons_layout.addWidget(self.load_db_button)

        self.settings_button = QPushButton(qta.icon('fa6s.gear'), " Settings")
        self.settings_button.clicked.connect(self.on_settings_clicked)
        buttons_layout.addWidget(self.settings_button)

        self.clear_source_button = QPushButton(qta.icon('fa6s.broom'), " Clear Source")
        self.clear_source_button.setEnabled(False)
        self.clear_source_button.clicked.connect(self.on_clear_source_clicked)
        buttons_layout.addWidget(self.clear_source_button)

        self.reset_button = QPushButton(qta.icon('fa6s.rotate-left'), " Clear All")
        self.reset_button.clicked.connect(self.on_reset_clicked)
        buttons_layout.addWidget(self.reset_button)

        self.get_free_button = QPushButton(qta.icon('fa6s.gift', color=theme.get_color('primary')), " Get FREE Presets")
        self.get_free_button.setToolTip("Get free presets from remote repository")
        self.get_free_button.clicked.connect(self.on_get_free_presets_clicked)
        buttons_layout.addWidget(self.get_free_button)
        
        buttons_layout.addStretch()
        
        main_layout.addLayout(buttons_layout)
        
        source_layout = QHBoxLayout()
        source_layout.setSpacing(8)
        source_icon = QLabel()
        source_icon.setPixmap(qta.icon('fa6s.folder-open', color=theme.get_color('gray')).pixmap(16, 16))
        source_layout.addWidget(source_icon)
        source_label = QLabel("Source:")
        source_label.setStyleSheet("font-weight: bold;")
        source_label.setMinimumWidth(50)
        source_layout.addWidget(source_label)
        self.source_path_input = QLineEdit()
        self.source_path_input.setPlaceholderText("Select source folder...")
        self.source_path_input.setReadOnly(False)
        self.source_path_input.editingFinished.connect(self.on_source_edited)
        source_layout.addWidget(self.source_path_input, 1)
        
        self.source_paste_button = QPushButton(qta.icon('fa6s.paste'), "")
        self.source_paste_button.setToolTip("Paste from clipboard")
        self.source_paste_button.setMaximumWidth(32)
        self.source_paste_button.clicked.connect(self.on_paste_source)
        source_layout.addWidget(self.source_paste_button)
        
        self.source_browse_button = QPushButton(qta.icon('fa6s.folder-open'), "")
        self.source_browse_button.setToolTip("Browse folder")
        self.source_browse_button.setMaximumWidth(32)
        self.source_browse_button.clicked.connect(self.on_select_source)
        source_layout.addWidget(self.source_browse_button)
        
        self.source_open_button = QPushButton(qta.icon('fa6s.arrow-up-right-from-square'), "")
        self.source_open_button.setToolTip("Open folder location")
        self.source_open_button.setMaximumWidth(32)
        self.source_open_button.clicked.connect(self.on_open_source)
        source_layout.addWidget(self.source_open_button)
        
        main_layout.addLayout(source_layout)

        file_layout = QHBoxLayout()
        file_layout.setSpacing(8)
        file_icon = QLabel()
        file_icon.setPixmap(qta.icon('fa6s.file', color=theme.get_color('gray')).pixmap(16, 16))
        file_layout.addWidget(file_icon)
        file_label = QLabel("File:")
        file_label.setStyleSheet("font-weight: bold;")
        file_label.setMinimumWidth(50)
        file_layout.addWidget(file_label)
        self.file_path_input = QLineEdit()
        self.file_path_input.setPlaceholderText("Select file...")
        self.file_path_input.setReadOnly(False)
        self.file_path_input.editingFinished.connect(self.on_file_edited)
        file_layout.addWidget(self.file_path_input, 1)
        
        self.file_paste_button = QPushButton(qta.icon('fa6s.paste'), "")
        self.file_paste_button.setToolTip("Paste from clipboard")
        self.file_paste_button.setMaximumWidth(32)
        self.file_paste_button.setEnabled(False)
        self.file_paste_button.clicked.connect(self.on_paste_file)
        file_layout.addWidget(self.file_paste_button)
        
        self.file_browse_button = QPushButton(qta.icon('fa6s.folder-open'), "")
        self.file_browse_button.setToolTip("Browse file")
        self.file_browse_button.setMaximumWidth(32)
        self.file_browse_button.setEnabled(False)
        self.file_browse_button.clicked.connect(self.on_select_file)
        file_layout.addWidget(self.file_browse_button)
        
        self.file_open_button = QPushButton(qta.icon('fa6s.arrow-up-right-from-square'), "")
        self.file_open_button.setToolTip("Open file location")
        self.file_open_button.setMaximumWidth(32)
        self.file_open_button.setEnabled(False)
        self.file_open_button.clicked.connect(self.on_open_file)
        file_layout.addWidget(self.file_open_button)
        
        main_layout.addLayout(file_layout)

        output_layout = QHBoxLayout()
        output_layout.setSpacing(8)
        
        output_icon = QLabel()
        output_icon.setPixmap(qta.icon('fa6s.folder', color=theme.get_color('gray')).pixmap(16, 16))
        output_layout.addWidget(output_icon)
        
        output_label = QLabel("Output:")
        output_label.setStyleSheet("font-weight: bold;")
        output_label.setMinimumWidth(50)
        output_layout.addWidget(output_label)
        
        self.output_path_input = QLineEdit()
        self.output_path_input.setPlaceholderText("Select output folder...")
        self.output_path_input.setReadOnly(False)
        self.output_path_input.editingFinished.connect(self.on_output_edited)
        output_layout.addWidget(self.output_path_input, 1)
        
        self.output_paste_button = QPushButton(qta.icon('fa6s.paste'), "")
        self.output_paste_button.setToolTip("Paste from clipboard")
        self.output_paste_button.setMaximumWidth(32)
        self.output_paste_button.clicked.connect(self.on_paste_output)
        output_layout.addWidget(self.output_paste_button)
        
        self.select_output_button = QPushButton(qta.icon('fa6s.folder-open'), "")
        self.select_output_button.setToolTip("Browse folder")
        self.select_output_button.setMaximumWidth(32)
        self.select_output_button.clicked.connect(self.on_select_output)
        output_layout.addWidget(self.select_output_button)
        
        self.output_open_button = QPushButton(qta.icon('fa6s.arrow-up-right-from-square'), "")
        self.output_open_button.setToolTip("Open folder location")
        self.output_open_button.setMaximumWidth(32)
        self.output_open_button.clicked.connect(self.on_open_output)
        output_layout.addWidget(self.output_open_button)
        
        main_layout.addLayout(output_layout)
        
        self.setLayout(main_layout)
    
    def on_load_from_database(self):
        self.load_from_database_requested.emit()
    
    def on_select_source(self):
        self.load_db_button.setEnabled(False)
        self.select_source_requested.emit()
    
    def on_select_file(self):
        self.select_file_requested.emit()

    def on_settings_clicked(self):
        self.settings_requested.emit()
    
    def on_clear_source_clicked(self):
        self.clear_source_requested.emit()

    def on_reset_clicked(self):
        self.set_output_path("")
        self.set_source_path("")
        self.set_file_path("")
        self.output_path_changed.emit("")
        self.reset_requested.emit()
    
    def on_get_free_presets_clicked(self):
        self.get_free_presets_requested.emit()
    
    def on_select_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder", self.output_path)
        if folder:
            folder = self._sanitize_path_text(folder)
            self.output_path = folder
            self.output_path_input.setText(folder)
            self.output_path_changed.emit(folder)

    def on_source_edited(self):
        path = self._sanitize_path_text(self.source_path_input.text())
        self.source_path = path
        self.source_path_changed.emit(path)
        self.clear_source_button.setEnabled(bool(path or getattr(self, 'selected_file', ''))) 

    def on_file_edited(self):
        path = self._sanitize_path_text(self.file_path_input.text())
        self.selected_file = path
        self.file_path_changed.emit(path)
        self.clear_source_button.setEnabled(bool(self.source_path_input.text() or path))

    def on_output_edited(self):
        path = self._sanitize_path_text(self.output_path_input.text())
        self.output_path = path
        self.output_path_changed.emit(path)
    
    def on_paste_source(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        sanitized = self._sanitize_path_text(text)
        if sanitized:
            self.source_path_input.setText(sanitized)
            self.source_path = sanitized
            self.source_path_changed.emit(sanitized)
    
    def on_paste_file(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        sanitized = self._sanitize_path_text(text)
        if sanitized:
            self.file_path_input.setText(sanitized)
            self.selected_file = sanitized
            self.file_path_changed.emit(sanitized)
    
    def on_paste_output(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        sanitized = self._sanitize_path_text(text)
        if sanitized:
            self.output_path_input.setText(sanitized)
            self.output_path = sanitized
            self.output_path_changed.emit(sanitized)
    
    def on_open_source(self):
        path = self._sanitize_path_text(self.source_path_input.text())
        if not path:
            QMessageBox.information(self, "No Path", "Please select or enter a source folder path first.")
            return
        
        if not os.path.exists(path):
            QMessageBox.warning(self, "Path Not Found", f"The path does not exist:\n{path}")
            return
        
        self._open_file_explorer(path)
    
    def on_open_file(self):
        path = self._sanitize_path_text(self.file_path_input.text())
        if not path:
            QMessageBox.information(self, "No Path", "Please select or enter a file path first.")
            return
        
        if not os.path.exists(path):
            QMessageBox.warning(self, "Path Not Found", f"The file does not exist:\n{path}")
            return
        
        folder_path = os.path.dirname(path)
        self._open_file_explorer(folder_path, select_file=path)
    
    def on_open_output(self):
        path = self._sanitize_path_text(self.output_path_input.text())
        if not path:
            QMessageBox.information(self, "No Path", "Please select or enter an output folder path first.")
            return
        
        if not os.path.exists(path):
            reply = QMessageBox.question(
                self,
                "Folder Not Found",
                f"The output folder does not exist:\n{path}\n\nDo you want to create it?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                os.makedirs(path, exist_ok=True)
                self._open_file_explorer(path)
            return
        
        self._open_file_explorer(path)
    
    def _open_file_explorer(self, path, select_file=None):
        system = platform.system()
        
        if system == "Windows":
            if select_file and os.path.isfile(select_file):
                subprocess.Popen(['explorer', '/select,', os.path.normpath(select_file)])
            else:
                subprocess.Popen(['explorer', os.path.normpath(path)])
        elif system == "Darwin":
            if select_file and os.path.isfile(select_file):
                subprocess.Popen(['open', '-R', select_file])
            else:
                subprocess.Popen(['open', path])
        else:
            subprocess.Popen(['xdg-open', path])

    def _sanitize_path_text(self, text):
        if not isinstance(text, str):
            return text
        t = text.strip()
        if len(t) >= 2 and ((t[0] == '"' and t[-1] == '"') or (t[0] == "'" and t[-1] == "'")):
            return t[1:-1]
        return t

    def set_output_path(self, path):
        self.output_path = path
        self.output_path_input.setText(path)
    
    def get_output_path(self):
        return self.output_path
    
    def set_source_path(self, path):
        """Update the Source path display"""
        self.source_path = path or ""
        self.source_path_input.setText(self.source_path)
        self.clear_source_button.setEnabled(bool(self.source_path or getattr(self, 'selected_file', '')))
    
    def set_file_path(self, path):
        """Update the File path display"""
        self.selected_file = path or ""
        self.file_path_input.setText(self.selected_file)
        self.clear_source_button.setEnabled(bool(self.source_path_input.text() or self.selected_file))
    
    def set_preset_type(self, preset_type):
        if preset_type and preset_type.lower() == 'single run':
            self.load_db_button.setEnabled(False)
            self.source_browse_button.setEnabled(False)
            self.source_paste_button.setEnabled(False)
            self.source_open_button.setEnabled(False)
            self.file_browse_button.setEnabled(True)
            self.file_paste_button.setEnabled(True)
            self.file_open_button.setEnabled(True)
            self.source_path_input.setEnabled(False)
            self.file_path_input.setEnabled(True)
        else:
            self.load_db_button.setEnabled(True)
            self.source_browse_button.setEnabled(True)
            self.source_paste_button.setEnabled(True)
            self.source_open_button.setEnabled(True)
            self.file_browse_button.setEnabled(False)
            self.file_paste_button.setEnabled(False)
            self.file_open_button.setEnabled(False)
            self.source_path_input.setEnabled(True)
            self.file_path_input.setEnabled(False)
    
    def disable_all_load_buttons(self):
        self.load_db_button.setEnabled(False)
        self.source_browse_button.setEnabled(False)
        self.source_paste_button.setEnabled(False)
        self.source_open_button.setEnabled(False)
        self.file_browse_button.setEnabled(False)
        self.file_paste_button.setEnabled(False)
        self.file_open_button.setEnabled(False)
        self.source_path_input.setEnabled(False)
        self.file_path_input.setEnabled(False)
    
    def enable_all_load_buttons(self):
        self.load_db_button.setEnabled(True)
        self.source_browse_button.setEnabled(True)
        self.source_paste_button.setEnabled(True)
        self.source_open_button.setEnabled(True)
        self.file_browse_button.setEnabled(False)
        self.file_paste_button.setEnabled(False)
        self.file_open_button.setEnabled(False)
        self.source_path_input.setEnabled(True)
        self.file_path_input.setEnabled(False)