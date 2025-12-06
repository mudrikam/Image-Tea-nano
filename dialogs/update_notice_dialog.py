from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QHBoxLayout, QPushButton, QCheckBox, QWidget, QSizePolicy
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QImageReader
import qtawesome as qta
import json
import os
from datetime import datetime, timezone, timedelta
from config import BASE_PATH


def format_human_readable_date(iso_date_str):
    """Convert ISO date string to human-readable format in UTC and WIB"""
    if not iso_date_str:
        return ""
    
    try:
        if iso_date_str.endswith('Z'):
            iso_date_str = iso_date_str[:-1] + '+00:00'
        
        dt = datetime.fromisoformat(iso_date_str.replace('Z', '+00:00'))
        
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        else:
            dt = dt.replace(tzinfo=timezone.utc)
        
        utc_time = dt.strftime("%B %d, %Y at %I:%M %p UTC")
        wib_dt = dt.astimezone(timezone(timedelta(hours=7)))
        wib_time = wib_dt.strftime("%B %d, %Y at %I:%M %p WIB")
        
        return f"{utc_time} or {wib_time}"
    except (ValueError, AttributeError):
        return iso_date_str


class UpdateNoticeDialog(QDialog):
    def __init__(self, parent=None, local_tag=None, remote_tag=None, remote_hash=None, release_notes=None, checked_time=None):
        super().__init__(parent)
        self.setWindowTitle("Update Available")
        self.setMinimumSize(240, 320)

        main_layout = QVBoxLayout()

        top_widget = QWidget()
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(12)

        logo_label = QLabel()
        ico_path = os.path.join(BASE_PATH, "res", "image_tea.ico")
        if os.path.isfile(ico_path):
            try:
                reader = QImageReader(ico_path)
                largest_image = None
                largest_area = 0
                frame_count = reader.imageCount() if hasattr(reader, "imageCount") else 0
                if frame_count and frame_count > 1:
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
                if largest_image is not None:
                    pixmap = QPixmap.fromImage(largest_image)
                    pixmap = pixmap.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    logo_label.setPixmap(pixmap)
            except Exception:
                pass
        top_layout.addWidget(logo_label, alignment=Qt.AlignTop)


        info_widget = QWidget()
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(6)

        repo_url = ""
        try:
            app_config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
            if os.path.exists(app_config_path):
                with open(app_config_path, "r", encoding="utf-8") as f:
                    app_cfg = json.load(f)
                    repo_url = app_cfg.get("links", {}).get("repo", "")
        except Exception:
            repo_url = ""

        current_label = QLabel(f"<b>Current version:</b> {local_tag or 'unknown'}")
        new_label = QLabel(f"<b>New version:</b> {remote_tag or 'unknown'}")
        new_label.setStyleSheet("QLabel { background-color: #4e9e20; color: white; font-weight: bold; padding: 4px 8px; border-radius: 4px; }")
        checked_label = QLabel(f"<b>Checked at:</b> {format_human_readable_date(checked_time) or ''}")
        checked_label.setWordWrap(True)

        commit_text = remote_hash or ""
        if repo_url and remote_hash:
            commit_url = f"{repo_url.rstrip('/')}/commit/{remote_hash}"
            commit_label = QLabel(f"<b>Commit:</b> <a href=\"{commit_url}\">{commit_text}</a>")
            commit_label.setTextFormat(Qt.RichText)
            commit_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
            commit_label.setOpenExternalLinks(True)
        else:
            commit_label = QLabel(f"<b>Commit:</b> {commit_text}")

        for lbl in (new_label, current_label, checked_label):
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            info_layout.addWidget(lbl)
        info_layout.addWidget(commit_label)

        info_widget.setLayout(info_layout)
        top_layout.addWidget(info_widget, stretch=1)

        top_widget.setLayout(top_layout)
        main_layout.addWidget(top_widget)

        notes_label = QLabel("<b>Release notes:</b>")
        main_layout.addWidget(notes_label)

        notes = QTextEdit()
        notes.setReadOnly(True)
        notes.setPlainText(release_notes or "No release notes available.")
        main_layout.addWidget(notes)

        self.skip_checkbox = QCheckBox("Skip this version (don't show again until next release)")
        self.skip_checkbox.setEnabled(False)
        self._skip_remaining = 30
        self.skip_checkbox.setToolTip(f"This option will be enabled after {self._skip_remaining} seconds")
        main_layout.addWidget(self.skip_checkbox)

        self._skip_timer = QTimer(self)
        self._skip_timer.setInterval(1000)

        def _tick():
            self._skip_remaining -= 1
            if self._skip_remaining > 0:
                self.skip_checkbox.setToolTip(f"This option will be enabled after {self._skip_remaining} seconds")
            else:
                self.skip_checkbox.setEnabled(True)
                self.skip_checkbox.setToolTip("")
                self._skip_timer.stop()

        self._skip_timer.timeout.connect(_tick)
        self._skip_timer.start()

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(12)
        update_icon = qta.icon('fa6s.download', color="#FFFFFF")
        later_icon = qta.icon('fa6s.clock-rotate-left')
        self.update_btn = QPushButton(update_icon, " Update Now")
        self.later_btn = QPushButton(later_icon, " Remind Me Later")
        self.update_btn.setStyleSheet("QPushButton { background-color: #4e9e20; color: white; font-weight: bold; padding: 8px 14px; border-radius: 6px; } QPushButton:hover { background-color: #3d7307; }")
        self.later_btn.setStyleSheet("QPushButton { padding: 8px 12px; border-radius: 6px; } QPushButton:hover { border: 1px solid #999; }")
        self.update_btn.setMinimumHeight(40)
        self.later_btn.setMinimumHeight(40)
        self.update_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.later_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_layout.addWidget(self.later_btn)
        btn_layout.addWidget(self.update_btn)
        main_layout.addLayout(btn_layout)

        self.setLayout(main_layout)
        self.result_action = None

        self.update_btn.clicked.connect(self._on_update)
        self.later_btn.clicked.connect(self._on_later)

    def _on_update(self):
        self.result_action = "update"
        self.accept()

    def _on_later(self):
        self.result_action = "skip" if self.skip_checkbox.isChecked() else "later"
        self.accept()
