from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QFileDialog
from PySide6.QtCore import Signal
import qtawesome as qta


class ActionBarWidget(QWidget):
    load_from_database_requested = Signal()
    select_source_requested = Signal()
    select_file_requested = Signal()
    settings_requested = Signal()
    output_path_changed = Signal(str)
    reset_requested = Signal()
    
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
        
        self.select_source_button = QPushButton(qta.icon('fa6s.folder-open'), " Select Source")
        self.select_source_button.clicked.connect(self.on_select_source)
        buttons_layout.addWidget(self.select_source_button)
        
        self.select_file_button = QPushButton(qta.icon('fa6s.file'), " Select File")
        self.select_file_button.clicked.connect(self.on_select_file)
        self.select_file_button.setEnabled(False)
        buttons_layout.addWidget(self.select_file_button)

        self.settings_button = QPushButton(qta.icon('fa6s.gear'), " Settings")
        self.settings_button.clicked.connect(self.on_settings_clicked)
        buttons_layout.addWidget(self.settings_button)
        
        self.reset_button = QPushButton(qta.icon('fa6s.rotate-left'), " Reset")
        self.reset_button.clicked.connect(self.on_reset_clicked)
        buttons_layout.addWidget(self.reset_button)
        
        buttons_layout.addStretch()
        
        main_layout.addLayout(buttons_layout)
        
        output_layout = QHBoxLayout()
        output_layout.setSpacing(8)
        
        output_icon = QLabel()
        output_icon.setPixmap(qta.icon('fa6s.folder', color='#888').pixmap(16, 16))
        output_layout.addWidget(output_icon)
        
        output_label = QLabel("Output:")
        output_label.setStyleSheet("font-weight: bold;")
        output_layout.addWidget(output_label)
        
        self.output_path_input = QLineEdit()
        self.output_path_input.setPlaceholderText("Select output folder...")
        self.output_path_input.setReadOnly(True)
        output_layout.addWidget(self.output_path_input)
        
        self.select_output_button = QPushButton(qta.icon('fa6s.folder-open'), " Browse")
        self.select_output_button.clicked.connect(self.on_select_output)
        output_layout.addWidget(self.select_output_button)
        
        main_layout.addLayout(output_layout)
        
        self.setLayout(main_layout)
    
    def on_load_from_database(self):
        self.select_source_button.setEnabled(False)
        self.load_from_database_requested.emit()
    
    def on_select_source(self):
        self.load_db_button.setEnabled(False)
        self.select_source_requested.emit()
    
    def on_select_file(self):
        self.select_file_requested.emit()

    def on_settings_clicked(self):
        self.settings_requested.emit()
    
    def on_reset_clicked(self):
        self.set_output_path("")
        self.output_path_changed.emit("")
        self.reset_requested.emit()
    
    def on_select_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder", self.output_path)
        if folder:
            self.output_path = folder
            self.output_path_input.setText(folder)
            self.output_path_changed.emit(folder)
    
    def set_output_path(self, path):
        self.output_path = path
        self.output_path_input.setText(path)
    
    def get_output_path(self):
        return self.output_path
    
    def set_preset_type(self, preset_type):
        """Enable/disable buttons based on preset type.
        - batch: enable load_db and select_source, disable select_file
        - single run: disable load_db and select_source, enable select_file
        """
        if preset_type and preset_type.lower() == 'single run':
            self.load_db_button.setEnabled(False)
            self.select_source_button.setEnabled(False)
            self.select_file_button.setEnabled(True)
        else:
            self.load_db_button.setEnabled(True)
            self.select_source_button.setEnabled(True)
            self.select_file_button.setEnabled(False)
    
    def disable_all_load_buttons(self):
        """Disable all load buttons when no preset is selected"""
        self.load_db_button.setEnabled(False)
        self.select_source_button.setEnabled(False)
        self.select_file_button.setEnabled(False)
    
    def enable_all_load_buttons(self):
        """Enable all load buttons for reset"""
        self.load_db_button.setEnabled(True)
        self.select_source_button.setEnabled(True)
        self.select_file_button.setEnabled(False)
