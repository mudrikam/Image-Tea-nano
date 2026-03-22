from PySide6.QtWidgets import QStatusBar, QLabel, QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt
import os
import json
from config import BASE_PATH
import qtawesome as qta
from ui.theme_system import theme

class MainStatusBar(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.status_label = QLabel("")
        self.version_btn = QPushButton()
        self.version_btn.setCursor(Qt.PointingHandCursor)
        self.version_btn.setFlat(True)
        self.version_btn.setStyleSheet(
            f"QPushButton {{ border-radius: 4px; padding: 2px 8px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {theme.get_color('primary')}; color: {theme.get_color('white')}; }}"
        )
        self.version_btn.installEventFilter(self)
        
        self._version_url = None
        self._commit_url = None
        self.version_btn.clicked.connect(self._on_version_clicked)
        self.commit_btn = QPushButton()
        self.commit_btn.setCursor(Qt.PointingHandCursor)
        self.commit_btn.setFlat(True)
        self.commit_btn.setStyleSheet(
            f"QPushButton {{ border-radius: 4px; padding: 2px 8px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {theme.get_color('primary')}; color: {theme.get_color('white')}; }}"
        )
        self.commit_btn.installEventFilter(self)
        self.commit_btn.clicked.connect(self._on_commit_clicked)
        self.update_btn = QPushButton()
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.setFlat(True)
        download_icon = qta.icon("fa6s.download", color=theme.get_color('white'))
        self.update_btn.setStyleSheet(
            f"QPushButton {{ color: {theme.get_color('white')}; background-color: {theme.get_color('primary')}; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {theme.get_color('primary_hover')}; }}"
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

        self.member_email_label = QLabel("")
        self.member_email_label.setStyleSheet(
            f"color: {theme.get_color('white')}; font-size: 12px; padding: 0 8px;"
        )
        self.member_email_label.hide()

        self.addWidget(self.status_label)
        self.addPermanentWidget(self.member_email_label)
        self.addPermanentWidget(self.version_commit_widget)

        
        self._versions_behind = 0
        self._check_env_and_set_style()
        self.update_version_and_commit()

    def _parse_version(self, tag):
        try:
            parts = tag.lstrip('v').split('.')
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0
            return major * 10000 + minor * 100 + patch
        except Exception:
            return 0

    def _check_env_and_set_style(self):
        from helpers.members_helper.members_helper import is_logged_in, get_session
        from datetime import datetime
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
        versions_behind = getattr(self, '_versions_behind', 0)
        if is_logged_in():
            session = get_session()
            email = session.get("email", "")
            status = session.get("status", "active")
            expires_at = session.get("expires_at")

            days_left = None
            is_expired = False
            if expires_at:
                try:
                    if isinstance(expires_at, str):
                        exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                        exp_dt = exp_dt.replace(tzinfo=None)
                    elif hasattr(expires_at, "year"):
                        exp_dt = expires_at.replace(tzinfo=None) if hasattr(expires_at, "tzinfo") and expires_at.tzinfo else expires_at
                    else:
                        exp_dt = None
                    if exp_dt:
                        days_left = (exp_dt - datetime.now().replace(tzinfo=None)).days
                        is_expired = days_left < 0
                except Exception:
                    pass

            member_inactive = (status not in ("active",)) or is_expired

            if member_inactive:
                self.setStyleSheet(f"QStatusBar {{ background-color: #c0392b; }}")
                self.status_label.setText(
                    f'<span style="color:white;font-weight:bold;">Membership expired or inactive. Renew or use your own API key.</span>'
                )
                self.member_email_label.setText(email)
                self.member_email_label.show()
            elif days_left is not None and days_left <= 7:
                self.setStyleSheet(f"QStatusBar {{ background-color: #e67e22; }}")
                self.status_label.setText(
                    f'<span style="color:white;font-weight:bold;">Member Active</span>'
                )
                self.member_email_label.setText(f"{email}  |  Expires in {days_left} day{'s' if days_left != 1 else ''}")
                self.member_email_label.show()
            else:
                self.setStyleSheet(f"QStatusBar {{ background-color: #1a6fbd; }}")
                self.status_label.setText(
                    f'<span style="color:{theme.get_color("white")};font-weight:bold;">Member Active</span>'
                )
                expiry_text = f"  |  Expires in {days_left} days" if days_left is not None else ""
                self.member_email_label.setText(f"{email}{expiry_text}")
                self.member_email_label.show()
        elif versions_behind >= 5:
            self.setStyleSheet(f"QStatusBar {{ background-color: {theme.get_color('warning')}; }}")
            self.status_label.setText(f'<span style="color:{theme.get_color("white")};font-weight:bold;">Image Tea is {versions_behind} updates behind, consider updating!</span>')
            self.member_email_label.hide()
        elif is_development:
            self.setStyleSheet(f"QStatusBar {{ background-color: {theme.get_color('error')}; }}")
            self.status_label.setText(f'<span style="color:{theme.get_color("white")};font-weight:bold;">Development!</span>')
            self.member_email_label.hide()
        else:
            self.setStyleSheet("")
            self.status_label.setText("")
            self.member_email_label.hide()

    def update_member_status(self):
        self._check_env_and_set_style()

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
                tag_icon_white = qta.icon("fa6s.tag", color=theme.get_color('white'))
                self.version_btn.setIcon(tag_icon_white)
            elif event.type() == leave_type:
                tag_icon_default = qta.icon("fa6s.tag")
                self.version_btn.setIcon(tag_icon_default)
        elif obj == self.commit_btn:
            if event.type() == enter_type:
                commit_icon_white = qta.icon("fa6s.code-commit", color=theme.get_color('white'))
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
                    remote_num = self._parse_version(tag_remote)
                    local_num = self._parse_version(tag_local)
                    self._versions_behind = max(0, remote_num - local_num)
                    self.update_btn.setText(f"Update to {tag_remote} Now")
                    self.update_btn.setEnabled(True)
                    self.update_btn.show()
                else:
                    self._versions_behind = 0
                    self.update_btn.setText("")
                    self.update_btn.setEnabled(False)
                    self.update_btn.hide()
                self._check_env_and_set_style()
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
            print(f"Failed to start update process from statusbar: {e}")
