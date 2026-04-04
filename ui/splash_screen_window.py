import os
import json
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QApplication, QProgressBar
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter, QFont, QColor
from config import BASE_PATH
from .theme_system import theme

# Flag indicating whether splash screen is currently active (visible)
splash_active = False


class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.SplashScreen)
        
        config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        
        splash_image_path = os.path.join(BASE_PATH, "res", "splash_screen.png")
        self.pixmap = QPixmap(splash_image_path)
        
        image_width = self.pixmap.width()
        image_height = self.pixmap.height()
        panel_width = 450
        overlap = 230
        total_width = image_width + panel_width - overlap
        
        self.setStyleSheet(f"background-color: {theme.get_color('background_dark')};")
        
        image_label = QLabel(self)
        image_label.setPixmap(self.pixmap)
        image_label.setFixedSize(image_width, image_height)
        image_label.lower()
        
        info_widget = QWidget(self)
        info_widget.setAttribute(Qt.WA_TranslucentBackground)
        info_widget.setStyleSheet("color: white;")
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(20, 15, 20, 15)
        info_layout.setSpacing(4)
        info_widget.raise_()
        
        name_label = QLabel(f"{self.config['name']} v{self.config['version']}")
        name_font = QFont()
        name_font.setPointSize(22)
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setStyleSheet(f"color: {theme.get_color('primary')}; background: transparent;")
        info_layout.addWidget(name_label)
        
        tagline_label = QLabel(self.config["tagline"])
        tagline_font = QFont()
        tagline_font.setPointSize(9)
        tagline_label.setFont(tagline_font)
        tagline_label.setStyleSheet(f"color: {theme.get_color('text_light')}; font-size: 14pt; background: transparent;")
        tagline_label.setWordWrap(True)
        info_layout.addWidget(tagline_label)
        
        info_layout.addStretch()
        
        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(1)
        meta_layout.setContentsMargins(0, 0, 0, 0)

        version_label = QLabel()
        version_label.setTextFormat(Qt.RichText)
        version_label.setText(f"Version: <b>{self.config['version']}</b>")
        version_label.setStyleSheet(f"color: {theme.get_color('foreground')}; margin: 0; padding: 0; background: transparent;")
        meta_layout.addWidget(version_label)

        developer_label = QLabel(f"Developer: {self.config['developer']}")
        developer_label.setStyleSheet(f"color: {theme.get_color('foreground')}; margin: 0; padding: 0; background: transparent;")
        meta_layout.addWidget(developer_label)

        license_label = QLabel(f"License: {self.config['license']}")
        license_label.setStyleSheet(f"color: {theme.get_color('foreground')}; margin: 0; padding: 0; background: transparent;")
        meta_layout.addWidget(license_label)

        info_layout.addLayout(meta_layout)

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
                        parts = []
                        if tag_remote:
                            parts.append(f"<span style=\"color:{theme.get_color('primary')}; font-weight:600;\">Latest: {tag_remote}</span>")
                        if tag_local:
                            parts.append(f"<span style=\"color:{theme.get_color('text_light')}; font-weight:600;\">Current: {tag_local}</span>")
                        if commit:
                            parts.append(f"<span style=\"color:{theme.get_color('text_light')};\">Commit: {commit}</span>")
                        update_html = ' &nbsp;|&nbsp; '.join(parts)
                        update_label = QLabel()
                        update_label.setTextFormat(Qt.RichText)
                        update_label.setText(update_html)
                        update_label.setStyleSheet(f"font-size:8pt; color: {theme.get_color('text_light')}; background: transparent;")
                        update_label.setAlignment(Qt.AlignLeft)
                        info_layout.addWidget(update_label)
            except Exception as e:
                print(f"Error reading update_config.json: {e}")
        
        description_label = QLabel(self.config["description"])
        description_label.setWordWrap(True)
        description_label.setStyleSheet(f"color: {theme.get_color('text_light')}; font-size: 9pt; background: transparent;")
        info_layout.addWidget(description_label)
        
        info_layout.addStretch()
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {theme.get_color('primary')}; font-weight: bold; background: transparent;")
        self.status_label.setAlignment(Qt.AlignLeft)
        info_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        _wht_q = QColor(theme.get_color('white'))
        _wht_rgb = f"{_wht_q.red()},{_wht_q.green()},{_wht_q.blue()}"
        self.progress_bar.setStyleSheet(
            f"QProgressBar {{ background-color: rgba({_wht_rgb},0.08); border-radius: 4px; }}"
            f"QProgressBar::chunk {{ background-color: {theme.get_color('primary')}; border-radius: 4px; }}"
        )
        info_layout.addWidget(self.progress_bar)
        
        info_widget.adjustSize()
        content_height = info_widget.sizeHint().height()
        window_height = max(image_height, content_height)
        
        info_widget.setGeometry(image_width - overlap, 0, panel_width, window_height)
        image_label.move(0, window_height - image_height)
        
        self.setFixedSize(total_width, window_height)

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
