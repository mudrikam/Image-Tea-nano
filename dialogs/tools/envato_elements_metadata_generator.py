import os
import json
import base64
import threading
from io import BytesIO
from PIL import Image
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel,
    QTextEdit, QLineEdit, QProgressBar, QFileDialog, QMessageBox,
    QSpinBox, QScrollArea, QGroupBox, QCheckBox, QComboBox, QApplication
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QBuffer, QIODevice, QByteArray
from PySide6.QtGui import QPixmap, QClipboard, QCursor, QIcon, QColor
import qtawesome as qta
from config import BASE_PATH
from database.db_operation import ImageTeaDB
from helpers.tools.envato_elements_api_helper import process_image_with_gemini
from helpers.tools.envato_elements_yaml_helper import (
    load_data_yaml, save_data_yaml, replace_placeholders, generate_final_description
)
from ui.theme_system import theme


class ImageProcessor(QThread):
    result_ready = Signal(dict)
    error_occurred = Signal(str)
    retry_status = Signal(str, int)
    
    def __init__(self, image_data, api_key, model, limits, service=None, endpoint=None, max_retries=5):
        super().__init__()
        self.image_data = image_data
        self.api_key = api_key
        self.model = model
        self.limits = limits
        self.service = service
        self.endpoint = endpoint
        self.max_retries = max_retries
    
    def run(self):
        result, error = process_image_with_gemini(
            self.image_data, 
            self.api_key, 
            self.model, 
            self.limits,
            service=self.service,
            endpoint=self.endpoint
        )
        
        if result:
            self.result_ready.emit(result)
        else:
            self.error_occurred.emit(error if error else "Unknown error")


class ImageDisplayWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        _gray_q0 = QColor(theme.get_color('gray'))
        _gray_rgb0 = f"{_gray_q0.red()},{_gray_q0.green()},{_gray_q0.blue()}"
        self.setStyleSheet(f"""
            QLabel {{
                border: 2px dashed {theme.get_color('gray')};
                border-radius: 8px;
                background-color: rgba({_gray_rgb0},0.05);
                color: {theme.get_color('gray')};
                font-size: 12px;
            }}
            QLabel:hover {{
                background-color: rgba({_gray_rgb0},0.1);
                border-color: {theme.get_color('gray')};
            }}
        """)
        self.setText("Drag & Drop Image Here\nor CLICK to Select File")
        self.setMinimumSize(400, 120)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.main_window = parent
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.main_window:
            self.main_window.open_image()
        super().mousePressEvent(event)
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if self.main_window:
                self.main_window.load_image(file_path)


class EnvatoElementsMetadataDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Envato Elements Metadata Generator")
        self.resize(300, 700)
        
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.db = ImageTeaDB()
        self.config_path = os.path.join(BASE_PATH, 'configs', 'elements_mockup_metadata_generator_config.json')
        self.runtime_state_path = os.path.join(BASE_PATH, 'temp', 'elements_mockup', 'runtime_state.json')
        
        self.image_data = None
        self.processor_thread = None
        
        self.load_config()
        
        if self.config['always_on_top']:
            self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(Qt.Window)
        
        self.setup_ui()
        self.setup_progress_timer()
        self.load_yaml_data()
        self.update_field_counts()
    
    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = {
                'limits': {
                    'title_min': 30,
                    'title_max': 100,
                    'tagline_max': 100,
                    'tags_expected': 15,
                    'expected_features': 8
                },
                'defaults': {
                    'items_count': 1,
                    'dpi': '300',
                    'width': '4500',
                    'height': '3000'
                },
                'always_on_top': False,
                'items_count': 1
            }
            self.save_config()
        
        if os.path.exists(self.runtime_state_path):
            with open(self.runtime_state_path, 'r', encoding='utf-8') as f:
                runtime_state = json.load(f)
                self.config['selected_api_key'] = runtime_state.get('selected_api_key', '')
        else:
            self.config['selected_api_key'] = ''
            self.save_runtime_state()
    
    def save_config(self):
        static_config = {
            'limits': self.config['limits'],
            'defaults': self.config['defaults'],
            'always_on_top': self.config['always_on_top'],
            'items_count': self.config['items_count']
        }
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(static_config, f, indent=2)
    
    def save_runtime_state(self):
        runtime_state = {
            'selected_api_key': self.config.get('selected_api_key', '')
        }
        os.makedirs(os.path.dirname(self.runtime_state_path), exist_ok=True)
        with open(self.runtime_state_path, 'w', encoding='utf-8') as f:
            json.dump(runtime_state, f, indent=2)
    
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(2)
        
        always_on_top_layout = QHBoxLayout()
        self.always_on_top_check = QCheckBox("Always on Top")
        self.always_on_top_check.setChecked(self.config['always_on_top'])
        self.always_on_top_check.toggled.connect(self.toggle_always_on_top)
        always_on_top_layout.addWidget(self.always_on_top_check)
        always_on_top_layout.addStretch()
        main_layout.addLayout(always_on_top_layout)
        
        self.create_api_selection_panel(main_layout)
        self.create_image_panel(main_layout)
        self.create_results_panel(main_layout)
    
    def setup_progress_timer(self):
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.update_progress_animation)
        self.button_blink_state = False
    
    def update_progress_animation(self):
        self.button_blink_state = not self.button_blink_state
        if self.button_blink_state:
            _succ_q = QColor(theme.get_color('success'))
            _succ_rgb = f"{_succ_q.red()},{_succ_q.green()},{_succ_q.blue()}"
            self.process_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba({_succ_rgb},0.3);
                    border: 2px solid {theme.get_color('success')};
                    border-radius: 5px;
                    padding: 4px;
                    font-weight: bold;
                    color: {theme.get_color('white')};
                }}
            """)
        else:
            _succ_q = QColor(theme.get_color('success'))
            _succ_rgb = f"{_succ_q.red()},{_succ_q.green()},{_succ_q.blue()}"
            self.process_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba({_succ_rgb},0.1);
                    border: 2px solid {theme.get_color('success')};
                    border-radius: 5px;
                    padding: 4px;
                    font-weight: bold;
                    color: {theme.get_color('text_dark')};
                }}
            """)
    
    def create_api_selection_panel(self, main_layout):
        api_group = QGroupBox("API Configuration")
        api_layout = QVBoxLayout(api_group)
        api_layout.setContentsMargins(4, 4, 4, 4)
        api_layout.setSpacing(2)
        
        self.api_combo = QComboBox()
        self.api_combo.setMaximumHeight(24)
        api_layout.addWidget(QLabel("Select API:"))
        api_layout.addWidget(self.api_combo)
        
        settings_btn = QPushButton("Settings")
        settings_btn.setIcon(qta.icon('fa6s.gear'))
        settings_btn.setMaximumHeight(24)
        settings_btn.clicked.connect(self.open_api_settings)
        api_layout.addWidget(settings_btn)
        
        main_layout.addWidget(api_group)
        
        self.load_api_keys()
    
    def load_api_keys(self):
        self.api_combo.clear()
        all_api_keys = self.db.get_all_api_keys()
        
        self.api_map = {}
        for row in all_api_keys:
            # DB row: (service, api_key, note, last_tested, status, model, provider_endpoint)
            service = row[0] if len(row) > 0 else None
            api_key = row[1] if len(row) > 1 else None
            note = row[2] if len(row) > 2 else ''
            last_tested = row[3] if len(row) > 3 else None
            status = row[4] if len(row) > 4 else ''
            model = row[5] if len(row) > 5 else ''
            endpoint = row[6] if len(row) > 6 else None
            if api_key and model:
                masked_key = f"***{api_key[-5:]}" if len(api_key) >= 5 else api_key
                display_text = f"{service} - {model} ({masked_key})"
                if note:
                    display_text += f" - {note}"
                
                self.api_combo.addItem(display_text, api_key)
                self.api_map[api_key] = {
                    'service': service,
                    'model': model,
                    'note': note,
                    'endpoint': endpoint
                }
        
        saved_api_key = self.config['selected_api_key']
        if saved_api_key:
            index = self.api_combo.findData(saved_api_key)
            if index >= 0:
                self.api_combo.setCurrentIndex(index)
        
        self.api_combo.currentIndexChanged.connect(self.on_api_selection_changed)
    
    def on_api_selection_changed(self):
        current_api_key = self.api_combo.currentData()
        if current_api_key:
            self.config['selected_api_key'] = current_api_key
            self.save_runtime_state()
    
    def open_api_settings(self):
        from dialogs.tools.envato_settings_dialog import EnvatoSettingsDialog
        dialog = EnvatoSettingsDialog(self.config, self)
        if dialog.exec():
            self.load_config()
            self.update_field_counts()
            self.update_description_realtime()
    
    def get_current_api_credentials(self):
        current_api_key = self.api_combo.currentData()
        if current_api_key and current_api_key in self.api_map:
            api_info = self.api_map[current_api_key]
            return current_api_key, api_info['service'], api_info['model'], api_info.get('endpoint')
        return None, None, None, None
    
    def toggle_always_on_top(self, checked):
        self.config['always_on_top'] = checked
        self.save_config()
        
        if checked:
            self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(Qt.Window)
        
        self.show()
    
    def create_image_panel(self, main_layout):
        image_group = QGroupBox("Image")
        image_layout = QVBoxLayout(image_group)
        image_layout.setContentsMargins(4, 4, 4, 4)
        image_layout.setSpacing(2)
        
        self.image_display = ImageDisplayWidget(self)
        self.image_display.setMinimumSize(400, 120)
        self.image_display.setMaximumHeight(150)
        image_layout.addWidget(self.image_display)
        
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(2)
        
        self.open_btn = QPushButton("Open")
        self.open_btn.setIcon(qta.icon('fa6s.folder-open'))
        self.open_btn.setMaximumHeight(24)
        self.open_btn.clicked.connect(self.open_image)
        
        self.paste_btn = QPushButton("Paste")
        self.paste_btn.setIcon(qta.icon('fa6s.paste'))
        self.paste_btn.setMaximumHeight(24)
        self.paste_btn.clicked.connect(self.paste_image)
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setIcon(qta.icon('fa6s.trash-can'))
        self.clear_btn.setMaximumHeight(24)
        self.clear_btn.clicked.connect(self.clear_all)
        
        buttons_layout.addWidget(self.open_btn)
        buttons_layout.addWidget(self.paste_btn)
        buttons_layout.addWidget(self.clear_btn)
        
        image_layout.addLayout(buttons_layout)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(20)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)
        image_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"color: {theme.get_color('text_light')}; font-style: italic; font-size: 11px;")
        self.status_label.setMaximumHeight(16)
        image_layout.addWidget(self.status_label)
        
        self.process_btn = QPushButton("Process Image")
        self.process_btn.setIcon(qta.icon('fa6s.play'))
        self.process_btn.setMaximumHeight(30)
        self.process_btn.clicked.connect(self.process_image)
        _succ_q2 = QColor(theme.get_color('success'))
        _succ_rgb2 = f"{_succ_q2.red()},{_succ_q2.green()},{_succ_q2.blue()}"
        _gray_q2 = QColor(theme.get_color('gray'))
        _gray_rgb2 = f"{_gray_q2.red()},{_gray_q2.green()},{_gray_q2.blue()}"
        self.process_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba({_succ_rgb2},0.05);
                border: 2px solid {theme.get_color('success')};
                border-radius: 5px;
                padding: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba({_succ_rgb2},0.1);
            }}
            QPushButton:disabled {{
                background-color: rgba({_gray_rgb2},0.05);
                border-color: {theme.get_color('gray')};
            }}
        """)
        image_layout.addWidget(self.process_btn)
        
        main_layout.addWidget(image_group)
    
    def create_results_panel(self, main_layout):
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)
        results_layout.setContentsMargins(4, 4, 4, 4)
        results_layout.setSpacing(2)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(300)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(2, 2, 2, 2)
        scroll_layout.setSpacing(2)
        
        title_layout = QHBoxLayout()
        self.title_label = QLabel("Title (0/50)")
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        scroll_layout.addLayout(title_layout)
        
        title_input_layout = QHBoxLayout()
        self.title_edit = QLineEdit()
        self.title_edit.setMaximumHeight(24)
        self.title_edit.textChanged.connect(self.save_yaml_data)
        self.title_edit.textChanged.connect(self.update_field_counts)
        title_copy_btn = self.create_copy_button(self.title_edit, "Title")
        title_input_layout.addWidget(self.title_edit)
        title_input_layout.addWidget(title_copy_btn)
        scroll_layout.addLayout(title_input_layout)
        
        tagline_layout = QHBoxLayout()
        self.tagline_label = QLabel("Tagline (0/100)")
        tagline_layout.addWidget(self.tagline_label)
        tagline_layout.addStretch()
        scroll_layout.addLayout(tagline_layout)
        
        tagline_input_layout = QHBoxLayout()
        self.tagline_edit = QLineEdit()
        self.tagline_edit.setMaximumHeight(24)
        self.tagline_edit.textChanged.connect(self.save_yaml_data)
        self.tagline_edit.textChanged.connect(self.update_field_counts)
        tagline_copy_btn = self.create_copy_button(self.tagline_edit, "Tagline")
        tagline_input_layout.addWidget(self.tagline_edit)
        tagline_input_layout.addWidget(tagline_copy_btn)
        scroll_layout.addLayout(tagline_input_layout)
        
        dims_layout = QHBoxLayout()
        dims_layout.addWidget(QLabel("DPI:"))
        self.dpi_edit = QLineEdit()
        defaults = self.config['defaults']
        self.dpi_edit.setText(defaults['dpi'])
        self.dpi_edit.setMaximumHeight(24)
        self.dpi_edit.textChanged.connect(self.save_config_values)
        self.dpi_edit.textChanged.connect(self.update_description_realtime)
        dpi_copy_btn = self.create_copy_button(self.dpi_edit, "DPI")
        dims_layout.addWidget(self.dpi_edit)
        dims_layout.addWidget(dpi_copy_btn)
        
        dims_layout.addWidget(QLabel("W:"))
        self.width_edit = QLineEdit()
        self.width_edit.setText(defaults['width'])
        self.width_edit.setMaximumHeight(24)
        self.width_edit.textChanged.connect(self.save_config_values)
        self.width_edit.textChanged.connect(self.update_description_realtime)
        width_copy_btn = self.create_copy_button(self.width_edit, "Width")
        dims_layout.addWidget(self.width_edit)
        dims_layout.addWidget(width_copy_btn)
        
        dims_layout.addWidget(QLabel("H:"))
        self.height_edit = QLineEdit()
        self.height_edit.setText(defaults['height'])
        self.height_edit.setMaximumHeight(24)
        self.height_edit.textChanged.connect(self.save_config_values)
        self.height_edit.textChanged.connect(self.update_description_realtime)
        height_copy_btn = self.create_copy_button(self.height_edit, "Height")
        dims_layout.addWidget(self.height_edit)
        dims_layout.addWidget(height_copy_btn)
        
        scroll_layout.addLayout(dims_layout)
        
        tags_label_layout = QHBoxLayout()
        self.tags_label = QLabel("Tags (0/15)")
        tags_label_layout.addWidget(self.tags_label)
        tags_label_layout.addStretch()
        scroll_layout.addLayout(tags_label_layout)
        
        tags_input_layout = QHBoxLayout()
        self.tags_edit = QTextEdit()
        self.tags_edit.setMaximumHeight(60)
        self.tags_edit.textChanged.connect(self.save_yaml_data)
        self.tags_edit.textChanged.connect(self.update_field_counts)
        tags_copy_btn = self.create_copy_button(self.tags_edit, "Tags")
        tags_copy_btn.setMaximumHeight(60)
        tags_input_layout.addWidget(self.tags_edit)
        tags_input_layout.addWidget(tags_copy_btn)
        scroll_layout.addLayout(tags_input_layout)
        
        items_input_layout = QHBoxLayout()
        items_input_layout.addWidget(QLabel("Items:"))
        self.items_count_spin = QSpinBox()
        self.items_count_spin.setMinimum(1)
        self.items_count_spin.setMaximum(999)
        self.items_count_spin.setValue(defaults.get('items_count', 1))
        self.items_count_spin.setMaximumHeight(24)
        self.items_count_spin.valueChanged.connect(self.update_items_count)
        items_input_layout.addWidget(self.items_count_spin)
        items_input_layout.addStretch()
        scroll_layout.addLayout(items_input_layout)
        
        desc_label_layout = QHBoxLayout()
        desc_label_layout.addWidget(QLabel("Description:"))
        desc_label_layout.addStretch()
        scroll_layout.addLayout(desc_label_layout)
        
        desc_input_layout = QHBoxLayout()
        self.description_edit = QTextEdit()
        self.description_edit.setMinimumHeight(100)
        self.description_edit.textChanged.connect(self.save_yaml_data)
        desc_copy_btn = self.create_copy_button(self.description_edit, "Description")
        desc_copy_btn.setMaximumHeight(100)
        desc_input_layout.addWidget(self.description_edit)
        desc_input_layout.addWidget(desc_copy_btn)
        scroll_layout.addLayout(desc_input_layout)
        
        scroll.setWidget(scroll_widget)
        results_layout.addWidget(scroll)
        main_layout.addWidget(results_group)
    
    def create_copy_button(self, widget, data_name):
        copy_btn = QPushButton()
        copy_btn.setIcon(qta.icon('fa6s.copy'))
        copy_btn.setMaximumSize(20, 20)
        copy_btn.setToolTip(f"Copy {data_name}")
        copy_btn.clicked.connect(lambda: self.copy_to_clipboard(widget, data_name))
        return copy_btn
    
    def copy_to_clipboard(self, widget, data_name):
        clipboard = QApplication.clipboard()
        if isinstance(widget, QTextEdit):
            text = widget.toPlainText()
        else:
            text = widget.text()
        
        clipboard.setText(text)
        
        content_preview = text[:50] + "..." if len(text) > 50 else text
        if not content_preview.strip():
            content_preview = f"(empty {data_name.lower()})"
        
        from PySide6.QtWidgets import QToolTip
        QToolTip.showText(widget.mapToGlobal(widget.rect().center()), 
                         f"Copied: {content_preview}")
    
    def update_field_counts(self):
        limits = self.config['limits']
        title_max = limits['title_max']
        tagline_max = limits['tagline_max']
        tags_expected = limits['tags_expected']
        
        title_len = len(self.title_edit.text())
        self.title_label.setText(f"Title ({title_len}/{title_max})")
        if title_len > title_max:
            self.title_label.setStyleSheet(f"color: {theme.get_color('error')}; font-weight: bold;")
        else:
            self.title_label.setStyleSheet("")
        
        tagline_len = len(self.tagline_edit.text())
        self.tagline_label.setText(f"Tagline ({tagline_len}/{tagline_max})")
        if tagline_len > tagline_max:
            self.tagline_label.setStyleSheet(f"color: {theme.get_color('error')}; font-weight: bold;")
        else:
            self.tagline_label.setStyleSheet("")
        
        tags_text = self.tags_edit.toPlainText()
        tags_list = [t.strip() for t in tags_text.split(',') if t.strip()]
        count = len(tags_list)
        self.tags_label.setText(f"Tags ({count}/{tags_expected})")
        if count == 0:
            self.tags_label.setStyleSheet("")
        elif count != tags_expected:
            self.tags_label.setStyleSheet(f"color: {theme.get_color('error')}; font-weight: bold;")
        else:
            self.tags_label.setStyleSheet("")
    
    def save_config_values(self):
        if 'defaults' not in self.config:
            self.config['defaults'] = {}
        self.config['defaults']['dpi'] = self.dpi_edit.text()
        self.config['defaults']['width'] = self.width_edit.text()
        self.config['defaults']['height'] = self.height_edit.text()
        self.save_config()
    
    def update_items_count(self):
        if 'defaults' not in self.config:
            self.config['defaults'] = {}
        self.config['defaults']['items_count'] = self.items_count_spin.value()
        self.config['items_count'] = self.items_count_spin.value()
        self.save_config()
        self.update_description_realtime()
    
    def update_description_realtime(self):
        yaml_data = load_data_yaml()
        ai_desc = yaml_data.get('ai_description', '')
        ai_features = yaml_data.get('ai_features', [])
        items_count = self.items_count_spin.value()
        dpi = self.dpi_edit.text()
        width = self.width_edit.text()
        height = self.height_edit.text()
        
        final_desc = generate_final_description(ai_desc, ai_features, items_count, dpi, width, height)
        
        self.description_edit.blockSignals(True)
        self.description_edit.setPlainText(final_desc.strip())
        self.description_edit.blockSignals(False)
    
    def load_yaml_data(self):
        yaml_data = load_data_yaml()
        results = yaml_data.get('results', {})
        self.title_edit.setText(results.get('title', ''))
        self.tagline_edit.setText(results.get('tagline', ''))
        
        tags = results.get('tags', [])
        if isinstance(tags, list):
            self.tags_edit.setPlainText(', '.join(tags))
        else:
            self.tags_edit.setPlainText(tags)
        
        defaults = self.config['defaults']
        self.items_count_spin.setValue(yaml_data.get('items_count', defaults['items_count']))
        self.dpi_edit.setText(str(results.get('dpi', defaults['dpi'])))
        self.width_edit.setText(str(results.get('width', defaults['width'])))
        self.height_edit.setText(str(results.get('height', defaults['height'])))
        
        if yaml_data.get('image_data'):
            self.image_data = yaml_data.get('image_data')
            try:
                image_bytes = base64.b64decode(self.image_data)
                pixmap = QPixmap()
                pixmap.loadFromData(image_bytes)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(400, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.image_display.setPixmap(scaled_pixmap)
                    self.image_display.setText("")
            except Exception as e:
                print(f"Failed to load image from yaml: {e}")
        
        self.update_description_realtime()
    
    def save_yaml_data(self):
        tags_text = self.tags_edit.toPlainText()
        tags_list = [t.strip() for t in tags_text.split(',') if t.strip()]
        
        yaml_data = load_data_yaml()
        yaml_data['results']['title'] = self.title_edit.text()
        yaml_data['results']['tagline'] = self.tagline_edit.text()
        yaml_data['results']['tags'] = tags_list
        yaml_data['results']['dpi'] = self.dpi_edit.text()
        yaml_data['results']['width'] = self.width_edit.text()
        yaml_data['results']['height'] = self.height_edit.text()
        yaml_data['items_count'] = self.items_count_spin.value()
        
        save_data_yaml(yaml_data)
    
    def open_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "",
            "Image Files (*.png *.jpg *.jpeg *.gif *.bmp *.tiff)"
        )
        if file_path:
            self.load_image(file_path)
    
    def paste_image(self):
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        
        if mime_data.hasImage():
            pixmap = clipboard.pixmap()
            if not pixmap.isNull():
                byte_array = QByteArray()
                buffer = QBuffer(byte_array)
                buffer.open(QIODevice.WriteOnly)
                pixmap.save(buffer, "PNG")
                
                img = Image.open(BytesIO(byte_array.data()))
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                
                compressed_buffer = BytesIO()
                img.save(compressed_buffer, format='JPEG', quality=85, optimize=True)
                compressed_bytes = compressed_buffer.getvalue()
                
                self.image_data = base64.b64encode(compressed_bytes).decode('utf-8')
                
                yaml_data = load_data_yaml()
                yaml_data['image_data'] = self.image_data
                save_data_yaml(yaml_data)
                
                scaled_pixmap = pixmap.scaled(400, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.image_display.setPixmap(scaled_pixmap)
                self.image_display.setText("")
                
                self.status_label.setText("Image pasted")
                self.auto_process_image()
    
    def load_image(self, file_path):
        img = Image.open(file_path)
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=85, optimize=True)
        compressed_bytes = buffer.getvalue()
        
        self.image_data = base64.b64encode(compressed_bytes).decode('utf-8')
        
        yaml_data = load_data_yaml()
        yaml_data['image_data'] = self.image_data
        save_data_yaml(yaml_data)
        
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(400, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_display.setPixmap(scaled_pixmap)
            self.image_display.setText("")
            
            self.status_label.setText("Image loaded")
            self.auto_process_image()
    
    def clear_all(self):
        self.image_data = None
        self.image_display.clear()
        self.image_display.setText("Drag & Drop Image Here\nor CLICK to Select File")
        self.title_edit.clear()
        self.tagline_edit.clear()
        self.tags_edit.clear()
        
        yaml_data = load_data_yaml()
        yaml_data['image_data'] = None
        save_data_yaml(yaml_data)
        
        self.update_field_counts()
        self.status_label.setText("Ready")
    
    def auto_process_image(self):
        if not self.image_data:
            return
        
        api_key, service, model, endpoint = self.get_current_api_credentials()
        if not api_key:
            self.status_label.setText("API key required")
            QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
            return
        
        self.process_btn.setText("Auto Processing...")
        self.process_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_timer.start(500)
        self.status_label.setText("Auto processing with AI...")
        
        self.processor_thread = ImageProcessor(
            self.image_data,
            api_key,
            model,
            limits=self.config['limits'],
            service=service,
            endpoint=endpoint,
            max_retries=5
        )
        self.processor_thread.result_ready.connect(self.on_result_ready)
        self.processor_thread.error_occurred.connect(self.on_error_occurred)
        self.processor_thread.start()
    
    def process_image(self):
        if not self.image_data:
            QMessageBox.warning(self, "Warning", "Please load an image first.")
            return
        
        api_key, service, model, endpoint = self.get_current_api_credentials()
        if not api_key:
            QMessageBox.warning(self, "Warning", "Please select an API key.")
            return
        
        self.process_btn.setText("Processing...")
        self.process_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_timer.start(500)
        self.status_label.setText("Processing with AI...")
        
        self.processor_thread = ImageProcessor(
            self.image_data,
            api_key,
            model,
            limits=self.config['limits'],
            service=service,
            endpoint=endpoint,
            max_retries=5
        )
        self.processor_thread.result_ready.connect(self.on_result_ready)
        self.processor_thread.error_occurred.connect(self.on_error_occurred)
        self.processor_thread.start()
    
    def on_result_ready(self, result):
        self.progress_timer.stop()
        self.progress_bar.setVisible(False)
        self.process_btn.setText("Process Image")
        self.process_btn.setEnabled(True)
        _succ_q5 = QColor(theme.get_color('success'))
        _succ_rgb5 = f"{_succ_q5.red()},{_succ_q5.green()},{_succ_q5.blue()}"
        _gray_q5 = QColor(theme.get_color('gray'))
        _gray_rgb5 = f"{_gray_q5.red()},{_gray_q5.green()},{_gray_q5.blue()}"
        self.process_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba({_succ_rgb5},0.05);
                border: 2px solid {theme.get_color('success')};
                border-radius: 5px;
                padding: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba({_succ_rgb5},0.1);
            }}
            QPushButton:disabled {{
                background-color: rgba({_gray_rgb5},0.05);
                border-color: {theme.get_color('gray')};
            }}
        """)
        self.status_label.setText("Processing completed successfully!")
        
        self.title_edit.setText(result.get('title', ''))
        self.tagline_edit.setText(result.get('tagline', ''))
        
        tags = result.get('tags', [])
        self.tags_edit.setPlainText(', '.join(tags))
        
        items_count = self.items_count_spin.value()
        dpi = self.dpi_edit.text()
        width = self.width_edit.text()
        height = self.height_edit.text()
        
        description = result.get('description', '')
        features = result.get('features', [])
        
        yaml_data = load_data_yaml()
        yaml_data['ai_description'] = description
        yaml_data['ai_features'] = features
        yaml_data['results']['title'] = result.get('title', '')
        yaml_data['results']['tagline'] = result.get('tagline', '')
        yaml_data['results']['tags'] = tags
        yaml_data['results']['dpi'] = self.dpi_edit.text()
        yaml_data['results']['width'] = self.width_edit.text()
        yaml_data['results']['height'] = self.height_edit.text()
        yaml_data['items_count'] = self.items_count_spin.value()
        save_data_yaml(yaml_data)
        
        final_desc = generate_final_description(description, features, items_count, dpi, width, height)
        
        self.description_edit.blockSignals(True)
        self.description_edit.setPlainText(final_desc.strip())
        self.description_edit.blockSignals(False)
        
        QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
    
    def on_error_occurred(self, error_message):
        print(f"[ERROR] {error_message}")
        self.progress_timer.stop()
        self.progress_bar.setVisible(False)
        self.process_btn.setText("Process Image")
        self.process_btn.setEnabled(True)
        _succ_q5 = QColor(theme.get_color('success'))
        _succ_rgb5 = f"{_succ_q5.red()},{_succ_q5.green()},{_succ_q5.blue()}"
        _gray_q5 = QColor(theme.get_color('gray'))
        _gray_rgb5 = f"{_gray_q5.red()},{_gray_q5.green()},{_gray_q5.blue()}"
        self.process_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba({_succ_rgb5},0.05);
                border: 2px solid {theme.get_color('success')};
                border-radius: 5px;
                padding: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba({_succ_rgb5},0.1);
            }}
            QPushButton:disabled {{
                background-color: rgba({_gray_rgb5},0.05);
                border-color: {theme.get_color('gray')};
            }}
        """)
        self.status_label.setText("Error occurred")
        
        QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_V and event.modifiers() == Qt.ControlModifier:
            self.paste_image()
        super().keyPressEvent(event)
