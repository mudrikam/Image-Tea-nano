from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QFrame, QProgressBar, QTabWidget, QWidget
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon
import qtawesome as qta
import os
import json
import webbrowser
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
        self.setWindowIcon(QIcon(os.path.join(BASE_PATH, "res", "image_tea.ico")))
        self.resize(380, 400)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(6)

        icon_label = QLabel()
        icon_label.setPixmap(qta.icon("fa6s.id-badge", color=theme.get_color("primary")).pixmap(48, 48))
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

        tabs = QTabWidget()
        main_layout.addWidget(tabs)

        # --- Login tab ---
        login_tab = QWidget()
        login_layout = QVBoxLayout(login_tab)
        login_layout.setContentsMargins(12, 12, 12, 12)
        login_layout.setSpacing(8)

        login_layout.addStretch()

        email_label = QLabel("Email")
        email_label.setStyleSheet(f"color: {theme.get_color('text_light')};")
        login_layout.addWidget(email_label)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("email@example.com")
        self.email_input.setMinimumHeight(34)
        login_layout.addWidget(self.email_input)

        license_label = QLabel("License Key")
        license_label.setStyleSheet(f"color: {theme.get_color('text_light')};")
        login_layout.addWidget(license_label)

        license_layout = QHBoxLayout()
        self.license_input = QLineEdit()
        self.license_input.setPlaceholderText("DSNA-XXXX")
        self.license_input.setMinimumHeight(34)
        self.license_input.setEchoMode(QLineEdit.Password)
        license_layout.addWidget(self.license_input)
        self.show_license_check = QCheckBox("Show")
        self.show_license_check.setFixedWidth(60)
        self.show_license_check.toggled.connect(self._toggle_license_visibility)
        license_layout.addWidget(self.show_license_check)
        login_layout.addLayout(license_layout)

        self.remember_checkbox = QCheckBox("Remember login")
        login_layout.addWidget(self.remember_checkbox)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        login_layout.addWidget(self.progress_bar)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color: {theme.get_color('error')}; font-size: 12px;")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setWordWrap(True)
        login_layout.addWidget(self.error_label)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

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

        login_layout.addLayout(btn_layout)
        login_layout.addStretch()

        tabs.addTab(login_tab, qta.icon("fa6s.right-to-bracket"), " Login")

        # --- Register tab ---
        register_tab = QWidget()
        register_layout = QVBoxLayout(register_tab)
        register_layout.setContentsMargins(20, 20, 20, 20)
        register_layout.setSpacing(12)

        self._register_url = self._load_register_url()

        register_layout.addStretch()

        reg_icon = QLabel()
        reg_icon.setPixmap(qta.icon("fa6s.cart-shopping", color=theme.get_color("primary")).pixmap(48, 48))
        reg_icon.setAlignment(Qt.AlignCenter)
        register_layout.addWidget(reg_icon)

        reg_title = QLabel("Register Member Image Tea")
        reg_title.setAlignment(Qt.AlignCenter)
        reg_title.setStyleSheet("font-size: 13px; font-weight: bold;")
        register_layout.addWidget(reg_title)

        reg_desc_en = QLabel(
            "To register as an Image Tea member, please checkout at the link below."
        )
        reg_desc_en.setAlignment(Qt.AlignCenter)
        reg_desc_en.setWordWrap(True)
        reg_desc_en.setStyleSheet(f"color: {theme.get_color('text_light')}; font-size: 11px;")
        register_layout.addWidget(reg_desc_en)

        reg_desc_id = QLabel(
            "Untuk mendaftar menjadi member Image Tea, silakan checkout di tautan di bawah ini."
        )
        reg_desc_id.setAlignment(Qt.AlignCenter)
        reg_desc_id.setWordWrap(True)
        reg_desc_id.setStyleSheet(f"color: {theme.get_color('text_light')}; font-size: 11px;")
        register_layout.addWidget(reg_desc_id)

        checkout_btn = QPushButton(qta.icon("fa6s.cart-shopping", color=theme.get_color("white")), " Checkout Now")
        checkout_btn.setMinimumHeight(38)
        checkout_btn.setCursor(Qt.PointingHandCursor)
        checkout_btn.setStyleSheet(
            f"QPushButton {{ background-color: {theme.get_color('primary')}; color: {theme.get_color('white')}; border-radius: 5px; "
            f"padding: 5px 14px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {theme.get_color('primary_hover')}; }}"
        )
        checkout_btn.clicked.connect(lambda: webbrowser.open(self._register_url))
        register_layout.addWidget(checkout_btn)

        register_layout.addStretch()

        tabs.addTab(register_tab, qta.icon("fa6s.user-plus"), " Register")

        self._worker = None
        self._load_saved_credentials()

    def closeEvent(self, event):
        super().closeEvent(event)

    def _load_register_url(self):
        config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg["links"]["register_member"]

    @staticmethod
    def get_register_url():
        config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg["links"]["register_member"]

    def _load_saved_credentials(self):
        from helpers.members_helper.members_helper import load_saved_credentials
        creds = load_saved_credentials()
        if creds:
            self.email_input.setText(creds.get("email", ""))
            self.license_input.setText(creds.get("license", ""))
            self.remember_checkbox.setChecked(True)

    def _set_loading(self, loading: bool):
        self.login_btn.setEnabled(not loading)
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

    def _toggle_license_visibility(self, checked):
        self.license_input.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
