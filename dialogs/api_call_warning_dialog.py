from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt
import qtawesome as qta

from ui.theme_system import theme

class ApiCallWarningDialog(QDialog):
    def __init__(self, parent=None, file_count=None):
        super().__init__(parent)
        self.setWindowTitle("Warning: Large Batch Generation")
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.setContentsMargins(24, 24, 24, 24)

        icon_label = QLabel()
        warn_icon = qta.icon('fa6s.triangle-exclamation', color=theme.get_color('warning'))
        icon_pixmap = warn_icon.pixmap(48, 48)
        icon_label.setPixmap(icon_pixmap)
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        count_text = f"{file_count:,}"
        label1 = QLabel(f"You are about to generate metadata for {count_text} files.")
        label1.setAlignment(Qt.AlignCenter)
        label1.setStyleSheet(f"color: {theme.get_color('warning')}; font-weight: bold; font-size: 18px;")
        layout.addWidget(label1)

        est_token = 0
        if file_count is not None:
            est_token = file_count * 3000
        label2 = QLabel(
            "This may take a long time and could use a lot of API quota.\n\n"
            "A large number of API requests in a short time \ncan quickly exhaust your API quota and reach platform limits,\n"
            "causing some files to fail to generate.\n\n"
            f"Estimated total tokens needed: {est_token:,} tokens \n(assuming 3,000 per file input and output)."
        )
        label2.setAlignment(Qt.AlignCenter)
        label2.setStyleSheet("font-size: 14px;")
        layout.addWidget(label2)

        note_label = QLabel(
            "Note: All API token consumption is entirely the responsibility of the user.\n"
            "Desainia Studio (developer) is not responsible for any API usage or charges incurred.\n"
            "Please check your API quota before proceeding."
        )
        note_label.setAlignment(Qt.AlignCenter)
        note_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(note_label)

        label3 = QLabel("By continuing, you acknowledge and understand the above risks.")
        label3.setAlignment(Qt.AlignCenter)
        label3.setStyleSheet(f"color: {theme.get_color('error')}; font-weight: bold; font-size: 12px;")
        layout.addWidget(label3)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        self.continue_btn = QPushButton(qta.icon('fa6s.check'), "Continue")
        self.cancel_btn = QPushButton(qta.icon('fa6s.xmark'), "Cancel")
        button_layout.addWidget(self.continue_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

        self.continue_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
