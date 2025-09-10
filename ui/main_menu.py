from PySide6.QtWidgets import QMenuBar, QMenu, QMessageBox, QDialog, QVBoxLayout, QLabel, QHBoxLayout
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtCore import Qt
import qtawesome as qta
import webbrowser
import sys
import os
import subprocess
from helpers.file_importer import import_files
from helpers.metadata_helper.metadata_operation import write_metadata_to_images, write_metadata_to_videos
from dialogs.csv_exporter_dialog import CSVExporterDialog
from dialogs.edit_prompt_dialog import EditPromptDialog
from dialogs.custom_prompt_dialog import CustomPromptDialog
from dialogs.batch_rename_dialog import BatchRenameDialog
from dialogs.read_documentation_dialog import ReadDocumentationDialog
from dialogs.donation_dialog import DonateDialog
from dialogs.add_api_key_dialog import AddApiKeyDialog
from dialogs.about_dialog import AboutDialog
from dialogs.file_metadata_dialog import FileMetadataDialog
from config import BASE_PATH
from dialogs.tools.prompt_generator_tool import PromptGeneratorDialog

def get_app_links():
    import json
    import os
    config_path = os.path.join(BASE_PATH, "configs", "app_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config["links"]

def clear_existing_metadata(window):
    msg = (
        "Are you sure you want to clear all metadata (title, description, tags, status and categories)?\n\n"
        "This will NOT remove metadata embedded in the image files, only metadata stored in the database."
    )
    reply = QMessageBox.question(window, "Clear Metadata", msg, QMessageBox.Yes | QMessageBox.No)
    if reply == QMessageBox.Yes:
        window.db.clear_all_metadata()
        window.table.refresh_table()

def run_updater(window):
    updater_path = os.path.join(BASE_PATH, "Image Tea Updater.exe")
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                f'powershell -Command "Start-Process -Verb runAs -FilePath \\"{updater_path}\\""',
                shell=True
            )
        else:
            subprocess.Popen([updater_path])
    except Exception as e:
        print(f"Failed to run updater: {e}")

def setup_main_menu(window):
    links = get_app_links()
    menubar = QMenuBar(window)
    file_menu = QMenu("File", menubar)

    import_action = QAction(qta.icon('fa6s.folder-open'), "Import Files", window)
    def do_import():
        if import_files(window, window.db):
            window.table.refresh_table()
    import_action.triggered.connect(do_import)
    file_menu.addAction(import_action)

    relaunch_action = QAction(qta.icon('fa6s.rotate-right'), "Relaunch", window)
    def relaunch_app():
        python_exe = sys.executable
        args = [python_exe] + sys.argv
        try:
            subprocess.Popen(args)
        except Exception as e:
            print(f"Failed to relaunch: {e}")
        window.close()
    relaunch_action.triggered.connect(relaunch_app)
    file_menu.addAction(relaunch_action)

    exit_action = QAction(qta.icon('fa6s.right-from-bracket'), "Exit", window)
    exit_action.triggered.connect(window.close)
    file_menu.addAction(exit_action)

    edit_menu = QMenu("Edit", menubar)
    delete_action = QAction(qta.icon('fa6s.trash'), "Delete Selected", window)
    delete_action.triggered.connect(lambda: window.table.delete_selected())
    edit_menu.addAction(delete_action)

    clear_action = QAction(qta.icon('fa6s.broom'), "Clear All", window)
    clear_action.triggered.connect(lambda: window.table.clear_all())
    edit_menu.addAction(clear_action)

    clear_metadata_action = QAction(qta.icon('fa6s.eraser'), "Clear Existing Metadata", window)
    clear_metadata_action.triggered.connect(lambda: clear_existing_metadata(window))
    edit_menu.addAction(clear_metadata_action)

    batch_rename_action = QAction(qta.icon('fa6s.i-cursor'), "Batch Rename", window)
    def open_batch_rename():
        dialog = BatchRenameDialog(window, table_widget=window.table, db=window.db)
        dialog.exec()
    batch_rename_action.triggered.connect(open_batch_rename)
    edit_menu.addAction(batch_rename_action)

    edit_metadata_action = QAction(qta.icon('fa6s.pen-to-square'), "Edit Metadata", window)
    def open_edit_metadata():
        selected = window.table.table.selectionModel().selectedRows()
        if selected:
            idx = selected[0].row()
            filepath_item = window.table.table.item(idx, 1)
            if filepath_item:
                filepath = filepath_item.data(Qt.UserRole)
                if not filepath:
                    filepath = filepath_item.text()
                dialog = FileMetadataDialog(filepath, parent=window)
                dialog.exec()
    edit_metadata_action.triggered.connect(open_edit_metadata)
    edit_menu.addAction(edit_metadata_action)

    metadata_menu = QMenu("Metadata", menubar)
    write_metadata_images_action = QAction(qta.icon('fa6s.floppy-disk'), "Write Metadata to Images", window)
    def do_write_metadata_images():
        write_metadata_to_images(window.db, window)
    write_metadata_images_action.triggered.connect(do_write_metadata_images)
    metadata_menu.addAction(write_metadata_images_action)

    write_metadata_videos_action = QAction(qta.icon('fa6s.floppy-disk'), "Write Metadata to Videos", window)
    def do_write_metadata_videos():
        write_metadata_to_videos(window.db, window)
    write_metadata_videos_action.triggered.connect(do_write_metadata_videos)
    metadata_menu.addAction(write_metadata_videos_action)

    export_metadata_action = QAction(qta.icon('fa6s.file-csv'), "Export Metadata to CSV", window)
    def show_export_dialog():
        dialog = CSVExporterDialog(window)
        dialog.exec()
    export_metadata_action.triggered.connect(show_export_dialog)
    metadata_menu.addAction(export_metadata_action)

    prompt_menu = QMenu("Prompt", menubar)
    edit_prompt_action = QAction(qta.icon('fa6s.pen-to-square'), "Edit Prompt", window)
    def open_edit_prompt():
        dialog = EditPromptDialog(window)
        dialog.exec()
    edit_prompt_action.triggered.connect(open_edit_prompt)
    prompt_menu.addAction(edit_prompt_action)

    custom_prompt_action = QAction(qta.icon('fa6s.comment'), "Custom Prompt", window)
    def open_custom_prompt():
        dialog = CustomPromptDialog(window)
        dialog.exec()
    custom_prompt_action.triggered.connect(open_custom_prompt)
    prompt_menu.addAction(custom_prompt_action)

    api_menu = QMenu("API", menubar)
    add_api_action = QAction(qta.icon('fa6s.key'), "Add API Key", window)
    def show_api_dialog():
        dlg = AddApiKeyDialog(window)
        dlg.exec()
    add_api_action.triggered.connect(show_api_dialog)
    api_menu.addAction(add_api_action)

    help_menu = QMenu("Help", menubar)
    about_action = QAction(qta.icon('fa6s.circle-info'), "About", window)
    def show_about():
        dialog = AboutDialog(window)
        dialog.exec()
    about_action.triggered.connect(show_about)
    help_menu.addAction(about_action)

    update_now_action = QAction(qta.icon('fa6s.download'), "Update Now", window)
    update_now_action.triggered.connect(lambda: run_updater(window))
    help_menu.addAction(update_now_action)

    donate_action = QAction(qta.icon('fa6s.circle-dollar-to-slot'), "Donate", window)
    def show_donate():
        dialog = DonateDialog(window)
        dialog.exec()
    donate_action.triggered.connect(show_donate)
    help_menu.addAction(donate_action)

    wa_action = QAction(qta.icon('fa5b.whatsapp'), "WhatsApp Group", window)
    def open_wa():
        webbrowser.open(links["whatsapp"])
    wa_action.triggered.connect(open_wa)
    help_menu.addAction(wa_action)

    repo_action = QAction(qta.icon('fa5b.github'), "Repository", window)
    def open_repo():
        webbrowser.open(links["repo"])
    repo_action.triggered.connect(open_repo)
    help_menu.addAction(repo_action)

    website_action = QAction(qta.icon('fa6s.globe'), "Website", window)
    def open_website():
        webbrowser.open(links["website"])
    website_action.triggered.connect(open_website)
    help_menu.addAction(website_action)

    readme_action = QAction(qta.icon('fa6s.book'), "Open README.md (GitHub)", window)
    def open_readme():
        webbrowser.open(links["readme"])
    readme_action.triggered.connect(open_readme)
    help_menu.addAction(readme_action)

    documentation_action = QAction(qta.icon('fa6s.book-open'), "Help", window)
    def open_documentation():
        dialog = ReadDocumentationDialog(window)
        dialog.exec()
    documentation_action.triggered.connect(open_documentation)
    help_menu.addAction(documentation_action)

    # Tools menu
    tools_menu = QMenu("Tools", menubar)
    prompt_generator_action = QAction(qta.icon('fa6s.wand-magic-sparkles'), "Prompt Generator", window)
    def open_prompt_generator():
        dlg = PromptGeneratorDialog(window)
        dlg.exec()
    prompt_generator_action.triggered.connect(open_prompt_generator)
    tools_menu.addAction(prompt_generator_action)

    
    menubar.addMenu(file_menu)
    menubar.addMenu(edit_menu)
    menubar.addMenu(metadata_menu)
    menubar.addMenu(prompt_menu)
    menubar.addMenu(api_menu)
    menubar.addMenu(tools_menu)
    menubar.addMenu(help_menu)
    window.setMenuBar(menubar)
    window.setMenuBar(menubar)
