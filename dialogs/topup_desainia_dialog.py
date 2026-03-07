from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QSizePolicy, QStackedWidget
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QIcon
import qtawesome as qta
import webbrowser
import os

from config import BASE_PATH
from ui.theme_system import theme


class TopupDesainiaDialog(QDialog):
    def __init__(self, topup_url: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Topup Desainia API Key")
        self.setMinimumSize(720, 540)
        self._topup_url = topup_url

        icon_path = os.path.join(BASE_PATH, "res", "image_tea.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._stack = QStackedWidget()

        fallback = self._make_fallback_widget()
        self._stack.addWidget(fallback)

        self._web_view = None
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            web_container = QWidget()
            web_vbox = QVBoxLayout(web_container)
            web_vbox.setContentsMargins(0, 0, 0, 0)
            self._web_view = QWebEngineView()
            self._web_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self._web_view.loadFinished.connect(self._on_load_finished)
            self._web_view.load(QUrl(self._topup_url))
            web_vbox.addWidget(self._web_view)
            self._stack.addWidget(web_container)
            self._stack.setCurrentIndex(1)
        except ImportError:
            pass

        layout.addWidget(self._stack, 1)

        btn_layout = QHBoxLayout()
        self.open_browser_btn = QPushButton("Open in Browser")
        self.open_browser_btn.setIcon(qta.icon('fa6s.arrow-up-right-from-square'))
        self.open_browser_btn.setToolTip("Open the topup page in your default browser")
        self.open_browser_btn.clicked.connect(self._open_in_browser)

        close_btn = QPushButton("Close")
        close_btn.setIcon(qta.icon('fa6s.xmark'))
        close_btn.clicked.connect(self.close)

        btn_layout.addWidget(self.open_browser_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def closeEvent(self, event):
        if self._web_view is not None:
            try:
                self._web_view.loadFinished.disconnect()
            except Exception:
                pass
            try:
                self._web_view.stop()
            except Exception as e:
                print(f"[TopupDesainiaDialog] closeEvent error: {e}")
        super().closeEvent(event)

    def _make_fallback_widget(self):
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setAlignment(Qt.AlignCenter)
        vbox.setSpacing(12)

        icon_lbl = QLabel()
        icon = qta.icon('fa6s.globe', color=theme.get_color('text_dark'))
        pix = icon.pixmap(64, 64)
        icon_lbl.setPixmap(pix)
        icon_lbl.setAlignment(Qt.AlignCenter)

        msg_lbl = QLabel("No internet connection or failed to load page.")
        msg_lbl.setAlignment(Qt.AlignCenter)
        msg_lbl.setStyleSheet(f"font-size: 14px; color: {theme.get_color('text_dark')};")

        vbox.addWidget(icon_lbl)
        vbox.addWidget(msg_lbl)
        return w

    def _on_load_finished(self, ok):
        if not ok:
            self._stack.setCurrentIndex(0)

    def _open_in_browser(self):
        try:
            webbrowser.open(self._topup_url)
        except Exception as e:
            print(f"[TopupDesainiaDialog] Failed to open browser: {e}")
