import os
import json
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter, QFont
from config import BASE_PATH


class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.SplashScreen)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        
        splash_image_path = os.path.join(BASE_PATH, "res", "splash_screen.png")
        pixmap = QPixmap(splash_image_path)
        
        info_widget = QWidget(self)
        info_widget.setGeometry(pixmap.width() // 2, 0, 500, pixmap.height())
        info_widget.setStyleSheet("background-color: #2b2b2b; color: white;")
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(30, 30, 30, 30)
        info_layout.setSpacing(8)
        
        image_label = QLabel(self)
        image_label.setPixmap(pixmap)
        image_label.setScaledContents(True)
        image_label.setFixedSize(pixmap.size())
        image_label.move(0, 0)
        image_label.raise_()
        info_layout.setSpacing(10)
        
        name_label = QLabel(self.config["name"])
        name_font = QFont()
        name_font.setPointSize(22)
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setStyleSheet("color: #4e9e20;")
        info_layout.addWidget(name_label)
        
        tagline_label = QLabel(self.config["tagline"])
        tagline_font = QFont()
        tagline_font.setPointSize(9)
        tagline_label.setFont(tagline_font)
        tagline_label.setStyleSheet("color: #cccccc; font-size: 14pt;")
        tagline_label.setWordWrap(True)
        info_layout.addWidget(tagline_label)
        
        info_layout.addSpacing(15)
        
        version_label = QLabel(f"Version: {self.config['version']}")
        version_label.setStyleSheet("color: #ffffff;")
        info_layout.addWidget(version_label)
        
        developer_label = QLabel(f"Developer: {self.config['developer']}")
        developer_label.setStyleSheet("color: #ffffff;")
        info_layout.addWidget(developer_label)
        
        license_label = QLabel(f"License: {self.config['license']}")
        license_label.setStyleSheet("color: #ffffff;")
        info_layout.addWidget(license_label)
        
        info_layout.addSpacing(15)
        
        description_label = QLabel(self.config["description"])
        description_label.setWordWrap(True)
        description_label.setStyleSheet("color: #aaaaaa; font-size: 9pt;")
        info_layout.addWidget(description_label)
        
        info_layout.addStretch()
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #4e9e20; font-weight: bold;")
        self.status_label.setAlignment(Qt.AlignLeft)
        info_layout.addWidget(self.status_label)
        
        self.setFixedSize(pixmap.width() // 2 + 500, pixmap.height())
        
    def show_message(self, message):
        self.status_label.setText(message)
        self.repaint()
    
    def finish(self, main_window):
        self.close()
