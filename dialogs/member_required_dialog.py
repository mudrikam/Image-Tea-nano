import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtGui import QIcon, QFont
from PySide6.QtCore import Qt
import qtawesome as qta
from config import BASE_PATH
from ui.theme_system import theme


class MemberRequiredDialog(QDialog):
    def __init__(self, message, parent=None):
        super().__init__(parent)
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        self.setWindowTitle('Member Required')
        self.setWindowIcon(QIcon(icon_path))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setFixedWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 14)
        layout.setSpacing(14)

        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa6s.lock', color=theme.get_color('warning')).pixmap(40, 40))
        icon_label.setAlignment(Qt.AlignHCenter)
        layout.addWidget(icon_label)

        title_label = QLabel('Member Required')
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignHCenter)
        layout.addWidget(title_label)

        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setAlignment(Qt.AlignHCenter)
        layout.addWidget(msg_label)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.login_btn = QPushButton(qta.icon('fa6s.id-badge'), 'Login')
        self.close_btn = QPushButton(qta.icon('fa6s.xmark'), 'Close')

        btn_layout.addWidget(self.login_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

        self.login_btn.clicked.connect(self.accept)
        self.close_btn.clicked.connect(self.reject)
