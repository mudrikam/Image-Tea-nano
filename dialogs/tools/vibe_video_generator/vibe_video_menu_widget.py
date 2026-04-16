from PySide6.QtWidgets import QMenuBar, QMenu, QMessageBox
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QAction
import qtawesome as qta
from dialogs.tools.vibe_video_generator.vibe_video_edit_script_dialog import EditScriptDialog
from dialogs.tools.vibe_video_generator.vibe_video_new_collection_dialog import NewCollectionDialog


class MenuWidget(QMenuBar):
    new_script_requested = Signal(object)
    new_collection_requested = Signal()
    render_collection_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.collections_widget = None
        self.scripts_widget = None
        self._setup_menus()

    def _setup_menus(self):
        # Collection menu (text only, no icon on the menu itself)
        collection_menu = self.addMenu('Collection')

        self.new_collection_action = QAction(qta.icon('fa6s.folder-plus'), 'New Collection', self)
        self.new_collection_action.setShortcut('Ctrl+Shift+N')
        self.new_collection_action.setToolTip('Create a new collection to organize your scripts')
        self.new_collection_action.triggered.connect(self._on_new_collection)
        collection_menu.addAction(self.new_collection_action)

        self.new_subfolder_action = QAction(qta.icon('fa6s.folder-tree'), 'New Subfolder', self)
        self.new_subfolder_action.setToolTip('Create a subfolder inside the selected collection')
        self.new_subfolder_action.triggered.connect(self._on_new_subfolder)
        collection_menu.addAction(self.new_subfolder_action)

        collection_menu.addSeparator()

        self.new_script_action = QAction(qta.icon('fa6s.file-circle-plus'), 'New Script', self)
        self.new_script_action.setShortcut('Ctrl+N')
        self.new_script_action.setToolTip('Create a new script in the selected collection')
        self.new_script_action.triggered.connect(self._on_new_script)
        collection_menu.addAction(self.new_script_action)

        collection_menu.addSeparator()

        self.render_collection_action = QAction(qta.icon('fa6s.film'), 'Render This Collection', self)
        self.render_collection_action.setToolTip('Render all scripts in the selected collection')
        self.render_collection_action.triggered.connect(self._on_render_collection)
        collection_menu.addAction(self.render_collection_action)

        collection_menu.addSeparator()

        self.rename_collection_action = QAction(qta.icon('fa6s.pen'), 'Rename Collection', self)
        self.rename_collection_action.setToolTip('Rename the selected collection')
        self.rename_collection_action.triggered.connect(self._on_rename_collection)
        collection_menu.addAction(self.rename_collection_action)

        self.delete_collection_action = QAction(qta.icon('fa6s.trash'), 'Delete Collection', self)
        self.delete_collection_action.setToolTip('Delete the selected collection and all its scripts')
        self.delete_collection_action.triggered.connect(self._on_delete_collection)
        collection_menu.addAction(self.delete_collection_action)

        # Script menu (text only)
        script_menu = self.addMenu('Script')

        self.edit_script_action = QAction(qta.icon('fa6s.pen-to-square'), 'Edit Script', self)
        self.edit_script_action.setShortcut('Ctrl+E')
        self.edit_script_action.setToolTip('Edit the selected script')
        self.edit_script_action.triggered.connect(self._on_edit_script)
        script_menu.addAction(self.edit_script_action)

        self.rename_script_action = QAction(qta.icon('fa6s.pen'), 'Rename Script', self)
        self.rename_script_action.setToolTip('Rename the selected script')
        self.rename_script_action.triggered.connect(self._on_rename_script)
        script_menu.addAction(self.rename_script_action)

        self.save_tsx_action = QAction(qta.icon('fa6s.file-export'), 'Save as TSX File', self)
        self.save_tsx_action.setToolTip('Save script as a standalone .tsx file')
        self.save_tsx_action.triggered.connect(self._on_save_script_as_tsx)
        script_menu.addAction(self.save_tsx_action)

        script_menu.addSeparator()

        self.delete_script_action = QAction(qta.icon('fa6s.trash'), 'Delete Script', self)
        self.delete_script_action.setToolTip('Delete the selected script')
        self.delete_script_action.triggered.connect(self._on_delete_script)
        script_menu.addAction(self.delete_script_action)

        # Tools menu (text only)
        tools_menu = self.addMenu('Tools')

        self.export_zip_action = QAction(qta.icon('fa6s.file-zipper'), 'Export Collection to ZIP', self)
        self.export_zip_action.setToolTip('Export collection (with all scripts) to a ZIP file')
        self.export_zip_action.triggered.connect(self._on_export_zip)
        tools_menu.addAction(self.export_zip_action)

        self._update_actions_state()

    def _update_actions_state(self, *args, **kwargs):
        """Enable/disable actions based on current selection."""
        has_collections_widget = self.collections_widget is not None
        has_selected_collection = False
        has_selected_script = False

        if has_collections_widget:
            selected = self.collections_widget.current_collection
            if selected:
                if selected.get('type') == 'collection':
                    has_selected_collection = True
                elif selected.get('type') == 'script':
                    has_selected_script = True

        # Collection actions
        self.new_collection_action.setEnabled(has_collections_widget)
        self.new_subfolder_action.setEnabled(has_selected_collection)
        self.new_script_action.setEnabled(has_selected_collection or has_collections_widget)
        self.render_collection_action.setEnabled(has_selected_collection)
        self.rename_collection_action.setEnabled(has_selected_collection)
        self.delete_collection_action.setEnabled(has_selected_collection)

        # Script actions
        self.edit_script_action.setEnabled(has_selected_script)
        self.rename_script_action.setEnabled(has_selected_script)
        self.save_tsx_action.setEnabled(has_selected_script)
        self.delete_script_action.setEnabled(has_selected_script)

        # Tools
        self.export_zip_action.setEnabled(has_selected_collection)

    def set_collections_widget(self, widget):
        """Connect to collections widget for selection tracking."""
        if self.collections_widget:
            try:
                self.collections_widget.collection_selected.disconnect(self._update_actions_state)
            except:
                pass

        self.collections_widget = widget
        if widget:
            widget.collection_selected.connect(self._update_actions_state)
            # Also refresh when data changes
            if hasattr(widget, 'collection_updated'):
                widget.collection_updated.connect(self._update_actions_state)
            if hasattr(widget, 'collection_created'):
                widget.collection_created.connect(self._update_actions_state)
            if hasattr(widget, 'collection_deleted'):
                widget.collection_deleted.connect(self._update_actions_state)
        self._update_actions_state()

    def set_scripts_widget(self, widget):
        """Connect to scripts widget for status updates."""
        self.scripts_widget = widget
        self._update_actions_state()

    # ----- Collection actions -----
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

    def _on_new_subfolder(self):
        if not self.collections_widget:
            return
        self.collections_widget._on_new_subfolder()

    def _on_rename_collection(self):
        if not self.collections_widget:
            return
        self.collections_widget._on_rename()

    def _on_delete_collection(self):
        if not self.collections_widget:
            return
        self.collections_widget._on_delete()

    def _on_render_collection(self):
        if not self.collections_widget:
            return
        selected = self.collections_widget.current_collection
        if selected and selected.get('type') == 'collection':
            self.collections_widget._on_render_collection(selected)
            self.render_collection_requested.emit(selected)

    def _on_export_zip(self):
        if not self.collections_widget:
            return
        selected = self.collections_widget.current_collection
        if selected and selected.get('type') == 'collection':
            self.collections_widget._export_collection_to_zip(selected)

    # ----- Script actions -----
    def _on_new_script(self):
        if not self.collections_widget:
            return
        self.collections_widget._on_new_script(self.collections_widget.current_collection)

    def _on_edit_script(self):
        if not self.collections_widget:
            return
        selected = self.collections_widget.current_collection
        if selected and selected.get('type') == 'script':
            self.collections_widget._on_edit_script(selected)

    def _on_rename_script(self):
        if not self.collections_widget:
            return
        selected = self.collections_widget.current_collection
        if selected and selected.get('type') == 'script':
            self.collections_widget._on_rename_script(selected)

    def _on_save_script_as_tsx(self):
        if not self.collections_widget:
            return
        selected = self.collections_widget.current_collection
        if selected and selected.get('type') == 'script':
            self.collections_widget._on_save_script_as_tsx(selected)

    def _on_delete_script(self):
        if not self.collections_widget:
            return
        selected = self.collections_widget.current_collection
        if selected and selected.get('type') == 'script':
            self.collections_widget._on_delete_script(selected)


