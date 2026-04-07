from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton, QComboBox, QLabel
from PySide6.QtCore import Qt
import qtawesome as qta
from ui.theme_system import theme


class CodeActionsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._render_settings_tab = None
        self._updating_from_render = False
        self._updating_from_actions = False
        self._setup_ui()

    def set_render_settings_tab(self, render_settings_tab):
        self._render_settings_tab = render_settings_tab
        if self._render_settings_tab:
            self._render_settings_tab.settings_changed.connect(self._on_render_settings_changed)
            self._populate_preset_combo()
            self._sync_preset_combo()

    def _on_render_settings_changed(self):
        self._sync_preset_combo()

    def _populate_preset_combo(self):
        if self._render_settings_tab:
            self.preset_combo.clear()
            for i in range(self._render_settings_tab.preset_combo.count()):
                text = self._render_settings_tab.preset_combo.itemText(i)
                data = self._render_settings_tab.preset_combo.itemData(i)
                self.preset_combo.addItem(text, data)

    def _sync_preset_combo(self):
        if self._render_settings_tab and hasattr(self, 'preset_combo'):
            current_render_preset = self._render_settings_tab.preset_combo.currentData()
            if current_render_preset and not self._updating_from_actions:
                self._updating_from_render = True
                idx = self.preset_combo.findData(current_render_preset)
                if idx >= 0:
                    self.preset_combo.setCurrentIndex(idx)
                self._updating_from_render = False

    def _on_preset_changed(self, index):
        if self._updating_from_render or self._render_settings_tab is None:
            return
        preset_key = self.preset_combo.currentData()
        if preset_key:
            self._updating_from_actions = True
            self._render_settings_tab.preset_combo.setCurrentIndex(
                self._render_settings_tab.preset_combo.findData(preset_key)
            )
            self._updating_from_actions = False

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

        main_row = QHBoxLayout()
        main_row.setSpacing(12)

        preset_layout = QHBoxLayout()
        preset_layout.setSpacing(8)
        preset_layout.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_layout.addWidget(self.preset_combo, 1)

        main_row.addLayout(preset_layout, 1)

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
        main_row.addWidget(self.render_btn)

        layout.addLayout(main_row)
