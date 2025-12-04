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

        # Check for .env DEVELOPMENT=true
        self._check_env_and_set_style()
        self.update_version_and_commit()

    def _check_env_and_set_style(self):
        env_path = os.path.join(BASE_PATH, ".env")
        is_development = False
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().upper() == "DEVELOPMENT=TRUE":
                            is_development = True
                            break
            except Exception:
                pass
        if is_development:
            self.setStyleSheet("QStatusBar { background-color: #FF0000; }")
            self.status_label.setText('<span style="color:white;font-weight:bold;">Development!</span>')
        else:
            self.setStyleSheet("")
            self.status_label.setText("")

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
                    # Prefer local commit hash; if missing, fall back to remote
                    commit_hash = commit_data.get("local") or commit_data.get("remote") or ""
                # Try to read repository URL from app config so we can link commit
                repo_url = ""
                try:
                    app_cfg_path = os.path.join(BASE_PATH, "configs", "app_config.json")
                    if os.path.exists(app_cfg_path):
                        with open(app_cfg_path, "r", encoding="utf-8") as af:
                            app_cfg = json.load(af)
                            repo_url = app_cfg.get("links", {}).get("repo", "")
                except Exception:
                    repo_url = ""
                tag_icon = qta.icon("fa6s.tag")
                commit_icon = qta.icon("fa6s.code-commit")
                self.version_icon_label.setPixmap(tag_icon.pixmap(16, 16))
                self.version_text_label.setText(f"Version: {tag_local}" if tag_local else "")
                self.commit_icon_label.setPixmap(commit_icon.pixmap(16, 16))
                # If we have a commit hash, present short hash (clickable if repo URL available)
                if commit_hash:
                    short_hash = commit_hash[:7]
                    # tooltip shows the full hash
                    self.commit_text_label.setToolTip(commit_hash)
                    if repo_url:
                        # build commit url (handle trailing slash)
                        commit_url = f"{repo_url.rstrip('/')}/commit/{commit_hash}"
                        # show clickable HTML link (only the short hash, no 'Commit:' prefix)
                        self.commit_text_label.setTextFormat(Qt.RichText)
                        self.commit_text_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
                        self.commit_text_label.setOpenExternalLinks(True)
                        self.commit_text_label.setCursor(Qt.PointingHandCursor)
                        self.commit_text_label.setText(f"<a href=\"{commit_url}\">{short_hash}</a>")
                    else:
                        # No repo URL available; just show the short hash text
                        self.commit_text_label.setText(short_hash)
                else:
                    self.commit_text_label.setText("")
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
