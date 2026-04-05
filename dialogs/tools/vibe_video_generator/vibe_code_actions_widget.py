from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton
from PySide6.QtCore import Qt
import qtawesome as qta
from ui.theme_system import theme


class CodeActionsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setContentsMargins(0, 0, 0, 0)
        self.actions_tab = QWidget()
        self._setup_actions_tab()
        self.tabs.addTab(self.actions_tab, 'Actions')
        layout.addWidget(self.tabs)

    def _setup_actions_tab(self):
        layout = QVBoxLayout(self.actions_tab)
        layout.setContentsMargins(4, 4, 4, 4)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.render_btn = QPushButton('Render Video')
        self.render_btn.setMinimumHeight(40)
        self.render_btn.setMinimumWidth(220)
        self.render_btn.setIcon(qta.icon('fa6s.film', color=theme.get_color('white')))
        self.render_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.render_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.get_color('primary')};
                color: {theme.get_color('white')};
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {theme.get_color('primary_hover')};
            }}
            QPushButton:pressed {{
                background-color: {theme.get_color('primary_pressed')};
            }}
        """)
        btn_layout.addWidget(self.render_btn)
        layout.addLayout(btn_layout)
