import hashlib
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QSizePolicy, QStackedWidget,
    QApplication
)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QFont, QColor, QCursor
from PySide6.QtWidgets import QPushButton, QToolTip
import qtawesome as qta
from ui.theme_system import theme


_COLOR_PALETTE = [
    '#2563eb', '#dc2626', '#16a34a', '#d97706',
    '#7c3aed', '#0891b2', '#e11d48', '#059669',
    '#9333ea', '#ea580c', '#0d9488', '#4f46e5',
]


def _date_color(date_str: str) -> str:
    h = int(hashlib.md5(date_str.encode()).hexdigest(), 16)
    return _COLOR_PALETTE[h % len(_COLOR_PALETTE)]


class HolidayCard(QFrame):
    clicked = Signal(dict)

    def __init__(self, holiday: dict, color: str, parent=None):
        super().__init__(parent)
        self._holiday = holiday
        self._color = color
        self._active = False
        self._setup_ui()
        self._apply_style()

    def _apply_style(self):
        if self._active:
            self.setStyleSheet(f'''
                HolidayCard {{
                    border-left: 3px solid {self._color};
                    border-top: 1px solid {self._color};
                    border-right: 1px solid {self._color};
                    border-bottom: 1px solid {self._color};
                    border-radius: 5px;
                }}
            ''')
        else:
            self.setStyleSheet(f'''
                HolidayCard {{
                    border: 1px solid rgba(128,128,128,0.2);
                    border-left: 3px solid {self._color};
                    border-radius: 5px;
                }}
                HolidayCard:hover {{
                    border-left: 3px solid {self._color};
                    border-top: 1px solid {self._color};
                    border-right: 1px solid {self._color};
                    border-bottom: 1px solid {self._color};
                    border-radius: 5px;
                }}
            ''')

    def set_active(self, active: bool):
        self._active = active
        self._apply_style()

    def _setup_ui(self):
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 8, 7)
        layout.setSpacing(10)

        dot = QFrame()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f'QFrame {{ background-color: {self._color}; border-radius: 4px; border: none; }}')
        layout.addWidget(dot)

        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(10)
        name_label = QLabel(self._holiday.get('name', ''))
        name_label.setFont(name_font)
        name_label.setWordWrap(True)
        info_layout.addWidget(name_label)

        desc = self._holiday.get('description', '')
        if desc:
            desc_label = QLabel(desc)
            desc_label.setStyleSheet(f'font-size: 10px; color: {theme.get_color("text_dark")};')
            desc_label.setWordWrap(True)
            info_layout.addWidget(desc_label)

        layout.addLayout(info_layout, 1)

        right_lyt = QVBoxLayout()
        right_lyt.setContentsMargins(0, 0, 0, 0)
        right_lyt.setSpacing(3)
        right_lyt.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        date_lbl = QLabel(self._holiday.get('date', ''))
        date_lbl.setStyleSheet(f'color: {self._color}; font-size: 10px; font-weight: bold;')
        date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        primary_type = self._holiday.get('primary_type', '') or ''
        if not primary_type:
            types = self._holiday.get('type', [])
            primary_type = types[0] if isinstance(types, list) and types else ''
        type_lbl = QLabel(str(primary_type))
        c = QColor(_date_color(self._holiday.get('date', '2000-01-01')))
        r, g, b = c.red(), c.green(), c.blue()
        type_lbl.setStyleSheet(f'font-size: 9px; border-radius: 3px; padding: 1px 6px; background-color: rgba({r},{g},{b},0.18); color: rgba({r},{g},{b},1.0);')
        type_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        right_lyt.addWidget(date_lbl)
        right_lyt.addWidget(type_lbl)
        layout.addLayout(right_lyt)

        copy_btn = QPushButton()
        copy_btn.setFixedSize(20, 20)
        copy_btn.setToolTip('Copy holiday name')
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        try:
            copy_btn.setIcon(qta.icon('fa6s.copy'))
        except Exception:
            copy_btn.setText('\u29c9')
        _name = self._holiday.get('name', '')
        def _copy():
            QApplication.clipboard().setText(_name)
            QToolTip.showText(QCursor.pos(), f'Copied: {_name}')
        copy_btn.clicked.connect(_copy)
        layout.addWidget(copy_btn)

        arr = QLabel()
        try:
            arr.setPixmap(qta.icon('fa6s.chevron-right').pixmap(10, 10))
        except Exception:
            arr.setText('>')
        layout.addWidget(arr)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._holiday)
        super().mousePressEvent(event)


class DateGroupHeader(QFrame):
    def __init__(self, date_str: str, color: str, count: int, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        bar = QFrame()
        bar.setFixedSize(3, 16)
        bar.setStyleSheet(f'background-color: {color}; border-radius: 2px; border: none;')
        layout.addWidget(bar)

        date_lbl = QLabel(date_str)
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        date_lbl.setFont(font)
        date_lbl.setStyleSheet(f'color: {color};')
        layout.addWidget(date_lbl)

        badge = QLabel(f"{count} holiday{'s' if count > 1 else ''}")
        c = QColor(color)
        r, g, b = c.red(), c.green(), c.blue()
        badge.setStyleSheet(f'border-radius: 8px; padding: 1px 8px; font-size: 9px; background-color: rgba({r},{g},{b},0.18); color: rgba({r},{g},{b},1.0);')
        layout.addWidget(badge)
        layout.addStretch()


class EmptyState(QWidget):
    def __init__(self, message='No holidays found', parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel()
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        try:
            icon_lbl.setPixmap(qta.icon('fa6s.calendar-xmark', color=theme.get_color('text_dark')).pixmap(40, 40))
        except Exception:
            pass

        text_lbl = QLabel(message)
        text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_lbl.setStyleSheet('font-size: 13px;')

        layout.addWidget(icon_lbl)
        layout.addWidget(text_lbl)


class HolidayListWidget(QWidget):
    holiday_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._holidays = []
        self._filtered = []
        self._search_text = ''
        self._active_card = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(8, 8, 8, 8)
        self._content_layout.setSpacing(4)
        self._content_layout.addStretch()
        self._scroll.setWidget(self._content)

        self._empty_state = EmptyState('Select a month to load holidays')
        self._stack.addWidget(self._scroll)
        self._stack.addWidget(self._empty_state)
        self._stack.setCurrentWidget(self._empty_state)

        layout.addWidget(self._stack)

    def set_holidays(self, holidays: list):
        self._active_card = None
        self._holidays = holidays
        self._apply_filter()

    def set_search(self, text: str):
        self._search_text = text.lower()
        self._apply_filter()

    def _apply_filter(self):
        if self._search_text:
            self._filtered = [
                h for h in self._holidays
                if self._search_text in h.get('name', '').lower()
                or self._search_text in h.get('description', '').lower()
            ]
        else:
            self._filtered = list(self._holidays)
        self._render()

    def _render(self):
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._filtered:
            msg = 'No matching holidays' if self._search_text else 'No holidays found'
            self._empty_state = EmptyState(msg)
            self._stack.removeWidget(self._stack.widget(1))
            self._stack.addWidget(self._empty_state)
            self._stack.setCurrentIndex(1)
            return

        self._stack.setCurrentIndex(0)
        grouped = {}
        for h in self._filtered:
            d = h.get('date', 'unknown')
            grouped.setdefault(d, []).append(h)

        insert_pos = 0
        for date_str in sorted(grouped.keys()):
            holidays_for_date = grouped[date_str]
            color = _date_color(date_str)

            header = DateGroupHeader(date_str, color, len(holidays_for_date))
            self._content_layout.insertWidget(insert_pos, header)
            insert_pos += 1

            for h in holidays_for_date:
                card = HolidayCard(h, color)
                card.clicked.connect(self._on_card_clicked)
                self._content_layout.insertWidget(insert_pos, card)
                insert_pos += 1

    def _on_card_clicked(self, holiday: dict):
        if self._active_card and self._active_card != self.sender():
            self._active_card.set_active(False)
        card = self.sender()
        if isinstance(card, HolidayCard):
            card.set_active(True)
            self._active_card = card
        self.holiday_selected.emit(holiday)

    def show_loading(self):
        self._empty_state = EmptyState('Loading holidays...')
        self._stack.removeWidget(self._stack.widget(1))
        self._stack.addWidget(self._empty_state)
        self._stack.setCurrentIndex(1)

    def show_error(self, message: str):
        self._empty_state = EmptyState(f'Error: {message}')
        self._stack.removeWidget(self._stack.widget(1))
        self._stack.addWidget(self._empty_state)
        self._stack.setCurrentIndex(1)

    def clear(self):
        self._holidays = []
        self._filtered = []
        self._render()
