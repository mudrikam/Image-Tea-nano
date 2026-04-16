from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget,
                               QTreeWidgetItem, QTreeWidgetItemIterator, QMessageBox,
                               QMenu, QLineEdit, QFileDialog, QProgressDialog)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction, QColor, QBrush
import qtawesome as qta
from ui.theme_system import theme
from dialogs.tools.vibe_video_generator.vibe_video_new_collection_dialog import NewCollectionDialog
from dialogs.tools.vibe_video_generator.vibe_video_edit_script_dialog import EditScriptDialog
from dialogs.tools.vibe_video_generator.vibe_video_output_tab import sanitize_filename
import os
import tempfile
import zipfile


class CollectionsWidget(QWidget):
    collection_selected = Signal(object)
    collection_created = Signal()
    collection_updated = Signal()
    collection_deleted = Signal()
    render_collection_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = parent.db if parent else None
        self.current_collection = None
        self._last_highlighted_item = None  # Track only the currently highlighted item
        self._setup_ui()
        self.load_collections()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('Search scripts or collections...')
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search_input)

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

        # Save selected script ID if a script is selected
        selected_script_id = None
        selected = self.collections_tree.selectedItems()
        if selected:
            data = selected[0].data(0, Qt.UserRole)
            if data and data.get('type') == 'script':
                selected_script_id = data.get('id')

        # Save expanded state
        expanded_ids = set()
        iterator = QTreeWidgetItemIterator(self.collections_tree)
        while iterator.value():
            item = iterator.value()
            if item.isExpanded():
                data = item.data(0, Qt.UserRole)
                if data and data.get('id'):
                    expanded_ids.add(data['id'])
            iterator += 1

        self.collections_tree.blockSignals(True)
        try:
            self.collections_tree.clear()
            tree = self.db.get_remotion_collection_tree()
            for col in tree:
                self._add_tree_item(col, None)

            self._apply_filter(self.search_input.text(), preserve_selection=False)

            # Restore expanded state
            iterator = QTreeWidgetItemIterator(self.collections_tree)
            while iterator.value():
                item = iterator.value()
                data = item.data(0, Qt.UserRole)
                if data and data.get('id') in expanded_ids:
                    item.setExpanded(True)
                iterator += 1

            # Restore selection and emit signal
            if selected_script_id:
                self._select_script_by_id(selected_script_id)
            elif current_id:
                self._select_by_id(current_id)
            else:
                # No previous selection - select first root collection if any
                first_root = self.collections_tree.topLevelItem(0)
                if first_root:
                    self.collections_tree.setCurrentItem(first_root)
                    data = first_root.data(0, Qt.UserRole)
                    if data:
                        self.current_collection = data
                        self.collection_selected.emit(data)
        finally:
            self.collections_tree.blockSignals(False)

    def _select_by_id(self, collection_id):
        iterator = QTreeWidgetItemIterator(self.collections_tree)
        while iterator.value():
            item = iterator.value()
            data = item.data(0, Qt.UserRole)
            if data and data.get('id') == collection_id and not item.isHidden():
                self.collections_tree.setCurrentItem(item)
                self.current_collection = data
                item.setExpanded(True)
                return
            iterator += 1

    def _select_script_by_id(self, script_id):
        iterator = QTreeWidgetItemIterator(self.collections_tree)
        while iterator.value():
            item = iterator.value()
            data = item.data(0, Qt.UserRole)
            if data and data.get('type') == 'script' and data.get('id') == script_id and not item.isHidden():
                self.collections_tree.setCurrentItem(item)
                self.current_collection = data
                parent = item.parent()
                while parent:
                    parent.setExpanded(True)
                    parent = parent.parent()
                return
            iterator += 1

    def _item_matches_search(self, item, search_text):
        if not search_text:
            return True
        data = item.data(0, Qt.UserRole) or {}
        haystacks = [
            item.text(0),
            data.get('name', ''),
            data.get('description', ''),
            data.get('tags', ''),
            data.get('script_content', '') if data.get('type') == 'script' else ''
        ]
        search_lower = search_text.lower()
        return any(search_lower in str(value).lower() for value in haystacks if value)

    def _filter_tree_item(self, item, search_text):
        child_match = False
        for index in range(item.childCount()):
            child = item.child(index)
            if self._filter_tree_item(child, search_text):
                child_match = True

        direct_match = self._item_matches_search(item, search_text)
        visible = direct_match or child_match
        item.setHidden(not visible)
        if search_text and child_match:
            item.setExpanded(True)
        return visible

    def _apply_filter(self, text, preserve_selection=True):
        selected_script_id = None
        selected_items = self.collections_tree.selectedItems()
        if preserve_selection and selected_items:
            selected_data = selected_items[0].data(0, Qt.UserRole)
            if selected_data and selected_data.get('type') == 'script':
                selected_script_id = selected_data.get('id')

        search_text = (text or '').strip()
        self.collections_tree.blockSignals(True)
        try:
            for index in range(self.collections_tree.topLevelItemCount()):
                self._filter_tree_item(self.collections_tree.topLevelItem(index), search_text)
        finally:
            self.collections_tree.blockSignals(False)

        current_item = self.collections_tree.currentItem()
        if current_item and current_item.isHidden():
            self.collections_tree.setCurrentItem(None)
            self.current_collection = None
            self.collection_selected.emit(None)

        if preserve_selection and selected_script_id:
            self._select_script_by_id(selected_script_id)

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
        item.setData(0, Qt.UserRole, {'type': 'collection', **collection})
        item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)

        for child in collection.get('children', []):
            self._add_tree_item(child, item)

        scripts = []
        collection_id = collection.get('id')
        if collection_id and self.db:
            scripts = self.db.get_remotion_scripts(collection_id, active_only=True)
            for idx, script in enumerate(scripts, 1):
                script_icon = qta.icon('fa6s.file-code', color=theme.get_color('primary'))
                script_item = QTreeWidgetItem(item)
                script_item.setIcon(0, script_icon)
                script_item.setText(0, f"{idx}. {script.get('name', 'Unnamed')}")
                script_item.setData(0, Qt.UserRole, {'type': 'script', **script})
                script_item.setChildIndicatorPolicy(QTreeWidgetItem.DontShowIndicator)

        n_scripts = len(scripts)
        n_collections = len(collection.get('children', []))
        script_label = "1 Script" if n_scripts == 1 else f"{n_scripts} Scripts"
        coll_label = "1 Collection" if n_collections == 1 else f"{n_collections} Collections"
        item.setText(0, f"{name} | {script_label} | {coll_label}")

    def _on_item_clicked(self, item, column):
        data = item.data(0, Qt.UserRole)
        if data and data.get('type') == 'collection':
            if item.childCount() > 0:
                item.setExpanded(not item.isExpanded())
            self.current_collection = data
            self.collection_selected.emit(data)
        elif data and data.get('type') == 'script':
            self.current_collection = data
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

            export_zip_action = QAction(qta.icon('fa6s.file-zipper'), 'Export to ZIP', menu)
            export_zip_action.triggered.connect(lambda: self._export_collection_to_zip(data))
            menu.addAction(export_zip_action)

            render_collection_action = QAction(qta.icon('fa6s.film'), 'Render This Collection', menu)
            render_collection_action.triggered.connect(lambda: self._on_render_collection(data))
            menu.addAction(render_collection_action)

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

            save_tsx_action = QAction(qta.icon('fa6s.file-export'), 'Save as TSX File', menu)
            save_tsx_action.triggered.connect(lambda: self._on_save_script_as_tsx(data))
            menu.addAction(save_tsx_action)

            menu.addSeparator()

            delete_script_action = QAction(qta.icon('fa6s.trash'), 'Delete Script', menu)
            delete_script_action.triggered.connect(lambda: self._on_delete_script(data))
            menu.addAction(delete_script_action)
        else:
            return

        menu.exec(self.collections_tree.viewport().mapToGlobal(pos))

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

    def _on_edit_script(self, script_data):
        if not self.db:
            return
        script_id = script_data.get('id')
        creds = self._get_ai_credentials()
        dlg = EditScriptDialog(self, collection_id=script_data.get('collection_id'), db=self.db, script_id=script_id,
                               api_key=creds['api_key'], endpoint=creds['endpoint'],
                               service=creds['service'], model=creds['model'])
        dlg.script_updated.connect(self._on_script_edited)
        if dlg.exec():
            self.collection_updated.emit()

    def _on_script_edited(self, script_data):
        self.load_collections()
        self.collection_selected.emit(script_data)

    def _on_save_script_as_tsx(self, script_data):
        if not self.db:
            return
        script_id = script_data.get('id')
        script_name = script_data.get('name', 'script')
        script = self.db.get_remotion_script(script_id)
        if not script:
            QMessageBox.warning(self, 'Error', 'Could not load script content.')
            return

        content = script.get('script_content', '')
        if not content:
            QMessageBox.warning(self, 'Error', 'Script content is empty.')
            return

        # Ensure .tsx extension
        if not script_name.endswith('.tsx'):
            default_name = f'{script_name}.tsx'
        else:
            default_name = script_name

        from PySide6.QtWidgets import QFileDialog
        import os

        home_dir = os.path.expanduser('~')
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            'Save Script as TSX',
            os.path.join(home_dir, default_name),
            'TypeScript React Files (*.tsx);;All Files (*)'
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            QMessageBox.information(self, 'Success', f'Script saved to:\n{file_path}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to save file:\n{str(e)}')

    def _on_rename_script(self, script_data):
        if not self.db:
            return
        script_id = script_data.get('id')
        old_name = script_data.get('name', '')
        from PySide6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(self, 'Rename Script', 'Enter new name:', text=old_name)
        if ok and new_name.strip():
            self.db.update_remotion_script(script_id, name=new_name.strip())
            script_data = self.db.get_remotion_script(script_id)
            self.load_collections()
            self.collection_selected.emit(script_data)

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
        creds = self._get_ai_credentials()
        dlg = EditScriptDialog(self, collection_id=collection_id, db=self.db,
                               api_key=creds['api_key'], endpoint=creds['endpoint'],
                               service=creds['service'], model=creds['model'])
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

        preview = self.db.get_remotion_collection_delete_preview(collection_id)
        sub_collections = preview['collections']
        scripts = preview['scripts']

        msg = f'You are about to delete collection <b>"{collection_name}"</b>.'

        if sub_collections or scripts:
            msg += '<br><br>The following items will also be deleted:'
            if sub_collections:
                items_html = ''.join(f'<li>{n}</li>' for n in sub_collections)
                msg += f'<br><b>Sub-collections ({len(sub_collections)}):</b><ul>{items_html}</ul>'
            if scripts:
                items_html = ''.join(f'<li>{n}</li>' for n in scripts)
                msg += f'<br><b>Scripts ({len(scripts)}):</b><ul>{items_html}</ul>'
        else:
            msg += '<br><br>This collection is empty.'

        msg += '<br><br>This action cannot be undone.'

        box = QMessageBox(self)
        box.setWindowTitle('Confirm Delete')
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(msg)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        yes_btn = box.button(QMessageBox.StandardButton.Yes)
        yes_btn.setIcon(qta.icon('fa6s.trash'))
        no_btn = box.button(QMessageBox.StandardButton.No)
        no_btn.setIcon(qta.icon('fa6s.xmark'))
        reply = box.exec()

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

    def _on_render_collection(self, collection_data):
        """Handle 'Render This Collection' context menu action."""
        self.render_collection_requested.emit(collection_data)

    def highlight_rendering_script(self, script_id):
        """Highlight the currently rendering script in the tree."""
        # Clear only previous highlight
        self._clear_last_highlight()

        primary_bg = QColor(theme.get_color('primary'))
        white_fg = QColor(theme.get_color('white'))

        iterator = QTreeWidgetItemIterator(self.collections_tree)
        while iterator.value():
            item = iterator.value()
            data = item.data(0, Qt.UserRole)
            if data and data.get('type') == 'script' and data.get('id') == script_id:
                item.setBackground(0, primary_bg)
                item.setForeground(0, white_fg)
                self._last_highlighted_item = item
                self.collections_tree.scrollToItem(item)
                break
            iterator += 1

    def _clear_last_highlight(self):
        """Clear highlight from the previously highlighted item only."""
        if self._last_highlighted_item:
            # Reset to default: use NoBrush to restore system appearance
            self._last_highlighted_item.setBackground(0, QBrush())
            self._last_highlighted_item.setForeground(0, QBrush())
            self._last_highlighted_item = None

    def clear_render_highlight(self):
        """Remove current rendering highlight (used when batch finishes)."""
        self._clear_last_highlight()

    def _export_collection_to_zip(self, collection_data):
        """Export all scripts in a collection (including sub-collections) to a ZIP file."""
        if not self.db:
            return

        collection_id = collection_data.get('id')
        collection_name = collection_data.get('name', 'collection')

        # Ask user for save location
        safe_name = sanitize_filename(collection_name)
        default_zip_name = f'{safe_name}.zip'
        home_dir = os.path.expanduser('~')
        zip_path, _ = QFileDialog.getSaveFileName(
            self,
            'Export Collection to ZIP',
            os.path.join(home_dir, default_zip_name),
            'ZIP Files (*.zip);;All Files (*)'
        )

        if not zip_path:
            return

        # Create temporary directory for staging
        with tempfile.TemporaryDirectory(prefix='vibe_export_') as temp_dir:
            # Recursively collect all scripts from this collection
            total_scripts = self._collect_all_scripts(collection_id)
            if total_scripts == 0:
                QMessageBox.information(self, 'Empty Collection', 'This collection has no scripts to export.')
                return

            # Show progress dialog
            progress = QProgressDialog(f'Exporting {total_scripts} scripts...', 'Cancel', 0, total_scripts, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(500)
            progress.setValue(0)

            try:
                # Start recursive export
                exported = self._export_collection_recursive(collection_id, collection_name, temp_dir, progress)

                # Check if user cancelled (before closing the dialog)
                if progress.wasCanceled():
                    QMessageBox.information(self, 'Cancelled', 'Export was cancelled.')
                    return

            except Exception as e:
                QMessageBox.critical(self, 'Export Error', f'Failed to export collection:\n{str(e)}')
                return
            finally:
                progress.close()

            # Create ZIP archive
            try:
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            # Archive name relative to temp_dir
                            arcname = os.path.relpath(file_path, temp_dir)
                            zipf.write(file_path, arcname)
            except Exception as e:
                QMessageBox.critical(self, 'Export Error', f'Failed to create ZIP file:\n{str(e)}')
                return

            QMessageBox.information(
                self,
                'Export Complete',
                f'Exported {exported} script(s) to:\n{zip_path}'
            )

    def _collect_all_scripts(self, collection_id):
        """Count all scripts recursively in a collection and its sub-collections."""
        count = 0
        # Get direct scripts
        if self.db:
            scripts = self.db.get_remotion_scripts(collection_id, active_only=True)
            count += len(scripts)
            # Get scripts from sub-collections
            children = self.db.get_remotion_collections(parent_collection_id=collection_id)
            for child in children:
                count += self._collect_all_scripts(child.get('id'))
        return count

    def _export_collection_recursive(self, collection_id, folder_name, base_dir, progress):
        """Recursively export collection and all sub-collections. Returns number of scripts exported."""
        count = 0
        # Create folder for this collection
        safe_folder = sanitize_filename(folder_name)
        collection_dir = os.path.join(base_dir, safe_folder)
        os.makedirs(collection_dir, exist_ok=True)

        # Export scripts directly in this collection
        if self.db:
            scripts = self.db.get_remotion_scripts(collection_id, active_only=True)
            for idx, script in enumerate(scripts, 1):
                script_content = script.get('script_content', '')
                if script_content:
                    script_name = script.get('name', f'script_{idx}')
                    safe_name = sanitize_filename(script_name)
                    if not safe_name.endswith('.tsx'):
                        safe_name += '.tsx'
                    file_path = os.path.join(collection_dir, safe_name)
                    try:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(script_content)
                        count += 1
                    except Exception as e:
                        print(f'[Export] Failed to write script {script_name}: {e}')

            # Update progress
            progress.setValue(progress.value() + len(scripts))

            if progress.wasCanceled():
                return count

            # Recurse into sub-collections
            children = self.db.get_remotion_collections(parent_collection_id=collection_id)
            for child in children:
                child_name = child.get('name', 'subcollection')
                count += self._export_collection_recursive(child.get('id'), child_name, collection_dir, progress)

        return count
