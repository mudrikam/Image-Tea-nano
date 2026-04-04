import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
import qtawesome as qta
from config import BASE_PATH
from ui.theme_system import theme


class VibeVideoGeneratorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Vibe Video Generator')
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint
        )
        self.resize(800, 600)
        self.setMinimumSize(600, 400)

        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel()
        try:
            pixmap = qta.icon('fa6s.video', color=theme.get_color('primary')).pixmap(64, 64)
        except Exception:
            pixmap = qta.icon('fa6s.video').pixmap(64, 64)
        icon_label.setPixmap(pixmap)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        title = QLabel('Vibe Video Generator')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet('font-size: 24px; font-weight: bold;')
        layout.addWidget(title)

        subtitle = QLabel('Coming Soon')
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet('font-size: 16px; color: gray;')
        layout.addWidget(subtitle)
