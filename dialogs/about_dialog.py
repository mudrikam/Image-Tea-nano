from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImageReader
import qtawesome as qta
import json
import os
from config import BASE_PATH

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setMinimumWidth(400)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(18)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(24)

        icon_label = QLabel()
        ico_path = os.path.join(BASE_PATH, "res", "image_tea.ico")
        if os.path.isfile(ico_path):
            try:
                reader = QImageReader(ico_path)
                largest_image = None
                largest_area = 0
                frame_count = reader.imageCount() if hasattr(reader, "imageCount") else 0
                if frame_count > 1:
                    for i in range(frame_count):
                        reader.jumpToImage(i)
                        image = reader.read()
                        if not image.isNull():
                            area = image.width() * image.height()
                            if area > largest_area:
                                largest_area = area
                                largest_image = image
                else:
                    image = reader.read()
                    if not image.isNull():
                        largest_image = image
                        largest_area = image.width() * image.height()
                if largest_image is not None:
                    pixmap = QPixmap.fromImage(largest_image)
                    pixmap = pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    icon_label.setPixmap(pixmap)
                else:
                    print("Failed to read any icon from .ico file")
            except Exception as e:
                print(f"Failed to load .ico file: {e}")
        else:
            print(f"ICO file not found: {ico_path}")

        icon_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        content_layout.addWidget(icon_label, alignment=Qt.AlignTop)

        app_config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
        try:
            with open(app_config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            app_name = config["name"]
            tagline = config["tagline"]
            developer = config["developer"]
            license_ = config["license"]
            version = config["version"]
            description = config["description"]
        except Exception as e:
            print(f"Failed to load app_config.json: {e}")
            raise

        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(6)

        name_label = QLabel(f"<b>{app_name}</b>")
        name_label.setAlignment(Qt.AlignLeft)
        name_label.setStyleSheet("font-size: 18px;")
        detail_layout.addWidget(name_label)

        tagline_label = QLabel(f"<b>{tagline}</b>")
        tagline_label.setAlignment(Qt.AlignLeft)
        tagline_label.setStyleSheet("color: #4e9e20; font-size: 18px;")
        detail_layout.addWidget(tagline_label)

        version_label = QLabel(f"Version: {version}")
        version_label.setAlignment(Qt.AlignLeft)
        detail_layout.addWidget(version_label)

        dev_label = QLabel(f"Developer: {developer}")
        dev_label.setAlignment(Qt.AlignLeft)
        detail_layout.addWidget(dev_label)

        license_label = QLabel(f"License: {license_}")
        license_label.setAlignment(Qt.AlignLeft)
        detail_layout.addWidget(license_label)

        desc_label = QLabel(description)
        desc_label.setAlignment(Qt.AlignLeft)
        desc_label.setWordWrap(True)
        detail_layout.addWidget(desc_label)

        content_layout.addWidget(detail_widget, stretch=1)
        main_layout.addLayout(content_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        close_btn = QPushButton(qta.icon('fa6s.xmark'), "Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        main_layout.addLayout(btn_layout)