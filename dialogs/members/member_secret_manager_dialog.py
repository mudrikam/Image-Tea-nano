import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtGui import QIcon, QFont
from PySide6.QtCore import Qt
import qtawesome as qta
from config import BASE_PATH
from ui.theme_system import theme
from dialogs.members.renew_secret_dialog import RenewSecretDialog


class MemberSecretManagerDialog(QDialog):
    """
    Centralized dialog for handling invalid/missing MEMBER_SECRET.
    Shows warning and offers to open RenewSecretDialog.
    Used by batch operations and other features requiring member secret.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Member Secret Required")
        self.setWindowIcon(QIcon(os.path.join(BASE_PATH, "res", "image_tea.ico")))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setFixedWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 14)
        layout.setSpacing(14)

        # Warning icon
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa6s.triangle-exclamation', color=theme.get_color('warning')).pixmap(40, 40))
        icon_label.setAlignment(Qt.AlignHCenter)
        layout.addWidget(icon_label)

        # Title
        title_label = QLabel('Member Secret Invalid')
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignHCenter)
        layout.addWidget(title_label)

        # Message
        msg_label = QLabel(
            "Your MEMBER_SECRET is missing, invalid, or expired.\n"
            "Update your secret to continue using member features."
        )
        msg_label.setWordWrap(True)
        msg_label.setAlignment(Qt.AlignHCenter)
        layout.addWidget(msg_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.renew_btn = QPushButton(qta.icon('fa6s.key'), 'Renew Member Secret...')
        self.cancel_btn = QPushButton(qta.icon('fa6s.xmark'), 'Cancel')

        btn_layout.addWidget(self.renew_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.renew_btn.clicked.connect(self._on_renew)
        self.cancel_btn.clicked.connect(self.reject)

    def _on_renew(self):
        dlg = RenewSecretDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.accept()
        # If user cancelled RenewSecretDialog, stay on this dialog
