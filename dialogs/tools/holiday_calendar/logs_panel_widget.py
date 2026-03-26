from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QFrame
)
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QTextCursor, QColor
import qtawesome as qta
from ui.theme_system import theme
from helpers.tools.holiday_calendar_helper.holiday_logger import logger


LEVEL_COLORS = {
    'INFO':    '#4499ff',
    'SUCCESS': '#44bb77',
    'WARNING': '#ffaa00',
    'ERROR':   '#ff4455',
    'API':     '#aa77ff',
    'CACHE':   '#00cccc',
}


class LogsPanelWidget(QWidget):
    toggled = Signal(bool)
    def __init__(self, parent=None):
        super().__init__(parent)
        self._max_lines = 500
        self._collapsed = True
        self._setup_ui()
        logger.log_emitted.connect(self._on_log)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setFixedHeight(28)
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        hdr_lyt = QHBoxLayout(header)
        hdr_lyt.setContentsMargins(10, 0, 6, 0)
        hdr_lyt.setSpacing(6)

        self._toggle_icon = QLabel()
        self._update_toggle_icon()

        icon_lbl = QLabel()
        try:
            icon_lbl.setPixmap(qta.icon('fa6s.terminal', color=theme.get_color('text_dark')).pixmap(12, 12))
        except Exception:
            pass

        title = QLabel('Runtime Logs')
        title.setStyleSheet('font-size: 10px; font-weight: bold; letter-spacing: 1px;')
        title.setCursor(Qt.CursorShape.PointingHandCursor)

        hdr_lyt.addWidget(self._toggle_icon)
        hdr_lyt.addWidget(icon_lbl)
        hdr_lyt.addWidget(title)
        hdr_lyt.addStretch()

        clear_btn = QPushButton()
        clear_btn.setFixedSize(20, 20)
        clear_btn.setToolTip('Clear logs')
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        try:
            clear_btn.setIcon(qta.icon('fa6s.trash'))
        except Exception:
            clear_btn.setText('X')
        clear_btn.clicked.connect(self._clear)
        hdr_lyt.addWidget(clear_btn)

        header.mousePressEvent = lambda e: self._toggle()

        layout.addWidget(header)

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setStyleSheet('''
            QTextEdit {
                font-family: "Consolas", "Courier New", monospace;
                font-size: 10px;
                border: none;
                padding: 3px 8px;
            }
        ''')
        self._log_view.setVisible(False)
        layout.addWidget(self._log_view, 1)

    def _update_toggle_icon(self):
        try:
            name = 'fa6s.chevron-right' if self._collapsed else 'fa6s.chevron-down'
            self._toggle_icon.setPixmap(qta.icon(name, color=theme.get_color('text_dark')).pixmap(10, 10))
        except Exception:
            self._toggle_icon.setText('>' if self._collapsed else 'v')

    def _toggle(self):
        self._collapsed = not self._collapsed
        self._log_view.setVisible(not self._collapsed)
        self._update_toggle_icon()
        self.toggled.emit(self._collapsed)

    @Slot(str, str)
    def _on_log(self, level: str, entry: str):
        color = LEVEL_COLORS.get(level, '#999999')
        self._log_view.moveCursor(QTextCursor.MoveOperation.End)
        self._log_view.setTextColor(QColor(color))
        self._log_view.insertPlainText(entry + '\n')
        self._log_view.moveCursor(QTextCursor.MoveOperation.End)
        self._trim()

    def _trim(self):
        doc = self._log_view.document()
        while doc.blockCount() > self._max_lines:
            cursor = QTextCursor(doc.begin())
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()

    def _clear(self):
        self._log_view.clear()
