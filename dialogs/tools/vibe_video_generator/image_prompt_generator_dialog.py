import os
import tempfile
import base64
import json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QApplication, QFileDialog, QSizePolicy, QComboBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QColor
import qtawesome as qta
from helpers.image_compression_helper import compress_and_save_image
from ui.api_key_section import ApiKeySectionWidget
from ui.theme_system import theme


IMAGE_ANALYSIS_SYSTEM_PROMPT = """You are a Remotion animation video expert. Analyze the provided image thoroughly and generate a detailed, specific prompt for creating a React/TypeScript Remotion animation that mimics, resembles, or animates based on the image.

RULES:
1. Output ONLY the detailed animation prompt text, no explanation, no markdown fencing
2. The prompt must be comprehensive (300-800 words minimum) and extremely specific
3. Include all of these sections clearly labeled:
   - VISUAL ELEMENTS: Describe every object, person, text, shape, and their positions/sizes in the image
   - COLOR PALETTE: List exact colors (hex codes if possible) and their distribution
   - COMPOSITION & LAYOUT: Explain the spatial arrangement, depth, perspective, framing
   - ANIMATION CONCEPT: Propose the overall animation idea - what moves, how, and why
   - MOTION DETAILS: For each animated element specify:
     * Type of motion (fade, scale, slide, rotate, bounce, morph, etc.)
     * Timing (when it starts, duration, easing functions)
     * Trajectory and path
     * Layering and z-index ordering
   - TRANSITIONS & EFFECTS: Any transitions between scenes, effects like blur, glow, shadow, particles
   - STYLE & ATMOSPHERE: Overall mood, visual style (minimalist, cartoon, photorealistic, retro, etc.)
   - TECHNICAL NOTES: Specific Remotion/React implementation hints (useCurrentFrame, interpolate, spring, sequence, AbsoluteFill positioning, etc.)

4. Be precise and technical where possible - the prompt should be unambiguous for AI code generation
5. If the image contains text, specify exact typography details (font style, size, weight, color, placement)
6. For complex scenes, break the animation into sequences or scenes
7. Use Remotion best practices: reference frame-based timing, fps awareness, performance considerations

OUTPUT FORMAT:
VISUAL ELEMENTS:
- Element 1: description
- Element 2: description
...

ANIMATION CONCEPT:
[Paragraph describing the overall animation idea]

MOTION DETAILS:
1. [Element name]: [specific motion details including timing, easing, duration]
2. [Element name]: [specific motion details]

TECHNICAL IMPLEMENTATION:
[Remotion-specific technical guidance]"""


class ImagePromptWorker(QThread):
    """Analisa gambar dan generate prompt animasi."""
    finished = Signal(bool, str)
    progress = Signal(str)

    def __init__(self, api_key, endpoint, service, model, image_path, max_retries=5):
        super().__init__()
        self.api_key = api_key
        self.endpoint = endpoint
        self.service = service
        self.model = model
        self.image_path = image_path
        self.max_retries = max_retries

    def run(self):
        compressed_path = None

        for attempt in range(1, self.max_retries + 1):
            try:
                self.progress.emit(f'Compressing... ({attempt}/{self.max_retries})')

                compressed_path = compress_and_save_image(self.image_path)
                if not compressed_path:
                    self.finished.emit(False, 'Compression failed')
                    return

                self.progress.emit('Reading...')

                with open(compressed_path, 'rb') as f:
                    image_bytes = f.read()
                image_b64 = base64.b64encode(image_bytes).decode('utf-8')
                image_data_url = f'data:image/jpeg;base64,{image_b64}'

                messages = [
                    {
                        'role': 'user',
                        'content': [
                            {'type': 'text', 'text': IMAGE_ANALYSIS_SYSTEM_PROMPT},
                            {'type': 'image_url', 'image_url': {'url': image_data_url}}
                        ]
                    }
                ]

                self.progress.emit('Analyzing...')

                svc = (self.service or '').lower()
                endpoint = (self.endpoint or '').strip()
                text = ''

                if endpoint:
                    from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
                    text = CustomEndpointHelper.call_endpoint(
                        self.api_key, endpoint, svc, self.model, IMAGE_ANALYSIS_SYSTEM_PROMPT,
                        image_path=compressed_path, timeout=180
                    )
                elif svc in ('openai', 'openrouter', 'maia', 'blackbox'):
                    from openai import OpenAI
                    config_path = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                        'configs', 'ai_config.json'
                    )
                    with open(config_path, 'r', encoding='utf-8') as f:
                        ai_config = json.load(f)
                    base_url = ai_config.get('provider_endpoints', {}).get(svc)
                    if not base_url:
                        base_url_map = {
                            'openai': 'https://api.openai.com/v1',
                            'openrouter': 'https://openrouter.ai/api/v1',
                            'maia': 'https://api.mixedrole.io/v1',
                            'blackbox': 'https://api.blackbox.ai/v1'
                        }
                        base_url = base_url_map.get(svc)
                    client = OpenAI(api_key=self.api_key, base_url=base_url)
                    response = client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        max_tokens=4000
                    )
                    from helpers.ai_helper.openai_stream_helper import extract_response_text
                    text = extract_response_text(response)
                elif svc == 'gemini':
                    import google.genai as genai
                    from google.genai.types import Part
                    client = genai.Client(api_key=self.api_key)
                    contents = []
                    for msg in messages:
                        if msg['role'] == 'user':
                            for ci in msg['content']:
                                if ci['type'] == 'text':
                                    contents.append(ci['text'])
                                elif ci['type'] == 'image_url':
                                    url = ci['image_url']['url']
                                    if url.startswith('data:image/jpeg;base64,'):
                                        b64 = url.split(',')[1]
                                        contents.append(Part.from_bytes(data=base64.b64decode(b64), mime_type='image/jpeg'))
                    try:
                        response = client.models.generate_content(model=self.model, contents=contents)
                        text = response.text
                    except Exception as gemini_err:
                        # Check if it's a model not supporting images
                        err_str = str(gemini_err).lower()
                        if 'does not support image input' in err_str or 'image' in err_str or 'vision' in err_str:
                            self.finished.emit(False, f'Model "{self.model}" does not support image input.\nUse a Gemini vision model like:\n- gemini-1.5-flash\n- gemini-1.5-pro\n- gemini-2.0-flash-exp\n- gemini-2.5-pro-exp')
                        else:
                            raise
                elif svc == 'groq':
                    self.finished.emit(False, 'Groq tidak mendukung analisis gambar.')
                    return
                else:
                    self.finished.emit(False, f'Service tidak didukung: {svc}')
                    return

                self.progress.emit('Processing...')

                if not text:
                    self.finished.emit(False, 'No response')
                    return

                prompt_text = text.strip()
                if prompt_text.startswith('```') and prompt_text.endswith('```'):
                    lines = prompt_text.split('\n')
                    if len(lines) > 2:
                        prompt_text = '\n'.join(lines[1:-1]).strip()

                self.finished.emit(True, prompt_text)
                break

            except Exception as e:
                last_error = str(e)
                print(f'[ImagePromptWorker] Attempt {attempt}/{self.max_retries}: {e}')

                if attempt >= self.max_retries:
                    self.finished.emit(False, f'Gagal setelah {self.max_retries} percobaan:\n{last_error}')
                else:
                    import time
                    wait_time = 2 ** attempt
                    self.progress.emit(f'Coba lagi dalam {wait_time}s...')
                    time.sleep(wait_time)


class ImagePromptGeneratorDialog(QDialog):
    """Dialog untuk generate prompt dari gambar."""

    def __init__(self, parent=None, db=None, current_api_key='', current_service='', current_model=''):
        super().__init__(parent)
        self.db = db
        self.selected_image_path = None
        self._worker = None
        self._api_key_section = None
        self._current_api_key = current_api_key or ''
        self._current_service = current_service or ''
        self._current_model = current_model or ''

        self.setWindowTitle('Generate from Image')
        self.setModal(True)
        self.setMinimumWidth(400)
        self._setup_ui()
        self._select_initial_credentials()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        # API Key section — expand to dialog width, very compact
        self._api_key_section = ApiKeySectionWidget(self.db, self)
        self._api_key_section.setMaximumHeight(34)
        # Allow section to expand horizontally with dialog
        self._api_key_section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # Hide non-essential elements
        if hasattr(self._api_key_section, 'tested_label'):
            self._api_key_section.tested_label.setVisible(False)
        if hasattr(self._api_key_section, 'join_member_btn'):
            self._api_key_section.join_member_btn.setVisible(False)
        if hasattr(self._api_key_section, 'add_api_btn'):
            self._api_key_section.add_api_btn.setVisible(False)
        if hasattr(self._api_key_section, 'get_api_btn'):
            self._api_key_section.get_api_btn.setVisible(False)
        # Tight widths
        if hasattr(self._api_key_section, 'model_combo'):
            self._api_key_section.model_combo.setFixedWidth(55)
        if hasattr(self._api_key_section, 'api_key_combo'):
            # Keep reasonable max to avoid overly wide, but allow expand
            self._api_key_section.api_key_combo.setMaximumWidth(280)
        layout.addWidget(self._api_key_section)

        # Image preview
        gray = QColor(theme.get_color('gray'))
        gray_rgba = f'rgba({gray.red()},{gray.green()},{gray.blue()},0.25)'
        bg_rgba = f'rgba({gray.red()},{gray.green()},{gray.blue()},0.06)'
        text_rgba = f'rgba({gray.red()},{gray.green()},{gray.blue()},0.6)'

        self.image_label = QLabel('No\nimage')
        self.image_label.setFixedSize(180, 120)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setWordWrap(True)
        self.image_label.setStyleSheet(f'''
            QLabel {{
                background-color: {bg_rgba};
                border: 2px dashed {gray_rgba};
                border-radius: 6px;
                color: {text_rgba};
                font-size: 11px;
            }}
        ''')
        layout.addWidget(self.image_label, 0, Qt.AlignmentFlag.AlignHCenter)

        # Open / Paste buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.addStretch()

        self.open_image_btn = QPushButton('Open Image')
        self.open_image_btn.setIcon(qta.icon('fa6s.folder-open'))
        self.open_image_btn.clicked.connect(self._on_open_image)
        self.open_image_btn.setMinimumHeight(28)
        self.open_image_btn.setMinimumWidth(90)
        btn_row.addWidget(self.open_image_btn)

        self.paste_clipboard_btn = QPushButton('Paste Clipboard')
        self.paste_clipboard_btn.setIcon(qta.icon('fa6s.clipboard'))
        self.paste_clipboard_btn.clicked.connect(self._on_paste_clipboard)
        self.paste_clipboard_btn.setMinimumHeight(28)
        self.paste_clipboard_btn.setMinimumWidth(90)
        btn_row.addWidget(self.paste_clipboard_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Progress
        self.progress_label = QLabel('')
        self.progress_label.setStyleSheet(f'color: {theme.get_color("primary")}; font-size: 10px;')
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress_label)

        # Action buttons: Cancel | Generate
        action_row = QHBoxLayout()
        action_row.addStretch()

        cancel_btn = QPushButton('Cancel')
        cancel_btn.setIcon(qta.icon('fa6s.xmark'))
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumWidth(80)
        action_row.addWidget(cancel_btn)

        self.generate_btn = QPushButton('Generate')
        self.generate_btn.setIcon(qta.icon('fa6s.wand-magic-sparkles'))
        self.generate_btn.clicked.connect(self._on_generate)
        self.generate_btn.setMinimumWidth(100)
        action_row.addWidget(self.generate_btn)

        layout.addLayout(action_row)

    def _on_open_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Select Image', '', 'Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)'
        )
        if file_path:
            self._set_selected_image(file_path)

    def _on_paste_clipboard(self):
        clipboard = QApplication.clipboard()
        pixmap = clipboard.pixmap()
        if pixmap.isNull():
            QMessageBox.warning(self, 'Empty', 'Clipboard has no image.')
            return
        try:
            temp = os.path.join(tempfile.gettempdir(), f'img_{os.getpid()}.png')
            if pixmap.save(temp, 'PNG'):
                self._set_selected_image(temp)
        except Exception as e:
            QMessageBox.warning(self, 'Error', f'Paste failed:\n{e}')

    def _set_selected_image(self, path):
        self.selected_image_path = path
        pm = QPixmap(path)
        if not pm.isNull():
            scaled = pm.scaled(self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(scaled)
        self.progress_label.setText(os.path.basename(path))

    def _get_current_credentials(self):
        if self._api_key_section:
            k = self._api_key_section.api_key
            i = self._api_key_section.api_key_map.get(k, {})
            return {
                'api_key': k or '',
                'service': i.get('service', '') or '',
                'model': i.get('model', '') or '',
                'endpoint': i.get('endpoint', '') or ''
            }
        return {'api_key': '', 'service': '', 'model': '', 'endpoint': ''}

    def _select_initial_credentials(self):
        if not self._api_key_section or not self.db:
            return
        self._api_key_section._populate_models()
        tgt_svc = self._current_service.capitalize() if self._current_service else ''
        tgt_mdl = self._current_model or ''

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
            if api_idx is None and self._current_api_key:
                for i in range(self._api_key_section.api_key_combo.count()):
                    if self._api_key_section.api_key_combo.itemData(i) == self._current_api_key:
                        api_idx = i
                        break
            if api_idx is not None:
                self._api_key_section.api_key_combo.setCurrentIndex(api_idx)
        elif self._current_api_key:
            for i in range(self._api_key_section.api_key_combo.count()):
                if self._api_key_section.api_key_combo.itemData(i) == self._current_api_key:
                    self._api_key_section.api_key_combo.setCurrentIndex(i)
                    break

    def _on_generate(self):
        if not self.selected_image_path:
            QMessageBox.warning(self, 'No Image', 'Select or paste an image first.')
            return
        creds = self._get_current_credentials()
        api_key = creds.get('api_key', '')
        if not api_key or len(api_key) < 6:
            QMessageBox.warning(self, 'API Key Required', 'Select an API key from the dropdown above.')
            self._api_key_section.api_key_combo.setFocus()
            return

        self.generate_btn.setEnabled(False)
        self.generate_btn.setText('Analyzing...')
        self.generate_btn.setIcon(qta.icon('fa6s.spinner', animation=qta.Spin(self.generate_btn)))
        self.open_image_btn.setEnabled(False)
        self.paste_clipboard_btn.setEnabled(False)
        self._api_key_section.setEnabled(False)

        # Keep strong reference to worker
        self._worker = ImagePromptWorker(
            api_key,
            creds.get('endpoint', ''),
            creds.get('service', ''),
            creds.get('model', ''),
            self.selected_image_path,
            max_retries=5
        )
        self._worker.progress.connect(self.progress_label.setText)
        self._worker.finished.connect(self._on_generation_finished)
        self._worker.start()

    def _on_generation_finished(self, success, result):
        # Worker already finished; schedule deletion
        if self._worker:
            self._worker.deleteLater()
            self._worker = None

        self.generate_btn.setEnabled(True)
        self.generate_btn.setText('Generate')
        self.generate_btn.setIcon(qta.icon('fa6s.wand-magic-sparkles'))
        self.open_image_btn.setEnabled(True)
        self.paste_clipboard_btn.setEnabled(True)
        self._api_key_section.setEnabled(True)

        if success:
            self.accept_with_result(result)
        else:
            QMessageBox.critical(self, 'Failed', f'Analysis error:\n{result}')
            self.progress_label.setText('')

    def accept_with_result(self, prompt):
        self.generated_prompt = prompt
        self.accept()

    def get_generated_prompt(self):
        return getattr(self, 'generated_prompt', None)

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(3000)
        super().closeEvent(event)
