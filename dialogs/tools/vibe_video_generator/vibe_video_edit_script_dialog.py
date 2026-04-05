from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QTabWidget, QTextEdit, QWidget, QPushButton, QMessageBox)
from PySide6.QtCore import Qt, Signal
import qtawesome as qta


class EditScriptDialog(QDialog):
    script_created = Signal(object)
    script_updated = Signal(object)

    def __init__(self, parent=None, collection_id=None, db=None, script_id=None):
        super().__init__(parent)
        self.collection_id = collection_id
        self.db = db
        self.script_id = script_id
        self.is_editing = script_id is not None
        self.setWindowTitle('Edit Script' if self.is_editing else 'New Script')
        self.setMinimumSize(650, 500)
        self._setup_ui()
        if self.is_editing:
            self._load_script_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        name_layout = QHBoxLayout()
        name_label = QLabel('Script Name:')
        name_label.setMinimumWidth(100)
        name_layout.addWidget(name_label)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('Enter script name...')
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        desc_layout = QHBoxLayout()
        desc_label = QLabel('Description:')
        desc_label.setMinimumWidth(100)
        desc_layout.addWidget(desc_label)
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText('Brief description...')
        desc_layout.addWidget(self.desc_edit)
        layout.addLayout(desc_layout)

        tabs = QTabWidget()

        self.prompt_tab = QWidget()
        prompt_layout = QVBoxLayout(self.prompt_tab)
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText('Enter prompt...')
        prompt_layout.addWidget(self.prompt_edit)

        self.script_tab = QWidget()
        script_layout = QVBoxLayout(self.script_tab)
        self.script_edit = QTextEdit()
        self.script_edit.setPlaceholderText('Enter TypeScript code...')
        script_layout.addWidget(self.script_edit)

        tabs.addTab(self.prompt_tab, qta.icon('fa6s.message'), 'Prompt')
        tabs.addTab(self.script_tab, qta.icon('fa6s.code'), 'TypeScript')
        layout.addWidget(tabs)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton('Cancel')
        cancel_btn.setIcon(qta.icon('fa6s.xmark'))
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton('Save' if self.is_editing else 'Create')
        ok_btn.setIcon(qta.icon('fa6s.floppy-disk'))
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def _load_script_data(self):
        if not self.db or not self.script_id:
            return
        script_data = self.db.get_remotion_script(self.script_id)
        if script_data:
            self.name_edit.setText(script_data.get('name', ''))
            self.desc_edit.setText(script_data.get('description') or '')
            self.script_edit.setPlainText(script_data.get('script_content', ''))

    def accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, 'Validation Error', 'Script name cannot be empty.')
            self.name_edit.setFocus()
            return
        script_content = self.script_edit.toPlainText().strip()
        if not script_content:
            QMessageBox.warning(self, 'Validation Error', 'TypeScript content cannot be empty.')
            self.script_edit.setFocus()
            return

        description = self.desc_edit.text().strip() or None

        if self.db:
            if self.is_editing and self.script_id:
                self.db.update_remotion_script(
                    script_id=self.script_id,
                    name=name,
                    script_content=script_content,
                    description=description,
                )
                script_data = self.db.get_remotion_script(self.script_id)
                self.script_updated.emit(script_data)
            elif self.collection_id:
                script_id = self.db.add_remotion_script(
                    collection_id=self.collection_id,
                    name=name,
                    script_content=script_content,
                    description=description,
                )
                script_data = self.db.get_remotion_script(script_id)
                self.script_created.emit(script_data)

        super().accept()
