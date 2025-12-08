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
        self.version_btn = QPushButton()
        self.version_btn.setCursor(Qt.PointingHandCursor)
        self.version_btn.setFlat(True)
        self.version_btn.setStyleSheet(
            "QPushButton { border-radius: 4px; padding: 2px 8px; font-weight: bold; }"
            "QPushButton:hover { background-color: #4e9e20; color: white; }"
        )
        self.version_btn.installEventFilter(self)
        
        self._version_url = None
        self._commit_url = None
        self.version_btn.clicked.connect(self._on_version_clicked)
        self.commit_btn = QPushButton()
        self.commit_btn.setCursor(Qt.PointingHandCursor)
        self.commit_btn.setFlat(True)
        self.commit_btn.setStyleSheet(
            "QPushButton { border-radius: 4px; padding: 2px 8px; font-weight: bold; }"
            "QPushButton:hover { background-color: #4e9e20; color: white; }"
        )
        self.commit_btn.installEventFilter(self)
        self.commit_btn.clicked.connect(self._on_commit_clicked)
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
        layout.addWidget(self.version_btn)
        layout.addWidget(self.commit_btn)
        layout.addWidget(self.update_btn)
        self.version_commit_widget.setLayout(layout)
        self.addWidget(self.status_label)
        self.addPermanentWidget(self.version_commit_widget)

        
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

    def eventFilter(self, obj, event):
        
        try:
            from PySide6.QtCore import QEvent
            enter_type = QEvent.Enter
            leave_type = QEvent.Leave
        except Exception:
            enter_type = 10
            leave_type = 11
        if obj == self.version_btn:
            if event.type() == enter_type:
                tag_icon_white = qta.icon("fa6s.tag", color="white")
                self.version_btn.setIcon(tag_icon_white)
            elif event.type() == leave_type:
                tag_icon_default = qta.icon("fa6s.tag")
                self.version_btn.setIcon(tag_icon_default)
        elif obj == self.commit_btn:
            if event.type() == enter_type:
                commit_icon_white = qta.icon("fa6s.code-commit", color="white")
                self.commit_btn.setIcon(commit_icon_white)
            elif event.type() == leave_type:
                commit_icon_default = qta.icon("fa6s.code-commit")
                self.commit_btn.setIcon(commit_icon_default)
        return super().eventFilter(obj, event)

    def set_status(self, text):
        self.status_label.setText(text)

    def set_api_info(self, service=None, api_key=None):
        """Set API information in the status bar"""
        if service and api_key:
            
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
                    
                    commit_hash = commit_data.get("local") or commit_data.get("remote") or ""
                
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
                
                if tag_local and repo_url:
                    version_url = f"{repo_url.rstrip('/')}/releases/tag/{tag_local}"
                    self.version_btn.setIcon(tag_icon)
                    self.version_btn.setText(f"Version: {tag_local.replace('v', '', 1)}")
                    self.version_btn.setToolTip(f"Open release page for {tag_local}")
                    
                    self._version_url = version_url
                    self.version_btn.setEnabled(True)
                    self.version_btn.show()
                else:
                    self.version_btn.setIcon(tag_icon)
                    self.version_btn.setText(f"Version: {tag_local.replace('v', '', 1)}")
                    self.version_btn.setToolTip("")
                    self._version_url = None
                    self.version_btn.setEnabled(False)
                    self.version_btn.show()
                
                if commit_hash:
                    short_hash = commit_hash[:7]
                    self.commit_btn.setIcon(commit_icon)
                    self.commit_btn.setText(short_hash)
                    self.commit_btn.setToolTip(f"Open commit page for {commit_hash}")
                    if repo_url:
                        commit_url = f"{repo_url.rstrip('/')}/commit/{commit_hash}"
                        
                        self._commit_url = commit_url
                        self.commit_btn.setEnabled(True)
                        self.commit_btn.show()
                    else:
                        self.commit_btn.setEnabled(False)
                        self.commit_btn.show()
                else:
                    self.commit_btn.setIcon(commit_icon)
                    self.commit_btn.setText("")
                    self.commit_btn.setToolTip("")
                    self._commit_url = None
                    self.commit_btn.setEnabled(False)
                    self.commit_btn.hide()
                if tag_remote and tag_local and tag_remote != tag_local:
                    self.update_btn.setText(f"Update to {tag_remote} Now")
                    self.update_btn.setEnabled(True)
                    self.update_btn.show()
                else:
                    self.update_btn.setText("")
                    self.update_btn.setEnabled(False)
                    self.update_btn.hide()
        else:
            
            self.version_btn.setText("")
            self.version_btn.setIcon(qta.icon("fa6s.tag"))
            self.version_btn.setEnabled(False)
            self.version_btn.hide()
            self.commit_btn.setText("")
            self.commit_btn.setIcon(qta.icon("fa6s.code-commit"))
            self.commit_btn.setEnabled(False)
            self.commit_btn.hide()
            self.update_btn.setText("")
            self.update_btn.setEnabled(False)
            self.update_btn.hide()

    def _open_url(self, url):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))

    def _on_version_clicked(self):
        if getattr(self, "_version_url", None):
            self._open_url(self._version_url)

    def _on_commit_clicked(self):
        if getattr(self, "_commit_url", None):
            self._open_url(self._commit_url)

    def _on_update_now_clicked(self):
        try:
            from ui.main_menu import run_updater
            run_updater(self.parent())
        except Exception as e:
            print(f"Failed to run updater from statusbar: {e}")
