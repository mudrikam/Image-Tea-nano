import os
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QGroupBox, QComboBox, QCheckBox, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import QApplication
import qtawesome as qta

WINDOWS_RESERVED_NAMES = {'CON', 'PRN', 'AUX', 'NUL',
                          'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
                          'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}

def sanitize_filename(name):
    if not isinstance(name, str):
        name = str(name)
    name = name.strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f-\x9f]', '_', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip('._ ')
    if not name:
        name = 'output'
    base, _, ext = name.rpartition('.')
    check = base.upper() if base else name.upper()
    if check in WINDOWS_RESERVED_NAMES:
        name = f'_{name}'
    if len(name) > 200:
        name = name[:200]
    return name


class OutputTabWidget(QWidget):
    output_path_changed = Signal(str)
    output_filename_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.output_path = ''
        self.output_filename = ''
        self._setup_ui()
        self._load_saved_output()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        filename_group = QGroupBox('Output Filename')
        filename_layout = QHBoxLayout()
        filename_layout.setSpacing(8)

        filename_icon = QLabel()
        filename_icon.setPixmap(qta.icon('fa6s.file', color='#888').pixmap(16, 16))
        filename_layout.addWidget(filename_icon)

        filename_label = QLabel('Filename:')
        filename_label.setStyleSheet('font-weight: bold;')
        filename_label.setMinimumWidth(60)
        filename_layout.addWidget(filename_label)

        self.output_filename_input = QLineEdit()
        self.output_filename_input.setPlaceholderText('e.g., my_video')
        self.output_filename_input.editingFinished.connect(self.on_filename_edited)
        filename_layout.addWidget(self.output_filename_input, 1)

        filename_group.setLayout(filename_layout)
        layout.addWidget(filename_group)

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

    def validate(self):
        if not self.output_filename_input.text().strip():
            QMessageBox.warning(self, 'Validation Error', 'Output filename cannot be empty.')
            self.output_filename_input.setFocus()
            return False
        if not self.output_path_input.text().strip():
            QMessageBox.warning(self, 'Validation Error', 'Output folder cannot be empty.')
            self.output_path_input.setFocus()
            return False
        return True

    def get_full_output_path(self):
        filename = sanitize_filename(self.output_filename_input.text().strip())
        folder = self._sanitize_path_text(self.output_path_input.text().strip())
        fmt = self.output_format_combo.currentText()
        if not filename or not folder:
            return ''
        return os.path.join(folder, f'{filename}.{fmt}')

    def on_filename_edited(self):
        raw = self.output_filename_input.text().strip()
        sanitized = sanitize_filename(raw)
        if sanitized != raw:
            self.output_filename_input.setText(sanitized)
        self.output_filename = sanitized
        self.output_filename_changed.emit(sanitized)

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
        import os
        start_dir = self.output_path if self.output_path else os.path.expanduser('~')
        folder = QFileDialog.getExistingDirectory(self, 'Select Output Folder', start_dir)
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

    def set_output_path(self, path):
        self.output_path = path
        self.output_path_input.setText(path)
        self._save_output_settings()

    def get_output_path(self):
        return self.output_path

    def set_output_filename(self, name):
        sanitized = sanitize_filename(name)
        self.output_filename = sanitized
        self.output_filename_input.setText(sanitized)
        self._save_output_settings()

    def get_output_filename(self):
        return self.output_filename

    def _get_temp_config_path(self):
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'temp', 'vibe_video_output_settings.json')

    def _load_saved_output(self):
        import json
        config_path = self._get_temp_config_path()
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            if saved.get('output_path'):
                self.output_path = saved['output_path']
                self.output_path_input.setText(self.output_path)
            if saved.get('output_filename'):
                self.output_filename = saved['output_filename']
                self.output_filename_input.setText(self.output_filename)
        except Exception as e:
            print(f'[Vibe Video] Failed to load output settings: {e}')

    def _save_output_settings(self):
        import json
        config_path = self._get_temp_config_path()
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'output_path': self.output_path,
                    'output_filename': self.output_filename,
                }, f, indent=4)
        except Exception as e:
            print(f'[Vibe Video] Failed to save output settings: {e}')
