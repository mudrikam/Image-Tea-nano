from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QFileDialog
from PySide6.QtCore import Signal
import qtawesome as qta


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
        
        buttons_layout.addStretch()
        
        main_layout.addLayout(buttons_layout)
        
        source_layout = QHBoxLayout()
        source_layout.setSpacing(8)
        source_icon = QLabel()
        source_icon.setPixmap(qta.icon('fa6s.folder-open', color='#888').pixmap(16, 16))
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
        self.source_browse_button = QPushButton(qta.icon('fa6s.folder-open'), " Browse")
        self.source_browse_button.clicked.connect(self.on_select_source)
        source_layout.addWidget(self.source_browse_button)
        main_layout.addLayout(source_layout)

        file_layout = QHBoxLayout()
        file_layout.setSpacing(8)
        file_icon = QLabel()
        file_icon.setPixmap(qta.icon('fa6s.file', color='#888').pixmap(16, 16))
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
        self.file_browse_button = QPushButton(qta.icon('fa6s.folder-open'), " Browse")
        self.file_browse_button.setEnabled(False)
        self.file_browse_button.clicked.connect(self.on_select_file)
        file_layout.addWidget(self.file_browse_button)
        main_layout.addLayout(file_layout)

        output_layout = QHBoxLayout()
        output_layout.setSpacing(8)
        
        output_icon = QLabel()
        output_icon.setPixmap(qta.icon('fa6s.folder', color='#888').pixmap(16, 16))
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
        
        self.select_output_button = QPushButton(qta.icon('fa6s.folder-open'), " Browse")
        self.select_output_button.clicked.connect(self.on_select_output)
        output_layout.addWidget(self.select_output_button)
        
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
    
    def on_select_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder", self.output_path)
        if folder:
            self.output_path = folder
            self.output_path_input.setText(folder)
            self.output_path_changed.emit(folder)

    def on_source_edited(self):
        path = self.source_path_input.text().strip()
        self.source_path = path
        self.source_path_changed.emit(path)
        self.clear_source_button.setEnabled(bool(path or getattr(self, 'selected_file', '')))

    def on_file_edited(self):
        path = self.file_path_input.text().strip()
        self.selected_file = path
        self.file_path_changed.emit(path)
        self.clear_source_button.setEnabled(bool(self.source_path_input.text() or path))

    def on_output_edited(self):
        path = self.output_path_input.text().strip()
        self.output_path = path
        self.output_path_changed.emit(path)

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
            self.file_browse_button.setEnabled(True)
            self.source_path_input.setEnabled(False)
            self.file_path_input.setEnabled(True)
        else:
            self.load_db_button.setEnabled(True)
            self.source_browse_button.setEnabled(True)
            self.file_browse_button.setEnabled(False)
            self.source_path_input.setEnabled(True)
            self.file_path_input.setEnabled(False)
    
    def disable_all_load_buttons(self):
        self.load_db_button.setEnabled(False)
        self.source_browse_button.setEnabled(False)
        self.file_browse_button.setEnabled(False)
        self.source_path_input.setEnabled(False)
        self.file_path_input.setEnabled(False)
    
    def enable_all_load_buttons(self):
        self.load_db_button.setEnabled(True)
        self.source_browse_button.setEnabled(True)
        self.file_browse_button.setEnabled(False)
        self.source_path_input.setEnabled(True)
        self.file_path_input.setEnabled(False)