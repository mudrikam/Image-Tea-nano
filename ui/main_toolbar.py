from PySide6.QtWidgets import QToolBar, QStyle, QWidget, QFrame, QWidgetAction, QHBoxLayout, QVBoxLayout, QLabel, QToolButton, QMessageBox, QPushButton, QComboBox, QDialog
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QObject, QEvent, QSize
import qtawesome as qta
import webbrowser
import os
import sys
import subprocess
from config import BASE_PATH
from helpers.file_importer import import_files
from helpers.metadata_helper.metadata_operation import write_metadata_to_images, write_metadata_to_videos
from ui.main_menu import run_updater
from ui.theme_system import theme

def get_app_links():
    import json
    import os
    config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config["links"]

class HoverIconEventFilter(QObject):
    def __init__(self, button, icon_normal, icon_hover, icon_size):
        super().__init__(button)
        self.button = button
        self.icon_normal = icon_normal
        self.icon_hover = icon_hover
        self.icon_size = icon_size

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Enter:
            self.button.setIcon(self.icon_hover)
            self.button.setIconSize(self.icon_size)
        elif event.type() == QEvent.Leave:
            self.button.setIcon(self.icon_normal)
            self.button.setIconSize(self.icon_size)
        return False

def add_vertical_separator(toolbar):
    wrapper = QWidget()
    layout = QHBoxLayout(wrapper)
    layout.setContentsMargins(8, 0, 8, 0)
    sep = QFrame()
    sep.setFrameShape(QFrame.VLine)
    sep.setFrameShadow(QFrame.Sunken)
    sep.setFixedHeight(32)
    layout.addWidget(sep)
    sep_action = QWidgetAction(toolbar)
    sep_action.setDefaultWidget(wrapper)
    toolbar.addAction(sep_action)

def create_toolbar_button_with_label(icon_normal, icon_hover, text, tooltip, triggered_func, window, icon_size, obj_name=None):
    btn_widget = QWidget()
    if obj_name:
        btn_widget.setObjectName(f"wrapper_{obj_name}")
    v_layout = QVBoxLayout(btn_widget)
    v_layout.setContentsMargins(2, 2, 2, 2)
    v_layout.setSpacing(0)
    btn = QToolButton()
    if obj_name:
        btn.setObjectName(obj_name)
    btn.setIcon(icon_normal)
    btn.setIconSize(icon_size)
    btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
    btn.setToolTip(tooltip)
    btn.clicked.connect(triggered_func)
    btn.installEventFilter(HoverIconEventFilter(btn, icon_normal, icon_hover, icon_size))
    label = QLabel(text)
    label.setStyleSheet(f"font-family: 'Segoe UI'; font-size: 9px; color: {theme.get_color('gray')};")
    label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    v_layout.addWidget(btn, alignment=Qt.AlignHCenter)
    v_layout.addWidget(label, alignment=Qt.AlignHCenter)
    action = QWidgetAction(window)
    if obj_name:
        action.setObjectName(f"action_{obj_name}")
    action.setDefaultWidget(btn_widget)
    return action

def create_toolbar_donate_button(icon_normal, icon_hover, text, label_text, tooltip, triggered_func, window, icon_size, obj_name=None, bg_color=None, bg_color_hover=None, bg_color_pressed=None, text_color=None):
    btn_widget = QWidget()
    if obj_name:
        btn_widget.setObjectName(f"wrapper_{obj_name}")
    v_layout = QVBoxLayout(btn_widget)
    v_layout.setContentsMargins(15, 2, 2, 2)
    v_layout.setSpacing(0)
    btn = QToolButton()
    if obj_name:
        btn.setObjectName(obj_name)
    btn.setIcon(icon_normal)
    btn.setIconSize(icon_size)
    btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    btn.setText(text)
    btn.setToolTip(tooltip)
    btn.setCursor(Qt.PointingHandCursor)
    btn.clicked.connect(triggered_func)
    btn.installEventFilter(HoverIconEventFilter(btn, icon_normal, icon_hover, icon_size))
    bg = bg_color if bg_color else theme.get_color('primary')
    bg_h = bg_color_hover if bg_color_hover else theme.get_color('primary_hover')
    bg_p = bg_color_pressed if bg_color_pressed else theme.get_color('primary_pressed')
    tc = text_color if text_color else theme.get_color('white')
    btn.setStyleSheet(f"""
        QToolButton#toolbar_donate {{
            background-color: {bg};
            color: {tc};
            border: none;
            border-radius: 6px;
            padding: 4px 10px;
            font-family: 'Segoe UI';
            font-size: 11px;
        }}
        QToolButton#toolbar_donate:hover {{
            background-color: {bg_h};
        }}
        QToolButton#toolbar_donate:pressed {{
            background-color: {bg_p};
        }}
    """)
    label = QLabel(label_text)
    label.setStyleSheet(f"font-family: 'Segoe UI'; font-size: 9px; color: {theme.get_color('gray')};")
    label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    v_layout.addWidget(btn, alignment=Qt.AlignHCenter)
    v_layout.addWidget(label, alignment=Qt.AlignHCenter)
    action = QWidgetAction(window)
    if obj_name:
        action.setObjectName(f"action_{obj_name}")
    action.setDefaultWidget(btn_widget)
    return action

def relaunch_app(window):
    python_exe = sys.executable
    args = [python_exe] + sys.argv
    try:
        subprocess.Popen(args)
    except Exception as e:
        print(f"Failed to relaunch: {e}")
    window.close()

def show_clear_dialog(window):
    """Show dialog to choose what to clear: all files, success only, or failed only"""
    dialog = QDialog(window)
    dialog.setWindowTitle("Clear Files")
    
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(15, 15, 15, 15)
    layout.setSpacing(10)
    
    # Icon and label
    top_layout = QHBoxLayout()
    icon_label = QLabel()
    icon_label.setPixmap(qta.icon('fa6s.triangle-exclamation', color=theme.get_color('warning')).pixmap(32, 32))
    top_layout.addWidget(icon_label)
    
    text_label = QLabel("Choose what to clear from database:")
    text_label.setWordWrap(True)
    top_layout.addWidget(text_label, 1)
    layout.addLayout(top_layout)
    
    # Combobox
    combo = QComboBox()
    combo.addItems(["Clear All Files", "Clear Success Only", "Clear Failed Only"])
    combo.setCurrentIndex(0)
    layout.addWidget(combo)
    
    # Buttons
    button_layout = QHBoxLayout()
    button_layout.addStretch()
    
    btn_clear = QPushButton("Clear")
    btn_clear.setIcon(qta.icon('fa6s.broom'))
    btn_clear.clicked.connect(dialog.accept)
    
    btn_cancel = QPushButton("Cancel")
    btn_cancel.setIcon(qta.icon('fa6s.xmark'))
    btn_cancel.clicked.connect(dialog.reject)
    btn_cancel.setDefault(True)
    
    button_layout.addWidget(btn_clear)
    button_layout.addWidget(btn_cancel)
    layout.addLayout(button_layout)
    
    result = dialog.exec()
    
    if result == QDialog.Accepted:
        choice = combo.currentText()
        if choice == "Clear All Files":
            window.table.clear_all()
        elif choice == "Clear Success Only":
            window.table.clear_success()
        elif choice == "Clear Failed Only":
            window.table.clear_failed()

def setup_main_toolbar(window: QWidget):
    # Remove existing toolbar if any
    if hasattr(window, 'toolbar') and window.toolbar:
        window.toolbar.deleteLater()
    
    toolbar = QToolBar("Main Toolbar", window)
    try:
        window.toolbar = toolbar
    except Exception:
        pass
    try:
        window.main_toolbar = toolbar
    except Exception:
        pass
    toolbar.setMovable(False)
    toolbar.setFloatable(False)
    toolbar.setIconSize(window.style().standardIcon(QStyle.SP_DesktopIcon).actualSize(toolbar.iconSize()))
    toolbar.setStyleSheet(f"""
        QToolBar {{ padding: 5px; }}
        QToolButton {{
            padding: 4px;
            border-radius: 6px;
        }}
        QToolButton:hover {{
            background-color: {theme.get_color('primary')};
        }}
    """)

    icon_color = theme.get_color('primary')
    icon_color_hover = theme.get_color('white')
    icon_size = toolbar.iconSize()

    def make_icon(icon_name, color):
        return qta.icon(icon_name, color=color)

    links = get_app_links()

    import_action = create_toolbar_button_with_label(
        make_icon('fa6s.folder-open', icon_color),
        make_icon('fa6s.folder-open', icon_color_hover),
        "Import",
        "Import files into the table for metadata generation. \nSupports common images, vector graphics, and videos.",
        lambda: (import_files(window, window.db) and window.table.refresh_table()),
        window, icon_size, obj_name='toolbar_import')
    toolbar.addAction(import_action)

    clear_all_action = create_toolbar_button_with_label(
        make_icon('fa6s.broom', icon_color),
        make_icon('fa6s.broom', icon_color_hover),
        "Clear",
        "Clear files from the database. \nChoose to clear all files, success only, or failed only. \nThis does NOT delete files from disk, only removes database entries.",
        lambda: show_clear_dialog(window),
        window, icon_size, obj_name='toolbar_clear')
    toolbar.addAction(clear_all_action)

    delete_selected_action = create_toolbar_button_with_label(
        make_icon('fa6s.trash', icon_color),
        make_icon('fa6s.trash', icon_color_hover),
        "Delete",
        "Delete selected files from the table. \nThis does NOT delete files from disk. \nSame as Clear All, but only for selected rows.",
        lambda: window.table.delete_selected(),
        window, icon_size, obj_name='toolbar_delete')
    toolbar.addAction(delete_selected_action)

    add_vertical_separator(toolbar)

    clear_metadata_action = create_toolbar_button_with_label(
        make_icon('fa6s.eraser', icon_color),
        make_icon('fa6s.eraser', icon_color_hover),
        "Clear",
        "Clear all metadata from database for all files. \nThis does NOT delete files from disk. \nOnly clears the metadata entries in the database. \nOriginal metadata in files remains unchanged. \nBut you CAN NOT UNDO this action. \nUSE WITH CAUTION.",
        lambda: window.table.clear_existing_metadata(),
        window, icon_size, obj_name='toolbar_clear_metadata')
    toolbar.addAction(clear_metadata_action)

    batch_rename_action = create_toolbar_button_with_label(
        make_icon('fa6s.i-cursor', icon_color),
        make_icon('fa6s.i-cursor', icon_color_hover),
        "Rename",
        "Batch rename selected files in the table. \nThis does NOT modify metadata. \nBut renaming your files directly on disk. \nUSE WITH CAUTION. \nRollback is supported via the dialog by Undo Rename button.",
        lambda: (lambda: __import__('dialogs.batch_rename_dialog', fromlist=['BatchRenameDialog']).BatchRenameDialog(window, table_widget=window.table, db=window.db).exec())(),
        window, icon_size, obj_name='toolbar_rename')
    toolbar.addAction(batch_rename_action)

    edit_metadata_action = create_toolbar_button_with_label(
        make_icon('fa6s.pen-to-square', icon_color),
        make_icon('fa6s.pen-to-square', icon_color_hover),
        "Edit",
        "Edit metadata for selected file in a dialog window. \nYou can modify title, description, keywords, \nand other metadata fields manually. \nSupports both images and videos.",
        lambda: open_edit_metadata(window),
        window, icon_size, obj_name='toolbar_edit')
    toolbar.addAction(edit_metadata_action)

    add_vertical_separator(toolbar)

    def _toolbar_write_images():
        from helpers.tools_dependency_helper import check_tools_available
        if not check_tools_available(["exiftool"], parent=window):
            return
        write_metadata_to_images(window.db, window)

    write_metadata_images_action = create_toolbar_button_with_label(
        make_icon('fa6s.image', icon_color),
        make_icon('fa6s.image', icon_color_hover),
        "Write",
        "Write metadata to image files in the table \nThis will modify the actual image files on disk. \nIf you proceed, the changes will be permanent (no rollback). \nUSE WITH CAUTION. \n\nSome image formats may not support certain metadata fields.",
        _toolbar_write_images,
        window, icon_size, obj_name='toolbar_write_images')
    toolbar.addAction(write_metadata_images_action)

    def _toolbar_write_videos():
        from helpers.tools_dependency_helper import check_tools_available
        if not check_tools_available(["exiftool"], parent=window):
            return
        write_metadata_to_videos(window.db, window)

    write_metadata_videos_action = create_toolbar_button_with_label(
        make_icon('fa6s.film', icon_color),
        make_icon('fa6s.film', icon_color_hover),
        "Write",
        "Write metadata to video files in the table \nThis will modify the actual video files on disk. \nIf you proceed, the changes will be permanent (no rollback). \nUSE WITH CAUTION. \n\nSome video formats may not support certain metadata fields.",
        _toolbar_write_videos,
        window, icon_size, obj_name='toolbar_write_videos')
    toolbar.addAction(write_metadata_videos_action)

    export_metadata_action = create_toolbar_button_with_label(
        make_icon('fa6s.file-csv', icon_color),
        make_icon('fa6s.file-csv', icon_color_hover),
        "Export",
        "Export metadata to CSV file in the table \nYou can choose the destination and filename. \nUseful for backup or further processing. \nSupports common CSV format \nthat can be used for microstock submissions.",
        lambda: (lambda: __import__('dialogs.csv_exporter_dialog', fromlist=['CSVExporterDialog']).CSVExporterDialog(window).exec())(),
        window, icon_size, obj_name='toolbar_export')
    toolbar.addAction(export_metadata_action)

    add_vertical_separator(toolbar)

    def open_edit_prompt_toolbar():
        from dialogs.edit_prompt_dialog import EditPromptDialog
        dialog = EditPromptDialog(window)
        result = dialog.exec()
        if result == EditPromptDialog.Accepted and hasattr(window, 'prompt_section'):
            window.prompt_section.refresh_presets()
    
    edit_prompt_action = create_toolbar_button_with_label(
        make_icon('fa6s.pen-to-square', icon_color),
        make_icon('fa6s.pen-to-square', icon_color_hover),
        "Prompt",
        "Edit the system prompt for AI metadata generation models. \nCustomize how the AI generates titles, descriptions, and keywords. \nAdvanced users can tailor the prompt to their needs. \nChanges affect all subsequent metadata generations. \nThis setting is overwritten to default if you update the Image Tea application. \n\nConsider saving a backup of your custom prompt.",
        open_edit_prompt_toolbar,
        window, icon_size, obj_name='toolbar_prompt')
    toolbar.addAction(edit_prompt_action)

    custom_prompt_action = create_toolbar_button_with_label(
        make_icon('fa6s.comment', icon_color),
        make_icon('fa6s.comment', icon_color_hover),
        "Custom",
        "Use a custom prompt for AI metadata generation. \nUse this to override the default prompt temporarily. \nUseful for one-off generations with different requirements. \nDoes not modify the saved system prompt. \nBut don't forget to clear it after use if you want to revert to the default prompt.",
        lambda: (lambda: __import__('dialogs.custom_prompt_dialog', fromlist=['CustomPromptDialog']).CustomPromptDialog(window).exec())(),
        window, icon_size, obj_name='toolbar_custom')
    toolbar.addAction(custom_prompt_action)

    def open_add_api_dialog():
        from dialogs.add_api_key_dialog import AddApiKeyDialog
        dlg = AddApiKeyDialog(window)
        result = dlg.exec()
        if hasattr(window, 'api_key_section'):
            window.api_key_section.refresh()
    
    add_api_action = create_toolbar_button_with_label(
        make_icon('fa6s.key', icon_color),
        make_icon('fa6s.key', icon_color_hover),
        "API Key",
        "Add or edit your API key for AI metadata generation services. \nAn API key is required to access AI models. \nMake sure to use a valid key from your AI service provider. \nKeep your API key secure and do not share it publicly.",
        open_add_api_dialog,
        window, icon_size, obj_name='toolbar_api_key')
    toolbar.addAction(add_api_action)

    def open_topup_dialog():
        try:
            import json
            config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
            with open(config_path, "r", encoding="utf-8") as f:
                app_cfg = json.load(f)
            topup_url = app_cfg.get("links", {}).get("get_api_key")
            if not topup_url:
                raise ValueError("Topup URL not found in app_config")
            from dialogs.topup_desainia_dialog import TopupDesainiaDialog
            dlg = TopupDesainiaDialog(topup_url, parent=window)
            dlg.setWindowModality(Qt.ApplicationModal)
            dlg.exec()
        except Exception as e:
            print(f"Failed to open topup dialog: {e}")

    topup_action = create_toolbar_button_with_label(
        make_icon('fa6s.coins', icon_color),
        make_icon('fa6s.coins', icon_color_hover),
        "Top Up",
        "Top up your API key balance.",
        open_topup_dialog,
        window, icon_size, obj_name='toolbar_topup')
    toolbar.addAction(topup_action)

    add_vertical_separator(toolbar)

    # Group: Relaunch + Update
    relaunch_action = create_toolbar_button_with_label(
        make_icon('fa6s.rotate-right', icon_color),
        make_icon('fa6s.rotate-right', icon_color_hover),
        "Relaunch",
        "Relaunch the application if needed (after updates or config changes).",
        lambda: relaunch_app(window),
        window, icon_size, obj_name='toolbar_relaunch')
    toolbar.addAction(relaunch_action)

    update_now_action = create_toolbar_button_with_label(
        make_icon('fa6s.download', icon_color),
        make_icon('fa6s.download', icon_color_hover),
        "Update",
        "Check for updates and apply updates if a new version is available. \nMake sure you have an active internet connection. \nPlease save your work before updating, as the application will restart. \nSome settings may be reset to default after an update. \nIt's recommended to back up your configuration files periodically. \n\nUpdates bring new features, improvements, and bug fixes.",
        lambda: run_updater(window),
        window, icon_size, obj_name='toolbar_update')
    toolbar.addAction(update_now_action)

    add_vertical_separator(toolbar)

    primary_color = theme.get_color('primary')
    primary_color_hover = theme.get_color('primary_hover')
    primary_color_pressed = theme.get_color('primary_pressed')
    white_color = theme.get_color('white')

    donate_action = create_toolbar_donate_button(
        make_icon('fa6s.circle-dollar-to-slot', white_color),
        make_icon('fa6s.circle-dollar-to-slot', white_color),
        "Donate",
        "Support Us",
        "Support development of this application by making a donation. \nYour contributions help fund new features and improvements. \nAny amount is appreciated, no matter how small. \nThank you for supporting the project!",
        lambda: (lambda: __import__('dialogs.donation_dialog', fromlist=['DonateDialog']).DonateDialog(window).exec())(),
        window, icon_size, obj_name='toolbar_donate',
        bg_color=primary_color,
        bg_color_hover=primary_color_hover,
        bg_color_pressed=primary_color_pressed,
        text_color=white_color)

    wa_action = create_toolbar_button_with_label(
        make_icon('fa6b.whatsapp', icon_color),
        make_icon('fa6b.whatsapp', icon_color_hover),
        "WhatsApp",
        "Join the WhatsApp support community for help and discussions.",
        lambda: webbrowser.open(links["whatsapp"]),
        window, icon_size, obj_name='toolbar_whatsapp')

    def open_documentation_toolbar():
        if not hasattr(window, '_read_documentation_dialog') or not window._read_documentation_dialog:
            from dialogs.read_documentation_dialog import ReadDocumentationDialog
            window._read_documentation_dialog = ReadDocumentationDialog(None)
            window._read_documentation_dialog.destroyed.connect(lambda: setattr(window, '_read_documentation_dialog', None))
            if hasattr(window, 'windowIcon') and not window.windowIcon().isNull():
                window._read_documentation_dialog.setWindowIcon(window.windowIcon())
        window._read_documentation_dialog.show()
        window._read_documentation_dialog.raise_()
        window._read_documentation_dialog.activateWindow()

    documentation_action = create_toolbar_button_with_label(
        make_icon('fa6s.book-open', icon_color),
        make_icon('fa6s.book-open', icon_color_hover),
        "Help",
        "Open the documentation/help dialog for guidance and troubleshooting.",
        open_documentation_toolbar,
        window, icon_size, obj_name='toolbar_help')

    toolbar.addAction(wa_action)
    toolbar.addAction(documentation_action)
    toolbar.addAction(donate_action)

    window.addToolBar(toolbar)

def open_edit_metadata(window):
    selected = window.table.table.selectionModel().selectedRows()
    if selected:
        idx = selected[0].row()
        filepath_item = window.table.table.item(idx, 1)
        if filepath_item:
            filepath = filepath_item.data(0x0100)
            if not filepath:
                filepath = filepath_item.text()
            from dialogs.file_metadata_dialog import FileMetadataDialog
            dialog = FileMetadataDialog(filepath, parent=window)
            dialog.exec()