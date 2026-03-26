import calendar
import hashlib
from datetime import date as Date
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGridLayout, QFrame, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
import qtawesome as qta
from ui.theme_system import theme


WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def _date_color(date_str: str) -> str:
    palette = [
        '#ff6a00', '#ff3d71', '#00d4ff', '#00e096',
        '#ffaa00', '#c56cff', '#ff6cb6', '#61f4de',
        '#ffd166', '#06d6a0', '#ef476f', '#118ab2',
    ]
    h = int(hashlib.md5(date_str.encode()).hexdigest(), 16)
    return palette[h % len(palette)]


class CalendarCell(QFrame):
    clicked = Signal(str, list)

    def __init__(self, day: int, date_str: str, holidays: list, is_today: bool = False, parent=None):
        super().__init__(parent)
        self._day = day
        self._date_str = date_str
        self._holidays = holidays
        self._is_today = is_today
        self._setup_ui()

    def _setup_ui(self):
        has_holidays = bool(self._holidays)

        if self._is_today:
            self.setStyleSheet(f'''
                CalendarCell {{
                    background-color: {theme.get_color("primary")}22;
                    border: 1px solid {theme.get_color("primary")};
                    border-radius: 4px;
                }}
                CalendarCell:hover {{
                    border: 1px solid {theme.get_color("primary")};
                    background-color: {theme.get_color("primary")}33;
                }}
            ''')
        else:
            self.setStyleSheet(f'''
                CalendarCell {{
                    border: 1px solid {theme.get_color("text_dark")}33;
                    border-radius: 4px;
                }}
                CalendarCell:hover {{
                    border: 1px solid {theme.get_color("primary")}88;
                }}
            ''')
        self.setMinimumHeight(72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        if self._holidays:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(2)

        day_lbl = QLabel(str(self._day))
        day_font = QFont()
        if self._is_today:
            day_font.setBold(True)
        day_lbl.setFont(day_font)

        if self._is_today:
            day_lbl.setStyleSheet(f'''
                color: white;
                background-color: {theme.get_color("primary")};
                border-radius: 9px;
                padding: 0px 4px;
                font-weight: bold;
                font-size: 11px;
            ''')
            day_lbl.setFixedWidth(22)
            day_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            day_lbl.setStyleSheet('font-size: 11px;')
        layout.addWidget(day_lbl, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        for h in self._holidays[:3]:
            color = _date_color(h.get('date', ''))
            name = h.get('name', '')
            chip = QLabel(name[:14] + ('...' if len(name) > 14 else ''))
            chip.setStyleSheet(f'''
                color: {color};
                background-color: {color}22;
                border: 1px solid {color}55;
                border-radius: 2px;
                padding: 0px 3px;
                font-size: 8px;
            ''')
            chip.setWordWrap(False)
            layout.addWidget(chip)

        if len(self._holidays) > 3:
            more_lbl = QLabel(f'+{len(self._holidays) - 3}')
            more_lbl.setStyleSheet('font-size: 8px;')
            layout.addWidget(more_lbl)

        layout.addStretch()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._holidays:
            self.clicked.emit(self._date_str, self._holidays)
        super().mousePressEvent(event)


class EmptyCell(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


class CalendarViewWidget(QWidget):
    date_clicked = Signal(str, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._year = 2026
        self._month = 1
        self._holidays = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        header_frame = QFrame()
        header_lyt = QHBoxLayout(header_frame)
        header_lyt.setContentsMargins(12, 4, 12, 4)

        self._month_year_lbl = QLabel()
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        self._month_year_lbl.setFont(font)
        self._month_year_lbl.setStyleSheet(f'color: {theme.get_color("primary")};')
        header_lyt.addWidget(self._month_year_lbl)
        header_lyt.addStretch()

        self._count_lbl = QLabel()
        self._count_lbl.setStyleSheet('padding: 1px 8px; font-size: 10px;')
        header_lyt.addWidget(self._count_lbl)
        layout.addWidget(header_frame)

        weekday_frame = QFrame()
        wd_layout = QHBoxLayout(weekday_frame)
        wd_layout.setContentsMargins(0, 0, 0, 0)
        wd_layout.setSpacing(4)
        for wd in WEEKDAYS:
            lbl = QLabel(wd)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet('font-size: 9px; font-weight: bold; padding: 1px 0;')
            wd_layout.addWidget(lbl, 1)
        layout.addWidget(weekday_frame)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._grid_widget = QWidget()
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setSpacing(4)
        scroll.setWidget(self._grid_widget)
        layout.addWidget(scroll, 1)

    def set_month(self, year: int, month: int):
        self._year = year
        self._month = month
        self._render()

    def set_holidays(self, holidays: list):
        self._holidays = holidays
        self._render()

    def _render(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        import calendar as cal_mod
        month_name = cal_mod.month_name[self._month]
        self._month_year_lbl.setText(f'{month_name} {self._year}')
        self._count_lbl.setText(f'{len(self._holidays)} holidays')

        today = Date.today()
        date_holiday_map: dict = {}
        for h in self._holidays:
            ds = h.get('date', '')
            if ds:
                date_holiday_map.setdefault(ds, []).append(h)

        first_weekday, num_days = calendar.monthrange(self._year, self._month)
        row = 0
        col = first_weekday

        for day in range(1, num_days + 1):
            date_obj = Date(self._year, self._month, day)
            date_str = date_obj.isoformat()
            holidays_on_day = date_holiday_map.get(date_str, [])
            is_today = date_obj == today
            cell = CalendarCell(day, date_str, holidays_on_day, is_today)
            cell.clicked.connect(self.date_clicked)
            self._grid.addWidget(cell, row, col)
            col += 1
            if col > 6:
                col = 0
                row += 1

        if col > 0:
            for c in range(col, 7):
                self._grid.addWidget(EmptyCell(), row, c)

        for c in range(7):
            self._grid.setColumnStretch(c, 1)

    def clear(self):
        self._holidays = []
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._month_year_lbl.setText('')
        self._count_lbl.setText('')
