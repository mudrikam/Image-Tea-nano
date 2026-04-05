from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QHBoxLayout, QPushButton, QMessageBox, QLabel
from PySide6.QtCore import Qt, Signal
import qtawesome as qta


class ScriptsWidget(QWidget):
    script_updated = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = parent.db if parent else None
        self.current_script_id = None
        self.current_script_name = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self.script_name_label = QLabel('No script selected')
        self.script_name_label.setStyleSheet('font-weight: bold; font-size: 12px; padding: 4px;')
        layout.addWidget(self.script_name_label)

        self.script_content = QTextEdit()
        self.script_content.setReadOnly(False)
        self.script_content.setFontFamily("Courier New")
        self.script_content.setFontPointSize(10)
        layout.addWidget(self.script_content)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.clear_btn = QPushButton('Clear')
        self.clear_btn.setIcon(qta.icon('fa6s.eraser'))
        self.clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(self.clear_btn)
        self.save_btn = QPushButton('Save')
        self.save_btn.setIcon(qta.icon('fa6s.floppy-disk'))
        self.save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    def display_script(self, script_data):
        self.current_script_id = script_data.get('id') if script_data else None
        self.current_script_name = script_data.get('name') if script_data else None
        has_script = script_data is not None
        self.clear_btn.setEnabled(has_script)
        self.save_btn.setEnabled(has_script)
        if script_data:
            self.script_name_label.setText(f"Script: {script_data.get('name', 'Unnamed')}")
            self.script_content.setPlainText(script_data.get('script_content', ''))
        else:
            self.script_name_label.setText('No script selected')
            self.script_content.clear()

    def update_script_name(self, new_name):
        self.current_script_name = new_name
        if new_name:
            self.script_name_label.setText(f"Script: {new_name}")

    def _on_clear(self):
        self.script_content.clear()

    def _on_save(self):
        if not self.db or not self.current_script_id:
            return
        script_content = self.script_content.toPlainText().strip()
        if not script_content:
            QMessageBox.warning(self, 'Validation Error', 'TypeScript content cannot be empty.')
            self.script_content.setFocus()
            return
        self.db.update_remotion_script(
            script_id=self.current_script_id,
            script_content=script_content
        )
        script_data = self.db.get_remotion_script(self.current_script_id)
        if script_data:
            self.update_script_name(script_data.get('name'))
        self.script_updated.emit(script_data)
