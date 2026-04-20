import os
import threading
import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QComboBox, QLabel, QMessageBox,
    QApplication, QLineEdit, QProgressBar,
    QFileDialog, QDialog, QTextEdit, QSpinBox,
    QScrollArea, QFrame, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
import qtawesome as qta

# Script fixer worker (refactored to helpers/remotion_helper)
from helpers.remotion_helper.script_fixer import ScriptFixWorker

# Other imports
from ui.theme_system import theme
from helpers.remotion_helper.remotion_helper import render_video as remotion_render_video
from dialogs.tools.vibe_video_generator.vibe_render_queue_widget import RenderQueueWidget
from dialogs.tools.vibe_video_generator.vibe_video_output_tab import sanitize_filename
from dialogs.tools.vibe_video_generator.batch_render_worker import BatchRenderWorker


class RenderCompleteDialog(QDialog):
    def __init__(self, parent, message, output_path):
        super().__init__(parent)
        import os

        self.output_path = output_path
        self.setWindowTitle('Render Complete')
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)

        output_exists = bool(output_path and os.path.exists(output_path))
        if output_exists:
            main_message = 'Video rendered successfully.'
        elif output_path:
            main_message = 'Render finished, but the output file was not found at the expected location.'
        else:
            main_message = message.strip() or 'Render finished.'

        icon_row = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa6s.circle-info', color='#4fa3e0').pixmap(32, 32))
        icon_row.addWidget(icon_label)
        icon_row.addSpacing(8)
        msg_label = QLabel(main_message)
        msg_label.setWordWrap(True)
        icon_row.addWidget(msg_label, 1)
        layout.addLayout(icon_row)

        details = []
        if output_path:
            normalized_path = os.path.normpath(output_path)
            details.append(f"<b>File:</b> {os.path.basename(normalized_path)}")
            details.append(f"<b>Folder:</b> {os.path.dirname(normalized_path)}")
            if output_exists:
                try:
                    file_size = os.path.getsize(output_path) / 1024 / 1024
                    details.append(f"<b>Size:</b> {file_size:.1f} MB")
                except Exception:
                    pass
            else:
                details.append(f"<b>Expected path:</b> {normalized_path}")
        elif message.strip():
            details.append(message.strip().replace('\n', '<br>'))

        if details:
            details_label = QLabel('<br>'.join(details))
            details_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            details_label.setWordWrap(True)
            # Use default text color (no custom stylesheet)
            layout.addWidget(details_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        open_btn = QPushButton('Open File Location')
        open_btn.setIcon(qta.icon('fa6s.folder-open'))
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setEnabled(bool(output_path))
        open_btn.clicked.connect(self._open_location)
        btn_row.addWidget(open_btn)
        ok_btn = QPushButton('OK')
        ok_btn.setIcon(qta.icon('fa6s.check'))
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def _open_location(self):
        import os
        import subprocess
        import platform
        path = self.output_path
        if not path:
            self.accept()
            return
        # Resolve to absolute file path then get folder
        abs_path = os.path.abspath(path)
        folder = os.path.dirname(abs_path)
        if not folder:
            folder = os.path.dirname(abs_path)  # fallback, shouldn't happen
        if platform.system() == 'Windows':
            subprocess.Popen(['explorer', folder])
        elif platform.system() == 'Darwin':
            subprocess.Popen(['open', folder])
        else:
            subprocess.Popen(['xdg-open', folder])
        self.accept()

    # Removed duplicate _open_location - see RenderCompleteDialog below


class RenderErrorDialog(QDialog):
    fix_requested = Signal()

    def __init__(self, parent, message, has_ai, retry_mode=False):
        super().__init__(parent)
        self.setWindowTitle('Render Failed')
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)

        icon_row = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa6s.circle-xmark', color='#e05555').pixmap(32, 32))
        icon_row.addWidget(icon_label)
        icon_row.addSpacing(8)
        title = QLabel('AI fix failed. Try again?' if retry_mode else 'Render failed. See details below.')
        icon_row.addWidget(title, 1)
        layout.addLayout(icon_row)

        self.error_text = QTextEdit()
        self.error_text.setReadOnly(True)
        self.error_text.setPlainText(message)
        self.error_text.setMinimumHeight(160)
        layout.addWidget(self.error_text)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        if has_ai:
            self.fix_btn = QPushButton('Try Again' if retry_mode else 'Fix Errors')
            self.fix_btn.setIcon(qta.icon('fa6s.wand-magic-sparkles'))
            self.fix_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.fix_btn.clicked.connect(self._on_fix)
            btn_row.addWidget(self.fix_btn)
        ok_btn = QPushButton('OK')
        ok_btn.setIcon(qta.icon('fa6s.check'))
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def _on_fix(self):
        self.fix_requested.emit()
        self.accept()


class BatchRenderSummaryDialog(QDialog):
    """Dialog showing batch render results with detailed breakdown."""
    
    def __init__(self, parent, stats, results):
        """
        Args:
            parent: parent widget
            stats: dict with total, completed, failed, cancelled
            results: list of result dicts, each with keys:
                script_id, name, collection, success, message, duration, output_path
        """
        super().__init__(parent)
        self.setWindowTitle('Batch Render Complete')
        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        layout = QVBoxLayout(self)

        # Summary stats
        stats_row = QHBoxLayout()
        primary_color = theme.get_color('primary')
        success_color = theme.get_color('success')
        error_color = theme.get_color('error')
        cancelled_color = theme.get_color('gray')

        total_box = self._create_stat_box('Total', str(stats['total']), primary_color)
        completed_box = self._create_stat_box('Completed', str(stats['completed']), success_color)
        failed_box = self._create_stat_box('Failed', str(stats['failed']), error_color)
        if stats.get('cancelled', 0) > 0:
            cancelled_box = self._create_stat_box('Cancelled', str(stats['cancelled']), cancelled_color)
            stats_row.addWidget(cancelled_box)

        stats_row.addWidget(total_box)
        stats_row.addWidget(completed_box)
        stats_row.addWidget(failed_box)
        layout.addLayout(stats_row)

        # Detailed table
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(['Script', 'Status', 'Output/Error', 'Duration'])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        table.setRowCount(len(results))
        for row, res in enumerate(results):
            # Script name
            script_display = f"{res.get('collection','')} / {res.get('name','')}" if res.get('collection') else res.get('name','')
            table.setItem(row, 0, QTableWidgetItem(script_display))
            # Status with color
            is_success = res['success']
            is_cancelled = res.get('message') == 'Render cancelled.'
            status_text = 'OK' if is_success else ('Cancelled' if is_cancelled else 'Failed')
            status_item = QTableWidgetItem(status_text)
            if is_success:
                status_item.setForeground(QColor(theme.get_color('success')))
            elif is_cancelled:
                status_item.setForeground(QColor(theme.get_color('gray')))
            else:
                status_item.setForeground(QColor(theme.get_color('error')))
            table.setItem(row, 1, status_item)
            # Output/Error
            if res['success'] and res.get('output_path'):
                import os
                table.setItem(row, 2, QTableWidgetItem(os.path.basename(res['output_path'])))
            elif not res['success']:
                err = res.get('message','')[:100]
                table.setItem(row, 2, QTableWidgetItem(err))
            else:
                table.setItem(row, 2, QTableWidgetItem(''))
            # Duration (in seconds)
            dur_sec = res.get('duration', 0)
            if dur_sec and dur_sec > 0:
                # Format as MM:SS or seconds
                if dur_sec >= 60:
                    minutes = int(dur_sec // 60)
                    seconds = dur_sec % 60
                    dur_text = f"{minutes}m {seconds:.0f}s"
                else:
                    dur_text = f"{dur_sec:.1f}s"
                table.setItem(row, 3, QTableWidgetItem(dur_text))
            else:
                table.setItem(row, 3, QTableWidgetItem('-'))

        layout.addWidget(table)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        copy_btn = QPushButton('Copy Report')
        copy_btn.setIcon(qta.icon('fa6s.copy'))
        copy_btn.clicked.connect(lambda: self._copy_report(stats, results))
        btn_row.addWidget(copy_btn)
        close_btn = QPushButton('Close')
        close_btn.setIcon(qta.icon('fa6s.check'))
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _create_stat_box(self, label, value, color):
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(8, 8, 8, 8)
        lbl = QLabel(label)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f'font-size: 11px; color: {theme.get_color("gray")};')
        val = QLabel(value)
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val.setStyleSheet(f'font-size: 18px; font-weight: bold; color: {color};')
        v.addWidget(lbl)
        v.addWidget(val)
        return box

    def _copy_report(self, stats, results):
        """Copy a text summary of the batch render to clipboard."""
        lines = []
        lines.append('=== Batch Render Report ===')
        lines.append(f"Total: {stats['total']}  Completed: {stats['completed']}  Failed: {stats['failed']}  Cancelled: {stats.get('cancelled',0)}")
        lines.append('')
        for res in results:
            status = 'OK' if res['success'] else ('Cancelled' if res.get('message') == 'Render cancelled.' else 'FAIL')
            script_full = f"{res.get('collection','')} / {res.get('name','')}" if res.get('collection') else res.get('name','')
            if res['success'] and res.get('output_path'):
                import os
                path = res['output_path']
                lines.append(f"[OK]   {script_full}\n      Output: {path}")
            elif not res['success']:
                err = res.get('message','')[:100]
                lines.append(f"[FAIL] {script_full}\n      Error: {err}")
            else:
                lines.append(f"[{status}] {script_full}")
        report = '\n'.join(lines)
        QApplication.clipboard().setText(report)
        QMessageBox.information(self, 'Copied', 'Report copied to clipboard.')


class RenderWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(bool, str)

    def __init__(self, script_content, output_path, render_settings):
        super().__init__()
        self.script_content = script_content
        self.output_path = output_path
        self.render_settings = render_settings
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def _on_progress(self, pct, msg):
        if pct is not None:
            self.progress.emit(pct, msg)
        else:
            self.progress.emit(-1, msg)

    def run(self):
        success, message = remotion_render_video(
            self.script_content,
            self.output_path,
            self.render_settings,
            self._on_progress,
            self._cancel_event
        )
        self.finished.emit(success, message)


class CodeActionsWidget(QWidget):
    rendering_started = Signal()
    rendering_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._render_settings_tab = None
        self._scripts_widget = None
        self._output_tab_widget = None
        self._updating_from_render = False
        self._updating_from_actions = False
        self._last_populate_count = 0  # track Action combo item count for smart repopulation
        self._render_worker = None
        self._batch_render_worker = None
        self._fix_worker = None
        self._ai_key = ''
        self._ai_endpoint = ''
        self._ai_service = ''
        self._ai_model = ''
        self._last_error_msg = ''
        self._is_rendering = False
        self._batch_render_active = False
        self._current_rendering_script_id = None
        self._batch_total = 0
        self._batch_current = 0
        self._batch_results = []
        self._batch_script_map = {}  # script_id -> {name, collection_name}
        self._render_queue_widget = None
        self._setup_ui()

    def set_render_settings_tab(self, render_settings_tab):
        self._render_settings_tab = render_settings_tab
        if self._render_settings_tab:
            self._render_settings_tab.settings_changed.connect(self._on_render_settings_changed)
            self._populate_preset_combo()
            self._sync_preset_combo()
            # Sync duration: seconds (Actions) -> frames (Render Settings)
            self._on_duration_changed()
            # Sync back: if user changes Render Settings duration directly
            self._render_settings_tab.duration_spin.valueChanged.connect(self._sync_duration_to_actions)

    def set_scripts_widget(self, scripts_widget):
        self._scripts_widget = scripts_widget
        if scripts_widget:
            scripts_widget.script_selected.connect(self._on_script_selected)

    def set_ai_credentials(self, api_key, endpoint, service, model):
        self._ai_key = api_key
        self._ai_endpoint = endpoint
        self._ai_service = service
        self._ai_model = model

    def _on_script_selected(self, name):
        if not name:
            return
        from dialogs.tools.vibe_video_generator.vibe_video_output_tab import sanitize_filename
        sanitized = sanitize_filename(name)
        self.filename_input.setText(sanitized)
        if self._output_tab_widget:
            self._output_tab_widget.set_output_filename(sanitized)

    def set_output_tab_widget(self, output_tab_widget):
        self._output_tab_widget = output_tab_widget
        if output_tab_widget:
            output_tab_widget.output_filename_changed.connect(self._on_output_filename_changed)
            output_tab_widget.output_path_changed.connect(self._on_output_path_changed)
            saved_filename = output_tab_widget.get_output_filename()
            saved_path = output_tab_widget.get_output_path()
            if saved_filename:
                self.filename_input.setText(saved_filename)
            if saved_path:
                self.folder_input.setText(saved_path)

    def enter_render_mode(self):
        """Called when rendering starts - disable UI controls but keep Cancel active."""
        # Disable output filename/folder inputs and browse button
        self.filename_input.setEnabled(False)
        self.folder_input.setEnabled(False)
        self.browse_btn.setEnabled(False)
        # Disable preset and duration controls
        if hasattr(self, 'preset_combo'):
            self.preset_combo.setEnabled(False)
        if hasattr(self, 'duration_seconds_spin'):
            self.duration_seconds_spin.setEnabled(False)
        # Note: render button stays enabled (becomes Cancel)
        # Other action buttons (Refine/Clear/Save) are in ScriptsWidget; handled by parent

    def exit_render_mode(self):
        """Called when rendering finishes - re-enable UI controls."""
        self.filename_input.setEnabled(True)
        self.folder_input.setEnabled(True)
        self.browse_btn.setEnabled(True)
        if hasattr(self, 'preset_combo'):
            self.preset_combo.setEnabled(True)
        if hasattr(self, 'duration_seconds_spin'):
            self.duration_seconds_spin.setEnabled(True)

    def _on_duration_changed(self):
        if not self._render_settings_tab:
            return
        # Both spinners now use seconds; direct copy
        self._render_settings_tab.duration_spin.blockSignals(True)
        self._render_settings_tab.duration_spin.setValue(self.duration_seconds_spin.value())
        self._render_settings_tab.duration_spin.blockSignals(False)

    def _sync_duration_to_actions(self):
        """Render Settings duration (seconds) -> Actions duration (seconds)."""
        if not self._render_settings_tab:
            return
        self.duration_seconds_spin.blockSignals(True)
        self.duration_seconds_spin.setValue(self._render_settings_tab.duration_spin.value())
        self.duration_seconds_spin.blockSignals(False)

    def _on_render_settings_changed(self):
        # Repopulate only if the Render combo's item count changed (e.g., custom preset added/removed)
        current_count = self._render_settings_tab.preset_combo.count() if self._render_settings_tab else 0
        if current_count != self._last_populate_count:
            self._populate_preset_combo()
        self._sync_preset_combo()

    def _populate_preset_combo(self):
        if self._render_settings_tab:
            self.preset_combo.blockSignals(True)
            self.preset_combo.clear()
            for i in range(self._render_settings_tab.preset_combo.count()):
                text = self._render_settings_tab.preset_combo.itemText(i)
                data = self._render_settings_tab.preset_combo.itemData(i)
                self.preset_combo.addItem(text, data)
            self.preset_combo.blockSignals(False)
            self._last_populate_count = self.preset_combo.count()

    def _sync_preset_combo(self):
        if self._render_settings_tab and hasattr(self, 'preset_combo'):
            current_render_preset = self._render_settings_tab.preset_combo.currentData()
            if current_render_preset and not self._updating_from_actions:
                self._updating_from_render = True
                idx = self.preset_combo.findData(current_render_preset)
                if idx >= 0:
                    self.preset_combo.setCurrentIndex(idx)
                self._updating_from_render = False

    def _on_preset_changed(self, index):
        if self._updating_from_render or self._render_settings_tab is None:
            return
        preset_key = self.preset_combo.currentData()
        if preset_key:
            self._updating_from_actions = True
            self._render_settings_tab.preset_combo.setCurrentIndex(
                self._render_settings_tab.preset_combo.findData(preset_key)
            )
            self._updating_from_actions = False
            # Re-sync duration because FPS may have changed
            self._on_duration_changed()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setContentsMargins(0, 0, 0, 0)
        self.render_tab = QWidget()
        self._setup_render_tab()
        self.tabs.addTab(self.render_tab, qta.icon('fa6s.circle', color=theme.get_color('error')), 'Render')
        self.queue_tab = QWidget()
        self._setup_queue_tab()
        self.tabs.addTab(self.queue_tab, qta.icon('fa6s.list-ul'), 'Render Queue')
        layout.addWidget(self.tabs)

    def _setup_render_tab(self):
        layout = QVBoxLayout(self.render_tab)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        single_row = QHBoxLayout()
        single_row.setSpacing(8)

        single_row.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        single_row.addWidget(self.preset_combo, 2)

        single_row.addWidget(QLabel("Duration:"))
        self.duration_seconds_spin = QSpinBox()
        self.duration_seconds_spin.setRange(1, 3600)
        self.duration_seconds_spin.setValue(5)
        self.duration_seconds_spin.setSuffix(" s")
        self.duration_seconds_spin.setToolTip('Output duration in seconds. Overrides the duration defined in the script.')
        self.duration_seconds_spin.valueChanged.connect(self._on_duration_changed)
        single_row.addWidget(self.duration_seconds_spin, 1)

        single_row.addWidget(QLabel("Filename:"))
        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText('e.g., my_video')
        self.filename_input.editingFinished.connect(self._on_actions_filename_edited)
        single_row.addWidget(self.filename_input, 2)

        single_row.addWidget(QLabel("Output:"))
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText('Select output folder...')
        self.folder_input.editingFinished.connect(self._on_actions_folder_edited)
        single_row.addWidget(self.folder_input, 3)
        self.browse_btn = QPushButton()
        self.browse_btn.setIcon(qta.icon('fa6s.folder-open'))
        self.browse_btn.setMaximumWidth(32)
        self.browse_btn.setToolTip('Browse folder')
        self.browse_btn.clicked.connect(self._on_actions_browse)
        single_row.addWidget(self.browse_btn)

        layout.addLayout(single_row)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(6)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat('Ready')
        bottom_row.addWidget(self.progress_bar, 1)

        self.render_btn = QPushButton('Render Video')
        self.render_btn.setMinimumHeight(40)
        self.render_btn.setMinimumWidth(220)
        self.render_btn.setIcon(qta.icon('fa6s.film', color=theme.get_color('white')))
        self.render_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.render_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.get_color('primary')};
                color: {theme.get_color('white')};
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {theme.get_color('primary_hover')};
            }}
            QPushButton:pressed {{
                background-color: {theme.get_color('primary_pressed')};
            }}
        """)
        self.render_btn.clicked.connect(self._on_render_clicked)
        bottom_row.addWidget(self.render_btn)

        layout.addLayout(bottom_row)

        # AI Fix Log panel (initially hidden, shown during fix)
        self.ai_log_group = QGroupBox("AI Fix Log")
        self.ai_log_group.setVisible(False)
        log_layout = QVBoxLayout(self.ai_log_group)
        log_layout.setContentsMargins(8, 8, 8, 8)
        log_layout.setSpacing(4)

        self.ai_log_label = QLabel()
        self.ai_log_label.setWordWrap(True)
        self.ai_log_label.setMaximumHeight(200)
        self.ai_log_label.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas; font-size: 9pt; padding: 4px;")
        self.ai_log_label.setText("")
        self.ai_log_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        log_layout.addWidget(self.ai_log_label)

        layout.addWidget(self.ai_log_group)
        layout.addStretch()

    def _setup_queue_tab(self):
        layout = QVBoxLayout(self.queue_tab)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self._render_queue_widget = RenderQueueWidget()
        layout.addWidget(self._render_queue_widget)

    def _on_actions_filename_edited(self):
        if self._output_tab_widget:
            self._output_tab_widget.set_output_filename(self.filename_input.text().strip())
            self.filename_input.setText(self._output_tab_widget.get_output_filename())

    def _on_actions_folder_edited(self):
        if self._output_tab_widget:
            self._output_tab_widget.set_output_path(self.folder_input.text().strip())

    def _on_actions_browse(self):
        import os
        current = self.folder_input.text()
        start_dir = current if current else os.path.expanduser('~')
        folder = QFileDialog.getExistingDirectory(self, 'Select Output Folder', start_dir)
        if folder:
            self.folder_input.setText(folder)
            if self._output_tab_widget:
                self._output_tab_widget.set_output_path(folder)

    def _on_output_filename_changed(self, name):
        self.filename_input.setText(name)

    def _on_output_path_changed(self, path):
        self.folder_input.setText(path)

    def _on_render_clicked(self):
        # Validate required widgets
        if not self._scripts_widget or not self._output_tab_widget or not self._render_settings_tab:
            QMessageBox.warning(self, 'Error', 'Required components not initialized.')
            return

        # Get current script content
        script_content = self._scripts_widget.script_content.toPlainText()
        if not script_content.strip():
            QMessageBox.warning(self, 'Validation Error', 'No script loaded or script is empty.')
            return

        # Validate output settings
        if not self._output_tab_widget.validate():
            w = self._output_tab_widget.parent()
            while w and not isinstance(w, QTabWidget):
                w = w.parent()
            if w:
                w.setCurrentWidget(self._output_tab_widget)
            return

        output_path = self._output_tab_widget.get_full_output_path()
        if not output_path:
            QMessageBox.warning(self, 'Validation Error', 'Output path or filename is empty.')
            return

        # Get all render settings
        if hasattr(self._render_settings_tab, 'get_all_render_settings'):
            render_settings = self._render_settings_tab.get_all_render_settings()
        else:
            render_settings = {}

        # Override duration (in seconds) from the Actions tab spinner
        render_settings['duration'] = self.duration_seconds_spin.value()

        # Overwrite setting from output tab takes precedence
        render_settings['overwrite'] = self._output_tab_widget.overwrite_checkbox.isChecked()

        # Disable button during render
        self._render_worker = RenderWorker(script_content, output_path, render_settings)
        self._is_rendering = True
        self.rendering_started.emit()
        self.render_btn.setEnabled(True)
        self.render_btn.setText('Cancel')
        self.render_btn.setIcon(qta.icon('fa6s.stop', color=theme.get_color('white')))
        _err_q = QColor(theme.get_color('error'))
        _err_rgb = f"{_err_q.red()},{_err_q.green()},{_err_q.blue()}"
        self.render_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba({_err_rgb},0.3);
                color: {theme.get_color('white')};
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: rgba({_err_rgb},0.5);
            }}
            QPushButton:pressed {{
                background-color: rgba({_err_rgb},0.7);
            }}
        """)
        self.render_btn.clicked.disconnect()
        self.render_btn.clicked.connect(self._on_cancel_clicked)
        self.progress_bar.setValue(0)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFormat('Starting...')
        self._render_worker.progress.connect(self._on_render_progress)
        self._render_worker.finished.connect(lambda success, msg: self._on_render_finished(success, msg))
        self._render_worker.start()

    def _on_cancel_clicked(self):
        if self._batch_render_active and self._batch_render_worker:
            self._batch_render_worker.cancel()
            self.render_btn.setEnabled(False)
            self.progress_bar.setFormat('Cancelling batch...')
        elif self._render_worker:
            self._render_worker.cancel()
            self.render_btn.setEnabled(False)
            self.progress_bar.setFormat('Cancelling...')

    def _restore_render_btn(self):
        self._is_rendering = False
        self._batch_render_active = False
        self._current_rendering_script_id = None
        self.rendering_finished.emit()
        # Restore render button
        self.render_btn.setEnabled(True)
        self.render_btn.setText('Render Video')
        self.render_btn.setIcon(qta.icon('fa6s.film', color=theme.get_color('white')))
        self.render_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.get_color('primary')};
                color: {theme.get_color('white')};
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {theme.get_color('primary_hover')};
            }}
            QPushButton:pressed {{
                background-color: {theme.get_color('primary_pressed')};
            }}
        """)
        self.render_btn.clicked.disconnect()
        self.render_btn.clicked.connect(self._on_render_clicked)
        # Reset progress bars
        self.progress_bar.setFormat('Ready')
        self.progress_bar.setValue(0)
        # Reset compact queue widget
        self._render_queue_widget.reset()

    def start_batch_render(self, collection_data):
        """Start batch rendering of a collection (recursive)."""
        if self._batch_render_active or self._is_rendering:
            QMessageBox.warning(self, 'Busy', 'A render is already in progress. Please wait or cancel first.')
            return

        if not self._scripts_widget or not self._output_tab_widget or not self._render_settings_tab:
            QMessageBox.warning(self, 'Error', 'Required components not initialized.')
            return

        collection_id = collection_data.get('id')
        collection_name = collection_data.get('name', 'Collection')

        if not collection_id:
            QMessageBox.warning(self, 'Error', 'Invalid collection.')
            return

        # Get all scripts recursively
        db = self._scripts_widget.db
        if not db:
            QMessageBox.warning(self, 'Error', 'Database not available.')
            return

        try:
            all_scripts = db.get_all_scripts_in_collection_tree(collection_id, active_only=True)
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to retrieve scripts:\n{str(e)}')
            return

        if not all_scripts:
            QMessageBox.information(self, 'No Scripts', 'This collection (and sub-collections) contain no active scripts.')
            return

        # Clear any previous batch data
        self._batch_results.clear()
        self._batch_script_map.clear()

        # Validate output folder
        base_folder = self._output_tab_widget.output_path_input.text().strip()
        if not base_folder:
            QMessageBox.warning(self, 'Validation Error', 'Output folder is empty.')
            w = self._output_tab_widget.parent()
            while w and not isinstance(w, QTabWidget):
                w = w.parent()
            if w:
                w.setCurrentWidget(self._output_tab_widget)
            return

        output_format = self._output_tab_widget.output_format_combo.currentText()
        overwrite = self._output_tab_widget.overwrite_checkbox.isChecked()

        # Get render settings ONCE and use for ALL scripts
        base_render_settings = self._render_settings_tab.get_all_render_settings()
        base_render_settings['duration'] = self.duration_seconds_spin.value()
        base_render_settings['overwrite'] = overwrite

        # Confirmation dialog before starting batch render
        preset_name = self._render_settings_tab.preset_combo.currentText()
        duration_sec = self.duration_seconds_spin.value()
        confirm_msg = (f"Render collection '{collection_name}' with {len(all_scripts)} script(s)?\n\n"
                       f"Settings: {preset_name}, Duration: {duration_sec}s, Format: {output_format}\n"
                       f"Output folder: {base_folder}\n\n"
                       f"All scripts will use the same settings.")
        reply = QMessageBox.question(
            self, 'Confirm Batch Render',
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Prepare queue
        scripts_queue = []
        sanitized_collection_name = sanitize_filename(collection_name)
        collection_folder = os.path.join(base_folder, sanitized_collection_name)
        os.makedirs(collection_folder, exist_ok=True)

        for idx, script in enumerate(all_scripts, 1):
            script_id = script.get('id')
            script_content = script.get('script_content', '')
            script_name = script.get('name', f'Script_{idx}')
            sanitized_script_name = sanitize_filename(script_name)
            filename = f"{idx:03d}_{sanitized_script_name}"
            output_path = os.path.join(collection_folder, f'{filename}.{output_format}')

            # Store mapping for UI display
            self._batch_script_map[script_id] = {
                'name': script_name,
                'collection_name': collection_name,
                'output_path': output_path
            }

            # IMPORTANT: Each script MUST get its own copy of settings
            # to prevent mutation from affecting subsequent scripts
            entry = {
                'script_id': script_id,
                'script_content': script_content,
                'script_name': script_name,
                'collection_name': collection_name,
                'output_path': output_path,
                'render_settings': base_render_settings.copy(),  # independent copy
            }
            scripts_queue.append(entry)

        # Initialize compact queue widget
        self._render_queue_widget.reset()
        self._render_queue_widget.set_queue_stats(len(scripts_queue), 0, 0, 0)

        # Initialize batch state
        self._batch_total = len(scripts_queue)
        self._batch_current = 0
        self._batch_render_active = True
        self._batch_results = []
        # _batch_script_map already filled in the loop - do NOT reset here

        # Switch to Render Queue tab
        self.tabs.setCurrentWidget(self.queue_tab)

        # Prepare UI
        self.enter_render_mode()
        self.rendering_started.emit()
        self._set_cancel_button_mode()
        self._render_queue_widget.set_queue_stats(self._batch_total, 0, 0, 0)

        # Create batch worker
        self._batch_render_worker = BatchRenderWorker(scripts_queue)
        self._batch_render_worker.script_started.connect(self._on_batch_script_started)
        self._batch_render_worker.script_progress.connect(self._on_batch_script_progress)
        self._batch_render_worker.script_finished.connect(self._on_batch_script_finished)
        self._batch_render_worker.queue_finished.connect(self._on_batch_queue_finished)
        self._batch_render_worker.start()

        # Overall progress bar shows count
        self.progress_bar.setRange(0, self._batch_total)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(f'Batch: 0/{self._batch_total}')

    def _set_cancel_button_mode(self):
        """Set render button to Cancel appearance."""
        self.render_btn.setEnabled(True)
        self.render_btn.setText('Cancel')
        self.render_btn.setIcon(qta.icon('fa6s.stop', color=theme.get_color('white')))
        _err_q = QColor(theme.get_color('error'))
        _err_rgb = f"{_err_q.red()},{_err_q.green()},{_err_q.blue()}"
        self.render_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba({_err_rgb},0.3);
                color: {theme.get_color('white')};
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: rgba({_err_rgb},0.5);
            }}
            QPushButton:pressed {{
                background-color: rgba({_err_rgb},0.7);
            }}
        """)
        self.render_btn.clicked.disconnect()
        self.render_btn.clicked.connect(self._on_cancel_clicked)

    def _set_cancel_button_mode(self):
        """Set render button to Cancel appearance."""
        self.render_btn.setEnabled(True)
        self.render_btn.setText('Cancel')
        self.render_btn.setIcon(qta.icon('fa6s.stop', color=theme.get_color('white')))
        _err_q = QColor(theme.get_color('error'))
        _err_rgb = f"{_err_q.red()},{_err_q.green()},{_err_q.blue()}"
        self.render_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba({_err_rgb},0.3);
                color: {theme.get_color('white')};
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: rgba({_err_rgb},0.5);
            }}
            QPushButton:pressed {{
                background-color: rgba({_err_rgb},0.7);
            }}
        """)
        self.render_btn.clicked.disconnect()
        self.render_btn.clicked.connect(self._on_cancel_clicked)

    def _on_batch_script_started(self, script_id):
        """Handle start of a single script in batch."""
        self._batch_current += 1
        self._current_rendering_script_id = script_id

        # Update overall progress bar
        self.progress_bar.setValue(self._batch_current)
        self.progress_bar.setFormat(f'Batch: {self._batch_current}/{self._batch_total}')

        # Get script info for display
        info = self._batch_script_map.get(script_id, {})
        script_name = info.get('name', f'Script {self._batch_current}')
        collection_name = info.get('collection_name', '')
        # Get the render settings that will be used for this script
        render_settings = self._render_settings_tab.get_all_render_settings()
        render_settings['duration'] = self.duration_seconds_spin.value()
        self._render_queue_widget.set_current_script(script_name, collection_name, render_settings)
        self._render_queue_widget.set_progress(0, "Starting...")

        # Load script into Scripts tab
        if self._scripts_widget:
            db = self._scripts_widget.db
            if db:
                script_data = db.get_remotion_script(script_id)
                if script_data:
                    self._scripts_widget.display_script(script_data)

        # Highlight in collections tree
        parent = self.parent()
        if parent and hasattr(parent, 'collections_widget'):
            parent.collections_widget.highlight_rendering_script(script_id)

    def _on_batch_script_progress(self, script_id, percentage, message):
        """Forward progress from current script to queue widget."""
        self._render_queue_widget.set_progress(percentage, message)

    def _on_batch_script_finished(self, script_id, success, message, duration):
        """Handle completion of a single script."""
        # Store result for summary
        info = self._batch_script_map.get(script_id, {})
        result = {
            'script_id': script_id,
            'name': info.get('name', 'Unknown'),
            'collection': info.get('collection_name', ''),
            'success': success,
            'message': message,
            'duration': duration,
            'output_path': info.get('output_path') if success else None
        }
        self._batch_results.append(result)

        # Update compact queue stats
        if success:
            self._render_queue_widget.on_script_completed()
        elif message == 'Render cancelled.':
            self._render_queue_widget.on_script_cancelled()
        else:
            self._render_queue_widget.on_script_failed()

    def _on_batch_queue_finished(self):
        """All scripts processed - show summary and cleanup."""
        self._batch_render_active = False
        # Compute stats from results
        total = len(self._batch_results)
        completed = sum(1 for r in self._batch_results if r['success'])
        failed = sum(1 for r in self._batch_results if not r['success'] and r['message'] != 'Render cancelled.')
        cancelled = sum(1 for r in self._batch_results if r['message'] == 'Render cancelled.')
        stats = {'total': total, 'completed': completed, 'failed': failed, 'cancelled': cancelled}
        self._show_batch_render_summary(stats)
        self._restore_render_btn()
        # Clear highlights
        parent = self.parent()
        if parent and hasattr(parent, 'collections_widget'):
            parent.collections_widget.clear_render_highlight()
        # Cleanup
        self._batch_results.clear()
        self._batch_script_map.clear()
        if self._batch_render_worker:
            self._batch_render_worker.wait(2000)
            self._batch_render_worker.deleteLater()
            self._batch_render_worker = None

    def _show_batch_render_summary(self, stats):
        """Display a dialog with batch render results."""
        dlg = BatchRenderSummaryDialog(self, stats, self._batch_results)
        dlg.exec()

    def _on_render_progress(self, percentage, message):
        if percentage >= 0:
            self.progress_bar.setValue(percentage)
            # Message already contains ETA from remotion helper; show it directly
            self.progress_bar.setFormat(f'{message}  ({percentage}%)')

    def _on_render_finished(self, success, message):
        self._restore_render_btn()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat('Ready')

        if message == 'Render cancelled.':
            return

        if success:
            output_path = self._output_tab_widget.get_full_output_path() if self._output_tab_widget else ''
            dlg = RenderCompleteDialog(self, message, output_path)
            dlg.exec()
        else:
            self._last_error_msg = message
            has_ai = bool(self._ai_key)
            dlg = RenderErrorDialog(self, message, has_ai)
            dlg.fix_requested.connect(self._on_fix_errors_requested)
            dlg.exec()

    def _on_fix_errors_requested(self):
        if not self._scripts_widget:
            return
        script_content = self._scripts_widget.script_content.toPlainText().strip()
        if not script_content:
            QMessageBox.warning(self, 'Error', 'No script loaded to fix.')
            return

        # Clear and show AI log panel
        self.ai_log_label.setText("")
        self.ai_log_group.setVisible(True)
        self._append_log("Starting AI fix...")

        self.render_btn.setEnabled(False)
        self.render_btn.setText('Fixing...')
        self.render_btn.setIcon(qta.icon('fa6s.spinner', animation=qta.Spin(self.render_btn)))
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat('AI is fixing the script...')

        self._fix_worker = ScriptFixWorker(
            self._ai_key, self._ai_endpoint, self._ai_service, self._ai_model,
            script_content, self._last_error_msg
        )
        # Connect progress signal for real-time logging
        self._fix_worker.progress.connect(self._on_fix_progress)
        self._fix_worker.finished.connect(self._on_fix_finished)
        self._fix_worker.start()

    def _on_fix_progress(self, message: str):
        """Handle progress updates from AI fix worker."""
        self._append_log(message)

    def _append_log(self, message: str):
        """Append a formatted message to the AI log panel."""
        from datetime import datetime
        timestamp = datetime.now().strftime('%H:%M:%S')
        entry = f"[{timestamp}] {message}"
        current = self.ai_log_label.text()
        if current:
            new_text = current + "\n" + entry
        else:
            new_text = entry
        # Limit to last 100 lines to prevent excessive growth
        lines = new_text.split('\n')
        if len(lines) > 100:
            new_text = '\n'.join(lines[-100:])
        self.ai_log_label.setText(new_text)

    def _on_fix_finished(self, success, result):
        worker = self._fix_worker
        self._fix_worker = None
        if worker:
            worker.quit()
            worker.wait(2000)
            worker.deleteLater()

        self._restore_render_btn()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat('Ready')

        if success:
            self._append_log("Fix completed successfully.")
        else:
            self._append_log(f"Fix failed: {result}")

        if not success:
            dlg = RenderErrorDialog(self, self._last_error_msg, has_ai=True, retry_mode=True)
            dlg.fix_requested.connect(self._on_fix_errors_requested)
            dlg.exec()
            return

        if not self._scripts_widget or not self._scripts_widget.db or not self._scripts_widget.current_script_id:
            QMessageBox.warning(self, 'Fix Complete', 'Script fixed but could not save - no script loaded.')
            return
        db = self._scripts_widget.db
        script_id = self._scripts_widget.current_script_id
        db.update_remotion_script(script_id=script_id, script_content=result)
        script_data = db.get_remotion_script(script_id)
        self._append_log(f"Script saved (id={script_id})")
        if script_data:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._apply_fixed_script(script_data))

    def _apply_fixed_script(self, script_data):
        if self._scripts_widget:
            self._scripts_widget.display_script(script_data)
            self._scripts_widget.script_updated.emit(script_data)
