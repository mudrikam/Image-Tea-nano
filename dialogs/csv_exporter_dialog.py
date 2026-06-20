from PySide6.QtWidgets import (QDialog, QVBoxLayout, QCheckBox, QLabel, QGridLayout, QWidget, QPushButton, 
                               QHBoxLayout, QLineEdit, QFileDialog, QProgressDialog, QApplication, QSizePolicy, 
                               QScrollArea, QFrame, QGroupBox, QTabWidget, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QComboBox, QSpinBox, QMessageBox, QInputDialog)
from PySide6.QtCore import Qt, QFileSystemWatcher
import json
import os
import sys
import datetime
import csv
import re
from config import BASE_PATH
from helpers.csv_exporter import export_csv_for_platforms, get_next_index, SHARED_FORMATS
import qtawesome as qta
from ui.theme_system import theme

class CSVExporterDialog(QDialog):
    CONFIG_PATH = os.path.join(BASE_PATH, "configs", "csv_config.json")
    PRESETS_PATH = os.path.join(BASE_PATH, "configs", "csv_exporter_presets.json")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Metadata to CSV")
        self.setFixedWidth(680)
        self.setMinimumHeight(400)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)
        self.setLayout(main_layout)

        self.config = self.load_config()
        
        # Track current preset name for filename generation
        self.current_preset_name = "Custom"

        self.fs_watcher = QFileSystemWatcher()
        try:
            if os.path.exists(self.CONFIG_PATH):
                self.fs_watcher.addPath(self.CONFIG_PATH)
            self.fs_watcher.fileChanged.connect(self.on_config_file_changed)
        except Exception as e:
            print(f"[CSVExporterDialog] Error setting up QFileSystemWatcher: {e}")

        self.platforms = [
            "Magnific", "Adobe Stock", "Shutterstock", "iStock",
            "123RF", "Vecteezy", "Pond5", "Depositphotos", "Canva", "MiriCanvas"
        ]
        self.platform_colors = {
            "Magnific": "#1C7AF5", "Adobe Stock": "#CC1818",
            "Shutterstock": "#D12222", "iStock": "#2178C0",
            "123RF": "#FFB20D", "Vecteezy": "#DB621C",
            "Pond5": "#0EA4D6", "Depositphotos": "#19B9CE",
            "Canva": "#007CCF", "MiriCanvas": "#00B2C6",
        }

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs, 1)

        self.default_tab = QWidget()
        default_layout = QVBoxLayout(self.default_tab)
        default_layout.setContentsMargins(8, 8, 8, 8)
        default_layout.setSpacing(8)
        self.tabs.addTab(self.default_tab, qta.icon('fa6s.list-check'), "Default")

        self.custom_tab = QWidget()
        self.custom_layout = QVBoxLayout(self.custom_tab)
        self.custom_layout.setContentsMargins(8, 8, 8, 8)
        self.custom_layout.setSpacing(8)
        self.tabs.addTab(self.custom_tab, qta.icon('fa6s.table-columns'), "Custom Format")
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # --- Default tab: left checkboxes, right csv list ---
        split_layout = QHBoxLayout()
        split_layout.setSpacing(8)
        split_layout.setStretch(0, 0)
        split_layout.setStretch(1, 1)
        default_layout.addLayout(split_layout, 1)

        # LEFT: checkboxes in QGroupBox
        left_group = QGroupBox("Platforms")
        left_v = QVBoxLayout(left_group)
        left_v.setContentsMargins(8, 8, 8, 8)
        left_v.setSpacing(6)

        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(4)
        self.check_all_btn = QPushButton(qta.icon('fa6s.check'), " Check All")
        self.check_all_btn.setToolTip("Check all platforms")
        self.check_all_btn.clicked.connect(self.check_all)
        ctrl_layout.addWidget(self.check_all_btn)
        self.uncheck_all_btn = QPushButton(qta.icon('fa6s.xmark'), " Uncheck All")
        self.uncheck_all_btn.setToolTip("Uncheck all platforms")
        self.uncheck_all_btn.clicked.connect(self.uncheck_all)
        ctrl_layout.addWidget(self.uncheck_all_btn)
        left_v.addLayout(ctrl_layout)

        cb_scroll = QScrollArea()
        cb_scroll.setWidgetResizable(True)
        cb_scroll.setFrameShape(QFrame.NoFrame)
        cb_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        cb_scroll.setStyleSheet("background-color: transparent;")
        cb_inner = QWidget()
        cb_inner_layout = QVBoxLayout(cb_inner)
        cb_inner_layout.setContentsMargins(4, 4, 4, 4)
        cb_inner_layout.setSpacing(6)
        cb_scroll.setWidget(cb_inner)
        left_v.addWidget(cb_scroll)

        self.platform_checkboxes = []
        self.checkbox_map = {}
        for platform in self.platforms:
            color = self.platform_colors.get(platform, theme.get_color('foreground'))
            checkbox = QCheckBox(platform)
            checkbox.setStyleSheet(f"color: {color};")
            checkbox.setChecked(self.config.get(platform, False))
            checkbox.toggled.connect(lambda checked, p=platform: self.on_platform_toggled(p, checked))
            cb_inner_layout.addWidget(checkbox)
            self.platform_checkboxes.append(checkbox)
            self.checkbox_map[platform] = checkbox
        cb_inner_layout.addStretch()

        left_group.setFixedWidth(210)
        split_layout.addWidget(left_group)

        # RIGHT: csv filename list in QGroupBox
        right_group = QGroupBox("Output Filenames")
        right_v = QVBoxLayout(right_group)
        right_v.setContentsMargins(8, 8, 8, 8)
        right_v.setSpacing(4)

        csv_scroll = QScrollArea()
        csv_scroll.setWidgetResizable(True)
        csv_scroll.setFrameShape(QFrame.NoFrame)
        csv_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        csv_scroll.setStyleSheet("background-color: transparent;")
        self.rename_container = QWidget()
        self.rename_layout = QVBoxLayout(self.rename_container)
        self.rename_layout.setContentsMargins(4, 4, 4, 4)
        self.rename_layout.setSpacing(6)
        csv_scroll.setWidget(self.rename_container)
        right_v.addWidget(csv_scroll)
        split_layout.addWidget(right_group, 1)

        self.rename_rows = {}
        for platform in self.platforms:
            color = self.platform_colors.get(platform, theme.get_color('foreground'))
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)

            icon_lbl = QLabel()
            icon_lbl.setPixmap(qta.icon('fa6s.file-csv', color=color).pixmap(16, 16))
            icon_lbl.setFixedWidth(20)
            row_layout.addWidget(icon_lbl)

            entry = QLineEdit()
            entry.setText(self.default_base_name(platform))
            entry.setToolTip("Edit base filename (no index/extension)")
            entry.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            entry.textChanged.connect(lambda text, p=platform: (self.update_suffixes(), self.validate_output_and_buttons()))
            row_layout.addWidget(entry, 1)

            suffix_label = QLabel("_001.CSV")
            suffix_label.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 10px;")
            suffix_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            row_layout.addWidget(suffix_label)

            export_btn = QPushButton(qta.icon('fa6s.file-export', color=theme.get_color('primary')), "")
            export_btn.setToolTip(f"Export {platform} CSV only")
            export_btn.setFixedWidth(28)
            export_btn.setFixedHeight(24)
            export_btn.clicked.connect(lambda _, p=platform: self.export_single_platform(p))
            row_layout.addWidget(export_btn)

            self.rename_layout.addWidget(row_widget)
            self.rename_rows[platform] = (row_widget, entry, suffix_label, export_btn)
            row_widget.setVisible(bool(self.config.get(platform, False)))
        self.rename_layout.addStretch()

        self.build_custom_format_tab()

        # output path row
        output_layout = QHBoxLayout()
        self.output_lineedit = QLineEdit()
        self.output_lineedit.setPlaceholderText("Select output folder...")
        output_layout.addWidget(self.output_lineedit)

        self.paste_output_btn = QPushButton(qta.icon('fa6s.paste'), "")
        self.paste_output_btn.setToolTip("Paste path from clipboard")
        self.paste_output_btn.setFixedWidth(32)
        self.paste_output_btn.clicked.connect(self.paste_output_path)
        output_layout.addWidget(self.paste_output_btn)

        self.select_output_btn = QPushButton(qta.icon('fa6s.folder-open'), "Select Output")
        self.select_output_btn.setToolTip("Select output folder")
        self.select_output_btn.clicked.connect(self.select_output_path)
        output_layout.addWidget(self.select_output_btn)
        main_layout.addLayout(output_layout)

        bottom_row = QHBoxLayout()
        self.open_folder_checkbox = QCheckBox("Open folder on export")
        self.open_folder_checkbox.setChecked(bool(self.config.get("open_folder_on_export", True)))
        self.open_folder_checkbox.toggled.connect(self.save_config_realtime)
        bottom_row.addWidget(self.open_folder_checkbox)
        bottom_row.addStretch()
        self.ok_btn = QPushButton(qta.icon('fa6s.file-csv', color=theme.get_color('success')), "Export All CSV")
        self.ok_btn.setToolTip("Export metadata to CSV")
        self.ok_btn.clicked.connect(self.export_current_tab)
        self.ok_btn.setFixedHeight(32)
        bottom_row.addWidget(self.ok_btn)
        main_layout.addLayout(bottom_row)

        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet(f'color: {theme.get_color("error")}; font-size: 11px')
        self.validation_label.setVisible(False)
        main_layout.addWidget(self.validation_label)

        self.output_lineedit.textChanged.connect(self.on_output_path_changed)
        self.validate_output_and_buttons()
        
        # Load default preset after all UI elements are created
        self.load_default_preset()

    def build_custom_format_tab(self):
        """Build the custom format tab with field mapping table"""
        info_label = QLabel("Define custom CSV format by mapping database fields to output columns:")
        info_label.setWordWrap(True)
        self.custom_layout.addWidget(info_label)

        # Control buttons
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(4)
        
        self.add_field_btn = QPushButton(qta.icon('fa6s.plus'), " Add Field")
        self.add_field_btn.setToolTip("Add a new field mapping")
        self.add_field_btn.clicked.connect(self.add_custom_field_row)
        ctrl_row.addWidget(self.add_field_btn)
        
        self.remove_field_btn = QPushButton(qta.icon('fa6s.minus'), " Remove Selected")
        self.remove_field_btn.setToolTip("Remove selected field mapping")
        self.remove_field_btn.clicked.connect(self.remove_custom_field_row)
        ctrl_row.addWidget(self.remove_field_btn)
        
        self.load_preset_btn = QPushButton(qta.icon('fa6s.download'), " Load Preset")
        self.load_preset_btn.setToolTip("Load format from platforms or saved presets")
        self.load_preset_btn.clicked.connect(self.load_preset_unified)
        ctrl_row.addWidget(self.load_preset_btn)
        
        self.save_preset_btn = QPushButton(qta.icon('fa6s.floppy-disk'), " Save Preset")
        self.save_preset_btn.setToolTip("Save current custom format to csv_exporter_presets.json")
        self.save_preset_btn.clicked.connect(self.save_custom_preset)
        ctrl_row.addWidget(self.save_preset_btn)
        
        self.delete_preset_btn = QPushButton(qta.icon('fa6s.trash-can'), " Delete Preset")
        self.delete_preset_btn.setToolTip("Delete a saved user preset")
        self.delete_preset_btn.clicked.connect(self.delete_custom_preset)
        ctrl_row.addWidget(self.delete_preset_btn)
        
        self.clear_all_btn = QPushButton(qta.icon('fa6s.broom'), " Clear All")
        self.clear_all_btn.setToolTip("Clear all field mappings")
        self.clear_all_btn.clicked.connect(self.clear_custom_fields)
        ctrl_row.addWidget(self.clear_all_btn)
        
        ctrl_row.addStretch()
        self.custom_layout.addLayout(ctrl_row)

        # Field mapping table
        self.custom_table = QTableWidget()
        self.custom_table.setColumnCount(6)
        self.custom_table.setHorizontalHeaderLabels(["Column Name", "Source Type", "Source Field/Custom Text", "Transform", "Quote", "Preview"])
        self.custom_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.custom_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.custom_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.custom_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.custom_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.custom_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.custom_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.custom_table.setAlternatingRowColors(True)
        self.custom_layout.addWidget(self.custom_table, 1)

        # CSV format settings
        format_group = QGroupBox("CSV Format Settings")
        format_layout = QGridLayout(format_group)
        format_layout.setContentsMargins(8, 8, 8, 8)
        format_layout.setSpacing(6)

        format_layout.addWidget(QLabel("Delimiter:"), 0, 0)
        self.delimiter_combo = QComboBox()
        self.delimiter_combo.addItems(["Comma (,)", "Semicolon (;)", "Tab", "Pipe (|)"])
        self.delimiter_combo.setCurrentIndex(0)
        format_layout.addWidget(self.delimiter_combo, 0, 1)

        format_layout.addWidget(QLabel("Global Quote:"), 0, 2)
        self.quote_combo = QComboBox()
        self.quote_combo.addItems(["Use Per Field", "All", "None", "Text Only"])
        self.quote_combo.setCurrentIndex(0)
        format_layout.addWidget(self.quote_combo, 0, 3)

        self.quote_header_cb = QCheckBox("Quote Header Row")
        self.quote_header_cb.setChecked(False)
        format_layout.addWidget(self.quote_header_cb, 1, 0, 1, 2)

        format_layout.addWidget(QLabel("Output Filename:"), 1, 2)
        # Generate default filename with date pattern
        today = datetime.datetime.now()
        default_custom_filename = f"Custom_Image_Tea_Metadata_{today.year}_{today.strftime('%B')}_{today.day:02d}"
        
        # Create horizontal layout for filename entry + suffix label
        filename_layout = QHBoxLayout()
        filename_layout.setContentsMargins(0, 0, 0, 0)
        filename_layout.setSpacing(2)
        
        self.custom_filename_edit = QLineEdit(default_custom_filename)
        self.custom_filename_edit.textChanged.connect(self.update_suffixes)
        filename_layout.addWidget(self.custom_filename_edit, 1)
        
        self.custom_suffix_label = QLabel("_001.CSV")
        self.custom_suffix_label.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 10px;")
        self.custom_suffix_label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        filename_layout.addWidget(self.custom_suffix_label)
        
        format_layout.addLayout(filename_layout, 1, 3)

        self.custom_layout.addWidget(format_group)

        # Available source fields must match the actual Image Tea files table/get_all_files() row.
        # files columns: id, filepath, filename, title, description, tags, status, original_filename
        self.available_fields = [
            "EMPTY", "id", "filepath", "filename", "title", "description", "tags", "status", "original_filename"
        ]

        # Transform options
        self.transform_options = [
            "None", "Uppercase", "Lowercase", "Title Case", "Sanitize", "Truncate"
        ]

    def add_custom_field_row(self):
        """Add a new row to the custom field mapping table"""
        row = self.custom_table.rowCount()
        self.custom_table.insertRow(row)

        # Column name
        col_name_item = QTableWidgetItem("Column_" + str(row + 1))
        self.custom_table.setItem(row, 0, col_name_item)

        # Source type dropdown (DB Field or Custom Text)
        source_type_combo = QComboBox()
        source_type_combo.addItems(["DB Field", "Custom Text"])
        source_type_combo.currentTextChanged.connect(lambda _text, r=row: self.on_source_type_changed(r))
        self.custom_table.setCellWidget(row, 1, source_type_combo)

        # Source field dropdown (or text input)
        source_combo = QComboBox()
        source_combo.addItems(self.available_fields)
        source_combo.currentTextChanged.connect(lambda _text, r=row: self.update_preview_row(r))
        self.custom_table.setCellWidget(row, 2, source_combo)

        # Transform dropdown
        transform_combo = QComboBox()
        transform_combo.addItems(self.transform_options)
        transform_combo.currentTextChanged.connect(lambda _text, r=row: self.update_preview_row(r))
        self.custom_table.setCellWidget(row, 3, transform_combo)

        # Per-field quote mode
        quote_combo = QComboBox()
        quote_combo.addItems(["Auto", "Yes", "No"])
        quote_combo.setCurrentIndex(0)
        self.custom_table.setCellWidget(row, 4, quote_combo)

        # Preview
        preview_item = QTableWidgetItem("")
        preview_item.setFlags(preview_item.flags() & ~Qt.ItemIsEditable)
        self.custom_table.setItem(row, 5, preview_item)

        self.update_preview_row(row)
        self.validate_output_and_buttons()
    
    def on_source_type_changed(self, row):
        """Handle source type change between DB Field and Custom Text"""
        source_type_combo = self.custom_table.cellWidget(row, 1)
        if not source_type_combo:
            return
        
        source_type = source_type_combo.currentText()
        
        # Remove existing widget
        old_widget = self.custom_table.cellWidget(row, 2)
        if old_widget:
            self.custom_table.removeCellWidget(row, 2)
        
        if source_type == "DB Field":
            # Create dropdown for database fields
            source_combo = QComboBox()
            source_combo.addItems(self.available_fields)
            source_combo.currentTextChanged.connect(lambda _text, r=row: self.update_preview_row(r))
            self.custom_table.setCellWidget(row, 2, source_combo)
        else:  # Custom Text
            # Create text input for custom text
            source_input = QLineEdit()
            source_input.setPlaceholderText("Enter custom text...")
            source_input.textChanged.connect(lambda _text, r=row: self.update_preview_row(r))
            self.custom_table.setCellWidget(row, 2, source_input)
        
        self.update_preview_row(row)

    def remove_custom_field_row(self):
        """Remove selected row from custom field mapping table"""
        current_row = self.custom_table.currentRow()
        if current_row >= 0:
            self.custom_table.removeRow(current_row)
            self.validate_output_and_buttons()

    def clear_custom_fields(self):
        """Clear all custom field mappings"""
        reply = QMessageBox.question(
            self, "Clear All Fields",
            "Are you sure you want to clear all field mappings?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.custom_table.setRowCount(0)
            self.validate_output_and_buttons()

    def update_preview_row(self, row):
        """Update preview for a specific row based on source type, field/text and transform"""
        try:
            source_type_combo = self.custom_table.cellWidget(row, 1)
            source_widget = self.custom_table.cellWidget(row, 2)
            transform_combo = self.custom_table.cellWidget(row, 3)
            
            if not source_type_combo or not source_widget or not transform_combo:
                return
            
            source_type = source_type_combo.currentText()
            transform = transform_combo.currentText()
            
            # Get value based on source type
            if source_type == "Custom Text":
                # Custom text input
                if isinstance(source_widget, QLineEdit):
                    preview_value = source_widget.text()
                else:
                    preview_value = ""
            else:
                # DB Field
                if isinstance(source_widget, QComboBox):
                    source_field = source_widget.currentText()
                    
                    # Generate sample preview
                    sample_data = {
                        "id": "1",
                        "filepath": "D:/assets/sample_image.jpg",
                        "filename": "sample_image.jpg",
                        "title": "Sample Title",
                        "description": "Sample description text",
                        "tags": "keyword1, keyword2, keyword3",
                        "status": "success",
                        "original_filename": "IMG_0001.jpg"
                    }
                    
                    preview_value = "" if source_field == "EMPTY" else sample_data.get(source_field, f"<{source_field}>")
                else:
                    preview_value = ""
            
            # Apply transform
            if transform == "Uppercase":
                preview_value = str(preview_value).upper()
            elif transform == "Lowercase":
                preview_value = str(preview_value).lower()
            elif transform == "Title Case":
                preview_value = str(preview_value).title()
            elif transform == "Sanitize":
                preview_value = re.sub(r'[^a-zA-Z0-9\s]', '', str(preview_value))
            elif transform == "Truncate":
                preview_value = str(preview_value)[:50] + "..." if len(str(preview_value)) > 50 else str(preview_value)
            
            preview_item = self.custom_table.item(row, 5)
            if preview_item:
                preview_item.setText(str(preview_value))
        except Exception as e:
            print(f"[CSVExporterDialog] Error updating preview for row {row}: {e}")

    def load_default_preset(self):
        """Load the default preset from the presets JSON file"""
        if not os.path.exists(self.PRESETS_PATH):
            # Create default presets file if it doesn't exist
            default_presets = {
                "presets": [
                    {
                        "name": "Default",
                        "delimiter_index": 0,
                        "quote_index": 0,
                        "quote_header": False,
                        "fields": [
                            {"column_name": "Filename", "source_field": "filename", "transform": "None", "quote": "Auto"},
                            {"column_name": "Title", "source_field": "title", "transform": "None", "quote": "Auto"},
                            {"column_name": "Tags", "source_field": "tags", "transform": "None", "quote": "Auto"}
                        ]
                    }
                ]
            }
            try:
                os.makedirs(os.path.dirname(self.PRESETS_PATH), exist_ok=True)
                with open(self.PRESETS_PATH, "w", encoding="utf-8") as f:
                    json.dump(default_presets, f, indent=2)
            except Exception as e:
                print(f"[CSVExporterDialog] Error creating default presets file: {e}")
                return
        
        try:
            with open(self.PRESETS_PATH, "r", encoding="utf-8") as f:
                presets_data = json.load(f)
            
            # Find and load the Default preset
            presets = presets_data.get("presets", [])
            default_preset = None
            for preset in presets:
                if preset.get("name") == "Default":
                    default_preset = preset
                    break
            
            if default_preset:
                self._apply_custom_format_config(default_preset)
            else:
                print("[CSVExporterDialog] No Default preset found in presets file")
        except Exception as e:
            print(f"[CSVExporterDialog] Error loading default preset: {e}")

    def load_preset_format(self):
        """Load format from existing SHARED_FORMATS (Magnific, Adobe Stock, etc.)"""
        platform_names = list(SHARED_FORMATS.keys())
        platform_name, ok = QInputDialog.getItem(
            self, "Load Platform Format",
            "Select a platform format to load:",
            platform_names, 0, False
        )
        if ok and platform_name:
            fmt = SHARED_FORMATS[platform_name]
            
            # Clear existing fields
            self.custom_table.setRowCount(0)
            
            # Set delimiter
            delimiter = fmt.get("delimiter", ",")
            delimiter_map = {",": 0, ";": 1, "\t": 2, "|": 3}
            self.delimiter_combo.setCurrentIndex(delimiter_map.get(delimiter, 0))
            
            # Set quote mode
            quote_fields = fmt.get("quote_fields", "all")
            if quote_fields == "all":
                self.quote_combo.setCurrentIndex(1)  # All
            elif quote_fields == "none":
                self.quote_combo.setCurrentIndex(2)  # None
            else:
                self.quote_combo.setCurrentIndex(0)  # Use Per Field
            
            # Set quote header
            self.quote_header_cb.setChecked(fmt.get("quote_header", False))
            
            # Set filename
            self.custom_filename_edit.setText(platform_name.lower().replace(" ", "_"))
            
            # Add fields
            headers = fmt.get("header", [])
            fields = fmt.get("fields", [])
            quote_field_list = fmt.get("quote_fields", [])
            
            for i, (header, field) in enumerate(zip(headers, fields)):
                # Map platform field names to database field names
                field_mapping = {
                    "keywords": "tags",
                    "description": "description",
                    "title": "title",
                    "filename": "filename",
                    "file name": "filename",
                    "oldfilename": "filename",
                    "originalfilename": "filename",
                    "file_name": "filename"
                }
                
                mapped_field = field_mapping.get(field.lower(), "EMPTY")
                if mapped_field not in self.available_fields:
                    mapped_field = "EMPTY"
                
                # Determine quote mode for this field
                quote_mode = "Auto"
                if isinstance(quote_field_list, list):
                    if any(qf in field.lower() for qf in quote_field_list):
                        quote_mode = "Yes"
                    else:
                        quote_mode = "No"
                
                # Add row
                row = self.custom_table.rowCount()
                self.custom_table.insertRow(row)
                self.custom_table.setItem(row, 0, QTableWidgetItem(header))
                
                source_combo = QComboBox()
                source_combo.addItems(self.available_fields)
                source_combo.setCurrentText(mapped_field)
                source_combo.currentTextChanged.connect(lambda _text, r=row: self.update_preview_row(r))
                self.custom_table.setCellWidget(row, 1, source_combo)
                
                transform_combo = QComboBox()
                transform_combo.addItems(self.transform_options)
                transform_combo.setCurrentText("None")
                transform_combo.currentTextChanged.connect(lambda _text, r=row: self.update_preview_row(r))
                self.custom_table.setCellWidget(row, 2, transform_combo)
                
                quote_combo = QComboBox()
                quote_combo.addItems(["Auto", "Yes", "No"])
                quote_combo.setCurrentText(quote_mode)
                self.custom_table.setCellWidget(row, 3, quote_combo)
                
                preview_item = QTableWidgetItem("")
                preview_item.setFlags(preview_item.flags() & ~Qt.ItemIsEditable)
                self.custom_table.setItem(row, 4, preview_item)
                
                self.update_preview_row(row)

    def load_preset_unified(self):
        """Load preset from SHARED_FORMATS or user saved presets"""
        # Build list of available presets
        preset_items = []
        
        # Add separator and SHARED_FORMATS
        preset_items.append("--- Platform Formats ---")
        for platform_name in SHARED_FORMATS.keys():
            preset_items.append(f"Platform: {platform_name}")
        
        # Add user presets if available
        user_presets = []
        if os.path.exists(self.PRESETS_PATH):
            try:
                with open(self.PRESETS_PATH, "r", encoding="utf-8") as f:
                    presets_data = json.load(f)
                user_presets = presets_data.get("presets", [])
            except Exception as e:
                print(f"[CSVExporterDialog] Error loading user presets: {e}")
        
        if user_presets:
            preset_items.append("--- User Presets ---")
            for preset in user_presets:
                preset_name = preset.get("name", "Unnamed")
                preset_items.append(f"User: {preset_name}")
        
        if len(preset_items) == 1:  # Only separator
            QMessageBox.information(self, "No Presets", "No presets available.")
            return
        
        # Show selection dialog
        selected, ok = QInputDialog.getItem(
            self, "Load Preset",
            "Select a preset to load:",
            preset_items, 0, False
        )
        
        if not ok or not selected:
            return
        
        # Skip separators
        if selected.startswith("---"):
            return
        
        # Load selected preset
        if selected.startswith("Platform: "):
            platform_name = selected.replace("Platform: ", "")
            self._load_from_shared_format(platform_name)
        elif selected.startswith("User: "):
            preset_name = selected.replace("User: ", "")
            self._load_from_user_preset(preset_name, user_presets)
    
    def _load_from_shared_format(self, platform_name):
        """Load format from SHARED_FORMATS"""
        if platform_name not in SHARED_FORMATS:
            return
        
        fmt = SHARED_FORMATS[platform_name]
        
        # Clear existing fields
        self.custom_table.setRowCount(0)
        
        # Set delimiter
        delimiter = fmt.get("delimiter", ",")
        delimiter_map = {",": 0, ";": 1, "\t": 2, "|": 3}
        self.delimiter_combo.setCurrentIndex(delimiter_map.get(delimiter, 0))
        
        # Set quote mode
        quote_fields = fmt.get("quote_fields", "all")
        if quote_fields == "all":
            self.quote_combo.setCurrentIndex(1)  # All
        elif quote_fields == "none":
            self.quote_combo.setCurrentIndex(2)  # None
        else:
            self.quote_combo.setCurrentIndex(0)  # Use Per Field
        
        # Set quote header
        self.quote_header_cb.setChecked(fmt.get("quote_header", False))
        
        # Set filename using default_base_name format
        self.current_preset_name = platform_name
        self.custom_filename_edit.setText(self.default_base_name(platform_name))
        
        # Add fields
        headers = fmt.get("header", [])
        fields = fmt.get("fields", [])
        quote_field_list = fmt.get("quote_fields", [])
        
        for i, (header, field) in enumerate(zip(headers, fields)):
            # Map platform field names to database field names
            field_mapping = {
                "keywords": "tags",
                "description": "description",
                "title": "title",
                "filename": "filename",
                "file name": "filename",
                "oldfilename": "filename",
                "originalfilename": "filename",
                "file_name": "filename"
            }
            
            mapped_field = field_mapping.get(field.lower(), "EMPTY")
            if mapped_field not in self.available_fields:
                mapped_field = "EMPTY"
            
            # Determine quote mode for this field
            quote_mode = "Auto"
            if isinstance(quote_field_list, list):
                if any(qf in field.lower() for qf in quote_field_list):
                    quote_mode = "Yes"
                else:
                    quote_mode = "No"
            
            # Add row
            row = self.custom_table.rowCount()
            self.custom_table.insertRow(row)
            self.custom_table.setItem(row, 0, QTableWidgetItem(header))
            
            # Source type
            source_type_combo = QComboBox()
            source_type_combo.addItems(["DB Field", "Custom Text"])
            source_type_combo.setCurrentText("DB Field")
            source_type_combo.currentTextChanged.connect(lambda _text, r=row: self.on_source_type_changed(r))
            self.custom_table.setCellWidget(row, 1, source_type_combo)
            
            # Source field
            source_combo = QComboBox()
            source_combo.addItems(self.available_fields)
            source_combo.setCurrentText(mapped_field)
            source_combo.currentTextChanged.connect(lambda _text, r=row: self.update_preview_row(r))
            self.custom_table.setCellWidget(row, 2, source_combo)
            
            transform_combo = QComboBox()
            transform_combo.addItems(self.transform_options)
            transform_combo.setCurrentText("None")
            transform_combo.currentTextChanged.connect(lambda _text, r=row: self.update_preview_row(r))
            self.custom_table.setCellWidget(row, 3, transform_combo)
            
            quote_combo = QComboBox()
            quote_combo.addItems(["Auto", "Yes", "No"])
            quote_combo.setCurrentText(quote_mode)
            self.custom_table.setCellWidget(row, 4, quote_combo)
            
            preview_item = QTableWidgetItem("")
            preview_item.setFlags(preview_item.flags() & ~Qt.ItemIsEditable)
            self.custom_table.setItem(row, 5, preview_item)
            
            self.update_preview_row(row)
    
    def _load_from_user_preset(self, preset_name, user_presets):
        """Load format from user preset"""
        selected_preset = None
        for preset in user_presets:
            if preset.get("name") == preset_name:
                selected_preset = preset
                break
        
        if selected_preset:
            self._apply_custom_format_config(selected_preset)

    def _collect_custom_format_config(self):
        fields = []
        for row in range(self.custom_table.rowCount()):
            col_name_item = self.custom_table.item(row, 0)
            source_type_combo = self.custom_table.cellWidget(row, 1)
            source_widget = self.custom_table.cellWidget(row, 2)
            transform_combo = self.custom_table.cellWidget(row, 3)
            quote_combo = self.custom_table.cellWidget(row, 4)
            
            if col_name_item and source_type_combo and source_widget and transform_combo and quote_combo:
                source_type = source_type_combo.currentText()
                
                # Get source value based on type
                if source_type == "Custom Text" and isinstance(source_widget, QLineEdit):
                    source_value = source_widget.text()
                elif source_type == "DB Field" and isinstance(source_widget, QComboBox):
                    source_value = source_widget.currentText()
                else:
                    source_value = ""
                
                fields.append({
                    "column_name": col_name_item.text(),
                    "source_type": source_type,
                    "source_value": source_value,
                    "transform": transform_combo.currentText(),
                    "quote": quote_combo.currentText()
                })
        return {
            "delimiter_index": self.delimiter_combo.currentIndex(),
            "quote_index": self.quote_combo.currentIndex(),
            "quote_header": self.quote_header_cb.isChecked(),
            "fields": fields
        }

    def _apply_custom_format_config(self, config):
        # Store preset name for filename generation
        preset_name = config.get("name", "Custom")
        self.current_preset_name = preset_name
        
        self.custom_table.setRowCount(0)
        self.delimiter_combo.setCurrentIndex(int(config.get("delimiter_index", 0)))
        self.quote_combo.setCurrentIndex(int(config.get("quote_index", 0)))
        self.quote_header_cb.setChecked(bool(config.get("quote_header", False)))
        
        # Generate filename based on preset name (always use preset name, ignore saved filename)
        filename = self.default_base_name(preset_name)
        self.custom_filename_edit.setText(filename)
        
        for field_data in config.get("fields", []):
            row = self.custom_table.rowCount()
            self.custom_table.insertRow(row)
            self.custom_table.setItem(row, 0, QTableWidgetItem(field_data.get("column_name", "")))

            # Source type (backward compatibility: if no source_type, assume DB Field)
            source_type = field_data.get("source_type", "DB Field")
            source_type_combo = QComboBox()
            source_type_combo.addItems(["DB Field", "Custom Text"])
            source_type_combo.setCurrentText(source_type)
            source_type_combo.currentTextChanged.connect(lambda _text, r=row: self.on_source_type_changed(r))
            self.custom_table.setCellWidget(row, 1, source_type_combo)

            # Source value (field or custom text)
            source_value = field_data.get("source_value", field_data.get("source_field", "EMPTY"))
            if source_type == "Custom Text":
                source_input = QLineEdit()
                source_input.setText(source_value)
                source_input.setPlaceholderText("Enter custom text...")
                source_input.textChanged.connect(lambda _text, r=row: self.update_preview_row(r))
                self.custom_table.setCellWidget(row, 2, source_input)
            else:  # DB Field
                source_combo = QComboBox()
                source_combo.addItems(self.available_fields)
                # Backward compatibility mapping
                if source_value == "keywords":
                    source_value = "tags"
                if source_value not in self.available_fields:
                    source_value = "EMPTY"
                source_combo.setCurrentText(source_value)
                source_combo.currentTextChanged.connect(lambda _text, r=row: self.update_preview_row(r))
                self.custom_table.setCellWidget(row, 2, source_combo)

            transform_combo = QComboBox()
            transform_combo.addItems(self.transform_options)
            transform_combo.setCurrentText(field_data.get("transform", "None"))
            transform_combo.currentTextChanged.connect(lambda _text, r=row: self.update_preview_row(r))
            self.custom_table.setCellWidget(row, 3, transform_combo)

            quote_combo = QComboBox()
            quote_combo.addItems(["Auto", "Yes", "No"])
            quote_combo.setCurrentText(field_data.get("quote", "Auto"))
            self.custom_table.setCellWidget(row, 4, quote_combo)

            preview_item = QTableWidgetItem("")
            preview_item.setFlags(preview_item.flags() & ~Qt.ItemIsEditable)
            self.custom_table.setItem(row, 5, preview_item)
            self.update_preview_row(row)
        self.validate_output_and_buttons()

    def save_custom_preset(self):
        """Save current custom format as a preset to the shared JSON file"""
        preset_name, ok = QInputDialog.getText(self, "Save Custom Preset", "Preset name:", text="My Preset")
        if not ok or not preset_name.strip():
            return
        
        # Load existing presets
        presets_data = {"presets": []}
        if os.path.exists(self.PRESETS_PATH):
            try:
                with open(self.PRESETS_PATH, "r", encoding="utf-8") as f:
                    presets_data = json.load(f)
            except Exception as e:
                print(f"[CSVExporterDialog] Error loading presets file: {e}")
        
        # Check if preset name is protected
        preset_name = preset_name.strip()
        if preset_name == "Default":
            QMessageBox.warning(self, "Protected Preset", "The Default preset is protected and cannot be overwritten.")
            return
        
        # Update current preset name and filename
        self.current_preset_name = preset_name
        self.custom_filename_edit.setText(self.default_base_name(preset_name))
        
        # Check if preset name already exists
        existing_names = [p.get("name", "") for p in presets_data.get("presets", [])]
        if preset_name in existing_names:
            reply = QMessageBox.question(
                self, "Preset Exists",
                f"Preset '{preset_name}' already exists. Overwrite?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            # Remove old preset
            presets_data["presets"] = [p for p in presets_data["presets"] if p.get("name") != preset_name]
        
        # Add new preset
        config = self._collect_custom_format_config()
        config["name"] = preset_name
        presets_data["presets"].append(config)
        
        # Save to file
        try:
            with open(self.PRESETS_PATH, "w", encoding="utf-8") as f:
                json.dump(presets_data, f, indent=2)
            QMessageBox.information(self, "Preset Saved", f"Preset '{preset_name}' saved!")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save preset:\n{e}")
            print(f"[CSVExporterDialog] Error saving preset: {e}")

    def delete_custom_preset(self):
        """Delete a user preset from the JSON file"""
        if not os.path.exists(self.PRESETS_PATH):
            QMessageBox.warning(self, "No Presets", "No presets file found.")
            return
        
        try:
            with open(self.PRESETS_PATH, "r", encoding="utf-8") as f:
                presets_data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Could not load presets file:\n{e}")
            return
        
        presets = presets_data.get("presets", [])
        user_presets = [p for p in presets if p.get("name") != "Default"]
        if not user_presets:
            QMessageBox.information(self, "No Presets", "No user presets available to delete.")
            return
        
        # Show dialog to select preset to delete
        preset_names = [p.get("name", f"Preset {i+1}") for i, p in enumerate(user_presets)]
        preset_name, ok = QInputDialog.getItem(
            self, "Delete Preset",
            "Select a preset to delete:",
            preset_names, 0, False
        )
        
        if not ok or not preset_name:
            return
        
        # Confirm deletion
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete preset '{preset_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
        
        # Remove preset
        presets_data["presets"] = [p for p in presets if p.get("name") != preset_name]
        
        # Save to file
        try:
            with open(self.PRESETS_PATH, "w", encoding="utf-8") as f:
                json.dump(presets_data, f, indent=2)
            QMessageBox.information(self, "Preset Deleted", f"Preset '{preset_name}' deleted!")
        except Exception as e:
            QMessageBox.critical(self, "Delete Error", f"Could not delete preset:\n{e}")
            print(f"[CSVExporterDialog] Error deleting preset: {e}")


    def export_custom_csv(self):
        """Export CSV using custom format"""
        output_path = self._sanitize_path_text(self.output_lineedit.text())
        if not output_path or not os.path.isdir(output_path):
            QMessageBox.warning(self, "Invalid Output Path", "Please select a valid output folder first.")
            return
        
        if self.custom_table.rowCount() == 0:
            QMessageBox.warning(self, "No Fields Defined", "Please add at least one field mapping.")
            return
        
        # Get delimiter
        delim_map = [',', ';', '\t', '|']
        delimiter = delim_map[self.delimiter_combo.currentIndex()]
        
        # Get quote settings
        quote_mode = self.quote_combo.currentIndex()
        quote_header = self.quote_header_cb.isChecked()
        
        # Build header and field mappings
        headers = []
        field_mappings = []
        source_types = []
        transforms = []
        quote_modes = []
        
        for row in range(self.custom_table.rowCount()):
            col_name_item = self.custom_table.item(row, 0)
            source_type_combo = self.custom_table.cellWidget(row, 1)
            source_widget = self.custom_table.cellWidget(row, 2)
            transform_combo = self.custom_table.cellWidget(row, 3)
            quote_combo = self.custom_table.cellWidget(row, 4)
            
            if col_name_item and source_type_combo and source_widget and transform_combo and quote_combo:
                headers.append(col_name_item.text())
                source_type = source_type_combo.currentText()
                source_types.append(source_type)
                
                # Get source value based on type
                if source_type == "Custom Text" and isinstance(source_widget, QLineEdit):
                    field_mappings.append(source_widget.text())
                elif source_type == "DB Field" and isinstance(source_widget, QComboBox):
                    field_mappings.append(source_widget.currentText())
                else:
                    field_mappings.append("")
                
                transforms.append(transform_combo.currentText())
                quote_modes.append(quote_combo.currentText())
        
        # Get files from database
        from database.db_operation import ImageTeaDB
        db = ImageTeaDB()
        files = db.get_all_files()
        
        if not files:
            QMessageBox.information(self, "No Data", "No files found in database to export.")
            return
        
        # Progress dialog
        progress = QProgressDialog(f"Exporting custom CSV...", "Cancel", 0, len(files), self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        
        # Build rows
        rows = []
        for file_data in files:
            if progress.wasCanceled():
                break
            
            row = []
            for field, source_type, transform in zip(field_mappings, source_types, transforms):
                if source_type == "Custom Text":
                    # Use custom text as-is
                    value = field
                else:
                    # Extract from database field
                    value = self._extract_field_value(file_data, field)
                value = self._apply_transform(value, transform)
                row.append(value)
            
            rows.append(row)
            progress.setValue(progress.value() + 1)
        
        # Generate filename using current preset name
        base_name = self.custom_filename_edit.text() or self.default_base_name(self.current_preset_name)
        from helpers.csv_exporter import generate_export_filename
        csv_filename = generate_export_filename(base_name, output_path)
        csv_path = os.path.join(output_path, csv_filename)
        
        # Write CSV
        try:
            self._write_custom_csv(csv_path, headers, rows, delimiter, quote_mode, quote_header, quote_modes)
            progress.setValue(len(files))
            self.update_suffixes()
            QMessageBox.information(self, "Export Complete", f"Custom CSV exported successfully to:\n{csv_path}")
            
            if self.open_folder_checkbox.isChecked():
                self.open_folder_windows(output_path)
                
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Error exporting custom CSV:\n{str(e)}")
            print(f"[CSVExporterDialog] Error exporting custom CSV: {e}")

    def _extract_field_value(self, file_data, field):
        """Extract field value from the actual Image Tea files table row."""
        file_dict = {
            "id": file_data[0] if len(file_data) > 0 else "",
            "filepath": file_data[1] if len(file_data) > 1 else "",
            "filename": file_data[2] if len(file_data) > 2 else "",
            "title": file_data[3] if len(file_data) > 3 and file_data[3] is not None else "",
            "description": file_data[4] if len(file_data) > 4 and file_data[4] is not None else "",
            "tags": file_data[5] if len(file_data) > 5 and file_data[5] is not None else "",
            "status": file_data[6] if len(file_data) > 6 and file_data[6] is not None else "",
            "original_filename": file_data[7] if len(file_data) > 7 and file_data[7] is not None else "",
        }
        if field == "EMPTY":
            return ""
        return str(file_dict.get(field, ""))

    def _apply_transform(self, value, transform):
        """Apply transformation to field value"""
        if transform == "Uppercase":
            return value.upper()
        elif transform == "Lowercase":
            return value.lower()
        elif transform == "Title Case":
            return value.title()
        elif transform == "Sanitize":
            return re.sub(r'[^a-zA-Z0-9\s]', '', value)
        elif transform == "Truncate":
            return value[:50] + "..." if len(value) > 50 else value
        else:
            return value

    def _csv_escape(self, value, delimiter, should_quote):
        value = "" if value is None else str(value)
        value = value.replace('"', '""')
        if should_quote:
            return f'"{value}"'
        return value

    def _write_custom_csv(self, file_path, headers, rows, delimiter, quote_mode, quote_header, quote_modes):
        """Write custom CSV file with global or per-field quoting."""
        with open(file_path, "w", encoding="utf-8", newline='') as f:
            header_line = delimiter.join([self._csv_escape(h, delimiter, quote_header) for h in headers])
            f.write(header_line + '\n')
            
            for row in rows:
                formatted = []
                for i, v in enumerate(row):
                    per_field = quote_modes[i] if i < len(quote_modes) else "Auto"
                    if quote_mode == 1:  # All
                        should_quote = True
                    elif quote_mode == 2:  # None
                        should_quote = False
                    elif quote_mode == 3:  # Text Only
                        should_quote = bool(v) and not str(v).replace('.', '').replace('-', '').isdigit()
                    else:  # Use Per Field
                        if per_field == "Yes":
                            should_quote = True
                        elif per_field == "No":
                            should_quote = False
                        else:
                            should_quote = False
                    formatted.append(self._csv_escape(v, delimiter, should_quote))
                f.write(delimiter.join(formatted) + '\n')

    def on_tab_changed(self, index):
        if self.tabs.currentWidget() == self.custom_tab:
            self.ok_btn.setText("Export Custom CSV")
            self.ok_btn.setToolTip("Export metadata using the custom format")
        else:
            self.ok_btn.setText("Export All CSV")
            self.ok_btn.setToolTip("Export metadata to CSV")
        self.validate_output_and_buttons()

    def paste_output_path(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            sanitized = self._sanitize_path_text(text)
            self.output_lineedit.setText(sanitized)
            self.update_suffixes()

    def select_output_path(self):
        home_dir = os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder", home_dir)
        if path:
            self.output_lineedit.setText(path)
            self.update_suffixes()

    def load_config(self):
        if os.path.exists(self.CONFIG_PATH):
            try:
                with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[CSVExporterDialog] Error loading config {self.CONFIG_PATH}: {e}")
                return {}
        else:
            print(f"[CSVExporterDialog] Config file does not exist: {self.CONFIG_PATH}")
            return {}

    def save_config_realtime(self):
        config = {}
        for platform, checkbox in self.checkbox_map.items():
            config[platform] = checkbox.isChecked()
        try:
            config["open_folder_on_export"] = bool(self.open_folder_checkbox.isChecked())
        except Exception:
            config["open_folder_on_export"] = True
        try:
            try:
                if self.fs_watcher and self.fs_watcher.files():
                    if self.CONFIG_PATH in self.fs_watcher.files():
                        self.fs_watcher.removePath(self.CONFIG_PATH)
            except Exception as e:
                print(f"[CSVExporterDialog] Error removing watcher path: {e}")
            with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            try:
                if os.path.exists(self.CONFIG_PATH):
                    self.fs_watcher.addPath(self.CONFIG_PATH)
            except Exception as e:
                print(f"[CSVExporterDialog] Error adding watcher path: {e}")
        except Exception:
            print(f"[CSVExporterDialog] Error saving config to {self.CONFIG_PATH}")

    def on_config_file_changed(self, path):
        try:
            print(f"[CSVExporterDialog] Config file changed externally: {path}")
            new_config = self.load_config()
            for platform, checkbox in self.checkbox_map.items():
                try:
                    val = bool(new_config.get(platform, False))
                    checkbox.blockSignals(True)
                    checkbox.setChecked(val)
                    checkbox.blockSignals(False)
                    row_widget, entry, suffix, _btn = self.rename_rows[platform]
                    row_widget.setVisible(val)
                except Exception as e:
                    print(f"[CSVExporterDialog] Error applying config for {platform}: {e}")
            try:
                of = bool(new_config.get("open_folder_on_export", True))
                self.open_folder_checkbox.blockSignals(True)
                self.open_folder_checkbox.setChecked(of)
                self.open_folder_checkbox.blockSignals(False)
            except Exception as e:
                print(f"[CSVExporterDialog] Error applying open_folder_on_export: {e}")
            self.update_suffixes()
        except Exception as e:
            print(f"[CSVExporterDialog] Error reloading config file: {e}")

    def default_base_name(self, platform):
        try:
            today = datetime.datetime.now()
            p = platform.replace(" ", "_")
            return f"{p}_Image_Tea_Metadata_{today.year}_{today.strftime('%B')}_{today.day:02d}"
        except Exception as e:
            print(f"[CSVExporterDialog] Error building default base name for {platform}: {e}")
            return platform.replace(" ", "_") + "_Image_Tea_Metadata"

    def on_platform_toggled(self, platform, checked):
        try:
            checked_bool = bool(checked)
            self.save_config_realtime()
            row_widget, entry, suffix, _btn = self.rename_rows[platform]
            row_widget.setVisible(checked_bool)
            self.update_suffixes()
            self.validate_output_and_buttons()
        except Exception as e:
            print(f"[CSVExporterDialog] Error toggling platform {platform}: {e}")

    def _sanitize_path_text(self, text):
        if not isinstance(text, str):
            return text
        t = text.strip()
        if len(t) >= 2 and ((t[0] == '"' and t[-1] == '"') or (t[0] == "'" and t[-1] == "'")):
            return t[1:-1]
        return t

    def on_output_path_changed(self, text):
        sanitized = self._sanitize_path_text(text)
        if sanitized != text:
            self.output_lineedit.blockSignals(True)
            self.output_lineedit.setText(sanitized)
            self.output_lineedit.blockSignals(False)
            text = sanitized
        self.update_suffixes()
        self.validate_output_and_buttons()

    def _name_validation(self):
        illegal = '/\\:*?"<>|'
        illegal_set = set(illegal)
        empty = []
        illegal_found = {}
        for p, (w, e, s, _btn) in self.rename_rows.items():
            if not w.isVisible():
                continue
            text = e.text().strip()
            if text == "":
                empty.append(p)
            found = [c for c in text if c in illegal_set]
            if found:
                illegal_found[p] = ''.join(sorted(set(found)))
        if empty:
            names = ', '.join(empty)
            return False, f"A file name is empty for: {names}"
        if illegal_found:
            parts = [f"{plat} ({chars})" for plat, chars in illegal_found.items()]
            return False, "Illegal characters prevent export: " + '; '.join(parts)
        return True, ""

    def check_all(self):
        try:
            for p, cb in self.checkbox_map.items():
                cb.blockSignals(True)
                cb.setChecked(True)
                cb.blockSignals(False)
                row_widget, entry, suffix, _btn = self.rename_rows[p]
                row_widget.setVisible(True)
            self.save_config_realtime()
            self.update_suffixes()
            self.validate_output_and_buttons()
        except Exception as e:
            print(f"[CSVExporterDialog] Error in check_all: {e}")

    def uncheck_all(self):
        try:
            for p, cb in self.checkbox_map.items():
                cb.blockSignals(True)
                cb.setChecked(False)
                cb.blockSignals(False)
                row_widget, entry, suffix, _btn = self.rename_rows[p]
                row_widget.setVisible(False)
            self.save_config_realtime()
            self.update_suffixes()
            self.validate_output_and_buttons()
        except Exception as e:
            print(f"[CSVExporterDialog] Error in uncheck_all: {e}")

    def validate_output_and_buttons(self):
        path = self._sanitize_path_text(self.output_lineedit.text())
        valid = False
        try:
            valid = os.path.isdir(path)
        except Exception as e:
            print(f"[CSVExporterDialog] validate path error: {e}")
            valid = False
        if self.tabs.currentWidget() == self.custom_tab:
            enabled = valid and self.custom_table.rowCount() > 0
            self.ok_btn.setEnabled(enabled)
            self.validation_label.setVisible(False)
            return
        any_selected = any(cb.isChecked() for cb in self.platform_checkboxes)
        names_ok, msg = self._name_validation()
        enabled = valid and any_selected and names_ok
        self.ok_btn.setEnabled(enabled)
        if not names_ok and any_selected:
            self.validation_label.setText(msg)
            self.validation_label.setVisible(True)
        else:
            self.validation_label.setVisible(False)

    def open_folder_windows(self, folder_path):
        if sys.platform.startswith("win"):
            os.startfile(folder_path)

    def export_current_tab(self):
        if self.tabs.currentWidget() == self.custom_tab:
            self.export_custom_csv()
        else:
            self.export_csv()

    def export_csv(self):
        selected = [p for p, cb in self.checkbox_map.items() if cb.isChecked()]
        output_path = self._sanitize_path_text(self.output_lineedit.text())
        if not selected:
            print("[CSVExporterDialog] No platforms selected for export")
            return
        if not output_path or not os.path.isdir(output_path):
            print(f"[CSVExporterDialog] Invalid output path: {output_path}")
            return

        name_map = {}
        for p in selected:
            try:
                _, entry, _, _btn = self.rename_rows[p]
                name_map[p] = entry.text()
            except Exception as e:
                print(f"[CSVExporterDialog] Error reading name entry for {p}: {e}")

        from database.db_operation import ImageTeaDB
        db = ImageTeaDB()
        files = db.get_all_files()
        total_files = len(files) * len(selected)
        progress = QProgressDialog("Exporting CSV...", "Cancel", 0, total_files, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.setAutoClose(True)
        progress.setAutoReset(True)
        def progress_callback():
            value = progress.value() + 1
            progress.setValue(value)
        export_csv_for_platforms(selected, output_path, progress_callback, name_map)
        progress.setValue(total_files)
        try:
            if bool(self.open_folder_checkbox.isChecked()):
                self.open_folder_windows(output_path)
        except Exception as e:
            print(f"[CSVExporterDialog] Error opening output folder (open_folder_checkbox): {e}")
            try:
                if bool(self.config.get("open_folder_on_export", True)):
                    self.open_folder_windows(output_path)
            except Exception as e2:
                print(f"[CSVExporterDialog] Error opening output folder (config fallback): {e2}")
        self.accept()

    def export_single_platform(self, platform):
        output_path = self._sanitize_path_text(self.output_lineedit.text())
        if not output_path or not os.path.isdir(output_path):
            print(f"[CSVExporterDialog] Invalid output path for single export: {output_path}")
            from PySide6.QtWidgets import QToolTip
            QToolTip.showText(
                self.select_output_btn.mapToGlobal(self.select_output_btn.rect().center()),
                "Please select a valid output folder first.",
                self.select_output_btn,
                self.select_output_btn.rect(),
                3000
            )
            return
        try:
            _, entry, _, _btn = self.rename_rows[platform]
            name_map = {platform: entry.text()}
        except Exception as e:
            print(f"[CSVExporterDialog] Error reading name entry for {platform}: {e}")
            return
        from database.db_operation import ImageTeaDB
        db = ImageTeaDB()
        files = db.get_all_files()
        progress = QProgressDialog(f"Exporting {platform} CSV...", "Cancel", 0, len(files), self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.setAutoClose(True)
        progress.setAutoReset(True)
        def progress_callback():
            progress.setValue(progress.value() + 1)
        export_csv_for_platforms([platform], output_path, progress_callback, name_map)
        progress.setValue(len(files))
        print(f"[CSVExporterDialog] Single export done: {platform}")
        try:
            if bool(self.open_folder_checkbox.isChecked()):
                self.open_folder_windows(output_path)
        except Exception as e:
            print(f"[CSVExporterDialog] Error opening folder after single export: {e}")
        self.update_suffixes()

    def update_suffixes(self):
        path = self._sanitize_path_text(self.output_lineedit.text())
        if not path or not os.path.isdir(path):
            for p, (w, e, s, _btn) in self.rename_rows.items():
                if w.isVisible():
                    s.setText("_001.CSV")
            if hasattr(self, 'custom_suffix_label'):
                self.custom_suffix_label.setText("_001.CSV")
            return
        for p, (w, e, s, _btn) in self.rename_rows.items():
            if not w.isVisible():
                continue
            base = e.text()
            try:
                idx = get_next_index(base, path)
                s.setText(f"_{idx:03d}.CSV")
            except Exception as ex:
                print(f"[CSVExporterDialog] Error computing next index for {p}: {ex}")
        
        # Update custom format suffix dynamically too
        if hasattr(self, 'custom_suffix_label') and hasattr(self, 'custom_filename_edit'):
            custom_base = self.custom_filename_edit.text().strip()
            if custom_base:
                try:
                    idx = get_next_index(custom_base, path)
                    self.custom_suffix_label.setText(f"_{idx:03d}.CSV")
                except Exception as ex:
                    print(f"[CSVExporterDialog] Error computing next custom index: {ex}")
                    self.custom_suffix_label.setText("_001.CSV")
            else:
                self.custom_suffix_label.setText("_001.CSV")
