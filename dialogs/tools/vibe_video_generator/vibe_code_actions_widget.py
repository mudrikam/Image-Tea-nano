from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton, QComboBox, QLabel, QMessageBox, QApplication
from PySide6.QtCore import Qt, QThread, Signal
import qtawesome as qta
from ui.theme_system import theme
from helpers.remotion_helper.remotion_helper import render_video as remotion_render_video


class RenderWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(bool, str)

    def __init__(self, script_content, output_path, render_settings):
        super().__init__()
        self.script_content = script_content
        self.output_path = output_path
        self.render_settings = render_settings

    def run(self):
        success, message = remotion_render_video(
            self.script_content,
            self.output_path,
            self.render_settings,
            lambda pct, msg: self.progress.emit(pct, msg) if pct is not None else None
        )
        self.finished.emit(success, message)


class CodeActionsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._render_settings_tab = None
        self._scripts_widget = None
        self._output_tab_widget = None
        self._updating_from_render = False
        self._updating_from_actions = False
        self._render_worker = None
        self._setup_ui()

    def set_render_settings_tab(self, render_settings_tab):
        self._render_settings_tab = render_settings_tab
        if self._render_settings_tab:
            self._render_settings_tab.settings_changed.connect(self._on_render_settings_changed)
            self._populate_preset_combo()
            self._sync_preset_combo()

    def set_scripts_widget(self, scripts_widget):
        self._scripts_widget = scripts_widget

    def set_output_tab_widget(self, output_tab_widget):
        self._output_tab_widget = output_tab_widget

    def _on_render_settings_changed(self):
        self._sync_preset_combo()

    def _populate_preset_combo(self):
        if self._render_settings_tab:
            self.preset_combo.clear()
            for i in range(self._render_settings_tab.preset_combo.count()):
                text = self._render_settings_tab.preset_combo.itemText(i)
                data = self._render_settings_tab.preset_combo.itemData(i)
                self.preset_combo.addItem(text, data)

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

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setContentsMargins(0, 0, 0, 0)
        self.actions_tab = QWidget()
        self._setup_actions_tab()
        self.tabs.addTab(self.actions_tab, 'Actions')
        layout.addWidget(self.tabs)

    def _setup_actions_tab(self):
        layout = QVBoxLayout(self.actions_tab)
        layout.setContentsMargins(4, 4, 4, 4)

        main_row = QHBoxLayout()
        main_row.setSpacing(12)

        preset_layout = QHBoxLayout()
        preset_layout.setSpacing(8)
        preset_layout.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_layout.addWidget(self.preset_combo, 1)

        main_row.addLayout(preset_layout, 1)

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
        main_row.addWidget(self.render_btn)
        self.render_btn.clicked.connect(self._on_render_clicked)

        layout.addLayout(main_row)

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

        # Overwrite setting from output tab takes precedence
        render_settings['overwrite'] = self._output_tab_widget.overwrite_checkbox.isChecked()

        # Disable button during render
        self.render_btn.setEnabled(False)
        self.render_btn.setText('Rendering...')

        # Start worker thread
        self._render_worker = RenderWorker(script_content, output_path, render_settings)
        self._render_worker.progress.connect(self._on_render_progress)
        self._render_worker.finished.connect(lambda success, msg: self._on_render_finished(success, msg))
        self._render_worker.start()

    def _on_render_progress(self, percentage, message):
        if percentage is not None:
            self.render_btn.setText(f'Rendering: {percentage}%')
        else:
            self.render_btn.setText(message[:50] + '...' if len(message) > 50 else message)

    def _on_render_finished(self, success, message):
        self.render_btn.setEnabled(True)
        self.render_btn.setText('Render Video')

        if success:
            QMessageBox.information(self, 'Render Complete', message)
        else:
            QMessageBox.critical(self, 'Render Failed', message)
