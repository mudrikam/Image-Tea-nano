from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTextEdit, QHBoxLayout, QPushButton, QMessageBox, QLabel, QApplication, QDialog, QLineEdit, QProgressBar)
from PySide6.QtCore import Qt, Signal, QRegularExpression, QThread, QTimer, QRect, QSize, QPoint
from PySide6.QtGui import QTextCharFormat, QColor, QFont, QSyntaxHighlighter, QPalette, QPainter, QTextCursor
import qtawesome as qta
from ui.theme_system import theme
from pygments import lex
from pygments.lexers import TypeScriptLexer
from pygments.token import Token

# Modern blue-focused modern TypeScript theme - VS Code One Dark Pro style
DARK_STYLES = {
    Token.Keyword: QColor('#c678dd'),
    Token.Keyword.Constant: QColor('#d19a66'),
    Token.Keyword.Declaration: QColor('#c678dd'),
    Token.Keyword.Namespace: QColor('#c678dd'),
    Token.Keyword.Type: QColor('#e5c07b'),
    Token.Name.Builtin: QColor('#e06c75'),
    Token.Name.Class: QColor('#e5c07b'),
    Token.Name.Decorator: QColor('#c678dd'),
    Token.Name.Entity: QColor('#e06c75'),
    Token.Name.Exception: QColor('#e06c75'),
    Token.Name.Function: QColor('#61afef'),
    Token.Name.Function.Magic: QColor('#56b6c2'),
    Token.Name.Variable: QColor('#e06c75'),
    Token.Name.Variable.Class: QColor('#e5c07b'),
    Token.Name.Variable.Global: QColor('#dcdfe4'),
    Token.Name.Variable.Instance: QColor('#dcdfe4'),
    Token.Name.Variable.Magic: QColor('#c678dd'),
    Token.Literal.Number: QColor('#d19a66'),
    Token.Literal.Number.Float: QColor('#d19a66'),
    Token.Literal.Number.Integer: QColor('#d19a66'),
    Token.Literal.String: QColor('#98c379'),
    Token.Literal.String.Affix: QColor('#98c379'),
    Token.Literal.String.Backtick: QColor('#98c379'),
    Token.Literal.String.Char: QColor('#98c379'),
    Token.Literal.String.Delimiter: QColor('#abb2bf'),
    Token.Literal.String.Doc: QColor('#5c6370'),
    Token.Literal.String.Double: QColor('#98c379'),
    Token.Literal.String.Escape: QColor('#d19a66'),
    Token.Literal.String.Heredoc: QColor('#98c379'),
    Token.Literal.String.Interpol: QColor('#e06c75'),
    Token.Literal.String.Other: QColor('#98c379'),
    Token.Literal.String.Regex: QColor('#c678dd'),
    Token.Literal.String.Single: QColor('#98c379'),
    Token.Literal.String.Symbol: QColor('#56b6c2'),
    Token.Comment: QColor('#5c6370'),
    Token.Comment.Multiline: QColor('#5c6370'),
    Token.Comment.Single: QColor('#5c6370'),
    Token.Comment.Special: QColor('#d19a66'),
    Token.Operator: QColor('#56b6c2'),
    Token.Operator.Word: QColor('#c678dd'),
    Token.Punctuation: QColor('#abb2bf'),
    Token.Generic: QColor('#abb2bf'),
    Token.Text: QColor('#abb2bf'),
}

# Modern blue-focused light theme - VS Code One Light Pro style
LIGHT_STYLES = {
    Token.Keyword: QColor('#a626a4'),
    Token.Keyword.Constant: QColor('#b76b00'),
    Token.Keyword.Declaration: QColor('#a626a4'),
    Token.Keyword.Namespace: QColor('#a626a4'),
    Token.Keyword.Type: QColor('#c18401'),
    Token.Name.Builtin: QColor('#e45649'),
    Token.Name.Class: QColor('#c18401'),
    Token.Name.Decorator: QColor('#a626a4'),
    Token.Name.Entity: QColor('#e45649'),
    Token.Name.Exception: QColor('#e45649'),
    Token.Name.Function: QColor('#4078f2'),
    Token.Name.Function.Magic: QColor('#0184bc'),
    Token.Name.Variable: QColor('#e45649'),
    Token.Name.Variable.Class: QColor('#c18401'),
    Token.Name.Variable.Global: QColor('#383a42'),
    Token.Name.Variable.Instance: QColor('#383a42'),
    Token.Name.Variable.Magic: QColor('#a626a4'),
    Token.Literal.Number: QColor('#b76b00'),
    Token.Literal.Number.Float: QColor('#b76b00'),
    Token.Literal.Number.Integer: QColor('#b76b00'),
    Token.Literal.String: QColor('#50a14f'),
    Token.Literal.String.Affix: QColor('#50a14f'),
    Token.Literal.String.Backtick: QColor('#50a14f'),
    Token.Literal.String.Char: QColor('#50a14f'),
    Token.Literal.String.Delimiter: QColor('#383a42'),
    Token.Literal.String.Doc: QColor('#a0a1a7'),
    Token.Literal.String.Double: QColor('#50a14f'),
    Token.Literal.String.Escape: QColor('#b76b00'),
    Token.Literal.String.Heredoc: QColor('#50a14f'),
    Token.Literal.String.Interpol: QColor('#e45649'),
    Token.Literal.String.Other: QColor('#50a14f'),
    Token.Literal.String.Regex: QColor('#a626a4'),
    Token.Literal.String.Single: QColor('#50a14f'),
    Token.Literal.String.Symbol: QColor('#0184bc'),
    Token.Comment: QColor('#a0a1a7'),
    Token.Comment.Multiline: QColor('#a0a1a7'),
    Token.Comment.Single: QColor('#a0a1a7'),
    Token.Comment.Special: QColor('#b76b00'),
    Token.Operator: QColor('#0184bc'),
    Token.Operator.Word: QColor('#a626a4'),
    Token.Punctuation: QColor('#383a42'),
    Token.Generic: QColor('#383a42'),
    Token.Text: QColor('#383a42'),
}

DARK_DEFAULT_TEXT = QColor('#abb2bf')
DARK_BG = QColor('#282c34')
LIGHT_DEFAULT_TEXT = QColor('#383a42')
LIGHT_BG = QColor('#fafafa')


class LineNumberArea(QWidget):
    """Widget to display line numbers next to a QTextEdit"""
    
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self._line_count = 0
        if editor:
            self.setFont(editor.font())
        self._update_count()
        
    def _update_count(self):
        self._line_count = self.editor.document().lineCount()
        
    def sizeHint(self):
        return QSize(self._calculate_width(), 0)
    
    def _calculate_width(self):
        # Calculate width needed for the highest line number
        if not self.editor or not self.editor.document():
            return 30
        line_count = self.editor.document().lineCount()
        digits = len(str(max(1, line_count)))
        # 2 digits = ~20px, each extra digit adds ~10px, plus padding
        return max(30, 20 + self.fontMetrics().horizontalAdvance('9') * digits)
    
    def update_width(self):
        self._update_count()
        width = self._calculate_width()
        self.setFixedWidth(width)
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            # Get theme colors for background and text
            _, default_text, bg = get_theme_colors()
            painter.fillRect(event.rect(), bg)
            painter.setPen(default_text)
            
            if not self.editor or not self.editor.document():
                return
            
            # Get the first visible block via cursor at top-left of viewport
            cursor = self.editor.cursorForPosition(QPoint(0, 0))
            block = cursor.block()
            if not block.isValid():
                block = self.editor.document().firstBlock()
                if not block.isValid():
                    return
            
            block_number = block.blockNumber()
            
            # Get document layout
            layout = self.editor.document().documentLayout()
            
            # Get the top position of the first visible block in document coordinates
            first_rect = layout.blockBoundingRect(block)
            top = int(first_rect.top())
            
            # Adjust for the current scroll position
            scroll_y = self.editor.verticalScrollBar().value()
            top -= scroll_y
            
            while block.isValid():
                rect = layout.blockBoundingRect(block)
                line_height = int(rect.height())
                bottom = top + line_height
                
                if top > event.rect().bottom():
                    break
                
                if bottom >= event.rect().top() and block.isVisible():
                    number = str(block_number + 1)
                    number_rect = QRect(0, top, self.width() - 4, line_height)
                    painter.drawText(number_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, number)
                
                block = block.next()
                block_number += 1
                top += line_height
        finally:
            painter.end()


def is_dark_mode():
    palette = QApplication.palette()
    base = palette.color(QPalette.ColorRole.Window)
    return base.lightness() < 128


def get_theme_colors():
    if is_dark_mode():
        return DARK_STYLES, DARK_DEFAULT_TEXT, DARK_BG
    return LIGHT_STYLES, LIGHT_DEFAULT_TEXT, LIGHT_BG


class TypeScriptHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._update_theme()

    def _update_theme(self):
        styles, default_text, bg = get_theme_colors()
        self._styles = styles
        self._default_format = QTextCharFormat()
        self._default_format.setForeground(default_text)

    def highlightBlock(self, text):
        try:
            full_text = self.currentBlock().text()
            for prev_block in self._iterate_prev_blocks():
                full_text = prev_block.text() + '\n' + full_text

            tokens = list(lex(full_text, TypeScriptLexer()))
            offset = 0
            for line_text, line_tokens in self._group_tokens_by_line(tokens):
                if line_text == text:
                    for tok_type, tok_value in line_tokens:
                        start = text.find(tok_value, offset)
                        if start == -1:
                            start = offset
                        fmt = QTextCharFormat()
                        color = self._styles.get(tok_type)
                        if color:
                            fmt.setForeground(color)
                        else:
                            fmt.setForeground(self._default_format.foreground().color())
                        self.setFormat(start, len(tok_value), fmt)
                        offset = start + len(tok_value)
                    return
        except Exception:
            self.setFormat(0, len(text), self._default_format)

    def update_theme(self):
        self._update_theme()
        self.rehighlight()

    def _iterate_prev_blocks(self):
        block = self.currentBlock().previous()
        blocks = []
        while block.isValid() and len(blocks) < 50:
            blocks.append(block)
            block = block.previous()
        blocks.reverse()
        return blocks

    def _group_tokens_by_line(self, tokens):
        lines = []
        current_line = ''
        current_tokens = []
        for tok_type, tok_value in tokens:
            if '\n' in tok_value:
                parts = tok_value.split('\n')
                for i, part in enumerate(parts):
                    if i > 0:
                        if current_line or current_tokens:
                            lines.append((current_line, current_tokens))
                        current_line = ''
                        current_tokens = []
                    if part:
                        current_line += part
                        current_tokens.append((tok_type, part))
            else:
                current_line += tok_value
                current_tokens.append((tok_type, tok_value))
        if current_line or current_tokens:
            lines.append((current_line, current_tokens))
        return lines


SCRIPT_REFINE_SYSTEM = """You are a Remotion TypeScript/React code refiner. The user gives you an existing script and a refinement instruction. Apply the change using SEARCH/REPLACE blocks.

OUTPUT FORMAT:
<<<SEARCH
exact lines from the original script to replace
===
replacement lines
>>>REPLACE

RULES:
1. Use SEARCH/REPLACE blocks - do NOT output the full script
2. SEARCH must exactly match consecutive lines in the original (whitespace-sensitive)
3. Make ONLY the minimal changes needed to fulfill the instruction
4. Valid 'remotion' imports: useCurrentFrame, useVideoConfig, interpolate, spring, Easing, Audio, Img, Video, AbsoluteFill, Sequence
5. interpolate() outputRange must contain ONLY numbers
6. All inline styles must use camelCase
7. Do NOT import Composition or registerRoot"""


class ScriptRefineWorker(QThread):
    finished = Signal(bool, str)
    MAX_RETRIES = 3

    def __init__(self, api_key, endpoint, service, model, script_content, instruction):
        super().__init__()
        self.api_key = api_key
        self.endpoint = endpoint
        self.service = service
        self.model = model
        self.script_content = script_content
        self.instruction = instruction

    def _call_ai(self, prompt):
        import os, json
        svc = (self.service or '').lower()
        ep = (self.endpoint or '').strip()
        if ep:
            from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
            return CustomEndpointHelper.call_endpoint(self.api_key, ep, svc, self.model, prompt, timeout=120)
        elif svc == 'gemini':
            import google.genai as genai
            client = genai.Client(api_key=self.api_key)
            return client.models.generate_content(model=self.model, contents=[prompt]).text
        elif svc in ('openai', 'openrouter', 'maia', 'blackbox'):
            from openai import OpenAI
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'configs', 'ai_config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                ai_config = json.load(f)
            client = OpenAI(api_key=self.api_key, base_url=ai_config['provider_endpoints'][svc])
            return client.chat.completions.create(model=self.model, messages=[{'role': 'user', 'content': prompt}]).choices[0].message.content
        elif svc == 'groq':
            from groq import Groq
            return Groq(api_key=self.api_key).chat.completions.create(model=self.model, messages=[{'role': 'user', 'content': prompt}]).choices[0].message.content
        else:
            raise ValueError(f'Unsupported service: {svc}')

    def run(self):
        try:
            from dialogs.tools.vibe_video_generator.vibe_code_actions_widget import _apply_search_replace
            full_prompt = (SCRIPT_REFINE_SYSTEM
                + '\n\nORIGINAL SCRIPT:\n' + self.script_content
                + '\n\nINSTRUCTION:\n' + self.instruction)
            for attempt in range(1, self.MAX_RETRIES + 1):
                print(f'[Vibe Video] Refine attempt {attempt}/{self.MAX_RETRIES}')
                text = self._call_ai(full_prompt)
                patched = _apply_search_replace(self.script_content, text)
                if patched:
                    print(f'[Vibe Video] Refine applied via SEARCH/REPLACE (attempt {attempt})')
                    self.finished.emit(True, patched)
                    return
                import re
                for pattern in [r'```(?:tsx?|typescript|javascript)\s*\n(.*?)```', r'```\s*\n(.*?)```']:
                    match = re.search(pattern, text, re.DOTALL)
                    if match:
                        code = match.group(1).strip()
                        if 'import' in code or 'export' in code:
                            print(f'[Vibe Video] Refine applied via full code fallback (attempt {attempt})')
                            self.finished.emit(True, code)
                            return
                print(f'[Vibe Video] Refine attempt {attempt} unusable, retrying...')
            self.finished.emit(False, f'AI failed to produce a valid refinement after {self.MAX_RETRIES} attempts')
        except Exception as e:
            print(f'[Vibe Video] Refine error: {e}')
            self.finished.emit(False, str(e))


class RefineRetryDialog(QDialog):
    retry_requested = Signal()

    def __init__(self, parent, last_instruction):
        super().__init__(parent)
        self.setWindowTitle('Refine Failed')
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        icon_row = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon('fa6s.circle-xmark', color='#e05555').pixmap(28, 28))
        icon_row.addWidget(icon_label)
        icon_row.addSpacing(8)
        msg = QLabel(f'AI failed to refine the script.\nInstruction: "{last_instruction}"')
        msg.setWordWrap(True)
        icon_row.addWidget(msg, 1)
        layout.addLayout(icon_row)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        retry_btn = QPushButton('Try Again')
        retry_btn.setIcon(qta.icon('fa6s.wand-magic-sparkles'))
        retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        retry_btn.clicked.connect(self._on_retry)
        btn_row.addWidget(retry_btn)
        ok_btn = QPushButton('Cancel')
        ok_btn.setIcon(qta.icon('fa6s.xmark'))
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def _on_retry(self):
        self.retry_requested.emit()
        self.accept()


class ScriptRefineDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Refine Script')
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Describe what you want to change or add:'))
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText('e.g. Add a pulsing red circle in the center')
        self.prompt_input.setMinimumHeight(34)
        layout.addWidget(self.prompt_input)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton('Cancel')
        cancel_btn.setIcon(qta.icon('fa6s.xmark'))
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        self.refine_btn = QPushButton('Refine')
        self.refine_btn.setIcon(qta.icon('fa6s.wand-magic-sparkles'))
        self.refine_btn.setDefault(True)
        self.refine_btn.clicked.connect(self._on_refine)
        btn_row.addWidget(self.refine_btn)
        layout.addLayout(btn_row)

    def _on_refine(self):
        if not self.prompt_input.text().strip():
            self.prompt_input.setFocus()
            return
        self.accept()

    def get_instruction(self):
        return self.prompt_input.text().strip()


class ScriptsWidget(QWidget):
    script_updated = Signal(object)
    script_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = parent.db if parent else None
        self.current_script_id = None
        self.current_script_name = None
        self._ai_key = ''
        self._ai_endpoint = ''
        self._ai_service = ''
        self._ai_model = ''
        self._refine_worker = None
        self._last_instruction = ''
        self._last_clicked_line = -1
        self._ctrl_selected_lines = set()  # Track lines selected with Ctrl
        self.line_number_area = None
        self._is_closing = False
        self._original_content = ''  # Track original content for change detection
        self._setup_ui()
        self._apply_theme()

    def set_ai_credentials(self, api_key, endpoint, service, model):
        self._ai_key = api_key
        self._ai_endpoint = endpoint
        self._ai_service = service
        self._ai_model = model

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Toolbar with Open in Browser button only (mirrors Preview tab)
        toolbar = QHBoxLayout()
        self.open_browser_btn = QPushButton('Open in Browser')
        self.open_browser_btn.setIcon(qta.icon('fa6s.arrow-up-right-from-square'))
        self.open_browser_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_browser_btn.setEnabled(False)
        self.open_browser_btn.clicked.connect(self._on_open_browser)
        toolbar.addWidget(self.open_browser_btn)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        # Editor container with line numbers
        editor_container = QWidget()
        editor_layout = QHBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        self.script_content = QTextEdit()
        self.script_content.setReadOnly(True)
        self.script_content.setFontFamily("Courier New")
        self.script_content.setFontPointSize(10)
        self.script_content.setAcceptRichText(False)

        self.line_number_area = LineNumberArea(self.script_content)
        editor_layout.addWidget(self.line_number_area)
        editor_layout.addWidget(self.script_content)

        layout.addWidget(editor_container)

        # Script name label below editor (like status label in Preview tab)
        self.script_name_label = QLabel('No script selected')
        layout.addWidget(self.script_name_label)

        self.highlighter = TypeScriptHighlighter(self.script_content.document())
        
        # Connect signals for line number updates
        self.script_content.document().blockCountChanged.connect(self._update_line_numbers)
        self.script_content.verticalScrollBar().valueChanged.connect(self.line_number_area.update)
        self.script_content.textChanged.connect(self._update_line_count)
        self.script_content.textChanged.connect(self._update_save_button_state)
        
        # Enable mouse tracking for line number clicks
        self.line_number_area.mousePressEvent = self._line_number_mouse_press
        self.line_number_area.mouseMoveEvent = self._line_number_mouse_move
        self.line_number_area.mouseReleaseEvent = self._line_number_mouse_release
        self.line_number_area.setMouseTracking(True)

        # Studio management for Open in Browser feature
        self._studio_worker = None
        self._studio_running = False
        self._studio_port = None
        self._preview_dir_for_studio = None
        self._studio_retry_count = 0
        self._studio_retry_timer = None

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat('AI is refining the script...')
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.refine_btn = QPushButton('Refine')
        self.refine_btn.setIcon(qta.icon('fa6s.wand-magic-sparkles'))
        self.refine_btn.setEnabled(False)
        self.refine_btn.clicked.connect(self._on_refine)
        btn_layout.addWidget(self.refine_btn)
        self.clear_btn = QPushButton('Clear')
        self.clear_btn.setIcon(qta.icon('fa6s.eraser'))
        self.clear_btn.setEnabled(False)
        self.clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(self.clear_btn)
        self.paste_btn = QPushButton('Paste')
        self.paste_btn.setIcon(qta.icon('fa6s.paste'))
        self.paste_btn.setEnabled(False)
        self.paste_btn.clicked.connect(self._on_paste)
        btn_layout.addWidget(self.paste_btn)
        self.save_btn = QPushButton('Save')
        self.save_btn.setIcon(qta.icon('fa6s.floppy-disk'))
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    def _apply_theme(self):
        styles, default_text, bg = get_theme_colors()
        palette = self.script_content.palette()
        palette.setColor(palette.ColorRole.Base, bg)
        palette.setColor(palette.ColorRole.Text, default_text)
        self.script_content.setPalette(palette)
        self.highlighter.update_theme()
        # Update line number area styling
        if self.line_number_area:
            self.line_number_area.update()
            self.line_number_area.update_width()
        self.script_name_label.setStyleSheet(f'color: {theme.get_color("text_dark")}; padding: 4px;')

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.PaletteChange:
            self._apply_theme()

    def _update_save_button_state(self):
        """Enable or disable save button based on content changes."""
        if not self.current_script_id:
            self.save_btn.setEnabled(False)
            return
        current = self.script_content.toPlainText()
        has_changes = current != self._original_content
        self.save_btn.setEnabled(has_changes)

    def _update_line_numbers(self):
        if self.line_number_area:
            self.line_number_area.update_width()
            self.line_number_area.update()

    def _update_line_count(self):
        # Update line count when text changes
        if self.line_number_area:
            self.line_number_area._update_count()
        if self.current_script_name:
            content = self.script_content.toPlainText()
            line_count = len(content.splitlines()) if content else 0
            self.script_name_label.setText(f"Script: {self.current_script_name}  |  {line_count} lines")

    def _line_number_mouse_press(self, event):
        """Handle mouse press on line number area"""
        if event.button() != Qt.MouseButton.LeftButton:
            return
        
        line = self._get_line_at_position(event.pos().y())
        if line < 0:
            return
        
        # Ensure editor has focus
        self.script_content.setFocus()
        
        is_ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        is_shift = event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        
        block = self.script_content.document().findBlockByNumber(line)
        block_start = block.position()
        block_end = block.position() + block.length() - 1
        
        if is_ctrl and not is_shift:
            # Ctrl+click: toggle individual line selection (non-contiguous)
            if line in self._ctrl_selected_lines:
                # Deselect this line
                self._ctrl_selected_lines.discard(line)
            else:
                # Add this line to individual selection
                self._ctrl_selected_lines.add(line)
            self._last_clicked_line = line
            self._update_extra_selections()
        else:
            # Normal click or Shift+click: contiguous selection
            cursor = self.script_content.textCursor()
            
            if is_shift and self._last_clicked_line >= 0:
                # Shift+click: select range from last clicked line to current line
                start_line = min(self._last_clicked_line, line)
                end_line = max(self._last_clicked_line, line)
                start_block = self.script_content.document().findBlockByNumber(start_line)
                end_block = self.script_content.document().findBlockByNumber(end_line)
                cursor.setPosition(start_block.position())
                cursor.setPosition(end_block.position() + end_block.length() - 1, cursor.MoveMode.KeepAnchor)
                # Clear Ctrl individual selections on normal/shift selection
                self._ctrl_selected_lines.clear()
            else:
                # Single click: select just this line
                cursor.setPosition(block_start)
                cursor.setPosition(block_end, cursor.MoveMode.KeepAnchor)
                # Clear Ctrl individual selections
                self._ctrl_selected_lines.clear()
            
            self.script_content.setTextCursor(cursor)
            self._last_clicked_line = line
            self._update_extra_selections()

    def _line_number_mouse_move(self, event):
        """Handle mouse drag on line number area"""
        if event.buttons() & Qt.MouseButton.LeftButton and self._last_clicked_line >= 0:
            line = self._get_line_at_position(event.pos().y())
            if line >= 0 and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                # Only drag for normal selection, not Ctrl multi-select
                cursor = self.script_content.textCursor()
                start_line = min(self._last_clicked_line, line)
                end_line = max(self._last_clicked_line, line)
                start_block = self.script_content.document().findBlockByNumber(start_line)
                end_block = self.script_content.document().findBlockByNumber(end_line)
                cursor.setPosition(start_block.position())
                cursor.setPosition(end_block.position() + end_block.length() - 1, cursor.MoveMode.KeepAnchor)
                self.script_content.setTextCursor(cursor)

    def _line_number_mouse_release(self, event):
        """Handle mouse release"""
        pass

    def _update_extra_selections(self):
        """Update extra selections for Ctrl+clicked individual lines"""
        selections = []
        
        # Get theme color for selection (use primary color)
        primary_color = theme.get_color('primary')
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(primary_color))
        fmt.setForeground(QColor('white'))
        
        for line in sorted(self._ctrl_selected_lines):
            block = self.script_content.document().findBlockByNumber(line)
            if block.isValid():
                cursor = QTextCursor(block)
                cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
                selection = QTextEdit.ExtraSelection()
                selection.cursor = cursor
                selection.format = fmt
                selections.append(selection)
        
        self.script_content.setExtraSelections(selections)

    def _get_line_at_position(self, y_pos):
        """Convert y coordinate to line number"""
        block = self.script_content.document().firstBlock()
        block_number = 0
        
        while block.isValid():
            block_rect = self.script_content.document().documentLayout().blockBoundingRect(block)
            top = int(block_rect.top())
            bottom = int(top + block_rect.height())
            
            # Adjust for scroll position
            scroll_y = self.script_content.verticalScrollBar().value()
            top -= scroll_y
            bottom -= scroll_y
            
            if top <= y_pos < bottom:
                return block_number
            
            block = block.next()
            block_number += 1
        
        return -1

    def display_script(self, script_data):
        self.current_script_id = script_data.get('id') if script_data else None
        self.current_script_name = script_data.get('name') if script_data else None
        has_script = script_data is not None
        self.clear_btn.setEnabled(has_script)
        self.save_btn.setEnabled(False)  # Always disabled initially until change detected
        self.refine_btn.setEnabled(has_script)
        self.open_browser_btn.setEnabled(has_script)
        self.paste_btn.setEnabled(has_script)
        self.script_content.setReadOnly(not has_script)
        if script_data:
            content = script_data.get('script_content', '')
            line_count = len(content.splitlines())
            self.script_name_label.setText(f"Script: {script_data.get('name', 'Unnamed')}  |  {line_count} lines")
            # Only update content if changed, and block signals to avoid unwanted textChanged
            if self.script_content.toPlainText() != content:
                self.script_content.blockSignals(True)
                self.script_content.setPlainText(content)
                self.script_content.blockSignals(False)
                self._update_line_numbers()
                self._update_line_count()
            # Store original content for change detection
            self._original_content = content
            self._update_save_button_state()
            self.script_selected.emit(script_data.get('name', ''))
        else:
            self.script_name_label.setText('No script selected')
            self._original_content = ''
            self.save_btn.setEnabled(False)
            self.paste_btn.setEnabled(False)
            self.script_selected.emit('')
            self.script_content.clear()

    def update_script_name(self, new_name):
        self.current_script_name = new_name
        if new_name:
            content = self.script_content.toPlainText()
            line_count = len(content.splitlines()) if content else 0
            self.script_name_label.setText(f"Script: {new_name}  |  {line_count} lines")

    def _on_clear(self):
        self.script_content.clear()

    def _on_refine(self):
        if not self._ai_key:
            QMessageBox.warning(self, 'API Key Required', 'Please select an API key in the main dialog first.')
            return
        dlg = ScriptRefineDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        instruction = dlg.get_instruction()
        self._last_instruction = instruction
        current_code = self.script_content.toPlainText().strip()
        if not current_code:
            return
        self.refine_btn.setEnabled(False)
        self.refine_btn.setText('Refining...')
        self.refine_btn.setIcon(qta.icon('fa6s.spinner', animation=qta.Spin(self.refine_btn)))
        self.clear_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self._refine_worker = ScriptRefineWorker(
            self._ai_key, self._ai_endpoint, self._ai_service, self._ai_model,
            current_code, instruction
        )
        self._refine_worker.finished.connect(self._on_refine_finished)
        self._refine_worker.start()

    def _on_refine_finished(self, success, result):
        if self._is_closing:
            return
        worker = self._refine_worker
        self._refine_worker = None
        if worker:
            worker.quit()
            worker.wait(2000)
            worker.deleteLater()

        self.refine_btn.setEnabled(True)
        self.refine_btn.setText('Refine')
        self.refine_btn.setIcon(qta.icon('fa6s.wand-magic-sparkles'))
        self.clear_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        if not success:
            print(f'[Vibe Video] Refine failed: {result}')
            dlg = RefineRetryDialog(self, self._last_instruction)
            dlg.retry_requested.connect(self._on_retry_refine)
            dlg.exec()
            # If no retry was started, restore save button state based on current changes
            if self._refine_worker is None:
                self._update_save_button_state()
            return
        if self.db and self.current_script_id:
            self.db.update_remotion_script(script_id=self.current_script_id, script_content=result)
            script_data = self.db.get_remotion_script(self.current_script_id)
            print(f'[Vibe Video] Script refined and saved')
            if script_data:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(50, lambda: self._apply_refine_result(script_data))

    def _apply_refine_result(self, script_data):
        if self._is_closing:
            return
        content = script_data.get('script_content', '')
        line_count = len(content.splitlines())
        self.script_name_label.setText(f"Script: {script_data.get('name', 'Unnamed')}  |  {line_count} lines")
        # Block signals to avoid triggering textChanged during programmatic update
        self.script_content.blockSignals(True)
        self.script_content.setPlainText(content)
        self.script_content.blockSignals(False)
        self._update_line_numbers()
        self._update_line_count()
        # Auto-save the refined script
        if self.db and self.current_script_id:
            try:
                self.db.update_remotion_script(
                    script_id=self.current_script_id,
                    script_content=content
                )
                # Update original content tracking after successful save
                self._original_content = content
            except Exception as e:
                print(f"[Vibe Video] Auto-save after refine failed: {e}")
        self._update_save_button_state()
        self.script_updated.emit(script_data)

    def _on_retry_refine(self):
        current_code = self.script_content.toPlainText().strip()
        if not current_code or not self._last_instruction:
            return
        self.refine_btn.setEnabled(False)
        self.refine_btn.setText('Refining...')
        self.refine_btn.setIcon(qta.icon('fa6s.spinner', animation=qta.Spin(self.refine_btn)))
        self.clear_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self._refine_worker = ScriptRefineWorker(
            self._ai_key, self._ai_endpoint, self._ai_service, self._ai_model,
            current_code, self._last_instruction
        )
        self._refine_worker.finished.connect(self._on_refine_finished)
        self._refine_worker.start()

    def _on_save(self):
        try:
            if not self.db or not self.current_script_id:
                return
            current_text = self.script_content.toPlainText()
            script_content = current_text.strip()
            if not script_content:
                QMessageBox.warning(self, 'Validation Error', 'TypeScript content cannot be empty.')
                self.script_content.setFocus()
                return

            # Check if content has changed before updating DB
            if current_text == self._original_content:
                # No changes to save
                return

            self.db.update_remotion_script(
                script_id=self.current_script_id,
                script_content=script_content
            )
            script_data = self.db.get_remotion_script(self.current_script_id)
            if script_data:
                self.update_script_name(script_data.get('name'))
                # Update original content tracking after successful save
                self._original_content = current_text
                self._update_save_button_state()
            self.script_updated.emit(script_data)
        except Exception as e:
            QMessageBox.critical(self, 'Save Error', f'Failed to save script:\n{str(e)}')

    def _on_paste(self):
        """Replace editor content with clipboard text."""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.script_content.setPlainText(text)
            self.script_content.setFocus()

    def _on_open_browser(self):
         """Open Remotion Studio in browser for the current script."""
         # Walk up the parent chain to find the dialog that has preview_tab_widget
         p = self.parent()
         while p is not None:
             if hasattr(p, 'preview_tab_widget'):
                 p.preview_tab_widget._on_open_browser()
                 return
             p = p.parent()
         # If not found, do nothing (or could log warning)

    def _on_studio_ready(self, port):
        """Called when Remotion Studio is ready."""
        if self._is_closing:
            return
        worker = self.sender()
        if worker is not self._studio_worker:
            return
        self._studio_port = port
        self._studio_running = True
        self._studio_retry_count = 0
        if self._studio_retry_timer:
            self._studio_retry_timer.stop()
            self._studio_retry_timer = None
        self.open_browser_btn.setEnabled(True)
        self.open_browser_btn.setText('Open in Browser')
        import webbrowser
        webbrowser.open(f'http://127.0.0.1:{port}')

    def _on_studio_failed(self, error):
        """Called when Remotion Studio fails to start."""
        if self._is_closing:
            return
        worker = self.sender()
        if worker is not self._studio_worker:
            return
        self._studio_running = False
        self._studio_worker = None
        self.open_browser_btn.setEnabled(True)
        self.open_browser_btn.setText('Open in Browser')
        if self._studio_retry_count < 3:
            self._studio_retry_count += 1
            print(f'[PreviewTab] Studio failed ({error}), retrying ({self._studio_retry_count}/3)...')
            # Schedule retry with cancellable timer
            if self._studio_retry_timer:
                self._studio_retry_timer.stop()
            self._studio_retry_timer = QTimer(self)
            self._studio_retry_timer.setSingleShot(True)
            self._studio_retry_timer.timeout.connect(self._retry_start_studio)
            self._studio_retry_timer.start(1000 * self._studio_retry_count)
        else:
            QMessageBox.critical(self, 'Studio Failed', f'Failed to start Remotion Studio:\n{error}')
            self._studio_retry_count = 0
            if self._studio_retry_timer:
                self._studio_retry_timer.stop()
                self._studio_retry_timer = None
            self._studio_retry_count = 0

    def _retry_start_studio(self):
        """Retry starting Remotion Studio after failure."""
        if self._is_closing:
            return
        # Avoid duplicate starts
        if self._studio_running:
            return
        if not hasattr(self, '_preview_dir_for_studio') or not self._preview_dir_for_studio:
            return
        self._studio_port = self._find_free_port(3100)
        from dialogs.tools.vibe_video_generator.vibe_video_preview_tab import StudioServerWorker
        self._studio_worker = StudioServerWorker(self._preview_dir_for_studio, self._studio_port)
        self._studio_worker.server_ready.connect(self._on_studio_ready)
        self._studio_worker.server_failed.connect(self._on_studio_failed)
        self._studio_worker.start()
        self._studio_running = True
        self.open_browser_btn.setEnabled(False)
        self.open_browser_btn.setText('Starting...')

    def _find_free_port(self, start=3100):
        """Find an available port starting from start."""
        import socket
        for port in range(start, start + 20):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('127.0.0.1', port))
                    return port
                except OSError:
                    continue
        return start

    def cleanup(self):
        """Clean up resources (call when dialog closes)."""
        self._is_closing = True
        if self._refine_worker:
            self._refine_worker.quit()
            if not self._refine_worker.wait(2000):
                print("[Vibe Video] Refine worker still running after 2s, terminating.")
                self._refine_worker.terminate()
                self._refine_worker.wait()
            self._refine_worker.deleteLater()
            self._refine_worker = None
