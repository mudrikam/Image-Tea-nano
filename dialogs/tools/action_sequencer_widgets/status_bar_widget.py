from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, 
                               QProgressBar, QSizePolicy)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
import qtawesome as qta

class StatusBarWidget(QWidget):
    run_actions_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)
        
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)
        
        self.files_label = QLabel("Files: 0")
        self.files_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.files_label)
        
        self.steps_label = QLabel("Steps: 0")
        self.steps_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.steps_label)
        
        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.status_label)
        
        stats_layout.addStretch()
        
        main_layout.addLayout(stats_layout)
        
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(16)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(20)
        self.progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        bottom_layout.addWidget(self.progress_bar)
        
        run_icon = qta.icon('fa6s.play')
        self.run_button = QPushButton(run_icon, " RUN ACTIONS")
        self.run_button.setMinimumHeight(40)
        self.run_button.setMinimumWidth(150)
        self.run_button.clicked.connect(self.on_run_clicked)
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #4e9e20;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3d7307;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        bottom_layout.addWidget(self.run_button)
        
        main_layout.addLayout(bottom_layout)
        
        self.setLayout(main_layout)
    
    def set_dummy_status(self):
        self.update_files_count(200)
        self.update_steps_count(4)
        self.update_status("Running")
        self.update_progress(60)
    
    def update_files_count(self, count, source='manual'):
        if source == 'database':
            self.files_label.setText(f"Files Loaded from Database: {count}")
        else:
            self.files_label.setText(f"Files Loaded: {count}")
    
    def update_steps_count(self, count):
        self.steps_label.setText(f"Steps: {count}")
    
    def update_status(self, status):
        self.status_label.setText(f"Status: {status}")
        
        if status == "Running":
            self.status_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        elif status == "Error":
            self.status_label.setStyleSheet("font-weight: bold; color: #f44336;")
        elif status == "Completed":
            self.status_label.setStyleSheet("font-weight: bold; color: #2196F3;")
        else:
            self.status_label.setStyleSheet("font-weight: bold; color: #888;")
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
    
    def on_run_clicked(self):
        self.run_actions_requested.emit()
    
    def set_run_button_enabled(self, enabled):
        self.run_button.setEnabled(enabled)
