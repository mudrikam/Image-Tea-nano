from html import escape

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextBrowser, QLineEdit,
    QPushButton, QFrame
)
import qtawesome as qta


class RefinePanel(QWidget):
    submit_requested = Signal(str)
    retry_requested = Signal()
    fix_errors_requested = Signal()
    interrupt_requested = Signal()
    new_session_requested = Signal()
    clear_session_requested = Signal()
    hide_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._session_active = False
        self._build_ui()
        self._set_idle_state()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel('Refine Session')
        title.setStyleSheet('font-size: 14px; font-weight: bold;')
        header.addWidget(title)
        header.addStretch()

        new_btn = QPushButton(qta.icon('fa6s.plus'), 'New Session')
        new_btn.setToolTip('Start a new refinement session')
        new_btn.clicked.connect(self._on_new_session)
        header.addWidget(new_btn)

        clear_btn = QPushButton(qta.icon('fa6s.eraser'), '')
        clear_btn.setToolTip('Clear visible session history')
        clear_btn.clicked.connect(self._on_clear_session)
        header.addWidget(clear_btn)

        hide_btn = QPushButton(qta.icon('fa6s.xmark'), '')
        hide_btn.setToolTip('Hide refine panel')
        hide_btn.clicked.connect(self.hide_requested.emit)
        header.addWidget(hide_btn)
        layout.addLayout(header)

        self.history = QTextBrowser()
        self.history.setOpenExternalLinks(False)
        self.history.setPlaceholderText('Your refinement history will appear here.')
        layout.addWidget(self.history, 1)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(separator)

        self.input = QLineEdit()
        self.input.setPlaceholderText('Describe a change to the script...')
        self.input.returnPressed.connect(self._submit)
        layout.addWidget(self.input)

        action_row = QHBoxLayout()
        self.status_label = QLabel('Ready')
        self.status_label.setStyleSheet('color: #888;')
        action_row.addWidget(self.status_label)
        action_row.addStretch()

        self.interrupt_btn = QPushButton(qta.icon('fa6s.stop'), 'Interrupt')
        self.interrupt_btn.clicked.connect(self.interrupt_requested.emit)
        action_row.addWidget(self.interrupt_btn)

        self.retry_btn = QPushButton(qta.icon('fa6s.rotate-right'), 'Retry')
        self.retry_btn.clicked.connect(self.retry_requested.emit)
        action_row.addWidget(self.retry_btn)

        self.fix_errors_btn = QPushButton(qta.icon('fa6s.screwdriver-wrench'), 'Fix Errors')
        self.fix_errors_btn.clicked.connect(self.fix_errors_requested.emit)
        action_row.addWidget(self.fix_errors_btn)

        self.send_btn = QPushButton(qta.icon('fa6s.wand-magic-sparkles'), 'Refine')
        self.send_btn.setDefault(True)
        self.send_btn.clicked.connect(self._submit)
        action_row.addWidget(self.send_btn)
        layout.addLayout(action_row)

    def _submit(self):
        instruction = self.input.text().strip()
        if not instruction or not self.send_btn.isEnabled():
            return
        self._session_active = True
        self.retry_btn.setVisible(False)
        self.fix_errors_btn.setVisible(False)
        self._append_entry('You', escape(instruction), '#4ea1ff')
        self.input.clear()
        self.set_busy(True)
        self.submit_requested.emit(instruction)

    def _on_new_session(self):
        self.history.clear()
        self.input.clear()
        self._session_active = False
        self._set_idle_state()
        self.new_session_requested.emit()

    def _on_clear_session(self):
        self.history.clear()
        self._session_active = False
        self._set_idle_state()
        self.clear_session_requested.emit()

    def _append_entry(self, label, text, color):
        self.history.append(
            f'<p><b style="color:{color};">{label}</b><br>{text}</p>'
        )

    def add_change(self, turn, instruction, added, removed):
        summary = (
            f'Turn {turn}<br>'
            f'<span style="color:#aaa;">Instruction:</span> {escape(instruction)}<br>'
            f'<span style="color:#72c98a;">Added: +{added} lines</span> &nbsp; '
            f'<span style="color:#e06c75;">Removed: -{removed} lines</span>'
        )
        self._append_entry('AI change', summary, '#72c98a')

    def add_status(self, text, success=True):
        color = '#72c98a' if success else '#e06c75'
        self._append_entry('Status', escape(text), color)

    def add_step(self, text):
        self._append_entry('Step', escape(text), '#c39bff')

    def show_retry(self, visible=True):
        self.retry_btn.setVisible(visible)

    def show_fix_errors(self, visible=True):
        self.fix_errors_btn.setVisible(visible)

    def clear_actions(self):
        self.retry_btn.setVisible(False)
        self.fix_errors_btn.setVisible(False)

    def set_busy(self, busy):
        self.send_btn.setEnabled(not busy)
        self.input.setEnabled(not busy)
        self.interrupt_btn.setEnabled(busy)
        self.retry_btn.setEnabled(not busy)
        self.fix_errors_btn.setEnabled(not busy)
        self.status_label.setText('Refining...' if busy else 'Ready')

    def _set_idle_state(self):
        self.clear_actions()
        self.set_busy(False)
