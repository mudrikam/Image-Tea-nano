from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QComboBox, QLineEdit,
    QPushButton, QLabel, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer
import qtawesome as qta
from ui.theme_system import theme


class FilterBarWidget(QWidget):
    country_changed = Signal(str)
    search_changed = Signal(str)
    view_mode_changed = Signal(str)
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_mode = 'list'
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._emit_search)
        self._setup_ui()

    def _setup_ui(self):
        self.setFixedHeight(44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        globe_lbl = QLabel()
        try:
            globe_lbl.setPixmap(qta.icon('fa6s.globe', color=theme.get_color('text_dark')).pixmap(14, 14))
        except Exception:
            pass
        globe_lbl.setFixedSize(16, 16)
        layout.addWidget(globe_lbl)

        self._country_combo = QComboBox()
        self._country_combo.setMinimumWidth(140)
        self._country_combo.setMaximumWidth(200)
        self._country_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._country_combo.currentIndexChanged.connect(self._on_country_changed)
        layout.addWidget(self._country_combo)

        sep = QLabel('|')
        layout.addWidget(sep)

        search_lbl = QLabel()
        try:
            search_lbl.setPixmap(qta.icon('fa6s.magnifying-glass', color=theme.get_color('text_dark')).pixmap(13, 13))
        except Exception:
            pass
        search_lbl.setFixedSize(16, 16)
        layout.addWidget(search_lbl)

        self._search_field = QLineEdit()
        self._search_field.setPlaceholderText('Search holidays...')
        self._search_field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._search_field.textChanged.connect(lambda: self._search_timer.start())
        layout.addWidget(self._search_field, 1)

        self._clear_btn = self._make_btn('fa6s.xmark', 'Clear search', lambda: self._search_field.clear())
        layout.addWidget(self._clear_btn)

        sep2 = QLabel('|')
        layout.addWidget(sep2)

        self._list_btn = self._make_btn('fa6s.list', 'List view', lambda: self._set_mode('list'))
        self._cal_btn = self._make_btn('fa6s.calendar-days', 'Calendar view', lambda: self._set_mode('calendar'))
        layout.addWidget(self._list_btn)
        layout.addWidget(self._cal_btn)

        self._refresh_btn = QPushButton()
        self._refresh_btn.setFixedSize(28, 28)
        self._refresh_btn.setToolTip('Refresh / Force reload from API')
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        try:
            self._refresh_btn.setIcon(qta.icon('fa6s.arrows-rotate', color=theme.get_color('primary')))
        except Exception:
            self._refresh_btn.setText('R')
        self._refresh_btn.clicked.connect(self.refresh_requested)
        layout.addWidget(self._refresh_btn)

        self._update_mode_buttons()

    def _make_btn(self, icon_name: str, tooltip: str, callback) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(28, 28)
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        try:
            btn.setIcon(qta.icon(icon_name))
        except Exception:
            pass
        btn.clicked.connect(callback)
        return btn

    def _set_mode(self, mode: str):
        self._current_mode = mode
        self._update_mode_buttons()
        self.view_mode_changed.emit(mode)

    def _update_mode_buttons(self):
        primary = theme.get_color('primary')

        if self._current_mode == 'list':
            try:
                self._list_btn.setIcon(qta.icon('fa6s.list', color=primary))
                self._cal_btn.setIcon(qta.icon('fa6s.calendar-days'))
            except Exception:
                pass
        else:
            try:
                self._cal_btn.setIcon(qta.icon('fa6s.calendar-days', color=primary))
                self._list_btn.setIcon(qta.icon('fa6s.list'))
            except Exception:
                pass

    def _on_country_changed(self, index: int):
        code = self._country_combo.itemData(index)
        if code:
            self.country_changed.emit(code)

    def _emit_search(self):
        self.search_changed.emit(self._search_field.text())

    def populate_countries(self, countries: list):
        self._country_combo.blockSignals(True)
        self._country_combo.clear()
        self._country_combo.addItem('\U0001f30d  World (All)', 'WORLD')
        for c in countries:
            self._country_combo.addItem(f"{c['code']} - {c['name']}", c['code'])
        self._country_combo.blockSignals(False)

    def set_country(self, code: str):
        self._country_combo.blockSignals(True)
        for i in range(self._country_combo.count()):
            if self._country_combo.itemData(i) == code.upper():
                self._country_combo.setCurrentIndex(i)
                break
        self._country_combo.blockSignals(False)

    def get_country(self) -> str:
        idx = self._country_combo.currentIndex()
        return self._country_combo.itemData(idx) or '' if idx >= 0 else ''

    def get_search_text(self) -> str:
        return self._search_field.text()

    def get_view_mode(self) -> str:
        return self._current_mode

    def set_view_mode(self, mode: str):
        self._current_mode = mode
        self._update_mode_buttons()
