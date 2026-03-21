from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QFrame, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon
import qtawesome as qta
import os
from config import BASE_PATH
from ui.theme_system import theme


class _LoginWorker(QThread):
    success = Signal(dict)
    failed = Signal(str)

    def __init__(self, email, license_key):
        super().__init__()
        self.email = email
        self.license_key = license_key

    def run(self):
        from helpers.members_helper.members_helper import login_member
        try:
            member = login_member(self.email, self.license_key)
        except Exception as e:
            print(f"[LoginWorker] Connection error: {e}")
            self.failed.emit("Failed to connect to server. Check your internet connection.")
            return
        if member is None:
            self.failed.emit("Invalid email or license key.")
            return
        self.success.emit(member)

class MemberLoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Member Login")
        self.setMinimumWidth(380)
        self.setWindowIcon(QIcon(os.path.join(BASE_PATH, "res", "image_tea.ico")))

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(6)

        icon_label = QLabel()
        icon_label.setPixmap(qta.icon("fa6s.id-badge", color=theme.get_color("primary")).pixmap(32, 32))
        icon_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(icon_label)

        title = QLabel("Member Login")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        main_layout.addWidget(title)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(f"color: {theme.get_color('text_dark')};")
        main_layout.addWidget(separator)

        email_label = QLabel("Email")
        email_label.setStyleSheet(f"color: {theme.get_color('text_light')};")
        main_layout.addWidget(email_label)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("email@example.com")
        self.email_input.setMinimumHeight(34)
        main_layout.addWidget(self.email_input)

        license_label = QLabel("License Key")
        license_label.setStyleSheet(f"color: {theme.get_color('text_light')};")
        main_layout.addWidget(license_label)

        self.license_input = QLineEdit()
        self.license_input.setPlaceholderText("DSNA-XXXX")
        self.license_input.setMinimumHeight(34)
        main_layout.addWidget(self.license_input)

        self.remember_checkbox = QCheckBox("Remember login")
        main_layout.addWidget(self.remember_checkbox)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        main_layout.addWidget(self.progress_bar)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color: {theme.get_color('error')}; font-size: 12px;")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setWordWrap(True)
        main_layout.addWidget(self.error_label)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.cancel_btn = QPushButton(qta.icon("fa6s.xmark"), "Cancel")
        self.cancel_btn.setMinimumHeight(34)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.login_btn = QPushButton(qta.icon("fa6s.right-to-bracket", color=theme.get_color("white")), "Login")
        self.login_btn.setMinimumHeight(34)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.setStyleSheet(
            f"QPushButton {{ background-color: {theme.get_color('primary')}; color: {theme.get_color('white')}; "
            f"border-radius: 5px; padding: 5px 14px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {theme.get_color('primary_hover')}; }}"
        )
        self.login_btn.clicked.connect(self._on_login)
        btn_layout.addWidget(self.login_btn)

        main_layout.addLayout(btn_layout)

        self._worker = None
        self._load_saved_credentials()

    def _load_saved_credentials(self):
        from helpers.members_helper.members_helper import load_saved_credentials
        creds = load_saved_credentials()
        if creds:
            self.email_input.setText(creds.get("email", ""))
            self.license_input.setText(creds.get("license", ""))
            self.remember_checkbox.setChecked(True)

    def _set_loading(self, loading: bool):
        self.login_btn.setEnabled(not loading)
        self.cancel_btn.setEnabled(not loading)
        self.email_input.setEnabled(not loading)
        self.license_input.setEnabled(not loading)
        self.remember_checkbox.setEnabled(not loading)
        if loading:
            self.progress_bar.show()
            self.error_label.setText("")
        else:
            self.progress_bar.hide()

    def _on_login(self):
        email = self.email_input.text().strip()
        license_key = self.license_input.text().strip()

        if not email:
            self.error_label.setText("Email is required.")
            return
        if not license_key:
            self.error_label.setText("License key is required.")
            return

        self._set_loading(True)

        self._worker = _LoginWorker(email, license_key)
        self._worker.success.connect(self._on_login_success)
        self._worker.failed.connect(self._on_login_failed)
        self._worker.start()

    def _on_login_success(self, member):
        self._set_loading(False)

        if member.get("_error") == "device_locked":
            self.error_label.setText(
                "This license is locked to a different device.\n"
                "Contact support to reset your device lock."
            )
            return

        from helpers.members_helper.members_helper import save_credentials, clear_saved_credentials
        email = self.email_input.text().strip()
        license_key = self.license_input.text().strip()
        if self.remember_checkbox.isChecked():
            save_credentials(email, license_key)
        else:
            clear_saved_credentials()

        self.accept()

    def _on_login_failed(self, message):
        self._set_loading(False)
        self.error_label.setText(message)
