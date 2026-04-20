from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QSizePolicy)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog
import qtawesome as qta
from dialogs.tools.icon_picker_dialog import IconPickerDialog
from ui.theme_system import theme


class NewCollectionDialog(QDialog):
    def __init__(self, parent=None, parent_collection_id=None, parent_collection_name=None):
        super().__init__(parent)
        self.collection_name = None
        self.collection_description = None
        self.selected_icon = 'folder'
        self.selected_color = theme.get_color('primary')
        self._parent_collection_id = parent_collection_id
        self._parent_collection_name = parent_collection_name
        self._setup_ui()

    def _setup_ui(self):
        title = 'New Subfolder' if self._parent_collection_name else 'New Collection'
        self.setWindowTitle(title)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)

        if self._parent_collection_name:
            parent_label = QLabel(f'Creating subfolder in "{self._parent_collection_name}"')
            layout.addWidget(parent_label)

        name_layout = QHBoxLayout()
        name_label = QLabel('Name:')
        name_label.setMinimumWidth(80)
        name_layout.addWidget(name_label)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('Collection name')
        self.name_edit.returnPressed.connect(self.accept)
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        desc_layout = QHBoxLayout()
        desc_label = QLabel('Description:')
        desc_label.setMinimumWidth(80)
        desc_layout.addWidget(desc_label)
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText('Optional description')
        self.desc_edit.returnPressed.connect(self.accept)
        desc_layout.addWidget(self.desc_edit)
        layout.addLayout(desc_layout)

        icon_row = QHBoxLayout()
        icon_row.setSpacing(6)
        icon_label_icon = QLabel()
        icon_label_icon.setPixmap(qta.icon('fa6s.icons', color=theme.get_color('gray')).pixmap(16, 16))
        icon_row.addWidget(icon_label_icon)
        icon_label_text = QLabel('Icon:')
        icon_label_text.setMinimumWidth(70)
        icon_row.addWidget(icon_label_text)
        self.icon_preview = QLabel()
        self.icon_preview.setFixedSize(28, 28)
        self.icon_preview.setAlignment(Qt.AlignCenter)
        self.icon_preview.setCursor(Qt.PointingHandCursor)
        self.icon_preview.mousePressEvent = lambda e: self._show_icon_picker()
        icon_row.addWidget(self.icon_preview)
        self.icon_input = QLineEdit()
        self.icon_input.setText(self.selected_icon)
        self.icon_input.setPlaceholderText('e.g., folder, folder-open')
        self.icon_input.textChanged.connect(self._on_icon_text_changed)
        icon_row.addWidget(self.icon_input, 1)
        self.icon_picker_btn = QPushButton(qta.icon('fa6s.magnifying-glass'), '')
        self.icon_picker_btn.setMaximumWidth(32)
        self.icon_picker_btn.clicked.connect(self._show_icon_picker)
        icon_row.addWidget(self.icon_picker_btn)
        layout.addLayout(icon_row)

        self._update_icon_preview()

        color_row = QHBoxLayout()
        color_row.setSpacing(6)
        color_label_icon = QLabel()
        color_label_icon.setPixmap(qta.icon('fa6s.palette', color=theme.get_color('gray')).pixmap(16, 16))
        color_row.addWidget(color_label_icon)
        color_label_text = QLabel('Color:')
        color_label_text.setMinimumWidth(70)
        color_row.addWidget(color_label_text)
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(28, 28)
        self.color_preview.setCursor(Qt.PointingHandCursor)
        self.color_preview.mousePressEvent = lambda e: self._pick_color()
        color_row.addWidget(self.color_preview)
        self.color_input = QLineEdit()
        self.color_input.setText(self.selected_color)
        self.color_input.setPlaceholderText('#888888')
        self.color_input.textChanged.connect(self._on_color_text_changed)
        color_row.addWidget(self.color_input, 1)
        self.color_picker_btn = QPushButton(qta.icon('fa6s.eye-dropper'), '')
        self.color_picker_btn.setMaximumWidth(32)
        self.color_picker_btn.clicked.connect(self._pick_color)
        color_row.addWidget(self.color_picker_btn)
        layout.addLayout(color_row)

        self._update_color_preview()

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton('Cancel')
        cancel_btn.setIcon(qta.icon('fa6s.xmark'))
        cancel_btn.clicked.connect(self.reject)
        self.ok_btn = QPushButton('Create')
        self.ok_btn.setIcon(qta.icon('fa6s.floppy-disk'))
        self.ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.ok_btn)
        layout.addLayout(btn_layout)

    def _update_icon_preview(self):
        icon_name = self.icon_input.text().strip()
        if icon_name:
            full_name = f'fa6s.{icon_name}' if '.' not in icon_name else icon_name
            try:
                icon = qta.icon(full_name, color=theme.get_color('warning'))
                self.icon_preview.setPixmap(icon.pixmap(24, 24))
            except Exception:
                self.icon_preview.clear()
        else:
            self.icon_preview.clear()

    def _on_icon_text_changed(self, text):
        self.selected_icon = text.strip()
        self._update_icon_preview()

    def _show_icon_picker(self):
        current_icon = self.icon_input.text().strip()
        dialog = IconPickerDialog(current_icon, self)
        dialog.icon_selected.connect(self._on_icon_picked)
        dialog.exec()

    def _on_icon_picked(self, icon_name):
        self.icon_input.setText(icon_name)
        self.selected_icon = icon_name
        self._update_icon_preview()

    def _update_color_preview(self):
        self.color_preview.setStyleSheet(f'background-color: {self.selected_color}; border-radius: 4px;')

    def _on_color_text_changed(self, text):
        txt = text.strip()
        if txt.startswith('#'):
            hexpart = txt[1:]
        else:
            hexpart = txt
        if len(hexpart) == 3 and all(c in '0123456789abcdefABCDEF' for c in hexpart):
            hexpart = ''.join([c*2 for c in hexpart])
        if len(hexpart) == 6 and all(c in '0123456789abcdefABCDEF' for c in hexpart):
            self.selected_color = '#' + hexpart.lower()
            self._update_color_preview()

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self.selected_color), self, 'Pick Color')
        if color.isValid():
            self.selected_color = color.name()
            self.color_input.setText(self.selected_color)
            self._update_color_preview()

    def accept(self):
        name = self.name_edit.text().strip()
        if not name:
            self.name_edit.setFocus()
            return
        self.collection_name = name
        self.collection_description = self.desc_edit.text().strip() or None
        super().accept()
