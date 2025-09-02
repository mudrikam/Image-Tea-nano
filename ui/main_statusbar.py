from PySide6.QtWidgets import QStatusBar, QLabel, QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt
import os
import json
from config import BASE_PATH
import qtawesome as qta

class MainStatusBar(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.status_label = QLabel("")
        self.version_icon_label = QLabel()
        self.version_text_label = QLabel("")
        self.commit_icon_label = QLabel()
        self.commit_text_label = QLabel("")
        self.update_btn = QPushButton()
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.setFlat(True)
        download_icon = qta.icon("fa6s.download", color="white")
        self.update_btn.setStyleSheet(
            "QPushButton { color: white; background-color: #4e9e20; font-weight: bold; }"
            "QPushButton:hover { background-color: #3d7307; }"
        )
        self.update_btn.setIcon(download_icon)
        self.update_btn.clicked.connect(self._on_update_now_clicked)

        self.version_commit_widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.version_icon_label)
        layout.addWidget(self.version_text_label)
        layout.addWidget(self.commit_icon_label)
        layout.addWidget(self.commit_text_label)
        layout.addWidget(self.update_btn)
        self.version_commit_widget.setLayout(layout)
        self.addWidget(self.status_label)
        self.addPermanentWidget(self.version_commit_widget)
        self.update_version_and_commit()

    def set_status(self, text):
        self.status_label.setText(text)

    def set_api_info(self, service=None, api_key=None):
        """Set API information in the status bar"""
        if service and api_key:
            # Show last 5 characters of API key
            masked_key = f"***{api_key[-5:]}" if len(api_key) >= 5 else f"***{api_key}"
            api_text = f"Using API: {service} ({masked_key})"
            self.set_status(api_text)
        else:
            self.set_status("")

    def update_version_and_commit(self):
        update_path = os.path.join(BASE_PATH, "configs", "update_config.json")
        if os.path.exists(update_path):
            with open(update_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                tag_local = data.get("tag_local", "")
                tag_remote = data.get("tag_remote", "")
                commit_hash = ""
                commit_data = data.get("commit_hash", {})
                if isinstance(commit_data, dict):
                    commit_hash = commit_data.get("local", "")
                tag_icon = qta.icon("fa6s.tag")
                commit_icon = qta.icon("fa6s.code-commit")
                self.version_icon_label.setPixmap(tag_icon.pixmap(16, 16))
                self.version_text_label.setText(f"Version: {tag_local}" if tag_local else "")
                self.commit_icon_label.setPixmap(commit_icon.pixmap(16, 16))
                self.commit_text_label.setText(f"Commit: {commit_hash}" if commit_hash else "")
                if tag_remote and tag_local and tag_remote != tag_local:
                    self.update_btn.setText(f"Update to {tag_remote} Now")
                    self.update_btn.setEnabled(True)
                    self.update_btn.show()
                else:
                    self.update_btn.setText("")
                    self.update_btn.setEnabled(False)
                    self.update_btn.hide()
        else:
            self.version_icon_label.clear()
            self.version_text_label.setText("")
            self.commit_icon_label.clear()
            self.commit_text_label.setText("")
            self.update_btn.setText("")
            self.update_btn.setEnabled(False)
            self.update_btn.hide()

    def _on_update_now_clicked(self):
        try:
            from ui.main_menu import run_updater
            run_updater(self.parent())
        except Exception as e:
            print(f"Failed to run updater from statusbar: {e}")
