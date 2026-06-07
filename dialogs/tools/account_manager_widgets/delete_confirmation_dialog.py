import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QFont, QPixmap, QPainter, QColor
import qtawesome as qta
from config import BASE_PATH
from ui.theme_system import theme


class DeleteConfirmationDialog(QDialog):
    """Dialog for confirming destructive deletion actions."""

    def __init__(self, item_type, item_name, parent=None, bulk_items=None, bulk_item_names=None):
        """
        Args:
            item_type: "Workspace", "Group", or "Profile"
            item_name: The exact name that must be typed, or a summary label for bulk delete
            parent: Parent widget
            bulk_items: Optional list of profile dicts for bulk deletion confirmation
            bulk_item_names: Backward-compatible list of item names for bulk deletion confirmation
        """
        super().__init__(parent)
        self.item_type = item_type
        self.item_name = item_name
        self.bulk_items = bulk_items or []
        if not self.bulk_items and bulk_item_names:
            self.bulk_items = [
                {
                    'profile_name': name,
                    'profile_icon': 'user',
                    'profile_color': '#3b82f6',
                }
                for name in bulk_item_names
            ]
        self.is_bulk_mode = len(self.bulk_items) > 1

        self.setWindowTitle(f'Delete {item_type}')
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setMinimumHeight(300 if self.is_bulk_mode else 0)

        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        warning_icon = QLabel()
        warning_icon.setPixmap(qta.icon('fa6s.triangle-exclamation', color='#ef4444').pixmap(32, 32))
        header_layout.addWidget(warning_icon)

        title_label = QLabel(self._get_title_text())
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        header_layout.addStretch()
        layout.addLayout(header_layout)

        warning_text = QLabel(self._get_warning_text())
        warning_text.setWordWrap(True)
        warning_text.setTextFormat(Qt.RichText)
        layout.addWidget(warning_text)

        if self.item_type in ['Workspace', 'Group']:
            cascade_text = QLabel('All nested items will also be deleted.')
            cascade_text.setStyleSheet('color: #ef4444; font-weight: bold;')
            layout.addWidget(cascade_text)

        if self.is_bulk_mode:
            summary_label = QLabel(f'Selected profiles ({len(self.bulk_items)}):')
            summary_label.setStyleSheet('font-weight: bold;')
            layout.addWidget(summary_label)

            self.bulk_list_widget = QListWidget()
            self.bulk_list_widget.setSpacing(4)
            self.bulk_list_widget.setMinimumHeight(180)
            self._populate_bulk_list()
            layout.addWidget(self.bulk_list_widget)

            self.confirm_checkbox = QCheckBox(
                'I understand that deleting these profiles is permanent and cannot be undone.'
            )
            self.confirm_checkbox.setStyleSheet('color: #ef4444; font-weight: bold;')
            self.confirm_checkbox.checkStateChanged.connect(self._on_checkbox_changed)
            layout.addWidget(self.confirm_checkbox)
        else:
            confirm_label = QLabel(f'Type <b>{self.item_name}</b> to confirm:')
            confirm_label.setTextFormat(Qt.RichText)
            layout.addWidget(confirm_label)

            self.name_input = QLineEdit()
            self.name_input.setPlaceholderText(f'Type "{self.item_name}" here')
            self.name_input.textChanged.connect(self._on_text_changed)
            layout.addWidget(self.name_input)

        layout.addStretch()

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton(' Cancel')
        cancel_btn.setIcon(qta.icon('fa6s.xmark'))
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.delete_btn = QPushButton(' Delete')
        self.delete_btn.setIcon(qta.icon('fa6s.trash'))
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self.accept)
        self.delete_btn.setDefault(True)
        button_layout.addWidget(self.delete_btn)

        layout.addLayout(button_layout)

    def _populate_bulk_list(self):
        self.bulk_list_widget.clear()

        for profile in self.bulk_items:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, profile)
            item.setIcon(QIcon(self._create_profile_icon(
                profile.get('profile_icon', 'user'),
                profile.get('profile_color', '#3b82f6')
            )))
            item.setText(profile.get('profile_name', 'Unnamed'))
            item.setTextAlignment(Qt.AlignVCenter)
            self.bulk_list_widget.addItem(item)

    def _create_profile_icon(self, icon_value, color):
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        r = int(color.lstrip('#')[0:2], 16)
        g = int(color.lstrip('#')[2:4], 16)
        b = int(color.lstrip('#')[4:6], 16)

        if icon_value.startswith('initial:'):
            initial = icon_value[8:].upper() or '?'
            painter.setBrush(QColor(r, g, b, 40))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(0, 0, 24, 24)
            painter.setPen(QColor(r, g, b))
            font = QFont()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignCenter, initial)
        elif icon_value.startswith('image:'):
            image_path = icon_value[6:]
            if os.path.exists(image_path):
                from PySide6.QtGui import QPainterPath
                path = QPainterPath()
                path.addEllipse(0, 0, 24, 24)
                painter.setClipPath(path)
                img = QPixmap(image_path).scaled(24, 24, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                painter.drawPixmap(0, 0, img)
            else:
                painter.drawPixmap(0, 0, qta.icon('fa6s.user', color=color).pixmap(24, 24))
        else:
            try:
                icon = qta.icon(icon_value if '.' in icon_value else f'fa6s.{icon_value}', color=color)
                painter.drawPixmap(0, 0, icon.pixmap(24, 24))
            except Exception:
                painter.drawPixmap(0, 0, qta.icon('fa6s.user', color=color).pixmap(24, 24))

        painter.end()
        return pixmap

    def _get_title_text(self):
        if self.is_bulk_mode:
            return f'Delete {len(self.bulk_items)} {self.item_type}s?'
        return f'Delete {self.item_type}?'

    def _get_warning_text(self):
        if self.is_bulk_mode:
            return f'This will permanently delete <b>{len(self.bulk_items)} {self.item_type.lower()}s</b>.'
        return f'This will permanently delete <b>{self.item_name}</b>.'

    def _on_text_changed(self, text):
        self.delete_btn.setEnabled(text == self.item_name)

    def _on_checkbox_changed(self, state):
        checked_value = state.value if hasattr(state, 'value') else int(state)
        expected_value = Qt.Checked.value if hasattr(Qt.Checked, 'value') else int(Qt.Checked)
        self.delete_btn.setEnabled(checked_value == expected_value)
