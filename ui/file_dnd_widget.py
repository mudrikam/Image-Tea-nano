from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QColor
from helpers.file_importer import import_files
import qtawesome as qta
import os
from ui.theme_system import theme

try:
    from PIL import Image
    PILLOW_FORMATS = set()
    for ext, fmt in Image.registered_extensions().items():
        PILLOW_FORMATS.add(ext.lower())
except ImportError:
    PILLOW_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp', '.eps', '.svg', '.pdf'}

class DragDropWidget(QWidget):
	"""
	Widget drag & drop yang dapat menerima file.
	Agar dapat digunakan, set 'on_files_dropped' ke fungsi callback yang menerima list path.
	"""
	def __init__(self, parent=None):
		super().__init__(parent)
		self.setAcceptDrops(True)
		self.on_files_dropped = None
		
		outer_layout = QVBoxLayout(self)
		outer_layout.setContentsMargins(0, 0, 0, 0)
		outer_layout.setSpacing(0)
		
		self.inner_widget = QWidget()
		self.inner_widget.setObjectName("innerWidget")
		self.inner_widget.setStyleSheet(f"QWidget#innerWidget {{ border: 2px dashed {theme.get_color('text_dark')}; border-radius: 12px; }}")
		
		layout = QVBoxLayout(self.inner_widget)
		layout.setContentsMargins(20, 20, 20, 20)
		layout.setSpacing(10)
		
		self.icon_label = QLabel()
		self.icon_label.setAlignment(Qt.AlignCenter)
		icon_color = QColor(theme.get_color('primary'))
		icon_color.setAlpha(int(0.85 * 255))
		self.icon_label.setPixmap(qta.icon("fa6s.folder-open", color=icon_color).pixmap(72, 72))
		
		self.text_label = QLabel("Add Files by Drag & Drop")
		self.text_label.setAlignment(Qt.AlignCenter)
		self.text_label.setStyleSheet(f"color: {theme.get_color('primary')}; font-size: 14pt; font-weight: bold;")
		
		self.sub_text = QLabel("Drag and drop images or videos here")
		self.sub_text.setAlignment(Qt.AlignCenter)
		self.sub_text.setStyleSheet(f"color: {theme.get_color('text_dark')}; font-size: 10pt;")
		self.sub_text.setWordWrap(True)
		
		layout.addStretch(1)
		layout.addWidget(self.icon_label)
		layout.addWidget(self.text_label)
		layout.addWidget(self.sub_text)
		layout.addStretch(1)
		
		outer_layout.addWidget(self.inner_widget)
		
		self._default_style = f"QWidget#innerWidget {{ border: 2px dashed {theme.get_color('text_dark')}; border-radius: 12px; }}"
		accept_color = QColor(theme.get_color('primary'))
		accept_color.setAlpha(int(0.9 * 255))
		reject_color = QColor(theme.get_color('error'))
		reject_color.setAlpha(int(0.9 * 255))
		self._accept_style = f"QWidget#innerWidget {{ border: 2px dashed rgba({accept_color.red()}, {accept_color.green()}, {accept_color.blue()}, 0.9); background-color: rgba({accept_color.red()}, {accept_color.green()}, {accept_color.blue()}, 0.06); border-radius: 12px; }}"
		self._reject_style = f"QWidget#innerWidget {{ border: 2px dashed rgba({reject_color.red()}, {reject_color.green()}, {reject_color.blue()}, 0.9); background-color: rgba({reject_color.red()}, {reject_color.green()}, {reject_color.blue()}, 0.06); border-radius: 12px; }}"
		
		video_exts = {
			".mp4", ".mpeg", ".mov", ".avi", ".flv",
			".mpg", ".webm", ".wmv", ".3gp", ".3gpp"
		}
		extra_exts = {'.svg', '.eps', '.pdf'}
		self._supported_exts = PILLOW_FORMATS | video_exts | extra_exts
		self._default_sub_text = "Drag and drop images or videos here"
		
		common_exts = [
			"jpg", "jpeg", "png", "psd", "eps", "svg", "pdf", "tiff", "webp",
			"mp4", "mpeg", "mov", "avi", "flv", "mpg", "webm", "wmv", "3gp", "3gpp"
		]
		supported_common = [ext for ext in common_exts if f".{ext}" in self._supported_exts]
		has_other = len(self._supported_exts - set(f".{ext}" for ext in supported_common)) > 0
		supported_text = ", ".join(supported_common)
		if has_other:
			supported_text += ", ..."
		self._supported_text = supported_text

	def dragEnterEvent(self, event: QDragEnterEvent):
		if event.mimeData().hasUrls():
			paths = [url.toLocalFile() for url in event.mimeData().urls()]
			unsupported_ext = None
			for p in paths:
				if not self._is_supported_file(p):
					unsupported_ext = p.lower().rsplit('.', 1)[-1] if '.' in p else ''
					break
			if unsupported_ext is None:
				self.inner_widget.setStyleSheet(self._accept_style)
				self.sub_text.setText(self._default_sub_text)
				event.acceptProposedAction()
			else:
				self.inner_widget.setStyleSheet(self._reject_style)
				self.sub_text.setText(f".{unsupported_ext} is not supported. Supported: {self._supported_text}")
				event.ignore()
		else:
			self.inner_widget.setStyleSheet(self._reject_style)
			self.sub_text.setText(f"File type not supported. Supported: {self._supported_text}")
			event.ignore()

	def dragLeaveEvent(self, event):
		self.inner_widget.setStyleSheet(self._default_style)
		self.sub_text.setText(self._default_sub_text)

	def dropEvent(self, event: QDropEvent):
		self.inner_widget.setStyleSheet(self._default_style)
		self.sub_text.setText(self._default_sub_text)
		if event.mimeData().hasUrls():
			paths = [url.toLocalFile() for url in event.mimeData().urls()]
			if self.on_files_dropped:
				self.on_files_dropped(paths)
			else:
				mainwin = self.window()
				if hasattr(mainwin, "db") and hasattr(mainwin, "table"):
					if import_files(mainwin, mainwin.db, file_paths=paths):
						mainwin.table.refresh_table()

	def _is_supported_file(self, path):
		ext = os.path.splitext(path)[1].lower()
		return ext in self._supported_exts
