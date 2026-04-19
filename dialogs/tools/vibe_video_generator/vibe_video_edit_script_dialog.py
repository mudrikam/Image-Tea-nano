from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                               QTabWidget, QTextEdit, QWidget, QPushButton, QMessageBox,
                               QSplitter, QComboBox, QSizePolicy, QApplication)
from PySide6.QtCore import Qt, Signal, QThread
from dialogs.tools.vibe_video_generator.vibe_video_scripts_widget import TypeScriptHighlighter
from dialogs.tools.vibe_video_generator.image_prompt_generator_dialog import ImagePromptGeneratorDialog
from ui.api_key_section import ApiKeySectionWidget
import qtawesome as qta

REMOTION_SYSTEM_PROMPT = """You are a Remotion video script generator. Generate valid TypeScript/React code for Remotion.

RULES:
1. Import React and ONLY these valid Remotion exports: useCurrentFrame, useVideoConfig, interpolate, spring, Easing, AbsoluteFill, Sequence, Audio, Img, Video
2. DO NOT import anything else from 'remotion' - functions like cameraZoom, random, noise do NOT exist
3. Create a single React functional component
4. Export the component as named export
5. Use inline styles only (no CSS files), all style keys must be camelCase
6. The component receives no props - use useCurrentFrame() and useVideoConfig() for animation
7. DO NOT import Composition or registerRoot - the wrapper handles that
8. Output ONLY the TypeScript code, no markdown fences, no explanation
9. interpolate() outputRange must contain ONLY numbers, never strings
10. interpolate() inputRange must be strictly increasing numbers
11. spring() returns a number - use it directly as a value
12. The component should fill the entire frame (width: '100%', height: '100%')
13. For consistent timing across different FPS values, base frame numbers on `fps`. For an N‑second animation, use `fps * N` as the frame count in `interpolate` ranges (e.g., a 1‑second fade: `interpolate(frame, [0, fps], [0, 1])`).

EXAMPLE OUTPUT:
import React from 'react';
import { useCurrentFrame, useVideoConfig, interpolate, spring } from 'remotion';

export const MyComponent: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  const opacity = interpolate(frame, [0, fps * 1], [0, 1], { extrapolateRight: 'clamp' });
  const scale = spring({ frame, fps, config: { damping: 200 } });

  return (
    <div style={{ flex: 1, justifyContent: 'center', alignItems: 'center', display: 'flex', backgroundColor: '#0f0f0f', width: '100%', height: '100%' }}>
      <h1 style={{ color: 'white', fontSize: 60, opacity, transform: `scale(${scale})` }}>
        Hello World
      </h1>
    </div>
  );
};
"""


class ScriptGeneratorWorker(QThread):
    finished = Signal(bool, str)

    def __init__(self, api_key, endpoint, service, model, prompt, max_retries=5):
        super().__init__()
        self.api_key = api_key
        self.endpoint = endpoint
        self.service = service
        self.model = model
        self.prompt = prompt
        self.max_retries = max_retries

    def run(self):
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                import os
                import json
                full_prompt = REMOTION_SYSTEM_PROMPT + "\n\nUSER REQUEST:\n" + self.prompt
                svc = (self.service or '').lower()
                endpoint = (self.endpoint or '').strip()

                print(f"[Vibe Video] Calling AI: service={svc}, model={self.model} (attempt {attempt}/{self.max_retries})")

                text = ''

                if endpoint:
                    from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
                    print(f"[Vibe Video] Using custom endpoint: {endpoint}")
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
                if code:
                    # Success
                    self.finished.emit(True, code)
                    break  # Exit retry loop
                else:
                    # No code extracted, treat as failure
                    raise ValueError("No valid TypeScript code extracted from AI response")

            except Exception as e:
                last_error = str(e)
                print(f"[Vibe Video] AI generation error (attempt {attempt}/{self.max_retries}): {e}")

                if attempt >= self.max_retries:
                    self.finished.emit(False, f"Failed after {self.max_retries} attempts:\n{last_error}")
                else:
                    import time
                    wait_time = 2 ** attempt
                    print(f"[Vibe Video] Retrying in {wait_time}s...")
                    time.sleep(wait_time)

    def _extract_code(self, text):
        import re
        patterns = [
            r'```(?:tsx?|typescript|javascript)\s*\n(.*?)```',
            r'```\s*\n(.*?)```',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1).strip()
        stripped = text.strip()
        if 'import' in stripped and ('React' in stripped or 'remotion' in stripped):
            return stripped
        return text.strip()


PROMPT_REFINE_SYSTEM = """You are a video prompt engineer. The user gives you a short, rough idea for an animated video. Your job is to rewrite it into a clear, detailed, and specific prompt that will help an AI code generator create a great Remotion (React/TypeScript) animation.

RULES:
- Output ONLY the refined prompt text, no explanation, no markdown
- Keep it 3-6 sentences
- Include: what to animate, colors/style, transitions/effects, overall mood
- Be specific about motion: fade, scale, slide, rotate, bounce, etc.
- Do NOT write any code"""


class PromptRefinerWorker(QThread):
    finished = Signal(bool, str)

    def __init__(self, api_key, endpoint, service, model, prompt):
        super().__init__()
        self.api_key = api_key
        self.endpoint = endpoint
        self.service = service
        self.model = model
        self.prompt = prompt

    def run(self):
        try:
            import os
            import json
            full_prompt = PROMPT_REFINE_SYSTEM + "\n\nUSER INPUT:\n" + self.prompt
            svc = (self.service or '').lower()
            endpoint = (self.endpoint or '').strip()
            text = ''
            if endpoint:
                from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
                text = CustomEndpointHelper.call_endpoint(self.api_key, endpoint, svc, self.model, full_prompt, timeout=60)
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
            self.finished.emit(True, text.strip())
        except Exception as e:
            print(f"[Vibe Video] Prompt refine error: {e}")
            self.finished.emit(False, str(e))


class EditScriptDialog(QDialog):
    script_created = Signal(object)
    script_updated = Signal(object)

    def __init__(self, parent=None, collection_id=None, db=None, script_id=None,
                 api_key='', endpoint='', service='', model=''):
        super().__init__(parent)
        self.collection_id = collection_id
        self.db = db
        self.script_id = script_id
        self.is_editing = script_id is not None
        # Store initial credentials to pre-select in API key section
        self._initial_api_key = api_key or ''
        self._initial_endpoint = endpoint or ''
        self._initial_service = service or ''
        self._initial_model = model or ''
        self._generator_worker = None
        self._refine_worker = None
        self._api_key_section = None
        self.setWindowTitle('Edit Script' if self.is_editing else 'New Script')
        self.setMinimumSize(750, 600)
        self._setup_ui()
        if self.is_editing:
            self._load_script_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # API Key Section (compact)
        # API Key Section (compact, at top)
        self._api_key_section = ApiKeySectionWidget(self.db, self)
        self._api_key_section.setMaximumHeight(36)
        # Hide non-essential elements for compactness
        if hasattr(self._api_key_section, 'tested_label'):
            self._api_key_section.tested_label.setVisible(False)
        if hasattr(self._api_key_section, 'join_member_btn'):
            self._api_key_section.join_member_btn.setVisible(False)
        if hasattr(self._api_key_section, 'add_api_btn'):
            self._api_key_section.add_api_btn.setVisible(False)
        if hasattr(self._api_key_section, 'get_api_btn'):
            self._api_key_section.get_api_btn.setVisible(False)
        # Pre-select credentials if initial values provided
        if self._initial_api_key or self._initial_service:
            self._preselect_credentials()
        layout.addWidget(self._api_key_section)

        name_layout = QHBoxLayout()
        name_label = QLabel('Script Name:')
        name_label.setMinimumWidth(100)
        name_layout.addWidget(name_label)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('Enter script name...')
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        desc_layout = QHBoxLayout()
        desc_label = QLabel('Description:')
        desc_label.setMinimumWidth(100)
        desc_layout.addWidget(desc_label)
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText('Brief description...')
        desc_layout.addWidget(self.desc_edit)
        layout.addLayout(desc_layout)

        # Tabs
        tabs = QTabWidget()
        self.prompt_tab = QWidget()
        prompt_layout = QVBoxLayout(self.prompt_tab)
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText(
            'Describe the video you want to create...\n\n'
            'Examples:\n'
            '- Create a "Hello World" text animation that fades in then zooms out\n'
            '- Create a countdown timer from 10 to 0 with gradient background\n'
            '- Create a spinning logo animation with bounce effect'
        )
        prompt_layout.addWidget(self.prompt_edit, 1)

        gen_row = QHBoxLayout()
        gen_row.addStretch()
        self.refine_btn = QPushButton('Refine Prompt')
        self.refine_btn.setIcon(qta.icon('fa6s.star'))
        self.refine_btn.setMinimumHeight(36)
        self.refine_btn.setToolTip('Let AI expand your simple idea into a detailed prompt')
        self.refine_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refine_btn.clicked.connect(self._on_refine_prompt)
        gen_row.addWidget(self.refine_btn)
        self.image_prompt_btn = QPushButton('Generate from Image')
        self.image_prompt_btn.setIcon(qta.icon('fa6s.image'))
        self.image_prompt_btn.setMinimumHeight(36)
        self.image_prompt_btn.setToolTip('Analyze an image and create a detailed animation prompt')
        self.image_prompt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.image_prompt_btn.clicked.connect(self._on_generate_from_image)
        gen_row.addWidget(self.image_prompt_btn)
        self.generate_btn = QPushButton('Generate Script')
        self.generate_btn.setIcon(qta.icon('fa6s.wand-magic-sparkles'))
        self.generate_btn.setMinimumHeight(36)
        self.generate_btn.setMinimumWidth(180)
        self.generate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_btn.clicked.connect(self._on_generate)
        gen_row.addWidget(self.generate_btn)
        prompt_layout.addLayout(gen_row)

        self.script_tab = QWidget()
        script_layout = QVBoxLayout(self.script_tab)
        self.script_edit = QTextEdit()
        self.script_edit.setPlaceholderText('Enter or paste TypeScript/React code here...')
        self._highlighter = TypeScriptHighlighter(self.script_edit.document())
        script_layout.addWidget(self.script_edit)
        script_btn_row = QHBoxLayout()
        script_btn_row.addStretch()
        self.paste_script_btn = QPushButton('Paste')
        self.paste_script_btn.setIcon(qta.icon('fa6s.paste'))
        self.paste_script_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.paste_script_btn.clicked.connect(self._on_paste_script)
        script_btn_row.addWidget(self.paste_script_btn)
        script_layout.addLayout(script_btn_row)

        tabs.addTab(self.prompt_tab, qta.icon('fa6s.wand-magic-sparkles'), 'Generate with AI')
        tabs.addTab(self.script_tab, qta.icon('fa6s.code'), 'TypeScript')
        self.tabs = tabs
        layout.addWidget(tabs)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton('Cancel')
        cancel_btn.setIcon(qta.icon('fa6s.xmark'))
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton('Save' if self.is_editing else 'Create')
        ok_btn.setIcon(qta.icon('fa6s.floppy-disk'))
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def _preselect_credentials(self):
        """Pre-select the initial credentials passed from parent."""
        if not self._api_key_section or not self.db:
            return
        self._api_key_section._populate_models()
        tgt_svc = self._initial_service.capitalize() if self._initial_service else ''
        tgt_mdl = self._initial_model or ''
        idx = -1
        for i in range(self._api_key_section.model_combo.count()):
            if self._api_key_section.model_combo.itemText(i).lower() == tgt_svc.lower():
                idx = i
                break
        if idx >= 0:
            self._api_key_section.model_combo.setCurrentIndex(idx)
            api_idx = None
            if tgt_mdl:
                for i in range(self._api_key_section.api_key_combo.count()):
                    d = self._api_key_section.api_key_combo.itemData(i)
                    if d:
                        info = self._api_key_section.api_key_map.get(d, {})
                        if info.get('model', '').lower() == tgt_mdl.lower():
                            api_idx = i
                            break
            if api_idx is None and self._initial_api_key:
                for i in range(self._api_key_section.api_key_combo.count()):
                    if self._api_key_section.api_key_combo.itemData(i) == self._initial_api_key:
                        api_idx = i
                        break
            if api_idx is not None:
                self._api_key_section.api_key_combo.setCurrentIndex(api_idx)
        elif self._initial_api_key:
            for i in range(self._api_key_section.api_key_combo.count()):
                if self._api_key_section.api_key_combo.itemData(i) == self._initial_api_key:
                    self._api_key_section.api_key_combo.setCurrentIndex(i)
                    break

    def _get_current_credentials(self):
        """Get currently selected credentials from the API key section."""
        if self._api_key_section:
            k = self._api_key_section.api_key
            i = self._api_key_section.api_key_map.get(k, {})
            return {
                'api_key': k or '',
                'endpoint': i.get('endpoint', '') or '',
                'service': i.get('service', '') or '',
                'model': i.get('model', '') or ''
            }
        return {'api_key': '', 'endpoint': '', 'service': '', 'model': ''}

    def _load_script_data(self):
        if not self.db or not self.script_id:
            return
        script_data = self.db.get_remotion_script(self.script_id)
        if script_data:
            self.name_edit.setText(script_data.get('name', ''))
            self.desc_edit.setText(script_data.get('description') or '')
            self.script_edit.setPlainText(script_data.get('script_content', ''))

    def _on_generate(self):
        prompt_text = self.prompt_edit.toPlainText().strip()
        if not prompt_text:
            QMessageBox.warning(self, 'Validation', 'Please describe the video you want to create.')
            self.prompt_edit.setFocus()
            return

        creds = self._get_current_credentials()
        api_key = creds.get('api_key', '')
        if not api_key:
            QMessageBox.warning(self, 'API Key Required',
                                'Please select an API key above.')
            self._api_key_section.api_key_combo.setFocus()
            return

        self.generate_btn.setEnabled(False)
        self.generate_btn.setText('Generating...')
        self.generate_btn.setIcon(qta.icon('fa6s.spinner', animation=qta.Spin(self.generate_btn)))
        self.refine_btn.setEnabled(False)

        self._generator_worker = ScriptGeneratorWorker(
            api_key, creds.get('endpoint', ''), creds.get('service', ''), creds.get('model', ''), prompt_text, max_retries=5
        )
        self._generator_worker.finished.connect(self._on_generate_finished)
        self._generator_worker.start()

    def _on_generate_finished(self, success, result):
        # Clean up worker
        if self._generator_worker:
            self._generator_worker.deleteLater()
            self._generator_worker = None

        self.generate_btn.setEnabled(True)
        self.generate_btn.setText('Generate Script')
        self.generate_btn.setIcon(qta.icon('fa6s.wand-magic-sparkles'))
        self.refine_btn.setEnabled(True)

        if success:
            self.script_edit.setPlainText(result)
            self.tabs.setCurrentIndex(1)
        else:
            QMessageBox.critical(self, 'Generation Failed', f'Failed to generate script:\n{result}')

    def _on_paste_script(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.script_edit.setPlainText(text)
            self.script_edit.setFocus()

    def _on_refine_prompt(self):
        prompt_text = self.prompt_edit.toPlainText().strip()
        if not prompt_text:
            QMessageBox.warning(self, 'Validation', 'Please write a brief idea first before refining.')
            self.prompt_edit.setFocus()
            return
        creds = self._get_current_credentials()
        api_key = creds.get('api_key', '')
        if not api_key:
            QMessageBox.warning(self, 'API Key Required',
                                'Please select an API key above.')
            self._api_key_section.api_key_combo.setFocus()
            return
        self.refine_btn.setEnabled(False)
        self.refine_btn.setText('Refining...')
        self.refine_btn.setIcon(qta.icon('fa6s.spinner', animation=qta.Spin(self.refine_btn)))
        self.generate_btn.setEnabled(False)
        self._refine_worker = PromptRefinerWorker(
            api_key, creds.get('endpoint', ''), creds.get('service', ''), creds.get('model', ''), prompt_text
        )
        self._refine_worker.finished.connect(self._on_refine_finished)
        self._refine_worker.start()

    def _on_refine_finished(self, success, result):
        worker = self._refine_worker
        self._refine_worker = None
        if worker:
            worker.quit()
            worker.wait(2000)
            worker.deleteLater()

        self.refine_btn.setEnabled(True)
        self.refine_btn.setText('Refine Prompt')
        self.refine_btn.setIcon(qta.icon('fa6s.star'))
        self.generate_btn.setEnabled(True)

        if success:
            self.prompt_edit.setPlainText(result)
        else:
            QMessageBox.critical(self, 'Refine Failed', f'Failed to refine prompt:\n{result}')

    def _on_generate_from_image(self):
        # Create and show dialog with current credentials from API key section
        creds = self._get_current_credentials()
        dlg = ImagePromptGeneratorDialog(
            self,
            db=self.db,
            current_api_key=creds.get('api_key', ''),
            current_service=creds.get('service', ''),
            current_model=creds.get('model', '')
        )

        if dlg.exec() == QDialog.Accepted:
            generated_prompt = dlg.get_generated_prompt()
            if generated_prompt:
                # Insert into prompt edit area, optionally appending if there's existing text
                current_text = self.prompt_edit.toPlainText().strip()
                if current_text:
                    # Append with separator
                    combined = f"{current_text}\n\n--- Generated from Image ---\n{generated_prompt}"
                else:
                    combined = generated_prompt
                self.prompt_edit.setPlainText(combined)
                # Switch to prompt tab
                self.tabs.setCurrentIndex(0)
                self.prompt_edit.setFocus()

    def _cleanup_workers(self):
        if self._refine_worker:
            self._refine_worker.quit()
            if not self._refine_worker.wait(2000):
                print("[Vibe Video] Prompt refiner still running after 2s, terminating.")
                self._refine_worker.terminate()
                self._refine_worker.wait()
            self._refine_worker.deleteLater()
            self._refine_worker = None
        if self._generator_worker:
            self._generator_worker.quit()
            if not self._generator_worker.wait(2000):
                print("[Vibe Video] Script generator still running after 2s, terminating.")
                self._generator_worker.terminate()
                self._generator_worker.wait()
            self._generator_worker.deleteLater()
            self._generator_worker = None

    def closeEvent(self, event):
        self._cleanup_workers()
        super().closeEvent(event)

    def reject(self):
        self._cleanup_workers()
        super().reject()

    def accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, 'Validation Error', 'Script name cannot be empty.')
            self.name_edit.setFocus()
            return
        script_content = self.script_edit.toPlainText().strip()
        if not script_content:
            QMessageBox.warning(self, 'Validation Error', 'TypeScript content cannot be empty.')
            self.script_edit.setFocus()
            return

        description = self.desc_edit.text().strip() or None

        if self.db:
            if self.is_editing and self.script_id:
                self.db.update_remotion_script(
                    script_id=self.script_id,
                    name=name,
                    script_content=script_content,
                    description=description,
                )
                script_data = self.db.get_remotion_script(self.script_id)
                self.script_updated.emit(script_data)
            elif self.collection_id:
                script_id = self.db.add_remotion_script(
                    collection_id=self.collection_id,
                    name=name,
                    script_content=script_content,
                    description=description,
                )
                script_data = self.db.get_remotion_script(script_id)
                self.script_created.emit(script_data)

        self._cleanup_workers()
        super().accept()
