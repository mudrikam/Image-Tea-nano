from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton, QComboBox, QLabel, QMessageBox, QApplication, QLineEdit, QProgressBar, QFileDialog, QDialog, QTextEdit
from PySide6.QtCore import Qt, QThread, Signal
import qtawesome as qta
from ui.theme_system import theme
from helpers.remotion_helper.remotion_helper import render_video as remotion_render_video


SCRIPT_FIX_SYSTEM = """You are a Remotion TypeScript/React error fixer. Fix the script based on the error given.

STRICT RULES:
1. Output ONLY the fixed TypeScript code - no markdown fences, no explanations, no comments about what you changed
2. Do NOT rewrite the whole script - make the MINIMAL change that fixes the error
3. Do NOT import Composition or registerRoot - these are handled externally
4. Export the component as a named export (e.g. export const MyComponent: React.FC = () => ...)
5. Do NOT use functions that don't exist in the imported Remotion version (e.g. cameraZoom is not a valid remotion export)
6. Check all imports - only import what actually exists in 'remotion': useCurrentFrame, useVideoConfig, interpolate, spring, Easing, Audio, Img, Video, AbsoluteFill, Sequence, useCurrentScale
7. interpolate() outputRange must contain ONLY numbers, never strings
8. interpolate() inputRange must be strictly increasing numbers
9. spring() returns a number, not an object
10. All inline styles must use camelCase (backgroundColor not background-color)
11. If the error says "X is not a function" or "X is not exported from remotion", remove that import and rewrite the affected code without it"""


class ScriptFixWorker(QThread):
    finished = Signal(bool, str)

    def __init__(self, api_key, endpoint, service, model, script_content, error_msg):
        super().__init__()
        self.api_key = api_key
        self.endpoint = endpoint
        self.service = service
        self.model = model
        self.script_content = script_content
        self.error_msg = error_msg

    def run(self):
        try:
            import os
            import json
            import re
            full_prompt = (SCRIPT_FIX_SYSTEM
                + "\n\nSCRIPT TO FIX:\n" + self.script_content
                + "\n\nERROR:\n" + self.error_msg)
            svc = (self.service or '').lower()
            endpoint = (self.endpoint or '').strip()
            text = ''
            if endpoint:
                from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
                text = CustomEndpointHelper.call_endpoint(self.api_key, endpoint, svc, self.model, full_prompt, timeout=120)
            elif svc == 'gemini':
                import google.genai as genai
                client = genai.Client(api_key=self.api_key)
                response = client.models.generate_content(model=self.model, contents=[full_prompt])
                text = response.text
            elif svc in ('openai', 'openrouter', 'maia', 'blackbox'):
                from openai import OpenAI
                config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'configs', 'ai_config.json')
                with open(config_path, 'r', encoding='utf-8') as f:
                    ai_config = json.load(f)
                base_url = ai_config['provider_endpoints'][svc]
                client = OpenAI(api_key=self.api_key, base_url=base_url)
                response = client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": full_prompt}])
                text = response.choices[0].message.content
            elif svc == 'groq':
                from groq import Groq
                client = Groq(api_key=self.api_key)
                response = client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": full_prompt}])
                text = response.choices[0].message.content
            else:
                self.finished.emit(False, f"Unsupported service: {svc}")
                return
            code = self._extract_code(text)
            self.finished.emit(True, code)
        except Exception as e:
            print(f"[Vibe Video] Script fix error: {e}")
            self.finished.emit(False, str(e))

    def _extract_code(self, text):
        import re
        for pattern in [r'```(?:tsx?|typescript|javascript)\s*\n(.*?)```', r'```\s*\n(.*?)```']:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1).strip()
        stripped = text.strip()
        if 'import' in stripped and ('React' in stripped or 'remotion' in stripped):
            return stripped
        return text.strip()


class RenderCompleteDialog(QDialog):
    def __init__(self, parent, message, output_path):
        super().__init__(parent)
        self.output_path = output_path
        self.setWindowTitle('Render Complete')
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)

        icon_row = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa6s.circle-info', color='#4fa3e0').pixmap(32, 32))
        icon_row.addWidget(icon_label)
        icon_row.addSpacing(8)
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        icon_row.addWidget(msg_label, 1)
        layout.addLayout(icon_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        open_btn = QPushButton('Open File Location')
        open_btn.setIcon(qta.icon('fa6s.folder-open'))
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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
            return
        folder = os.path.dirname(path)
        if platform.system() == 'Windows':
            subprocess.Popen(['explorer', '/select,', os.path.normpath(path)])
        elif platform.system() == 'Darwin':
            subprocess.Popen(['open', '-R', path])
        else:
            subprocess.Popen(['xdg-open', folder])


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


class RenderWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(bool, str)

    def __init__(self, script_content, output_path, render_settings):
        super().__init__()
        self.script_content = script_content
        self.output_path = output_path
        self.render_settings = render_settings

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
            self._on_progress
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
        self._fix_worker = None
        self._ai_key = ''
        self._ai_endpoint = ''
        self._ai_service = ''
        self._ai_model = ''
        self._last_error_msg = ''
        self._setup_ui()

    def set_render_settings_tab(self, render_settings_tab):
        self._render_settings_tab = render_settings_tab
        if self._render_settings_tab:
            self._render_settings_tab.settings_changed.connect(self._on_render_settings_changed)
            self._populate_preset_combo()
            self._sync_preset_combo()

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
        layout.setSpacing(4)

        single_row = QHBoxLayout()
        single_row.setSpacing(8)

        single_row.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        single_row.addWidget(self.preset_combo, 2)

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

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat('%p%')
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

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
        layout.addWidget(self.render_btn)

    def _on_actions_filename_edited(self):
        if self._output_tab_widget:
            self._output_tab_widget.set_output_filename(self.filename_input.text().strip())
            self.filename_input.setText(self._output_tab_widget.get_output_filename())

    def _on_actions_folder_edited(self):
        if self._output_tab_widget:
            self._output_tab_widget.set_output_path(self.folder_input.text().strip())

    def _on_actions_browse(self):
        current = self.folder_input.text()
        folder = QFileDialog.getExistingDirectory(self, 'Select Output Folder', current)
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

        # Overwrite setting from output tab takes precedence
        render_settings['overwrite'] = self._output_tab_widget.overwrite_checkbox.isChecked()

        # Disable button during render
        self.render_btn.setEnabled(False)
        self.render_btn.setText('Rendering...')
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat('%p%')
        self.progress_bar.setVisible(True)

        # Start worker thread
        self._render_worker = RenderWorker(script_content, output_path, render_settings)
        self._render_worker.progress.connect(self._on_render_progress)
        self._render_worker.finished.connect(lambda success, msg: self._on_render_finished(success, msg))
        self._render_worker.start()

    def _on_render_progress(self, percentage, message):
        if percentage >= 0:
            self.progress_bar.setValue(percentage)
            self.progress_bar.setFormat(f'{message}  ({percentage}%)')

    def _on_render_finished(self, success, message):
        self.render_btn.setEnabled(True)
        self.render_btn.setText('Render Video')
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)

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
        self.render_btn.setEnabled(False)
        self.render_btn.setText('Fixing...')
        self.render_btn.setIcon(qta.icon('fa6s.spinner', animation=qta.Spin(self.render_btn)))
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat('AI is fixing the script...')
        self.progress_bar.setVisible(True)
        self._fix_worker = ScriptFixWorker(
            self._ai_key, self._ai_endpoint, self._ai_service, self._ai_model,
            script_content, self._last_error_msg
        )
        self._fix_worker.finished.connect(self._on_fix_finished)
        self._fix_worker.start()

    def _on_fix_finished(self, success, result):
        self.render_btn.setEnabled(True)
        self.render_btn.setText('Render Video')
        self.render_btn.setIcon(qta.icon('fa6s.film', color=theme.get_color('white')))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        if not success:
            print(f'[Vibe Video] Fix failed: {result}')
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
        if script_data:
            self._scripts_widget.display_script(script_data)
            self._scripts_widget.script_updated.emit(script_data)
        print(f'[Vibe Video] Script fixed and saved (id={script_id})')
