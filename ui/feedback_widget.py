from PySide6.QtCore import QThread, Signal, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
import qtawesome as qta

from helpers.feedback_helper import (
    FIELD_LIMITS,
    FeedbackError,
    build_feedback_payload,
    collect_diagnostics,
    diagnostics_summary,
    submit_feedback,
)
from ui.theme_system import theme


_ACTIVE_FEEDBACK_WORKERS = set()
_SHUTDOWN_HOOK_CONNECTED = False


def wait_for_feedback_workers():
    """Prevent Qt from destroying a worker while its HTTP request is finishing."""
    for worker in tuple(_ACTIVE_FEEDBACK_WORKERS):
        if worker.isRunning():
            worker.requestInterruption()
            worker.wait(16_000)


class FeedbackSubmitWorker(QThread):
    submitted = Signal(dict)
    failed = Signal(str)

    def __init__(self, payload):
        super().__init__()
        self.payload = payload

    def run(self):
        try:
            result = submit_feedback(self.payload)
        except FeedbackError as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))
        except Exception:
            if not self.isInterruptionRequested():
                self.failed.emit("Feedback was not sent because an unexpected error occurred. Please retry.")
        else:
            if not self.isInterruptionRequested():
                self.submitted.emit(result)


class FeedbackSuccessDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Feedback Sent")
        self.resize(420, 200)
        self.setMinimumSize(360, 160)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        icon_label = QLabel(self)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setPixmap(qta.icon("fa6s.circle-check", color=theme.get_color("primary")).pixmap(48, 48))
        layout.addWidget(icon_label)

        message = QLabel(
            "Thank you for your feedback!\nYour submission has been received successfully.",
            self,
        )
        message.setAlignment(Qt.AlignCenter)
        message.setWordWrap(True)
        layout.addWidget(message)

        wa_btn = QPushButton(qta.icon("fa6s.share"), " Join WhatsApp Group for Updates", self)
        wa_btn.setCursor(Qt.PointingHandCursor)
        wa_btn.clicked.connect(self._open_whatsapp)

        close_btn = QPushButton(qta.icon("fa6s.xmark"), "Close", self)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(wa_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _open_whatsapp(self):
        QDesktopServices.openUrl(QUrl("https://chat.whatsapp.com/CMQvDxpCfP647kBBA6dRn3"))


class FeedbackWidget(QWidget):
    TYPE_LABELS = (
        ("Bug report", "bug_report"),
        ("Feature request", "request"),
        ("General feedback", "feedback"),
    )

    def __init__(self, parent=None):
        global _SHUTDOWN_HOOK_CONNECTED
        super().__init__(parent)
        self._worker = None
        self._diagnostics = collect_diagnostics()
        self._build_ui()
        app = QApplication.instance()
        if app is not None and not _SHUTDOWN_HOOK_CONNECTED:
            app.aboutToQuit.connect(wait_for_feedback_workers)
            _SHUTDOWN_HOOK_CONNECTED = True

    def _build_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer_layout.addWidget(scroll)

        content = QWidget(scroll)
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 18, 24, 24)
        layout.setSpacing(10)

        heading = QLabel("Send feedback", content)
        heading.setStyleSheet(f"font-size: 17pt; font-weight: bold; color: {theme.get_color('primary')};")
        layout.addWidget(heading)

        intro = QLabel("Report a problem, request a feature, or share an idea. All fields are required.", content)
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {theme.get_color('text_dark')};")
        layout.addWidget(intro)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)

        self.name_edit = QLineEdit(content)
        self.name_edit.setPlaceholderText("Your name")
        self.name_edit.setMaxLength(FIELD_LIMITS["name"])
        form.addRow("Name", self.name_edit)

        self.title_edit = QLineEdit(content)
        self.title_edit.setPlaceholderText("Short summary")
        self.title_edit.setMaxLength(FIELD_LIMITS["title"])
        form.addRow("Title", self.title_edit)

        self.type_combo = QComboBox(content)
        for label, value in self.TYPE_LABELS:
            self.type_combo.addItem(label, value)
        form.addRow("Type", self.type_combo)

        message_container = QWidget(content)
        message_layout = QVBoxLayout(message_container)
        message_layout.setContentsMargins(0, 0, 0, 0)
        message_layout.setSpacing(3)
        self.message_edit = QPlainTextEdit(message_container)
        self.message_edit.setPlaceholderText("Describe your feedback. Include steps to reproduce a bug when applicable.")
        self.message_edit.setMinimumHeight(150)
        self.message_edit.textChanged.connect(self._update_message_counter)
        message_layout.addWidget(self.message_edit)
        self.message_counter = QLabel(message_container)
        self.message_counter.setAlignment(Qt.AlignRight)
        self.message_counter.setStyleSheet(f"font-size: 9pt; color: {theme.get_color('text_dark')};")
        message_layout.addWidget(self.message_counter)
        form.addRow("Message", message_container)
        layout.addLayout(form)

        disclosure = QLabel(
            "The following non-sensitive diagnostics will be sent with your feedback. "
            "Image Tea does not include your hostname, account details, API keys, file paths, files, table data, or logs.",
            content,
        )
        disclosure.setWordWrap(True)
        disclosure.setStyleSheet(f"color: {theme.get_color('text_dark')};")
        layout.addWidget(disclosure)

        diagnostics_label = QLabel(diagnostics_summary(self._diagnostics), content)
        diagnostics_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        diagnostics_label.setStyleSheet(
            f"background-color: {theme.get_color('background_dark')}; "
            f"color: {theme.get_color('text_light')}; border-radius: 5px; padding: 9px;"
        )
        layout.addWidget(diagnostics_label)

        action_layout = QHBoxLayout()
        self.status_label = QLabel(content)
        self.status_label.setWordWrap(True)
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        action_layout.addWidget(self.status_label, 1)
        self.send_button = QPushButton(qta.icon("fa6s.paper-plane", color=theme.get_color("white")), "Send feedback", content)
        self.send_button.setCursor(Qt.PointingHandCursor)
        self.send_button.setMinimumHeight(36)
        self.send_button.setStyleSheet(
            f"QPushButton {{ background-color: {theme.get_color('primary')}; color: {theme.get_color('white')}; "
            "border: none; border-radius: 5px; padding: 6px 16px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {theme.get_color('primary_hover')}; }}"
            f"QPushButton:pressed {{ background-color: {theme.get_color('primary_pressed')}; }}"
            f"QPushButton:disabled {{ background-color: {theme.get_color('button_disabled_bg')}; "
            f"color: {theme.get_color('button_disabled_fg')}; }}"
        )
        self.send_button.clicked.connect(self._submit)
        action_layout.addWidget(self.send_button)
        layout.addLayout(action_layout)
        layout.addStretch()

        scroll.setWidget(content)
        self._form_widgets = (self.name_edit, self.title_edit, self.type_combo, self.message_edit)
        self._update_message_counter()

    def _update_message_counter(self):
        text = self.message_edit.toPlainText()
        limit = FIELD_LIMITS["message"]
        if len(text) > limit:
            cursor = self.message_edit.textCursor()
            position = min(cursor.position(), limit)
            self.message_edit.blockSignals(True)
            self.message_edit.setPlainText(text[:limit])
            cursor = self.message_edit.textCursor()
            cursor.setPosition(position)
            self.message_edit.setTextCursor(cursor)
            self.message_edit.blockSignals(False)
            text = text[:limit]
        self.message_counter.setText(f"{len(text):,} / {limit:,}")

    def _set_busy(self, busy):
        for widget in self._form_widgets:
            widget.setEnabled(not busy)
        self.send_button.setEnabled(not busy)

    def _set_status(self, message, color_key):
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {theme.get_color(color_key)};")

    def _submit(self):
        if self._worker and self._worker.isRunning():
            return
        try:
            payload = build_feedback_payload(
                self.name_edit.text(),
                self.title_edit.text(),
                self.type_combo.currentData(),
                self.message_edit.toPlainText(),
                self._diagnostics,
            )
        except FeedbackError as exc:
            self._set_status(str(exc), "error")
            return

        self._set_busy(True)
        self._set_status("Sending feedback...", "text_dark")
        worker = FeedbackSubmitWorker(payload)
        self._worker = worker
        _ACTIVE_FEEDBACK_WORKERS.add(worker)
        worker.submitted.connect(self._on_submitted)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(lambda current=worker: self._release_worker(current))
        worker.start()

    def _release_worker(self, worker):
        _ACTIVE_FEEDBACK_WORKERS.discard(worker)
        worker.deleteLater()
        if self._worker is worker:
            self._worker = None

    def _on_submitted(self, _result):
        self.name_edit.clear()
        self.title_edit.clear()
        self.type_combo.setCurrentIndex(0)
        self.message_edit.clear()
        self._set_busy(False)
        self._set_status("", "text_dark")
        dialog = FeedbackSuccessDialog(self.window())
        dialog.exec()

    def _on_failed(self, message):
        self._set_busy(False)
        self._set_status(message, "error")

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
        super().closeEvent(event)
