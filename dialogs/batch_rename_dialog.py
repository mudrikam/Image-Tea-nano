import os
import json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QComboBox, QRadioButton, QButtonGroup, QGroupBox,
    QFormLayout, QLineEdit, QCheckBox, QLabel, QHBoxLayout, QSpinBox, QPushButton, QWidget, QMessageBox,
    QProgressDialog, QTabWidget, QSplitter, QScrollArea, QInputDialog
)
from PySide6.QtCore import Qt, QThread, Signal
from datetime import datetime
import re
import qtawesome as qta
from ui.theme_system import theme

class UndoRenameWorkerThread(QThread):
    progress_updated = Signal(int, str)  # current, status_text
    finished_signal = Signal(int, int)  # success_count, fail_count
    
    def __init__(self, files, db):
        super().__init__()
        self.files = files
        self.db = db
        
    def run(self):
        try:
            success_count = 0
            fail_count = 0
            
            for i, filepath in enumerate(self.files):
                current_file = os.path.basename(filepath) if filepath else "Unknown"
                self.progress_updated.emit(i, f"Undoing rename: {current_file}")
                
                try:
                    self.db.undo_rename([filepath])
                    success_count += 1
                except Exception as e:
                    fail_count += 1
            
            self.progress_updated.emit(len(self.files), "Undo rename completed")
            
            self.finished_signal.emit(success_count, fail_count)
            
        except Exception as e:
            self.finished_signal.emit(0, len(self.files))

class RenameWorkerThread(QThread):
    progress_updated = Signal(int, str)  # current, status_text
    finished_signal = Signal(list, int, int)  # results, success_count, fail_count
    
    def __init__(self, files, pattern_func, db):
        super().__init__()
        self.files = files
        self.pattern_func = pattern_func
        self.db = db
        
    def run(self):
        try:
            results = []
            success_count = 0
            fail_count = 0
            
            total_files = len(self.files)
            
            for i, file_info in enumerate(self.files):
                current_file = os.path.basename(file_info['filepath']) if file_info['filepath'] else file_info['filename']
                self.progress_updated.emit(i, f"Renaming: {current_file}")
                
                try:
                    new_filename = self.pattern_func(file_info, i)
                    
                    old_path = file_info['filepath']
                    if old_path and os.path.exists(old_path):
                        directory = os.path.dirname(old_path)
                        new_path = os.path.join(directory, new_filename)
                        
                        if os.path.exists(new_path) and new_path != old_path:
                            result = (old_path, file_info['filename'], new_filename, old_path, False, "File already exists")
                            fail_count += 1
                        else:
                            try:
                                os.rename(old_path, new_path)
                                result = (old_path, file_info['filename'], new_filename, new_path, True, None)
                                success_count += 1
                            except Exception as rename_error:
                                result = (old_path, file_info['filename'], new_filename, old_path, False, str(rename_error))
                                fail_count += 1
                    else:
                        result = (old_path, file_info['filename'], new_filename, old_path, False, "File not found")
                        fail_count += 1
                        
                except Exception as e:
                    result = (
                        file_info['filepath'],
                        file_info['filename'], 
                        file_info['filename'],
                        file_info['filepath'],
                        False,
                        f"Pattern error: {str(e)}"
                    )
                    fail_count += 1
                
                results.append(result)
                
                self.progress_updated.emit(i + 1, f"Processed {i + 1}/{total_files} files")
            
            self.progress_updated.emit(total_files, "Updating database...")
            
            if results:
                self.db.batch_update_file_paths(results)
            
            self.finished_signal.emit(results, success_count, fail_count)
            
        except Exception as e:
            self.finished_signal.emit([], 0, len(self.files))

class BatchRenameDialog(QDialog):
    VAR_COLORS = {
        "prefix": "#1976d2",
        "original": "#ff891a",
        "number": "#fbc02d",
        "suffix": "#388e3c",
        "timestamp": "#00A6C4",
        "date": "#d32f2f",
        "title": "#9508d1",
    }
    PRESETS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs", "batch_rename_presets.json")

    def __init__(self, parent=None, table_widget=None, db=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Rename")
        self.setWindowFlags(self.windowFlags() | Qt.MSWindowsFixedSizeDialogHint)
        self.setFixedWidth(620)
        self.table_widget = table_widget
        self.db = db
        self.pattern_order = ["prefix", "title", "suffix"]

        layout = QVBoxLayout(self)

        self.combo_mode = QComboBox(self)
        self.combo_mode.addItem("Rename All")
        self.combo_mode.addItem("Selected Only")
        self.combo_mode.setCurrentIndex(0)
        self.combo_mode.setToolTip("Rename All: process every file in the database.\nSelected Only: process only the checked rows in the table.")
        layout.addWidget(self.combo_mode)

        self.tab_widget = QTabWidget(self)
        layout.addWidget(self.tab_widget)

        self._build_same_as_title_tab()
        self._build_custom_naming_tab()

        self.info_label = QLabel(
            "<b>Info:</b> After renaming, you can restore the previous filename using Undo Rename if needed.",
            self
        )
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        undo_layout = QHBoxLayout()
        self.undo_btn = QPushButton("Undo Rename", self)
        self.undo_btn.setIcon(qta.icon('fa6s.rotate-left'))
        self.undo_btn.setToolTip("Restore file names to what they were before the last rename.")
        undo_layout.addWidget(self.undo_btn)
        undo_layout.addStretch()
        layout.addLayout(undo_layout)
        self.rename_btn = QPushButton("Rename", self)
        self.rename_btn.setIcon(qta.icon('fa6s.pen-to-square', color=theme.get_color('white')))
        self.rename_btn.setToolTip("Start renaming files using the active tab settings.")
        self.rename_btn.setMinimumHeight(36)
        self.rename_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.get_color('primary')};
                color: {theme.get_color('white')};
                border: none;
                border-radius: 5px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{ background-color: {theme.get_color('primary_hover')}; }}
            QPushButton:pressed {{ background-color: {theme.get_color('primary_pressed')}; }}
            QPushButton:disabled {{ background-color: {theme.get_color('button_disabled_bg')}; color: {theme.get_color('button_disabled_fg')}; }}
        """)
        layout.addWidget(self.rename_btn)

        self.rename_btn.clicked.connect(self.do_rename)
        self.undo_btn.clicked.connect(self.do_undo_rename)

        self.setLayout(layout)
        self.update_preview()

    def _build_same_as_title_tab(self):
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)

        san_group = QGroupBox("Sanitization Options")
        san_layout = QVBoxLayout(san_group)

        self.sat_remove_special_checkbox = QCheckBox("Remove Special Characters")
        self.sat_remove_special_checkbox.setToolTip("Strip special characters from the title (e.g. @, #, $, %, &) before using it as the filename.")
        self.sat_replace_space_checkbox = QCheckBox("Replace space with underscore")
        self.sat_replace_space_checkbox.setToolTip("Replace all spaces in the title with underscores (_).")
        self.sat_sanitize_checkbox = QCheckBox("Sanitize filename (alphanumeric only)")
        self.sat_sanitize_checkbox.setToolTip("Keep only letters (A-Z) and digits (0-9) in the filename.\nAll other characters including spaces and underscores will be removed.")
        san_layout.addWidget(self.sat_remove_special_checkbox)
        san_layout.addWidget(self.sat_replace_space_checkbox)
        san_layout.addWidget(self.sat_sanitize_checkbox)
        tab_layout.addWidget(san_group)

        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Preset:"))
        self.sat_preset_combo = QComboBox()
        self.sat_preset_combo.setMinimumWidth(140)
        self.sat_preset_combo.setToolTip("Select a saved sanitization preset. Settings are applied automatically.")
        preset_layout.addWidget(self.sat_preset_combo)
        self.sat_preset_save_btn = QPushButton()
        self.sat_preset_save_btn.setIcon(qta.icon('fa6s.floppy-disk'))
        self.sat_preset_save_btn.setFixedWidth(30)
        self.sat_preset_save_btn.setToolTip("Save the current sanitization settings as a new preset.")
        self.sat_preset_delete_btn = QPushButton()
        self.sat_preset_delete_btn.setIcon(qta.icon('fa6s.trash'))
        self.sat_preset_delete_btn.setFixedWidth(30)
        self.sat_preset_delete_btn.setToolTip("Delete the currently selected preset.")
        preset_layout.addWidget(self.sat_preset_save_btn)
        preset_layout.addWidget(self.sat_preset_delete_btn)
        preset_layout.addStretch()
        tab_layout.addLayout(preset_layout)

        self.sat_preview_label = QLabel("Preview: ")
        self.sat_preview_label.setTextFormat(Qt.RichText)
        self.sat_preview_label.setWordWrap(True)
        tab_layout.addWidget(self.sat_preview_label)

        tab_layout.addStretch()
        self.tab_widget.addTab(tab, "Same as Title")

        self.sat_remove_special_checkbox.toggled.connect(self.update_preview)
        self.sat_replace_space_checkbox.toggled.connect(self.update_preview)
        self.sat_sanitize_checkbox.toggled.connect(self.update_preview)
        self.sat_preset_combo.currentIndexChanged.connect(lambda: self._load_preset("same_as_title"))
        self.sat_preset_save_btn.clicked.connect(lambda: self._save_preset("same_as_title"))
        self.sat_preset_delete_btn.clicked.connect(lambda: self._delete_preset("same_as_title"))

    def _build_custom_naming_tab(self):
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)

        splitter = QSplitter(Qt.Horizontal)

        left_widget = QWidget()
        left_layout = QFormLayout(left_widget)
        left_layout.setContentsMargins(4, 4, 4, 4)

        self.prefix_edit = QLineEdit()
        self.prefix_edit.setToolTip("Text prepended to the filename.\nExample: \"mystore\" → mystore_Title.jpg")
        left_layout.addRow("Prefix", self.prefix_edit)

        self.suffix_edit = QLineEdit()
        self.suffix_edit.setToolTip("Text appended to the filename, before the extension.\nExample: \"v2\" → Title_v2.jpg")
        left_layout.addRow("Suffix", self.suffix_edit)

        numbering_layout = QHBoxLayout()
        self.numbering_checkbox = QCheckBox("Add Numbering")
        self.numbering_checkbox.setToolTip("Append a sequential number to each filename.")
        self.numbering_spin = QSpinBox()
        self.numbering_spin.setMinimum(1)
        self.numbering_spin.setMaximum(10)
        self.numbering_spin.setValue(3)
        self.numbering_spin.setEnabled(False)
        self.numbering_spin.setToolTip("Number of digits in the sequence.\nExample: 3 digits → 001, 002, 003, ...")
        numbering_layout.addWidget(self.numbering_checkbox)
        numbering_layout.addWidget(QLabel("Digits:"))
        numbering_layout.addWidget(self.numbering_spin)
        left_layout.addRow(numbering_layout)
        self.numbering_checkbox.toggled.connect(self.numbering_spin.setEnabled)

        self.timestamp_combo = QComboBox()
        self.timestamp_combo.addItem("None")
        self.timestamp_combo.addItem("Timestamp")
        self.timestamp_combo.addItem("Date")
        self.timestamp_combo.setToolTip("None: no date/time appended.\nTimestamp: append full datetime (YYYYmmdd_HHMMSS).\nDate: append date only (YYYY-MM-DD).")
        left_layout.addRow("Timestamp/Date", self.timestamp_combo)

        self.remove_special_checkbox = QCheckBox("Remove Special Characters")
        self.remove_special_checkbox.setToolTip("Strip special characters from the output filename (e.g. @, #, $, %) to ensure compatibility across all operating systems.")
        left_layout.addRow(self.remove_special_checkbox)

        self.replace_space_checkbox = QCheckBox("Replace space with underscore")
        self.replace_space_checkbox.setToolTip("Replace all spaces in the output filename with underscores (_).")
        left_layout.addRow(self.replace_space_checkbox)

        self.sanitize_checkbox = QCheckBox("Sanitize filename (alphanumeric only)")
        self.sanitize_checkbox.setToolTip("Keep only letters (A-Z) and digits (0-9) in the output filename.\nAll other characters including spaces and underscores will be removed.")
        left_layout.addRow(self.sanitize_checkbox)

        splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 4, 4, 4)

        self.radio_default_pattern = QRadioButton("Default Pattern")
        self.radio_default_pattern.setToolTip("Use the default pattern: {prefix}_{title}_{suffix}")
        self.radio_custom_pattern = QRadioButton("Custom Pattern")
        self.radio_custom_pattern.setToolTip("Arrange the variables in custom order using the checklist below.")
        self.pattern_mode_group = QButtonGroup(right_widget)
        self.pattern_mode_group.addButton(self.radio_default_pattern)
        self.pattern_mode_group.addButton(self.radio_custom_pattern)
        self.radio_default_pattern.setChecked(True)
        pattern_mode_layout = QHBoxLayout()
        pattern_mode_layout.addWidget(self.radio_default_pattern)
        pattern_mode_layout.addWidget(self.radio_custom_pattern)
        right_layout.addLayout(pattern_mode_layout)

        self.pattern_edit = QLineEdit()
        self.pattern_edit.setText("{prefix}_{title}_{suffix}")
        self.pattern_edit.setReadOnly(True)
        self.pattern_edit.setToolTip("Filename pattern built from the variable checklist below.\nAuto-generated \u2014 not directly editable.")
        right_layout.addWidget(QLabel("Pattern:"))
        right_layout.addWidget(self.pattern_edit)

        variable_names = ["prefix", "original", "number", "suffix", "timestamp", "date", "title"]
        VAR_TOOLTIPS = {
            "prefix": "Text from the Prefix field.",
            "original": "Original filename without extension.",
            "number": "Sequential number based on the Digits setting.",
            "suffix": "Text from the Suffix field.",
            "timestamp": "Date and time the rename was run (format: YYYYmmdd_HHMMSS).",
            "date": "Date the rename was run (format: YYYY-MM-DD).",
            "title": "File title from the database metadata.",
        }
        self.checklist_widget = QWidget()
        self.checklist_layout = QVBoxLayout(self.checklist_widget)
        self.checklist_layout.setContentsMargins(0, 0, 0, 0)
        self.check_vars = []
        for var in variable_names:
            h = QHBoxLayout()
            cb = QCheckBox()
            cb.setChecked(var in self.pattern_order)
            cb.setToolTip(f"Check to include {{{var}}} in the filename pattern.")
            color_label = QLabel(f"{{{var}}}")
            color_label.setStyleSheet(f"color: {self.VAR_COLORS[var]}; font-weight: bold;")
            color_label.setToolTip(VAR_TOOLTIPS[var])
            left_btn = QPushButton()
            left_btn.setIcon(qta.icon('fa6s.angle-left'))
            left_btn.setFixedWidth(28)
            left_btn.setToolTip(f"Move {{{var}}} left in the pattern order.")
            right_btn = QPushButton()
            right_btn.setIcon(qta.icon('fa6s.angle-right'))
            right_btn.setFixedWidth(28)
            right_btn.setToolTip(f"Move {{{var}}} right in the pattern order.")
            h.addWidget(cb)
            h.addWidget(color_label)
            h.addWidget(left_btn)
            h.addWidget(right_btn)
            self.checklist_layout.addLayout(h)
            self.check_vars.append((cb, left_btn, right_btn, var, color_label))
            cb.stateChanged.connect(self.update_checklist_pattern)
            left_btn.clicked.connect(lambda checked, v=var: self.move_pattern_var(v, -1))
            right_btn.clicked.connect(lambda checked, v=var: self.move_pattern_var(v, 1))
        right_layout.addWidget(QLabel("Checklist Variables:"))
        right_layout.addWidget(self.checklist_widget)
        right_layout.addStretch()

        splitter.addWidget(right_widget)
        splitter.setSizes([220, 220])
        tab_layout.addWidget(splitter)

        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Preset:"))
        self.cn_preset_combo = QComboBox()
        self.cn_preset_combo.setMinimumWidth(140)
        self.cn_preset_combo.setToolTip("Select a saved custom naming preset. Settings are applied automatically.")
        preset_layout.addWidget(self.cn_preset_combo)
        self.cn_preset_save_btn = QPushButton()
        self.cn_preset_save_btn.setIcon(qta.icon('fa6s.floppy-disk'))
        self.cn_preset_save_btn.setFixedWidth(30)
        self.cn_preset_save_btn.setToolTip("Save the current custom naming configuration as a new preset.")
        self.cn_preset_delete_btn = QPushButton()
        self.cn_preset_delete_btn.setIcon(qta.icon('fa6s.trash'))
        self.cn_preset_delete_btn.setFixedWidth(30)
        self.cn_preset_delete_btn.setToolTip("Delete the currently selected preset.")
        preset_layout.addWidget(self.cn_preset_save_btn)
        preset_layout.addWidget(self.cn_preset_delete_btn)
        preset_layout.addStretch()
        tab_layout.addLayout(preset_layout)

        self.cn_preview_label = QLabel("Preview: ")
        self.cn_preview_label.setTextFormat(Qt.RichText)
        self.cn_preview_label.setWordWrap(True)
        tab_layout.addWidget(self.cn_preview_label)

        self.tab_widget.addTab(tab, "Custom Naming")

        self.radio_default_pattern.toggled.connect(self._on_pattern_mode_toggle)
        self.radio_custom_pattern.toggled.connect(self._on_pattern_mode_toggle)
        self.prefix_edit.textChanged.connect(self.update_preview)
        self.suffix_edit.textChanged.connect(self.update_preview)
        self.pattern_edit.textChanged.connect(self.update_preview)
        self.numbering_checkbox.toggled.connect(self.update_preview)
        self.numbering_spin.valueChanged.connect(self.update_preview)
        self.timestamp_combo.currentIndexChanged.connect(self.update_preview)
        self.remove_special_checkbox.toggled.connect(self.update_preview)
        self.replace_space_checkbox.toggled.connect(self.update_preview)
        self.sanitize_checkbox.toggled.connect(self.update_preview)
        self.cn_preset_combo.currentIndexChanged.connect(lambda: self._load_preset("custom_naming"))
        self.cn_preset_save_btn.clicked.connect(lambda: self._save_preset("custom_naming"))
        self.cn_preset_delete_btn.clicked.connect(lambda: self._delete_preset("custom_naming"))

        self._on_pattern_mode_toggle()
        self._refresh_preset_combos()

    def _load_presets_data(self):
        if not os.path.exists(self.PRESETS_FILE):
            return {"presets": []}
        with open(self.PRESETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_presets_data(self, data):
        with open(self.PRESETS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def _refresh_preset_combos(self):
        data = self._load_presets_data()
        sat_names = [""] + [p["name"] for p in data["presets"] if p["type"] == "same_as_title"]
        cn_names = [""] + [p["name"] for p in data["presets"] if p["type"] == "custom_naming"]
        self.sat_preset_combo.blockSignals(True)
        self.sat_preset_combo.clear()
        self.sat_preset_combo.addItems(sat_names)
        self.sat_preset_combo.blockSignals(False)
        self.cn_preset_combo.blockSignals(True)
        self.cn_preset_combo.clear()
        self.cn_preset_combo.addItems(cn_names)
        self.cn_preset_combo.blockSignals(False)

    def _save_preset(self, preset_type):
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        data = self._load_presets_data()
        data["presets"] = [p for p in data["presets"] if not (p["name"] == name and p["type"] == preset_type)]
        if preset_type == "same_as_title":
            preset = {
                "type": "same_as_title",
                "name": name,
                "remove_special": self.sat_remove_special_checkbox.isChecked(),
                "replace_space": self.sat_replace_space_checkbox.isChecked(),
                "sanitize": self.sat_sanitize_checkbox.isChecked()
            }
        else:
            preset = {
                "type": "custom_naming",
                "name": name,
                "prefix": self.prefix_edit.text(),
                "suffix": self.suffix_edit.text(),
                "numbering": self.numbering_checkbox.isChecked(),
                "digits": self.numbering_spin.value(),
                "timestamp_mode": self.timestamp_combo.currentText(),
                "remove_special": self.remove_special_checkbox.isChecked(),
                "replace_space": self.replace_space_checkbox.isChecked(),
                "sanitize": self.sanitize_checkbox.isChecked(),
                "pattern_mode": "custom" if self.radio_custom_pattern.isChecked() else "default",
                "pattern_order": list(self.pattern_order)
            }
        data["presets"].append(preset)
        self._save_presets_data(data)
        print(f"[batch_rename] Preset '{name}' ({preset_type}) saved.")
        self._refresh_preset_combos()

    def _delete_preset(self, preset_type):
        combo = self.sat_preset_combo if preset_type == "same_as_title" else self.cn_preset_combo
        name = combo.currentText()
        if not name:
            return
        data = self._load_presets_data()
        before = len(data["presets"])
        data["presets"] = [p for p in data["presets"] if not (p["name"] == name and p["type"] == preset_type)]
        if len(data["presets"]) < before:
            self._save_presets_data(data)
            print(f"[batch_rename] Preset '{name}' ({preset_type}) deleted.")
        self._refresh_preset_combos()

    def _load_preset(self, preset_type):
        combo = self.sat_preset_combo if preset_type == "same_as_title" else self.cn_preset_combo
        name = combo.currentText()
        if not name:
            return
        data = self._load_presets_data()
        preset = next((p for p in data["presets"] if p["name"] == name and p["type"] == preset_type), None)
        if preset is None:
            print(f"[batch_rename] Preset '{name}' ({preset_type}) not found.")
            return
        if preset_type == "same_as_title":
            self.sat_remove_special_checkbox.setChecked(preset["remove_special"])
            self.sat_replace_space_checkbox.setChecked(preset["replace_space"])
            self.sat_sanitize_checkbox.setChecked(preset["sanitize"])
        else:
            self.prefix_edit.setText(preset["prefix"])
            self.suffix_edit.setText(preset["suffix"])
            self.numbering_checkbox.setChecked(preset["numbering"])
            self.numbering_spin.setValue(preset["digits"])
            idx = self.timestamp_combo.findText(preset["timestamp_mode"])
            if idx >= 0:
                self.timestamp_combo.setCurrentIndex(idx)
            self.remove_special_checkbox.setChecked(preset["remove_special"])
            self.replace_space_checkbox.setChecked(preset["replace_space"])
            self.sanitize_checkbox.setChecked(preset["sanitize"])
            if preset["pattern_mode"] == "custom":
                self.radio_custom_pattern.setChecked(True)
            else:
                self.radio_default_pattern.setChecked(True)
            self.pattern_order = list(preset["pattern_order"])
            for cb, _, _, var, _ in self.check_vars:
                cb.blockSignals(True)
                cb.setChecked(var in self.pattern_order)
                cb.blockSignals(False)
            self.update_checklist_pattern()
        print(f"[batch_rename] Preset '{name}' ({preset_type}) loaded.")
        self.update_preview()

    def _on_pattern_mode_toggle(self):
        custom_enabled = self.radio_custom_pattern.isChecked()
        self.pattern_edit.setReadOnly(True)
        self.checklist_widget.setEnabled(custom_enabled)
        if self.radio_default_pattern.isChecked():
            self.pattern_order = ["prefix", "title", "suffix"]
            self.pattern_edit.setText("{prefix}_{title}_{suffix}")
            # Set checklist to match default pattern
            for cb, _, _, var, _ in self.check_vars:
                cb.blockSignals(True)
                cb.setChecked(var in self.pattern_order)
                cb.blockSignals(False)
        elif self.radio_custom_pattern.isChecked():
            # Restore checklist to match current pattern_order (custom)
            for cb, _, _, var, _ in self.check_vars:
                cb.blockSignals(True)
                cb.setChecked(var in self.pattern_order)
                cb.blockSignals(False)
            self.update_checklist_pattern()
        self.update_preview()

    def update_checklist_pattern(self):
        checked_vars = []
        for cb, _, _, var, _ in self.check_vars:
            if cb.isChecked():
                checked_vars.append(var)
        self.pattern_order = [v for v in self.pattern_order if v in checked_vars]
        for v in checked_vars:
            if v not in self.pattern_order:
                self.pattern_order.append(v)
        pattern = "_".join(f"{{{v}}}" for v in self.pattern_order)
        self.pattern_edit.setText(pattern)
        self.update_preview()

    def move_pattern_var(self, var, direction):
        if var not in self.pattern_order:
            return
        idx = self.pattern_order.index(var)
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self.pattern_order):
            return
        self.pattern_order[idx], self.pattern_order[new_idx] = self.pattern_order[new_idx], self.pattern_order[idx]
        self.update_checklist_pattern()

    def update_preview(self):
        self._update_sat_preview()
        self._update_cn_preview()

    def _compute_preview_html(self, pattern, example_vars, sanitize_fn, remove_special, replace_space, sanitize_alnum):
        def _san_alnum(s):
            v = re.sub(r'[^A-Za-z0-9]', '', s)
            return v if v else 'file'

        sanitized_vars = {}
        for k, v in example_vars.items():
            if not v:
                sanitized_vars[k] = v
                continue
            val = v
            if sanitize_alnum:
                val = _san_alnum(val)
            else:
                if remove_special:
                    val = re.sub(r'[^A-Za-z0-9_-]', '', val)
                if replace_space:
                    val = val.replace(' ', '_')
            sanitized_vars[k] = val

        try:
            preview_raw = pattern.format(**sanitized_vars)
        except Exception:
            return "Invalid pattern"

        preview_raw = re.sub(r'_{2,}', '_', preview_raw)
        preview_raw = re.sub(r'_+\.', '.', preview_raw)
        preview_raw = re.sub(r'\._+', '.', preview_raw)
        preview_raw = re.sub(r'^_+|_+$', '', preview_raw)

        if sanitize_alnum:
            final = re.sub(r'[^A-Za-z0-9]', '', preview_raw)
            preview_html = final if final else 'file'
        else:
            preview_html = preview_raw

        var_spans = []
        for var, color in self.VAR_COLORS.items():
            val = sanitized_vars.get(var, "")
            if not val:
                continue
            display_val = val
            if sanitize_alnum:
                display_val = re.sub(r'[^A-Za-z0-9]', '', val)
            if not display_val:
                continue
            marker = f"__VAR_{var.upper()}__"
            preview_html = re.sub(re.escape(display_val), marker, preview_html, count=1)
            var_spans.append((marker, f'<span style="color:{color};font-weight:bold;">{display_val}</span>'))

        for marker, span in var_spans:
            preview_html = preview_html.replace(marker, span, 1)

        return preview_html

    def _update_sat_preview(self):
        remove_special = self.sat_remove_special_checkbox.isChecked()
        replace_space = self.sat_replace_space_checkbox.isChecked()
        sanitize_alnum = self.sat_sanitize_checkbox.isChecked()
        example_title = "Title Example"
        example_vars = {"title": example_title}
        preview_html = self._compute_preview_html(
            "{title}", example_vars, None, remove_special, replace_space, sanitize_alnum
        )
        self.sat_preview_label.setText(f"Preview: {preview_html}")

    def _update_cn_preview(self):
        prefix = self.prefix_edit.text()
        suffix = self.suffix_edit.text()
        numbering = self.numbering_checkbox.isChecked()
        digits = self.numbering_spin.value()
        timestamp_mode = self.timestamp_combo.currentText()
        remove_special = self.remove_special_checkbox.isChecked()
        replace_space = self.replace_space_checkbox.isChecked()
        sanitize_alnum = self.sanitize_checkbox.isChecked()

        if self.radio_default_pattern.isChecked():
            pattern = "{prefix}_{title}_{suffix}"
        else:
            pattern = self.pattern_edit.text()

        now = datetime.now()
        today_date = now.strftime("%Y-%m-%d")
        today_timestamp = now.strftime("%Y%m%d_%H%M%S")
        timestamp_val = today_timestamp if (timestamp_mode == "Timestamp" or "{timestamp}" in pattern) else ""
        date_val = today_date if (timestamp_mode == "Date" or "{date}" in pattern) else ""

        example_title = re.sub(r'[.,\-]', '', "Title Example")
        example_vars = {
            "prefix": prefix,
            "original": "original_name",
            "number": f"{1:0{digits}d}" if numbering else "",
            "suffix": suffix,
            "timestamp": timestamp_val,
            "date": date_val,
            "title": example_title
        }
        preview_html = self._compute_preview_html(pattern, example_vars, None, remove_special, replace_space, sanitize_alnum)
        self.cn_preview_label.setText(f"Preview: {preview_html}")

    def _sanitize_windows_filename(self, name):
        # Remove Windows forbidden characters: <>:"/\|?* and control chars
        return re.sub(r'[<>:"/\\|?*\x00-\x1F]', '', name)

    def _sanitize_alnum_base(self, base):
        # Keep only ASCII letters and digits; fallback to 'file' if result empty
        sanitized = re.sub(r'[^A-Za-z0-9]', '', base)
        if not sanitized:
            print(f"[batch_rename] _sanitize_alnum_base: sanitized base empty for '{base}', fallback to 'file'")
            sanitized = 'file'
        return sanitized

    def do_rename(self):
        mode = self.combo_mode.currentText()
        
        # Get files from database, not just current page
        if mode == "Rename All":
            all_files_db = self.db.get_all_files()
            files = []
            for db_row in all_files_db:
                # db_row: [id, filepath, filename, title, description, tags, category, status, ...]
                if len(db_row) >= 8:
                    files.append({
                        "filepath": db_row[1],
                        "filename": db_row[2],
                        "title": db_row[3] or "",
                        "description": db_row[4] or "",
                        "tags": db_row[5] or "",
                        "status": db_row[7] if len(db_row) > 7 else "",
                        "row": -1
                    })
        else:
            file_rows = []
            for row in range(self.table_widget.table.rowCount()):
                checkbox_item = self.table_widget.table.item(row, 0)
                if checkbox_item and checkbox_item.checkState() == Qt.Checked:
                    file_rows.append(row)
            
            if not file_rows:
                mb = QMessageBox(self)
                mb.setWindowTitle("No Selection")
                mb.setIcon(QMessageBox.Information)
                mb.setText("No rows checked for renaming.")
                btn_ok = QPushButton("OK")
                btn_ok.setIcon(qta.icon('fa6s.xmark'))
                mb.addButton(btn_ok, QMessageBox.AcceptRole)
                mb.exec()
                return

            files = []
            for row in file_rows:
                filepath_item = self.table_widget.table.item(row, 1)
                filepath = filepath_item.data(Qt.UserRole) if filepath_item else None
                filename = self.table_widget.table.item(row, 2).text()
                title = self.table_widget.table.item(row, 3).text()
                description = self.table_widget.table.item(row, 4).text()
                tags = self.table_widget.table.item(row, 5).text()
                status = self.table_widget.table.item(row, 8).text()
                files.append({
                    "filepath": filepath,
                    "filename": filename,
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "status": status,
                    "row": row
                })

        def sanitize_title(title):
            if not title:
                return title
            return re.sub(r'[.,\-]', '', title)

        def sanitize_windows_filename(name):
            return self._sanitize_windows_filename(name)

        if self.tab_widget.currentIndex() == 0:
            def pattern_func(file_info, idx):
                base, ext = os.path.splitext(file_info['filename'])
                title = file_info['title'] or base
                title = sanitize_title(title)
                remove_special = self.sat_remove_special_checkbox.isChecked()
                replace_space = self.sat_replace_space_checkbox.isChecked()
                sanitize_name = self.sat_sanitize_checkbox.isChecked()

                if sanitize_name:
                    title = re.sub(r'[^A-Za-z0-9]', '', title)
                    if not title:
                        orig_base = os.path.splitext(file_info.get('filename',''))[0]
                        fb = self._sanitize_alnum_base(orig_base)
                        print(f"[batch_rename] sanitize resulted in empty title for '{file_info.get('filename','')}', falling back to sanitized original base '{fb}'")
                        title = fb
                else:
                    if remove_special:
                        title = re.sub(r'[^A-Za-z0-9_-]', '', title)
                    if replace_space:
                        title = title.replace(' ', '_')

                safe_title = sanitize_windows_filename(title)
                return f"{safe_title}{ext}"
        else:
            def pattern_func(file_info, idx):
                pattern = self.pattern_edit.text()
                prefix = self.prefix_edit.text()
                suffix = self.suffix_edit.text()
                numbering = self.numbering_checkbox.isChecked()
                digits = self.numbering_spin.value()
                timestamp_mode = self.timestamp_combo.currentText()
                remove_special = self.remove_special_checkbox.isChecked()
                replace_space = self.replace_space_checkbox.isChecked()
                now = datetime.now()
                today_date = now.strftime("%Y-%m-%d")
                today_timestamp = now.strftime("%Y%m%d_%H%M%S")
                if "{original}" in pattern:
                    base, ext = os.path.splitext(file_info['filename'])
                else:
                    base, ext = "", os.path.splitext(file_info['filename'])[1]
                timestamp_val = today_timestamp if (timestamp_mode == "Timestamp" or "{timestamp}" in pattern) else ""
                date_val = today_date if (timestamp_mode == "Date" or "{date}" in pattern) else ""
                number_val = f"{idx+1:0{digits}d}" if numbering else ""
                sanitized_title = sanitize_title(file_info['title'] or base)
                vars_dict = {
                    "prefix": prefix,
                    "original": base,
                    "number": number_val,
                    "suffix": suffix,
                    "timestamp": timestamp_val,
                    "date": date_val,
                    "title": sanitized_title
                }
                try:
                    new_base = pattern.format(**vars_dict)
                except Exception:
                    new_base = base
                new_base = re.sub(r'_{2,}', '_', new_base)
                new_base = re.sub(r'_+\.', '.', new_base)
                new_base = re.sub(r'\._+', '.', new_base)
                new_base = re.sub(r'^_+|_+$', '', new_base)
                sanitize_name = self.sanitize_checkbox.isChecked()
                if sanitize_name:
                    new_base_s = re.sub(r'[^A-Za-z0-9]', '', new_base)
                    if not new_base_s:
                        # fallback to sanitized original filename base
                        orig_base = os.path.splitext(file_info.get('filename',''))[0]
                        fb = self._sanitize_alnum_base(orig_base)
                        print(f"[batch_rename] sanitize resulted in empty name for '{file_info.get('filename','')}', falling back to sanitized original base '{fb}'")
                        new_base = fb
                    else:
                        new_base = new_base_s
                else:
                    if remove_special:
                        new_base = re.sub(r'[^A-Za-z0-9_-]', '', new_base)
                    if replace_space:
                        new_base = new_base.replace(' ', '_')
                safe_base = sanitize_windows_filename(new_base)
                return f"{safe_base}{ext}"

        mb = QMessageBox(self)
        mb.setWindowTitle("Confirm Rename")
        mb.setIcon(QMessageBox.Question)
        mb.setText(f"Are you sure you want to rename {len(files)} files? After renaming, you can restore the previous filename using Undo Rename if needed.")
        btn_yes = QPushButton("Yes")
        btn_yes.setIcon(qta.icon('fa6s.check'))
        btn_no = QPushButton("No")
        btn_no.setIcon(qta.icon('fa6s.xmark'))
        mb.addButton(btn_yes, QMessageBox.AcceptRole)
        mb.addButton(btn_no, QMessageBox.RejectRole)
        mb.exec()
        if mb.clickedButton() != btn_yes:
            return

        # Create progress dialog
        self.progress_dialog = QProgressDialog("Preparing to rename files...", "Cancel", 0, len(files), self)
        self.progress_dialog.setWindowTitle("Batch Rename Progress")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        self.progress_dialog.show()
        
        # Create and start worker thread
        self.rename_worker = RenameWorkerThread(files, pattern_func, self.db)
        self.rename_worker.progress_updated.connect(self._on_progress_updated)
        self.rename_worker.finished_signal.connect(self._on_rename_finished)
        self.progress_dialog.canceled.connect(self._on_progress_canceled)
        
        self.rename_btn.setEnabled(False)
        self.undo_btn.setEnabled(False)
        
        self.rename_worker.start()

    def _on_progress_updated(self, current, status_text):
        if hasattr(self, 'progress_dialog') and self.progress_dialog is not None:
            try:
                self.progress_dialog.setValue(current)
                self.progress_dialog.setLabelText(status_text)
            except (AttributeError, RuntimeError):
                # Dialog may have been closed already
                pass

    def _on_progress_canceled(self):
        if hasattr(self, 'rename_worker') and self.rename_worker:
            self.rename_worker.terminate()
            self.rename_worker.wait()
        self._cleanup_progress()

    def _on_rename_finished(self, results, success_count, fail_count):
        self._cleanup_progress()
        
        self.table_widget.refresh_table()

        msg = f"Renaming completed.\nSuccess: {success_count}\nFailed: {fail_count}"
        if fail_count > 0:
            msg += "\nSome files could not be renamed. Check the table for details."
        
        mb = QMessageBox(self)
        mb.setWindowTitle("Batch Rename")
        mb.setIcon(QMessageBox.Information)
        mb.setText(msg)
        btn_ok = QPushButton("OK")
        btn_ok.setIcon(qta.icon('fa6s.xmark'))
        mb.addButton(btn_ok, QMessageBox.AcceptRole)
        mb.exec()

    def _cleanup_progress(self):
        self.rename_btn.setEnabled(True)
        self.undo_btn.setEnabled(True)
        
        if hasattr(self, 'progress_dialog') and self.progress_dialog is not None:
            try:
                self.progress_dialog.close()
            except (AttributeError, RuntimeError):
                pass
            self.progress_dialog = None

    def do_undo_rename(self):
        mode = self.combo_mode.currentText()
        if mode == "Rename All":
            # get_all_files() returns: (id, filepath, filename, title, description, tags, status, original_filename, file_prompt)
            all_files = self.db.get_all_files()
            files = [file_tuple[1] for file_tuple in all_files if file_tuple[1]]
        else:
            file_rows = []
            for row in range(self.table_widget.table.rowCount()):
                checkbox_item = self.table_widget.table.item(row, 0)
                if checkbox_item and checkbox_item.checkState() == Qt.Checked:
                    file_rows.append(row)
            if not file_rows:
                QMessageBox.information(self, "No Selection", "No rows checked for undo rename.")
                return

            files = []
            for row in file_rows:
                filepath_item = self.table_widget.table.item(row, 1)
                filepath = filepath_item.data(Qt.UserRole) if filepath_item else None
                if filepath:
                    files.append(filepath)

        if not files:
            mb = QMessageBox(self)
            mb.setWindowTitle("No Files")
            mb.setIcon(QMessageBox.Information)
            mb.setText("No files found to undo rename.")
            btn_ok = QPushButton("OK")
            btn_ok.setIcon(qta.icon('fa6s.xmark'))
            mb.addButton(btn_ok, QMessageBox.AcceptRole)
            mb.exec()
            return

        mb = QMessageBox(self)
        mb.setWindowTitle("Confirm Undo Rename")
        mb.setIcon(QMessageBox.Question)
        mb.setText(f"Are you sure you want to undo rename for {len(files)} files? This will restore their original filenames if possible.")
        btn_yes = QPushButton("Yes")
        btn_yes.setIcon(qta.icon('fa6s.check'))
        btn_no = QPushButton("No")
        btn_no.setIcon(qta.icon('fa6s.xmark'))
        mb.addButton(btn_yes, QMessageBox.AcceptRole)
        mb.addButton(btn_no, QMessageBox.RejectRole)
        mb.exec()
        if mb.clickedButton() != btn_yes:
            return

        self.undo_progress_dialog = QProgressDialog("Preparing to undo rename...", "Cancel", 0, len(files), self)
        self.undo_progress_dialog.setWindowTitle("Undo Rename Progress")
        self.undo_progress_dialog.setWindowModality(Qt.WindowModal)
        self.undo_progress_dialog.setMinimumDuration(0)
        self.undo_progress_dialog.setValue(0)
        self.undo_progress_dialog.show()
        
        self.undo_worker = UndoRenameWorkerThread(files, self.db)
        self.undo_worker.progress_updated.connect(self._on_undo_progress_updated)
        self.undo_worker.finished_signal.connect(self._on_undo_finished)
        self.undo_progress_dialog.canceled.connect(self._on_undo_progress_canceled)
        
        self.rename_btn.setEnabled(False)
        self.undo_btn.setEnabled(False)
        
        self.undo_worker.start()

    def _on_undo_progress_updated(self, current, status_text):
        if hasattr(self, 'undo_progress_dialog') and self.undo_progress_dialog is not None:
            try:
                self.undo_progress_dialog.setValue(current)
                self.undo_progress_dialog.setLabelText(status_text)
            except (AttributeError, RuntimeError):
                # Dialog may have been closed already
                pass

    def _on_undo_progress_canceled(self):
        if hasattr(self, 'undo_worker') and self.undo_worker:
            self.undo_worker.terminate()
            self.undo_worker.wait()
        self._cleanup_undo_progress()

    def _on_undo_finished(self, success_count, fail_count):
        self._cleanup_undo_progress()
        
        self.table_widget.refresh_table()

        msg = f"Undo rename completed.\nSuccess: {success_count}\nFailed: {fail_count}"
        if fail_count > 0:
            msg += "\nSome files could not be restored. Check the table for details."
        
        mb = QMessageBox(self)
        mb.setWindowTitle("Undo Rename")
        mb.setIcon(QMessageBox.Information)
        mb.setText(msg)
        btn_ok = QPushButton("OK")
        btn_ok.setIcon(qta.icon('fa6s.xmark'))
        mb.addButton(btn_ok, QMessageBox.AcceptRole)
        mb.exec()

    def _cleanup_undo_progress(self):
        self.rename_btn.setEnabled(True)
        self.undo_btn.setEnabled(True)
        
        if hasattr(self, 'undo_progress_dialog') and self.undo_progress_dialog is not None:
            try:
                self.undo_progress_dialog.close()
            except (AttributeError, RuntimeError):
                pass
            self.undo_progress_dialog = None