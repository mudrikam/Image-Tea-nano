import os
import json
import time
import math
from pathlib import Path
from PIL import Image
from PySide6.QtCore import Qt, QThread, Signal, QObject, QPointF, QRectF, Slot
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QLineEdit,
    QPushButton, QProgressBar, QFileDialog, QMessageBox, QApplication,
    QTableWidget, QTableWidgetItem, QHeaderView, QSlider, QSpinBox,
    QCheckBox, QComboBox, QSizePolicy, QColorDialog, QSplitter,
    QScrollArea, QFrame, QGroupBox, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
)
from PySide6.QtGui import (
    QIcon, QFont, QColor, QDragEnterEvent, QDropEvent, QPixmap,
    QPainter, QWheelEvent, QMouseEvent
)
from PySide6.QtWidgets import QAbstractItemView
import qtawesome as qta
from config import BASE_PATH
from database.db_operation import ImageTeaDB
from ui.theme_system import theme
from ui.DragDropPathMixin import DragDropPathMixin
from dialogs.tools.background_remover.background_remover_config import BackgroundRemoverConfig
from dialogs.tools.background_remover.background_remover_worker import BackgroundRemoverWorker, SUPPORTED_EXTENSIONS
from dialogs.tools.background_remover.widgets.multi_handle_slider import MultiHandleSlider
from dialogs.tools.background_remover import models_manager
from helpers.tools.background_remover_helper import apply_levels_to_mask

IMAGE_EXTENSIONS = SUPPORTED_EXTENSIONS


# =========================================================================
# ImageGraphicsView — ported from Keong-MAS
# =========================================================================
class ImageGraphicsView(QGraphicsView):
    """Graphics view with zoom and pan, ported from Keong-MAS."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_view()
        self.current_scale = 1.0
        self.is_panning = False
        self.is_right_clicking = False
        self.pan_start = QPointF()
        self.pan_button = None

    def _setup_view(self):
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.pixmap_item = None

    def zoom_in(self, factor=1.05):
        factor = float(factor)
        new_scale = self.current_scale * factor
        if new_scale > 10.0:
            factor = 10.0 / max(1e-9, self.current_scale)
            new_scale = 10.0
        self.scale(factor, factor)
        self.current_scale = new_scale

    def zoom_out(self, factor=None):
        if factor is None:
            factor = 1.0 / 1.05
        factor = float(factor)
        new_scale = self.current_scale * factor
        if new_scale < 0.1:
            factor = 0.1 / max(1e-9, self.current_scale)
            new_scale = 0.1
        self.scale(factor, factor)
        self.current_scale = new_scale
        self._notify_preview_update()

    def reset_zoom(self):
        try:
            if self.scene and not self.scene.sceneRect().isNull():
                self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
                self.current_scale = self.transform().m11()
                self._notify_preview_update()
        except Exception:
            pass

    def set_image(self, image_path, preserve_zoom=False):
        if not os.path.exists(image_path):
            return
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            return
        saved_transform = None
        saved_h_scroll = None
        saved_v_scroll = None
        if preserve_zoom and self.pixmap_item:
            saved_transform = self.transform()
            saved_h_scroll = self.horizontalScrollBar().value()
            saved_v_scroll = self.verticalScrollBar().value()
        self.scene.clear()
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)
        self.scene.setSceneRect(QRectF(pixmap.rect()))
        if preserve_zoom and saved_transform:
            self.setTransform(saved_transform)
            if saved_h_scroll is not None:
                self.horizontalScrollBar().setValue(saved_h_scroll)
            if saved_v_scroll is not None:
                self.verticalScrollBar().setValue(saved_v_scroll)
        else:
            self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
            self.current_scale = self.transform().m11()
        self._notify_preview_update()

    def clear(self):
        self.scene.clear()
        self.pixmap_item = None
        self.current_scale = 1.0

    def wheelEvent(self, event: QWheelEvent):
        fine = 1.05
        coarse = 1.25
        if event.angleDelta().y() > 0:
            factor = fine if (event.modifiers() & Qt.ControlModifier) else coarse
        else:
            factor = (1.0 / fine) if (event.modifiers() & Qt.ControlModifier) else (1.0 / coarse)
        new_scale = self.current_scale * factor
        if new_scale < 0.1:
            factor = 0.1 / max(1e-9, self.current_scale)
            new_scale = 0.1
        elif new_scale > 10.0:
            factor = 10.0 / max(1e-9, self.current_scale)
            new_scale = 10.0
        self.scale(factor, factor)
        self.current_scale = new_scale
        self._notify_preview_update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.is_panning = True
            self.pan_start = event.pos()
            self.pan_button = Qt.LeftButton
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        elif event.button() == Qt.MiddleButton:
            self.is_panning = True
            self.pan_start = event.pos()
            self.pan_button = Qt.MiddleButton
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        elif event.button() == Qt.RightButton:
            self.is_right_clicking = True
            pw = self.parent()
            while pw and not isinstance(pw, ImagePreviewWidget):
                pw = pw.parent()
            if pw:
                pw.toggle_before_after(not pw.showing_before)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.is_panning:
            delta = event.pos() - self.pan_start
            self.pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if (event.button() == Qt.LeftButton or event.button() == Qt.MiddleButton) and self.is_panning:
            if event.button() == self.pan_button:
                self.is_panning = False
                self.pan_button = None
                self.setCursor(Qt.ArrowCursor)
            event.accept()
        elif event.button() == Qt.RightButton and self.is_right_clicking:
            self.is_right_clicking = False
            pw = self.parent()
            while pw and not isinstance(pw, ImagePreviewWidget):
                pw = pw.parent()
            if pw:
                pw.show_after()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            pw = self.parent()
            while pw and not isinstance(pw, ImagePreviewWidget):
                pw = pw.parent()
            if pw:
                fp = pw.get_current_file_path()
                if fp:
                    pw.file_double_clicked.emit(fp)
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def _notify_preview_update(self):
        pw = self.parent()
        while pw and not isinstance(pw, ImagePreviewWidget):
            pw = pw.parent()
        if pw and hasattr(pw, '_update_nav_zoom_slider'):
            pw._update_nav_zoom_slider()


# =========================================================================
# ImagePreviewWidget — ported from Keong-MAS
# =========================================================================
class ImagePreviewWidget(QWidget):
    """Preview widget with zoom, pan, before/after toggle, mask mode, ported from Keong-MAS."""

    file_double_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.before_path = None
        self.after_path = None
        self.showing_before = False
        self.mask_mode = False
        self.mask_before_path = None
        self.mask_after_path = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = ImageGraphicsView(self)
        layout.addWidget(self.view)

        # Floating navigation frame (top-right)
        try:
            self._nav_frame = QFrame(self)
            self._nav_frame.setObjectName('previewNav')
            self._nav_frame.setStyleSheet('''
                QFrame#previewNav {
                    background-color: rgba(128, 128, 128, 0.2);
                    border-radius: 6px;
                }
                QPushButton { background: transparent; color: white; border: none; }
            ''')
            nav_layout = QHBoxLayout(self._nav_frame)
            nav_layout.setContentsMargins(6, 4, 6, 4)
            nav_layout.setSpacing(6)

            self._before_hold_btn = QPushButton()
            self._before_hold_btn.setToolTip('Hold to see Before (release to go back)')
            try:
                self._before_hold_btn.setIcon(qta.icon('fa5s.image'))
            except Exception:
                pass
            self._before_hold_btn.pressed.connect(lambda: self.show_before())
            self._before_hold_btn.released.connect(lambda: self.show_after())
            nav_layout.addWidget(self._before_hold_btn)

            self._reset_zoom_btn = QPushButton()
            self._reset_zoom_btn.setToolTip('Reset view')
            try:
                self._reset_zoom_btn.setIcon(qta.icon('fa5s.redo'))
            except Exception:
                pass
            self._reset_zoom_btn.clicked.connect(self._on_nav_reset_zoom)
            nav_layout.addWidget(self._reset_zoom_btn)

            self._zoom_out_btn = QPushButton()
            self._zoom_out_btn.setToolTip('Zoom out')
            try:
                self._zoom_out_btn.setIcon(qta.icon('fa5s.search-minus'))
            except Exception:
                pass
            self._zoom_out_btn.clicked.connect(self._on_nav_zoom_out)
            nav_layout.addWidget(self._zoom_out_btn)

            try:
                self._zoom_slider = QSlider(Qt.Horizontal)
                self._zoom_slider.setRange(10, 1000)
                self._zoom_slider.setFixedWidth(120)
                self._zoom_slider.setFixedHeight(16)
                try:
                    init_val = int(round(self.view.current_scale * 100))
                except Exception:
                    init_val = 100
                self._zoom_slider.setValue(init_val)
                self._zoom_slider.setToolTip(f"Zoom: {init_val}%")
                self._slider_updating = False
                self._zoom_slider.valueChanged.connect(self._on_nav_zoom_slider_changed)
                nav_layout.addWidget(self._zoom_slider)
            except Exception:
                self._zoom_slider = None

            self._zoom_in_btn = QPushButton()
            self._zoom_in_btn.setToolTip('Zoom in')
            try:
                self._zoom_in_btn.setIcon(qta.icon('fa5s.search-plus'))
            except Exception:
                pass
            self._zoom_in_btn.clicked.connect(self._on_nav_zoom_in)
            nav_layout.addWidget(self._zoom_in_btn)

            self._nav_frame.setLayout(nav_layout)
            self._nav_frame.setFixedHeight(34)
            self._nav_frame.setWindowOpacity(0.92)
            self._nav_frame.raise_()
            try:
                self._nav_frame.adjustSize()
                w = max(self._nav_frame.sizeHint().width(), 160)
                self._nav_frame.setFixedWidth(w)
            except Exception:
                pass
            self._nav_frame.show()
        except Exception:
            self._nav_frame = None

    def set_images(self, before_path, after_path=None, preserve_zoom=False):
        self.before_path = before_path
        self.after_path = after_path
        self.showing_before = False
        self.mask_mode = False
        self._update_display(preserve_zoom=preserve_zoom)

    def set_mask_images(self, before_mask_path, after_mask_path=None, preserve_zoom=False, show_before=None):
        self.mask_before_path = before_mask_path
        self.mask_after_path = after_mask_path
        if show_before is not None:
            self.showing_before = show_before
        else:
            self.showing_before = True
        self.mask_mode = True
        self._update_display(preserve_zoom=preserve_zoom)

    def show_before(self):
        if self.mask_mode:
            if self.mask_before_path:
                self.showing_before = True
                self._update_display(preserve_zoom=True)
        else:
            if self.before_path:
                self.showing_before = True
                self._update_display(preserve_zoom=True)

    def show_after(self):
        if self.mask_mode:
            if self.mask_after_path:
                self.showing_before = False
                self._update_display(preserve_zoom=True)
            elif self.mask_before_path:
                self.showing_before = False
                self._update_display(preserve_zoom=True)
        else:
            if self.after_path:
                self.showing_before = False
                self._update_display(preserve_zoom=True)
            elif self.before_path:
                self.showing_before = False
                self._update_display(preserve_zoom=True)

    def toggle_before_after(self, show_before):
        if show_before:
            self.show_before()
        else:
            self.show_after()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        try:
            if self._nav_frame:
                margin = 10
                frame_w = self._nav_frame.width()
                x = max(0, self.width() - frame_w - margin)
                y = margin
                self._nav_frame.move(x, y)
                self._nav_frame.raise_()
                self._update_nav_zoom_slider()
                try:
                    self._nav_frame.adjustSize()
                    w = max(self._nav_frame.sizeHint().width(), 160)
                    self._nav_frame.setFixedWidth(w)
                except Exception:
                    pass
        except Exception:
            pass

    def _on_nav_zoom_out(self):
        try:
            if self.view:
                self.view.zoom_out()
                self._update_nav_zoom_slider()
        except Exception:
            pass

    def _on_nav_reset_zoom(self):
        try:
            if self.view:
                self.view.reset_zoom()
                self._update_nav_zoom_slider()
        except Exception:
            pass

    def _on_nav_zoom_in(self):
        try:
            if self.view:
                self.view.zoom_in()
                self._update_nav_zoom_slider()
        except Exception:
            pass

    def _on_nav_zoom_slider_changed(self, value):
        try:
            if not hasattr(self, '_zoom_slider') or self._zoom_slider is None:
                return
            if getattr(self, '_slider_updating', False):
                return
            slider_min = self._zoom_slider.minimum()
            slider_max = self._zoom_slider.maximum()
            min_scale = 0.1
            max_scale = 10.0
            t = (value - slider_min) / float(slider_max - slider_min)
            target = min_scale * ((max_scale / min_scale) ** t)
            try:
                current = self.view.current_scale
                if current <= 0:
                    factor = target
                else:
                    factor = target / current
                if factor <= 0:
                    factor = 1.0
                self.view.scale(factor, factor)
                self.view.current_scale = target
            except Exception:
                pass
            try:
                self._zoom_slider.setToolTip(f"Zoom: {int(round(self.view.current_scale * 100))}%")
            except Exception:
                pass
        finally:
            try:
                self._update_nav_zoom_slider()
            except Exception:
                pass

    def _update_nav_zoom_slider(self):
        try:
            if not hasattr(self, '_zoom_slider') or self._zoom_slider is None:
                return
            self._slider_updating = True
            slider_min = self._zoom_slider.minimum()
            slider_max = self._zoom_slider.maximum()
            min_scale = 0.1
            max_scale = 10.0
            current = max(min_scale, min(max_scale, float(self.view.current_scale)))
            try:
                if current <= min_scale:
                    t = 0.0
                elif current >= max_scale:
                    t = 1.0
                else:
                    t = math.log(current / min_scale) / math.log(max_scale / min_scale)
            except Exception:
                t = 0.0
            val = int(round(slider_min + t * (slider_max - slider_min)))
            val = max(slider_min, min(slider_max, val))
            self._zoom_slider.setValue(val)
            try:
                self._zoom_slider.setToolTip(f"Zoom: {int(round(current * 100))}%")
            except Exception:
                pass
        except Exception:
            pass
        finally:
            self._slider_updating = False
            try:
                if self._nav_frame:
                    self._nav_frame.adjustSize()
                    w = max(self._nav_frame.sizeHint().width(), 160)
                    self._nav_frame.setFixedWidth(w)
            except Exception:
                pass

    def get_current_file_path(self):
        if self.mask_mode:
            if self.showing_before:
                return self.mask_before_path
            elif self.mask_after_path:
                return self.mask_after_path
            else:
                return self.mask_before_path
        else:
            if self.showing_before:
                return self.before_path
            elif self.after_path:
                return self.after_path
            else:
                return self.before_path

    def clear(self):
        self.before_path = None
        self.after_path = None
        self.mask_before_path = None
        self.mask_after_path = None
        self.showing_before = False
        self.mask_mode = False
        self.view.clear()

    def _update_display(self, preserve_zoom=False):
        if self.mask_mode:
            if self.showing_before and self.mask_before_path:
                self.view.set_image(self.mask_before_path, preserve_zoom=preserve_zoom)
            elif not self.showing_before and self.mask_after_path:
                self.view.set_image(self.mask_after_path, preserve_zoom=preserve_zoom)
            elif self.mask_before_path:
                self.view.set_image(self.mask_before_path, preserve_zoom=preserve_zoom)
            else:
                self.view.clear()
        else:
            if self.showing_before and self.before_path:
                self.view.set_image(self.before_path, preserve_zoom=preserve_zoom)
            elif not self.showing_before and self.after_path:
                self.view.set_image(self.after_path, preserve_zoom=preserve_zoom)
            elif self.before_path:
                self.view.set_image(self.before_path, preserve_zoom=preserve_zoom)
            else:
                self.view.clear()


# =========================================================================
# MaskWorker — ported from Keong-MAS
# =========================================================================
class MaskWorker(QObject):
    """Worker to generate mask from a raw original image using rembg in background."""
    finished = Signal(str, str)  # mask_path, ori_path
    error = Signal(str)
    progress = Signal(int, str)

    def __init__(self, image_path, output_dir, model_name=None):
        super().__init__()
        self.image_path = image_path
        self.output_dir = output_dir
        self.model_name = model_name
        self.abort = False

    @Slot()
    def run(self):
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            input_img = Image.open(self.image_path)
            base = os.path.splitext(os.path.basename(self.image_path))[0]
            ori_temp = os.path.join(self.output_dir, f'{base}_ori_temp.png')
            input_img.save(ori_temp)

            self.progress.emit(5, "Preparing model...")
            try:
                prepared = models_manager.prepare_model(model_name=self.model_name)
            except Exception:
                prepared = None

            if self.abort:
                self.progress.emit(0, "Cancelled")
                return

            import rembg
            self.progress.emit(20, "Processing: Removing background (mask)...")

            session = None
            try:
                if self.model_name:
                    session = rembg.new_session(self.model_name)
                elif prepared:
                    session = rembg.new_session(prepared)
            except Exception:
                try:
                    session = rembg.new_session()
                except Exception:
                    session = None

            mask = rembg.remove(input_img, only_mask=True, session=session)
            if self.abort:
                self.progress.emit(0, "Cancelled")
                return

            mask_path = os.path.join(self.output_dir, f'{base}_mask_temp.png')
            mask.save(mask_path)

            self.progress.emit(100, "Done")
            self.finished.emit(mask_path, ori_temp)
        except Exception as e:
            self.error.emit(str(e))


# =========================================================================
# DropTableWidget
# =========================================================================
class DropTableWidget(QTableWidget):
    files_dropped = Signal(list)

    def __init__(self, parent_dialog, parent=None):
        super().__init__(parent)
        self.parent_dialog = parent_dialog
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            file_paths = []
            seen = set()
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                file_path = self.parent_dialog._sanitize_path(file_path)
                if os.path.isdir(file_path):
                    for root, dirs, files in os.walk(file_path):
                        for f in files:
                            ext = Path(f).suffix.lower()
                            if ext in IMAGE_EXTENSIONS:
                                fp = os.path.join(root, f)
                                if fp not in seen:
                                    seen.add(fp)
                                    file_paths.append(fp)
                elif os.path.isfile(file_path) and self.parent_dialog._is_image_file(file_path):
                    if file_path not in seen:
                        seen.add(file_path)
                        file_paths.append(file_path)
            if file_paths:
                self.files_dropped.emit(file_paths)
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.rowCount() == 0:
            from PySide6.QtGui import QPainter
            painter = QPainter(self.viewport())
            painter.save()
            painter.setPen(QColor(120, 120, 120))
            vp = self.viewport()
            cx = vp.width() // 2
            cy = vp.height() // 2
            icon_pix = qta.icon('fa6s.file-arrow-up', color=theme.get_color('text_dark')).pixmap(36, 36)
            painter.drawPixmap(cx - 18, cy - 36, icon_pix)
            font = painter.font()
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(0, cy + 8, vp.width(), 20, Qt.AlignCenter, "Drop images here")
            painter.restore()


# =========================================================================
# Model download worker
# =========================================================================
class _ModelDownloadWorker(QObject):
    progress = Signal(str, float)
    finished = Signal(str, bool)

    def __init__(self, model_name):
        super().__init__()
        self.model_name = model_name

    def run(self):
        def callback(name, progress):
            self.progress.emit(name, progress)
        success = models_manager.download_model(self.model_name, callback)
        self.finished.emit(self.model_name, success)


# =========================================================================
# BackgroundRemoverDialog
# =========================================================================
class BackgroundRemoverDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Background Remover")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)

        self.db = ImageTeaDB()
        self.loaded_files = []
        self.worker_thread = None
        self.config = BackgroundRemoverConfig()
        self._mask_mode = False
        self._current_mask_path = None
        self._current_original_path = None
        self._mask_worker = None
        self._mask_thread = None
        self._mask_in_progress = False
        self._current_file_index = 0
        self._total_files = 0

        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setup_ui()
        self.load_settings()
        self._refresh_model_list()
        self.resize(950, 720)

    def load_settings(self):
        output_path = self.config.get('output_path', '')
        model_name = self.config.get('model_name', 'isnet-general-use')
        black = self.config.get('black_point', 20)
        mid = self.config.get('mid_point', 128)
        white = self.config.get('white_point', 235)
        auto_crop = self.config.get('auto_crop', True)
        margin = self.config.get('margin', 10)
        solid_bg = self.config.get('solid_bg', False)
        sb_color = self.config.get('solid_bg_color', '#FFFFFF')
        save_mask = self.config.get('save_mask', False)
        jpg_export = self.config.get('jpg_export', False)
        jpg_quality = self.config.get('jpg_quality', 90)

        if output_path:
            self.output_path_input.setText(output_path)
        self.model_combo.setCurrentText(model_name)
        self.multi_slider.setValues(black, mid, white, emit=False)
        self.black_value.setText(str(black))
        self.mid_value.setText(str(mid))
        self.white_value.setText(str(white))
        self.crop_check.setChecked(auto_crop)
        self.margin_spin.setValue(margin)
        self.solid_bg_check.setChecked(solid_bg)
        self.color_btn.setStyleSheet(f"background-color: {sb_color}; border: 1px solid #888;")
        self.save_mask_check.setChecked(save_mask)
        self.jpg_check.setChecked(jpg_export)
        self.jpg_quality_spin.setValue(jpg_quality)

    def save_settings(self):
        self.config.set('output_path', self.output_path_input.text())
        self.config.set('model_name', self.model_combo.currentText())
        b, m, w = self.multi_slider.getValues()
        self.config.set('black_point', b)
        self.config.set('mid_point', m)
        self.config.set('white_point', w)
        self.config.set('auto_crop', self.crop_check.isChecked())
        self.config.set('margin', self.margin_spin.value())
        self.config.set('solid_bg', self.solid_bg_check.isChecked())
        self.config.set('solid_bg_color', self._solid_bg_color)
        self.config.set('save_mask', self.save_mask_check.isChecked())
        self.config.set('jpg_export', self.jpg_check.isChecked())
        self.config.set('jpg_quality', self.jpg_quality_spin.value())

    # ============================= UI Setup =============================

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Header
        header_layout = QHBoxLayout()
        header_icon = qta.icon('fa6s.eraser', color=theme.get_color('primary'))
        icon_label = QLabel()
        icon_label.setPixmap(header_icon.pixmap(24, 24))
        header_layout.addWidget(icon_label)

        title_label = QLabel("Background Remover")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {theme.get_color('primary')};")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        subtitle_label = QLabel("Remove image backgrounds using AI with ONNX models (rembg)")
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet(f"color: {theme.get_color('gray')}; padding-top: 4px;")
        main_layout.addWidget(subtitle_label)

        main_layout.addSpacing(8)

        # ===== Toolbar (Load DB, Clear Source, Clear All) =====
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)

        self.load_db_button = QPushButton(qta.icon('fa6s.database'), " Load Database")
        self.load_db_button.clicked.connect(self.on_load_from_database)
        toolbar_layout.addWidget(self.load_db_button)

        self.clear_source_button = QPushButton(qta.icon('fa6s.broom'), " Clear Source")
        self.clear_source_button.clicked.connect(self.on_clear_source)
        toolbar_layout.addWidget(self.clear_source_button)

        self.clear_all_button = QPushButton(qta.icon('fa6s.trash-can'), " Clear All")
        self.clear_all_button.clicked.connect(self.on_clear_all)
        toolbar_layout.addWidget(self.clear_all_button)

        self.clear_completed_button = QPushButton(qta.icon('fa6s.check'), " Clear Completed")
        self.clear_completed_button.clicked.connect(self.on_clear_completed)
        toolbar_layout.addWidget(self.clear_completed_button)

        self.clear_failed_button = QPushButton(qta.icon('fa6s.xmark'), " Clear Failed")
        self.clear_failed_button.clicked.connect(self.on_clear_failed)
        toolbar_layout.addWidget(self.clear_failed_button)

        toolbar_layout.addStretch()
        main_layout.addLayout(toolbar_layout)

        # Source path
        path_layout = QHBoxLayout()
        path_layout.setSpacing(8)

        source_icon = QLabel()
        source_icon.setPixmap(qta.icon('fa6s.folder-open', color=theme.get_color('gray')).pixmap(16, 16))
        path_layout.addWidget(source_icon)

        source_label = QLabel("Source:")
        source_label.setStyleSheet("font-weight: bold;")
        source_label.setMinimumWidth(50)
        path_layout.addWidget(source_label)

        self.source_path_input = QLineEdit()
        self.source_path_input.setPlaceholderText("Select source folder or image file...")
        self.source_path_input.editingFinished.connect(self.on_source_edited)
        self.source_path_input.setAcceptDrops(True)
        self.source_path_input.dragEnterEvent = DragDropPathMixin.make_drag_enter_handler(self.source_path_input)
        self.source_path_input.dropEvent = DragDropPathMixin.make_drop_handler(self.source_path_input, 'source', self.on_source_dropped)
        path_layout.addWidget(self.source_path_input, 1)

        self.source_browse_button = QPushButton(qta.icon('fa6s.folder-open'), "")
        self.source_browse_button.setToolTip("Browse folder")
        self.source_browse_button.setMaximumWidth(32)
        self.source_browse_button.clicked.connect(self.on_browse_source)
        path_layout.addWidget(self.source_browse_button)

        self.source_open_button = QPushButton(qta.icon('fa6s.arrow-up-right-from-square'), "")
        self.source_open_button.setToolTip("Open folder location")
        self.source_open_button.setMaximumWidth(32)
        self.source_open_button.clicked.connect(self.on_open_source)
        path_layout.addWidget(self.source_open_button)

        main_layout.addLayout(path_layout)

        # Output path
        output_layout = QHBoxLayout()
        output_layout.setSpacing(8)

        output_icon = QLabel()
        output_icon.setPixmap(qta.icon('fa6s.folder', color=theme.get_color('gray')).pixmap(16, 16))
        output_layout.addWidget(output_icon)

        output_label = QLabel("Output:")
        output_label.setStyleSheet("font-weight: bold;")
        output_label.setMinimumWidth(50)
        output_layout.addWidget(output_label)

        self.output_path_input = QLineEdit()
        self.output_path_input.setPlaceholderText("Select output folder (default: PNG folder next to source)...")
        self.output_path_input.editingFinished.connect(self.on_output_edited)
        self.output_path_input.setAcceptDrops(True)
        self.output_path_input.dragEnterEvent = DragDropPathMixin.make_drag_enter_handler(self.output_path_input)
        self.output_path_input.dropEvent = DragDropPathMixin.make_drop_handler(self.output_path_input, 'output', self.on_output_dropped)
        output_layout.addWidget(self.output_path_input, 1)

        self.output_browse_button = QPushButton(qta.icon('fa6s.folder-open'), "")
        self.output_browse_button.setToolTip("Browse folder")
        self.output_browse_button.setMaximumWidth(32)
        self.output_browse_button.clicked.connect(self.on_browse_output)
        output_layout.addWidget(self.output_browse_button)

        self.output_open_button = QPushButton(qta.icon('fa6s.arrow-up-right-from-square'), "")
        self.output_open_button.setToolTip("Open folder location")
        self.output_open_button.setMaximumWidth(32)
        self.output_open_button.clicked.connect(self.on_open_output)
        output_layout.addWidget(self.output_open_button)

        main_layout.addLayout(output_layout)

        # ===== Model + Levels row =====
        model_levels_layout = QHBoxLayout()
        model_levels_layout.setSpacing(8)

        model_label = QLabel("Model:")
        model_label.setStyleSheet("font-weight: bold;")
        model_levels_layout.addWidget(model_label)

        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(160)
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        model_levels_layout.addWidget(self.model_combo)

        model_levels_layout.addSpacing(4)

        self.configure_mask_btn = QPushButton(" Adjust Mask")
        self.configure_mask_btn.setCheckable(True)
        self.configure_mask_btn.setToolTip("Click to generate mask preview and adjust levels")
        self.configure_mask_btn.clicked.connect(self._on_atur_masking)
        model_levels_layout.addWidget(self.configure_mask_btn)

        self.reset_levels_btn = QPushButton(" Reset Levels")
        self.reset_levels_btn.setToolTip("Reset levels to default (20/128/235)")
        self.reset_levels_btn.clicked.connect(self._on_reset_levels)
        model_levels_layout.addWidget(self.reset_levels_btn)

        model_levels_layout.addSpacing(4)

        self.multi_slider = MultiHandleSlider()
        self.multi_slider.setMinimumWidth(200)
        self.multi_slider.valuesChanged.connect(self._on_multi_slider_changed)
        model_levels_layout.addWidget(self.multi_slider, 1)

        self.black_value = QLabel("20")
        self.black_value.setMinimumWidth(30)
        self.black_value.setAlignment(Qt.AlignCenter)
        self.black_value.setStyleSheet("font-weight: bold;")
        model_levels_layout.addWidget(self.black_value)

        self.mid_value = QLabel("128")
        self.mid_value.setMinimumWidth(30)
        self.mid_value.setAlignment(Qt.AlignCenter)
        self.mid_value.setStyleSheet("font-weight: bold;")
        model_levels_layout.addWidget(self.mid_value)

        self.white_value = QLabel("235")
        self.white_value.setMinimumWidth(30)
        self.white_value.setAlignment(Qt.AlignCenter)
        self.white_value.setStyleSheet("font-weight: bold;")
        model_levels_layout.addWidget(self.white_value)

        main_layout.addLayout(model_levels_layout)

        # ===== Checkboxes row =====
        check_layout = QHBoxLayout()
        check_layout.setSpacing(12)

        self.crop_check = QCheckBox("Auto Crop")
        self.crop_check.setToolTip("Automatically crop transparent areas")
        check_layout.addWidget(self.crop_check)

        margin_label = QLabel("Margin:")
        check_layout.addWidget(margin_label)
        self.margin_spin = QSpinBox()
        self.margin_spin.setRange(0, 200)
        self.margin_spin.setValue(10)
        self.margin_spin.setMinimumWidth(60)
        check_layout.addWidget(self.margin_spin)

        self.solid_bg_check = QCheckBox("Solid BG")
        self.solid_bg_check.setToolTip("Add solid background color")
        check_layout.addWidget(self.solid_bg_check)

        self._solid_bg_color = '#FFFFFF'
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(20, 20)
        self.color_btn.setStyleSheet(f"background-color: {self._solid_bg_color}; border: 1px solid #888;")
        self.color_btn.clicked.connect(self._on_color_picker)
        check_layout.addWidget(self.color_btn)

        self.save_mask_check = QCheckBox("Save Mask")
        check_layout.addWidget(self.save_mask_check)

        self.jpg_check = QCheckBox("JPG Export")
        check_layout.addWidget(self.jpg_check)

        quality_label = QLabel("Quality:")
        check_layout.addWidget(quality_label)
        self.jpg_quality_spin = QSpinBox()
        self.jpg_quality_spin.setRange(1, 100)
        self.jpg_quality_spin.setValue(90)
        self.jpg_quality_spin.setMinimumWidth(60)
        check_layout.addWidget(self.jpg_quality_spin)

        check_layout.addStretch()
        main_layout.addLayout(check_layout)

        # ===== Splitter: File table + Preview =====
        splitter = QSplitter(Qt.Horizontal)

        table_container = QWidget()
        table_layout = QVBoxLayout()
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(4)

        files_label = QLabel("Loaded Files:")
        files_label.setStyleSheet("font-weight: bold;")
        table_layout.addWidget(files_label)

        self.files_table = DropTableWidget(self)
        self.files_table.setColumnCount(3)
        self.files_table.setHorizontalHeaderLabels(["File Name", "Path", "Status"])
        self.files_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.files_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.files_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.files_table.setMinimumHeight(180)
        self.files_table.files_dropped.connect(self._on_files_dropped)
        table_layout.addWidget(self.files_table)

        table_container.setLayout(table_layout)
        splitter.addWidget(table_container)

        self.image_preview = ImagePreviewWidget()
        splitter.addWidget(self.image_preview)

        splitter.setSizes([500, 400])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter, 1)

        # ===== Stats =====
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)

        self.files_count_label = QLabel("Files: 0")
        self.files_count_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.files_count_label)

        self.processed_label = QLabel("Processed: 0/0")
        self.processed_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.processed_label)

        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.status_label)

        stats_layout.addStretch()
        main_layout.addLayout(stats_layout)

        # ===== Mode combo + Progress bar + START/STOP button =====
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        mode_label = QLabel("Mode:")
        mode_label.setStyleSheet("font-weight: bold;")
        action_layout.addWidget(mode_label)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["All", "Failed Only"])
        self.mode_combo.setToolTip("All: process all files. Failed Only: retry only failed files.")
        self.mode_combo.setMinimumWidth(120)
        action_layout.addWidget(self.mode_combo)

        action_layout.addSpacing(8)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMaximumHeight(20)
        action_layout.addWidget(self.progress_bar, 1)

        self.process_button = QPushButton(qta.icon('fa6s.play'), " START")
        self.process_button.setMinimumHeight(40)
        self.process_button.setMinimumWidth(180)
        self.process_button.clicked.connect(self.on_process_clicked)
        self._apply_process_button_style()
        action_layout.addWidget(self.process_button)

        main_layout.addLayout(action_layout)
        self.setLayout(main_layout)

    def _apply_process_button_style(self):
        self.process_button.setStyleSheet(f"""
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
            QPushButton:disabled {{
                background-color: {theme.get_color('gray')};
            }}
        """)

    def _apply_stop_button_style(self):
        error_base = theme.get_color('error')
        error_hover = QColor(error_base).darker(115).name()
        error_pressed = QColor(error_base).darker(130).name()
        white = theme.get_color('white')
        self.process_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {error_base};
                color: {white};
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {error_hover};
            }}
            QPushButton:pressed {{
                background-color: {error_pressed};
            }}
        """)

    def _set_process_button_to_stop(self):
        self.process_button.setText(" STOP")
        self.process_button.setIcon(qta.icon('fa6s.stop', color=theme.get_color('white')))
        self._apply_stop_button_style()

    def _set_process_button_to_start(self):
        self.process_button.setText(" START")
        self.process_button.setIcon(qta.icon('fa6s.play', color=theme.get_color('white')))
        self.process_button.setEnabled(True)
        self._apply_process_button_style()

    # ============================= Model Management =============================

    def _refresh_model_list(self):
        available = models_manager.get_available_models()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(available)
        self.model_combo.blockSignals(False)
        saved_model = self.config.get('model_name', models_manager.DEFAULT_MODEL)
        idx = self.model_combo.findText(saved_model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        else:
            self.model_combo.setCurrentText(models_manager.DEFAULT_MODEL)
        self._check_model_availability()

    def _check_model_availability(self):
        model_name = self.model_combo.currentText()
        if not model_name:
            return
        model_path = models_manager.get_model_path(model_name)
        if model_path:
            self.status_label.setText(f"Status: Model '{model_name}' ready")
        else:
            self.status_label.setText(f"Status: Model '{model_name}' not found")

    def _on_model_changed(self, model_name):
        if not model_name:
            return
        self.save_settings()
        model_path = models_manager.get_model_path(model_name)
        if model_path:
            self.status_label.setText(f"Status: Model '{model_name}' ready")
            return
        self.status_label.setText(f"Status: Downloading model '{model_name}'...")
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)
        self.process_button.setEnabled(False)
        self._download_thread = QThread()
        self._download_worker = _ModelDownloadWorker(model_name)
        self._download_worker.moveToThread(self._download_thread)
        self._download_thread.started.connect(self._download_worker.run)
        self._download_worker.progress.connect(self._on_download_progress)
        self._download_worker.finished.connect(self._on_download_finished)
        self._download_worker.finished.connect(self._download_thread.quit)
        self._download_worker.finished.connect(self._download_worker.deleteLater)
        self._download_thread.finished.connect(self._download_thread.deleteLater)
        self._download_thread.start()

    def _on_download_progress(self, model_name, progress):
        self.progress_bar.setValue(int(progress))
        self.status_label.setText(f"Status: Downloading '{model_name}'... {int(progress)}%")

    def _on_download_finished(self, model_name, success):
        self.process_button.setEnabled(True)
        if success:
            self.status_label.setText(f"Status: Model '{model_name}' ready")
            self.progress_bar.setValue(100)
        else:
            self.status_label.setText(f"Status: Failed to download model '{model_name}'")
            self.progress_bar.setValue(0)

    # ============================= MultiHandleSlider =============================

    def _on_multi_slider_changed(self, black, mid, white):
        self.black_value.setText(str(black))
        self.mid_value.setText(str(mid))
        self.white_value.setText(str(white))
        self.save_settings()
        if self._mask_mode and self._current_mask_path:
            self._update_levels_preview()

    def _on_reset_levels(self):
        self.multi_slider.setValues(20, 128, 235)
        self.multi_slider.set_mid_manual(False)
        if self._mask_mode and self._current_mask_path:
            self._update_levels_preview()

    # ============================= Atur Masking =============================

    def _on_atur_masking(self, checked):
        if checked:
            if not self.loaded_files:
                QMessageBox.warning(self, "No Files", "Please load image files first.")
                self.configure_mask_btn.setChecked(False)
                return
            if self._mask_in_progress:
                return
            first_file = self.loaded_files[0]
            self._generate_mask_preview(first_file)
        else:
            self._mask_mode = False
            self._current_mask_path = None
            self.image_preview.set_mode('normal')

    def _generate_mask_preview(self, image_path):
        """Generate mask from the first image using background MaskWorker (ported from Keong-MAS)."""
        self._mask_in_progress = True
        self.configure_mask_btn.setEnabled(False)
        self.status_label.setText("Status: Generating mask preview...")
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(0)  # Busy mode

        temp_dir = os.path.join(BASE_PATH, 'temp')
        os.makedirs(temp_dir, exist_ok=True)

        model_name = self.model_combo.currentText()
        self._mask_worker = MaskWorker(image_path, temp_dir, model_name=model_name)
        self._mask_thread = QThread()
        self._mask_worker.moveToThread(self._mask_thread)
        self._mask_thread.started.connect(self._mask_worker.run)
        self._mask_worker.progress.connect(self._on_mask_progress)
        self._mask_worker.finished.connect(self._on_mask_generated)
        self._mask_worker.error.connect(self._on_mask_error)
        self._mask_worker.finished.connect(self._mask_thread.quit)
        self._mask_worker.finished.connect(self._mask_worker.deleteLater)
        self._mask_thread.finished.connect(self._mask_thread.deleteLater)
        self._mask_thread.start()

    def _on_mask_progress(self, value, message):
        if value == 0:
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setFormat(message)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(value))
            if message:
                self.progress_bar.setFormat(message)
            if int(value) >= 100:
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(100)

    def _on_mask_generated(self, mask_path, ori_path):
        self._mask_in_progress = False
        self.configure_mask_btn.setEnabled(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)

        self._current_mask_path = mask_path
        self._current_original_path = ori_path

        # Generate adjusted mask with current levels
        try:
            mask_img = Image.open(mask_path)
            b, m, w = self.multi_slider.getValues()
            mask_adj = apply_levels_to_mask(mask_img, black_point=b, mid_point=m, white_point=w)
            base = os.path.splitext(os.path.basename(mask_path))[0].replace('_mask_temp', '')
            temp_dir = os.path.dirname(mask_path)
            mask_adj_temp = os.path.join(temp_dir, f'{base}_mask_adj_temp_{int(time.time()*1000)}.png')
            mask_adj.save(mask_adj_temp)

            self.image_preview.set_mask_images(mask_path, mask_adj_temp, preserve_zoom=False, show_before=True)
            self._mask_mode = True
            self.status_label.setText("Status: Mask preview ready. Adjust levels...")
        except Exception as e:
            self.status_label.setText(f"Status: Mask preview failed: {str(e)[:60]}")
            self.configure_mask_btn.setChecked(False)
            self._mask_mode = False

    def _on_mask_error(self, error_msg):
        self._mask_in_progress = False
        self.configure_mask_btn.setEnabled(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_label.setText("Status: Mask generation failed")
        self.configure_mask_btn.setChecked(False)
        self._mask_mode = False
        QMessageBox.warning(self, "Mask Error", f"Failed to generate mask:\n{error_msg}")

    def _update_levels_preview(self):
        if not self._current_mask_path:
            return
        try:
            b, m, w = self.multi_slider.getValues()
            mask_img = Image.open(self._current_mask_path)
            mask_adj = apply_levels_to_mask(mask_img, black_point=b, mid_point=m, white_point=w)
            base = os.path.splitext(os.path.basename(self._current_mask_path))[0].replace('_mask_temp', '')
            temp_dir = os.path.dirname(self._current_mask_path)
            mask_adj_temp = os.path.join(temp_dir, f'{base}_mask_adj_temp_{int(time.time()*1000)}.png')
            mask_adj.save(mask_adj_temp)
            self.image_preview.set_mask_images(self._current_mask_path, mask_adj_temp, preserve_zoom=True, show_before=False)
        except Exception:
            pass

    # ============================= Color Picker =============================

    def _on_color_picker(self):
        color = QColorDialog.getColor(QColor(self._solid_bg_color), self, "Select Background Color")
        if color.isValid():
            self._solid_bg_color = color.name()
            self.color_btn.setStyleSheet(f"background-color: {self._solid_bg_color}; border: 1px solid #888;")
            self.save_settings()

    # ============================= Path Utilities =============================

    def _sanitize_path(self, path):
        if not isinstance(path, str):
            return path
        t = path.strip()
        if len(t) >= 2 and ((t[0] == '"' and t[-1] == '"') or (t[0] == "'" and t[-1] == "'")):
            return t[1:-1]
        return t

    def _is_image_file(self, path):
        ext = Path(path).suffix.lower()
        return ext in IMAGE_EXTENSIONS

    def _on_files_dropped(self, paths):
        for p in paths:
            if p not in self.loaded_files:
                self.loaded_files.append(p)
        self.update_files_table()
        self.update_stats()

    def _get_file_status(self, filepath):
        """Get the status of a file from the table."""
        basename = os.path.basename(filepath)
        for row in range(self.files_table.rowCount()):
            if self.files_table.item(row, 0).text() == basename:
                item = self.files_table.item(row, 2)
                if item:
                    return item.text()
        return "Ready"

    # ============================= Button Handlers =============================

    def _on_stop_clicked(self):
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.stop()
            self.status_label.setText("Status: Stopping...")
            self.process_button.setEnabled(False)

    def on_load_from_database(self):
        all_files = self.db.get_all_files()
        self.loaded_files = []
        for file_row in all_files:
            filepath = file_row[1]
            if os.path.exists(filepath) and self._is_image_file(filepath):
                self.loaded_files.append(filepath)
        self.update_files_table()
        self.update_stats()

    def on_clear_source(self):
        self.loaded_files = []
        self.source_path_input.clear()
        self.update_files_table()
        self.update_stats()
        self.image_preview.clear()

    def on_clear_completed(self):
        """Remove files with 'Completed' status from the list."""
        indices_to_remove = []
        for row in range(self.files_table.rowCount()):
            item = self.files_table.item(row, 2)
            if item and item.text() == "Completed":
                indices_to_remove.append(row)
        for idx in reversed(indices_to_remove):
            if idx < len(self.loaded_files):
                self.loaded_files.pop(idx)
        self.update_files_table()
        self.update_stats()

    def on_clear_failed(self):
        """Remove files with 'Failed' or 'Error' status from the list."""
        indices_to_remove = []
        for row in range(self.files_table.rowCount()):
            item = self.files_table.item(row, 2)
            if item and item.text() in ("Failed", "Error"):
                indices_to_remove.append(row)
        for idx in reversed(indices_to_remove):
            if idx < len(self.loaded_files):
                self.loaded_files.pop(idx)
        self.update_files_table()
        self.update_stats()

    def on_clear_all(self):
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.stop()
            self.worker_thread.wait()
        self.loaded_files = []
        self.source_path_input.clear()
        self.output_path_input.clear()
        self.files_table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.status_label.setText("Status: Idle")
        self.update_stats()
        self.image_preview.clear()
        self._mask_mode = False
        self._current_mask_path = None
        self.configure_mask_btn.setChecked(False)

    def on_browse_source(self):
        home_dir = os.path.expanduser('~')
        folder = QFileDialog.getExistingDirectory(self, "Select Source Folder", home_dir)
        if folder:
            self.loaded_files = []
            for root, dirs, files in os.walk(folder):
                for f in files:
                    fp = os.path.join(root, f)
                    if self._is_image_file(fp):
                        self.loaded_files.append(fp)
            if self.loaded_files:
                self.source_path_input.setText(folder)
                self.update_files_table()
                self.update_stats()
            else:
                QMessageBox.information(self, "No Images", f"No supported image files found in:\n{folder}")

    def on_open_source(self):
        path = self.source_path_input.text()
        if path and os.path.exists(path):
            import platform
            import subprocess
            target = os.path.dirname(path) if os.path.isfile(path) else path
            if platform.system() == "Windows":
                os.startfile(target)
            elif platform.system() == "Darwin":
                subprocess.run(["open", target])
            else:
                subprocess.run(["xdg-open", target])

    def on_source_edited(self):
        path = self.source_path_input.text().strip()
        if not path or not os.path.exists(path):
            return
        self.loaded_files = []
        if os.path.isfile(path) and self._is_image_file(path):
            self.loaded_files = [path]
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for f in files:
                    fp = os.path.join(root, f)
                    if self._is_image_file(fp):
                        self.loaded_files.append(fp)
        if self.loaded_files:
            self.update_files_table()
            self.update_stats()

    def on_source_dropped(self, path):
        self.loaded_files = []
        if os.path.isfile(path) and self._is_image_file(path):
            self.loaded_files = [path]
            self.source_path_input.setText(path)
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for f in files:
                    fp = os.path.join(root, f)
                    if self._is_image_file(fp):
                        self.loaded_files.append(fp)
            if self.loaded_files:
                self.source_path_input.setText(path)
        self.update_files_table()
        self.update_stats()

    def on_output_dropped(self, path):
        self.save_settings()

    def on_browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder", os.path.expanduser('~'))
        if folder:
            self.output_path_input.setText(folder)
            self.save_settings()

    def on_open_output(self):
        path = self.output_path_input.text()
        if path:
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            import platform
            import subprocess
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])

    def on_output_edited(self):
        self.save_settings()

    def update_files_table(self):
        self.files_table.setRowCount(len(self.loaded_files))
        for idx, filepath in enumerate(self.loaded_files):
            name_item = QTableWidgetItem(os.path.basename(filepath))
            path_item = QTableWidgetItem(filepath)
            status_item = QTableWidgetItem("Ready")
            status_item.setIcon(qta.icon('fa6s.circle', color=theme.get_color('gray')))
            self.files_table.setItem(idx, 0, name_item)
            self.files_table.setItem(idx, 1, path_item)
            self.files_table.setItem(idx, 2, status_item)

    def update_stats(self):
        self.files_count_label.setText(f"Files: {len(self.loaded_files)}")
        self.processed_label.setText("Processed: 0/0")

    # ============================= Processing =============================

    def on_process_clicked(self):
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.stop()
            self.status_label.setText("Status: Stopping...")
            self.process_button.setEnabled(False)
            return

        if not self.loaded_files:
            QMessageBox.warning(self, "No Files", "Please load image files first.")
            return

        model_name = self.model_combo.currentText()
        model_path = models_manager.get_model_path(model_name)
        if not model_path:
            reply = QMessageBox.question(
                self, "Model Not Found",
                f"Model '{model_name}' is not available. Download it now?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._on_model_changed(model_name)
            return

        # Filter files based on mode
        mode = self.mode_combo.currentText()
        if mode == "Failed Only":
            files_to_process = []
            for fp in self.loaded_files:
                status = self._get_file_status(fp)
                if status in ("Failed", "Error"):
                    files_to_process.append(fp)
            if not files_to_process:
                QMessageBox.information(self, "No Failed Files", "No failed files to retry.")
                return
        else:
            files_to_process = self.loaded_files.copy()

        output_path = self.output_path_input.text().strip()
        if not output_path:
            output_path = None

        b, m, w = self.multi_slider.getValues()
        options = {
            'model_name': model_name,
            'black_point': b,
            'mid_point': m,
            'white_point': w,
            'auto_crop': self.crop_check.isChecked(),
            'margin': self.margin_spin.value(),
            'solid_bg': self.solid_bg_check.isChecked(),
            'solid_bg_color': self._solid_bg_color,
            'save_mask': self.save_mask_check.isChecked(),
            'jpg_export': self.jpg_check.isChecked(),
            'jpg_quality': self.jpg_quality_spin.value(),
        }

        self._set_process_button_to_stop()
        self.status_label.setText("Status: Processing...")
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)

        self._current_file_index = 0
        self._total_files = len(files_to_process)

        self.worker_thread = BackgroundRemoverWorker(
            files_to_process, output_path, options
        )
        self.worker_thread.progress_updated.connect(self.on_progress_updated)
        self.worker_thread.step_progress.connect(self._on_step_progress)
        self.worker_thread.status_updated.connect(self.on_status_updated)
        self.worker_thread.completed.connect(self.on_processing_completed)
        self.worker_thread.stopped.connect(self.on_processing_stopped)
        self.worker_thread.error_occurred.connect(self.on_processing_error)
        self.worker_thread.start()

    def on_progress_updated(self, current, total):
        pct = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(pct)
        self.processed_label.setText(f"Processed: {current}/{total}")
        self._current_file_index = current

    def _on_step_progress(self, percent, message):
        """Handle within-file step progress, scaled to overall progress."""
        total = self._total_files
        if total == 0:
            return
        current = self._current_file_index
        file_share = 100.0 / total
        # Scale: current file's progress within its share
        overall = int((current * file_share) + (percent * file_share / 100.0))
        self.progress_bar.setValue(overall)
        self.status_label.setText(f"Status: {message}")

    def on_status_updated(self, filename, status):
        for row in range(self.files_table.rowCount()):
            if self.files_table.item(row, 0).text() == filename:
                status_item = self.files_table.item(row, 2)
                status_item.setText(status)
                if status == "Completed":
                    status_item.setIcon(qta.icon('fa6s.circle-check', color=theme.get_color('success')))
                    status_item.setForeground(QColor(theme.get_color('success')))
                elif status == "Failed":
                    status_item.setIcon(qta.icon('fa6s.circle-xmark', color=theme.get_color('error')))
                    status_item.setForeground(QColor(theme.get_color('error')))
                elif status == "Processing":
                    status_item.setIcon(qta.icon('fa6s.spinner', color=theme.get_color('warning'), spin=1.2))
                    status_item.setForeground(QColor(theme.get_color('warning')))
                elif status.startswith("Error"):
                    status_item.setIcon(qta.icon('fa6s.circle-xmark', color=theme.get_color('error')))
                    status_item.setForeground(QColor(theme.get_color('error')))
                break

    def on_processing_completed(self, processed, total):
        self.status_label.setText(f"Status: Completed ({processed}/{total})")
        self._set_process_button_to_start()
        self.progress_bar.setValue(100)

        # Load last processed result into preview
        if self.loaded_files:
            last_file = self.loaded_files[-1]
            output_dir = self.output_path_input.text().strip() or os.path.join(os.path.dirname(last_file), 'PNG')
            base_name = Path(last_file).stem
            result_path = os.path.join(output_dir, f"{base_name}.png")
            if os.path.exists(result_path):
                self.image_preview.set_images(last_file, result_path)
            else:
                # Try to find any result file
                from glob import glob
                results = glob(os.path.join(output_dir, f"{base_name}*.png"))
                if results:
                    self.image_preview.set_images(last_file, results[0])

        output_path = self.output_path_input.text().strip()
        if output_path and os.path.exists(output_path):
            reply = QMessageBox.question(
                self, "Processing Complete",
                f"Processing complete! {processed}/{total} files saved to:\n{output_path}\n\nOpen output folder?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._open_file_explorer(output_path)

    def on_processing_stopped(self, processed, total):
        self.status_label.setText(f"Status: Stopped ({processed}/{total} processed)")
        self._set_process_button_to_start()

    def on_processing_error(self, error_msg):
        self.status_label.setText("Status: Error")
        self._set_process_button_to_start()
        QMessageBox.critical(self, "Processing Error", error_msg)

    def _open_file_explorer(self, path):
        import platform
        import subprocess
        system = platform.system()
        if system == "Windows":
            subprocess.Popen(['explorer', os.path.normpath(path)])
        elif system == "Darwin":
            subprocess.Popen(['open', path])
        else:
            subprocess.Popen(['xdg-open', path])

    def closeEvent(self, event):
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.stop()
            self.worker_thread.wait(3000)
        if self._mask_thread and self._mask_thread.isRunning():
            if self._mask_worker:
                self._mask_worker.abort = True
            self._mask_thread.quit()
            self._mask_thread.wait(2000)
        super().closeEvent(event)


# Add set_mode method to ImagePreviewWidget for compatibility
def _image_preview_set_mode(self, mode):
    if mode == 'normal':
        self.mask_mode = False
        self.show_after()
    elif mode == 'mask':
        self.mask_mode = True
        self.show_before()

ImagePreviewWidget.set_mode = _image_preview_set_mode