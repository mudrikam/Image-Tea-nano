from PySide6.QtCore import QThread, Signal, Qt, QPoint, QTimer
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QProgressBar, QSizePolicy, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QMenu, QApplication, QWidget, QFileDialog, QListWidget, QListWidgetItem, QInputDialog, QPlainTextEdit, QToolTip
from PySide6.QtGui import QColor, QBrush, QAction
from database.db_operation import ImageTeaDB
import datetime
import qtawesome as qta
import json
import os
import csv
import re
import webbrowser
import urllib.parse
import base64

class ApiKeyTestThread(QThread):
    result = Signal(str, str, object)
    def __init__(self, api_key, service=None, model=None):
        super().__init__()
        self.api_key = api_key
        self.service = service
        self.model = model
    def run(self):
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
                    client = OpenAI(api_key=self.api_key, base_url="https://openrouter.ai/api/v1")
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
        self.result.emit('fail', None, None)


class ModelManagerDialog(QDialog):
    def __init__(self, model_list: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Model Manager")
        self.setFixedWidth(520)
        self.model_list = {k: list(v) for k, v in (model_list or {}).items()}
        layout = QVBoxLayout()
        openrouter_hint = QLabel("If you're using OpenRouter, please select 'OpenAI' for Service.")
        openrouter_hint.setWordWrap(True)
        openrouter_hint.setStyleSheet("font-size:10px; color: #696969;")
        layout.addWidget(openrouter_hint)
        top_layout = QHBoxLayout()
        self.service_list = QListWidget()
        self.service_list.setFixedWidth(140)
        
        services = sorted(self.model_list.keys()) if isinstance(self.model_list, dict) else []
        if not services:
            services = ['gemini', 'openai']
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
        service = service_item.text().lower()
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
        service = service_item.text().lower()
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
        service = service_item.text().lower()
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
        service = service_item.text().lower()
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
        service = service_item.text().lower()
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
        cfg['model_list'] = self.model_list
        try:
            with open(cfg_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(self, 'Save Models', f'Failed to save model list: {e}')
            return
        self.accept()

class AddApiKeyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add API Key")
        self.setFixedWidth(620)
        self.db = ImageTeaDB()
        self._label_icon_color = "#666"
        layout = QVBoxLayout()
        label_width = 80
        self.model_list = {}
        ai_prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "ai_config.json")
        try:
            with open(ai_prompt_path, "r", encoding="utf-8") as f:
                ai_prompt = json.load(f)
                self.model_list = ai_prompt["model_list"]
        except Exception as e:
            print(f"Failed to load model list: {e}")
            self.model_list = {}
        service_layout = QHBoxLayout()
        _service_label_widget, service_label = self._create_icon_label_widget("Service:", 'fa6s.gears', label_width)
        service_label.setToolTip("Select the service/model for this API key")
        self.service_combo = QComboBox()
        self.service_combo.addItem("Gemini")
        self.service_combo.addItem("OpenAI")
        self.service_combo.addItem("OpenRouter")
        self.service_combo.addItem("Groq")
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
        self.model_manager_btn = QPushButton()
        self.model_manager_btn.setIcon(qta.icon('fa6s.gears'))
        self.model_manager_btn.setFixedWidth(32)
        self.model_manager_btn.setToolTip('Manage models')
        self.model_manager_btn.setFocusPolicy(Qt.NoFocus)
        self.model_manager_btn.clicked.connect(self._open_model_manager)
        model_layout.addWidget(_model_label_widget)
        model_layout.addWidget(self.model_combo)
        model_layout.addWidget(self.model_manager_btn)
        layout.addLayout(model_layout)
        self._refresh_model_combo()
        key_layout = QHBoxLayout()
        _key_label_widget, self.key_label = self._create_icon_label_widget("API Key:", 'fa6s.key', label_width)
        self.key_label.setToolTip("Enter your API key here")
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("Enter API Key")
        self.key_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.key_edit.setToolTip("Enter your API key here")
        # Mask API key by default and track visibility
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

        csv_btn_layout = QHBoxLayout()
        self.test_all_btn = QPushButton()
        self.test_all_btn.setText("Test All")
        self.test_all_btn.setIcon(qta.icon('fa6s.list-check'))
        self.test_all_btn.setIconSize(self.test_all_btn.iconSize())
        self.test_all_btn.setToolTip("Test all API keys sequentially")
        self.sort_combo = QComboBox()
        self.sort_combo.setToolTip("Filter / Sort API table")
        try:
            rows = self.db.get_all_api_keys()
            services = sorted({(r[0] if not isinstance(r, dict) else r.get('service')) for r in rows if r and (r[0] if not isinstance(r, dict) else r.get('service'))})
        except Exception as e:
            print(f"Error fetching services for sort combo: {e}")
            services = []
        sort_items = ["All"]
        display_service_map = {'openai': 'OpenAI', 'openrouter': 'OpenRouter', 'gemini': 'Gemini', 'groq': 'Groq'}
        for s in services:
            try:
                svc_display = display_service_map.get(str(s).lower(), str(s).capitalize())
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
        self.export_csv_btn = QPushButton()
        self.export_csv_btn.setText("Export CSV")
        self.export_csv_btn.setIcon(qta.icon('fa6s.file-csv'))
        self.export_csv_btn.setIconSize(self.export_csv_btn.iconSize())
        self.export_csv_btn.setToolTip("Export API key list to CSV")
        self.import_csv_btn = QPushButton()
        self.import_csv_btn.setText("Import CSV")
        self.import_csv_btn.setIcon(qta.icon('fa6s.file-import'))
        self.import_csv_btn.setIconSize(self.import_csv_btn.iconSize())
        self.import_csv_btn.setToolTip("Import API key list from CSV")
        self.delete_all_btn = QPushButton()
        self.delete_all_btn.setText("Delete All")
        self.delete_all_btn.setIcon(qta.icon('fa6s.trash'))
        self.delete_all_btn.setToolTip("Delete all API keys (cannot be undone)")
        self.delete_all_btn.setFixedWidth(100)
        self.delete_all_btn.clicked.connect(self._delete_all_api_keys)
        csv_btn_layout.addWidget(self.test_all_btn)
        csv_btn_layout.addWidget(self.sort_combo)
        csv_btn_layout.addWidget(self.refresh_btn)
        csv_btn_layout.addWidget(self.export_csv_btn)
        csv_btn_layout.addWidget(self.import_csv_btn)
        csv_btn_layout.addWidget(self.delete_all_btn)
        csv_btn_layout.addStretch()
        layout.addLayout(csv_btn_layout)

        self.api_table = QTableWidget()
        self.api_table.setColumnCount(6)
        self.api_table.setHorizontalHeaderLabels(["Service", "API", "Last Tested", "Model", "Note", "Actions"])
        self.api_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.api_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.api_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.api_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.api_table.setMinimumHeight(100)
        self.api_table.setToolTip("List of all API keys you have added")
        header = self.api_table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        self.api_table.setSortingEnabled(True)
        layout.addWidget(self.api_table)
        self._row_testing = None
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink_row)
        self._blink_state = False
        self._refresh_api_table()
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.progress_bar.setToolTip("Shows progress when testing API key")
        layout.addWidget(self.progress_bar)
        # Raw error display moved to a dedicated dialog; in-line widgets removed
        btn_layout = QHBoxLayout()
        self.test_and_save_btn = QPushButton()
        self.test_and_save_btn.setText("Test and Save")
        self.test_and_save_btn.setIcon(qta.icon('fa6s.play'))
        self.test_and_save_btn.setIconSize(self.test_and_save_btn.iconSize())
        self.test_and_save_btn.setMinimumHeight(32)
        self.test_and_save_btn.setToolTip("Test the API key and save it if valid")
        self.get_api_key_btn = QPushButton()
        self.get_api_key_btn.setObjectName("get_api_key_btn")
        self.get_api_key_btn.setText("Get API Key")
        self.get_api_key_btn.setIcon(qta.icon('fa6s.cart-shopping', color='white'))
        self.get_api_key_btn.setIconSize(self.get_api_key_btn.iconSize())
        self.get_api_key_btn.setMinimumHeight(32)
        self.get_api_key_btn.setStyleSheet("""
            QPushButton#get_api_key_btn {
                background-color: #4e9e20;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton#get_api_key_btn:hover {
                background-color: #3f8a18;
            }
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
        try:
            self._load_app_links()
        except Exception as e:
            print(f"Failed to load app links in AddApiKeyDialog: {e}")
            self._whatsapp_link = None
            self._get_api_key_link = None

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
        service = self.service_combo.currentText().lower()
        self.model_combo.clear()
        if service == "gemini":
            models = self.model_list.get("gemini", [])
        elif service == "openai":
            models = self.model_list.get("openai", [])
        elif service == "openrouter":
            models = self.model_list.get("openrouter", [])
        elif service == "groq":
            models = self.model_list.get("groq", [])
        else:
            models = []
        for m in models:
            self.model_combo.addItem(m)
        if self.model_combo.count() > 0:
            self.model_combo.setCurrentIndex(0)

    def _refresh_api_table(self):
        
        try:
            rows = self.db.get_all_api_keys()
        except Exception as e:
            print(f"Error fetching API keys: {e}")
            raise

        
        normalized = []
        for r in rows:
            if isinstance(r, dict):
                normalized.append((r.get('service'), r.get('api'), r.get('note'), r.get('last_tested'), r.get('status'), r.get('model', '')))
            else:
                if len(r) == 6:
                    normalized.append((r[0], r[1], r[2], r[3], r[4], r[5]))
                elif len(r) == 5:
                    normalized.append((r[0], r[1], r[2], r[3], r[4], ''))
                else:
                    
                    normalized.append((r[0], r[1], r[2], r[3] if len(r) > 3 else None, '', ''))

        
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
        for row_idx, (service, api, note, last_tested, status, model) in enumerate(display):
            if isinstance(last_tested, (tuple, list)):
                last_tested = " ".join(str(x) for x in last_tested)
            
            
            tooltip_lines = []
            tooltip_lines.append(f"Service: {service}")
            truncated_api = self._truncate_api_key(api)
            tooltip_lines.append(f"API Key: {truncated_api}")
            tooltip_lines.append(f"Model: {model or 'N/A'}")
            tooltip_lines.append(f"Last Tested: {last_tested or 'Never'}")
            tooltip_lines.append(f"Status: {status or 'Unknown'}")
            tooltip_lines.append(f"Note: {note or 'N/A'}")
            tooltip_text = "\n".join(tooltip_lines)
            
            display_service_map = {'openai': 'OpenAI', 'openrouter': 'OpenRouter', 'gemini': 'Gemini', 'groq': 'Groq'}
            svc_display = display_service_map.get(str(service).lower(), str(service))
            service_item = QTableWidgetItem(svc_display)
            service_item.setToolTip(tooltip_text)
            self.api_table.setItem(row_idx, 0, service_item)
            
            api_item = QTableWidgetItem(str(api))
            api_item.setToolTip(tooltip_text)
            self.api_table.setItem(row_idx, 1, api_item)
            
            last_tested_item = QTableWidgetItem(str(last_tested))
            last_tested_item.setToolTip(tooltip_text)
            self.api_table.setItem(row_idx, 2, last_tested_item)
            
            model_item = QTableWidgetItem(str(model or ''))
            model_item.setToolTip(tooltip_text)
            self.api_table.setItem(row_idx, 3, model_item)
            
            note_item = QTableWidgetItem(str(note))
            note_item.setToolTip(tooltip_text)
            self.api_table.setItem(row_idx, 4, note_item)
            
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
            action_layout.addStretch()
            self.api_table.setCellWidget(row_idx, 5, action_widget)
            if status == "active":
                brush = QBrush(QColor(91, 184, 16, int(0.4 * 255)))
            elif status == "invalid":
                brush = QBrush(QColor(255, 41, 41, int(0.4 * 255)))
            else:
                brush = None
            if brush:
                for col in range(5):
                    item = self.api_table.item(row_idx, col)
                    if item:
                        item.setBackground(brush)
        
        self.api_table.setSortingEnabled(True)
        self._stop_blinking()

    def _test_api_key_row(self, row):
        if self._row_testing is not None:
            return
        service_item = self.api_table.item(row, 0)
        api_item = self.api_table.item(row, 1)
        if not service_item or not api_item:
            return
        service = service_item.text().lower()
        api_key = api_item.text().strip()
        model = None
        
        try:
            rows = self.db.get_all_api_keys()
            for r in rows:
                if isinstance(r, dict):
                    if r.get('api') == api_key and str(r.get('service')).lower() == service:
                        model = r.get('model')
                        break
                else:
                    if len(r) >= 2 and r[1] == api_key and str(r[0]).lower() == service:
                        if len(r) == 6:
                            model = r[5]
                        elif len(r) == 5:
                            
                            model = r[5] if len(r) > 5 else None
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
        self._test_thread_row = ApiKeyTestThread(api_key, service, model)
        self._test_thread_row.result.connect(lambda status, service, text: self._on_test_row_result(row, status, service, text))
        self._test_thread_row.finished.connect(lambda: self._stop_blinking())
        self._test_thread_row.start()

    def _on_test_row_result(self, row, status, service, text):
        self._stop_blinking()
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
        widget = self.api_table.cellWidget(row, 5)
        if widget:
            layout = widget.layout()
            if layout and layout.count() > btn_idx:
                return layout.itemAt(btn_idx).widget()
        return None

    def _blink_row(self):
        if self._row_testing is None:
            return
        color1 = QColor(255, 255, 128, 180)
        color2 = QColor(255, 255, 255, 0)
        color = color1 if self._blink_state else color2
        for col in range(5):
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
            for col in range(5):
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
        service = service_item.text().lower()
        api_key = api_item.text().strip()
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

    def _on_api_table_row_clicked(self, row, column):
        if column == 5:
            return
        service_item = self.api_table.item(row, 0)
        api_item = self.api_table.item(row, 1)
        model_item = self.api_table.item(row, 3)
        note_item = self.api_table.item(row, 4)
        if service_item and api_item:
            service_text = service_item.text()
            api_text = api_item.text()
            model_text = model_item.text() if model_item else ""
            note_text = note_item.text() if note_item else ""
            self.key_edit.setText(api_text)
            self.note_edit.setText(note_text)
            self.service_combo.setCurrentText(service_text.capitalize())
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
                        
                        service_key = service_text.lower()
                        if service_key not in self.model_list:
                            self.model_list[service_key] = []
                        if model_text not in self.model_list[service_key]:
                            self.model_list[service_key].append(model_text)
                            
                            ai_prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "ai_config.json")
                            try:
                                with open(ai_prompt_path, "r", encoding="utf-8") as f:
                                    ai_config = json.load(f)
                                ai_config["model_list"] = self.model_list
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
            if service_text.lower() == "openai":
                self._detected_service = "openai"
            elif service_text.lower() == "openrouter":
                self._detected_service = "openrouter"
            elif service_text.lower() == "gemini":
                self._detected_service = "gemini"
            elif service_text.lower() == "groq":
                self._detected_service = "groq"
            else:
                self._detected_service = None

    def _on_key_edit_changed(self, text):
        api_key = text.strip()
        service = None
        ak = api_key or ''
        lower = ak.lower()
        # Groq keys start with 'gsk_'
        if lower.startswith('gsk_') or lower.startswith('gsk-'):
            service = 'groq'
        elif re.match(r"^sk-?or-", ak, re.IGNORECASE):
            service = 'openrouter'
        elif ak.startswith('sk-') and len(ak) > 40:
            service = 'openai'
        elif len(ak) > 30 and 'AIza' in ak:
            service = 'gemini'
        else:
            service = None
        if service == 'openai':
            self.service_combo.setCurrentText("OpenAI")
        elif service == 'openrouter':
            self.service_combo.setCurrentText("OpenRouter")
        elif service == 'gemini':
            self.service_combo.setCurrentText("Gemini")
        elif service == 'groq':
            self.service_combo.setCurrentText("Groq")
        self._detected_service = service
        self._api_key_valid = False
        self.progress_bar.setVisible(False)

    def _on_service_combo_changed(self, idx):
        if self.service_combo.currentText() == "OpenAI":
            self._detected_service = 'openai'
        elif self.service_combo.currentText() == "OpenRouter":
            self._detected_service = 'openrouter'
        elif self.service_combo.currentText() == "Gemini":
            self._detected_service = 'gemini'
        elif self.service_combo.currentText() == "Groq":
            self._detected_service = 'groq'
        else:
            self._detected_service = None
        self._refresh_model_combo()
        self._api_key_valid = False

    def _on_model_combo_changed(self, idx):
        try:
            self._api_key_valid = False
        except Exception as e:
            print(f"[AddApiKeyDialog] Error handling model combo change: {e}")

    def _open_model_manager(self):
        dlg = ModelManagerDialog(self.model_list, self)
        if dlg.exec():
            
            ai_prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "ai_config.json")
            try:
                with open(ai_prompt_path, "r", encoding="utf-8") as f:
                    ai_prompt = json.load(f)
                    self.model_list = ai_prompt.get("model_list", {})
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
        self._test_thread = ApiKeyTestThread(api_key, service, model)
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
        service = self._detected_service
        model = self.model_combo.currentText() if self.model_combo.count() > 0 else None
        if not api_key:
            QMessageBox.warning(self, "Input Error", "API Key cannot be empty.")
            return
        # Fallback detection in case _detected_service wasn't set by the live detection
        if not service:
            ak = api_key.strip()
            ak_lower = ak.lower()
            if ak_lower.startswith('gsk_') or ak_lower.startswith('gsk-'):
                service = 'groq'
            elif re.match(r"^sk-?or-", ak, re.IGNORECASE):
                service = 'openrouter'
            elif ak.startswith('sk-') and len(ak) > 40:
                service = 'openai'
            elif len(ak) > 30 and 'AIza' in ak:
                service = 'gemini'
        if not service:
            QMessageBox.warning(self, "Input Error", "API Key format not recognized as Gemini, OpenAI, OpenRouter, or Groq.")
            return
        if not model:
            QMessageBox.warning(self, "Input Error", "Model must be selected.")
            return
        self.progress_bar.setVisible(True)
        self.test_and_save_btn.setEnabled(False)
        self._test_thread = ApiKeyTestThread(api_key, service, model)
        self._test_thread.result.connect(lambda status, service, text: self._on_test_and_save_result(status, service, text, note, model))
        self._test_thread.finished.connect(lambda: self.test_and_save_btn.setEnabled(True))
        self._test_thread.finished.connect(lambda: self.progress_bar.setVisible(False))
        self._test_thread.start()

    def _on_test_and_save_result(self, status, service, text, note, model):
        if status == 'success':
            self._detected_service = service
            self._api_key_valid = True
            last_tested = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.db.set_api_key(service, self.key_edit.text().strip(), note, last_tested, status="active", model=model)
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
                        if len(row) == 6:
                            s, a, n, lt, st, m = row
                        elif len(row) == 5:
                            s, a, n, lt, st = row
                        else:
                            s, a, n, lt = row
                            st = ""
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
            self.db.set_api_key(service, self.key_edit.text().strip(), note, last_tested, status="invalid", model=model)
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
        vbox.addWidget(close_btn)
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
        mb = QMessageBox(self)
        mb.setWindowTitle("Delete All API Keys")
        mb.setText("Delete ALL API keys?\n\nThis action cannot be undone.")
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
        model_item = self.api_table.item(row, 3)
        note_item = self.api_table.item(row, 4)
        if not service_item or not api_item:
            return
        service_text = service_item.text()
        api_text = api_item.text()
        model_text = model_item.text() if model_item else ""
        note_text = note_item.text() if note_item else ""
        self.key_edit.setText(api_text)
        self.note_edit.setText(note_text)
        self.service_combo.setCurrentText(service_text.capitalize())
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
                    service_key = service_text.lower()
                    if service_key not in self.model_list:
                        self.model_list[service_key] = []
                    if model_text not in self.model_list[service_key]:
                        self.model_list[service_key].append(model_text)
                        ai_prompt_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "ai_config.json")
                        try:
                            with open(ai_prompt_path, "r", encoding="utf-8") as f:
                                ai_config = json.load(f)
                            ai_config["model_list"] = self.model_list
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
        if service_text.lower() == "openai":
            self._detected_service = "openai"
        elif service_text.lower() == "openrouter":
            self._detected_service = "openrouter"
        elif service_text.lower() == "gemini":
            self._detected_service = "gemini"
        elif service_text.lower() == "groq":
            self._detected_service = "groq"
        else:
            self._detected_service = None
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

    def export_api_keys_csv(self):
        try:
            rows = self.db.get_all_api_keys()
        except Exception as e:
            print(f"Error fetching API keys for export: {e}")
            QMessageBox.critical(self, "Export CSV", "Failed to fetch API Key data.")
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
        headers = ["Service", "API", "Last Tested", "Note", "Status", "Model"]
        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
                writer.writerow(headers)
                for row in rows:
                    if isinstance(row, dict):
                        service = row.get("service")
                        api = row.get("api")
                        last_tested = row.get("last_tested")
                        note = row.get("note")
                        status = row.get("status")
                        model = row.get("model")
                    else:
                        if len(row) == 6:
                            service, api, note, last_tested, status, model = row
                        elif len(row) == 5:
                            service, api, note, last_tested, status = row
                            model = ""
                        else:
                            service, api, note, last_tested = row
                            status = ""
                            model = ""
                    if isinstance(last_tested, (tuple, list)):
                        last_tested = " ".join(str(x) for x in last_tested)
                    try:
                        api_encoded = base64.b64encode(str(api).encode('utf-8')).decode('utf-8')
                    except Exception:
                        api_encoded = api
                    writer.writerow([service, api_encoded, last_tested, note, status, model])
            QMessageBox.information(self, "Export CSV", f"API Keys exported successfully to:\n{file_path}")
        except Exception as e:
            print(f"Error exporting API keys to CSV: {e}")
            QMessageBox.critical(self, "Export CSV", "Failed to write CSV file.")

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
                        self.db.set_api_key(service, api, note, last_tested, status, model)
                        imported += 1
                    except Exception as e:
                        print(f"Error saving API key: {e}")
            self._refresh_api_table()
            QMessageBox.information(self, "Import CSV", f"Import finished.\nImported: {imported}\nSkipped (already exists): {skipped}")
        except Exception as e:
            print(f"Error importing API keys from CSV: {e}")
            QMessageBox.critical(self, "Import CSV", "Failed to import API keys from CSV.")

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
            if len(row) == 6:
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
            self.db.set_api_key(service, api, note, now, "invalid", model)
            self._test_all_results.append((api, "fail"))
            self._set_row_status_color(self._test_all_index, "invalid")
            self._test_all_index += 1
            self._test_all_next()
            return
        self._row_testing = self._test_all_index
        self._blink_state = False
        self._blink_timer.start(300)
        self._test_all_thread = ApiKeyTestThread(api, service, model)
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
            brush = QBrush(QColor(91, 184, 16, int(0.4 * 255)))
        elif status == "invalid" or status == "fail":
            brush = QBrush(QColor(255, 41, 41, int(0.4 * 255)))
        else:
            brush = None
        if brush:
            for col in range(5):
                item = self.api_table.item(row_idx, col)
                if item:
                    item.setBackground(brush)
        else:
            for col in range(5):
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
            if len(row) == 6:
                service, api, note, last_tested, st, model = row
            elif len(row) == 5:
                service, api, note, last_tested, st = row
                model = ""
            else:
                service, api, note, last_tested = row
                st = ""
                model = ""
        self.db.set_api_key(service, api, note, now, "active" if status == "success" else "invalid", model)
        self._test_all_results.append((api, status))
