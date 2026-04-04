from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit


class ScriptsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.script_editor = QTextEdit()
        self.script_editor.setPlaceholderText('Script content will appear here...')
        self.script_editor.setReadOnly(True)
        layout.addWidget(self.script_editor)
