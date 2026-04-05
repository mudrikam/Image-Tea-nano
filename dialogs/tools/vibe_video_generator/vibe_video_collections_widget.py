from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget,
                               QTreeWidgetItem, QTreeWidgetItemIterator, QMessageBox,
                               QMenu)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
import qtawesome as qta
from dialogs.tools.vibe_video_generator.vibe_video_new_collection_dialog import NewCollectionDialog
from dialogs.tools.vibe_video_generator.vibe_video_edit_script_dialog import EditScriptDialog


class CollectionsWidget(QWidget):
    collection_selected = Signal(object)
    collection_created = Signal()
    collection_updated = Signal()
    collection_deleted = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = parent.db if parent else None
        self.current_collection = None
        self._setup_ui()
        self.load_collections()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self.collections_tree = QTreeWidget()
        self.collections_tree.setHeaderLabel('Collections')
        self.collections_tree.header().hide()
        self.collections_tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.collections_tree.setExpandsOnDoubleClick(False)
        self.collections_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.collections_tree.customContextMenuRequested.connect(self._show_context_menu)
        self.collections_tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.collections_tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.collections_tree)

    def load_collections(self):
        if not self.db:
            return
        current_id = self.current_collection['id'] if self.current_collection else None
        self.collections_tree.clear()
        tree = self.db.get_remotion_collection_tree()
        for col in tree:
            self._add_tree_item(col, None)
        if current_id:
            self._select_by_id(current_id)

    def _select_by_id(self, collection_id):
        iterator = QTreeWidgetItemIterator(self.collections_tree)
        while iterator.value():
            item = iterator.value()
            data = item.data(0, Qt.UserRole)
            if data and data.get('id') == collection_id:
                self.collections_tree.setCurrentItem(item)
                item.setExpanded(True)
                return
            iterator += 1

    def _add_tree_item(self, collection, parent_item):
        icon_name = collection.get('icon', 'folder')
        color = collection.get('color') or 'gray'
        if '.' not in icon_name:
            full_icon = f'fa6s.{icon_name}'
        else:
            full_icon = icon_name
        try:
            icon = qta.icon(full_icon, color=color)
        except Exception:
            icon = qta.icon('fa6s.folder', color=color)

        name = collection.get('name', 'Unnamed')

        if parent_item is None:
            item = QTreeWidgetItem(self.collections_tree)
        else:
            item = QTreeWidgetItem(parent_item)

        item.setIcon(0, icon)
        item.setText(0, name)
        item.setData(0, Qt.UserRole, {'type': 'collection', **collection})
        item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)

        for child in collection.get('children', []):
            self._add_tree_item(child, item)

        collection_id = collection.get('id')
        if collection_id and self.db:
            scripts = self.db.get_remotion_scripts(collection_id, active_only=True)
            for script in scripts:
                script_icon = qta.icon('fa6s.file-code', color='#58a6ff')
                script_item = QTreeWidgetItem(item)
                script_item.setIcon(0, script_icon)
                script_item.setText(0, script.get('name', 'Unnamed'))
                script_item.setData(0, Qt.UserRole, {'type': 'script', **script})
                script_item.setChildIndicatorPolicy(QTreeWidgetItem.DontShowIndicator)

    def _on_item_clicked(self, item, column):
        data = item.data(0, Qt.UserRole)
        if data and data.get('type') == 'collection':
            if item.childCount() > 0:
                item.setExpanded(not item.isExpanded())
            self.current_collection = data
            self.collection_selected.emit(data)
        elif data and data.get('type') == 'script':
            self.collection_selected.emit(data)

    def _on_selection_changed(self):
        selected = self.collections_tree.selectedItems()
        if not selected:
            self.current_collection = None
            self.collection_selected.emit(None)

    def _show_context_menu(self, pos):
        item = self.collections_tree.itemAt(pos)
        if not item:
            menu = QMenu(self)
            new_action = QAction(qta.icon('fa6s.folder-plus'), 'New Collection', menu)
            new_action.triggered.connect(self._on_new_collection)
            menu.addAction(new_action)
            menu.exec(self.collections_tree.viewport().mapToGlobal(pos))
            return

        data = item.data(0, Qt.UserRole)
        if not data:
            return

        item_type = data.get('type')

        if item_type == 'collection':
            menu = QMenu(self)
            new_action = QAction(qta.icon('fa6s.folder-plus'), 'New Collection', menu)
            new_action.triggered.connect(self._on_new_collection)
            menu.addAction(new_action)

            new_sub_action = QAction(qta.icon('fa6s.folder-tree'), 'New Subfolder', menu)
            new_sub_action.triggered.connect(self._on_new_subfolder)
            menu.addAction(new_sub_action)

            new_script_action = QAction(qta.icon('fa6s.file-circle-plus'), 'New Script', menu)
            new_script_action.triggered.connect(lambda: self._on_new_script(data))
            menu.addAction(new_script_action)

            menu.addSeparator()

            rename_action = QAction(qta.icon('fa6s.pen'), 'Rename', menu)
            rename_action.triggered.connect(self._on_rename)
            menu.addAction(rename_action)

            delete_action = QAction(qta.icon('fa6s.trash'), 'Delete', menu)
            delete_action.triggered.connect(self._on_delete)
            menu.addAction(delete_action)
        elif item_type == 'script':
            menu = QMenu(self)
            edit_action = QAction(qta.icon('fa6s.pen-to-square'), 'Edit Script', menu)
            edit_action.triggered.connect(lambda: self._on_edit_script(data))
            menu.addAction(edit_action)

            rename_action = QAction(qta.icon('fa6s.pen'), 'Rename Script', menu)
            rename_action.triggered.connect(lambda: self._on_rename_script(data))
            menu.addAction(rename_action)

            menu.addSeparator()

            delete_script_action = QAction(qta.icon('fa6s.trash'), 'Delete Script', menu)
            delete_script_action.triggered.connect(lambda: self._on_delete_script(data))
            menu.addAction(delete_script_action)
        else:
            return

        menu.exec(self.collections_tree.viewport().mapToGlobal(pos))

    def _on_edit_script(self, script_data):
        if not self.db:
            return
        script_id = script_data.get('id')
        collection_id = script_data.get('collection_id')
        dlg = EditScriptDialog(self, collection_id=collection_id, db=self.db)
        dlg.setWindowTitle('Edit Script')
        dlg.name_edit.setText(script_data.get('name', ''))
        dlg.desc_edit.setText(script_data.get('description') or '')
        dlg.script_edit.setText(script_data.get('script_content', ''))
        if dlg.exec():
            self.db.update_remotion_script(
                script_id,
                name=dlg.name_edit.text().strip(),
                script_content=dlg.script_edit.toPlainText().strip(),
                description=dlg.desc_edit.text().strip() or None,
            )
            self.load_collections()
            self.collection_updated.emit()

    def _on_rename_script(self, script_data):
        if not self.db:
            return
        script_id = script_data.get('id')
        old_name = script_data.get('name', '')
        from PySide6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(self, 'Rename Script', 'Enter new name:', text=old_name)
        if ok and new_name.strip():
            self.db.update_remotion_script(script_id, name=new_name.strip())
            self.load_collections()
            self.collection_updated.emit()

    def _on_delete_script(self, script_data):
        if not self.db:
            return
        script_id = script_data.get('id')
        script_name = script_data.get('name', '')
        reply = QMessageBox.question(self, 'Confirm Delete', f'Delete script "{script_name}"?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_remotion_script(script_id)
            self.load_collections()
            self.collection_updated.emit()

    def _on_new_script(self, collection_data):
        if not self.db:
            return
        collection_id = collection_data.get('id')
        dlg = EditScriptDialog(self, collection_id=collection_id, db=self.db)
        if dlg.exec():
            self.load_collections()
            self.collection_updated.emit()

    def _on_new_collection(self):
        if not self.db:
            return
        dlg = NewCollectionDialog(self)
        if dlg.exec():
            self.db.add_remotion_collection(
                name=dlg.collection_name,
                description=dlg.collection_description,
                icon=dlg.selected_icon,
                color=dlg.selected_color
            )
            self.load_collections()
            self.collection_created.emit()

    def _on_new_subfolder(self):
        if not self.db:
            return
        selected = self.collections_tree.selectedItems()
        if not selected:
            QMessageBox.information(self, 'No Selection', 'Please select a collection first to create a subfolder.')
            return
        parent_data = selected[0].data(0, Qt.UserRole)
        parent_id = parent_data['id']
        parent_name = parent_data.get('name', 'Unknown')

        dlg = NewCollectionDialog(self, parent_collection_id=parent_id, parent_collection_name=parent_name)
        if dlg.exec():
            self.db.add_remotion_collection(
                name=dlg.collection_name,
                description=dlg.collection_description,
                parent_collection_id=parent_id,
                icon=dlg.selected_icon,
                color=dlg.selected_color
            )
            self.load_collections()
            self._expand_to_parent(parent_id)
            self.collection_created.emit()

    def _on_rename(self):
        selected = self.collections_tree.selectedItems()
        if not selected:
            QMessageBox.information(self, 'No Selection', 'Please select a collection to rename.')
            return
        item = selected[0]
        data = item.data(0, Qt.UserRole)
        collection_id = data['id']
        old_name = data.get('name', '')

        dlg = NewCollectionDialog(self, parent_collection_name=f'Renaming "{old_name}"')
        dlg.name_edit.setText(old_name)
        dlg.desc_edit.setText(data.get('description') or '')
        dlg.icon_input.setText(data.get('icon', 'folder'))
        dlg.selected_icon = data.get('icon', 'folder')
        if data.get('color'):
            dlg.color_input.setText(data['color'])
            dlg.selected_color = data['color']
        dlg.setWindowTitle('Rename Collection')
        dlg._update_icon_preview()
        dlg._update_color_preview()

        if dlg.exec():
            self.db.update_remotion_collection(
                collection_id,
                name=dlg.collection_name,
                description=dlg.collection_description,
                icon=dlg.selected_icon,
                color=dlg.selected_color
            )
            self.load_collections()
            self.collection_updated.emit()

    def _on_delete(self):
        selected = self.collections_tree.selectedItems()
        if not selected:
            QMessageBox.information(self, 'No Selection', 'Please select a collection to delete.')
            return
        item = selected[0]
        data = item.data(0, Qt.UserRole)
        collection_id = data['id']
        collection_name = data.get('name', '')
        script_count = data.get('script_count', 0)

        msg = f'Delete collection "{collection_name}"'
        if script_count > 0:
            msg += f' and all {script_count} script(s) inside it?'
        else:
            msg += '?'

        reply = QMessageBox.question(self, 'Confirm Delete', msg,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_remotion_collection(collection_id)
            self.current_collection = None
            self.collection_selected.emit(None)
            self.load_collections()
            self.collection_deleted.emit()

    def _expand_to_parent(self, parent_id):
        iterator = QTreeWidgetItemIterator(self.collections_tree)
        while iterator.value():
            item = iterator.value()
            data = item.data(0, Qt.UserRole)
            if data and data.get('id') == parent_id:
                item.setExpanded(True)
                break
            iterator += 1
