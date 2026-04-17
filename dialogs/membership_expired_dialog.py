import os
import webbrowser
import json
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtGui import QIcon, QFont
from PySide6.QtCore import Qt
import qtawesome as qta
from config import BASE_PATH
from ui.theme_system import theme


class MembershipExpiredDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        self.setWindowTitle('Membership Expired')
        self.setWindowIcon(QIcon(icon_path))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setFixedWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 14)
        layout.setSpacing(14)

        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa6s.lock', color=theme.get_color('error')).pixmap(40, 40))
        icon_label.setAlignment(Qt.AlignHCenter)
        layout.addWidget(icon_label)

        title_label = QLabel('Membership Expired')
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignHCenter)
        layout.addWidget(title_label)

        msg_label = QLabel(
            'Your membership has expired. Please renew your membership to continue using Vibe Video Generator.'
        )
        msg_label.setWordWrap(True)
        msg_label.setAlignment(Qt.AlignHCenter)
        layout.addWidget(msg_label)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.renew_btn = QPushButton(qta.icon('fa6s.cart-shopping'), 'Renew Membership')
        self.close_btn = QPushButton(qta.icon('fa6s.xmark'), 'Close')

        btn_layout.addWidget(self.renew_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

        self.renew_btn.clicked.connect(self._on_renew)
        self.close_btn.clicked.connect(self.reject)

    def _on_renew(self):
        config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        url = cfg.get('purchese_links', {}).get('Purchese Membership')
        if url:
            webbrowser.open(url)
        self.accept()
