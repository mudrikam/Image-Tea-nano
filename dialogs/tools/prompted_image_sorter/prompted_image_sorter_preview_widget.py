import os
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget, QSizePolicy
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from ui.theme_system import theme


class PromptedImageSorterPreviewWidget(QWidget):
    """Preview widget showing the currently processed image with metadata. Right side of splitter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._original_pixmap = None
        self._current_file = None
        self._setup_ui()
        self._show_no_image()

    def _setup_ui(self):
        """Set up the preview area with image on top, metadata at bottom."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Preview image label - scales with widget
        self.image_label = QLabel("No Image")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        layout.addWidget(self.image_label, 1)

        # Metadata labels
        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(2)

        self.filename_label = QLabel("Filename: —")
        self.filename_label.setStyleSheet("font-size: 10px;")
        meta_layout.addWidget(self.filename_label)

        self.size_label = QLabel("Size: —")
        self.size_label.setStyleSheet("font-size: 10px;")
        meta_layout.addWidget(self.size_label)

        self.dimensions_label = QLabel("Dimensions: —")
        self.dimensions_label.setStyleSheet("font-size: 10px;")
        meta_layout.addWidget(self.dimensions_label)

        self.duration_label = QLabel("Duration: —")
        self.duration_label.setStyleSheet("font-size: 10px;")
        meta_layout.addWidget(self.duration_label)

        self.output_label = QLabel("Output: —")
        self.output_label.setStyleSheet("font-size: 10px;")
        meta_layout.addWidget(self.output_label)

        layout.addLayout(meta_layout)

    def _show_no_image(self):
        """Show placeholder when no image is loaded."""
        self._original_pixmap = None
        self._current_file = None
        self.image_label.setText("No Image")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(
            f"color: {theme.get_color('gray')}; font-size: 12px; font-style: italic;"
        )
        self.image_label.setPixmap(QPixmap())
        self.filename_label.setText("Filename: —")
        self.size_label.setText("Size: —")
        self.dimensions_label.setText("Dimensions: —")
        self.duration_label.setText("Duration: —")
        self.output_label.setText("Output: —")

    def load_image(self, file_path, output_folder="—", duration_ms=0):
        """Load an image from file path and display its metadata."""
        if not file_path or not os.path.exists(file_path):
            self._show_no_image()
            return

        self._current_file = file_path
        pixmap = QPixmap(file_path)

        if pixmap.isNull():
            self._show_no_image()
            self.output_label.setText(f"Output: {output_folder}")
            return

        self._original_pixmap = pixmap

        self.image_label.setText("")
        self.image_label.setStyleSheet("")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scale_pixmap()

        filename = os.path.basename(file_path)
        max_len = 20
        if len(filename) > max_len:
            display_name = filename[:max_len-3] + "..."
        else:
            display_name = filename
        self.filename_label.setText(f"Filename: {display_name}")

        try:
            size_bytes = os.path.getsize(file_path)
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
            self.size_label.setText(f"Size: {size_str}")
        except Exception:
            self.size_label.setText("Size: —")

        self.dimensions_label.setText(f"Dimensions: {pixmap.width()} × {pixmap.height()}")

        if duration_ms > 0:
            self.duration_label.setText(f"Duration: {duration_ms} ms")
        else:
            self.duration_label.setText("Duration: —")

        self.output_label.setText(f"Output: {output_folder}")

    def _scale_pixmap(self):
        """Scale pixmap to fit image label while maintaining aspect ratio."""
        if self._original_pixmap and not self._original_pixmap.isNull():
            scaled = self._original_pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)

    def resizeEvent(self, event):
        """Handle widget resize to scale image."""
        super().resizeEvent(event)
        self._scale_pixmap()
