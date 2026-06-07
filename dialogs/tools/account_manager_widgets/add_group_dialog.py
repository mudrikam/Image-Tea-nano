import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QTextEdit, QMessageBox, QSizePolicy, QColorDialog, QFileDialog, QComboBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QFont, QPixmap, QPainter, QColor
import qtawesome as qta
from config import BASE_PATH
from ui.theme_system import theme


class AddGroupDialog(QDialog):
    """Dialog for creating/editing group"""
    group_saved = Signal(dict)
    
    def __init__(self, group_data=None, parent=None):
        super().__init__(parent)
        self.group_data = group_data
        self.is_edit_mode = group_data is not None
        self.selected_icon = group_data.get('group_icon', 'users') if group_data else 'users'
        self.selected_color = group_data.get('group_color', '#3b82f6') if group_data else '#3b82f6'
        self.icon_mode = 'initial' if not group_data else 'icon'  # Default to Initial for new, Icon for edit
        
        self.setWindowTitle('Edit Group' if self.is_edit_mode else 'New Group')
        self.setModal(True)
        self.setMinimumWidth(450)
        
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self._setup_ui()
        if self.is_edit_mode:
            self._load_data()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        dialog_icon = qta.icon('fa6s.users', color=theme.get_color('primary'))
        icon_label = QLabel()
        icon_label.setPixmap(dialog_icon.pixmap(24, 24))
        header_layout.addWidget(icon_label)
        
        title_label = QLabel('Edit Group' if self.is_edit_mode else 'New Group')
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Name field
        name_layout = QHBoxLayout()
        name_layout.setSpacing(6)
        name_icon = QLabel()
        name_icon.setPixmap(qta.icon('fa6s.signature', color=theme.get_color('gray')).pixmap(16, 16))
        name_layout.addWidget(name_icon)
        name_label = QLabel('Name:')
        name_label.setMinimumWidth(70)
        name_layout.addWidget(name_label)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText('e.g., Admin Accounts, Developer Team')
        self.name_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.name_input.textChanged.connect(self._on_name_changed)
        name_layout.addWidget(self.name_input, 1)
        layout.addLayout(name_layout)
        
        # Description field
        desc_layout = QHBoxLayout()
        desc_layout.setSpacing(6)
        desc_icon = QLabel()
        desc_icon.setPixmap(qta.icon('fa6s.align-left', color=theme.get_color('gray')).pixmap(16, 16))
        desc_layout.addWidget(desc_icon)
        desc_label = QLabel('Description:')
        desc_label.setMinimumWidth(70)
        desc_layout.addWidget(desc_label)
        
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText('Optional description...')
        self.desc_input.setMaximumHeight(60)
        desc_layout.addWidget(self.desc_input, 1)
        layout.addLayout(desc_layout)
        
        # Icon mode selector
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(6)
        mode_icon = QLabel()
        mode_icon.setPixmap(qta.icon('fa6s.circle-half-stroke', color=theme.get_color('gray')).pixmap(16, 16))
        mode_layout.addWidget(mode_icon)
        mode_label = QLabel('Picture Mode:')
        mode_label.setMinimumWidth(70)
        mode_layout.addWidget(mode_label)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(['Icon', 'Image', 'Initial'])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo, 1)
        layout.addLayout(mode_layout)
        
        # Icon picker
        icon_layout = QHBoxLayout()
        icon_layout.setSpacing(6)
        icon_icon = QLabel()
        icon_icon.setPixmap(qta.icon('fa6s.icons', color=theme.get_color('gray')).pixmap(16, 16))
        icon_layout.addWidget(icon_icon)
        icon_label_text = QLabel('Icon:')
        icon_label_text.setMinimumWidth(70)
        icon_layout.addWidget(icon_label_text)

        self.icon_preview = QLabel()
        self.icon_preview.setFixedSize(28, 28)
        self.icon_preview.setAlignment(Qt.AlignCenter)
        self.icon_preview.setCursor(Qt.PointingHandCursor)
        self.icon_preview.setToolTip('Click to choose icon')
        self.icon_preview.mousePressEvent = lambda e: self._choose_icon() if self.icon_mode == 'icon' else None
        icon_layout.addWidget(self.icon_preview)
        
        self.icon_btn = QPushButton(qta.icon('fa6s.magnifying-glass'), '')
        self.icon_btn.setMaximumWidth(32)
        self.icon_btn.setToolTip('Choose Icon')
        self.icon_btn.clicked.connect(self._choose_icon)
        icon_layout.addWidget(self.icon_btn)
        
        # Image mode controls
        self.image_btn = QPushButton(qta.icon('fa6s.folder-open'), '')
        self.image_btn.setMaximumWidth(32)
        self.image_btn.setToolTip('Choose Image')
        self.image_btn.clicked.connect(self._choose_image)
        self.image_btn.hide()
        icon_layout.addWidget(self.image_btn)
        
        icon_layout.addStretch()
        layout.addLayout(icon_layout)
        
        # Color picker
        color_layout = QHBoxLayout()
        color_layout.setSpacing(6)
        color_icon = QLabel()
        color_icon.setPixmap(qta.icon('fa6s.palette', color=theme.get_color('gray')).pixmap(16, 16))
        color_layout.addWidget(color_icon)
        color_label = QLabel('Color:')
        color_label.setMinimumWidth(70)
        color_layout.addWidget(color_label)
        
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(28, 28)
        self.color_preview.setCursor(Qt.PointingHandCursor)
        self.color_preview.setToolTip('Click to choose color')
        self.color_preview.mousePressEvent = lambda e: self._choose_color()
        self._update_color_preview()
        color_layout.addWidget(self.color_preview)
        
        self.color_input = QLineEdit()
        self.color_input.setText(self.selected_color)
        self.color_input.setPlaceholderText('#3b82f6')
        self.color_input.textChanged.connect(self._on_color_changed)
        self.color_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        color_layout.addWidget(self.color_input, 1)
        
        color_layout.addStretch()
        layout.addLayout(color_layout)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton(qta.icon('fa6s.xmark'), ' Cancel')
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton(qta.icon('fa6s.floppy-disk'), ' Save')
        save_btn.clicked.connect(self._on_save)
        save_btn.setDefault(True)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        
        # Initialize preview based on mode
        self._update_icon_preview()
        # Set default mode after controls are created
        if not self.is_edit_mode:
            self.mode_combo.setCurrentText('Initial')
        else:
            self._on_mode_changed(self.mode_combo.currentText())
     
    def _update_icon_preview(self):
        if self.icon_mode == 'icon':
            try:
                icon = qta.icon(self.selected_icon, color=self.selected_color)
                # Draw icon on circle background
                pixmap = QPixmap(28, 28)
                pixmap.fill(Qt.transparent)
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.Antialiasing)

                # Draw thin circle background with icon color
                r, g, b = int(self.selected_color[1:3], 16), int(self.selected_color[3:5], 16), int(self.selected_color[5:7], 16)
                pen_color = QColor(r, g, b, 100)  # More transparent for thin border
                painter.setPen(pen_color)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(1, 1, 26, 26)

                painter.end()

                # Composite icon on top
                result = QPixmap(28, 28)
                result.fill(Qt.transparent)
                painter2 = QPainter(result)
                painter2.drawPixmap(0, 0, pixmap)
                icon_pixmap = icon.pixmap(20, 20)
                painter2.drawPixmap(4, 4, icon_pixmap)
                painter2.end()

                self.icon_preview.setPixmap(result)
            except:
                self.icon_preview.setText('?')

        elif self.icon_mode == 'image':
            # Image mode - show the stored image path or default
            icon_text = self.selected_icon if self.selected_icon.startswith('image:') else ''
            if icon_text:
                image_path = icon_text[6:]  # Remove 'image:' prefix
                if os.path.exists(image_path):
                    # Create circular pixmap with image, no border
                    pixmap = QPixmap(28, 28)
                    pixmap.fill(Qt.transparent)
                    painter = QPainter(pixmap)
                    painter.setRenderHint(QPainter.Antialiasing)
                    
                    from PySide6.QtGui import QPainterPath
                    path = QPainterPath()
                    path.addEllipse(0, 0, 28, 28)
                    painter.setClipPath(path)
                    
                    img = QPixmap(image_path).scaled(28, 28, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    painter.drawPixmap(0, 0, img)
                    painter.end()
                    
                    self.icon_preview.setPixmap(pixmap)
                else:
                    self.icon_preview.setText('?')
            else:
                self.icon_preview.setText('?')

        elif self.icon_mode == 'initial':
            self._update_initial_preview()

    def _on_mode_changed(self, mode_text):
        """Handle mode change - show/hide appropriate controls"""
        mode = mode_text.lower()
        self.icon_mode = mode

        if mode == 'icon':
            self.icon_btn.show()
            self.image_btn.hide()
            self.icon_preview.mousePressEvent = lambda e: self._choose_icon()
            self.icon_preview.setToolTip('Click to choose icon')
        elif mode == 'image':
            self.icon_btn.hide()
            self.image_btn.show()
            self.icon_preview.mousePressEvent = lambda e: self._choose_image()
            self.icon_preview.setToolTip('Click to choose image')
        elif mode == 'initial':
            self.icon_btn.hide()
            self.image_btn.hide()
            self.icon_preview.mousePressEvent = lambda e: None
            self.icon_preview.setToolTip('')
            self._update_initial_preview()

        self._update_icon_preview()

    def _update_initial_preview(self):
        """Update the icon preview to show initial letter (auto-generated from group name)"""
        name = self.name_input.text().strip()
        initial = name[0].upper() if name else '?'
        color = self.selected_color

        # Create circular pixmap with initial
        pixmap = QPixmap(28, 28)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw circle background
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        circle_color = QColor(r, g, b, 40)  # Light tint for initial mode bg
        painter.setBrush(circle_color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, 28, 28)

        # Draw initial text
        painter.setPen(QColor(r, g, b))
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, initial)
        painter.end()

        self.icon_preview.setPixmap(pixmap)

    def _choose_icon(self):
        from dialogs.tools.icon_picker_dialog import IconPickerDialog
        dialog = IconPickerDialog(current_icon=self.selected_icon, parent=self)
        dialog.icon_selected.connect(self._on_icon_selected)
        dialog.exec()

    def _on_icon_selected(self, icon_name):
        self.selected_icon = icon_name
        self._update_icon_preview()

    def _choose_image(self):
        """Open file dialog to choose image"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            'Select Group Picture',
            '',
            'Image Files (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*.*)'
        )
        if path:
            self.selected_icon = f'image:{path}'
            self._update_icon_preview()

    def _on_color_changed(self, text):
        if text.startswith('#') and len(text) == 7:
            self.selected_color = text
            self._update_color_preview()
            self._update_icon_preview()

    def _on_name_changed(self, text):
        """Auto-update initial preview in initial mode when name changes"""
        if self.icon_mode == 'initial':
            self._update_initial_preview()

    def _update_color_preview(self):
        self.color_preview.setStyleSheet(f'background-color: {self.selected_color}; border: 1px solid #444; border-radius: 3px;')

    def _choose_color(self):
        """Open color dialog to choose color"""
        from PySide6.QtGui import QColor
        color = QColorDialog.getColor(QColor(self.selected_color), self, 'Choose Color')
        if color.isValid():
            self.selected_color = color.name()
            self.color_input.setText(self.selected_color)
            self._update_color_preview()
            self._update_icon_preview()

    def _load_data(self):
        if not self.group_data:
            return
        
        self.name_input.setText(self.group_data.get('group_name', ''))
        self.desc_input.setPlainText(self.group_data.get('group_description', ''))

        # Detect icon mode from group_icon
        group_icon = self.group_data.get('group_icon', 'users')
        if group_icon.startswith('image:'):
            self.icon_mode = 'image'
            self.mode_combo.setCurrentText('Image')
            self.selected_icon = group_icon
        elif group_icon.startswith('initial:'):
            self.icon_mode = 'initial'
            self.mode_combo.setCurrentText('Initial')
            self.selected_icon = group_icon
        else:
            self.icon_mode = 'icon'
            self.mode_combo.setCurrentText('Icon')
            self.selected_icon = group_icon

        self.color_input.setText(self.selected_color)

        # Update preview
        self._on_mode_changed(self.mode_combo.currentText())

    def _on_save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, 'Validation Error', 'Group name is required')
            return
        
        # Build icon value based on mode - Initial mode auto-generates from group name
        if self.icon_mode == 'initial':
            initial = name[0].upper() if name else 'U'
            icon_value = f'initial:{initial}'
        else:
            icon_value = self.selected_icon
        
        data = {
            'group_name': name,
            'group_description': self.desc_input.toPlainText().strip(),
            'group_icon': icon_value,
            'group_color': self.selected_color,
        }
        
        if self.is_edit_mode:
            data['group_id'] = self.group_data['group_id']
        
        self.group_saved.emit(data)
        self.accept()
