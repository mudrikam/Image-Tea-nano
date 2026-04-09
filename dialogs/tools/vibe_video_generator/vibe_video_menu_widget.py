from PySide6.QtWidgets import QMenuBar, QMenu, QMessageBox
from PySide6.QtCore import Signal, Qt
import qtawesome as qta
from dialogs.tools.vibe_video_generator.vibe_video_edit_script_dialog import EditScriptDialog
from dialogs.tools.vibe_video_generator.vibe_video_new_collection_dialog import NewCollectionDialog


class MenuWidget(QMenuBar):
    new_script_requested = Signal(object)
    new_collection_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.collections_widget = None
        self.scripts_widget = None
        self._setup_menus()

    def _setup_menus(self):
        file_menu = QMenu('File', self)
        self.addMenu(file_menu)

        new_collection_action = file_menu.addAction(
            qta.icon('fa6s.folder-plus'), 'New Collection'
        )
        new_collection_action.setShortcut('Ctrl+Shift+N')
        new_collection_action.triggered.connect(self._on_new_collection)

        file_menu.addSeparator()

        new_script_action = file_menu.addAction(
            qta.icon('fa6s.file-circle-plus'), 'New Script'
        )
        new_script_action.setShortcut('Ctrl+N')
        new_script_action.triggered.connect(self._on_new_script)

        edit_menu = QMenu('Edit', self)
        self.addMenu(edit_menu)



    def _on_new_collection(self):
        if not self.collections_widget:
            return
        dlg = NewCollectionDialog(self)
        if dlg.exec():
            self.collections_widget.db.add_remotion_collection(
                name=dlg.collection_name,
                description=dlg.collection_description,
                icon=dlg.selected_icon,
                color=dlg.selected_color
            )
            self.collections_widget.load_collections()
            self.new_collection_requested.emit()

    def _on_new_script(self):
        if not self.collections_widget or not self.scripts_widget:
            return

        db = self.collections_widget.db
        if not db:
            return

        selected = self.collections_widget.current_collection
        if not selected:
            all_collections = db.get_remotion_collections()
            if not all_collections:
                default_id = db.add_remotion_collection(
                    name='Default',
                    description='Default collection',
                    icon='folder',
                    color=None
                )
                self.collections_widget.load_collections()
                selected = db.get_remotion_collection(default_id)
            else:
                QMessageBox.information(self, 'No Collection', 'Please select a collection first.')
                return

        collection_id = selected['id']
        creds = self._get_ai_credentials()
        dlg = EditScriptDialog(self, collection_id=collection_id, db=db,
                               api_key=creds['api_key'], endpoint=creds['endpoint'],
                               service=creds['service'], model=creds['model'])
        if dlg.exec():
            self.new_script_requested.emit(collection_id)

    def _get_ai_credentials(self):
        parent_dlg = self.parent()
        while parent_dlg and not hasattr(parent_dlg, 'api_key'):
            parent_dlg = parent_dlg.parent()
        if parent_dlg and hasattr(parent_dlg, 'api_key'):
            endpoint = getattr(parent_dlg, 'selected_endpoint', '')
            return {
                'api_key': parent_dlg.api_key or '',
                'endpoint': endpoint or '',
                'service': parent_dlg.selected_service or '',
                'model': parent_dlg.selected_model_name or ''
            }
        return {'api_key': '', 'endpoint': '', 'service': '', 'model': ''}


