from PySide6.QtWidgets import QWidget, QHBoxLayout, QComboBox, QLabel, QSpacerItem, QSizePolicy, QPushButton
from PySide6.QtCore import Signal, Slot, QUrl
from PySide6.QtGui import QDesktopServices
from dialogs.add_api_key_dialog import AddApiKeyDialog
import qtawesome as qta

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
        self.get_api_btn = QPushButton("Get FREE API Key")
        self.get_api_btn.setVisible(False)
        self.get_api_btn.setMinimumWidth(140)
        # Add green color and icon to make the button more visible
        try:
            self.get_api_btn.setIcon(qta.icon('fa6s.key', color='#FFFFFF'))
        except Exception:
            pass
        self.get_api_btn.setStyleSheet("""
            QPushButton {
                background-color: #4e9e20;
                color: #ffffff;
                border-radius: 4px;
                padding: 6px 8px;
            }
            QPushButton:hover {
                background-color: #3f8a1a;
            }
        """)
        self.get_api_btn.setToolTip(
            "This application requires an API key to function.\n"
            "For Gemini, Google provides free API keys at https://aistudio.google.com/."
        )
        self.get_api_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://aistudio.google.com/api-keys")))
        self.tested_label.setText(" - | -")
        self.tested_label.setToolTip(
            "This application requires an API key to function.\n"
            "For Gemini, Google provides free API keys at https://aistudio.google.com/api-keys"
        )
        layout.addWidget(self.tested_label)
        layout.addWidget(self.get_api_btn)

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
        try:
            height = self.get_api_btn.sizeHint().height()
            if not height or height < 1:
                height = self.get_api_btn.height()
            self.add_api_btn.setFixedHeight(height + 4)
            self.add_api_btn.setMinimumHeight(height + 4)
        except Exception:
            pass
        layout.addWidget(self.add_api_btn)
        layout.addItem(QSpacerItem(24, 1, QSizePolicy.Expanding, QSizePolicy.Minimum))

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
            service, api_key, note, last_tested, status, model = entry
            service_disp = service.lower() if service.lower() in ("openai", "gemini") else service
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
            service, api_key, note, last_tested, status, model = entry
            service_disp = service.lower() if service.lower() in ("openai", "gemini") else service
            if selected_model is None or service_disp.capitalize() == selected_model:
                if api_key and len(api_key) > 5:
                    masked_key = '*' * (len(api_key) - 5) + api_key[-5:]
                else:
                    masked_key = api_key
                label = f"{masked_key} ({note})" if note else masked_key
                self.api_key_combo.addItem(label, api_key)
                self.api_key_map[api_key] = {'service': service_disp, 'note': note, 'last_tested': last_tested, 'model': model}
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
            try:
                self.add_api_btn.setVisible(False)
            except Exception:
                pass
            self.selected_service = self.api_key_map[api_key]['service']
            self.selected_model_name = self.api_key_map[api_key]['model']
            self.tested_label.setToolTip(
                "This application requires an API key to function.\n"
                "For Gemini, Google provides free API keys at https://aistudio.google.com/."
            )
            self.api_key_changed.emit(self.api_key, self.selected_service, self.selected_model_name)
        else:
            self.api_key = None
            self.selected_service = None
            self.selected_model_name = None
            self.tested_label.setVisible(False)
            self.get_api_btn.setVisible(True)
            try:
                self.add_api_btn.setVisible(True)
            except Exception:
                pass
            self.api_key_changed.emit('', '', '')

    def _open_add_api_dialog(self):
        try:
            dlg = AddApiKeyDialog(self)
            dlg.exec()
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
            try:
                self.add_api_btn.setVisible(False)
            except Exception:
                pass
            self.tested_label.setToolTip(
                "This application requires an API key to function.\n"
                "For Gemini, Google provides free API keys at https://aistudio.google.com/."
            )
            self.api_key_changed.emit(self.api_key, self.selected_service, self.selected_model_name)
        else:
            self.api_key = None
            self.selected_service = None
            self.selected_model_name = None
            self.tested_label.setVisible(False)
            self.get_api_btn.setVisible(True)
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

    def set_current_api_by_details(self, api_key, service, model):
        """Set the current API key selection by matching api_key, service, and model"""
        service_capitalized = service.capitalize() if service else ""
        
        # First set the correct service in model combo
        for i in range(self.model_combo.count()):
            if self.model_combo.itemText(i) == service_capitalized:
                self.model_combo.blockSignals(True)
                self.model_combo.setCurrentIndex(i)
                self.model_combo.blockSignals(False)
                self._refresh_api_key_combo(service_capitalized)
                break
        
        # Then set the correct API key
        for i in range(self.api_key_combo.count()):
            combo_api_key = self.api_key_combo.itemData(i)
            if combo_api_key == api_key:
                self.api_key_combo.blockSignals(True)
                self.api_key_combo.setCurrentIndex(i)
                self.api_key_combo.blockSignals(False)
                self._on_api_combo_changed(i)
                break

    def refresh(self):
        self._populate_models()
        if self.model_combo.count() > 0:
            self._on_model_combo_changed(self.model_combo.currentIndex())
        else:
            self._refresh_api_key_combo(None)
