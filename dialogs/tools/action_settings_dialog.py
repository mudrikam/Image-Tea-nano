import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                               QListWidget, QListWidgetItem, QLineEdit, QComboBox, QCheckBox, QSpinBox,
                               QMessageBox, QFileDialog, QWidget, QTabWidget, QTableWidget,
                               QTableWidgetItem, QDialogButtonBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QFont
from config import BASE_PATH
import qtawesome as qta
from database.db_operation import ImageTeaDB
from helpers.tools.action_sequencer_helpers.action_sequencer_config_helper import ActionSequencerConfig


class ActionSettingsDialog(QDialog):
    platforms_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Action Settings")
        self.setModal(True)
        
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.current_platform = None
        self.db = ImageTeaDB()
        self.config = ActionSequencerConfig()
        self.setup_ui()
        self.load_platforms()
        self.resize(600, 400)
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)
        
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        dialog_icon = qta.icon('fa6s.gears', color='#27AE60')
        icon_label = QLabel()
        icon_label.setPixmap(dialog_icon.pixmap(32, 32))
        header_layout.addWidget(icon_label)
        
        header_label = QLabel("Action Settings")
        header_font = QFont()
        header_font.setBold(True)
        header_font.setPointSize(12)
        header_label.setFont(header_font)
        header_layout.addWidget(header_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        self.tab_widget = QTabWidget()
        
        platform_tab = QWidget()
        platform_layout = QVBoxLayout()
        platform_layout.setSpacing(8)
        platform_layout.setContentsMargins(8, 8, 8, 8)
        
        platform_form_layout = QHBoxLayout()
        platform_form_layout.setSpacing(6)
        platform_icon = QLabel()
        platform_icon.setPixmap(qta.icon('fa6s.desktop', color='#888').pixmap(16, 16))
        platform_form_layout.addWidget(platform_icon)
        platform_label = QLabel("Platform:")
        platform_label.setMinimumWidth(80)
        platform_form_layout.addWidget(platform_label)
        self.name_input = QComboBox()
        self.name_input.setEditable(False)
        self.name_input.addItems(["Photoshop", "Illustrator"])
        self.name_input.setCurrentIndex(-1)
        self.name_input.currentTextChanged.connect(self.on_field_changed)
        platform_form_layout.addWidget(self.name_input, 1)
        platform_layout.addLayout(platform_form_layout)
        
        exec_path_layout = QHBoxLayout()
        exec_path_layout.setSpacing(6)
        exec_icon = QLabel()
        exec_icon.setPixmap(qta.icon('fa6s.file-code', color='#888').pixmap(16, 16))
        exec_path_layout.addWidget(exec_icon)
        exec_label = QLabel("Exe Path:")
        exec_label.setMinimumWidth(80)
        exec_path_layout.addWidget(exec_label)
        self.exec_path_input = QLineEdit()
        self.exec_path_input.setPlaceholderText("Path to .exe file")
        self.exec_path_input.textChanged.connect(self.on_field_changed)
        exec_path_layout.addWidget(self.exec_path_input, 1)
        self.browse_button = QPushButton(qta.icon('fa6s.folder-open'), "")
        self.browse_button.setMaximumWidth(32)
        self.browse_button.clicked.connect(self.on_browse_exec_path)
        exec_path_layout.addWidget(self.browse_button)
        platform_layout.addLayout(exec_path_layout)
        
        note_layout = QHBoxLayout()
        note_layout.setSpacing(6)
        note_icon = QLabel()
        note_icon.setPixmap(qta.icon('fa6s.note-sticky', color='#888').pixmap(16, 16))
        note_layout.addWidget(note_icon)
        note_label = QLabel("Note:")
        note_label.setMinimumWidth(80)
        note_layout.addWidget(note_label)
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("Optional note (e.g., collection info)")
        self.note_input.textChanged.connect(self.on_field_changed)
        note_layout.addWidget(self.note_input, 1)
        platform_layout.addLayout(note_layout)
        
        self.platform_list = QListWidget()
        self.platform_list.setAlternatingRowColors(True)
        self.platform_list.setSpacing(2)
        self.platform_list.currentItemChanged.connect(self.on_platform_selected)
        platform_layout.addWidget(self.platform_list)
        
        platform_button_layout = QHBoxLayout()
        platform_button_layout.setSpacing(4)
        
        self.add_button = QPushButton(qta.icon('fa6s.plus'), " Add")
        self.add_button.clicked.connect(self.on_add_platform)
        platform_button_layout.addWidget(self.add_button)
        
        self.remove_button = QPushButton(qta.icon('fa6s.trash'), " Remove")
        self.remove_button.clicked.connect(self.on_remove_platform)
        self.remove_button.setEnabled(False)
        platform_button_layout.addWidget(self.remove_button)
        
        platform_button_layout.addStretch()
        platform_layout.addLayout(platform_button_layout)
        
        platform_tab.setLayout(platform_layout)
        self.tab_widget.addTab(platform_tab, qta.icon('fa6s.desktop'), " Platforms")
        
        output_tab = self.create_output_settings_tab()
        self.tab_widget.addTab(output_tab, qta.icon('fa6s.file-export'), " Output Settings")
        
        layout.addWidget(self.tab_widget)
        
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(4)
        footer_layout.addStretch()
        
        self.save_button = QPushButton(qta.icon('fa6s.floppy-disk'), " Save")
        self.save_button.clicked.connect(self.on_save_platform)
        self.save_button.setEnabled(False)
        self.save_button.setMaximumWidth(100)
        footer_layout.addWidget(self.save_button)
        
        close_button = QPushButton(qta.icon('fa6s.xmark'), " Close")
        close_button.setMaximumWidth(100)
        close_button.clicked.connect(self.accept)
        footer_layout.addWidget(close_button)
        
        layout.addLayout(footer_layout)
        
        self.setLayout(layout)
    
    def create_output_settings_tab(self):
        output_tab = QWidget()
        output_layout = QVBoxLayout()
        output_layout.setSpacing(8)
        output_layout.setContentsMargins(8, 8, 8, 8)
        
        prefix_layout = QHBoxLayout()
        prefix_layout.setSpacing(6)
        prefix_icon = QLabel()
        prefix_icon.setPixmap(qta.icon('fa6s.text-width', color='#888').pixmap(16, 16))
        prefix_layout.addWidget(prefix_icon)
        prefix_label = QLabel("Prefix:")
        prefix_label.setMinimumWidth(120)
        prefix_layout.addWidget(prefix_label)
        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("e.g., output_")
        self.prefix_input.setText(self.config.get('output_prefix', ''))
        self.prefix_input.textChanged.connect(self.on_output_config_changed)
        prefix_layout.addWidget(self.prefix_input, 1)
        output_layout.addLayout(prefix_layout)
        
        suffix_layout = QHBoxLayout()
        suffix_layout.setSpacing(6)
        suffix_icon = QLabel()
        suffix_icon.setPixmap(qta.icon('fa6s.text-width', color='#888').pixmap(16, 16))
        suffix_layout.addWidget(suffix_icon)
        suffix_label = QLabel("Suffix:")
        suffix_label.setMinimumWidth(120)
        suffix_layout.addWidget(suffix_label)
        self.suffix_input = QLineEdit()
        self.suffix_input.setPlaceholderText("e.g., _final")
        self.suffix_input.setText(self.config.get('output_suffix', ''))
        self.suffix_input.textChanged.connect(self.on_output_config_changed)
        suffix_layout.addWidget(self.suffix_input, 1)
        output_layout.addLayout(suffix_layout)
        
        watch_layout = QHBoxLayout()
        watch_layout.setSpacing(6)
        watch_icon = QLabel()
        watch_icon.setPixmap(qta.icon('fa6s.eye', color='#888').pixmap(16, 16))
        watch_layout.addWidget(watch_icon)
        self.enable_file_watch_check = QCheckBox("Enable File Watcher")
        self.enable_file_watch_check.setChecked(self.config.get('enable_file_watcher', True))
        self.enable_file_watch_check.toggled.connect(self.on_output_config_changed)
        watch_layout.addWidget(self.enable_file_watch_check)
        watch_layout.addStretch()
        output_layout.addLayout(watch_layout)
        
        timeout_layout = QHBoxLayout()
        timeout_layout.setSpacing(6)
        timeout_icon = QLabel()
        timeout_icon.setPixmap(qta.icon('fa6s.clock', color='#888').pixmap(16, 16))
        timeout_layout.addWidget(timeout_icon)
        timeout_label = QLabel("Watch Timeout (s):")
        timeout_label.setMinimumWidth(120)
        timeout_layout.addWidget(timeout_label)
        self.watch_timeout_spin = QSpinBox()
        self.watch_timeout_spin.setMinimum(5)
        self.watch_timeout_spin.setMaximum(300)
        self.watch_timeout_spin.setValue(self.config.get('watch_timeout', 30))
        self.watch_timeout_spin.valueChanged.connect(self.on_output_config_changed)
        timeout_layout.addWidget(self.watch_timeout_spin)
        timeout_layout.addStretch()
        output_layout.addLayout(timeout_layout)
        
        output_layout.addStretch()
        
        save_layout = QHBoxLayout()
        save_layout.addStretch()
        self.save_output_button = QPushButton(qta.icon('fa6s.floppy-disk'), " Save Output Settings")
        self.save_output_button.clicked.connect(self.on_save_output_settings)
        self.save_output_button.setEnabled(False)
        save_layout.addWidget(self.save_output_button)
        output_layout.addLayout(save_layout)
        
        output_tab.setLayout(output_layout)
        return output_tab
    
    def on_output_config_changed(self):
        self.save_output_button.setEnabled(True)
    
    def on_save_output_settings(self):
        self.config.set('output_prefix', self.prefix_input.text().strip())
        self.config.set('output_suffix', self.suffix_input.text().strip())
        self.config.set('enable_file_watcher', self.enable_file_watch_check.isChecked())
        self.config.set('watch_timeout', self.watch_timeout_spin.value())
        
        if self.config.save():
            QMessageBox.information(self, "Success", "Output settings saved successfully")
            self.save_output_button.setEnabled(False)
        else:
            QMessageBox.critical(self, "Error", "Failed to save output settings")
    
    def load_platforms(self):
        self.platform_list.clear()
        try:
            platforms = self.db.get_all_platforms()
            for platform in platforms:
                item = QListWidgetItem(platform['name'])
                item.setData(Qt.UserRole, platform)
                self.platform_list.addItem(item)
        except Exception as e:
            print(f'Failed to load platforms: {e}')

    
    def on_platform_selected(self, current, previous):
        if current:
            platform_data = current.data(Qt.UserRole)
            self.current_platform = platform_data
            self.name_input.setCurrentText(platform_data.get('name', ''))
            self.exec_path_input.setText(platform_data.get('exec_path', ''))
            self.note_input.setText(platform_data.get('note', ''))
            self.remove_button.setEnabled(True)
            self.save_button.setEnabled(False)
        else:
            self.current_platform = None
            # don't clear the combo items; just clear selection
            self.name_input.setCurrentIndex(-1)
            self.exec_path_input.clear()
            self.note_input.clear()
            self.remove_button.setEnabled(False)
            self.save_button.setEnabled(False)
    
    def on_field_changed(self):
        name = self.name_input.currentText().strip()
        # enable save if name is present (for add or edit)
        self.save_button.setEnabled(bool(name))
    
    def on_browse_exec_path(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Executable",
            "",
            "Executable Files (*.exe);;All Files (*)"
        )
        
        if file_path:
            self.exec_path_input.setText(file_path)
    
    def on_add_platform(self):
        name = self.name_input.currentText().strip()
        exec_path = self.exec_path_input.text().strip()
        note = self.note_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Validation Error", "Platform name is required")
            return
        
        try:
            new_id = self.db.add_platform(name, exec_path, note)
            self.platforms_changed.emit()
            self.load_platforms()
            
            for i in range(self.platform_list.count()):
                item = self.platform_list.item(i)
                data = item.data(Qt.UserRole)
                if data and data.get('id') == new_id:
                    self.platform_list.setCurrentRow(i)
                    break
            
            self.name_input.setCurrentIndex(-1)
            self.exec_path_input.clear()
            self.note_input.clear()
            self.save_button.setEnabled(False)
        except Exception as e:
            print(f'Failed to add platform: {e}')
    
    def on_save_platform(self):
        if not self.current_platform:
            QMessageBox.warning(self, "No Selection", "Please select a platform to edit or use Add button to create new one")
            return
        
        name = self.name_input.currentText().strip()
        exec_path = self.exec_path_input.text().strip()
        note = self.note_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Validation Error", "Platform name is required")
            return
        
        # Save platform_id before reload clears current_platform
        platform_id = self.current_platform['id']
        
        try:
            self.db.update_platform(platform_id, name, exec_path, note)
            self.platforms_changed.emit()
            self.load_platforms()
            
            # Reselect the saved platform using saved id
            for i in range(self.platform_list.count()):
                item = self.platform_list.item(i)
                data = item.data(Qt.UserRole)
                if data and data.get('id') == platform_id:
                    self.platform_list.setCurrentRow(i)
                    break
            
            self.save_button.setEnabled(False)
            self.accept()
        except Exception as e:
            print(f'Failed to save platform: {e}')

    
    def on_remove_platform(self):
        if not self.current_platform:
            return
        
        platform_id = self.current_platform['id']
        platform_name = self.current_platform['name']
        
        try:
            presets = self.db.get_presets_by_platform(platform_id)
            action_sets = self.db.get_action_sets_by_platform(platform_id)
            
            total_steps = 0
            total_actions = 0
            
            for preset in presets:
                steps = self.db.get_preset_steps(preset['id'])
                total_steps += len(steps)
            
            for action_set in action_sets:
                actions = self.db.get_actions_by_action_set(action_set['id'])
                total_actions += len(actions)
            
            confirm_dialog = QDialog(self)
            confirm_dialog.setWindowTitle("Confirm Platform Deletion")
            confirm_dialog.setModal(True)
            confirm_dialog.resize(500, 300)
            
            dialog_layout = QVBoxLayout()
            
            warning_label = QLabel(
                f"WARNING: You are about to delete platform '{platform_name}'.\n"
                f"The following records will be PERMANENTLY DELETED:\n"
                f"This action CANNOT be undone."
            )
            warning_label.setStyleSheet("color: #e74c3c; font-weight: bold; padding: 10px;")
            warning_label.setWordWrap(True)
            dialog_layout.addWidget(warning_label)
            
            table = QTableWidget()
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels(["Record Type", "Count"])
            table.setRowCount(4)
            table.setEditTriggers(QTableWidget.NoEditTriggers)
            table.setSelectionMode(QTableWidget.NoSelection)
            
            items_data = [
                ("Presets", len(presets)),
                ("Steps (in all Presets)", total_steps),
                ("Action Sets", len(action_sets)),
                ("Actions (in all Action Sets)", total_actions)
            ]
            
            for row, (record_type, count) in enumerate(items_data):
                type_item = QTableWidgetItem(record_type)
                count_item = QTableWidgetItem(str(count))
                count_item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row, 0, type_item)
                table.setItem(row, 1, count_item)
            
            table.resizeColumnsToContents()
            table.horizontalHeader().setStretchLastSection(True)
            dialog_layout.addWidget(table)
            
            button_box = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.No)
            yes_btn = button_box.button(QDialogButtonBox.Yes)
            no_btn = button_box.button(QDialogButtonBox.No)
            yes_btn.setText("Delete All")
            yes_btn.setIcon(qta.icon('fa6s.trash'))
            no_btn.setText("Cancel")
            no_btn.setIcon(qta.icon('fa6s.xmark'))
            button_box.accepted.connect(confirm_dialog.accept)
            button_box.rejected.connect(confirm_dialog.reject)
            dialog_layout.addWidget(button_box)
            
            confirm_dialog.setLayout(dialog_layout)
            
            if confirm_dialog.exec() == QDialog.Accepted:
                try:
                    self.db.delete_platform(platform_id)
                    self.platforms_changed.emit()
                    self.load_platforms()
                    QMessageBox.information(self, 'Success', f'Platform "{platform_name}" and all related records have been deleted.')
                except Exception as e:
                    QMessageBox.critical(self, 'Database Error', f'Failed to remove platform: {e}')
        
        except Exception as e:
            QMessageBox.critical(self, 'Database Error', f'Failed to retrieve platform data: {e}')
