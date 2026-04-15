from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton, QComboBox, QLabel, QMessageBox, QApplication, QLineEdit, QProgressBar, QFileDialog, QDialog, QTextEdit, QSpinBox
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
import threading
import qtawesome as qta
from ui.theme_system import theme
from helpers.remotion_helper.remotion_helper import render_video as remotion_render_video


SCRIPT_FIX_SYSTEM = """You are a Remotion TypeScript/React error fixer. Fix the script based on the error given.

OUTPUT FORMAT - Use SEARCH/REPLACE blocks to show ONLY the parts that need changing:

<<<SEARCH
exact lines from the original script that need to change
===
replacement lines
>>>REPLACE

You can output multiple SEARCH/REPLACE blocks. Each SEARCH section must exactly match lines in the original script (whitespace-sensitive).

STRICT RULES:
1. Use SEARCH/REPLACE blocks - do NOT output the full script
2. SEARCH content must be an EXACT match of consecutive lines in the original script
3. Make the MINIMAL change that fixes the error
4. Do NOT import Composition or registerRoot - these are handled externally
5. Do NOT use functions that don't exist in 'remotion'. Valid exports: useCurrentFrame, useVideoConfig, interpolate, spring, Easing, Audio, Img, Video, AbsoluteFill, Sequence, useCurrentScale
6. interpolate() outputRange must contain ONLY numbers, never strings
7. interpolate() inputRange must be strictly increasing numbers
8. spring() returns a number, not an object
9. All inline styles must use camelCase (backgroundColor not background-color)
10. If the error says "X is not a function", remove that import and rewrite the affected code without it

EXAMPLE:
<<<SEARCH
import { useCurrentFrame, useVideoConfig, interpolate, spring, cameraZoom } from 'remotion';
===
import { useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';
>>>REPLACE

<<<SEARCH
  const camera = cameraZoom({ frame, fps, zoom: interpolate(frame, [0, 120], [1, 1.2]) });
===
  const zoom = interpolate(frame, [0, 120], [1, 1.2], { extrapolateRight: 'clamp' });
>>>REPLACE"""


def _apply_search_replace(original: str, ai_response: str) -> str:
    import re
    blocks = re.findall(
        r'<<<SEARCH\s*\n(.*?)\n===\s*\n(.*?)\n>>>REPLACE',
        ai_response, re.DOTALL
    )
    if not blocks:
        return ''
    result = original
    applied = 0
    for search_text, replace_text in blocks:
        search_clean = search_text.rstrip()
        replace_clean = replace_text.rstrip()
        if search_clean in result:
            result = result.replace(search_clean, replace_clean, 1)
            applied += 1
            print(f'[Vibe Video] Applied fix block ({applied})')
        else:
            stripped_search = '\n'.join(line.strip() for line in search_clean.splitlines())
            stripped_result = '\n'.join(line.strip() for line in result.splitlines())
            if stripped_search in stripped_result:
                lines = result.splitlines()
                search_lines = search_clean.splitlines()
                replace_lines = replace_clean.splitlines()
                search_stripped = [l.strip() for l in search_lines]
                for i in range(len(lines) - len(search_lines) + 1):
                    window = [lines[i + j].strip() for j in range(len(search_lines))]
                    if window == search_stripped:
                        lines[i:i + len(search_lines)] = replace_lines
                        applied += 1
                        print(f'[Vibe Video] Applied fix block with fuzzy match ({applied})')
                        break
                result = '\n'.join(lines)
            else:
                print(f'[Vibe Video] Could not match SEARCH block: {search_clean[:80]}...')
    if applied == 0:
        return ''
    return result


class ScriptFixWorker(QThread):
    finished = Signal(bool, str)
    MAX_RETRIES = 3

    def __init__(self, api_key, endpoint, service, model, script_content, error_msg):
        super().__init__()
        self.api_key = api_key
        self.endpoint = endpoint
        self.service = service
        self.model = model
        self.script_content = script_content
        self.error_msg = error_msg

    def _call_ai(self, prompt):
        import os
        import json
        svc = (self.service or '').lower()
        endpoint = (self.endpoint or '').strip()
        if endpoint:
            from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
            return CustomEndpointHelper.call_endpoint(self.api_key, endpoint, svc, self.model, prompt, timeout=120)
        elif svc == 'gemini':
            import google.genai as genai
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(model=self.model, contents=[prompt])
            return response.text
        elif svc in ('openai', 'openrouter', 'maia', 'blackbox'):
            from openai import OpenAI
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'configs', 'ai_config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                ai_config = json.load(f)
            base_url = ai_config['provider_endpoints'][svc]
            client = OpenAI(api_key=self.api_key, base_url=base_url)
            response = client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": prompt}])
            return response.choices[0].message.content
        elif svc == 'groq':
            from groq import Groq
            client = Groq(api_key=self.api_key)
            response = client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": prompt}])
            return response.choices[0].message.content
        else:
            raise ValueError(f"Unsupported service: {svc}")

    def run(self):
        try:
            full_prompt = (SCRIPT_FIX_SYSTEM
                + "\n\nSCRIPT TO FIX:\n" + self.script_content
                + "\n\nERROR:\n" + self.error_msg)
            for attempt in range(1, self.MAX_RETRIES + 1):
                print(f'[Vibe Video] Fix attempt {attempt}/{self.MAX_RETRIES}')
                text = self._call_ai(full_prompt)
                patched = _apply_search_replace(self.script_content, text)
                if patched:
                    print(f'[Vibe Video] Fix applied via SEARCH/REPLACE blocks (attempt {attempt})')
                    self.finished.emit(True, patched)
                    return
                code = self._extract_code(text)
                if code and ('import' in code or 'export' in code):
                    print(f'[Vibe Video] Fix applied via full code fallback (attempt {attempt})')
                    self.finished.emit(True, code)
                    return
                print(f'[Vibe Video] Attempt {attempt} produced unusable response, retrying...')
            self.finished.emit(False, f"AI failed to produce a valid fix after {self.MAX_RETRIES} attempts")
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
            details_label.setStyleSheet('color: #444; font-size: 11px;')
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
        # Determine the folder containing the output file
        folder = os.path.dirname(path)
        if not folder:
            folder = os.path.dirname(os.path.abspath(path))
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

    def _on_duration_changed(self):
        if not self._render_settings_tab:
            return
        fps = self._render_settings_tab.fps_spin.value()
        if fps <= 0:
            return
        frames = round(self.duration_seconds_spin.value() * fps)
        self._render_settings_tab.duration_spin.blockSignals(True)
        self._render_settings_tab.duration_spin.setValue(frames)
        self._render_settings_tab.duration_spin.blockSignals(False)

    def _sync_duration_to_render_settings(self):
        self._on_duration_changed()

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
        if self._render_worker:
            self._render_worker.cancel()
            self.render_btn.setEnabled(False)
            self.progress_bar.setFormat('Cancelling...')

    def _restore_render_btn(self):
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

    def _on_render_progress(self, percentage, message):
        if percentage >= 0:
            self.progress_bar.setValue(percentage)
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
        self.render_btn.setEnabled(False)
        self.render_btn.setText('Fixing...')
        self.render_btn.setIcon(qta.icon('fa6s.spinner', animation=qta.Spin(self.render_btn)))
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat('AI is fixing the script...')
        self._fix_worker = ScriptFixWorker(
            self._ai_key, self._ai_endpoint, self._ai_service, self._ai_model,
            script_content, self._last_error_msg
        )
        self._fix_worker.finished.connect(self._on_fix_finished)
        self._fix_worker.start()

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
        print(f'[Vibe Video] Script fixed and saved (id={script_id})')
        if script_data:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._apply_fixed_script(script_data))

    def _apply_fixed_script(self, script_data):
        if self._scripts_widget:
            self._scripts_widget.display_script(script_data)
            self._scripts_widget.script_updated.emit(script_data)
