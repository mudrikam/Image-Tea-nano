from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTextEdit, QHBoxLayout, QPushButton, QMessageBox, QLabel, QApplication, QProgressBar, QGroupBox)
from PySide6.QtCore import Qt, Signal, QRegularExpression, QThread, QTimer, QRect, QSize, QPoint
from PySide6.QtGui import QTextCharFormat, QColor, QFont, QSyntaxHighlighter, QPalette, QPainter, QTextCursor, QShortcut, QKeySequence
import qtawesome as qta
from ui.theme_system import theme
from pygments import lex
from pygments.lexers import TypeScriptLexer
from pygments.token import Token
import difflib

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


class ScriptRefineWorker(QThread):
    finished = Signal(bool, str)
    progress = Signal(str)
    turn_completed = Signal(int, str)  # (turn_number, script_content)

    def __init__(self, api_key, endpoint, service, model, script_content, instruction):
        super().__init__()
        self.api_key = api_key
        self.endpoint = endpoint
        self.service = service
        self.model = model
        self.script_content = script_content
        self.instruction = instruction

    def _call_ai(self, prompt):
        from helpers.remotion_helper.remotion_ai_client import call_remotion_ai
        return call_remotion_ai(
            self.api_key, self.endpoint, self.service, self.model, prompt, timeout=45
        )

    def run(self):
        from helpers.remotion_helper.remotion_refine_agent import RemotionRefineAgent

        def emit_step(step):
            self.progress.emit(step.message)

        try:
            self.progress.emit('Agent: inspecting the current Remotion file.')
            agent = RemotionRefineAgent(
                self._call_ai,
                self.script_content,
                self.instruction,
                emit_step=emit_step,
            )
            result = agent.run()
            if result.success:
                self.progress.emit('Agent: validated edit and completed the refinement.')
                self.turn_completed.emit(1, result.script)
                self.finished.emit(True, result.script)
            else:
                self.finished.emit(False, result.message)
        except Exception as exc:
            self.progress.emit(f'Agent crashed: {exc}')
            self.finished.emit(False, str(exc))

class ScriptTextEdit(QTextEdit):
    """QTextEdit that supports standard undo/redo shortcuts even when read-only."""

    def keyPressEvent(self, event):
        ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        key = event.key()
        if ctrl and key == Qt.Key.Key_Z:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                if self.document().isRedoAvailable():
                    self.redo()
            elif self.document().isUndoAvailable():
                self.undo()
            return
        if ctrl and key == Qt.Key.Key_Y:
            if self.document().isRedoAvailable():
                self.redo()
            return
        super().keyPressEvent(event)


class ScriptsWidget(QWidget):
    script_updated = Signal(object)
    script_selected = Signal(str)
    refine_started = Signal()
    refine_finished = Signal()

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
        self._refine_previous_content = ''
        self._refine_panel = None
        self._refine_session_context = []
        self._last_refine_error = ''
        self._pending_preview_error = ''
        self._fix_pass_active = False
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

    def set_refine_panel(self, panel):
        self._refine_panel = panel

    def _get_generator_dialog(self):
        parent = self.parentWidget()
        while parent is not None:
            if hasattr(parent, 'show_refine_panel'):
                return parent
            parent = parent.parentWidget()
        return None

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Open in Browser button + action buttons on a single row
        self.open_browser_btn = QPushButton('Open in Browser')
        self.open_browser_btn.setIcon(qta.icon('fa6s.arrow-up-right-from-square'))
        self.open_browser_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_browser_btn.setEnabled(False)
        self.open_browser_btn.clicked.connect(self._on_open_browser)

        self._setup_action_buttons(layout)

        # Editor container with line numbers
        editor_container = QWidget()
        editor_layout = QHBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        self.script_content = ScriptTextEdit()
        self.script_content.setReadOnly(True)
        self.script_content.setFontFamily("Courier New")
        self.script_content.setFontPointSize(10)
        self.script_content.setAcceptRichText(False)

        self.line_number_area = LineNumberArea(self.script_content)
        editor_layout.addWidget(self.line_number_area)
        editor_layout.addWidget(self.script_content)

        layout.addWidget(editor_container)

        # Status label for AI operations (below editor)
        self.ai_status_label = QLabel('')
        self.ai_status_label.setStyleSheet('color: #888; font-size: 11px;')
        self.ai_status_label.setVisible(False)  # hidden by default
        layout.addWidget(self.ai_status_label)

        # Script name label (keep but move lower or integrate)
        self.script_name_label = QLabel('No script selected')
        layout.addWidget(self.script_name_label)

        self.highlighter = TypeScriptHighlighter(self.script_content.document())
        
        # Connect signals for line number updates
        self.script_content.document().blockCountChanged.connect(self._update_line_numbers)
        self.script_content.verticalScrollBar().valueChanged.connect(self.line_number_area.update)
        self.script_content.textChanged.connect(self._update_line_count)
        self.script_content.textChanged.connect(self._update_save_button_state)
        # Enable undo/redo and connect availability signals
        self.script_content.setUndoRedoEnabled(True)
        self.script_content.document().undoAvailable.connect(self._update_undo_redo_buttons)
        self.script_content.document().redoAvailable.connect(self._update_undo_redo_buttons)
        
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

        # Keyboard shortcut for save (Ctrl+S)
        self._save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        self._save_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._save_shortcut.activated.connect(self._on_save)

    def _setup_action_buttons(self, layout):
        """Create the action buttons (Refine, Undo, Redo, Clear, Paste, Save)."""
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.open_browser_btn)
        btn_layout.addStretch()

        self.refine_btn = QPushButton('Refine')
        self.refine_btn.setIcon(qta.icon('fa6s.wand-magic-sparkles'))
        self.refine_btn.setEnabled(False)
        self.refine_btn.clicked.connect(self._on_refine)
        btn_layout.addWidget(self.refine_btn)

        self.interrupt_btn = QPushButton('Interrupt')
        self.interrupt_btn.setIcon(qta.icon('fa6s.stop'))
        self.interrupt_btn.setEnabled(False)
        self.interrupt_btn.clicked.connect(self._on_interrupt)
        self.interrupt_btn.setVisible(False)  # Hidden by default
        btn_layout.addWidget(self.interrupt_btn)

        # Undo/Redo buttons for AI changes
        self.undo_btn = QPushButton('Undo')
        self.undo_btn.setIcon(qta.icon('fa6s.rotate-left'))
        self.undo_btn.setToolTip('Undo last change (Ctrl+Z)')
        self.undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.undo_btn.setEnabled(False)
        self.undo_btn.clicked.connect(self._on_undo)
        btn_layout.addWidget(self.undo_btn)

        self.redo_btn = QPushButton('Redo')
        self.redo_btn.setIcon(qta.icon('fa6s.rotate-right'))
        self.redo_btn.setToolTip('Redo undone change (Ctrl+Y)')
        self.redo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.redo_btn.setEnabled(False)
        self.redo_btn.clicked.connect(self._on_redo)
        btn_layout.addWidget(self.redo_btn)

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

    def _update_undo_redo_buttons(self):
        """Update undo/redo button states based on document's undo/redo availability."""
        doc = self.script_content.document()
        self.undo_btn.setEnabled(doc.isUndoAvailable())
        self.redo_btn.setEnabled(doc.isRedoAvailable())

    def _replace_content_undoable(self, new_content: str):
        """Replace entire editor content as a single undoable action."""
        cursor = self.script_content.textCursor()
        cursor.beginEditBlock()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(new_content)
        cursor.endEditBlock()

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

    def display_script(self, script_data, from_ai: bool = False):
        new_script_id = script_data.get('id') if script_data else None
        new_script_name = script_data.get('name') if script_data else None

        # Update current identifiers
        self.current_script_id = new_script_id
        self.current_script_name = new_script_name
        has_script = script_data is not None
        self.clear_btn.setEnabled(has_script)
        self.save_btn.setEnabled(False)
        self.refine_btn.setEnabled(has_script)
        self.open_browser_btn.setEnabled(has_script)
        self.paste_btn.setEnabled(has_script)
        self.script_content.setReadOnly(not has_script)

        if script_data:
            content = script_data.get('script_content', '')
            line_count = len(content.splitlines())
            self.script_name_label.setText(f"Script: {new_script_name or 'Unnamed'}  |  {line_count} lines")

            if self.script_content.toPlainText() != content:
                if from_ai:
                    # Replace with undoable command for AI changes
                    self.script_content.blockSignals(True)
                    self._replace_content_undoable(content)
                    self.script_content.blockSignals(False)
                else:
                    # Normal script selection: clear undo stack and set directly
                    self.script_content.blockSignals(True)
                    self.script_content.setPlainText(content)  # this clears undo stack
                    self.script_content.blockSignals(False)
                self._update_line_numbers()
                self._update_line_count()
            self._original_content = content
            self._update_save_button_state()
            self.script_selected.emit(new_script_name or '')
        else:
            self.script_name_label.setText('No script selected')
            self._original_content = ''
            self.save_btn.setEnabled(False)
            self.paste_btn.setEnabled(False)
            self.script_selected.emit('')
            self.script_content.clear()

        self._update_undo_redo_buttons()

    def update_script_name(self, new_name):
        self.current_script_name = new_name
        if new_name:
            content = self.script_content.toPlainText()
            line_count = len(content.splitlines()) if content else 0
            self.script_name_label.setText(f"Script: {new_name}  |  {line_count} lines")

    def _on_clear(self):
        self.script_content.clear()

    def _on_refine(self):
        if self._refine_panel:
            dialog = self._get_generator_dialog()
            if dialog:
                dialog.show_refine_panel()
            self._refine_panel.input.setFocus()

    def refine_instruction(self, instruction, is_fix=False):
        instruction = (instruction or '').strip()
        current_code = self.script_content.toPlainText().strip()
        if not self.current_script_id or not current_code:
            if self._refine_panel:
                self._refine_panel.add_status('Select a script with content before refining.', False)
                self._refine_panel.set_busy(False)
            return
        if not self._ai_key:
            if self._refine_panel:
                self._refine_panel.add_status('Select an API key in the main window before refining.', False)
                self._refine_panel.set_busy(False)
            return
        if self._refine_worker:
            # Do not drop a preview error while an automatic/user refinement is
            # still running. Queue the latest error and process it when the
            # worker finishes instead of making Fix Errors appear unresponsive.
            if self._last_refine_error:
                self._pending_preview_error = self._last_refine_error
            return

        self._last_instruction = instruction
        self._last_refine_error = ''
        self._fix_pass_active = is_fix
        self._refine_previous_content = current_code
        context = '\n'.join(self._refine_session_context[-8:])
        worker_instruction = instruction
        if context:
            worker_instruction = (
                'Previous refinement session context:\n'
                f'{context}\n\nCurrent user instruction:\n{instruction}'
            )
        self.refine_btn.setEnabled(False)
        self.refine_btn.setVisible(False)
        self.interrupt_btn.setEnabled(True)
        self.interrupt_btn.setVisible(True)
        self.clear_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self._refine_worker = ScriptRefineWorker(
            self._ai_key, self._ai_endpoint, self._ai_service, self._ai_model,
            current_code, worker_instruction
        )
        self._refine_worker.progress.connect(self._on_refine_progress)
        self._refine_worker.turn_completed.connect(self._on_turn_completed)
        self._refine_worker.finished.connect(self._on_refine_finished)
        self._refine_worker.start()
        self.refine_started.emit()

    def _on_refine_progress(self, message):
        if self._is_closing:
            return
        if self.current_script_name:
            content = self.script_content.toPlainText()
            line_count = len(content.splitlines()) if content else 0
            
            # Truncate the message if it's too long to prevent GUI stretch
            display_msg = message if len(message) <= 60 else message[:57] + "..."
            
            self.script_name_label.setText(f"Script: {self.current_script_name}  |  {line_count} lines  |  {display_msg}")
        if self._refine_panel:
            self._refine_panel.add_step(message)

    def _on_turn_completed(self, turn, script):
        """Simpan progress tiap turn ke DB dan update preview."""
        if self.db and self.current_script_id:
            try:
                self.db.update_remotion_script(
                    script_id=self.current_script_id,
                    script_content=script
                )
                # Update editor hanya jika konten berubah (hindari reset cursor)
                current_display = self.script_content.toPlainText()
                if current_display != script:
                    self.script_content.blockSignals(True)
                    self._replace_content_undoable(script)
                    self.script_content.blockSignals(False)
                self._original_content = script
                self._update_save_button_state()
                self._update_line_numbers()
                self._update_line_count()
                if self._refine_panel:
                    old_lines = self._refine_previous_content.splitlines()
                    new_lines = script.splitlines()
                    added = sum(1 for change in difflib.ndiff(old_lines, new_lines) if change.startswith('+ '))
                    removed = sum(1 for change in difflib.ndiff(old_lines, new_lines) if change.startswith('- '))
                    self._refine_panel.add_change(turn, self._last_instruction, added, removed)
                    self._refine_session_context.append(
                        f'Turn {turn}: Added {added} lines, Removed {removed} lines.'
                    )
                self._refine_previous_content = script
                print(f"[Vibe Video] Turn {turn} disimpan ke database.")
            except Exception as e:
                print(f"[Vibe Video] Gagal simpan turn {turn}: {e}")

    def _on_interrupt(self):
        """Handle interrupt button click."""
        if self._refine_worker:
            # Terminate the worker thread forcefully
            self._refine_worker.terminate()
            self._refine_worker.wait(2000)
            self._refine_worker.deleteLater()
            self._refine_worker = None
            print("[Vibe Video] Refinement interrupted by user.")

        # Restore UI state
        self.refine_btn.setEnabled(True)
        self.refine_btn.setText('Refine')
        self.refine_btn.setIcon(qta.icon('fa6s.wand-magic-sparkles'))
        self.refine_btn.setVisible(True)
        self.interrupt_btn.setEnabled(False)
        self.interrupt_btn.setVisible(False)
        self.clear_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        if self._refine_panel:
            self._refine_panel.set_busy(False)
            self._refine_panel.add_status('Refinement interrupted.', False)
        self.refine_finished.emit()

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
        self.refine_btn.setVisible(True)
        self.interrupt_btn.setEnabled(False)
        self.interrupt_btn.setVisible(False)
        self.clear_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        if self._refine_panel:
            self._refine_panel.set_busy(False)
        self.refine_finished.emit()
        if not success:
            print(f'[Vibe Video] Refine failed: {result}')
            if self._refine_panel:
                self._refine_panel.add_status(f'AI failed to refine the script: {result}', False)
                self._refine_panel.show_retry(True)
            pending_error = self._pending_preview_error
            self._pending_preview_error = ''
            if pending_error and not self._fix_pass_active:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self.fix_preview_error(pending_error))
            self._fix_pass_active = False
            return
        if self.db and self.current_script_id:
            self.db.update_remotion_script(script_id=self.current_script_id, script_content=result)
            script_data = self.db.get_remotion_script(self.current_script_id)
            print(f'[Vibe Video] Script refined and saved')
            if script_data:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(50, lambda: self._apply_refine_result(script_data))

        if self._refine_panel:
            self._refine_panel.add_status('Refinement completed.', True)
        pending_error = self._pending_preview_error
        self._pending_preview_error = ''
        # Only re-trigger an error-fix pass for errors that arrived during a
        # *normal* refinement. A fix pass that just finished must not re-queue
        # the same error, otherwise the agent loops forever on an unresolved
        # preview error.
        if pending_error and not self._fix_pass_active:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.fix_preview_error(pending_error))
        self._fix_pass_active = False

    def retry_refine(self):
        if self._last_instruction and not self._refine_worker:
            if self._refine_panel:
                self._refine_panel.add_step('Retrying the last refinement instruction.')
                self._refine_panel.set_busy(True)
            self.refine_instruction(self._last_instruction)

    def fix_preview_error(self, error):
        error = (error or '').strip()
        if not error:
            return
        self._last_refine_error = error
        instruction = (
            'Fix the current Remotion runtime error below. This is an error-repair pass, '
            'not a visual redesign. Inspect the exact component and call site named by '
            'the error, make the smallest safe change that removes the error, and keep '
            'the existing visual behavior. For missing-parameter errors, verify the '
            'function signature and pass the required runtime values such as frame, fps, '
            'or width explicitly (for example render <MainScene frame={frame} /> when the '
            'parent already has a frame variable). Use find_text to locate the named '
            'component or call site if you are not certain where it is defined. The full '
            'current component source is already provided. Return executable SEARCH/REPLACE '
            'blocks that fix the error, not a plan or prose explanation.\n\n'
            f'REMOTION ERROR:\n{error}'
        )
        if self._refine_panel:
            self._refine_panel.add_step('Starting an error-fix pass from the latest Remotion error.')
            self._refine_panel.set_busy(True)
        self.refine_instruction(instruction, is_fix=True)

    def clear_refine_session(self):
        self._last_instruction = ''
        self._refine_previous_content = self.script_content.toPlainText()
        self._refine_session_context.clear()
        self._last_refine_error = ''

    def _apply_refine_result(self, script_data):
        if self._is_closing:
            return
        content = script_data.get('script_content', '')
        line_count = len(content.splitlines())
        self.script_name_label.setText(f"Script: {script_data.get('name', 'Unnamed')}  |  {line_count} lines")

        # Replace with undoable command (AI change)
        current_display = self.script_content.toPlainText()
        if current_display != content:
            self.script_content.blockSignals(True)
            self._replace_content_undoable(content)
            self.script_content.blockSignals(False)
        # Auto-save and update original content tracking
        if self.db and self.current_script_id:
            try:
                self.db.update_remotion_script(
                    script_id=self.current_script_id,
                    script_content=content
                )
                self._original_content = content
            except Exception as e:
                print(f"[Vibe Video] Auto-save after refine failed: {e}")
        self._update_line_numbers()
        self._update_line_count()
        self._update_save_button_state()
        self.script_updated.emit(script_data)

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

    def _on_undo(self):
        """Undo last edit (AI or manual) via Qt's undo stack."""
        if self.script_content.document().isUndoAvailable():
            self.script_content.undo()

    def _on_redo(self):
        """Redo last undone edit via Qt's redo stack."""
        if self.script_content.document().isRedoAvailable():
            self.script_content.redo()

    def _on_paste(self):
        """Replace editor content with clipboard text."""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            current = self.script_content.toPlainText()
            if current != text:
                self.script_content.blockSignals(True)
                self._replace_content_undoable(text)
                self.script_content.blockSignals(False)
                self._update_line_numbers()
                self._update_line_count()
                self._update_save_button_state()
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
        from dialogs.tools.vibe_video_generator.vibe_video_preview_tab import RemotionStudioWorker
        self._studio_worker = RemotionStudioWorker(self._preview_dir_for_studio, self._studio_port)
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

        # Stop studio worker and retry timer
        if self._studio_retry_timer:
            self._studio_retry_timer.stop()
            self._studio_retry_timer = None
        if self._studio_worker:
            self._studio_worker.quit()
            if not self._studio_worker.wait(2000):
                print("[Vibe Video] Studio worker still running after 2s, terminating.")
                self._studio_worker.terminate()
                self._studio_worker.wait()
            self._studio_worker.deleteLater()
            self._studio_worker = None
