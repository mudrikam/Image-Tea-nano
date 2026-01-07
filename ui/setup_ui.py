from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox, QDialog, QSpacerItem, QSizePolicy
import datetime
from PySide6.QtCore import Qt, QTimer
from helpers.check_for_update_helper import show_update_dialog_if_available
from dialogs.add_api_key_dialog import AddApiKeyDialog
import qtawesome as qta
from helpers.video_proxy_helper import get_video_proxy_invoker
from ui.main_table import ImageTableWidget
from ui.prompt_section import PromptSectionWidget
from ui.stats_section import StatsSectionWidget
from ui.main_menu import setup_main_menu
from ui.main_toolbar import setup_main_toolbar
from helpers.batch_processing_helper import batch_generate_metadata
from dialogs.api_call_warning_dialog import ApiCallWarningDialog
from ui.properties_widget import PropertiesWidget
from ui.api_key_section import ApiKeySectionWidget
from ui.main_statusbar import MainStatusBar
from database.db_operation import ImageTeaDB
from dialogs.guide_tour import GuideOverlay

def setup_ui(self):
    invoker = get_video_proxy_invoker(timeout=5)
    if invoker is None:
        print('[Startup Warning] VideoProxyInvoker could not be created; video dialogs will not appear.')

    setup_main_menu(self)
    try:
        from dialogs.backup_global_config_dialog import configs_newer_than_latest_backup
        if configs_newer_than_latest_backup() and hasattr(self, 'backup_configs_action'):
            try:
                self.backup_configs_action.setIcon(qta.icon('fa6s.triangle-exclamation', color="#e61515"))
            except Exception:
                pass
    except Exception:
        pass
    setup_main_toolbar(self)
    self.db = getattr(self, 'db', None) or ImageTeaDB()
    central = QWidget()
    layout = QVBoxLayout()

    self.prompt_section = PromptSectionWidget(self)
    layout.addWidget(self.prompt_section)

    api_layout = QHBoxLayout()

    self.api_key_section = ApiKeySectionWidget(self.db, self)
    api_layout.addWidget(self.api_key_section)
    layout.addLayout(api_layout)

    def on_api_key_changed(api_key, service, model):
        self.api_key = api_key
        self.selected_service = service
        self.selected_model_name = model

    self.api_key_section.api_key_changed.connect(on_api_key_changed)
    # Set initial values
    self.api_key = self.api_key_section.get_current_api_key()
    self.selected_service = self.api_key_section.get_current_service()
    self.selected_model_name = self.api_key_section.get_current_model()

    main_content_layout = QHBoxLayout()
    self.table = ImageTableWidget(self, db=self.db)
    self.properties_widget = PropertiesWidget(self)
    self.table._properties_widget = self.properties_widget
    self.properties_widget.db = self.db

    def on_table_selection_changed():
        selected_row = self.table.get_selected_row_data() if hasattr(self.table, "get_selected_row_data") else None
        self.properties_widget.set_properties(selected_row)

    if hasattr(self.table, "selectionModel"):
        self.table.selectionModel().selectionChanged.connect(lambda *_: on_table_selection_changed())

    if hasattr(self.table, "data_refreshed"):
        self.table.data_refreshed.connect(lambda: on_table_selection_changed())

    main_content_layout.addWidget(self.table, stretch=3)
    main_content_layout.addWidget(self.properties_widget, stretch=1)
    layout.addLayout(main_content_layout)

    btn_row_layout = QHBoxLayout()
    self.stats_section = StatsSectionWidget(self)
    self.stats_section.db = self.db
    btn_row_layout.addWidget(self.stats_section)

    self.table.stats_changed.connect(self.stats_section.update_stats)

    btn_row_layout.addStretch()

    gen_group_layout = QVBoxLayout()
    self.gen_mode_combo = QComboBox()
    self.gen_mode_combo.addItems([
        "All Files",
        "Selected Only",
        "Failed Only",
        "Drafts Only",
        "Resume From Stopped",
        "All (Rolling API Keys)",
        "Failed Only (Rolling API Keys)",
        "Selected Only (Rolling API Keys)",
        "Drafts Only (Rolling API Keys)"
    ])
    self.gen_mode_combo.setToolTip("Choose which files to generate metadata for")
    gen_group_layout.addWidget(self.gen_mode_combo)

    self.gen_btn = QPushButton(qta.icon('fa6s.wand-magic-sparkles', color='white'), "Generate Metadata")
    self.gen_btn.setStyleSheet("""
        QPushButton {
            background-color: #4e9e20;
            color: white;
            border: none;
            border-radius: 5px;
            padding: 6px 12px;
            min-height: 36px;
            max-height: 36px;
            min-width: 240px;
            max-width: 240px;
        }
        QPushButton:hover { background-color: #3d7307; }
        QPushButton:pressed { background-color: #376006; }
        QPushButton:disabled { background-color: #9fbf9a; color: #f2f2f2; }
    """)
    self.gen_btn.setCursor(Qt.PointingHandCursor)

    def update_gen_btn_tooltip(idx):
        mode = self.gen_mode_combo.currentText()
        if mode == "All Files":
            self.gen_btn.setToolTip("Generate metadata for all files in the table")
        elif mode == "Selected Only":
            self.gen_btn.setToolTip("Generate metadata only for selected files")
        elif mode == "Failed Only":
            self.gen_btn.setToolTip("Generate metadata only for files that previously failed")
        elif mode == "Drafts Only":
            self.gen_btn.setToolTip("Generate metadata starting from the first draft file onwards")
        elif mode == "Resume From Stopped":
            self.gen_btn.setToolTip("Resume generation starting from the first stopped file onwards")
        elif mode == "All (Rolling API Keys)":
            self.gen_btn.setToolTip("Use all available API keys automatically when one fails")
        elif mode == "Failed Only (Rolling API Keys)":
            self.gen_btn.setToolTip("Retry only failed files using all available API keys with automatic retry")
        elif mode == "Selected Only (Rolling API Keys)":
            self.gen_btn.setToolTip("Generate only selected files using all available API keys with automatic retry")
        elif mode == "Drafts Only (Rolling API Keys)":
            self.gen_btn.setToolTip("Generate drafts onwards using all available API keys with automatic retry")
        else:
            self.gen_btn.setToolTip("Generate metadata")

    self.gen_mode_combo.currentIndexChanged.connect(update_gen_btn_tooltip)
    update_gen_btn_tooltip(self.gen_mode_combo.currentIndex())

    self.gen_btn.setFixedSize(240, 36)
    font = self.gen_btn.font()
    font.setPointSize(font.pointSize() + 4)
    font.setBold(True)
    self.gen_btn.setFont(font)

    def on_generate_clicked():
        mode = self.gen_mode_combo.currentText()
        total_files = self.table.table.rowCount()
        if mode == "All Files" and total_files >= 1000:
            dialog = ApiCallWarningDialog(self)
            result = dialog.exec()
            if result != QDialog.Accepted:
                return
        batch_generate_metadata(self)
        on_table_selection_changed()

    self.gen_btn.clicked.connect(on_generate_clicked)
    gen_group_layout.addWidget(self.gen_btn)

    btn_row_layout.addLayout(gen_group_layout)

    layout.addLayout(btn_row_layout)
    central.setLayout(layout)
    self.setCentralWidget(central)

    self.statusbar = MainStatusBar(self)
    self.setStatusBar(self.statusbar)
    try:
        QTimer.singleShot(500, lambda: show_update_dialog_if_available(parent=self))
    except Exception:
        pass

    try:
        self.guide_overlay = GuideOverlay(self)
        QTimer.singleShot(100, lambda: self.guide_overlay.show_if_needed())
    except Exception:
        pass

    on_table_selection_changed()