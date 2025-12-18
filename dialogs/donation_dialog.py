from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
import os
import datetime
from config import BASE_PATH
import qtawesome as qta

def _get_donation_optout_path():
    return os.path.join(BASE_PATH, "temp", ".donation_optout")

def is_donation_optout_today():
    path = _get_donation_optout_path()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                date_str = f.read().strip()
            if date_str == datetime.date.today().isoformat():
                return True
        except Exception as e:
            print(f"Error reading donation opt-out file: {e}")
    return False

def set_donation_optout_today():
    path = _get_donation_optout_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(datetime.date.today().isoformat())
    except Exception as e:
        print(f"Error writing donation opt-out file: {e}")

class DonateDialog(QDialog):
    def __init__(self, parent=None, show_not_today=False):
        super().__init__(parent)
        self.setWindowTitle("Donate")
        self.setMinimumWidth(350)
        layout = QVBoxLayout(self)
        label = QLabel("Scan QRIS to donate:")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        image_path = os.path.join(BASE_PATH, "res", "images", "qris.jpeg")
        img_label = QLabel()
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            img_label.setPixmap(pixmap.scaledToWidth(300))
            img_label.setAlignment(Qt.AlignCenter)
        else:
            img_label.setText("QRIS image not found.")
            img_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(img_label)

        if show_not_today:
            button_layout = QHBoxLayout()
            button_layout.addStretch(1)
            not_today_btn = QPushButton(qta.icon('fa6s.xmark'), " Not Today")
            not_today_btn.clicked.connect(self._not_today)
            button_layout.addWidget(not_today_btn)
            layout.addLayout(button_layout)

    def _not_today(self):
        set_donation_optout_today()
        self.reject()
