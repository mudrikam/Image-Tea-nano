import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QGroupBox, QComboBox, QCheckBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import QApplication
import qtawesome as qta


class OutputTabWidget(QWidget):
    output_path_changed = Signal(str)
    entry_point_changed = Signal(str)
    composition_id_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.output_path = ''
        self.entry_point = ''
        self.composition_id = ''
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        output_group = QGroupBox('Output Path')
        output_layout = QVBoxLayout()
        output_layout.setSpacing(8)

        output_path_layout = QHBoxLayout()
        output_path_layout.setSpacing(8)

        output_icon = QLabel()
        output_icon.setPixmap(qta.icon('fa6s.folder', color='#888').pixmap(16, 16))
        output_path_layout.addWidget(output_icon)

        output_label = QLabel('Output:')
        output_label.setStyleSheet('font-weight: bold;')
        output_label.setMinimumWidth(60)
        output_path_layout.addWidget(output_label)

        self.output_path_input = QLineEdit()
        self.output_path_input.setPlaceholderText('Select output folder...')
        self.output_path_input.editingFinished.connect(self.on_output_edited)
        output_path_layout.addWidget(self.output_path_input, 1)

        self.output_paste_button = QPushButton(qta.icon('fa6s.paste'), '')
        self.output_paste_button.setToolTip('Paste from clipboard')
        self.output_paste_button.setMaximumWidth(32)
        self.output_paste_button.clicked.connect(self.on_paste_output)
        output_path_layout.addWidget(self.output_paste_button)

        self.output_browse_button = QPushButton(qta.icon('fa6s.folder-open'), '')
        self.output_browse_button.setToolTip('Browse folder')
        self.output_browse_button.setMaximumWidth(32)
        self.output_browse_button.clicked.connect(self.on_browse_output)
        output_path_layout.addWidget(self.output_browse_button)

        self.output_open_button = QPushButton(qta.icon('fa6s.arrow-up-right-from-square'), '')
        self.output_open_button.setToolTip('Open folder location')
        self.output_open_button.setMaximumWidth(32)
        self.output_open_button.clicked.connect(self.on_open_output)
        output_path_layout.addWidget(self.output_open_button)

        output_layout.addLayout(output_path_layout)

        output_format_layout = QHBoxLayout()
        output_format_layout.setSpacing(8)

        format_icon = QLabel()
        format_icon.setPixmap(qta.icon('fa6s.file-video', color='#888').pixmap(16, 16))
        output_format_layout.addWidget(format_icon)

        format_label = QLabel('Format:')
        format_label.setStyleSheet('font-weight: bold;')
        format_label.setMinimumWidth(60)
        output_format_layout.addWidget(format_label)

        self.output_format_combo = QComboBox()
        self.output_format_combo.addItems(['mp4', 'webm', 'mov', 'gif', 'png', 'jpg', 'mp3', 'wav', 'aac'])
        self.output_format_combo.currentTextChanged.connect(self.on_format_changed)
        output_format_layout.addWidget(self.output_format_combo, 1)

        output_layout.addLayout(output_format_layout)

        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        entry_group = QGroupBox('Entry Point')
        entry_layout = QVBoxLayout()
        entry_layout.setSpacing(8)

        entry_path_layout = QHBoxLayout()
        entry_path_layout.setSpacing(8)

        entry_icon = QLabel()
        entry_icon.setPixmap(qta.icon('fa6s.file-code', color='#888').pixmap(16, 16))
        entry_path_layout.addWidget(entry_icon)

        entry_label = QLabel('Entry:')
        entry_label.setStyleSheet('font-weight: bold;')
        entry_label.setMinimumWidth(60)
        entry_path_layout.addWidget(entry_label)

        self.entry_point_input = QLineEdit()
        self.entry_point_input.setPlaceholderText('Select entry point file (e.g., src/index.ts)...')
        self.entry_point_input.editingFinished.connect(self.on_entry_edited)
        entry_path_layout.addWidget(self.entry_point_input, 1)

        self.entry_paste_button = QPushButton(qta.icon('fa6s.paste'), '')
        self.entry_paste_button.setToolTip('Paste from clipboard')
        self.entry_paste_button.setMaximumWidth(32)
        self.entry_paste_button.clicked.connect(self.on_paste_entry)
        entry_path_layout.addWidget(self.entry_paste_button)

        self.entry_browse_button = QPushButton(qta.icon('fa6s.folder-open'), '')
        self.entry_browse_button.setToolTip('Browse file')
        self.entry_browse_button.setMaximumWidth(32)
        self.entry_browse_button.clicked.connect(self.on_browse_entry)
        entry_path_layout.addWidget(self.entry_browse_button)

        self.entry_open_button = QPushButton(qta.icon('fa6s.arrow-up-right-from-square'), '')
        self.entry_open_button.setToolTip('Open file location')
        self.entry_open_button.setMaximumWidth(32)
        self.entry_open_button.clicked.connect(self.on_open_entry)
        entry_path_layout.addWidget(self.entry_open_button)

        entry_layout.addLayout(entry_path_layout)
        entry_group.setLayout(entry_layout)
        layout.addWidget(entry_group)

        comp_group = QGroupBox('Composition')
        comp_layout = QVBoxLayout()
        comp_layout.setSpacing(8)

        comp_id_layout = QHBoxLayout()
        comp_id_layout.setSpacing(8)

        comp_icon = QLabel()
        comp_icon.setPixmap(qta.icon('fa6s.film', color='#888').pixmap(16, 16))
        comp_id_layout.addWidget(comp_icon)

        comp_label = QLabel('ID:')
        comp_label.setStyleSheet('font-weight: bold;')
        comp_label.setMinimumWidth(60)
        comp_id_layout.addWidget(comp_label)

        self.composition_id_input = QLineEdit()
        self.composition_id_input.setPlaceholderText('Enter composition ID...')
        self.composition_id_input.editingFinished.connect(self.on_composition_id_edited)
        comp_id_layout.addWidget(self.composition_id_input, 1)

        self.comp_paste_button = QPushButton(qta.icon('fa6s.paste'), '')
        self.comp_paste_button.setToolTip('Paste from clipboard')
        self.comp_paste_button.setMaximumWidth(32)
        self.comp_paste_button.clicked.connect(self.on_paste_composition_id)
        comp_id_layout.addWidget(self.comp_paste_button)

        comp_layout.addLayout(comp_id_layout)
        comp_group.setLayout(comp_layout)
        layout.addWidget(comp_group)

        options_group = QGroupBox('Output Options')
        options_layout = QVBoxLayout()
        options_layout.setSpacing(6)

        self.overwrite_checkbox = QCheckBox('Overwrite existing file')
        self.overwrite_checkbox.setChecked(True)
        options_layout.addWidget(self.overwrite_checkbox)

        self.sequence_checkbox = QCheckBox('Output as image sequence')
        options_layout.addWidget(self.sequence_checkbox)

        self.muted_checkbox = QCheckBox('Mute audio')
        options_layout.addWidget(self.muted_checkbox)

        self.enforce_audio_checkbox = QCheckBox('Enforce silent audio track')
        options_layout.addWidget(self.enforce_audio_checkbox)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        layout.addStretch()

    def _sanitize_path_text(self, text):
        if not isinstance(text, str):
            return text
        t = text.strip()
        if len(t) >= 2 and ((t[0] == '"' and t[-1] == '"') or (t[0] == "'" and t[-1] == "'")):
            return t[1:-1]
        return t

    def on_output_edited(self):
        self.output_path = self.output_path_input.text()
        self.output_path_changed.emit(self.output_path)

    def on_paste_output(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        sanitized = self._sanitize_path_text(text)
        if sanitized:
            self.output_path_input.setText(sanitized)
            self.output_path = sanitized
            self.output_path_changed.emit(sanitized)

    def on_browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, 'Select Output Folder', self.output_path)
        if folder:
            folder = self._sanitize_path_text(folder)
            self.output_path = folder
            self.output_path_input.setText(folder)
            self.output_path_changed.emit(folder)

    def on_open_output(self):
        path = self.output_path_input.text()
        if path and os.path.exists(path):
            os.startfile(path)

    def on_format_changed(self, format):
        pass

    def on_entry_edited(self):
        self.entry_point = self.entry_point_input.text()
        self.entry_point_changed.emit(self.entry_point)

    def on_paste_entry(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        sanitized = self._sanitize_path_text(text)
        if sanitized:
            self.entry_point_input.setText(sanitized)
            self.entry_point = sanitized
            self.entry_point_changed.emit(sanitized)

    def on_browse_entry(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Select Entry Point File', '',
            'TypeScript Files (*.ts *.tsx);;JavaScript Files (*.js *.jsx);;All Files (*)'
        )
        if file_path:
            file_path = self._sanitize_path_text(file_path)
            self.entry_point = file_path
            self.entry_point_input.setText(file_path)
            self.entry_point_changed.emit(file_path)

    def on_open_entry(self):
        path = self.entry_point_input.text()
        if path and os.path.exists(path):
            os.startfile(os.path.dirname(path))

    def on_composition_id_edited(self):
        self.composition_id = self.composition_id_input.text()
        self.composition_id_changed.emit(self.composition_id)

    def on_paste_composition_id(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        sanitized = self._sanitize_path_text(text)
        if sanitized:
            self.composition_id_input.setText(sanitized)
            self.composition_id = sanitized
            self.composition_id_changed.emit(sanitized)

    def set_output_path(self, path):
        self.output_path = path
        self.output_path_input.setText(path)

    def get_output_path(self):
        return self.output_path

    def set_entry_point(self, path):
        self.entry_point = path
        self.entry_point_input.setText(path)

    def get_entry_point(self):
        return self.entry_point

    def set_composition_id(self, comp_id):
        self.composition_id = comp_id
        self.composition_id_input.setText(comp_id)

    def get_composition_id(self):
        return self.composition_id
