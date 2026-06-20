from PySide6.QtCore import QThread, Signal, Qt, QPoint, QTimer, QEvent
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QProgressBar, QSizePolicy, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QMenu, QApplication, QWidget, QFileDialog, QListWidget, QListWidgetItem, QInputDialog, QPlainTextEdit, QToolTip
from PySide6.QtGui import QColor, QBrush, QAction
from database.db_operation import ImageTeaDB
from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
from config import BASE_PATH
import datetime
import qtawesome as qta
import json
import os
import csv
import re
import webbrowser
import urllib.parse
import base64

from ui.theme_system import theme

class FetchModelsThread(QThread):
    result = Signal(bool, list, str)  # success, models_list, error_message
    
    def __init__(self, api_key, endpoint):
        super().__init__()
        self.api_key = api_key
        self.endpoint = endpoint
    
    def run(self):
        try:
            from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
            success, models, error = CustomEndpointHelper.fetch_models(self.api_key, self.endpoint)
            self.result.emit(success, models, error)
        except Exception as e:
            self.result.emit(False, [], str(e))


class FetchModelsDialog(QDialog):
    model_selected = Signal(str)  # Emits selected model ID
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fetch Models")
        self.setFixedSize(450, 400)
        self.selected_model = None
        
        layout = QVBoxLayout()
        
        # Search box
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search models...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.addAction(qta.icon('fa6s.magnifying-glass'), QLineEdit.LeadingPosition)
        self.search_edit.textChanged.connect(self._filter_models)
        layout.addWidget(self.search_edit)
        
        # Models list
        self.models_list = QListWidget()
        self.models_list.itemDoubleClicked.connect(self._on_model_double_clicked)
        layout.addWidget(self.models_list)
        
        # Stats
        self.stats_widget = QWidget()
        stats_layout = QHBoxLayout(self.stats_widget)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(12)
        
        total_icon = QLabel()
        total_icon.setPixmap(qta.icon('fa6s.cubes', color=theme.get_color('text_dark')).pixmap(12, 12))
        self.total_models_lbl = QLabel('Total: 0')
        self.total_models_lbl.setStyleSheet(f"color: {theme.get_color('text_dark')};")
        
        free_icon = QLabel()
        free_icon.setPixmap(qta.icon('fa6s.gift', color=theme.get_color('primary')).pixmap(12, 12))
        self.free_models_lbl = QLabel('Free: 0')
        self.free_models_lbl.setStyleSheet(f"color: {theme.get_color('primary')}; font-weight: bold;")
        
        stats_layout.addWidget(total_icon)
        stats_layout.addWidget(self.total_models_lbl)
        stats_layout.addWidget(free_icon)
        stats_layout.addWidget(self.free_models_lbl)
        stats_layout.addStretch()
        layout.addWidget(self.stats_widget)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.select_btn = QPushButton('Select Model')
        self.select_btn.setIcon(qta.icon('fa6s.check'))
        self.select_btn.setToolTip('Select model')
        self.select_btn.clicked.connect(self._on_select_clicked)
        
        self.cancel_btn = QPushButton('Cancel')
        self.cancel_btn.setIcon(qta.icon('fa6s.xmark'))
        self.cancel_btn.setToolTip('Cancel')
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.select_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        self.models_data = []
        self.fetch_thread = None
    
    def fetch_models(self, api_key, endpoint):
        """Start fetching models from endpoint"""
        self.progress_bar.setVisible(True)
        self.models_list.clear()
        self.select_btn.setEnabled(False)
        
        self.fetch_thread = FetchModelsThread(api_key, endpoint)
        self.fetch_thread.result.connect(self._on_fetch_result)
        self.fetch_thread.finished.connect(lambda: self.progress_bar.setVisible(False))
        self.fetch_thread.start()
    
    def _on_fetch_result(self, success, models, error):
        """Handle fetch result"""
        self.progress_bar.setVisible(False)
        
        if not success:
            QMessageBox.warning(self, "Fetch Models", f"Failed to fetch models:\n{error}")
            self.reject()
            return
        
        if not models:
            QMessageBox.information(self, "Fetch Models", "No models found at this endpoint.")
            self.reject()
            return
        
        self.models_data = models
        self._populate_models()
        self.select_btn.setEnabled(True)
    
    def _populate_models(self):
        """Populate list with models"""
        self.models_list.clear()
        
        total_models = len(self.models_data)
        free_models = sum(1 for model in self.models_data if model.get('free', False))
        self.total_models_lbl.setText(f'Total: {total_models}')
        self.free_models_lbl.setText(f'Free: {free_models}')
        
        for model in self.models_data:
            item = QListWidgetItem(model['id'])
            
            # Style free models with primary color
            model_text_lower = str(model.get('id', '')).lower()
            is_free_model = model.get('free', False) or ('free' in model_text_lower)
            if is_free_model:
                primary_color = QColor(theme.get_color('primary'))
                item.setForeground(QBrush(primary_color))
            
            item.setData(Qt.UserRole, model['id'])
            self.models_list.addItem(item)
        
        if self.models_list.count() > 0:
            self.models_list.setCurrentRow(0)
    
    def _filter_models(self, text):
        """Filter models based on search text"""
        search_text = text.lower().strip()
        
        for i in range(self.models_list.count()):
            item = self.models_list.item(i)
            if not search_text:
                item.setHidden(False)
            else:
                item.setHidden(search_text not in item.text().lower())
    
    def _on_model_double_clicked(self, item):
        """Handle double-click on model"""
        self.selected_model = item.data(Qt.UserRole)
        self.accept()
    
    def _on_select_clicked(self):
        """Handle select button click"""
        current_item = self.models_list.currentItem()
        if current_item:
            self.selected_model = current_item.data(Qt.UserRole)
            self.accept()
        else:
            QMessageBox.warning(self, "Select Model", "Please select a model from the list.")
    
    def get_selected_model(self):
        """Return selected model ID"""
        return self.selected_model


class ApiKeyTestThread(QThread):
    result = Signal(str, str, object)
    def __init__(self, api_key, service=None, model=None, provider_endpoint=None):
        super().__init__()
        self.api_key = api_key
        self.service = service
        self.model = model
        self.provider_endpoint = provider_endpoint
    def run(self):
        if getattr(self, 'provider_endpoint', None):
            try:
                from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
                ok, msg = CustomEndpointHelper.test_connectivity(self.api_key, self.provider_endpoint, self.service, self.model)
                if ok:
                    self.result.emit('success', self.service, msg)
                else:
                    self.result.emit('fail', self.service, msg)
                return
            except Exception as e:
                print(f"Custom endpoint test error: {e}")
                try:
                    err_text = str(e)
                except Exception:
                    err_text = "<failed to stringify error>"
                self.result.emit('fail', self.service, err_text)
                return
        if self.service == 'gemini' or self.service is None:
            try:
                from google import genai
                client = genai.Client(api_key=self.api_key)
                if not self.model:
                    raise RuntimeError("No model selected for Gemini API key test.")
                response = client.models.generate_content(
                    model=self.model,
                    contents="Just say OK."
                )
                if hasattr(response, 'text') and response.text:
                    self.result.emit('success', 'gemini', 'OK')
                    return
            except Exception as e:
                print(f"Gemini API Key test error: {e}")
                if self.service == 'gemini':
                    try:
                        err_text = str(e)
                    except Exception:
                        err_text = "<failed to stringify error>"
                    self.result.emit('fail', 'gemini', err_text)
                    return
        if self.service == 'openai' or self.service == 'openrouter' or self.service is None:
            try:
                from openai import OpenAI
                if self.service == 'openrouter' or re.match(r"^sk-?or-", self.api_key, re.IGNORECASE):
                    try:
                        cfg_path = os.path.join(BASE_PATH, 'configs', 'ai_config.json')
                        with open(cfg_path, 'r', encoding='utf-8') as f:
                            cfg = json.load(f)
                        base_url = cfg.get('provider_endpoints', {}).get('openrouter') or "https://openrouter.ai/api/v1"
                    except Exception:
                        base_url = "https://openrouter.ai/api/v1"
                    client = OpenAI(api_key=self.api_key, base_url=base_url)
                    detected_service = 'openrouter'
                else:
                    client = OpenAI(api_key=self.api_key)
                    detected_service = 'openai'
                if not self.model:
                    raise RuntimeError("No model selected for OpenAI/OpenRouter API key test.")
                response = client.responses.create(
                    model=self.model,
                    input="Just say OK."
                )
                if response:
                    self.result.emit('success', detected_service, 'OK')
                    return
            except Exception as e:
                print(f"OpenAI/OpenRouter API Key test error: {e}")
                try:
                    err_text = str(e)
                except Exception:
                    err_text = "<failed to stringify error>"
                detected_service = 'openrouter' if (self.service == 'openrouter' or re.match(r"^sk-?or-", self.api_key, re.IGNORECASE)) else 'openai'
                self.result.emit('fail', detected_service, err_text)
                return
        if self.service == 'groq' or self.service is None:
            try:
                from groq import Groq
                client = Groq(api_key=self.api_key)
                if not self.model:
                    raise RuntimeError("No model selected for Groq API key test.")
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": [{"type": "text", "text": "Just say OK."}]}]
                )
                if response and hasattr(response, 'choices') and response.choices:
                    self.result.emit('success', 'groq', 'OK')
                    return
            except Exception as e:
                print(f"Groq API Key test error: {e}")
                if self.service == 'groq':
                    try:
                        err_text = str(e)
                    except Exception:
                        err_text = "<failed to stringify error>"
                    self.result.emit('fail', 'groq', err_text)
                    return
        if self.service == 'blackbox' or self.service is None:
            try:
                from openai import OpenAI
                try:
                    cfg_path = os.path.join(BASE_PATH, 'configs', 'ai_config.json')
                    with open(cfg_path, 'r', encoding='utf-8') as f:
                        cfg = json.load(f)
                    base_url = cfg.get('provider_endpoints', {}).get('blackbox') or "https://api.blackbox.ai"
                except Exception:
                    base_url = "https://api.blackbox.ai"
                client = OpenAI(api_key=self.api_key, base_url=base_url)
                if not self.model:
                    raise RuntimeError("No model selected for Blackbox API key test.")
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": "Just say OK."}]
                )
                if response and hasattr(response, 'choices') and response.choices:
                    self.result.emit('success', 'blackbox', 'OK')
                    return
            except Exception as e:
                print(f"Blackbox API Key test error: {e}")
                if self.service == 'blackbox':
                    try:
                        err_text = str(e)
                    except Exception:
                        err_text = "<failed to stringify error>"
                    self.result.emit('fail', 'blackbox', err_text)
                    return
        if self.service == 'maia' or self.service is None:
            try:
                from openai import OpenAI
                try:
                    cfg_path = os.path.join(BASE_PATH, 'configs', 'ai_config.json')
                    with open(cfg_path, 'r', encoding='utf-8') as f:
                        cfg = json.load(f)
                    base_url = cfg.get('provider_endpoints', {}).get('maia') or "https://api.maiarouter.ai/v1"
                except Exception:
                    base_url = "https://api.maiarouter.ai/v1"
                client = OpenAI(api_key=self.api_key, base_url=base_url)
                if not self.model:
                    raise RuntimeError("No model selected for Maia Router API key test.")
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": "Just say OK."}]
                )
                if response and hasattr(response, 'choices') and response.choices:
                    self.result.emit('success', 'maia', 'OK')
                    return
            except Exception as e:
                print(f"Maia Router API Key test error: {e}")
                if self.service == 'maia':
                    try:
                        err_text = str(e)
                    except Exception:
                        err_text = "<failed to stringify error>"
                    self.result.emit('fail', 'maia', err_text)
                    return
        self.result.emit('fail', None, None)


class ModelManagerDialog(QDialog):
    def __init__(self, model_list: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Model Manager")
        self.setFixedWidth(550)
        self.model_list = {k: list(v) for k, v in (model_list or {}).items()}
        layout = QVBoxLayout()
        model_hint = QLabel("Manage the list of models for each service. This is used to populate the model dropdown when adding API keys. Changes here will affect the model selection for all API keys using that service.")
        model_hint.setWordWrap(True)
        model_hint.setStyleSheet(f"font-size:10px; color: {theme.get_color('text_dark')};")
        layout.addWidget(model_hint)
        top_layout = QHBoxLayout()
        self.service_list = QListWidget()
        self.service_list.setFixedWidth(140)
        
        if isinstance(self.model_list, dict) and 'custom' not in self.model_list:
            self.model_list.setdefault('custom', [])

        services = sorted(self.model_list.keys()) if isinstance(self.model_list, dict) else []
        if not services:
            services = ['gemini', 'openai', 'custom']
            for s in services:
                self.model_list.setdefault(s, [])
        self.service_list.addItems([s.capitalize() for s in services])
        self.service_list.currentItemChanged.connect(self._on_service_selected)
        top_layout.addWidget(self.service_list)

        right_layout = QVBoxLayout()
        self.models_list = QListWidget()
        right_layout.addWidget(self.models_list)

        btns_layout = QHBoxLayout()
        self.add_btn = QPushButton()
        self.add_btn.setIcon(qta.icon('fa6s.plus'))
        self.add_btn.setToolTip('Add model')
        self.add_btn.clicked.connect(self._add_model)
        self.edit_btn = QPushButton()
        self.edit_btn.setIcon(qta.icon('fa6s.pen'))
        self.edit_btn.setToolTip('Edit selected model')
        self.edit_btn.clicked.connect(self._edit_model)
        self.delete_btn = QPushButton()
        self.delete_btn.setIcon(qta.icon('fa6s.trash'))
        self.delete_btn.setToolTip('Delete selected model')
        self.delete_btn.clicked.connect(self._delete_model)
        self.up_btn = QPushButton()
        self.up_btn.setIcon(qta.icon('fa6s.arrow-up'))
        self.up_btn.setToolTip('Move up')
        self.up_btn.clicked.connect(self._move_up)
        self.down_btn = QPushButton()
        self.down_btn.setIcon(qta.icon('fa6s.arrow-down'))
        self.down_btn.setToolTip('Move down')
        self.down_btn.clicked.connect(self._move_down)
        btns_layout.addWidget(self.add_btn)
        btns_layout.addWidget(self.edit_btn)
        btns_layout.addWidget(self.delete_btn)
        btns_layout.addWidget(self.up_btn)
        btns_layout.addWidget(self.down_btn)
        right_layout.addLayout(btns_layout)

        top_layout.addLayout(right_layout)
        layout.addLayout(top_layout)

        bottom_layout = QHBoxLayout()
        self.save_btn = QPushButton('Save')
        self.save_btn.setIcon(qta.icon('fa6s.floppy-disk'))
        self.save_btn.clicked.connect(self._save_and_close)
        self.close_btn = QPushButton('Close')
        self.close_btn.setIcon(qta.icon('fa6s.xmark'))
        self.close_btn.clicked.connect(self.reject)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.save_btn)
        bottom_layout.addWidget(self.close_btn)
        layout.addLayout(bottom_layout)

        self.setLayout(layout)
        
        if self.service_list.count() > 0:
            self.service_list.setCurrentRow(0)

    def _on_service_selected(self, current, previous):
        if not current:
            return
        service = current.text().lower()
        self._load_models_for(service)

    def _load_models_for(self, service):
        self.models_list.clear()
        models = self.model_list.get(service, [])
        for m in models:
            self.models_list.addItem(QListWidgetItem(m))

    def _get_text_with_custom_buttons(self, title, label_text, text=''):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setMinimumWidth(360)
        vbox = QVBoxLayout()
        lbl = QLabel(label_text)
        vbox.addWidget(lbl)
        edit = QLineEdit()
        edit.setText(text or '')
        edit.selectAll()
        edit.setMinimumWidth(240)
        edit_h = QHBoxLayout()
        edit_h.addWidget(edit)
        btn_paste = QPushButton()
        btn_paste.setIcon(qta.icon('fa6s.paste'))
        btn_paste.setToolTip('Paste from clipboard')
        btn_paste.setFocusPolicy(Qt.NoFocus)
        btn_paste.setFixedWidth(32)
        def _do_paste():
            try:
                edit.setText(QApplication.clipboard().text())
                edit.setFocus()
                edit.selectAll()
            except Exception as e:
                print(f"[ModelManager] Paste failed: {e}")
        btn_paste.clicked.connect(_do_paste)
        edit_h.addWidget(btn_paste)
        vbox.addLayout(edit_h)
        hbox = QHBoxLayout()
        hbox.addStretch()
        btn_save = QPushButton("Save")
        btn_save.setIcon(qta.icon('fa6s.floppy-disk'))
        btn_save.clicked.connect(dlg.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setIcon(qta.icon('fa6s.xmark'))
        btn_cancel.clicked.connect(dlg.reject)
        hbox.addWidget(btn_save)
        hbox.addWidget(btn_cancel)
        vbox.addLayout(hbox)
        dlg.setLayout(vbox)
        result = dlg.exec()
        return edit.text(), bool(result)

    def _add_model(self):
        service_item = self.service_list.currentItem()
        if not service_item:
            return
        service = self.normalize_service_key(service_item.text())
        name, ok = self._get_text_with_custom_buttons('Add Model', 'Model name:')
        if ok and name:
            name = name.strip()
            self.model_list.setdefault(service, [])
            if name in self.model_list[service]:
                QMessageBox.warning(self, 'Add Model', 'Model already exists for this service.')
                return
            self.model_list[service].append(name)
            self.models_list.addItem(QListWidgetItem(name))

    def _edit_model(self):
        service_item = self.service_list.currentItem()
        sel = self.models_list.currentItem()
        if not service_item or not sel:
            return
        service = self.normalize_service_key(service_item.text())
        old = sel.text()
        name, ok = self._get_text_with_custom_buttons('Edit Model', 'Model name:', text=old)
        if ok and name:
            name = name.strip()
            idx = self.models_list.row(sel)
            self.model_list[service][idx] = name
            sel.setText(name)

    def _delete_model(self):
        service_item = self.service_list.currentItem()
        sel = self.models_list.currentItem()
        if not service_item or not sel:
            return
        service = self.normalize_service_key(service_item.text())
        mb = QMessageBox(self)
        mb.setWindowTitle("Delete Model")
        mb.setText(f"Delete model '{sel.text()}' for '{service}'?")
        mb.setIcon(QMessageBox.Warning)
        btn_yes = QPushButton("Delete")
        btn_yes.setIcon(qta.icon('fa6s.trash'))
        btn_no = QPushButton("Cancel")
        btn_no.setIcon(qta.icon('fa6s.xmark'))
        mb.addButton(btn_yes, QMessageBox.AcceptRole)
        mb.addButton(btn_no, QMessageBox.RejectRole)
        mb.setDefaultButton(btn_no)
        mb.exec()
        if mb.clickedButton() == btn_yes:
            idx = self.models_list.row(sel)
            self.models_list.takeItem(idx)
            try:
                self.model_list[service].pop(idx)
            except Exception as e:
                print(f"[ModelManager] Error removing model at index {idx} for service {service}: {e}")

    def _move_up(self):
        sel = self.models_list.currentItem()
        service_item = self.service_list.currentItem()
        if not sel or not service_item:
            return
        service = self.normalize_service_key(service_item.text())
        idx = self.models_list.row(sel)
        if idx <= 0:
            return
        self.model_list[service][idx-1], self.model_list[service][idx] = self.model_list[service][idx], self.model_list[service][idx-1]
        self._load_models_for(service)
        self.models_list.setCurrentRow(idx-1)

    def _move_down(self):
        sel = self.models_list.currentItem()
        service_item = self.service_list.currentItem()
        if not sel or not service_item:
            return
        service = self.normalize_service_key(service_item.text())
        idx = self.models_list.row(sel)
        if idx < 0 or idx >= len(self.model_list.get(service, [])) - 1:
            return
        self.model_list[service][idx+1], self.model_list[service][idx] = self.model_list[service][idx], self.model_list[service][idx+1]
        self._load_models_for(service)
        self.models_list.setCurrentRow(idx+1)

    def _save_and_close(self):
        
        cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "ai_config.json")
        try:
            with open(cfg_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
        cfg['model_list'] = AddApiKeyDialog.normalize_model_list(self.model_list)
        try:
            with open(cfg_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(self, 'Save Models', f'Failed to save model list: {e}')
            return
        self.accept()

class AddApiKeyDialog(QDialog):
    # Central mapping for services: display_name -> internal_key
    SERVICE_MAP = {
        'Gemini': 'gemini',
        'OpenAI': 'openai',
        'OpenRouter': 'openrouter',
        'Groq': 'groq',
        'Blackbox': 'blackbox',
        'Maia': 'maia',
        'Custom Endpoint': 'custom'
    }
    
    # Central mapping for endpoints: display_name -> url
    ENDPOINT_MAP = {
        'Desainia API': 'https://api.desainia.my.id/v1',
        'OpenRouter Custom': 'https://openrouter.ai/api/v1',
        'Groq Custom': 'https://api.groq.com/openai/v1',
        'Together AI': 'https://api.together.xyz/v1',
        'Mistral AI': 'https://api.mistral.ai/v1',
        'Cohere': 'https://api.cohere.com/v2',
        'Perplexity': 'https://api.perplexity.ai',
        'Fireworks AI': 'https://api.fireworks.ai/inference/v1',
        'Anthropic': 'https://api.anthropic.com/v1/messages',
        'Ollama Local': 'http://localhost:11434/v1',
        'KoboiLLM': 'https://api.koboillm.com/v1'
    }

    SERVICE_ALIASES = {
        'custom endpoint': 'custom',
        'custom': 'custom'
    }

    @classmethod
    def normalize_service_key(cls, service):
        service_text = (service or '').strip().lower()
        if not service_text:
            return ''
        if service_text in cls.SERVICE_ALIASES:
            return cls.SERVICE_ALIASES[service_text]
        if service_text in cls.SERVICE_MAP.values():
            return service_text
        normalized_display_map = {display.lower(): key for display, key in cls.SERVICE_MAP.items()}
        return normalized_display_map.get(service_text, service_text)

    @classmethod
    def get_service_display_name(cls, service):
        service_key = cls.normalize_service_key(service)
        reverse_service_map = {v: k for k, v in cls.SERVICE_MAP.items()}
        return reverse_service_map.get(service_key, str(service))

    @classmethod
    def normalize_model_list(cls, model_list):
        normalized_model_list = {}
        if not isinstance(model_list, dict):
            normalized_model_list['custom'] = []
            return normalized_model_list

        for raw_service, models in model_list.items():
            service_key = cls.normalize_service_key(raw_service)
            if not service_key:
                continue
            normalized_model_list.setdefault(service_key, [])
            for model in (models or []):
                if model and model not in normalized_model_list[service_key]:
                    normalized_model_list[service_key].append(model)

        normalized_model_list.setdefault('custom', [])
        return normalized_model_list
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API Key Manager")
        self.setFixedWidth(620)
        self.db = ImageTeaDB()
        self._label_icon_color = theme.get_color('text_dark')
        layout = QVBoxLayout()
        label_width = 80
        self.model_list = {}
        ai_prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "ai_config.json")
        try:
            with open(ai_prompt_path, "r", encoding="utf-8") as f:
                ai_prompt = json.load(f)
                self.model_list = self.normalize_model_list(ai_prompt.get("model_list", {}))
        except Exception as e:
            print(f"Failed to load model list: {e}")
            self.model_list = {}
        try:
            self.model_list = self.normalize_model_list(self.model_list)
        except Exception:
            self.model_list = {'custom': []}
        service_layout = QHBoxLayout()
        _service_label_widget, service_label = self._create_icon_label_widget("Service:", 'fa6s.gears', label_width)
        service_label.setToolTip("Select the service/model for this API key")
        self.service_combo = QComboBox()
        # Populate service combo with userData
        for display_name, service_key in self.SERVICE_MAP.items():
            self.service_combo.addItem(display_name, service_key)
        self.service_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.service_combo.setToolTip("Select the service/model for this API key")
        service_layout.addWidget(_service_label_widget)
        service_layout.addWidget(self.service_combo)
        layout.addLayout(service_layout)
        model_layout = QHBoxLayout()
        _model_label_widget, model_label = self._create_icon_label_widget("Model:", 'fa6s.brain', label_width)
        model_label.setToolTip("Select the model for this API key")
        self.model_combo = QComboBox()
        self.model_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.model_combo.setToolTip("Select the model for this API key")
        self.model_paste_btn = QPushButton()
        self.model_paste_btn.setIcon(qta.icon('fa6s.paste'))
        self.model_paste_btn.setFixedWidth(32)
        self.model_paste_btn.setToolTip('Paste model from clipboard')
        self.model_paste_btn.setFocusPolicy(Qt.NoFocus)
        self.model_paste_btn.clicked.connect(self._on_model_paste_clicked)
        self.fetch_models_btn = QPushButton()
        self.fetch_models_btn.setIcon(qta.icon('fa6s.download'))
        self.fetch_models_btn.setFixedWidth(32)
        self.fetch_models_btn.setToolTip('Fetch models from custom endpoint')
        self.fetch_models_btn.setFocusPolicy(Qt.NoFocus)
        self.fetch_models_btn.clicked.connect(self._on_fetch_models_clicked)
        self.fetch_models_btn.setVisible(False)  # Hidden by default, shown only for custom endpoint
        self.add_model_btn = QPushButton()
        self.add_model_btn.setIcon(qta.icon('fa6s.plus'))
        self.add_model_btn.setFixedWidth(32)
        self.add_model_btn.setToolTip('Save current model to list')
        self.add_model_btn.setFocusPolicy(Qt.NoFocus)
        self.add_model_btn.clicked.connect(self._on_add_model_clicked)
        self.model_manager_btn = QPushButton()
        self.model_manager_btn.setIcon(qta.icon('fa6s.gears'))
        self.model_manager_btn.setFixedWidth(32)
        self.model_manager_btn.setToolTip('Manage models')
        self.model_manager_btn.setFocusPolicy(Qt.NoFocus)
        self.model_manager_btn.clicked.connect(self._open_model_manager)
        model_layout.addWidget(_model_label_widget)
        model_layout.addWidget(self.model_combo)
        model_layout.addWidget(self.model_paste_btn)
        model_layout.addWidget(self.fetch_models_btn)
        model_layout.addWidget(self.add_model_btn)
        model_layout.addWidget(self.model_manager_btn)
        layout.addLayout(model_layout)
        self.model_combo.installEventFilter(self)
        self._refresh_model_combo()
        key_layout = QHBoxLayout()
        _key_label_widget, self.key_label = self._create_icon_label_widget("API Key:", 'fa6s.key', label_width)
        self.key_label.setToolTip("Enter your API key here")
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("Enter API Key")
        self.key_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.key_edit.setToolTip("Enter your API key here")
        self.key_edit.setEchoMode(QLineEdit.Password)
        self._api_key_visible = False

        self.paste_btn = QPushButton()
        self.paste_btn.setIcon(qta.icon('fa6s.paste'))
        self.paste_btn.setFixedWidth(32)
        self.paste_btn.setToolTip("Paste from clipboard")
        self.paste_btn.setFocusPolicy(Qt.NoFocus)
        self.paste_btn.clicked.connect(self._on_paste_clicked)

        self.eye_btn = QPushButton()
        self.eye_btn.setIcon(qta.icon('fa6s.eye-slash'))
        self.eye_btn.setFixedWidth(32)
        self.eye_btn.setToolTip("Warning: revealing API key may expose it to others")
        self.eye_btn.setFocusPolicy(Qt.NoFocus)
        self.eye_btn.clicked.connect(self._on_eye_clicked)

        key_layout.addWidget(_key_label_widget)
        key_layout.addWidget(self.key_edit)
        key_layout.addWidget(self.paste_btn)
        key_layout.addWidget(self.eye_btn)
        layout.addLayout(key_layout)

        note_layout = QHBoxLayout()
        _note_label_widget, note_label = self._create_icon_label_widget("Note:", 'fa6s.clipboard', label_width)
        note_label.setToolTip("Optional note for this API key")
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("Optional note")
        self.note_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.note_edit.setToolTip("Optional note for this API key")
        note_layout.addWidget(_note_label_widget)
        note_layout.addWidget(self.note_edit)
        layout.addLayout(note_layout)

        endpoint_layout = QHBoxLayout()
        _endpoint_label_widget, endpoint_label = self._create_icon_label_widget("Endpoint:", 'fa6s.link', label_width)
        endpoint_label.setToolTip("Custom endpoint URL - supports both formats:\n• https://api.example.com/v1 (auto-adds /chat/completions)\n• https://api.example.com/v1/chat/completions (full path)")
        self.endpoint_edit = QComboBox()
        self.endpoint_edit.setEditable(True)
        self.endpoint_edit.addItem("", "")
        # Populate endpoint combo with userData
        for display_name, url in self.ENDPOINT_MAP.items():
            self.endpoint_edit.addItem(display_name, url)
        self.endpoint_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.endpoint_edit.setToolTip("Supports both formats:\n• Short: https://api.example.com/v1\n• Full: https://api.example.com/v1/chat/completions\nSystem will auto-complete if needed")
        self.endpoint_edit.currentIndexChanged.connect(self._on_endpoint_combo_changed)
        endpoint_layout.addWidget(_endpoint_label_widget)
        endpoint_layout.addWidget(self.endpoint_edit)
        self.endpoint_paste_btn = QPushButton()
        self.endpoint_paste_btn.setIcon(qta.icon('fa6s.paste'))
        self.endpoint_paste_btn.setFixedWidth(32)
        self.endpoint_paste_btn.setToolTip("Paste endpoint from clipboard")
        self.endpoint_paste_btn.setFocusPolicy(Qt.NoFocus)
        self.endpoint_paste_btn.clicked.connect(self._on_endpoint_paste)
        endpoint_layout.addWidget(self.endpoint_paste_btn)
        layout.addLayout(endpoint_layout)

        csv_btn_layout_top = QHBoxLayout()
        self.test_all_btn = QPushButton()
        self.test_all_btn.setObjectName('test_all_btn')
        self.test_all_btn.setText("Test All")
        self.test_all_btn.setIcon(qta.icon('fa6s.list-check', color=theme.get_color('white')))
        self.test_all_btn.setIconSize(self.test_all_btn.iconSize())
        self.test_all_btn.setToolTip("Test all API keys sequentially")
        self.test_all_btn.setStyleSheet(f"""
            QPushButton#test_all_btn {{
                background-color: {theme.get_color('primary')};
                color: {theme.get_color('white')};
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 12px;
            }}
            QPushButton#test_all_btn:hover {{
                background-color: {theme.get_color('primary_hover')};
            }}
        """)
        self.sort_combo = QComboBox()
        self.sort_combo.setToolTip("Filter / Sort API table")
        try:
            rows = self.db.get_all_api_keys()
            services = sorted({(r[0] if not isinstance(r, dict) else r.get('service')) for r in rows if r and (r[0] if not isinstance(r, dict) else r.get('service'))})
        except Exception as e:
            print(f"Error fetching services for sort combo: {e}")
            services = []
        sort_items = ["All"]
        # Create reverse map: internal_key -> display_name
        for s in services:
            try:
                svc_display = self.get_service_display_name(s)
                sort_items.append(f"Service: {svc_display}")
            except Exception:
                sort_items.append(f"Service: {s}")
        sort_items += [
            "Status: Active",
            "Status: Invalid",
            "Last Tested (Newest)",
            "Last Tested (Oldest)",
            "API (A-Z)",
            "API (Z-A)",
            "Model (A-Z)",
            "Model (Z-A)"
        ]
        self.sort_combo.addItems(sort_items)
        self.sort_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.sort_combo.setFixedWidth(140)
        self.sort_combo.currentIndexChanged.connect(self._refresh_api_table)
        self.refresh_btn = QPushButton()
        self.refresh_btn.setIcon(qta.icon('fa6s.rotate'))
        self.refresh_btn.setToolTip("Refresh table")
        self.refresh_btn.setFixedWidth(32)
        self.refresh_btn.clicked.connect(self._refresh_api_table)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search table...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.addAction(qta.icon('fa6s.magnifying-glass'), QLineEdit.LeadingPosition)
        self.search_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.search_edit.textChanged.connect(self._apply_table_search)
        csv_btn_layout_bottom = QHBoxLayout()
        self.export_csv_btn = QPushButton()
        self.export_csv_btn.setText("Backup Keys")
        self.export_csv_btn.setIcon(qta.icon('fa6s.file-csv'))
        self.export_csv_btn.setIconSize(self.export_csv_btn.iconSize())
        self.export_csv_btn.setToolTip("Backup API key list to CSV")
        self.import_csv_btn = QPushButton()
        self.import_csv_btn.setText("Import Keys")
        self.import_csv_btn.setIcon(qta.icon('fa6s.file-import'))
        self.import_csv_btn.setIconSize(self.import_csv_btn.iconSize())
        self.import_csv_btn.setToolTip("Import API key list from CSV")
        self.delete_selected_btn = QPushButton()
        self.delete_selected_btn.setText("Delete Selected")
        self.delete_selected_btn.setIcon(qta.icon('fa6s.trash'))
        self.delete_selected_btn.setToolTip("Delete the selected API key")
        self.delete_selected_btn.setFixedWidth(120)
        self.delete_selected_btn.clicked.connect(self._delete_selected_api_key)
        self.delete_all_btn = QPushButton()
        self.delete_all_btn.setText("Delete All")
        self.delete_all_btn.setIcon(qta.icon('fa6s.trash'))
        self.delete_all_btn.setToolTip("Delete all API keys (cannot be undone)")
        self.delete_all_btn.setFixedWidth(100)
        self.delete_all_btn.clicked.connect(self._delete_all_api_keys)
        csv_btn_layout_bottom.addWidget(self.export_csv_btn)
        csv_btn_layout_bottom.addWidget(self.import_csv_btn)
        csv_btn_layout_bottom.addWidget(self.delete_selected_btn)
        csv_btn_layout_bottom.addWidget(self.delete_all_btn)
        csv_btn_layout_bottom.addStretch()
        layout.addLayout(csv_btn_layout_bottom)

        csv_btn_layout_top.addWidget(self.test_all_btn)
        self.topup_btn = QPushButton()
        self.topup_btn.setObjectName('topup_btn')
        self.topup_btn.setText("Top Up API Key")
        self.topup_btn.setIcon(qta.icon('fa6s.coins', color=theme.get_color('white')))
        self.topup_btn.setIconSize(self.topup_btn.iconSize())
        self.topup_btn.setToolTip("Top up Desainia API key balance")
        self.topup_btn.setStyleSheet(f"""
            QPushButton#topup_btn {{
                background-color: {theme.get_color('primary')};
                color: {theme.get_color('white')};
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 12px;
            }}
            QPushButton#topup_btn:hover {{
                background-color: {theme.get_color('primary_hover')};
            }}
        """)
        self.topup_btn.clicked.connect(self._open_topup_dialog)
        csv_btn_layout_top.addWidget(self.topup_btn)
        self.new_btn = QPushButton()
        self.new_btn.setText("New")
        self.new_btn.setIcon(qta.icon('fa6s.file-circle-plus', color=theme.get_color('primary')))
        self.new_btn.setIconSize(self.new_btn.iconSize())
        self.new_btn.setToolTip("Reset entry to blank (first launch)")
        self.new_btn.setMinimumHeight(self.test_all_btn.minimumHeight())
        self.new_btn.clicked.connect(self._reset_entry_form)
        csv_btn_layout_top.addWidget(self.new_btn)
        csv_btn_layout_top.addWidget(self.sort_combo)
        csv_btn_layout_top.addWidget(self.refresh_btn)
        csv_btn_layout_top.addWidget(self.search_edit, 1)
        csv_btn_layout_top.addStretch()
        layout.addLayout(csv_btn_layout_top)
        self.api_table = QTableWidget()
        self.api_table.setColumnCount(7)
        self.api_table.setHorizontalHeaderLabels(["Service", "API", "Endpoint", "Last Tested", "Model", "Note", "Actions"])
        self.api_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        header = self.api_table.horizontalHeader()
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.api_table.setColumnWidth(6, 100)
        self.api_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.api_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.api_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.api_table.setMinimumHeight(200)
        self.api_table.setToolTip("List of all API keys you have added")
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        self.api_table.setSortingEnabled(True)
        layout.addWidget(self.api_table, 1)
        self._row_testing = None
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink_row)
        self._blink_state = False
        self.stats_widget = QWidget()
        stats_layout = QHBoxLayout(self.stats_widget)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(12)
        icon_size = 12
        def _add_stat(icon_name, initial_text, color_key='text_dark'):
            icon_lbl = QLabel()
            color = theme.get_color(color_key)
            icon = qta.icon(icon_name, color=color)
            pix = icon.pixmap(icon_size, icon_size)
            icon_lbl.setPixmap(pix)
            text_lbl = QLabel(initial_text)
            text_lbl.setStyleSheet(f"color: {color};")
            stats_layout.addWidget(icon_lbl)
            stats_layout.addWidget(text_lbl)
            return text_lbl
        self.stats_models_lbl = _add_stat('fa6s.cubes', 'Models: 0', 'primary')
        self.stats_apis_lbl = _add_stat('fa6s.server', 'APIs: 0', 'warning')
        self.stats_valid_lbl = _add_stat('fa6s.check', 'Valid: 0', 'success')
        self.stats_invalid_lbl = _add_stat('fa6s.xmark', 'Invalid: 0', 'error')
        self.stats_last_tested_lbl = _add_stat('fa6s.clock', 'Last Tested: Never', 'text_dark')
        stats_layout.addStretch()
        self.stats_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.stats_widget.setFixedHeight(28)
        layout.addWidget(self.stats_widget, 0)
        self._refresh_api_table()
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.progress_bar.setToolTip("Shows progress when testing API key")
        layout.addWidget(self.progress_bar)
        btn_layout = QHBoxLayout()
        self.test_and_save_btn = QPushButton()
        self.test_and_save_btn.setText("Test and Save")
        self.test_and_save_btn.setIcon(qta.icon('fa6s.play', color=theme.get_color('primary')))
        self.test_and_save_btn.setIconSize(self.test_and_save_btn.iconSize())
        self.test_and_save_btn.setMinimumHeight(32)
        self.test_and_save_btn.setToolTip("Test the API key and save it if valid")
        self.get_api_key_btn = QPushButton()
        self.get_api_key_btn.setObjectName("get_api_key_btn")
        self.get_api_key_btn.setText("Get API Key")
        self.get_api_key_btn.setIcon(qta.icon('fa6s.cart-shopping', color=theme.get_color('white')))
        self.get_api_key_btn.setIconSize(self.get_api_key_btn.iconSize())
        self.get_api_key_btn.setMinimumHeight(32)
        self.get_api_key_btn.setStyleSheet(f"""
            QPushButton#get_api_key_btn {{
                background-color: {theme.get_color('primary')};
                color: {theme.get_color('white')};
                font-weight: bold;
                border-radius: 4px;
            }}
            QPushButton#get_api_key_btn:hover {{
                background-color: {theme.get_color('primary_hover')};
            }}
        """)
        self.get_api_key_btn.setToolTip("Open API key purchase page")
        self.get_api_key_btn.clicked.connect(self._open_buy_api_key_page)
        self.close_btn = QPushButton()
        self.close_btn.setText("Close")
        self.close_btn.setIcon(qta.icon('fa6s.xmark'))
        self.close_btn.setIconSize(self.close_btn.iconSize())
        self.close_btn.setMinimumHeight(32)
        self.close_btn.setToolTip("Close this dialog")
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.test_and_save_btn)
        btn_layout.addWidget(self.close_btn)
        btn_layout.addWidget(self.get_api_key_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        self.test_and_save_btn.clicked.connect(self.test_and_save_api_key)
        self.export_csv_btn.clicked.connect(self.export_api_keys_csv)
        self.import_csv_btn.clicked.connect(self.import_api_keys_csv)
        self.test_all_btn.clicked.connect(self.test_all_api_keys)
        self.key_edit.textChanged.connect(self._on_key_edit_changed)
        self.service_combo.currentIndexChanged.connect(self._on_service_combo_changed)
        self.api_table.cellClicked.connect(self._on_api_table_row_clicked)
        self.api_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.api_table.customContextMenuRequested.connect(self._show_context_menu)
        self.model_combo.currentIndexChanged.connect(self._on_model_combo_changed)
        self._detected_service = None
        self._api_key_valid = False
        self._testing = False
        self._test_all_running = False
        self._test_all_results = []
        self._test_all_row_blinking = False
        self._service_manually_selected = False
        self._model_manually_selected = False
        try:
            self._load_app_links()
        except Exception as e:
            print(f"Failed to load app links in AddApiKeyDialog: {e}")
            self._whatsapp_link = None
            self._get_api_key_link = None
        self._reset_entry_form_initial_values = {
            'service': 'Gemini',
            'model': '',
            'api_key': '',
            'note': '',
            'endpoint': ''
        }
        self._update_endpoint_state()

    def closeEvent(self, event):
        self._blink_timer.stop()
        for attr in ('_test_thread', '_test_thread_row', '_test_all_thread'):
            t = getattr(self, attr, None)
            if t is not None and t.isRunning():
                t.blockSignals(True)
                t.quit()
                t.wait(2000)
        super().closeEvent(event)

    def _reset_entry_form(self):
        self.service_combo.setCurrentText(self._reset_entry_form_initial_values['service'])
        self._service_manually_selected = False
        self._model_manually_selected = False
        self.model_combo.setCurrentText(self._reset_entry_form_initial_values['model'])
        self.key_edit.setText(self._reset_entry_form_initial_values['api_key'])
        self.note_edit.setText(self._reset_entry_form_initial_values['note'])
        self.endpoint_edit.setCurrentText(self._reset_entry_form_initial_values['endpoint'])
        self._detected_service = None
        self._api_key_valid = False
        self.progress_bar.setVisible(False)

    def _truncate_api_key(self, api, head=6, tail=6, min_len=20):
        """Return a truncated API key for display in tooltips. Keep full API when editing."""
        try:
            if not api:
                return ""
            s = str(api)
            if len(s) <= min_len:
                return s
            return f"{s[:head]}...{s[-tail:]}"
        except Exception as e:
            print(f"Error truncating API key: {e}")
            return str(api)

    def _load_app_links(self):
        try:
            app_cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "app_config.json")
            with open(app_cfg_path, 'r', encoding='utf-8') as f:
                app_cfg = json.load(f)
                self._whatsapp_link = app_cfg.get('links', {}).get('whatsapp')
                self._get_api_key_link = app_cfg.get('links', {}).get('get_api_key')
        except Exception:
            self._whatsapp_link = None
            self._get_api_key_link = None

    def _on_paste_clicked(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        self.key_edit.setText(text)

    def _on_eye_clicked(self):
        """Show/hide API key. When revealing, show an English warning dialog first."""
        try:
            if not getattr(self, '_api_key_visible', False):
                mb = QMessageBox(self)
                mb.setWindowTitle("Reveal API Key - Warning")
                mb.setIcon(QMessageBox.Warning)
                mb.setText(
                    "Warning: Revealing your API key may expose it to others who can view your screen or access your system clipboard."
                    " Do not share your API key with untrusted parties or paste it into unknown websites.\n\n"
                    "Are you sure to reveal the API key?"
                )
                btn_yes = QPushButton("Reveal")
                btn_yes.setIcon(qta.icon('fa6s.eye'))
                btn_no = QPushButton("Cancel")
                btn_no.setIcon(qta.icon('fa6s.xmark'))
                mb.addButton(btn_yes, QMessageBox.AcceptRole)
                mb.addButton(btn_no, QMessageBox.RejectRole)
                mb.setDefaultButton(btn_no)
                mb.exec()
                if mb.clickedButton() != btn_yes:
                    return
            self._api_key_visible = not getattr(self, '_api_key_visible', False)
            if self._api_key_visible:
                self.key_edit.setEchoMode(QLineEdit.Normal)
                self.eye_btn.setIcon(qta.icon('fa6s.eye'))
            else:
                self.key_edit.setEchoMode(QLineEdit.Password)
                self.eye_btn.setIcon(qta.icon('fa6s.eye-slash'))
        except Exception as e:
            print(f"[AddApiKeyDialog] Error toggling API key visibility: {e}")



    def _create_icon_label_widget(self, text, icon_name, width):
        """Create a small widget with an icon on the left and text label on the right.
        Returns (widget_container, text_label).
        """
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        icon_lbl = QLabel()
        icon_size = 14
        icon = qta.icon(icon_name, color=self._label_icon_color)
        pix = icon.pixmap(icon_size, icon_size)
        icon_lbl.setPixmap(pix)

        text_lbl = QLabel(text)
        spacing = layout.spacing() if layout.spacing() is not None else 6
        icon_w = pix.width() if pix else icon_size
        text_w = max(10, int(width) - icon_w - spacing)
        text_lbl.setFixedWidth(text_w)
        text_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(icon_lbl)
        layout.addWidget(text_lbl)
        widget.setFixedWidth(int(width))
        return widget, text_lbl

    def _refresh_model_combo(self):
        service_key = self.normalize_service_key(self.service_combo.currentData())
        self.model_combo.clear()

        if service_key == 'custom':
            seen = set()
            aggregated = []
            try:
                for svc_models in (self.model_list or {}).values():
                    for m in (svc_models or []):
                        if m and m not in seen:
                            seen.add(m)
                            aggregated.append(m)
            except Exception:
                aggregated = []
            try:
                for m in (self.model_list.get('custom', []) or []):
                    if m and m not in seen:
                        seen.add(m)
                        aggregated.append(m)
            except Exception:
                pass
            aggregated = sorted(aggregated)
            for m in aggregated:
                self.model_combo.addItem(m)
            self.model_combo.setEditable(True)
        else:
            models = self.model_list.get(service_key, []) if isinstance(self.model_list, dict) else []
            for m in (models or []):
                self.model_combo.addItem(m)
            self.model_combo.setEditable(True)

        if self.model_combo.count() > 0:
            self.model_combo.setCurrentIndex(0)

    def eventFilter(self, obj, event):
        if obj is self.model_combo and event.type() in (QEvent.MouseButtonPress, QEvent.KeyPress):
            if event.type() == QEvent.MouseButtonPress or (event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Down, Qt.Key_Enter, Qt.Key_Return)):
                self._open_model_search_popup()
                return True
        return super().eventFilter(obj, event)

    def _open_model_search_popup(self):
        service_key = self.normalize_service_key(self.service_combo.currentData())
        if service_key == 'custom':
            seen = set()
            models = []
            try:
                for svc_models in (self.model_list or {}).values():
                    for m in (svc_models or []):
                        if m and m not in seen:
                            seen.add(m)
                            models.append(m)
            except Exception:
                models = []
            try:
                for m in (self.model_list.get('custom', []) or []):
                    if m and m not in seen:
                        seen.add(m)
                        models.append(m)
            except Exception:
                pass
            models = sorted(models)
        else:
            models = self.model_list.get(service_key, []) if service_key else []

        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.Popup)
        dlg.setAttribute(Qt.WA_DeleteOnClose)
        vbox = QVBoxLayout(dlg)
        search = QLineEdit()
        search.setPlaceholderText("Search models...")
        search.setClearButtonEnabled(True)
        listw = QListWidget()
        listw.addItems(models)
        listw.setSelectionMode(QListWidget.SingleSelection)
        vbox.addWidget(search)
        vbox.addWidget(listw)
        def _filter(text):
            t = text.lower()
            for i in range(listw.count()):
                item = listw.item(i)
                item.setHidden(t not in item.text().lower())
        search.textChanged.connect(_filter)
        def _choose():
            it = listw.currentItem()
            if not it:
                for i in range(listw.count()):
                    item = listw.item(i)
                    if not item.isHidden():
                        it = item
                        break
            if it:
                self.model_combo.setCurrentText(it.text())
                dlg.close()
        listw.itemActivated.connect(lambda item: (self.model_combo.setCurrentText(item.text()), dlg.close()))
        search.returnPressed.connect(_choose)
        def _search_keypress(e):
            if e.key() == Qt.Key_Down:
                for i in range(listw.count()):
                    if not listw.item(i).isHidden():
                        listw.setCurrentRow(i)
                        break
                listw.setFocus()
            else:
                QLineEdit.keyPressEvent(search, e)
        search.keyPressEvent = _search_keypress
        pos = self.model_combo.mapToGlobal(QPoint(0, self.model_combo.height()))
        dlg.setFixedWidth(self.model_combo.width())
        dlg.move(pos)
        dlg.show()
        search.setFocus()

    def _apply_table_search(self, text=''):
        q = (text or '').strip().lower()
        for r in range(self.api_table.rowCount()):
            if not q:
                self.api_table.setRowHidden(r, False)
                continue
            serv = self.api_table.item(r, 0).text() if self.api_table.item(r, 0) else ''
            api_item = self.api_table.item(r, 1)
            api = api_item.data(Qt.UserRole) if api_item and api_item.data(Qt.UserRole) is not None else (api_item.text() if api_item else '')
            endpoint = self.api_table.item(r, 2).text() if self.api_table.item(r, 2) else ''
            last = self.api_table.item(r, 3).text() if self.api_table.item(r, 3) else ''
            model = self.api_table.item(r, 4).text() if self.api_table.item(r, 4) else ''
            note = self.api_table.item(r, 5).text() if self.api_table.item(r, 5) else ''
            hay = ' '.join([str(serv), str(api), str(endpoint), str(model), str(note), str(last)]).lower()
            hide = q not in hay
            self.api_table.setRowHidden(r, hide)

    def _refresh_api_table(self):
        
        try:
            rows = self.db.get_all_api_keys()
        except Exception as e:
            print(f"Error fetching API keys: {e}")
            raise

        
        normalized = []
        for r in rows:
            if isinstance(r, dict):
                normalized.append((
                    r.get('service'),
                    r.get('api') or r.get('api_key'),
                    r.get('provider_endpoint') if 'provider_endpoint' in r else (r.get('endpoint') or ''),
                    r.get('last_tested'),
                    r.get('status'),
                    r.get('model', ''),
                    r.get('note')
                ))
            else:
                service = r[0] if len(r) > 0 else None
                api = r[1] if len(r) > 1 else None
                note = r[2] if len(r) > 2 else ''
                last_tested = r[3] if len(r) > 3 else None
                status = r[4] if len(r) > 4 else ''
                model = r[5] if len(r) > 5 else ''
                endpoint = r[6] if len(r) > 6 else ''
                normalized.append((service, api, endpoint, last_tested, status, model, note))

        
        sel = self.sort_combo.currentText() if hasattr(self, 'sort_combo') else 'All'

        def try_parse_dt(v):
            if not v:
                return None
            if isinstance(v, (tuple, list)):
                v = " ".join(str(x) for x in v)
            try:
                
                return datetime.datetime.fromisoformat(str(v))
            except Exception:
                try:
                    return datetime.datetime.strptime(str(v), '%Y-%m-%d %H:%M:%S')
                except Exception:
                    try:
                        return datetime.datetime.strptime(str(v), '%Y/%m/%d %H:%M:%S')
                    except Exception:
                        print(f"Failed to parse last_tested '{v}' for sorting")
                        return None

        display = list(normalized)
        if sel.startswith('Service:'):
            svc = sel.split(':', 1)[1].strip().lower()
            display = [t for t in display if str(t[0]).lower() == svc]
        elif sel == 'Status: Active':
            display = [t for t in display if str(t[4]).lower() == 'active']
        elif sel == 'Status: Invalid':
            display = [t for t in display if str(t[4]).lower() == 'invalid']
        elif sel == 'Last Tested (Newest)':
            display.sort(key=lambda x: (try_parse_dt(x[3]) is None, try_parse_dt(x[3]) or datetime.datetime.min), reverse=True)
        elif sel == 'Last Tested (Oldest)':
            display.sort(key=lambda x: (try_parse_dt(x[3]) is None, try_parse_dt(x[3]) or datetime.datetime.min))
        elif sel == 'API (A-Z)':
            display.sort(key=lambda x: (x[1] or '').lower())
        elif sel == 'API (Z-A)':
            display.sort(key=lambda x: (x[1] or '').lower(), reverse=True)
        elif sel == 'Model (A-Z)':
            display.sort(key=lambda x: (x[5] or '').lower())
        elif sel == 'Model (Z-A)':
            display.sort(key=lambda x: (x[5] or '').lower(), reverse=True)

        
        self.api_table.setSortingEnabled(False)
        self.api_table.setRowCount(len(display))
        for row_idx, (service, api, endpoint, last_tested, status, model, note) in enumerate(display):
            if isinstance(last_tested, (tuple, list)):
                last_tested = " ".join(str(x) for x in last_tested)

            tooltip_lines = []
            tooltip_lines.append(f"Service: {service}")
            truncated_api = self._truncate_api_key(api)
            tooltip_lines.append(f"API Key: {truncated_api}")
            tooltip_lines.append(f"Endpoint: {endpoint or 'Default'}")
            tooltip_lines.append(f"Model: {model or 'N/A'}")
            tooltip_lines.append(f"Last Tested: {last_tested or 'Never'}")
            tooltip_lines.append(f"Status: {status or 'Unknown'}")
            tooltip_lines.append(f"Note: {note or 'N/A'}")
            tooltip_text = "\n".join(tooltip_lines)

            svc_display = self.get_service_display_name(service)
            service_item = QTableWidgetItem(svc_display)
            service_item.setToolTip(tooltip_text)
            self.api_table.setItem(row_idx, 0, service_item)

            display_api = (str(api)[-7:] if api and len(str(api)) > 7 else str(api))
            if display_api and len(str(api)) > 7:
                display_api = f"...{display_api}"
            api_item = QTableWidgetItem(display_api)
            api_item.setData(Qt.UserRole, api)
            api_item.setToolTip(tooltip_text)
            self.api_table.setItem(row_idx, 1, api_item)

            endpoint_item = QTableWidgetItem(str(endpoint or ''))
            endpoint_item.setToolTip(tooltip_text)
            self.api_table.setItem(row_idx, 2, endpoint_item)

            last_tested_item = QTableWidgetItem(str(last_tested))
            last_tested_item.setToolTip(tooltip_text)
            self.api_table.setItem(row_idx, 3, last_tested_item)

            model_item = QTableWidgetItem(str(model or ''))
            model_item.setToolTip(tooltip_text)
            self.api_table.setItem(row_idx, 4, model_item)

            note_item = QTableWidgetItem(str(note))
            note_item.setToolTip(tooltip_text)
            self.api_table.setItem(row_idx, 5, note_item)

            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(0, 0, 0, 0)
            test_btn = QPushButton()
            test_btn.setIcon(qta.icon('fa6s.play'))
            test_btn.setToolTip("Test this API Key")
            test_btn.setFixedWidth(28)
            test_btn.setProperty("row", row_idx)
            test_btn.clicked.connect(lambda _, r=row_idx: self._test_api_key_row(r))
            delete_btn = QPushButton()
            delete_btn.setIcon(qta.icon('fa6s.trash'))
            delete_btn.setToolTip("Delete this API Key")
            delete_btn.setFixedWidth(28)
            delete_btn.setProperty("row", row_idx)
            delete_btn.clicked.connect(lambda _, r=row_idx: self._delete_api_key_row(r))
            action_layout.addWidget(test_btn)
            action_layout.addWidget(delete_btn)
            if endpoint and ('api.desainia.my.id' in str(endpoint) or 'api.koboillm.com' in str(endpoint)):
                dollar_btn = QPushButton()
                dollar_btn.setIcon(qta.icon('fa6s.dollar-sign'))
                dollar_btn.setToolTip("Check credit usage")
                dollar_btn.setFixedWidth(28)
                dollar_btn.clicked.connect(lambda _, a=api, e=endpoint: self._open_credit_usage_dialog(a, e))
                action_layout.addWidget(dollar_btn)
            action_layout.addStretch()
            self.api_table.setCellWidget(row_idx, 6, action_widget)
            if status == "active":
                color = QColor(theme.get_color('success'))
                color.setAlpha(int(0.4 * 255))
                brush = QBrush(color)
            elif status == "invalid":
                color = QColor(theme.get_color('error'))
                color.setAlpha(int(0.4 * 255))
                brush = QBrush(color)
            else:
                brush = None
            if brush:
                for col in range(6):
                    item = self.api_table.item(row_idx, col)
                    if item:
                        item.setBackground(brush)
        
        self.api_table.setSortingEnabled(True)
        self._stop_blinking()
        try:
            self._update_stats(display)
        except Exception as e:
            print(f"[AddApiKeyDialog] Error updating API stats: {e}")
        if hasattr(self, 'search_edit'):
            self._apply_table_search(self.search_edit.text())

    def _update_stats(self, rows):
        total_api = len(rows)
        models = set()
        valid = 0
        invalid = 0
        last_dt = None
        for r in rows:
            model = r[5] if len(r) > 5 else ''
            if model:
                models.add(model)
            status = str(r[4]).lower() if r[4] is not None else ''
            if status == 'active':
                valid += 1
            elif status == 'invalid':
                invalid += 1
            lt = r[3]
            if lt:
                if isinstance(lt, (tuple, list)):
                    lt_str = " ".join(str(x) for x in lt)
                else:
                    lt_str = str(lt)
                dt = None
                try:
                    dt = datetime.datetime.fromisoformat(lt_str)
                except Exception:
                    try:
                        dt = datetime.datetime.strptime(lt_str, '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        try:
                            dt = datetime.datetime.strptime(lt_str, '%Y/%m/%d %H:%M:%S')
                        except Exception:
                            print(f"Failed to parse last_tested '{lt_str}' for stats")
                            dt = None
                if dt and (last_dt is None or dt > last_dt):
                    last_dt = dt
        models_count = len(models)
        last_tested_str = last_dt.strftime('%Y-%m-%d %H:%M:%S') if last_dt else 'Never'
        self.stats_models_lbl.setText(f"Models: {models_count}")
        self.stats_apis_lbl.setText(f"APIs: {total_api}")
        self.stats_valid_lbl.setText(f"Valid: {valid}")
        self.stats_invalid_lbl.setText(f"Invalid: {invalid}")
        self.stats_last_tested_lbl.setText(f"Last Tested: {last_tested_str}")

    def _test_api_key_row(self, row):
        if self._row_testing is not None:
            return
        service_item = self.api_table.item(row, 0)
        api_item = self.api_table.item(row, 1)
        if not service_item or not api_item:
            return
        service = self.normalize_service_key(service_item.text())
        api_key = api_item.data(Qt.UserRole) if api_item and api_item.data(Qt.UserRole) is not None else api_item.text().strip()
        model = None
        provider_endpoint = None

        try:
            rows = self.db.get_all_api_keys()
            for r in rows:
                if isinstance(r, dict):
                    if r.get('api') == api_key and str(r.get('service')).lower() == service:
                        model = r.get('model')
                        provider_endpoint = r.get('provider_endpoint') or r.get('endpoint')
                        break
                else:
                    if len(r) >= 2 and r[1] == api_key and str(r[0]).lower() == service:
                        model = r[5] if len(r) > 5 else None
                        provider_endpoint = r[6] if len(r) > 6 else None
                        break
        except Exception as e:
            print(f"Error fetching API keys for model lookup: {e}")
        test_btn = self._get_action_btn(row, 0)
        if test_btn:
            test_btn.setIcon(qta.icon('fa6s.stop'))
            test_btn.setToolTip("Stop testing")
        self._row_testing = row
        self._blink_state = False
        self._blink_timer.start(300)
        self._test_thread_row = ApiKeyTestThread(api_key, service, model, provider_endpoint)
        self._test_thread_row.result.connect(lambda status, service, text: self._on_test_row_result(row, status, service, text))
        self._test_thread_row.finished.connect(lambda: self._stop_blinking())
        self._test_thread_row.start()

    def _on_test_row_result(self, row, status, service, text):
        self._stop_blinking()
        api_item = self.api_table.item(row, 0)
        key_item = self.api_table.item(row, 1)
        if api_item and key_item:
            svc = self.normalize_service_key(service or api_item.text())
            api_key = key_item.data(Qt.UserRole) if key_item.data(Qt.UserRole) is not None else key_item.text().strip()
            note = None
            model = None
            provider_endpoint = None
            try:
                rows = self.db.get_all_api_keys()
                for r in rows:
                    if isinstance(r, dict):
                        if r.get('api') == api_key and str(r.get('service')).lower() == svc:
                            note = r.get('note')
                            model = r.get('model')
                            provider_endpoint = r.get('provider_endpoint') or r.get('endpoint')
                            break
                    else:
                        if len(r) >= 2 and r[1] == api_key and str(r[0]).lower() == svc:
                            note = r[2] if len(r) > 2 else None
                            model = r[5] if len(r) > 5 else None
                            provider_endpoint = r[6] if len(r) > 6 else None
                            break
            except Exception as e:
                print(f"[AddApiKeyDialog] Error fetching row data for status update: {e}")
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db_status = "active" if status == 'success' else "invalid"
            try:
                self.db.set_api_key(svc, api_key, note, now, db_status, model, provider_endpoint=provider_endpoint)
            except Exception as e:
                print(f"[AddApiKeyDialog] Error saving test result to db: {e}")
        self._refresh_api_table()
        if status == 'success':
            QMessageBox.information(self, "API Key Test", "API Key is valid and active.")
        else:
            QMessageBox.warning(self, "API Key Test", "API Key invalid or not supported.")
            err = text or "<no raw error available>"
            try:
                self._show_error_dialog(err)
            except Exception as e:
                print(f"[AddApiKeyDialog] Error showing error dialog: {e}")

    def _get_action_btn(self, row, btn_idx):
        widget = self.api_table.cellWidget(row, 6)
        if widget:
            layout = widget.layout()
            if layout and layout.count() > btn_idx:
                return layout.itemAt(btn_idx).widget()
        return None

    def _blink_row(self):
        if self._row_testing is None:
            return
        color1 = QColor(theme.get_color('warning'))
        color1.setAlpha(180)
        color2 = QColor(theme.get_color('white'))
        color2.setAlpha(0)
        color = color1 if self._blink_state else color2
        for col in range(6):
            item = self.api_table.item(self._row_testing, col)
            if item:
                item.setBackground(QBrush(color))
        self._blink_state = not self._blink_state

    def _stop_blinking(self):
        if self._row_testing is not None:
            test_btn = self._get_action_btn(self._row_testing, 0)
            if test_btn:
                test_btn.setIcon(qta.icon('fa6s.play'))
                test_btn.setToolTip("Test this API Key")
        self._blink_timer.stop()
        if self._row_testing is not None:
            for col in range(6):
                item = self.api_table.item(self._row_testing, col)
                if item:
                    item.setBackground(QBrush())
        self._row_testing = None
        self._blink_state = False

    def _delete_api_key_row(self, row):
        if self._row_testing == row:
            self._stop_blinking()
        service_item = self.api_table.item(row, 0)
        api_item = self.api_table.item(row, 1)
        if not service_item or not api_item:
            return
        service = self.normalize_service_key(service_item.text())
        api_key = api_item.data(Qt.UserRole) if api_item and api_item.data(Qt.UserRole) is not None else api_item.text().strip()
        if not api_key or not service:
            QMessageBox.warning(self, "Delete API Key", "No API Key selected to delete.")
            return
        mb = QMessageBox(self)
        mb.setWindowTitle("Delete API Key")
        mb.setText(f"Delete API Key for '{service}'?\nThis cannot be undone.")
        mb.setIcon(QMessageBox.Warning)
        btn_yes = QPushButton("Delete")
        btn_yes.setIcon(qta.icon('fa6s.trash'))
        btn_no = QPushButton("Cancel")
        btn_no.setIcon(qta.icon('fa6s.xmark'))
        mb.addButton(btn_yes, QMessageBox.AcceptRole)
        mb.addButton(btn_no, QMessageBox.RejectRole)
        mb.setDefaultButton(btn_no)
        mb.exec()
        if mb.clickedButton() == btn_yes:
            self.db.delete_api_key(service, api_key)
            self._refresh_api_table()
            self.key_edit.clear()
            self.note_edit.clear()

    def _delete_selected_api_key(self):
        sel = self.api_table.selectionModel().selectedRows()
        rows_to_delete = []
        if sel:
            for idx in sel:
                r = idx.row()
                service_item = self.api_table.item(r, 0)
                api_item = self.api_table.item(r, 1)
                note_item = self.api_table.item(r, 5)
                if not service_item or not api_item:
                    continue
                service = self.normalize_service_key(service_item.text())
                api = api_item.data(Qt.UserRole) if api_item.data(Qt.UserRole) is not None else api_item.text().strip()
                note = note_item.text().strip() if note_item else ''
                rows_to_delete.append((service, api, note))
        else:
            row = self.api_table.currentRow()
            if row < 0:
                QMessageBox.warning(self, "Delete API Key", "No API Key selected to delete.")
                return
            service_item = self.api_table.item(row, 0)
            api_item = self.api_table.item(row, 1)
            note_item = self.api_table.item(row, 5)
            if not service_item or not api_item:
                QMessageBox.warning(self, "Delete API Key", "No API Key selected to delete.")
                return
            service = self.normalize_service_key(service_item.text())
            api = api_item.data(Qt.UserRole) if api_item.data(Qt.UserRole) is not None else api_item.text().strip()
            note = note_item.text().strip() if note_item else ''
            rows_to_delete.append((service, api, note))

        if not rows_to_delete:
            QMessageBox.warning(self, "Delete API Key", "No API Key selected to delete.")
            return

        def _trunc_api(a: object) -> str:
            s = str(a) if a is not None else ''
            if len(s) > 7:
                return f"...{s[-7:]}"
            return s

        preview_lines = []
        for svc, api, note in rows_to_delete[:10]:
            svc_cap = (svc or '').capitalize()
            line = f"{_trunc_api(api)} ({svc_cap}"
            if note:
                line += f" - {note}"
            line += ")"
            preview_lines.append(line)
        remaining = max(0, len(rows_to_delete) - 10)
        if remaining:
            preview_lines.append(f"...and {remaining} other API{'s' if remaining > 1 else ''}")

        total = len(rows_to_delete)
        preview_text = "\n".join(preview_lines)
        title = f"Delete {total} API Key{'s' if total > 1 else ''}"
        main = f"Delete {total} selected API key{'s' if total > 1 else ''}?\n\nThis action cannot be undone."
        mb = QMessageBox(self)
        mb.setWindowTitle(title)
        mb.setText(main)
        if preview_text:
            mb.setInformativeText(preview_text)
        mb.setIcon(QMessageBox.Warning)
        btn_yes = QPushButton("Delete")
        btn_yes.setIcon(qta.icon('fa6s.trash'))
        btn_no = QPushButton("Cancel")
        btn_no.setIcon(qta.icon('fa6s.xmark'))
        mb.addButton(btn_yes, QMessageBox.AcceptRole)
        mb.addButton(btn_no, QMessageBox.RejectRole)
        mb.setDefaultButton(btn_no)
        mb.exec()
        if mb.clickedButton() == btn_yes:
            failed = 0
            for svc, api, _ in rows_to_delete:
                try:
                    self.db.delete_api_key(svc, api)
                except Exception as e:
                    print(f"Error deleting selected API key ({svc}, {api}): {e}")
                    failed += 1
            self._refresh_api_table()
            self.key_edit.clear()
            self.note_edit.clear()
            if failed == 0:
                QMessageBox.information(self, "Delete API Key", f"Deleted {total} API key{'s' if total > 1 else ''}.")
            else:
                QMessageBox.critical(self, "Delete API Key", f"Failed to delete {failed} of {total} selected API key{'s' if total > 1 else ''}.")

    def _on_api_table_row_clicked(self, row, column):
        if column == 6:
            return
        service_item = self.api_table.item(row, 0)
        api_item = self.api_table.item(row, 1)
        endpoint_item = self.api_table.item(row, 2)
        model_item = self.api_table.item(row, 4)
        note_item = self.api_table.item(row, 5)
        if service_item and api_item:
            service_text = service_item.text()
            api_text = api_item.data(Qt.UserRole) if api_item and api_item.data(Qt.UserRole) is not None else api_item.text()
            endpoint_text = endpoint_item.text() if endpoint_item else ""
            model_text = model_item.text() if model_item else ""
            note_text = note_item.text() if note_item else ""
            self.key_edit.setText(api_text)
            self.note_edit.setText(note_text)
            self.endpoint_edit.setCurrentText(endpoint_text)
            # Find combo text from SERVICE_MAP (reverse lookup)
            combo_text = self.get_service_display_name(service_text)
            self.service_combo.setCurrentText(combo_text)
            self._refresh_model_combo()
            
            if model_text:
                idx = self.model_combo.findText(model_text)
                if idx >= 0:
                    self.model_combo.setCurrentIndex(idx)
                else:
                    
                    mb = QMessageBox(self)
                    mb.setWindowTitle("Save Model")
                    mb.setText(f"The model '{model_text}' is not in your model list.\n\nWould you like to add it to your {service_text} models?")
                    btn_yes = QPushButton("Save")
                    btn_yes.setIcon(qta.icon('fa6s.floppy-disk'))
                    btn_no = QPushButton("No")
                    btn_no.setIcon(qta.icon('fa6s.xmark'))
                    mb.addButton(btn_yes, QMessageBox.AcceptRole)
                    mb.addButton(btn_no, QMessageBox.RejectRole)
                    mb.setDefaultButton(btn_yes)
                    mb.exec()
                    reply = QMessageBox.Yes if mb.clickedButton() == btn_yes else QMessageBox.No
                    if reply == QMessageBox.Yes:
                        
                        service_key = self.normalize_service_key(service_text)
                        if service_key not in self.model_list:
                            self.model_list[service_key] = []
                        if model_text not in self.model_list[service_key]:
                            self.model_list[service_key].append(model_text)
                            
                            ai_prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "ai_config.json")
                            try:
                                with open(ai_prompt_path, "r", encoding="utf-8") as f:
                                    ai_config = json.load(f)
                                ai_config["model_list"] = self.normalize_model_list(self.model_list)
                                with open(ai_prompt_path, "w", encoding="utf-8") as f:
                                    json.dump(ai_config, f, indent=2, ensure_ascii=False)
                            except Exception as e:
                                print(f"Error saving model to config: {e}")
                        
                        self._refresh_model_combo()
                    
                    idx = self.model_combo.findText(model_text)
                    if idx < 0:
                        self.model_combo.addItem(model_text)
                        idx = self.model_combo.findText(model_text)
                    self.model_combo.setCurrentIndex(idx)
            elif self.model_combo.count() > 0:
                self.model_combo.setCurrentIndex(0)
            # Set detected service using normalized service key
            self._detected_service = self.normalize_service_key(service_text) or None
            self._update_endpoint_state()

    def _on_key_edit_changed(self, text):
        api_key = text.strip()
        service = None
        ak = api_key or ''
        lower = ak.lower()
        if lower.startswith('gsk_') or lower.startswith('gsk-'):
            service = 'groq'
        elif re.match(r"^sk-?or-", ak, re.IGNORECASE):
            service = 'openrouter'
        elif ak.startswith('sk-') and len(ak) == 25:
            service = 'maia'
        elif ak.startswith('sk-') and len(ak) > 40:
            service = 'openai'
        elif ak.startswith('AIza') or ak.startswith('AQ'):
            service = 'gemini'
        else:
            service = None
        if not self._service_manually_selected:
            # Use reverse map to get display name for service
            if service:
                self.service_combo.setCurrentText(self.get_service_display_name(service))
        self._detected_service = service
        self._api_key_valid = False
        self.progress_bar.setVisible(False)

    def _on_service_combo_changed(self, idx):
        """When user selects a service, update internal state and refresh models"""
        self._detected_service = self.normalize_service_key(self.service_combo.currentData()) or None
        self._refresh_model_combo()
        self._api_key_valid = False
        self._service_manually_selected = True
        self._update_endpoint_state()

    def _on_model_combo_changed(self, idx):
        try:
            self._api_key_valid = False
            self._model_manually_selected = True
        except Exception as e:
            print(f"[AddApiKeyDialog] Error handling model combo change: {e}")

    def _update_endpoint_state(self):
        """Enable/disable endpoint field based on service selection"""
        service_key = self.normalize_service_key(self.service_combo.currentData())
        is_custom = service_key == 'custom'
        self.endpoint_edit.setEnabled(is_custom)
        self.endpoint_paste_btn.setEnabled(is_custom)
        self.fetch_models_btn.setVisible(is_custom)

    def _on_endpoint_combo_changed(self, idx):
        """When user selects a provider from dropdown, auto-fill the endpoint URL"""
        url = self.endpoint_edit.currentData()
        if url:
            self.endpoint_edit.setCurrentText(url)

    def _on_endpoint_paste(self):
        try:
            clip = QApplication.clipboard().text()
            if clip:
                self.endpoint_edit.setCurrentText(clip)
        except Exception as e:
            print(f"[AddApiKeyDialog] Failed to paste endpoint: {e}")

    def _on_model_paste_clicked(self):
        """Paste model name from clipboard"""
        try:
            clip = QApplication.clipboard().text().strip()
            if clip:
                self.model_combo.setCurrentText(clip)
        except Exception as e:
            print(f"[AddApiKeyDialog] Failed to paste model: {e}")

    def _on_fetch_models_clicked(self):
        """Fetch models from custom endpoint"""
        try:
            # Validate inputs
            api_key = self.key_edit.text().strip()
            endpoint = self.endpoint_edit.currentText().strip()
            
            if not api_key:
                QMessageBox.warning(self, "Fetch Models", "Please enter an API key first.")
                return
            
            if not endpoint:
                QMessageBox.warning(self, "Fetch Models", "Please enter a custom endpoint URL first.")
                return
            
            # Create and show dialog
            dialog = FetchModelsDialog(self)
            dialog.fetch_models(api_key, endpoint)
            
            if dialog.exec():
                selected_model = dialog.get_selected_model()
                if selected_model:
                    # Set the model in the combo
                    self.model_combo.setCurrentText(selected_model)
                    
        except Exception as e:
            print(f"[AddApiKeyDialog] Error fetching models: {e}")
            QMessageBox.critical(self, "Fetch Models", f"Failed to fetch models: {e}")
    
    def _on_add_model_clicked(self):
        """Save the current model text to the model list for the active provider"""
        try:
            model_text = self.model_combo.currentText().strip()
            if not model_text:
                QMessageBox.warning(self, "Add Model", "Please enter or select a model name first.")
                return
            
            # Get service key from combo userData
            service_key = self.normalize_service_key(self.service_combo.currentData())
            service = self.service_combo.currentText()
            
            if not service_key:
                QMessageBox.warning(self, "Add Model", "Please select a service/provider first.")
                return
            
            # Check if model already exists
            if service_key not in self.model_list:
                self.model_list[service_key] = []
            
            if model_text in self.model_list[service_key]:
                QMessageBox.information(self, "Add Model", f"Model '{model_text}' already exists in {service} list.")
                # Still select it
                idx = self.model_combo.findText(model_text)
                if idx >= 0:
                    self.model_combo.setCurrentIndex(idx)
                return
            
            # Add model to list
            self.model_list[service_key].append(model_text)
            
            # Save to ai_config.json
            ai_prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "ai_config.json")
            try:
                with open(ai_prompt_path, "r", encoding="utf-8") as f:
                    ai_config = json.load(f)
                ai_config["model_list"] = self.model_list
                with open(ai_prompt_path, "w", encoding="utf-8") as f:
                    json.dump(ai_config, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Error saving model to config: {e}")
                QMessageBox.critical(self, "Add Model", f"Failed to save model to config: {e}")
                return
            
            # Refresh combo and select the new model
            self._refresh_model_combo()
            idx = self.model_combo.findText(model_text)
            if idx < 0:
                # If not found after refresh (shouldn't happen), add it manually
                self.model_combo.addItem(model_text)
                idx = self.model_combo.findText(model_text)
            self.model_combo.setCurrentIndex(idx)
            
            QMessageBox.information(self, "Add Model", f"Model '{model_text}' has been saved to {service} list.")
        except Exception as e:
            print(f"[AddApiKeyDialog] Error adding model: {e}")
            QMessageBox.critical(self, "Add Model", f"Failed to add model: {e}")

    def _open_model_manager(self):
        dlg = ModelManagerDialog(self.model_list, self)
        if dlg.exec():
            
            ai_prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "ai_config.json")
            try:
                with open(ai_prompt_path, "r", encoding="utf-8") as f:
                    ai_prompt = json.load(f)
                    self.model_list = self.normalize_model_list(ai_prompt.get("model_list", {}))
            except Exception as e:
                QMessageBox.critical(self, 'Model Manager', f'Failed to reload model list: {e}')
                return
            self._refresh_model_combo()

    def _start_test_thread(self, api_key, service):
        if self._testing:
            return
        self._testing = True
        self.progress_bar.setVisible(True)
        self.test_and_save_btn.setEnabled(False)
        model = self.model_combo.currentText() if self.model_combo.count() > 0 else None
        provider_endpoint = None
        service_key = self.normalize_service_key(self.service_combo.currentData())
        if service_key == 'custom':
            ep = self.endpoint_edit.currentText().strip()
            provider_endpoint = ep if ep else None
        self._test_thread = ApiKeyTestThread(api_key, service, model, provider_endpoint)
        self._test_thread.result.connect(self._on_test_result_auto)
        self._test_thread.finished.connect(lambda: self._set_testing(False))
        self._test_thread.finished.connect(lambda: self.test_and_save_btn.setEnabled(True))
        self._test_thread.finished.connect(lambda: self.progress_bar.setVisible(False))
        self._test_thread.start()

    def _set_testing(self, val):
        self._testing = val

    def _on_test_result_auto(self, status, service, text):
        if status == 'success':
            self._detected_service = service
            self._api_key_valid = True
        else:
            self._api_key_valid = False

    def test_and_save_api_key(self):
        api_key = self.key_edit.text().strip()
        note = self.note_edit.text().strip()
        service_key = self.normalize_service_key(self.service_combo.currentData())
        is_custom = service_key == 'custom'
        if is_custom:
            service = "custom"
        else:
            service = self._detected_service
        model = self.model_combo.currentText() if self.model_combo.count() > 0 else None
        if not api_key:
            QMessageBox.warning(self, "Input Error", "API Key cannot be empty.")
            return
        if not is_custom:
            if not service:
                ak = api_key.strip()
                ak_lower = ak.lower()
                if ak_lower.startswith('gsk_') or ak_lower.startswith('gsk-'):
                    service = 'groq'
                elif re.match(r"^sk-?or-", ak, re.IGNORECASE):
                    service = 'openrouter'
                elif ak.startswith('sk-') and len(ak) == 25:
                    service = 'maia'
                elif ak.startswith('sk-') and len(ak) > 40:
                    service = 'openai'
                elif ak.startswith('AIza') or ak.startswith('AQ'):
                    service = 'gemini'
                elif model and 'blackboxai' in model.lower():
                    service = 'blackbox'
        if not service:
            QMessageBox.warning(self, "Input Error", "API Key format not recognized as Gemini, OpenAI, OpenRouter, Groq, Blackbox, Maia, or Custom Endpoint.")
            return
        if not model:
            QMessageBox.warning(self, "Input Error", "Model must be selected.")
            return
        self.progress_bar.setVisible(True)
        self.test_and_save_btn.setEnabled(False)
        provider_endpoint = None
        if is_custom:
            if hasattr(self, 'endpoint_edit'):
                ep = self.endpoint_edit.currentText().strip()
                provider_endpoint = ep if ep else None
        self._pending_provider_endpoint = provider_endpoint
        self._test_thread = ApiKeyTestThread(api_key, service, model, provider_endpoint)
        self._test_thread.result.connect(lambda status, service, text: self._on_test_and_save_result(status, service, text, note, model))
        self._test_thread.finished.connect(lambda: self.test_and_save_btn.setEnabled(True))
        self._test_thread.finished.connect(lambda: self.progress_bar.setVisible(False))
        self._test_thread.start()

    def _on_test_and_save_result(self, status, service, text, note, model):
        if status == 'success':
            self._detected_service = service
            self._api_key_valid = True
            last_tested = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.db.set_api_key(service, self.key_edit.text().strip(), note, last_tested, status="active", model=model, provider_endpoint=getattr(self, '_pending_provider_endpoint', None))
            self._refresh_api_table()
            self.key_edit.clear()
            self.note_edit.clear()
            api_exists = False
            try:
                rows = self.db.get_all_api_keys()
                for row in rows:
                    if isinstance(row, dict):
                        if row["service"] == service and row["api"] == self.key_edit.text().strip():
                            api_exists = True
                            break
                    else:
                        if len(row) == 7:
                            s, a, n, lt, st, m, ep = row
                        elif len(row) == 6:
                            s, a, n, lt, st, m = row
                        elif len(row) == 5:
                            s, a, n, lt, st = row
                            m = ""
                        else:
                            s, a, n, lt = row
                            st = ""
                            m = ""
                        if s == service and a == self.key_edit.text().strip():
                            api_exists = True
                            break
            except Exception as e:
                print(f"[AddApiKeyDialog] Error checking existing API keys: {e}")
            if api_exists:
                QMessageBox.information(self, "Saved", f"API Key for '{service}' is valid and active, ready to use.")
            else:
                QMessageBox.information(self, "Saved", f"API Key for '{service}' saved.")
        else:
            self._api_key_valid = False
            last_tested = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.db.set_api_key(service, self.key_edit.text().strip(), note, last_tested, status="invalid", model=model, provider_endpoint=getattr(self, '_pending_provider_endpoint', None))
            self._refresh_api_table()
            QMessageBox.warning(self, "Test API Key", "API Key invalid or not supported.")
            err = text or "<no raw error available>"
            self._show_error_dialog(err)

    def _show_error_dialog(self, error_text):
        dlg = QDialog(self)
        dlg.setWindowTitle("API Error Details")
        dlg.setMinimumWidth(480)
        vbox = QVBoxLayout()
        label = QLabel("Raw error / response:")
        vbox.addWidget(label)
        error_box = QPlainTextEdit()
        error_box.setReadOnly(True)
        error_box.setPlainText(error_text)
        error_box.setMinimumHeight(120)
        vbox.addWidget(error_box)
        hbox = QHBoxLayout()
        copy_btn = QPushButton(qta.icon('fa6s.copy'), "Copy Error")
        def _popup_copy():
            QApplication.clipboard().setText(error_text)
            try:
                pos = copy_btn.mapToGlobal(copy_btn.rect().center())
                QToolTip.showText(pos, "Error report copied to clipboard — click 'Report Error' to send.", copy_btn)
            except Exception as e:
                print(f"[AddApiKeyDialog] Error showing tooltip after copy: {e}")
        copy_btn.clicked.connect(_popup_copy)
        report_btn = QPushButton(qta.icon('fa6s.bug'), "Report Error")
        report_btn.clicked.connect(lambda: self._report_error_via_whatsapp(error_text))
        hbox.addStretch()
        hbox.addWidget(copy_btn)
        hbox.addWidget(report_btn)
        vbox.addLayout(hbox)
        close_btn = QPushButton(qta.icon('fa6s.xmark'), "Close")
        close_btn.clicked.connect(dlg.accept)
        hbox_close = QHBoxLayout()
        hbox_close.addStretch()
        hbox_close.addWidget(close_btn)
        vbox.addLayout(hbox_close)
        dlg.setLayout(vbox)
        dlg.exec()

    def delete_api_key(self):
        service = self.service_combo.currentText().lower()
        api_key = self.key_edit.text().strip()
        if not api_key or not service:
            QMessageBox.warning(self, "Delete API Key", "No API Key selected to delete.")
            return
        confirm = QMessageBox.question(self, "Delete API Key", f"Delete API Key for '{service}'?\nThis cannot be undone.", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            self.db.delete_api_key(service, api_key)
            self._refresh_api_table()
            self.key_edit.clear()
            self.note_edit.clear()

    def _delete_all_api_keys(self):
        try:
            rows = self.db.get_all_api_keys()
        except Exception as e:
            print(f"Error fetching API keys for delete all check: {e}")
            rows = []
        if not rows:
            QMessageBox.information(self, "Delete All API Keys", "No API keys saved.")
            return
        def _trunc_api(a: object) -> str:
            s = str(a) if a is not None else ''
            if len(s) > 7:
                return f"...{s[-7:]}"
            return s
        preview_lines = []
        for r in rows[:10]:
            if isinstance(r, dict):
                svc = (r.get('service') or '').capitalize()
                api = r.get('api') or ''
                note = r.get('note') or ''
            else:
                if len(r) == 6:
                    svc, api, note, _, _, _ = r
                elif len(r) == 5:
                    svc, api, note, _, _ = r
                else:
                    svc, api, note = r[0], r[1], r[2] if len(r) > 2 else ''
                svc = (svc or '').capitalize()
                api = api or ''
                note = note or ''
            line = f"{_trunc_api(api)} ({svc}"
            if note:
                line += f" - {note}"
            line += ")"
            preview_lines.append(line)
        remaining = max(0, len(rows) - 10)
        if remaining:
            preview_lines.append(f"...and {remaining} other API{'s' if remaining > 1 else ''}")
        message = "Delete ALL API keys?\n\nThis action cannot be undone.\n\n" + "\n".join(preview_lines)
        mb = QMessageBox(self)
        mb.setWindowTitle("Delete All API Keys")
        mb.setText(message)
        mb.setIcon(QMessageBox.Warning)
        btn_yes = QPushButton("Delete")
        btn_yes.setIcon(qta.icon('fa6s.trash'))
        btn_no = QPushButton("Cancel")
        btn_no.setIcon(qta.icon('fa6s.xmark'))
        mb.addButton(btn_yes, QMessageBox.AcceptRole)
        mb.addButton(btn_no, QMessageBox.RejectRole)
        mb.setDefaultButton(btn_no)
        mb.exec()
        if mb.clickedButton() == btn_yes:
            try:
                self.db.delete_all_api_keys()
                self._refresh_api_table()
                self.key_edit.clear()
                self.note_edit.clear()
                QMessageBox.information(self, "Delete All API Keys", "All API keys have been deleted.")
            except Exception as e:
                print(f"Error deleting all API keys: {e}")
                
    def _show_context_menu(self, pos: QPoint):
        index = self.api_table.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        self.api_table.selectRow(row)
        service_item = self.api_table.item(row, 0)
        api_item = self.api_table.item(row, 1)
        endpoint_item = self.api_table.item(row, 2)
        model_item = self.api_table.item(row, 4)
        note_item = self.api_table.item(row, 5)
        if not service_item or not api_item:
            return
        service_text = service_item.text()
        api_text = api_item.data(Qt.UserRole) if api_item and api_item.data(Qt.UserRole) is not None else api_item.text()
        endpoint_text = endpoint_item.text() if endpoint_item else ""
        model_text = model_item.text() if model_item else ""
        note_text = note_item.text() if note_item else ""
        self.key_edit.setText(api_text)
        self.note_edit.setText(note_text)
        self.endpoint_edit.setCurrentText(endpoint_text)
        combo_text = self.get_service_display_name(service_text)
        self.service_combo.setCurrentText(combo_text)
        self._refresh_model_combo()
        if model_text:
            idx = self.model_combo.findText(model_text)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
            else:
                mb = QMessageBox(self)
                mb.setWindowTitle("Save Model")
                mb.setText(f"The model '{model_text}' is not in your model list.\n\nWould you like to add it to your {service_text} models?")
                btn_yes = QPushButton("Save")
                btn_yes.setIcon(qta.icon('fa6s.floppy-disk'))
                btn_no = QPushButton("No")
                btn_no.setIcon(qta.icon('fa6s.xmark'))
                mb.addButton(btn_yes, QMessageBox.AcceptRole)
                mb.addButton(btn_no, QMessageBox.RejectRole)
                mb.setDefaultButton(btn_yes)
                mb.exec()
                reply = QMessageBox.Yes if mb.clickedButton() == btn_yes else QMessageBox.No
                if reply == QMessageBox.Yes:
                    service_key = self.normalize_service_key(service_text)
                    if service_key not in self.model_list:
                        self.model_list[service_key] = []
                    if model_text not in self.model_list[service_key]:
                        self.model_list[service_key].append(model_text)
                        ai_prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "ai_config.json")
                        try:
                            with open(ai_prompt_path, "r", encoding="utf-8") as f:
                                ai_config = json.load(f)
                            ai_config["model_list"] = self.normalize_model_list(self.model_list)
                            with open(ai_prompt_path, "w", encoding="utf-8") as f:
                                json.dump(ai_config, f, indent=2, ensure_ascii=False)
                        except Exception as e:
                            print(f"Error saving model to config: {e}")
                    self._refresh_model_combo()
                idx = self.model_combo.findText(model_text)
                if idx < 0:
                    self.model_combo.addItem(model_text)
                    idx = self.model_combo.findText(model_text)
                self.model_combo.setCurrentIndex(idx)
        elif self.model_combo.count() > 0:
            self.model_combo.setCurrentIndex(0)
        self._detected_service = self.normalize_service_key(service_text) or None
        self._update_endpoint_state()
        menu = QMenu(self)
        action_test = QAction(qta.icon('fa6s.play'), "Test and Save", self)
        action_test.triggered.connect(self.test_and_save_api_key)
        menu.addAction(action_test)
        menu.exec(self.api_table.viewport().mapToGlobal(pos))

    def _report_error_via_whatsapp(self, error_text=None):
        if not getattr(self, '_whatsapp_link', None):
            QMessageBox.warning(self, "Report Error", "No reporting link configured.")
            return
        try:
            link = self._whatsapp_link
            if error_text and ('wa.me' in link or 'api.whatsapp.com' in link):
                msg = urllib.parse.quote(f"Image Tea API Key Error Report:\n{error_text}")
                sep = '&' if '?' in link else '?'
                url = f"{link}{sep}text={msg}"
            else:
                url = link
            webbrowser.open(url)
        except Exception as e:
            QMessageBox.critical(self, "Report Error", f"Failed to open report link: {e}")

    def _open_buy_api_key_page(self):
        if not self._get_api_key_link:
            QMessageBox.warning(self, "Buy API Key", "No buy API key link configured.")
            return
        try:
            webbrowser.open(self._get_api_key_link)
        except Exception as e:
            QMessageBox.critical(self, "Buy API Key", f"Failed to open buy API key page: {e}")

    def _open_topup_dialog(self):
        try:
            app_cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "app_config.json")
            with open(app_cfg_path, 'r', encoding='utf-8') as f:
                app_cfg = json.load(f)
            topup_url = app_cfg['links']['get_api_key']
        except Exception as e:
            print(f"[AddApiKeyDialog] Failed to load topup URL: {e}")
            return
        from dialogs.topup_desainia_dialog import TopupDesainiaDialog
        dlg = TopupDesainiaDialog(topup_url)
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.exec()

    def _open_credit_usage_dialog(self, api_key, endpoint=''):
        from dialogs.credit_usage_dialog import CreditUsageDialog
        dlg = CreditUsageDialog(api_key, self, endpoint=endpoint)
        dlg.exec()

    def export_api_keys_csv(self):
        try:
            rows = self.db.get_all_api_keys()
        except Exception as e:
            print(f"Error fetching API keys for export: {e}")
            QMessageBox.critical(self, "Backup Keys", "Failed to fetch API Key data.")
            return
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        home_dir = os.path.expanduser("~")
        default_filename = f"Image_Tea_API_Keys_Backup_{now}.csv"
        default_path = os.path.join(home_dir, default_filename)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export API Keys to CSV",
            default_path,
            "CSV Files (*.csv);;All Files (*)"
        )
        if not file_path:
            return
        headers = ["Service", "API", "Endpoint", "Last Tested", "Note", "Status", "Model"]
        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
                writer.writerow(headers)
                for row in rows:
                    if isinstance(row, dict):
                        service = row.get("service")
                        api = row.get("api")
                        endpoint = row.get("provider_endpoint") or row.get('endpoint')
                        last_tested = row.get("last_tested")
                        note = row.get("note")
                        status = row.get("status")
                        model = row.get("model")
                    else:
                        service = row[0] if len(row) > 0 else ''
                        api = row[1] if len(row) > 1 else ''
                        note = row[2] if len(row) > 2 else ''
                        last_tested = row[3] if len(row) > 3 else ''
                        status = row[4] if len(row) > 4 else ''
                        model = row[5] if len(row) > 5 else ''
                        endpoint = row[6] if len(row) > 6 else ''
                    if isinstance(last_tested, (tuple, list)):
                        last_tested = " ".join(str(x) for x in last_tested)
                    try:
                        api_encoded = base64.b64encode(str(api).encode('utf-8')).decode('utf-8')
                    except Exception:
                        api_encoded = api
                    writer.writerow([service, api_encoded, endpoint or '', last_tested, note, status, model])
            QMessageBox.information(self, "Backup Keys", f"API Keys exported successfully to:\n{file_path}")
        except Exception as e:
            print(f"Error exporting API keys to CSV: {e}")
            QMessageBox.critical(self, "Backup Keys", "Failed to write CSV file.")

    def import_api_keys_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import API Keys from CSV",
            os.path.expanduser("~"),
            "CSV Files (*.csv);;All Files (*)"
        )
        if not file_path:
            return
        imported = 0
        skipped = 0
        try:
            with open(file_path, "r", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    service = row.get("Service")
                    api = row.get("API")
                    last_tested = row.get("Last Tested")
                    note = row.get("Note")
                    status = row.get("Status")
                    model = row.get("Model")
                    endpoint = row.get("Endpoint")
                    if not service or not api:
                        continue
                    try:
                        api = base64.b64decode(api.encode('utf-8')).decode('utf-8')
                    except Exception:
                        pass
                    exists = False
                    try:
                        db_rows = self.db.get_all_api_keys()
                        for db_row in db_rows:
                            if isinstance(db_row, dict):
                                if db_row.get("service") == service and db_row.get("api") == api:
                                    exists = True
                                    break
                            else:
                                if len(db_row) >= 2 and db_row[0] == service and db_row[1] == api:
                                    exists = True
                                    break
                    except Exception as e:
                        print(f"Error checking existing API key: {e}")
                    if exists:
                        skipped += 1
                        continue
                    try:
                        self.db.set_api_key(service, api, note, last_tested, status, model, provider_endpoint=endpoint)
                        imported += 1
                    except Exception as e:
                        print(f"Error saving API key: {e}")
            self._refresh_api_table()
            QMessageBox.information(self, "Import Keys", f"Import finished.\nImported: {imported}\nSkipped (already exists): {skipped}")
        except Exception as e:
            print(f"Error importing API keys from CSV: {e}")
            QMessageBox.critical(self, "Import Keys", "Failed to import API keys from CSV.")

    def test_all_api_keys(self):
        if self._test_all_running:
            return
        self._test_all_running = True
        self._test_all_results = []
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(0)
        self.progress_bar.setMinimum(0)
        self.test_all_btn.setEnabled(False)
        self._test_all_index = 0
        try:
            self._test_all_rows = self.db.get_all_api_keys()
        except Exception as e:
            print(f"Error fetching API keys for test all: {e}")
            self._test_all_rows = []
        self._test_all_next()

    def _test_all_next(self):
        if self._test_all_index >= len(self._test_all_rows):
            self._stop_blinking()
            self.progress_bar.setVisible(False)
            self.test_all_btn.setEnabled(True)
            self._test_all_running = False
            self._refresh_api_table()
            total = len(self._test_all_rows)
            ok = sum(1 for r in self._test_all_results if r[1] == "success")
            fail = total - ok
            QMessageBox.information(self, "Test All API Keys", f"Tested {total} API keys.\nSuccess: {ok}\nFailed: {fail}")
            return
        row = self._test_all_rows[self._test_all_index]
        if isinstance(row, dict):
            service = row["service"]
            api = row["api"]
            note = row.get("note")
            model = row.get("model")
        else:
            if len(row) == 7:
                service, api, note, last_tested, status, model, endpoint = row
            elif len(row) == 6:
                service, api, note, last_tested, status, model = row
            elif len(row) == 5:
                service, api, note, last_tested, status = row
                model = ""
            else:
                service, api, note, last_tested = row
                status = ""
                model = ""
        if not model:
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            provider_endpoint = row.get('provider_endpoint') if isinstance(row, dict) else (row[6] if len(row) > 6 else None)
            self.db.set_api_key(service, api, note, now, "invalid", model, provider_endpoint=provider_endpoint)
            self._test_all_results.append((api, "fail"))
            self._set_row_status_color(self._test_all_index, "invalid")
            self._test_all_index += 1
            self._test_all_next()
            return
        self._row_testing = self._test_all_index
        self._blink_state = False
        self._blink_timer.start(300)
        provider_endpoint = None
        if isinstance(row, dict):
            provider_endpoint = row.get('provider_endpoint') or row.get('endpoint')
        else:
            provider_endpoint = row[6] if len(row) > 6 else None
        self._test_all_thread = ApiKeyTestThread(api, service, model, provider_endpoint)
        self._test_all_thread.result.connect(lambda status, svc, text, idx=self._test_all_index: self._on_test_all_result(idx, status, svc, text))
        self._test_all_thread.finished.connect(self._test_all_blink_stop_and_next)
        self._test_all_thread.start()

    def _test_all_blink_stop_and_next(self):
        self._stop_blinking()
        if self._test_all_index < len(self._test_all_results):
            status = self._test_all_results[self._test_all_index][1]
            self._set_row_status_color(self._test_all_index, status)
        self._test_all_index += 1
        self._test_all_next()

    def _set_row_status_color(self, row_idx, status):
        if status == "success":
            color = QColor(theme.get_color('success'))
            color.setAlpha(int(0.4 * 255))
            brush = QBrush(color)
        elif status == "invalid" or status == "fail":
            color = QColor(theme.get_color('error'))
            color.setAlpha(int(0.4 * 255))
            brush = QBrush(color)
        else:
            brush = None
        if brush:
            for col in range(6):
                item = self.api_table.item(row_idx, col)
                if item:
                    item.setBackground(brush)
        else:
            for col in range(6):
                item = self.api_table.item(row_idx, col)
                if item:
                    item.setBackground(QBrush())

    def _on_test_all_result(self, idx, status, service, text):
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        row = self._test_all_rows[idx]
        if isinstance(row, dict):
            api = row["api"]
            note = row.get("note")
            model = row.get("model")
        else:
            if len(row) == 7:
                service, api, note, last_tested, st, model, endpoint = row
            elif len(row) == 6:
                service, api, note, last_tested, st, model = row
            elif len(row) == 5:
                service, api, note, last_tested, st = row
                model = ""
            else:
                service, api, note, last_tested = row
                st = ""
                model = ""
        provider_endpoint = row.get('provider_endpoint') if isinstance(row, dict) else (row[6] if len(row) > 6 else None)
        self.db.set_api_key(service, api, note, now, "active" if status == "success" else "invalid", model, provider_endpoint=provider_endpoint)
        self._test_all_results.append((api, status))
