from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QTextEdit
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
import qtawesome as qta
import json
import os

from ui.theme_system import theme


class GetApiKeyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API Key Required")
        self.setFixedWidth(550)
        self.setMinimumHeight(300)
        
        layout = QVBoxLayout()
        
        lang_layout = QHBoxLayout()
        lang_label = QLabel("Language:")
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("English", "en")
        self.lang_combo.addItem("Indonesia", "id")
        self.lang_combo.setFixedWidth(150)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_layout.addWidget(lang_label)
        lang_layout.addWidget(self.lang_combo)
        lang_layout.addStretch()
        layout.addLayout(lang_layout)
        
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMinimumHeight(180)
        layout.addWidget(self.info_text)
        
        btn_layout = QHBoxLayout()
        
        self.get_free_btn = QPushButton()
        self.get_free_btn.setText("Get FREE API Key")
        self.get_free_btn.setIcon(qta.icon('fa6s.gift'))
        self.get_free_btn.setMinimumHeight(36)
        self.get_free_btn.setToolTip("Get free API key from Google AI Studio")
        self.get_free_btn.clicked.connect(self._open_free_api_page)
        
        self.get_api_btn = QPushButton()
        self.get_api_btn.setObjectName("get_api_btn")
        self.get_api_btn.setText("Get API Key")
        self.get_api_btn.setIcon(qta.icon('fa6s.cart-shopping', color=theme.get_color('white')))
        self.get_api_btn.setMinimumHeight(36)
        self.get_api_btn.setStyleSheet(f"""
            QPushButton#get_api_btn {{
                background-color: {theme.get_color('primary')};
                color: {theme.get_color('white')};
                font-weight: bold;
                border-radius: 4px;
            }}
            QPushButton#get_api_btn:hover {{
                background-color: {theme.get_color('primary_hover')};
            }}
        """)
        self.get_api_btn.setToolTip("Get API key from our spreadsheet")
        self.get_api_btn.clicked.connect(self._open_get_api_page)
        
        btn_layout.addWidget(self.get_free_btn)
        btn_layout.addWidget(self.get_api_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        self._api_key_info_en = ""
        self._api_key_info_id = ""
        self._free_api_link = "https://aistudio.google.com/api-keys"
        self._get_api_link = ""
        
        self._load_config()
        self._on_language_changed(0)
    
    def _load_config(self):
        try:
            app_cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "app_config.json")
            with open(app_cfg_path, 'r', encoding='utf-8') as f:
                app_cfg = json.load(f)
                self._api_key_info_en = app_cfg.get('api_key_info_en')
                self._api_key_info_id = app_cfg.get('api_key_info_id')
                self._get_api_link = app_cfg.get('links', {}).get('get_api_key')
        except Exception as e:
            print(f"Failed to load app config: {e}")
    
    def _on_language_changed(self, index):
        lang = self.lang_combo.itemData(index)
        if lang == "en":
            self.info_text.setPlainText(self._api_key_info_en)
        elif lang == "id":
            self.info_text.setPlainText(self._api_key_info_id)
    
    def _open_free_api_page(self):
        try:
            QDesktopServices.openUrl(QUrl(self._free_api_link))
        except Exception as e:
            print(f"Failed to open free API page: {e}")
    
    def _open_get_api_page(self):
        try:
            QDesktopServices.openUrl(QUrl(self._get_api_link))
        except Exception as e:
            print(f"Failed to open get API page: {e}")
