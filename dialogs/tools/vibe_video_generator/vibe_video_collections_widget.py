from PySide6.QtWidgets import (QWidget, QVBoxLayout, QToolBar, QToolButton, QTreeWidget,
                               QTreeWidgetItem, QTreeWidgetItemIterator, QHeaderView, QMessageBox,
                               QMenu)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QAction
import qtawesome as qta
from dialogs.tools.vibe_video_generator.vibe_video_new_collection_dialog import NewCollectionDialog


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

        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setFloatable(False)

        self.new_collection_btn = QToolButton()
        self.new_collection_btn.setIcon(qta.icon('fa6s.folder-plus'))
        self.new_collection_btn.setText(' New Collection')
        self.new_collection_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.new_collection_btn.setToolTip('Create new root collection')
        self.new_collection_btn.clicked.connect(self._on_new_collection)
        toolbar.addWidget(self.new_collection_btn)

        self.new_subfolder_btn = QToolButton()
        self.new_subfolder_btn.setIcon(qta.icon('fa6s.folder-tree'))
        self.new_subfolder_btn.setText(' New Subfolder')
        self.new_subfolder_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.new_subfolder_btn.setToolTip('Create subfolder under selected collection')
        self.new_subfolder_btn.clicked.connect(self._on_new_subfolder)
        toolbar.addWidget(self.new_subfolder_btn)

        self.rename_btn = QToolButton()
        self.rename_btn.setIcon(qta.icon('fa6s.pen'))
        self.rename_btn.setText(' Rename')
        self.rename_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.rename_btn.setToolTip('Rename selected collection')
        self.rename_btn.clicked.connect(self._on_rename)
        toolbar.addWidget(self.rename_btn)

        self.delete_btn = QToolButton()
        self.delete_btn.setIcon(qta.icon('fa6s.trash'))
        self.delete_btn.setText(' Delete')
        self.delete_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.delete_btn.setToolTip('Delete selected collection and all its scripts')
        self.delete_btn.clicked.connect(self._on_delete)
        toolbar.addWidget(self.delete_btn)

        layout.addWidget(toolbar)

        self.collections_tree = QTreeWidget()
        self.collections_tree.setHeaderLabels(['Collection', 'Scripts'])
        self.collections_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.collections_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.collections_tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.collections_tree.setExpandsOnDoubleClick(False)
        self.collections_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.collections_tree.customContextMenuRequested.connect(self._show_context_menu)
        self.collections_tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.collections_tree.itemDoubleClicked.connect(self._on_double_click)
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
        count = collection.get('script_count', 0)

        if parent_item is None:
            item = QTreeWidgetItem(self.collections_tree)
        else:
            item = QTreeWidgetItem(parent_item)

        item.setIcon(0, icon)
        item.setText(0, name)
        item.setText(1, str(count))
        item.setTextAlignment(1, Qt.AlignRight)
        item.setData(0, Qt.UserRole, collection)

        for child in collection.get('children', []):
            self._add_tree_item(child, item)

    def _on_selection_changed(self):
        selected = self.collections_tree.selectedItems()
        if selected:
            item = selected[0]
            # Auto-expand if item has children
            if item.childCount() > 0:
                item.setExpanded(True)
            data = item.data(0, Qt.UserRole)
            self.current_collection = data
            self.collection_selected.emit(data)
        else:
            self.current_collection = None
            self.collection_selected.emit(None)

    def _on_double_click(self, item, column):
        item.setExpanded(not item.isExpanded())

    def _show_context_menu(self, pos):
        item = self.collections_tree.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        rename_action = QAction(qta.icon('fa6s.pen'), 'Rename', menu)
        rename_action.triggered.connect(self._on_rename)
        menu.addAction(rename_action)

        menu.addSeparator()

        delete_action = QAction(qta.icon('fa6s.trash'), 'Delete', menu)
        delete_action.triggered.connect(self._on_delete)
        menu.addAction(delete_action)

        menu.exec(self.collections_tree.viewport().mapToGlobal(pos))

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
