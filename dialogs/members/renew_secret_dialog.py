from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
import qtawesome as qta
import os
from config import BASE_PATH
from ui.theme_system import theme
from helpers.members_helper.members_helper import update_member_secret_in_env, _is_member_secret_format_valid


class RenewSecretDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Renew Member Secret")
        self.setWindowIcon(QIcon(os.path.join(BASE_PATH, "res", "image_tea.ico")))
        self.resize(420, 200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # Title section
        title_layout = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(qta.icon("fa6s.key", color=theme.get_color("primary")).pixmap(32, 32))
        title_layout.addWidget(icon)
        title = QLabel("Update MEMBER_SECRET")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        title_layout.addWidget(title)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        # Description
        desc = QLabel(
            "Enter your MEMBER_SECRET. The format is validated automatically."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 11px;")
        layout.addWidget(desc)

        # Input row (input + paste button)
        input_layout = QHBoxLayout()
        input_layout.setSpacing(5)
        self.secret_edit = QLineEdit()
        self.secret_edit.setPlaceholderText("Paste MEMBER_SECRET here...")
        self.secret_edit.setMinimumHeight(34)
        self.secret_edit.setEchoMode(QLineEdit.Password)  # Mask by default
        input_layout.addWidget(self.secret_edit, 1)  # stretch factor 1

        self.paste_btn = QPushButton(qta.icon('fa6s.paste'), "")
        self.paste_btn.setFixedWidth(34)
        self.paste_btn.setFixedHeight(34)
        self.paste_btn.setToolTip("Paste from clipboard")
        self.paste_btn.clicked.connect(self._paste_clipboard)
        input_layout.addWidget(self.paste_btn)

        layout.addLayout(input_layout)

        # Show password checkbox
        self.show_check = QCheckBox("Show characters")
        self.show_check.setChecked(False)
        self.show_check.toggled.connect(self._toggle_echo)
        layout.addWidget(self.show_check)

        # Buttons row (right-aligned)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.ok_btn = QPushButton(qta.icon('fa6s.check'), " Update")
        self.ok_btn.setMinimumWidth(90)
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._on_accept)
        btn_layout.addWidget(self.ok_btn)
        self.cancel_btn = QPushButton(qta.icon('fa6s.xmark'), " Cancel")
        self.cancel_btn.setMinimumWidth(90)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def _toggle_echo(self, checked):
        self.secret_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)

    def _paste_clipboard(self):
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.secret_edit.setText(text.strip())

    def _on_accept(self):
        raw = self.secret_edit.text().strip()
        if not raw:
            QMessageBox.warning(self, "Empty", "Please enter the MEMBER_SECRET.")
            return
        if raw.upper().startswith("MEMBER_SECRET="):
            raw = raw[len("MEMBER_SECRET="):]
        if not raw:
            QMessageBox.warning(self, "Invalid", "Could not extract secret from input.")
            return
        if not _is_member_secret_format_valid(raw):
            QMessageBox.warning(self, "Invalid", "MEMBER_SECRET format is not valid.")
            return
        if update_member_secret_in_env(raw):
            QMessageBox.information(self, "Success", "MEMBER_SECRET updated successfully.")
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to update .env file.")

    def get_secret(self) -> str:
        """Return the cleaned secret (without prefix)."""
        raw = self.secret_edit.text().strip()
        if raw.upper().startswith("MEMBER_SECRET="):
            raw = raw[len("MEMBER_SECRET="):]
        return raw
