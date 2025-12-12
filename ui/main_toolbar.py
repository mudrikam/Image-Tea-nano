from PySide6.QtWidgets import QToolBar, QStyle, QWidget, QFrame, QWidgetAction, QHBoxLayout, QVBoxLayout, QLabel, QToolButton
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QObject, QEvent
import qtawesome as qta
import webbrowser
import os
import sys
import subprocess
from config import BASE_PATH
from dialogs.csv_exporter_dialog import CSVExporterDialog
from dialogs.edit_prompt_dialog import EditPromptDialog
from dialogs.custom_prompt_dialog import CustomPromptDialog
from dialogs.batch_rename_dialog import BatchRenameDialog
from dialogs.read_documentation_dialog import ReadDocumentationDialog
from dialogs.donation_dialog import DonateDialog
from dialogs.add_api_key_dialog import AddApiKeyDialog
from dialogs.file_metadata_dialog import FileMetadataDialog
from helpers.file_importer import import_files
from helpers.metadata_helper.metadata_operation import write_metadata_to_images, write_metadata_to_videos
from ui.main_menu import clear_existing_metadata, run_updater

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

def create_toolbar_button_with_label(icon_normal, icon_hover, text, tooltip, triggered_func, window, icon_size):
    btn_widget = QWidget()
    v_layout = QVBoxLayout(btn_widget)
    v_layout.setContentsMargins(2, 2, 2, 2)
    v_layout.setSpacing(0)
    btn = QToolButton()
    btn.setIcon(icon_normal)
    btn.setIconSize(icon_size)
    btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
    btn.setToolTip(tooltip)
    btn.clicked.connect(triggered_func)
    btn.installEventFilter(HoverIconEventFilter(btn, icon_normal, icon_hover, icon_size))
    label = QLabel(text)
    label.setStyleSheet("font-family: 'Segoe UI'; font-size: 9px; color: #666;")
    label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    v_layout.addWidget(btn, alignment=Qt.AlignHCenter)
    v_layout.addWidget(label, alignment=Qt.AlignHCenter)
    action = QWidgetAction(window)
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

def setup_main_toolbar(window: QWidget):
    toolbar = QToolBar("Main Toolbar", window)
    toolbar.setMovable(False)
    toolbar.setFloatable(False)
    toolbar.setIconSize(window.style().standardIcon(QStyle.SP_DesktopIcon).actualSize(toolbar.iconSize()))
    toolbar.setStyleSheet("""
        QToolBar { padding: 5px; }
        QToolButton {
            padding: 4px;
            border-radius: 6px;
        }
        QToolButton:hover {
            background-color: #4e9e20;
        }
    """)

    icon_color = "#4e9e20"
    icon_color_hover = "#FFFFFF"
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
        window, icon_size)
    toolbar.addAction(import_action)

    clear_all_action = create_toolbar_button_with_label(
        make_icon('fa6s.broom', icon_color),
        make_icon('fa6s.broom', icon_color_hover),
        "Clear",
        "Clear all files from the table. \nThis does NOT delete files from disk. \nOnly clears the database entries. \nUse when you want to start fresh.",
        lambda: window.table.clear_all(),
        window, icon_size)
    toolbar.addAction(clear_all_action)

    delete_selected_action = create_toolbar_button_with_label(
        make_icon('fa6s.trash', icon_color),
        make_icon('fa6s.trash', icon_color_hover),
        "Delete",
        "Delete selected files from the table. \nThis does NOT delete files from disk. \nSame as Clear All, but only for selected rows.",
        lambda: window.table.delete_selected(),
        window, icon_size)
    toolbar.addAction(delete_selected_action)

    add_vertical_separator(toolbar)

    clear_metadata_action = create_toolbar_button_with_label(
        make_icon('fa6s.eraser', icon_color),
        make_icon('fa6s.eraser', icon_color_hover),
        "Clear",
        "Clear all metadata from database for all files. \nThis does NOT delete files from disk. \nOnly clears the metadata entries in the database. \nOriginal metadata in files remains unchanged. \nBut you CAN NOT UNDO this action. \nUSE WITH CAUTION.",
        lambda: clear_existing_metadata(window),
        window, icon_size)
    toolbar.addAction(clear_metadata_action)

    batch_rename_action = create_toolbar_button_with_label(
        make_icon('fa6s.i-cursor', icon_color),
        make_icon('fa6s.i-cursor', icon_color_hover),
        "Rename",
        "Batch rename selected files in the table. \nThis does NOT modify metadata. \nBut renaming your files directly on disk. \nUSE WITH CAUTION. \nRollback is supported via the dialog by Undo Rename button.",
        lambda: BatchRenameDialog(window, table_widget=window.table, db=window.db).exec(),
        window, icon_size)
    toolbar.addAction(batch_rename_action)

    edit_metadata_action = create_toolbar_button_with_label(
        make_icon('fa6s.pen-to-square', icon_color),
        make_icon('fa6s.pen-to-square', icon_color_hover),
        "Edit",
        "Edit metadata for selected file in a dialog window. \nYou can modify title, description, keywords, \nand other metadata fields manually. \nSupports both images and videos.",
        lambda: open_edit_metadata(window),
        window, icon_size)
    toolbar.addAction(edit_metadata_action)

    add_vertical_separator(toolbar)

    write_metadata_images_action = create_toolbar_button_with_label(
        make_icon('fa6s.image', icon_color),
        make_icon('fa6s.image', icon_color_hover),
        "Write",
        "Write metadata to image files in the table \nThis will modify the actual image files on disk. \nIf you proceed, the changes will be permanent (no rollback). \nUSE WITH CAUTION. \n\nSome image formats may not support certain metadata fields.",
        lambda: write_metadata_to_images(window.db, window),
        window, icon_size)
    toolbar.addAction(write_metadata_images_action)

    write_metadata_videos_action = create_toolbar_button_with_label(
        make_icon('fa6s.film', icon_color),
        make_icon('fa6s.film', icon_color_hover),
        "Write",
        "Write metadata to video files in the table \nThis will modify the actual video files on disk. \nIf you proceed, the changes will be permanent (no rollback). \nUSE WITH CAUTION. \n\nSome video formats may not support certain metadata fields.",
        lambda: write_metadata_to_videos(window.db, window),
        window, icon_size)
    toolbar.addAction(write_metadata_videos_action)

    export_metadata_action = create_toolbar_button_with_label(
        make_icon('fa6s.file-csv', icon_color),
        make_icon('fa6s.file-csv', icon_color_hover),
        "Export",
        "Export metadata to CSV file in the table \nYou can choose the destination and filename. \nUseful for backup or further processing. \nSupports common CSV format \nthat can be used for microstock submissions.",
        lambda: CSVExporterDialog(window).exec(),
        window, icon_size)
    toolbar.addAction(export_metadata_action)

    add_vertical_separator(toolbar)

    edit_prompt_action = create_toolbar_button_with_label(
        make_icon('fa6s.pen-to-square', icon_color),
        make_icon('fa6s.pen-to-square', icon_color_hover),
        "Prompt",
        "Edit the system prompt for AI metadata generation models. \nCustomize how the AI generates titles, descriptions, and keywords. \nAdvanced users can tailor the prompt to their needs. \nChanges affect all subsequent metadata generations. \nThis setting is overwritten to default if you update the Image Tea application. \n\nConsider saving a backup of your custom prompt.",
        lambda: EditPromptDialog(window).exec(),
        window, icon_size)
    toolbar.addAction(edit_prompt_action)

    custom_prompt_action = create_toolbar_button_with_label(
        make_icon('fa6s.comment', icon_color),
        make_icon('fa6s.comment', icon_color_hover),
        "Custom",
        "Use a custom prompt for AI metadata generation. \nUse this to override the default prompt temporarily. \nUseful for one-off generations with different requirements. \nDoes not modify the saved system prompt. \nBut don't forget to clear it after use if you want to revert to the default prompt.",
        lambda: CustomPromptDialog(window).exec(),
        window, icon_size)
    toolbar.addAction(custom_prompt_action)

    add_api_action = create_toolbar_button_with_label(
        make_icon('fa6s.key', icon_color),
        make_icon('fa6s.key', icon_color_hover),
        "API Key",
        "Add or edit your API key for AI metadata generation services. \nAn API key is required to access AI models. \nMake sure to use a valid key from your AI service provider. \nKeep your API key secure and do not share it publicly.",
        lambda: AddApiKeyDialog(window).exec(),
        window, icon_size)
    toolbar.addAction(add_api_action)

    add_vertical_separator(toolbar)

    # Group: Relaunch + Update
    relaunch_action = create_toolbar_button_with_label(
        make_icon('fa6s.rotate-right', icon_color),
        make_icon('fa6s.rotate-right', icon_color_hover),
        "Relaunch",
        "Relaunch the application if needed (after updates or config changes).",
        lambda: relaunch_app(window),
        window, icon_size)
    toolbar.addAction(relaunch_action)

    update_now_action = create_toolbar_button_with_label(
        make_icon('fa6s.download', icon_color),
        make_icon('fa6s.download', icon_color_hover),
        "Update",
        "Check for updates and run the updater if a new version is available. \nMake sure you have an active internet connection. \nPlease save your work before updating, as the application will restart. \nSome settings may be reset to default after an update. \nIt's recommended to back up your configuration files periodically. \n\nUpdates bring new features, improvements, and bug fixes.",
        lambda: run_updater(window),
        window, icon_size)
    toolbar.addAction(update_now_action)

    add_vertical_separator(toolbar)

    donate_action = create_toolbar_button_with_label(
        make_icon('fa6s.circle-dollar-to-slot', icon_color),
        make_icon('fa6s.circle-dollar-to-slot', icon_color_hover),
        "Donate",
        "Support development of this application by making a donation. \nYour contributions help fund new features and improvements. \nAny amount is appreciated, no matter how small. \nThank you for supporting the project!",
        lambda: DonateDialog(window).exec(),
        window, icon_size)

    wa_action = create_toolbar_button_with_label(
        make_icon('fa6b.whatsapp', icon_color),
        make_icon('fa6b.whatsapp', icon_color_hover),
        "WhatsApp",
        "Join the WhatsApp support community for help and discussions.",
        lambda: webbrowser.open(links["whatsapp"]),
        window, icon_size)

    repo_action = create_toolbar_button_with_label(
        make_icon('fa6b.github', icon_color),
        make_icon('fa6b.github', icon_color_hover),
        "Repo",
        "Open the GitHub repository for this application.",
        lambda: webbrowser.open(links["repo"]),
        window, icon_size)

    website_action = create_toolbar_button_with_label(
        make_icon('fa6b.tiktok', icon_color),
        make_icon('fa6b.tiktok', icon_color_hover),
        "TikTok",
        "Visit TikTok @desainia for tutorials and updates.",
        lambda: webbrowser.open(links["tiktok"]),
        window, icon_size)

    readme_action = create_toolbar_button_with_label(
        make_icon('fa6b.telegram', icon_color),
        make_icon('fa6b.telegram', icon_color_hover),
        "Telegram",
        "Chat with our Telegram bot for support and information.",
        lambda: webbrowser.open(links["telegram"]),
        window, icon_size)

    documentation_action = create_toolbar_button_with_label(
        make_icon('fa6s.book-open', icon_color),
        make_icon('fa6s.book-open', icon_color_hover),
        "Help",
        "Open the documentation/help dialog for guidance and troubleshooting.",
        lambda: ReadDocumentationDialog(window).exec(),
        window, icon_size)
    
    toolbar.addAction(wa_action)
    toolbar.addAction(website_action)
    toolbar.addAction(readme_action)
    toolbar.addAction(repo_action)
    toolbar.addAction(donate_action)
    toolbar.addAction(documentation_action)

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
            dialog = FileMetadataDialog(filepath, parent=window)
            dialog.exec()