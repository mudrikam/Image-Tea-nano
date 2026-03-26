import webbrowser
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QGroupBox,
    QSpinBox, QCheckBox, QScrollArea, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
import qtawesome as qta
from ui.theme_system import theme
from helpers.tools.holiday_calendar_helper import config_helper, cache_helper
from helpers.tools.holiday_calendar_helper.holiday_logger import logger



class FieldRow(QFrame):
    def __init__(self, label: str, widget, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        lbl = QLabel(label)
        lbl.setFixedWidth(120)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(lbl)
        layout.addWidget(widget, 1)


class ConfigTabWidget(QWidget):
    config_saved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        page_title = QLabel('Configuration')
        tf = QFont()
        tf.setBold(True)
        tf.setPointSize(13)
        page_title.setFont(tf)
        page_title.setStyleSheet(f'color: {theme.get_color("primary")};')
        layout.addWidget(page_title)

        subtitle = QLabel('Manage API key and cache settings for Holiday Calendar.')
        layout.addWidget(subtitle)

        api_group = QGroupBox('API Settings')
        api_lyt = QVBoxLayout(api_group)
        api_lyt.setSpacing(8)
        api_lyt.setContentsMargins(12, 12, 12, 12)

        self._api_key_field = QLineEdit()
        self._api_key_field.setPlaceholderText('Enter your Calendarific API key...')
        self._api_key_field.setEchoMode(QLineEdit.EchoMode.Password)

        key_row_widget = QWidget()
        key_row_lyt = QHBoxLayout(key_row_widget)
        key_row_lyt.setContentsMargins(0, 0, 0, 0)
        key_row_lyt.setSpacing(4)
        key_row_lyt.addWidget(self._api_key_field, 1)

        self._toggle_btn = QPushButton()
        self._toggle_btn.setFixedSize(28, 28)
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setToolTip('Show/hide API key')
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        try:
            self._toggle_btn.setIcon(qta.icon('fa6s.eye'))
        except Exception:
            self._toggle_btn.setText('V')

        def _toggle_visibility(checked):
            if checked:
                self._api_key_field.setEchoMode(QLineEdit.EchoMode.Normal)
                try:
                    self._toggle_btn.setIcon(qta.icon('fa6s.eye-slash', color=theme.get_color('primary')))
                except Exception:
                    pass
            else:
                self._api_key_field.setEchoMode(QLineEdit.EchoMode.Password)
                try:
                    self._toggle_btn.setIcon(qta.icon('fa6s.eye'))
                except Exception:
                    pass
        self._toggle_btn.toggled.connect(_toggle_visibility)
        key_row_lyt.addWidget(self._toggle_btn)

        api_lyt.addWidget(FieldRow('API Key', key_row_widget))

        self._base_url_field = QLineEdit()
        self._base_url_field.setPlaceholderText('https://calendarific.com/api/v2')
        api_lyt.addWidget(FieldRow('Base URL', self._base_url_field))

        self._default_country_field = QLineEdit()
        self._default_country_field.setPlaceholderText('e.g. US or ID')
        api_lyt.addWidget(FieldRow('Negara Default', self._default_country_field))

        get_key_btn = QPushButton('Get API Key at calendarific.com')
        get_key_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        try:
            get_key_btn.setIcon(qta.icon('fa6s.arrow-up-right-from-square'))
        except Exception:
            pass
        get_key_btn.clicked.connect(lambda: webbrowser.open('https://calendarific.com/account/dashboard'))
        api_lyt.addWidget(get_key_btn)
        layout.addWidget(api_group)

        cache_group = QGroupBox('Cache Settings')
        cache_lyt = QVBoxLayout(cache_group)
        cache_lyt.setSpacing(8)
        cache_lyt.setContentsMargins(12, 12, 12, 12)

        self._expire_days_spin = QSpinBox()
        self._expire_days_spin.setRange(1, 365)
        self._expire_days_spin.setValue(7)
        self._expire_days_spin.setSuffix(' days')
        cache_lyt.addWidget(FieldRow('Cache Expiry', self._expire_days_spin))

        self._use_sqlite_check = QCheckBox('Use SQLite cache (recommended)')
        cache_lyt.addWidget(self._use_sqlite_check)

        clear_cache_btn = QPushButton('Clear All Cache')
        clear_cache_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        try:
            clear_cache_btn.setIcon(qta.icon('fa6s.trash'))
        except Exception:
            pass
        clear_cache_btn.clicked.connect(self._clear_cache)
        cache_lyt.addWidget(clear_cache_btn)
        layout.addWidget(cache_group)

        save_btn = QPushButton('Save Configuration')
        save_btn.setFixedHeight(36)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f'''
            QPushButton {{
                background-color: {theme.get_color("primary")};
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {theme.get_color("primary_hover")}; }}
            QPushButton:pressed {{ background-color: {theme.get_color("primary_pressed")}; }}
        ''')
        try:
            save_btn.setIcon(qta.icon('fa6s.floppy-disk', color='white'))
        except Exception:
            pass
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _load_values(self):
        from database.db_operation import ImageTeaDB
        self._api_key_field.setText(ImageTeaDB().calendarific_get_api_key())
        self._base_url_field.setText(config_helper.get_base_url())
        self._default_country_field.setText(config_helper.get_default_country())
        self._expire_days_spin.setValue(config_helper.get_expire_days())
        self._use_sqlite_check.setChecked(config_helper.get_use_sqlite())

    def _save(self):
        from database.db_operation import ImageTeaDB
        ImageTeaDB().calendarific_set_api_key(self._api_key_field.text().strip())
        config_helper.set_base_url(self._base_url_field.text().strip() or 'https://calendarific.com/api/v2')
        config_helper.set_default_country(self._default_country_field.text().strip().upper() or 'US')
        config_helper.set_expire_days(self._expire_days_spin.value())
        config_helper.set_use_sqlite(self._use_sqlite_check.isChecked())
        logger.success('Configuration saved.')
        self.config_saved.emit()

    def _clear_cache(self):
        reply = QMessageBox.question(
            self, 'Clear Cache',
            'This will delete all holiday cache data. Continue?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            cache_helper.clear_all()
