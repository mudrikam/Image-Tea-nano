import os
import json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QFileDialog, QMessageBox, QSizePolicy, QColorDialog, QComboBox,
    QTabWidget, QWidget, QScrollArea, QListWidget, QInputDialog, QAbstractItemView,
    QCheckBox, QGroupBox, QRadioButton
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QFont, QPixmap, QPainter, QColor
import qtawesome as qta
from config import BASE_PATH
from ui.theme_system import theme


class AddProfileDialog(QDialog):
    """Dialog for creating/editing profile"""
    profile_saved = Signal(dict)
    PROXY_SETTING_KEYS = [
        'proxy_enabled',
        'proxy_mode',
        'proxy_scheme',
        'proxy_host',
        'proxy_port',
        'proxy_username',
        'proxy_password',
        'proxy_bypass_list',
        'proxy_pac_url',
        'proxy_dns_remote',
        'proxy_share_all_protocols',
        'proxy_http_host',
        'proxy_http_port',
        'proxy_ssl_host',
        'proxy_ssl_port',
        'proxy_ftp_host',
        'proxy_ftp_port',
        'proxy_socks_host',
        'proxy_socks_port',
        'proxy_socks_version',
    ]

    def __init__(self, profile_data=None, workspace_data=None, parent=None):
        super().__init__(parent)
        self.profile_data = profile_data
        self.workspace_data = workspace_data
        self.is_edit_mode = profile_data is not None
        self.selected_icon = profile_data.get('profile_icon', 'initial') if profile_data else 'initial'
        self.selected_color = profile_data.get('profile_color', '#3b82f6') if profile_data else '#3b82f6'
        self.icon_mode = 'initial' if not profile_data else 'icon'  # Default to Initial for new, Icon for edit
        self.additional_parameters = []
        self.proxy_settings = self._default_proxy_settings()

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
        self.proxy_tab = QWidget()
        self.tabs.addTab(self.main_tab, qta.icon('fa6s.user-gear'), 'Main Data')
        self.tabs.addTab(self.parameters_tab, qta.icon('fa6s.sliders'), 'Parameters')
        self.tabs.addTab(self.proxy_tab, qta.icon('fa6s.network-wired'), 'Proxy')
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
        self._setup_proxy_tab()
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

    def _setup_proxy_tab(self):
        proxy_layout = QVBoxLayout(self.proxy_tab)
        proxy_layout.setContentsMargins(0, 0, 0, 0)
        proxy_layout.setSpacing(0)

        proxy_scroll = QScrollArea()
        proxy_scroll.setWidgetResizable(True)
        proxy_scroll.setFrameShape(QScrollArea.NoFrame)
        proxy_content = QWidget()
        proxy_form_layout = QVBoxLayout(proxy_content)
        proxy_form_layout.setContentsMargins(8, 8, 8, 8)
        proxy_form_layout.setSpacing(8)

        self.proxy_enabled_checkbox = QCheckBox('Enable custom proxy for this profile')
        self.proxy_enabled_checkbox.toggled.connect(self._update_proxy_ui_state)
        proxy_form_layout.addWidget(self.proxy_enabled_checkbox)

        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(6)
        mode_icon = QLabel()
        mode_icon.setPixmap(qta.icon('fa6s.route', color=theme.get_color('gray')).pixmap(16, 16))
        mode_layout.addWidget(mode_icon)
        mode_label = QLabel('Mode:')
        mode_label.setMinimumWidth(70)
        mode_layout.addWidget(mode_label)

        self.proxy_mode_combo = QComboBox()
        self.proxy_mode_combo.addItem('Use browser/system default', 'system')
        self.proxy_mode_combo.addItem('Direct / no proxy', 'direct')
        self.proxy_mode_combo.addItem('Manual', 'manual')
        self.proxy_mode_combo.addItem('PAC script URL', 'pac')
        self.proxy_mode_combo.addItem('Auto detect', 'autodetect')
        self.proxy_mode_combo.currentIndexChanged.connect(self._update_proxy_ui_state)
        mode_layout.addWidget(self.proxy_mode_combo, 1)
        proxy_form_layout.addLayout(mode_layout)

        self.proxy_hint_label = QLabel()
        self.proxy_hint_label.setWordWrap(True)
        self.proxy_hint_label.setStyleSheet(f"color: {theme.get_color('gray')};")
        proxy_form_layout.addWidget(self.proxy_hint_label)

        self.manual_proxy_group = QGroupBox('Manual Proxy')
        manual_layout = QVBoxLayout(self.manual_proxy_group)
        manual_layout.setSpacing(8)

        self.proxy_single_radio = QRadioButton('Single proxy for all protocols')
        self.proxy_advanced_radio = QRadioButton('Advanced per protocol')
        self.proxy_single_radio.setChecked(True)
        self.proxy_single_radio.toggled.connect(self._update_proxy_ui_state)
        self.proxy_advanced_radio.toggled.connect(self._update_proxy_ui_state)
        manual_layout.addWidget(self.proxy_single_radio)
        manual_layout.addWidget(self.proxy_advanced_radio)

        self.single_proxy_widget = QWidget()
        single_layout = QVBoxLayout(self.single_proxy_widget)
        single_layout.setContentsMargins(0, 0, 0, 0)
        single_layout.setSpacing(6)

        single_host_layout = QHBoxLayout()
        self.proxy_scheme_combo = QComboBox()
        self.proxy_scheme_combo.addItem('HTTP', 'http')
        self.proxy_scheme_combo.addItem('HTTPS', 'https')
        self.proxy_scheme_combo.addItem('SOCKS4', 'socks4')
        self.proxy_scheme_combo.addItem('SOCKS5', 'socks5')
        single_host_layout.addWidget(self.proxy_scheme_combo)

        self.proxy_host_input = QLineEdit()
        self.proxy_host_input.setPlaceholderText('Host or IP')
        single_host_layout.addWidget(self.proxy_host_input, 1)

        self.proxy_port_input = QLineEdit()
        self.proxy_port_input.setPlaceholderText('Port')
        self.proxy_port_input.setMaximumWidth(90)
        single_host_layout.addWidget(self.proxy_port_input)
        single_layout.addLayout(single_host_layout)

        auth_layout = QHBoxLayout()
        self.proxy_username_input = QLineEdit()
        self.proxy_username_input.setPlaceholderText('Username (stored for persistence)')
        auth_layout.addWidget(self.proxy_username_input, 1)

        self.proxy_password_input = QLineEdit()
        self.proxy_password_input.setPlaceholderText('Password (stored for persistence)')
        self.proxy_password_input.setEchoMode(QLineEdit.Password)
        auth_layout.addWidget(self.proxy_password_input, 1)
        single_layout.addLayout(auth_layout)
        manual_layout.addWidget(self.single_proxy_widget)

        self.advanced_proxy_widget = QWidget()
        advanced_layout = QVBoxLayout(self.advanced_proxy_widget)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.setSpacing(6)

        self.proxy_http_host_input, self.proxy_http_port_input = self._create_proxy_endpoint_row(advanced_layout, 'HTTP:')
        self.proxy_ssl_host_input, self.proxy_ssl_port_input = self._create_proxy_endpoint_row(advanced_layout, 'HTTPS:')
        self.proxy_ftp_host_input, self.proxy_ftp_port_input = self._create_proxy_endpoint_row(advanced_layout, 'FTP:')

        socks_layout = QHBoxLayout()
        socks_label = QLabel('SOCKS:')
        socks_label.setMinimumWidth(70)
        socks_layout.addWidget(socks_label)
        self.proxy_socks_host_input = QLineEdit()
        self.proxy_socks_host_input.setPlaceholderText('SOCKS host')
        socks_layout.addWidget(self.proxy_socks_host_input, 1)
        self.proxy_socks_port_input = QLineEdit()
        self.proxy_socks_port_input.setPlaceholderText('Port')
        self.proxy_socks_port_input.setMaximumWidth(90)
        socks_layout.addWidget(self.proxy_socks_port_input)
        self.proxy_socks_version_combo = QComboBox()
        self.proxy_socks_version_combo.addItem('SOCKS4', '4')
        self.proxy_socks_version_combo.addItem('SOCKS5', '5')
        socks_layout.addWidget(self.proxy_socks_version_combo)
        advanced_layout.addLayout(socks_layout)
        manual_layout.addWidget(self.advanced_proxy_widget)

        self.proxy_remote_dns_checkbox = QCheckBox('Use remote DNS when supported (relevant for SOCKS)')
        manual_layout.addWidget(self.proxy_remote_dns_checkbox)
        proxy_form_layout.addWidget(self.manual_proxy_group)

        self.pac_proxy_group = QGroupBox('PAC Script')
        pac_layout = QVBoxLayout(self.pac_proxy_group)
        pac_layout.setSpacing(6)
        self.proxy_pac_url_input = QLineEdit()
        self.proxy_pac_url_input.setPlaceholderText('https://example.com/proxy.pac')
        pac_layout.addWidget(self.proxy_pac_url_input)
        proxy_form_layout.addWidget(self.pac_proxy_group)

        bypass_group = QGroupBox('Bypass List')
        bypass_layout = QVBoxLayout(bypass_group)
        bypass_layout.setSpacing(6)
        self.proxy_bypass_input = QTextEdit()
        self.proxy_bypass_input.setPlaceholderText('localhost\n127.0.0.1\n*.internal')
        self.proxy_bypass_input.setMaximumHeight(90)
        bypass_layout.addWidget(self.proxy_bypass_input)
        proxy_form_layout.addWidget(bypass_group)

        proxy_note = QLabel('Proxy username/password are persisted for profile portability. Runtime authentication support depends on the target browser and proxy type.')
        proxy_note.setWordWrap(True)
        proxy_note.setStyleSheet(f"color: {theme.get_color('gray')};")
        proxy_form_layout.addWidget(proxy_note)
        proxy_form_layout.addStretch()

        proxy_scroll.setWidget(proxy_content)
        proxy_layout.addWidget(proxy_scroll)

        self._update_proxy_ui_state()

    def _create_proxy_endpoint_row(self, parent_layout, label_text):
        row_layout = QHBoxLayout()
        row_layout.setSpacing(6)
        label = QLabel(label_text)
        label.setMinimumWidth(70)
        row_layout.addWidget(label)
        host_input = QLineEdit()
        host_input.setPlaceholderText('Host or IP')
        row_layout.addWidget(host_input, 1)
        port_input = QLineEdit()
        port_input.setPlaceholderText('Port')
        port_input.setMaximumWidth(90)
        row_layout.addWidget(port_input)
        parent_layout.addLayout(row_layout)
        return host_input, port_input

    def _default_proxy_settings(self):
        return {
            'proxy_enabled': 'false',
            'proxy_mode': 'system',
            'proxy_scheme': 'http',
            'proxy_host': '',
            'proxy_port': '',
            'proxy_username': '',
            'proxy_password': '',
            'proxy_bypass_list': '[]',
            'proxy_pac_url': '',
            'proxy_dns_remote': 'false',
            'proxy_share_all_protocols': 'true',
            'proxy_http_host': '',
            'proxy_http_port': '',
            'proxy_ssl_host': '',
            'proxy_ssl_port': '',
            'proxy_ftp_host': '',
            'proxy_ftp_port': '',
            'proxy_socks_host': '',
            'proxy_socks_port': '',
            'proxy_socks_version': '5',
        }

    def _is_truthy(self, value):
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}

    def _normalize_proxy_text(self, value):
        return str(value or '').strip()

    def _normalize_proxy_port(self, value):
        text = self._normalize_proxy_text(value)
        return text if text.isdigit() else ''

    def _parse_bypass_list(self, value):
        if isinstance(value, list):
            return [self._normalize_proxy_text(item) for item in value if self._normalize_proxy_text(item)]
        if isinstance(value, str) and value.strip():
            try:
                decoded = json.loads(value)
                if isinstance(decoded, list):
                    return [self._normalize_proxy_text(item) for item in decoded if self._normalize_proxy_text(item)]
            except json.JSONDecodeError:
                pass
            return [line.strip() for line in value.splitlines() if line.strip()]
        return []

    def _serialize_bypass_list(self, value):
        return json.dumps(self._parse_bypass_list(value))

    def _load_proxy_settings(self, profile_data):
        settings = self._default_proxy_settings()
        for key in self.PROXY_SETTING_KEYS:
            if key in profile_data:
                settings[key] = str(profile_data.get(key, settings[key]))
        return settings

    def _apply_proxy_settings_to_ui(self, settings):
        self.proxy_settings = settings
        self.proxy_enabled_checkbox.setChecked(self._is_truthy(settings.get('proxy_enabled')))
        mode_index = self.proxy_mode_combo.findData(settings.get('proxy_mode', 'system'))
        self.proxy_mode_combo.setCurrentIndex(mode_index if mode_index >= 0 else 0)

        scheme_index = self.proxy_scheme_combo.findData(settings.get('proxy_scheme', 'http'))
        self.proxy_scheme_combo.setCurrentIndex(scheme_index if scheme_index >= 0 else 0)
        self.proxy_host_input.setText(settings.get('proxy_host', ''))
        self.proxy_port_input.setText(settings.get('proxy_port', ''))
        self.proxy_username_input.setText(settings.get('proxy_username', ''))
        self.proxy_password_input.setText(settings.get('proxy_password', ''))
        self.proxy_bypass_input.setPlainText('\n'.join(self._parse_bypass_list(settings.get('proxy_bypass_list'))))
        self.proxy_pac_url_input.setText(settings.get('proxy_pac_url', ''))
        self.proxy_remote_dns_checkbox.setChecked(self._is_truthy(settings.get('proxy_dns_remote')))
        share_all_protocols = self._is_truthy(settings.get('proxy_share_all_protocols', 'true'))
        self.proxy_http_host_input.setText(settings.get('proxy_http_host', ''))
        self.proxy_http_port_input.setText(settings.get('proxy_http_port', ''))
        self.proxy_ssl_host_input.setText(settings.get('proxy_ssl_host', ''))
        self.proxy_ssl_port_input.setText(settings.get('proxy_ssl_port', ''))
        self.proxy_ftp_host_input.setText(settings.get('proxy_ftp_host', ''))
        self.proxy_ftp_port_input.setText(settings.get('proxy_ftp_port', ''))
        self.proxy_socks_host_input.setText(settings.get('proxy_socks_host', ''))
        self.proxy_socks_port_input.setText(settings.get('proxy_socks_port', ''))
        socks_version_index = self.proxy_socks_version_combo.findData(settings.get('proxy_socks_version', '5'))
        self.proxy_socks_version_combo.setCurrentIndex(socks_version_index if socks_version_index >= 0 else 1)
        self.proxy_single_radio.setChecked(share_all_protocols)
        self.proxy_advanced_radio.setChecked(not share_all_protocols)
        self._update_proxy_ui_state()

    def _collect_proxy_settings_from_ui(self):
        proxy_enabled = self.proxy_enabled_checkbox.isChecked()
        proxy_mode = self.proxy_mode_combo.currentData() or 'system'
        share_all_protocols = self.proxy_single_radio.isChecked()
        settings = self._default_proxy_settings()
        settings.update({
            'proxy_enabled': 'true' if proxy_enabled else 'false',
            'proxy_mode': proxy_mode,
            'proxy_scheme': self.proxy_scheme_combo.currentData() or 'http',
            'proxy_host': self._normalize_proxy_text(self.proxy_host_input.text()),
            'proxy_port': self._normalize_proxy_port(self.proxy_port_input.text()),
            'proxy_username': self._normalize_proxy_text(self.proxy_username_input.text()),
            'proxy_password': self._normalize_proxy_text(self.proxy_password_input.text()),
            'proxy_bypass_list': self._serialize_bypass_list(self.proxy_bypass_input.toPlainText()),
            'proxy_pac_url': self._normalize_proxy_text(self.proxy_pac_url_input.text()),
            'proxy_dns_remote': 'true' if self.proxy_remote_dns_checkbox.isChecked() else 'false',
            'proxy_share_all_protocols': 'true' if share_all_protocols else 'false',
            'proxy_http_host': self._normalize_proxy_text(self.proxy_http_host_input.text()),
            'proxy_http_port': self._normalize_proxy_port(self.proxy_http_port_input.text()),
            'proxy_ssl_host': self._normalize_proxy_text(self.proxy_ssl_host_input.text()),
            'proxy_ssl_port': self._normalize_proxy_port(self.proxy_ssl_port_input.text()),
            'proxy_ftp_host': self._normalize_proxy_text(self.proxy_ftp_host_input.text()),
            'proxy_ftp_port': self._normalize_proxy_port(self.proxy_ftp_port_input.text()),
            'proxy_socks_host': self._normalize_proxy_text(self.proxy_socks_host_input.text()),
            'proxy_socks_port': self._normalize_proxy_port(self.proxy_socks_port_input.text()),
            'proxy_socks_version': self.proxy_socks_version_combo.currentData() or '5',
        })
        return settings

    def _update_proxy_ui_state(self):
        proxy_enabled = getattr(self, 'proxy_enabled_checkbox', None) and self.proxy_enabled_checkbox.isChecked()
        proxy_mode = self.proxy_mode_combo.currentData() if hasattr(self, 'proxy_mode_combo') else 'system'
        is_manual = proxy_enabled and proxy_mode == 'manual'
        is_pac = proxy_enabled and proxy_mode == 'pac'
        use_single = self.proxy_single_radio.isChecked() if hasattr(self, 'proxy_single_radio') else True

        if hasattr(self, 'manual_proxy_group'):
            self.manual_proxy_group.setEnabled(proxy_enabled)
            self.manual_proxy_group.setVisible(is_manual)
        if hasattr(self, 'pac_proxy_group'):
            self.pac_proxy_group.setEnabled(proxy_enabled)
            self.pac_proxy_group.setVisible(is_pac)
        if hasattr(self, 'single_proxy_widget'):
            self.single_proxy_widget.setVisible(is_manual and use_single)
        if hasattr(self, 'advanced_proxy_widget'):
            self.advanced_proxy_widget.setVisible(is_manual and not use_single)
        if hasattr(self, 'proxy_bypass_input'):
            self.proxy_bypass_input.setEnabled(proxy_enabled and proxy_mode in {'manual', 'pac'})

        hint = 'Proxy settings are disabled for this profile.'
        if proxy_enabled:
            if proxy_mode == 'system':
                hint = 'Use the browser or operating system proxy defaults for this profile.'
            elif proxy_mode == 'direct':
                hint = 'Force direct connections and bypass proxies when the browser supports it.'
            elif proxy_mode == 'manual':
                hint = 'Manual proxy is translated to Chromium launch flags and Firefox profile preferences.'
            elif proxy_mode == 'pac':
                hint = 'PAC URL is passed to Chromium and written to Firefox proxy preferences.'
            elif proxy_mode == 'autodetect':
                hint = 'Use automatic proxy detection where the browser supports it.'
        if hasattr(self, 'proxy_hint_label'):
            self.proxy_hint_label.setText(hint)

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
        self._apply_proxy_settings_to_ui(self._load_proxy_settings(self.profile_data))

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

        proxy_settings = self._collect_proxy_settings_from_ui()
        proxy_mode = proxy_settings.get('proxy_mode', 'system')
        if proxy_settings.get('proxy_enabled') == 'true':
            if proxy_mode == 'manual':
                if proxy_settings.get('proxy_share_all_protocols') == 'true':
                    if not proxy_settings.get('proxy_host') or not proxy_settings.get('proxy_port'):
                        QMessageBox.warning(self, 'Validation Error', 'Manual proxy requires host and port')
                        self.tabs.setCurrentWidget(self.proxy_tab)
                        return
                else:
                    advanced_has_endpoint = any([
                        proxy_settings.get('proxy_http_host') and proxy_settings.get('proxy_http_port'),
                        proxy_settings.get('proxy_ssl_host') and proxy_settings.get('proxy_ssl_port'),
                        proxy_settings.get('proxy_ftp_host') and proxy_settings.get('proxy_ftp_port'),
                        proxy_settings.get('proxy_socks_host') and proxy_settings.get('proxy_socks_port'),
                    ])
                    if not advanced_has_endpoint:
                        QMessageBox.warning(self, 'Validation Error', 'Advanced manual proxy requires at least one proxy endpoint')
                        self.tabs.setCurrentWidget(self.proxy_tab)
                        return
            elif proxy_mode == 'pac' and not proxy_settings.get('proxy_pac_url'):
                QMessageBox.warning(self, 'Validation Error', 'PAC proxy mode requires a PAC URL')
                self.tabs.setCurrentWidget(self.proxy_tab)
                return

        data = {
            'profile_name': name,
            'profile_description': self.desc_input.toPlainText().strip(),
            'profile_icon': icon_value,
            'profile_color': self.selected_color,
            'profile_browser_profile_name': browser_profile_name,
            'profile_browser_profile_path': self.profile_path_input.text().strip(),
            'launch_window_mode': self.window_mode_combo.currentData() or 'windowed',
            'launch_additional_parameters': list(self.additional_parameters),
            'proxy_settings': proxy_settings,
        }

        if self.is_edit_mode:
            data['profile_id'] = self.profile_data['profile_id']

        self.profile_saved.emit(data)
        self.accept()