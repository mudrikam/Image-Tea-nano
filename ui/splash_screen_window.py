import os
import json
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QApplication, QProgressBar
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter, QFont
from config import BASE_PATH

# Flag indicating whether splash screen is currently active (visible)
splash_active = False


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
        
        info_layout.addSpacing(10)
        
        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(2)
        meta_layout.setContentsMargins(0, 0, 0, 0)

        version_label = QLabel()
        version_label.setTextFormat(Qt.RichText)
        version_label.setText(f"Version: <b>{self.config['version']}</b>")
        version_label.setStyleSheet("color: #ffffff; margin: 0; padding: 0;")
        meta_layout.addWidget(version_label)
        
        developer_label = QLabel(f"Developer: {self.config['developer']}")
        developer_label.setStyleSheet("color: #ffffff; margin: 0; padding: 0;")
        meta_layout.addWidget(developer_label)
        
        license_label = QLabel(f"License: {self.config['license']}")
        license_label.setStyleSheet("color: #ffffff; margin: 0; padding: 0;")
        meta_layout.addWidget(license_label)

        info_layout.addLayout(meta_layout)
        
        info_layout.addSpacing(10)

        # If update config exists, show update status: Latest (remote), Current (local), Commit
        update_config_path = os.path.join(BASE_PATH, "configs", "update_config.json")
        if os.path.exists(update_config_path):
            try:
                with open(update_config_path, "r", encoding="utf-8") as uf:
                    update_cfg = json.load(uf)

                tag_remote = update_cfg.get("tag_remote")
                tag_local = update_cfg.get("tag_local")
                last_update = None
                commit = None
                if isinstance(update_cfg.get("update"), dict):
                    last_update = update_cfg["update"].get("last_update")
                ch = update_cfg.get("commit_hash") or {}
                if isinstance(ch, dict):
                    commit = ch.get("remote") or ch.get("local")

                update_lines = []
                if tag_remote:
                    txt = f"Latest: {tag_remote}"
                    if last_update:
                        txt += f" ({last_update})"
                    update_lines.append(txt)
                if tag_local:
                    update_lines.append(f"Current: {tag_local}")
                if commit:
                    update_lines.append(f"Commit: {commit}")

                if update_lines:
                    # compact inline display: versions in green, commit in gray, small font
                    parts = []
                    if tag_remote:
                        parts.append(f'<span style="color:#4e9e20; font-weight:600;">Latest: {tag_remote}</span>')
                    if tag_local:
                        parts.append(f'<span style="color:#aaaaaa; font-weight:600;">Current: {tag_local}</span>')
                    if commit:
                        parts.append(f'<span style="color:#aaaaaa;">Commit: {commit}</span>')
                    update_html = ' &nbsp;|&nbsp; '.join(parts)
                    update_label = QLabel(update_html)
                    update_label.setTextFormat(Qt.RichText)
                    update_label.setStyleSheet("font-size:8pt;")
                    update_label.setAlignment(Qt.AlignLeft)
                    info_layout.addWidget(update_label)
            except Exception as e:
                print(f"Error reading update_config.json: {e}")
        
        description_label = QLabel(self.config["description"])
        description_label.setWordWrap(True)
        description_label.setStyleSheet("color: #aaaaaa; font-size: 9pt;")
        info_layout.addWidget(description_label)
        
        info_layout.addStretch()
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #4e9e20; font-weight: bold;")
        self.status_label.setAlignment(Qt.AlignLeft)
        info_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet(
            "QProgressBar { background-color: rgba(255,255,255,0.08); border-radius: 4px; }"
            "QProgressBar::chunk { background-color: #4e9e20; border-radius: 4px; }"
        )
        info_layout.addWidget(self.progress_bar)
        
        self.setFixedSize(pixmap.width() // 2 + 500, pixmap.height())

    def show_message(self, message):
        self.status_label.setText(message)
        self.repaint()

    def set_progress(self, percent: int):
        if percent < 0:
            percent = 0
        if percent > 100:
            percent = 100
        self.progress_bar.setValue(int(percent))
        self.repaint()

        screen = QApplication.primaryScreen().geometry()
        splash_geometry = self.frameGeometry()
        center_point = screen.center()
        splash_geometry.moveCenter(center_point)
        self.move(splash_geometry.topLeft())
        
    def show_message(self, message):
        self.status_label.setText(message)
        self.repaint()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_active = True
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if getattr(self, '_drag_active', False) and (event.buttons() & Qt.LeftButton):
            try:
                new_pos = event.globalPos() - self._drag_offset
                self.move(new_pos)
            except Exception:
                pass
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if getattr(self, '_drag_active', False) and event.button() == Qt.LeftButton:
            self._drag_active = False
            self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    def show(self):
        global splash_active
        splash_active = True
        super().show()

    def finish(self, main_window):
        global splash_active
        splash_active = False
        self.close()

    def closeEvent(self, event):
        global splash_active
        splash_active = False
        super().closeEvent(event)
