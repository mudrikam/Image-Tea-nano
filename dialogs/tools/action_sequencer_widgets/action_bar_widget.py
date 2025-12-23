from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Signal
import qtawesome as qta


class ActionBarWidget(QWidget):
    load_from_database_requested = Signal()
    select_source_requested = Signal()
    select_file_requested = Signal()
    settings_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.files_count = 0
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        self.load_db_button = QPushButton(qta.icon('fa6s.database'), " Load from Database")
        self.load_db_button.clicked.connect(self.on_load_from_database)
        buttons_layout.addWidget(self.load_db_button)
        
        self.select_source_button = QPushButton(qta.icon('fa6s.folder-open'), " Select Source")
        self.select_source_button.clicked.connect(self.on_select_source)
        buttons_layout.addWidget(self.select_source_button)
        
        self.select_file_button = QPushButton(qta.icon('fa6s.file'), " Select File")
        self.select_file_button.clicked.connect(self.on_select_file)
        self.select_file_button.setEnabled(False)
        buttons_layout.addWidget(self.select_file_button)

        self.settings_button = QPushButton(qta.icon('fa6s.gears'), " Settings")
        self.settings_button.clicked.connect(self.on_settings_clicked)
        buttons_layout.addWidget(self.settings_button)
        
        buttons_layout.addStretch()
        
        main_layout.addLayout(buttons_layout)
        
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
