from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
import qtawesome as qta
from ui.theme_system import theme


MONTHS = [
    'January', 'February', 'March', 'April',
    'May', 'June', 'July', 'August',
    'September', 'October', 'November', 'December'
]

MONTH_ICONS = [
    'fa6s.snowflake', 'fa6s.heart', 'fa6s.leaf', 'fa6s.seedling',
    'fa6s.sun', 'fa6s.umbrella-beach', 'fa6s.fire', 'fa6s.campground',
    'fa6s.apple-whole', 'fa6s.ghost', 'fa6s.cloud-sun', 'fa6s.holly-berry'
]


class MonthItem(QFrame):
    clicked = Signal(int)

    def __init__(self, month_idx: int, parent=None):
        super().__init__(parent)
        self.month_idx = month_idx
        self._selected = False
        self._setup_ui()
        self._apply_style(False)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(16, 16)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label_text = 'All Year' if self.month_idx == -1 else MONTHS[self.month_idx]
        self._label = QLabel(label_text)
        self._label.setFont(QFont(theme.get_color('foreground'), 9))

        self._count_label = QLabel('')
        self._count_label.setFixedWidth(26)
        self._count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._count_label.setStyleSheet('font-size: 9px;')

        layout.addWidget(self._icon_label)
        layout.addWidget(self._label, 1)
        layout.addWidget(self._count_label)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_icon(theme.get_color('text_dark'))

    def _icon_name(self) -> str:
        return 'fa6s.calendar' if self.month_idx == -1 else MONTH_ICONS[self.month_idx]

    def _refresh_icon(self, color: str):
        try:
            self._icon_label.setPixmap(qta.icon(self._icon_name(), color=color).pixmap(14, 14))
        except Exception:
            self._icon_label.setText('')

    def set_count(self, count: int):
        self._count_label.setText(str(count) if count > 0 else '')

    def _apply_style(self, selected: bool):
        primary = theme.get_color('primary')
        text_dark = theme.get_color('text_dark')

        p = QColor(primary)
        pr, pg, pb = p.red(), p.green(), p.blue()

        if selected:
            self.setStyleSheet(f'''
                MonthItem {{
                    background-color: {primary};
                    border-radius: 4px;
                }}
            ''')
            self._label.setStyleSheet('color: white; font-weight: bold; font-size: 12px;')
            self._count_label.setStyleSheet('color: rgba(255,255,255,180); font-size: 9px;')
            self._refresh_icon('#ffffff')
        else:
            self.setStyleSheet(f'''
                MonthItem {{
                    background-color: transparent;
                    border-radius: 4px;
                }}
                MonthItem:hover {{
                    background-color: rgba({pr}, {pg}, {pb}, 0.12);
                }}
            ''')
            self._label.setStyleSheet('font-size: 12px;')
            self._count_label.setStyleSheet('font-size: 9px;')
            self._refresh_icon(text_dark)

    def set_selected(self, selected: bool):
        self._selected = selected
        self._apply_style(selected)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.month_idx)
        super().mousePressEvent(event)


class SidebarWidget(QWidget):
    month_selected = Signal(int)
    year_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_year = 2026
        self._month_items: list[MonthItem] = []
        self._setup_ui()

    def _setup_ui(self):
        self.setMinimumWidth(150)
        self.setMaximumWidth(260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(4)

        year_frame = QFrame()
        year_layout = QHBoxLayout(year_frame)
        year_layout.setContentsMargins(6, 4, 6, 4)
        year_layout.setSpacing(4)

        btn_style = ''
        self._prev_btn = QPushButton()
        self._prev_btn.setFixedSize(24, 24)
        self._prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        try:
            self._prev_btn.setIcon(qta.icon('fa6s.chevron-left'))
        except Exception:
            self._prev_btn.setText('<')
        self._prev_btn.clicked.connect(self._prev_year)

        self._year_label = QLabel(str(self._current_year))
        self._year_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setBold(True)
        font.setPointSize(13)
        self._year_label.setFont(font)
        self._year_label.setStyleSheet(f'color: {theme.get_color("primary")};')

        self._next_btn = QPushButton()
        self._next_btn.setFixedSize(24, 24)
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        try:
            self._next_btn.setIcon(qta.icon('fa6s.chevron-right'))
        except Exception:
            self._next_btn.setText('>')
        self._next_btn.clicked.connect(self._next_year)

        year_layout.addWidget(self._prev_btn)
        year_layout.addWidget(self._year_label, 1)
        year_layout.addWidget(self._next_btn)
        layout.addWidget(year_frame)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(divider)

        months_lbl = QLabel('MONTHS')
        months_lbl.setStyleSheet('font-size: 9px; font-weight: bold; letter-spacing: 1px; padding: 2px 4px 1px 4px;')
        layout.addWidget(months_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        months_container = QWidget()
        months_layout = QVBoxLayout(months_container)
        months_layout.setContentsMargins(0, 0, 0, 0)
        months_layout.setSpacing(1)

        all_item = MonthItem(-1)
        all_item.clicked.connect(self._on_month_clicked)
        self._month_items.append(all_item)
        months_layout.addWidget(all_item)

        for i in range(12):
            item = MonthItem(i)
            item.clicked.connect(self._on_month_clicked)
            self._month_items.append(item)
            months_layout.addWidget(item)

        months_layout.addStretch()
        scroll.setWidget(months_container)
        layout.addWidget(scroll, 1)

    def _prev_year(self):
        self._current_year -= 1
        self._year_label.setText(str(self._current_year))
        self.year_changed.emit(self._current_year)

    def _next_year(self):
        self._current_year += 1
        self._year_label.setText(str(self._current_year))
        self.year_changed.emit(self._current_year)

    def _on_month_clicked(self, month_idx: int):
        self._select_item(month_idx)
        signal_val = 0 if month_idx == -1 else month_idx + 1
        self.month_selected.emit(signal_val)

    def _select_item(self, month_idx: int):
        for item in self._month_items:
            item.set_selected(item.month_idx == month_idx)

    def set_selected_month(self, month_idx: int):
        self._select_item(month_idx)

    def set_month_counts(self, counts: dict):
        total = sum(counts.values())
        for item in self._month_items:
            if item.month_idx == -1:
                item.set_count(total)
            else:
                item.set_count(counts.get(item.month_idx + 1, 0))

    def set_year(self, year: int):
        self._current_year = year
        self._year_label.setText(str(year))

    def get_year(self) -> int:
        return self._current_year
