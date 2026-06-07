import os
import json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QFileDialog, QMessageBox, QSizePolicy, QColorDialog, QComboBox,
    QTabWidget, QWidget, QScrollArea, QListWidget, QInputDialog, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QFont, QPixmap, QPainter, QColor
import qtawesome as qta
from config import BASE_PATH
from ui.theme_system import theme


class AddProfileDialog(QDialog):
    """Dialog for creating/editing profile"""
    profile_saved = Signal(dict)

    def __init__(self, profile_data=None, workspace_data=None, parent=None):
        super().__init__(parent)
        self.profile_data = profile_data
        self.workspace_data = workspace_data
        self.is_edit_mode = profile_data is not None
        self.selected_icon = profile_data.get('profile_icon', 'initial') if profile_data else 'initial'
        self.selected_color = profile_data.get('profile_color', '#3b82f6') if profile_data else '#3b82f6'
        self.icon_mode = 'initial' if not profile_data else 'icon'  # Default to Initial for new, Icon for edit
        self.additional_parameters = []

        self.setWindowTitle('Edit Profile' if self.is_edit_mode else 'New Profile')
        self.setModal(True)
        self.setMinimumWidth(450)
        self.setMinimumHeight(340)

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

        dialog_icon = qta.icon('fa6s.user', color=theme.get_color('primary'))
        icon_label = QLabel()
        icon_label.setPixmap(dialog_icon.pixmap(24, 24))
        header_layout.addWidget(icon_label)

        title_label = QLabel('Edit Profile' if self.is_edit_mode else 'New Profile')
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        header_layout.addStretch()
        layout.addLayout(header_layout)

        self.tabs = QTabWidget()
        self.main_tab = QWidget()
        self.parameters_tab = QWidget()
        self.tabs.addTab(self.main_tab, qta.icon('fa6s.user-gear'), 'Main Data')
        self.tabs.addTab(self.parameters_tab, qta.icon('fa6s.sliders'), 'Parameters')
        layout.addWidget(self.tabs, 1)

        main_tab_layout = QVBoxLayout(self.main_tab)
        main_tab_layout.setContentsMargins(0, 0, 0, 0)
        main_tab_layout.setSpacing(8)

        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)
        main_scroll.setFrameShape(QScrollArea.NoFrame)
        main_content = QWidget()
        main_layout = QVBoxLayout(main_content)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        main_scroll.setWidget(main_content)
        main_tab_layout.addWidget(main_scroll)

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
        self.name_input.setPlaceholderText('e.g., John Doe, Admin Profile')
        self.name_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        name_layout.addWidget(self.name_input, 1)
        main_layout.addLayout(name_layout)

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
        main_layout.addLayout(desc_layout)

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
        main_layout.addLayout(mode_layout)

        # Icon preview container - will be updated based on mode
        icon_container_layout = QHBoxLayout()
        icon_container_layout.setSpacing(6)
        icon_icon_lbl = QLabel()
        icon_icon_lbl.setPixmap(qta.icon('fa6s.icons', color=theme.get_color('gray')).pixmap(16, 16))
        icon_container_layout.addWidget(icon_icon_lbl)
        icon_label_text = QLabel('Icon:')
        icon_label_text.setMinimumWidth(70)
        icon_container_layout.addWidget(icon_label_text)

        self.icon_preview = QLabel()
        self.icon_preview.setFixedSize(28, 28)
        self.icon_preview.setAlignment(Qt.AlignCenter)
        self.icon_preview.setCursor(Qt.PointingHandCursor)
        self.icon_preview.setToolTip('Click to choose icon')
        self.icon_preview.mousePressEvent = lambda e: self._choose_icon() if self.icon_mode == 'icon' else None
        icon_container_layout.addWidget(self.icon_preview)

        # Icon mode controls
        self.icon_btn = QPushButton(qta.icon('fa6s.magnifying-glass'), '')
        self.icon_btn.setMaximumWidth(32)
        self.icon_btn.setToolTip('Choose Icon')
        self.icon_btn.clicked.connect(self._choose_icon)
        icon_container_layout.addWidget(self.icon_btn)

        # Image mode controls
        self.image_btn = QPushButton(qta.icon('fa6s.folder-open'), '')
        self.image_btn.setMaximumWidth(32)
        self.image_btn.setToolTip('Choose Image')
        self.image_btn.clicked.connect(self._choose_image)
        self.image_btn.hide()
        icon_container_layout.addWidget(self.image_btn)

        # Initial mode - auto-filled from profile name (no manual input)
        # Initial preview will be updated automatically based on profile name

        icon_container_layout.addStretch()
        main_layout.addLayout(icon_container_layout)

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
        main_layout.addLayout(color_layout)

        # Browser profile name - auto-generated from name
        profile_name_layout = QHBoxLayout()
        profile_name_layout.setSpacing(6)
        profile_icon_lbl = QLabel()
        profile_icon_lbl.setPixmap(qta.icon('fa6s.tag', color=theme.get_color('gray')).pixmap(16, 16))
        profile_name_layout.addWidget(profile_icon_lbl)
        profile_label = QLabel('Profile Folder:')
        profile_label.setMinimumWidth(70)
        profile_name_layout.addWidget(profile_label)

        self.profile_name_input = QLineEdit()
        self.profile_name_input.setPlaceholderText('Auto-generated from profile name')
        self.profile_name_input.setEnabled(False)
        self.profile_name_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.profile_name_input.setStyleSheet('QLineEdit:disabled { background-color: rgba(255,255,255,0.05); color: #888; }')
        profile_name_layout.addWidget(self.profile_name_input, 1)
        main_layout.addLayout(profile_name_layout)

        # Auto-update browser profile name from profile name
        self.name_input.textChanged.connect(self._update_browser_profile_name)

        # Browser profile path - auto-generated
        path_layout = QHBoxLayout()
        path_layout.setSpacing(6)
        path_icon = QLabel()
        path_icon.setPixmap(qta.icon('fa6s.folder', color=theme.get_color('gray')).pixmap(16, 16))
        path_layout.addWidget(path_icon)
        path_label = QLabel('Profile Path:')
        path_label.setMinimumWidth(70)
        path_layout.addWidget(path_label)

        self.profile_path_input = QLineEdit()
        self.profile_path_input.setPlaceholderText('Auto-generated from workspace root + name')
        self.profile_path_input.setEnabled(False)
        self.profile_path_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.profile_path_input.setStyleSheet('QLineEdit:disabled { background-color: rgba(255,255,255,0.05); color: #888; }')
        path_layout.addWidget(self.profile_path_input, 1)

        main_layout.addLayout(path_layout)

        # Launch window mode setting - persisted per profile
        window_mode_layout = QHBoxLayout()
        window_mode_layout.setSpacing(6)
        window_mode_icon = QLabel()
        window_mode_icon.setPixmap(qta.icon('fa6s.window-maximize', color=theme.get_color('gray')).pixmap(16, 16))
        window_mode_layout.addWidget(window_mode_icon)
        window_mode_label = QLabel('Start Window:')
        window_mode_label.setMinimumWidth(70)
        window_mode_layout.addWidget(window_mode_label)

        self.window_mode_combo = QComboBox()
        self.window_mode_combo.addItem('Windowed', 'windowed')
        self.window_mode_combo.addItem('Maximized', 'maximized')
        self.window_mode_combo.addItem('Fullscreen', 'fullscreen')
        self.window_mode_combo.setToolTip('Choose how this profile window should open when launched')
        window_mode_layout.addWidget(self.window_mode_combo, 1)
        main_layout.addLayout(window_mode_layout)

        main_layout.addStretch()
        self._setup_parameters_tab()

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

    def _setup_parameters_tab(self):
        parameters_layout = QVBoxLayout(self.parameters_tab)
        parameters_layout.setContentsMargins(8, 8, 8, 8)
        parameters_layout.setSpacing(8)

        input_layout = QHBoxLayout()
        input_layout.setSpacing(6)
        param_icon = QLabel()
        param_icon.setPixmap(qta.icon('fa6s.terminal', color=theme.get_color('gray')).pixmap(16, 16))
        input_layout.addWidget(param_icon)

        self.parameter_input = QLineEdit()
        self.parameter_input.setPlaceholderText('e.g., --disable-web-security')
        self.parameter_input.returnPressed.connect(self._add_parameter)
        input_layout.addWidget(self.parameter_input, 1)

        self.add_parameter_btn = QPushButton(qta.icon('fa6s.plus'), ' Add')
        self.add_parameter_btn.clicked.connect(self._add_parameter)
        input_layout.addWidget(self.add_parameter_btn)
        parameters_layout.addLayout(input_layout)

        self.parameters_list = QListWidget()
        self.parameters_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.parameters_list.itemDoubleClicked.connect(lambda item: self._edit_parameter())
        self.parameters_list.setAlternatingRowColors(True)
        parameters_layout.addWidget(self.parameters_list, 1)

        action_layout = QHBoxLayout()
        action_layout.addStretch()

        self.edit_parameter_btn = QPushButton(qta.icon('fa6s.pen'), ' Edit')
        self.edit_parameter_btn.clicked.connect(self._edit_parameter)
        action_layout.addWidget(self.edit_parameter_btn)

        self.remove_parameter_btn = QPushButton(qta.icon('fa6s.trash'), ' Remove')
        self.remove_parameter_btn.clicked.connect(self._remove_parameter)
        action_layout.addWidget(self.remove_parameter_btn)

        self.clear_parameters_btn = QPushButton(qta.icon('fa6s.broom'), ' Clear')
        self.clear_parameters_btn.clicked.connect(self._clear_parameters)
        action_layout.addWidget(self.clear_parameters_btn)
        parameters_layout.addLayout(action_layout)

    def _normalize_parameter(self, value):
        return (value or '').strip()

    def _add_parameter(self):
        parameter = self._normalize_parameter(self.parameter_input.text())
        if not parameter:
            return
        self.additional_parameters.append(parameter)
        self.parameter_input.clear()
        self._refresh_parameters_list()

    def _edit_parameter(self):
        current_row = self.parameters_list.currentRow()
        if current_row < 0 or current_row >= len(self.additional_parameters):
            QMessageBox.information(self, 'No Parameter Selected', 'Select a parameter to edit')
            return

        current_value = self.additional_parameters[current_row]
        new_value, accepted = QInputDialog.getText(self, 'Edit Parameter', 'Parameter:', text=current_value)
        if not accepted:
            return

        new_value = self._normalize_parameter(new_value)
        if not new_value:
            QMessageBox.warning(self, 'Validation Error', 'Parameter cannot be empty')
            return

        self.additional_parameters[current_row] = new_value
        self._refresh_parameters_list(current_row)

    def _remove_parameter(self):
        current_row = self.parameters_list.currentRow()
        if current_row < 0 or current_row >= len(self.additional_parameters):
            QMessageBox.information(self, 'No Parameter Selected', 'Select a parameter to remove')
            return

        self.additional_parameters.pop(current_row)
        next_row = min(current_row, len(self.additional_parameters) - 1)
        self._refresh_parameters_list(next_row)

    def _clear_parameters(self):
        if not self.additional_parameters:
            return
        self.additional_parameters.clear()
        self._refresh_parameters_list()

    def _refresh_parameters_list(self, selected_row=None):
        self.parameters_list.clear()
        for parameter in self.additional_parameters:
            self.parameters_list.addItem(parameter)
        if selected_row is not None and selected_row >= 0 and self.additional_parameters:
            self.parameters_list.setCurrentRow(min(selected_row, len(self.additional_parameters) - 1))

    def _parse_additional_parameters(self, value):
        if isinstance(value, list):
            return [self._normalize_parameter(item) for item in value if self._normalize_parameter(item)]
        if isinstance(value, str) and value.strip():
            try:
                decoded = json.loads(value)
                if isinstance(decoded, list):
                    return [self._normalize_parameter(item) for item in decoded if self._normalize_parameter(item)]
            except json.JSONDecodeError:
                return [line.strip() for line in value.splitlines() if line.strip()]
        return []

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
        """Update the icon preview to show initial letter (auto-generated from profile name)"""
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

    def _update_browser_profile_name(self, text):
        """Auto-generate sanitized browser profile name from profile name"""
        import re
        sanitized = re.sub(r'[^a-zA-Z0-9\s]', '', text)
        sanitized = re.sub(r'\s+', '_', sanitized).strip('_')
        self.profile_name_input.setText(sanitized)
        self._generate_browser_profile_path(sanitized)
        
        # Auto-update initial preview in initial mode when name changes
        if self.icon_mode == 'initial' and text:
            self._update_initial_preview()

    def _generate_browser_profile_path(self, profile_folder_name):
        """Generate full profile path from workspace root + profile folder name"""
        if not self.workspace_data:
            return

        root_path = self.workspace_data.get('workspace_root_profile_path', '')
        if not root_path:
            return

        # Combine root path with profile folder name
        full_path = os.path.join(root_path, profile_folder_name)
        self.profile_path_input.setText(full_path)

    def _update_icon_preview(self):
        """Update icon preview based on current mode"""
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
                    # No border for image mode - just circular image
                    painter.end()
                    
                    self.icon_preview.setPixmap(pixmap)
                else:
                    self.icon_preview.setText('?')
            else:
                self.icon_preview.setText('?')

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
            'Select Profile Picture',
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
        if not self.profile_data:
            return

        self.name_input.setText(self.profile_data.get('profile_name', ''))
        self.desc_input.setPlainText(self.profile_data.get('profile_description', ''))

        # Detect icon mode from profile_icon
        profile_icon = self.profile_data.get('profile_icon', 'user')
        if profile_icon.startswith('image:'):
            self.icon_mode = 'image'
            self.mode_combo.setCurrentText('Image')
            self.selected_icon = profile_icon
        elif profile_icon.startswith('initial:'):
            self.icon_mode = 'initial'
            self.mode_combo.setCurrentText('Initial')
            # For initial mode, we don't store the letter separately - it's auto-generated from name
            self.selected_icon = profile_icon
        else:
            self.icon_mode = 'icon'
            self.mode_combo.setCurrentText('Icon')
            self.selected_icon = profile_icon

        # Browser profile name is auto-generated, but load if exists
        browser_profile_name = self.profile_data.get('profile_browser_profile_name', '')
        if browser_profile_name:
            self.profile_name_input.setText(browser_profile_name)

        # Generate profile path from workspace + profile name
        self._generate_browser_profile_path(browser_profile_name)
        self.color_input.setText(self.selected_color)
        launch_window_mode = (self.profile_data.get('launch_window_mode') or 'windowed').lower()
        index = self.window_mode_combo.findData(launch_window_mode)
        self.window_mode_combo.setCurrentIndex(index if index >= 0 else 0)
        self.additional_parameters = self._parse_additional_parameters(self.profile_data.get('launch_additional_parameters', []))
        self._refresh_parameters_list()

        # Update preview
        self._on_mode_changed(self.mode_combo.currentText())

    def _on_save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, 'Validation Error', 'Profile name is required')
            return

        browser_profile_name = self.profile_name_input.text().strip()
        
        # Check for duplicate profile name (folder already exists on disk)
        import os
        root_path = self.workspace_data.get('workspace_root_profile_path', '') if self.workspace_data else ''
        full_path = os.path.join(root_path, browser_profile_name) if root_path and browser_profile_name else ''
        
        if not self.is_edit_mode:
            # Creating new profile - check if folder exists
            if full_path and os.path.exists(full_path):
                QMessageBox.warning(self, 'Profile Exists', 'A profile with this name already exists. Please use another name.')
                return
        else:
            # Edit mode - check if NEW name conflicts with other profiles
            if full_path and os.path.exists(full_path):
                old_browser_name = self.profile_data.get('profile_browser_profile_name', '')
                if browser_profile_name != old_browser_name:
                    QMessageBox.warning(self, 'Profile Exists', 'A profile with this name already exists. Please use another name.')
                    return

        # Build icon value based on mode - Initial mode auto-generates from profile name
        if self.icon_mode == 'initial':
            initial = name[0].upper() if name else 'U'
            icon_value = f'initial:{initial}'
        else:
            icon_value = self.selected_icon

        data = {
            'profile_name': name,
            'profile_description': self.desc_input.toPlainText().strip(),
            'profile_icon': icon_value,
            'profile_color': self.selected_color,
            'profile_browser_profile_name': browser_profile_name,
            'profile_browser_profile_path': self.profile_path_input.text().strip(),
            'launch_window_mode': self.window_mode_combo.currentData() or 'windowed',
            'launch_additional_parameters': list(self.additional_parameters),
        }

        if self.is_edit_mode:
            data['profile_id'] = self.profile_data['profile_id']

        self.profile_saved.emit(data)
        self.accept()