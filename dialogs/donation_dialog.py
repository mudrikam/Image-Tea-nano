from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QSizePolicy
from PySide6.QtGui import QPixmap, QPalette
from PySide6.QtCore import Qt
import os
import datetime
from config import BASE_PATH
import qtawesome as qta
import webbrowser

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
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(350)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        label = QLabel("Scan QRIS to donate:")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        image_path = os.path.join(BASE_PATH, "res", "images", "qris.jpeg")
        img_label = QLabel()
        img_label.setContentsMargins(0, 0, 0, 0)
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
            button_layout.setContentsMargins(0, 0, 0, 0)
            button_layout.setSpacing(10)

            is_dark = self.palette().color(QPalette.Window).lightness() < 128

            treat_btn = QPushButton(qta.icon('fa6s.gift', color='#ffffff'), " Treat Dev")
            treat_btn.setMinimumHeight(36)
            treat_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            treat_btn.clicked.connect(self._treat_dev)
            treat_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4e9e20;
                    color: white;
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #3d8e1a;
                }
                QPushButton:pressed {
                    background-color: #2f6b13;
                }
            """)
            button_layout.addWidget(treat_btn, 1)

            not_today_btn = QPushButton(qta.icon('fa6s.xmark'), " Not Today")
            not_today_btn.setMinimumHeight(36)
            not_today_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            not_today_btn.clicked.connect(self._not_today)

            if is_dark:
                not_today_style = """
                    QPushButton {
                        background-color: rgba(255,255,255,0.06);
                        color: #ffffff;
                        border-radius: 6px;
                        padding: 6px 12px;
                    }
                    QPushButton:hover {
                        background-color: rgba(255,255,255,0.09);
                    }
                    QPushButton:pressed {
                        background-color: rgba(255,255,255,0.12);
                    }
                """
            else:
                not_today_style = """
                    QPushButton {
                        background-color: rgba(0,0,0,0.06);
                        color: #222222;
                        border-radius: 6px;
                        padding: 6px 12px;
                    }
                    QPushButton:hover {
                        background-color: rgba(0,0,0,0.08);
                    }
                    QPushButton:pressed {
                        background-color: rgba(0,0,0,0.10);
                    }
                """

            not_today_btn.setStyleSheet(not_today_style)
            button_layout.addWidget(not_today_btn, 1)

            layout.addLayout(button_layout)

    def _not_today(self):
        set_donation_optout_today()
        self.reject()

    def _treat_dev(self):
        url = "https://lynk.id/desainiajob/s/8rov8rp3o695"
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"Error opening donation link: {e}")
        self.accept()
