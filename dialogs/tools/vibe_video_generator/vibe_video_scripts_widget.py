from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QHBoxLayout, QPushButton, QMessageBox, QLabel, QApplication
from PySide6.QtCore import Qt, Signal, QRegularExpression
from PySide6.QtGui import QTextCharFormat, QColor, QFont, QSyntaxHighlighter, QPalette
import qtawesome as qta
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


class ScriptsWidget(QWidget):
    script_updated = Signal(object)
    script_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = parent.db if parent else None
        self.current_script_id = None
        self.current_script_name = None
        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self.script_name_label = QLabel('No script selected')
        layout.addWidget(self.script_name_label)

        self.script_content = QTextEdit()
        self.script_content.setReadOnly(True)
        self.script_content.setFontFamily("Courier New")
        self.script_content.setFontPointSize(10)
        layout.addWidget(self.script_content)

        self.highlighter = TypeScriptHighlighter(self.script_content.document())

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.clear_btn = QPushButton('Clear')
        self.clear_btn.setIcon(qta.icon('fa6s.eraser'))
        self.clear_btn.setEnabled(False)
        self.clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(self.clear_btn)
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

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.PaletteChange:
            self._apply_theme()

    def display_script(self, script_data):
        self.current_script_id = script_data.get('id') if script_data else None
        self.current_script_name = script_data.get('name') if script_data else None
        has_script = script_data is not None
        self.clear_btn.setEnabled(has_script)
        self.save_btn.setEnabled(has_script)
        self.script_content.setReadOnly(not has_script)
        if script_data:
            self.script_name_label.setText(f"Script: {script_data.get('name', 'Unnamed')}")
            self.script_content.setPlainText(script_data.get('script_content', ''))
            self.script_selected.emit(script_data.get('name', ''))
        else:
            self.script_name_label.setText('No script selected')
            self.script_selected.emit('')
            self.script_content.clear()

    def update_script_name(self, new_name):
        self.current_script_name = new_name
        if new_name:
            self.script_name_label.setText(f"Script: {new_name}")

    def _on_clear(self):
        self.script_content.clear()

    def _on_save(self):
        if not self.db or not self.current_script_id:
            return
        script_content = self.script_content.toPlainText().strip()
        if not script_content:
            QMessageBox.warning(self, 'Validation Error', 'TypeScript content cannot be empty.')
            self.script_content.setFocus()
            return
        self.db.update_remotion_script(
            script_id=self.current_script_id,
            script_content=script_content
        )
        script_data = self.db.get_remotion_script(self.current_script_id)
        if script_data:
            self.update_script_name(script_data.get('name'))
        self.script_updated.emit(script_data)
