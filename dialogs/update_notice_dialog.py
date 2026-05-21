from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextBrowser, QHBoxLayout, QPushButton, QCheckBox, QWidget, QSizePolicy
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QPixmap, QImageReader, QDesktopServices
import qtawesome as qta
import json
import os
from datetime import datetime, timezone, timedelta
from config import BASE_PATH
from ui.theme_system import theme
from dialogs.donation_dialog import DonateDialog


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
    except Exception:
        print(f"format_human_readable_date error: {iso_date_str}")
        return iso_date_str


class UpdateNoticeDialog(QDialog):
    def __init__(self, parent=None, local_tag=None, remote_tag=None, remote_hash=None, release_notes=None, checked_time=None):
        super().__init__(parent)
        self.setWindowTitle("Update Available")
        self.setMinimumSize(400, 350)

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
            except Exception as e:
                print(f"[UpdateNoticeDialog] Error loading icon '{ico_path}': {e}")
        top_layout.addWidget(logo_label, alignment=Qt.AlignTop)


        info_widget = QWidget()
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(6)
        app_config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
        with open(app_config_path, "r", encoding="utf-8") as f:
            app_cfg = json.load(f)
            repo_url = app_cfg["links"]["repo"]

        current_label = QLabel(f"<b>Current version:</b> {local_tag or 'unknown'}")
        new_label = QLabel(f"<b>Latest:</b> {remote_tag or 'unknown'}")
        new_label.setStyleSheet(f"QLabel {{ background-color: {theme.get_color('primary')}; color: {theme.get_color('white')}; font-size: 14pt; font-weight: bold; padding: 4px 8px; border-radius: 4px; }}")
        checked_label = QLabel(f"<b>Checked at:</b> {format_human_readable_date(checked_time) or ''}")
        checked_label.setWordWrap(True)

        commit_text = remote_hash or ""
        for lbl in (new_label, current_label, checked_label):
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            info_layout.addWidget(lbl)

        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(6)

        commit_icon = qta.icon('fa6s.code-commit')
        short_hash = (commit_text or "")[:7]
        commit_btn = QPushButton(commit_icon, f" {short_hash}")
        commit_btn.setToolTip(commit_text or "No commit available")
        commit_btn.setCursor(Qt.PointingHandCursor)

        commit_url = ""
        if repo_url and remote_hash:
            commit_url = f"{repo_url.rstrip('/')}/commit/{remote_hash}"
            commit_btn.clicked.connect(lambda _, u=commit_url: QDesktopServices.openUrl(QUrl(u)))
            commit_btn.setEnabled(bool(short_hash))
        else:
            commit_btn.setEnabled(False)

        app_config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
        with open(app_config_path, "r", encoding="utf-8") as f:
            app_cfg = json.load(f)
            wa_link = app_cfg["links"]["whatsapp"]


        bug_icon = qta.icon('fa6s.bug')
        report_btn = QPushButton(bug_icon, " Found a Bug")
        report_btn.setCursor(Qt.PointingHandCursor)
        if wa_link:
            report_btn.clicked.connect(lambda _, u=wa_link: QDesktopServices.openUrl(QUrl(u)))
        else:
            report_btn.setEnabled(False)

        # Community button (WhatsApp group)
        community_icon = qta.icon('fa6b.whatsapp')
        community_btn = QPushButton(community_icon, " Community")
        community_btn.setCursor(Qt.PointingHandCursor)
        if wa_link:
            community_btn.clicked.connect(lambda _, u=wa_link: QDesktopServices.openUrl(QUrl(u)))
        else:
            community_btn.setEnabled(False)

        # Donate button
        donate_icon = qta.icon('fa6s.heart')
        donate_btn = QPushButton(donate_icon, " Donate")
        donate_btn.setCursor(Qt.PointingHandCursor)
        donate_btn.clicked.connect(self._on_donate)

        buttons_layout.addWidget(commit_btn)
        buttons_layout.addWidget(report_btn)
        buttons_layout.addWidget(community_btn)
        buttons_layout.addWidget(donate_btn)
        buttons_widget.setLayout(buttons_layout)
        info_layout.addWidget(buttons_widget)

        info_widget.setLayout(info_layout)
        top_layout.addWidget(info_widget, stretch=1)

        top_widget.setLayout(top_layout)
        main_layout.addWidget(top_widget)

        notes_label = QLabel("<b>Release notes:</b>")
        main_layout.addWidget(notes_label)

        notes = QTextBrowser()
        notes.setOpenExternalLinks(True)
        notes.setSearchPaths([os.path.join(BASE_PATH, "res", "images")])
        notes.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        try:
            notes.setMarkdown(release_notes or "No release notes available.")
        except Exception:
            notes.setPlainText(release_notes or "No release notes available.")
        main_layout.addWidget(notes)

        self.skip_checkbox = QCheckBox("Skip this version until next release")
        self.skip_checkbox.setEnabled(False)
        self._skip_remaining = 30
        self.skip_checkbox.setToolTip(f"This option will be enabled after {self._skip_remaining} seconds")

        skip_container = QWidget()
        skip_layout = QHBoxLayout()
        skip_layout.setContentsMargins(0, 0, 0, 0)
        skip_layout.setSpacing(6)
        self._skip_countdown_label = QLabel(f"({self._skip_remaining}s)")
        self._skip_countdown_label.setStyleSheet(f"QLabel {{ color: {theme.get_color('text_dark')}; }}")
        skip_layout.addWidget(self.skip_checkbox)
        skip_layout.addWidget(self._skip_countdown_label, alignment=Qt.AlignLeft)
        skip_container.setLayout(skip_layout)
        main_layout.addWidget(skip_container)

        self._skip_timer = QTimer(self)
        self._skip_timer.setInterval(1000)

        def _tick():
            self._skip_remaining -= 1
            if self._skip_remaining > 0:
                self.skip_checkbox.setToolTip(f"This option will be enabled after {self._skip_remaining} seconds")
                self._skip_countdown_label.setText(f"({self._skip_remaining}s)")
            else:
                self.skip_checkbox.setEnabled(True)
                self.skip_checkbox.setToolTip("")
                self._skip_countdown_label.setText("")
                self._skip_timer.stop()

        self._skip_timer.timeout.connect(_tick)
        self._skip_timer.start()

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(12)
        update_icon = qta.icon('fa6s.download', color=theme.get_color('white'))
        later_icon = qta.icon('fa6s.clock-rotate-left')
        self.update_btn = QPushButton(update_icon, " Update Now")
        self.later_btn = QPushButton(later_icon, " Remind Me Later")
        self._update_remaining = 60
        self.update_btn.setText(f" Update Now ({self._update_remaining}s)")
        self._update_countdown_timer = QTimer(self)
        self._update_countdown_timer.setInterval(1000)

        def _update_tick():
            self._update_remaining -= 1
            if self._update_remaining > 0:
                self.update_btn.setText(f" Update Now ({self._update_remaining}s)")
            else:
                self._update_countdown_timer.stop()
                self._on_auto_close()

        self._update_countdown_timer.timeout.connect(_update_tick)
        self._update_countdown_timer.start()

        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self._on_auto_close)
        self._auto_close_timer.start(self._update_remaining * 1000)
        self.later_btn.setEnabled(False)
        self._later_remaining = 5
        self.later_btn.setText(f" Remind Me Later ({self._later_remaining})")
        self._later_timer = QTimer(self)
        self._later_timer.setInterval(1000)

        def _later_tick():
            self._later_remaining -= 1
            if self._later_remaining > 0:
                self.later_btn.setText(f" Remind Me Later ({self._later_remaining})")
            else:
                self.later_btn.setEnabled(True)
                self.later_btn.setText(" Remind Me Later")
                self._later_timer.stop()

        self._later_timer.timeout.connect(_later_tick)
        self._later_timer.start()
        self.update_btn.setStyleSheet(f"QPushButton {{ background-color: {theme.get_color('primary')}; color: {theme.get_color('white')}; font-weight: bold; padding: 8px 14px; border-radius: 6px; }} QPushButton:hover {{ background-color: {theme.get_color('primary_hover')}; }}")
        self.later_btn.setStyleSheet(f"QPushButton {{ padding: 8px 12px; border-radius: 6px; }} QPushButton:hover {{ border: 1px solid {theme.get_color('gray')}; }}")
        self.update_btn.setMinimumHeight(40)
        self.later_btn.setMinimumHeight(40)
        self.update_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.later_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn_layout.addWidget(self.later_btn)
        btn_layout.addWidget(self.update_btn)
        main_layout.addLayout(btn_layout)

        self.setLayout(main_layout)
        self.result_action = None

        self._close_allowed = False
        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self._enable_close)
        self._close_timer.start(5000)

        self.update_btn.clicked.connect(self._on_update)
        self.later_btn.clicked.connect(self._on_later)

    def _on_update(self):
        self._update_countdown_timer.stop()
        self._auto_close_timer.stop()
        self.result_action = "update"
        self.accept()
        
        import sys
        import subprocess
        import platform
        
        update_worker_py = os.path.join(BASE_PATH, "Update_Worker.py")
        
        if os.path.exists(update_worker_py):
            system = platform.system()
            
            if system == "Windows":
                pythonw_path = os.path.join(BASE_PATH, "python", "Windows", "pythonw.exe")
                python_path = os.path.join(BASE_PATH, "python", "Windows", "python.exe")
                
                if os.path.exists(pythonw_path):
                    subprocess.Popen([pythonw_path, update_worker_py, "--auto"], shell=False)
                elif os.path.exists(python_path):
                    subprocess.Popen([python_path, update_worker_py, "--auto"], shell=False)
                else:
                    subprocess.Popen([sys.executable, update_worker_py, "--auto"], shell=False)
            else:
                subprocess.Popen([sys.executable, update_worker_py, "--auto"], shell=False)

    def _on_later(self):
        self._update_countdown_timer.stop()
        self._auto_close_timer.stop()
        self.result_action = "skip" if self.skip_checkbox.isChecked() else "later"
        self.accept()

    def _on_donate(self):
        """Open donation dialog"""
        dialog = DonateDialog(self)
        dialog.exec()

    def _on_auto_close(self):
        self._update_countdown_timer.stop()
        self._auto_close_timer.stop()
        self.result_action = "timeout"
        self.accept()

    def _enable_close(self):
        self._close_allowed = True

    def closeEvent(self, event):
        self._update_countdown_timer.stop()
        self._auto_close_timer.stop()
        self._later_timer.stop()
        self._skip_timer.stop()
        if getattr(self, "_close_allowed", True):
            super().closeEvent(event)
        else:
            event.ignore()
