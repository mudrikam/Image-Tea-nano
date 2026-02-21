from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QSizePolicy
from PySide6.QtGui import QPixmap, QPalette, QColor
from PySide6.QtCore import Qt, QUrl
import os
import datetime
import json
from config import BASE_PATH
import qtawesome as qta
import webbrowser

from ui.theme_system import theme

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
        label = QLabel("Donation")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        # determine lynk id url from config
        url = None
        try:
            cfg_path = os.path.join(BASE_PATH, "configs", "app_config.json")
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            url = cfg.get("links", {}).get("lynk_id")
        except Exception as e:
            print(f"[donation_dialog] failed reading config for donation url: {e}")

        def add_qris():
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

        loaded_page = False
        if url:
            try:
                from PySide6.QtWebEngineWidgets import QWebEngineView
                web = QWebEngineView()
                web.setUrl(QUrl(url))
                def _on_load(ok):
                    nonlocal loaded_page
                    if not ok:
                        print(f"[donation_dialog] web page failed to load, falling back to QRIS")
                        web.setParent(None)
                        web.deleteLater()
                        add_qris()
                    else:
                        loaded_page = True
                web.loadFinished.connect(_on_load)

                def _on_render_terminated(status, code):
                    print(f"[donation_dialog] render process terminated (status={status}, code={code}), falling back to QRIS")
                    if not loaded_page:
                        web.setParent(None)
                        web.deleteLater()
                        add_qris()
                web.renderProcessTerminated.connect(_on_render_terminated)

                layout.addWidget(web)
            except Exception as e:
                print(f"[donation_dialog] WebEngine unavailable or error: {e}")
                add_qris()
        else:
            add_qris()

        if show_not_today:
            button_layout = QHBoxLayout()
            button_layout.setContentsMargins(0, 0, 0, 0)
            button_layout.setSpacing(10)

            is_dark = self.palette().color(QPalette.Window).lightness() < 128

            treat_btn = QPushButton(qta.icon('fa6s.gift', color=theme.get_color('white')), " Treat Dev")
            treat_btn.setMinimumHeight(36)
            treat_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            treat_btn.clicked.connect(self._treat_dev)
            treat_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme.get_color('primary')};
                    color: {theme.get_color('white')};
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {theme.get_color('primary_hover')};
                }}
                QPushButton:pressed {{
                    background-color: {theme.get_color('primary_pressed')};
                }}
            """)
            button_layout.addWidget(treat_btn, 1)

            not_today_btn = QPushButton(qta.icon('fa6s.xmark'), " Not Today")
            not_today_btn.setMinimumHeight(36)
            not_today_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            not_today_btn.clicked.connect(self._not_today)

            if is_dark:
                _wht_q = QColor(theme.get_color('white'))
                _wht_rgb = f"{_wht_q.red()},{_wht_q.green()},{_wht_q.blue()}"
                not_today_style = f"""
                    QPushButton {{
                        background-color: rgba({_wht_rgb},0.06);
                        color: {theme.get_color('white')};
                        border-radius: 6px;
                        padding: 6px 12px;
                    }}
                    QPushButton:hover {{
                        background-color: rgba({_wht_rgb},0.09);
                    }}
                    QPushButton:pressed {{
                        background-color: rgba({_wht_rgb},0.12);
                    }}
                """
            else:
                _blk_q = QColor(theme.get_color('black'))
                _blk_rgb = f"{_blk_q.red()},{_blk_q.green()},{_blk_q.blue()}"
                not_today_style = f"""
                    QPushButton {{
                        background-color: rgba({_blk_rgb},0.06);
                        color: {theme.get_color('text_dark')};
                        border-radius: 6px;
                        padding: 6px 12px;
                    }}
                    QPushButton:hover {{
                        background-color: rgba({_blk_rgb},0.08);
                    }}
                    QPushButton:pressed {{
                        background-color: rgba({_blk_rgb},0.10);
                    }}
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
