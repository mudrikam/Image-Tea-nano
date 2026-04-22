from PySide6.QtWidgets import QWidget, QHBoxLayout, QComboBox, QLabel, QSpacerItem, QSizePolicy, QPushButton
from PySide6.QtCore import Signal, Slot, QUrl
from PySide6.QtGui import QDesktopServices
from dialogs.add_api_key_dialog import AddApiKeyDialog
import qtawesome as qta
import os
import json
from ui.theme_system import theme

class ApiKeySectionWidget(QWidget):
    api_key_changed = Signal(str, str, str)  # api_key, service, model

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.api_key = None
        self.selected_service = None
        self.selected_model_name = None
        self.api_key_map = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.model_combo = QComboBox()
        self.model_combo.setEditable(False)
        self.model_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.model_combo.setFixedWidth(120)
        self.model_combo.setToolTip("Select the model/service to filter API keys")
        layout.addWidget(self.model_combo)

        self.api_key_combo = QComboBox()
        self.api_key_combo.setEditable(False)
        self.api_key_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.api_key_combo.setToolTip("Select the API key to use for the selected model")
        self.api_key_combo.setMaximumWidth(550)
        layout.addWidget(self.api_key_combo)

        self.tested_label = QLabel()
        self.tested_label.setText(" - | -")
        self.tested_label.setToolTip(
            "This application requires an API key to function."
        )
        layout.addWidget(self.tested_label)

        self.join_member_btn = QPushButton("Join Member")
        self.join_member_btn.setVisible(False)
        self.join_member_btn.setMinimumWidth(120)
        try:
            self.join_member_btn.setIcon(qta.icon('fa6s.user-check', color=theme.get_color('white')))
        except Exception:
            pass
        self.join_member_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.get_color('primary')};
                color: {theme.get_color('white')};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {theme.get_color('primary_hover')};
            }}
        """)
        self.join_member_btn.setToolTip(
            "Join as a member to generate metadata without needing your own API key."
        )
        app_cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "app_config.json")
        with open(app_cfg_path, 'r', encoding='utf-8') as f:
            app_cfg = json.load(f)
        register_member_link = app_cfg['links']['register_member']
        self.join_member_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(register_member_link)))
        layout.addWidget(self.join_member_btn)

        self.add_api_btn = QPushButton("Add API Key")
        try:
            self.add_api_btn.setIcon(qta.icon('fa6s.plus'))
        except Exception:
            pass
        self.add_api_btn.setMinimumWidth(110)
        try:
            self.add_api_btn.setStyleSheet("")
            self.add_api_btn.setFlat(False)
        except Exception:
            pass
        self.add_api_btn.setToolTip("Add a new API Key")
        self.add_api_btn.setVisible(False)
        self.add_api_btn.clicked.connect(lambda: self._open_add_api_dialog())
        layout.addWidget(self.add_api_btn)

        self.get_api_btn = QPushButton("Get API Key Here")
        self.get_api_btn.setVisible(False)
        self.get_api_btn.setMinimumWidth(140)
        try:
            self.get_api_btn.setIcon(qta.icon('fa6s.key'))
        except Exception:
            pass
        try:
            self.get_api_btn.setStyleSheet("")
            self.get_api_btn.setFlat(False)
        except Exception:
            pass
        self.get_api_btn.setToolTip(
            "This application requires an API key to function."
        )
        get_api_link = app_cfg['links']['get_api_key']
        self.get_api_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(get_api_link)))
        layout.addWidget(self.get_api_btn)

        layout.addItem(QSpacerItem(24, 1, QSizePolicy.Expanding, QSizePolicy.Minimum))

        try:
            height = self.add_api_btn.sizeHint().height()
            if not height or height < 1:
                height = self.add_api_btn.height()
            self.add_api_btn.setFixedHeight(height + 4)
            self.add_api_btn.setMinimumHeight(height + 4)
            self.join_member_btn.setFixedHeight(height)
            self.join_member_btn.setMinimumHeight(height)
            self.get_api_btn.setFixedHeight(height + 4)
            self.get_api_btn.setMinimumHeight(height + 4)
        except Exception:
            pass

        self.model_combo.installEventFilter(self)
        self.api_key_combo.installEventFilter(self)

        self.model_combo.currentIndexChanged.connect(self._on_model_combo_changed)
        self.api_key_combo.currentIndexChanged.connect(self._on_api_combo_changed)

        self._populate_models()
        if self.model_combo.count() > 0:
            self._on_model_combo_changed(self.model_combo.currentIndex())
        else:
            self._refresh_api_key_combo(None)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj == self.model_combo and event.type() == QEvent.MouseButtonPress:
            self._populate_models()
        if obj == self.api_key_combo and event.type() == QEvent.MouseButtonPress:
            selected_model = self.model_combo.currentText()
            self._refresh_api_key_combo(selected_model)
        return super().eventFilter(obj, event)

    def _populate_models(self):
        api_keys = self.db.get_all_api_keys()
        model_set = []
        for entry in api_keys:
            if not entry:
                continue
            service = entry[0]
            model = entry[5] if len(entry) > 5 else ''
            service_disp = service.lower() if service.lower() in ("openai", "gemini", "openrouter", "groq", "blackbox", "maia", "custom") else service
            if service_disp.capitalize() not in model_set:
                model_set.append(service_disp.capitalize())
        current_model = self.model_combo.currentText()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for model in model_set:
            self.model_combo.addItem(model)
        if current_model in model_set:
            self.model_combo.setCurrentText(current_model)
        self.model_combo.blockSignals(False)

    def _refresh_api_key_combo(self, selected_model=None):
        api_keys = self.db.get_all_api_keys()
        self.api_key_combo.blockSignals(True)
        self.api_key_combo.clear()
        self.api_key_map.clear()
        for entry in api_keys:
            if not entry:
                continue
            service = entry[0]
            api_key = entry[1] if len(entry) > 1 else ''
            note = entry[2] if len(entry) > 2 else ''
            last_tested = entry[3] if len(entry) > 3 else None
            status = entry[4] if len(entry) > 4 else ''
            model = entry[5] if len(entry) > 5 else ''
            endpoint = entry[6] if len(entry) > 6 else ''
            service_disp = service.lower() if service.lower() in ("openai", "gemini", "openrouter", "groq", "blackbox", "maia", "custom") else service
            if selected_model is None or service_disp.capitalize() == selected_model:
                if api_key and len(api_key) > 5:
                    masked_key = '*' * (len(api_key) - 5) + api_key[-5:]
                else:
                    masked_key = api_key
                label = f"{masked_key} ({note})" if note else masked_key
                self.api_key_combo.addItem(label, api_key)
                self.api_key_map[api_key] = {'service': service_disp, 'note': note, 'last_tested': last_tested, 'model': model, 'endpoint': endpoint}
        self.api_key_combo.blockSignals(False)
        if self.api_key_combo.count() > 0:
            self.api_key_combo.setCurrentIndex(0)
            api_key = self.api_key_combo.currentData()
            self.api_key = api_key
            last_tested = self.api_key_map[api_key]['last_tested']
            model = self.api_key_map[api_key]['model']
            self.tested_label.setText(f"{last_tested if last_tested else '-'} | {model if model else '-'}")
            self.tested_label.setVisible(True)
            self.get_api_btn.setVisible(False)
            self.join_member_btn.setVisible(False)
            try:
                self.add_api_btn.setVisible(False)
            except Exception:
                pass
            self.selected_service = self.api_key_map[api_key]['service']
            self.selected_model_name = self.api_key_map[api_key]['model']
            self.tested_label.setToolTip(
                "This application requires an API key to function."
            )
            self.api_key_changed.emit(self.api_key, self.selected_service, self.selected_model_name)
        else:
            self.api_key = None
            self.selected_service = None
            self.selected_model_name = None
            self.tested_label.setVisible(False)
            self.get_api_btn.setVisible(True)
            self.join_member_btn.setVisible(True)
            try:
                self.add_api_btn.setVisible(True)
            except Exception:
                pass
            self.api_key_changed.emit('', '', '')

    def _open_add_api_dialog(self):
        try:
            dlg = AddApiKeyDialog(self)
            result = dlg.exec()
            self.refresh()
        except Exception as e:
            print(f"Failed to open AddApiKeyDialog: {e}")

    @Slot(int)
    def _on_model_combo_changed(self, idx):
        selected_model = self.model_combo.currentText()
        self._refresh_api_key_combo(selected_model)

    @Slot(int)
    def _on_api_combo_changed(self, idx):
        api_key = self.api_key_combo.itemData(idx)
        if api_key and api_key in self.api_key_map:
            self.api_key = api_key
            self.selected_service = self.api_key_map[api_key]['service']
            self.selected_model_name = self.api_key_map[api_key]['model']
            last_tested = self.api_key_map[api_key]['last_tested']
            model = self.api_key_map[api_key]['model']
            self.tested_label.setText(f"{last_tested if last_tested else '-'} | {model if model else '-'}")
            self.tested_label.setVisible(True)
            self.get_api_btn.setVisible(False)
            self.join_member_btn.setVisible(False)
            try:
                self.add_api_btn.setVisible(False)
            except Exception:
                pass
            self.tested_label.setToolTip(
                "This application requires an API key to function."
            )
            self.api_key_changed.emit(self.api_key, self.selected_service, self.selected_model_name)
        else:
            self.api_key = None
            self.selected_service = None
            self.selected_model_name = None
            self.tested_label.setVisible(False)
            self.get_api_btn.setVisible(True)
            self.join_member_btn.setVisible(True)
            try:
                self.add_api_btn.setVisible(True)
            except Exception:
                pass
            self.api_key_changed.emit('', '', '')

    def get_current_api_key(self):
        return self.api_key

    def get_current_service(self):
        return self.selected_service

    def get_current_model(self):
        return self.selected_model_name

    def set_current_api_by_details(self, api_key, service, model, skip_refresh=False):
        """Set the current API key selection by matching api_key, service, and model"""
        if service:
            service_lower = service.lower()
            if service_lower in ('openai', 'gemini', 'groq', 'blackbox', 'maia', 'custom'):
                service_capitalized = service_lower.capitalize()
            else:
                service_capitalized = service
        else:
            service_capitalized = ""
        
        service_found = False
        for i in range(self.model_combo.count()):
            if self.model_combo.itemText(i) == service_capitalized:
                self.model_combo.blockSignals(True)
                self.model_combo.setCurrentIndex(i)
                self.model_combo.blockSignals(False)
                if not skip_refresh:
                    self._refresh_api_key_combo(service_capitalized)
                service_found = True
                break
        
        if not service_found:
            print(f"Service '{service_capitalized}' not found in model combo")
            return
        
        api_found = False
        for i in range(self.api_key_combo.count()):
            combo_api_key = self.api_key_combo.itemData(i)
            if combo_api_key == api_key:
                self.api_key_combo.blockSignals(True)
                self.api_key_combo.setCurrentIndex(i)
                self.api_key_combo.blockSignals(False)
                self._on_api_combo_changed(i)
                api_found = True
                break
        
        if not api_found:
            print(f"API key ***{api_key[-5:] if api_key and len(api_key) >= 5 else api_key} not found in combo")

    def refresh(self):
        current_api_key = self.api_key
        current_service = self.selected_service
        current_model = self.selected_model_name
        
        self._populate_models()
        
        if current_api_key and current_service:
            selected_model = self.model_combo.currentText()
            self._refresh_api_key_combo(selected_model)
            self.set_current_api_by_details(current_api_key, current_service, current_model, skip_refresh=True)
        else:
            if self.model_combo.count() > 0:
                self._on_model_combo_changed(self.model_combo.currentIndex())
            else:
                self._refresh_api_key_combo(None)
