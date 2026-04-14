from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox, QDialog, QSpacerItem, QSizePolicy
import datetime
from PySide6.QtCore import Qt, QTimer
from dialogs.add_api_key_dialog import AddApiKeyDialog
import qtawesome as qta
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
from .theme_system import theme

def _init_video_proxy_invoker():
    try:
        from helpers.video_proxy_helper import get_video_proxy_invoker
        invoker = get_video_proxy_invoker(timeout=5)
        if invoker is None:
            print('[Startup Warning] VideoProxyInvoker could not be created; video dialogs will not appear.')
    except Exception as e:
        print(f'[Startup Warning] VideoProxyInvoker init failed: {e}')

def setup_ui(self):
    QTimer.singleShot(0, lambda: _init_video_proxy_invoker())

    setup_main_menu(self)
    try:
        from dialogs.backup_global_config_dialog import configs_newer_than_latest_backup
        if configs_newer_than_latest_backup() and hasattr(self, 'backup_configs_action'):
            try:
                self.backup_configs_action.setIcon(qta.icon('fa6s.triangle-exclamation', color=theme.get_color('error')))
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

    def on_tags_data_changed():
        self.table.refresh_table()
        on_table_selection_changed()

    if hasattr(self.table, "selectionModel"):
        self.table.selectionModel().selectionChanged.connect(lambda *_: on_table_selection_changed())

    if hasattr(self.table, "data_refreshed"):
        self.table.data_refreshed.connect(lambda: on_table_selection_changed())

    if hasattr(self.properties_widget.tags_pill_widget, "data_changed"):
        self.properties_widget.tags_pill_widget.data_changed.connect(on_tags_data_changed)

    main_content_layout.addWidget(self.table, stretch=3)
    main_content_layout.addWidget(self.properties_widget, stretch=1)
    layout.addLayout(main_content_layout, stretch=1)

    btn_row_layout = QHBoxLayout()
    self.stats_section = StatsSectionWidget(self)
    self.stats_section.db = self.db
    btn_row_layout.addWidget(self.stats_section, stretch=1)

    self.table.stats_changed.connect(self.stats_section.update_stats)

    gen_group_layout = QVBoxLayout()
    self.gen_mode_combo = QComboBox()
    gen_mode_descriptions = {
        "All Files": "Generate metadata for all files in the table",
        "Selected Only": "Generate metadata only for selected files",
        "Failed Only": "Generate metadata only for files that previously failed",
        "Drafts Only": "Generate metadata starting from the first draft file onwards",
        "Resume From Stopped": "Resume generation starting from the first stopped file onwards",
        "All (Rolling API Keys)": "Generate metadata for all files using all available API keys with automatic retry",
        "Failed Only (Rolling API Keys)": "Retry only failed files using all available API keys with automatic retry",
        "Selected Only (Rolling API Keys)": "Generate only selected files using all available API keys with automatic retry",
        "Drafts Only (Rolling API Keys)": "Generate drafts onwards using all available API keys with automatic retry",
        "All (Parallel API Processing)": "Process all files in parallel using multiple API keys simultaneously",
        "Failed Only (Parallel API Processing)": "Retry only failed files using parallel API processing",
        "Selected Only (Parallel API Processing)": "Generate only selected files using parallel API processing",
        "Drafts Only (Parallel API Processing)": "Generate drafts onwards using parallel API processing"
    }
    self.gen_mode_combo.addItems(list(gen_mode_descriptions.keys()))
    self.gen_mode_combo.setToolTip("Choose which files to generate metadata for")
    gen_group_layout.addWidget(self.gen_mode_combo)

    self.gen_mode_desc_label = QLabel()
    self.gen_mode_desc_label.setWordWrap(True)
    self.gen_mode_desc_label.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 10px;")
    gen_group_layout.addWidget(self.gen_mode_desc_label)

    self.gen_btn = QPushButton(qta.icon('fa6s.wand-magic-sparkles', color=theme.get_color('white')), "Generate Metadata")
    self.gen_btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {theme.get_color('primary')};
            color: {theme.get_color('white')};
            border: none;
            border-radius: 5px;
            padding: 6px 12px;
            min-height: 36px;
            max-height: 36px;
            min-width: 240px;
            max-width: 240px;
        }}
        QPushButton:hover {{ background-color: {theme.get_color('primary_hover')}; }}
        QPushButton:pressed {{ background-color: {theme.get_color('primary_pressed')}; }}
        QPushButton:disabled {{ background-color: {theme.get_color('button_disabled_bg')}; color: {theme.get_color('button_disabled_fg')}; }}
    """)
    self.gen_btn.setCursor(Qt.PointingHandCursor)

    def update_gen_btn_tooltip(idx):
        mode = self.gen_mode_combo.currentText()
        description = gen_mode_descriptions.get(mode, "Generate metadata")
        self.gen_btn.setToolTip(description)
        self.gen_mode_desc_label.setText(description)

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
        self.guide_overlay = GuideOverlay(self)
        QTimer.singleShot(100, lambda: self.guide_overlay.show_if_needed())
    except Exception:
        pass

    on_table_selection_changed()