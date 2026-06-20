from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QMessageBox, QAbstractItemView, QHeaderView,
    QVBoxLayout, QWidget, QProgressBar, QMenu, QLabel, QHBoxLayout, QLineEdit,
    QPushButton, QToolTip, QTabWidget, QScrollArea, QFrame, QLayout, QComboBox,
    QSpacerItem, QSizePolicy, QSpinBox, QSlider, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QPoint, QTimer, QRect, QSize, QPoint as QtQPoint, QEvent, QItemSelectionModel, QThread
from PySide6.QtGui import QColor, QBrush, QAction, QGuiApplication, QPixmap, QImage, QFont
from dialogs.file_metadata_dialog import FileMetadataDialog
from dialogs.donation_dialog import DonateDialog, is_donation_optout_today
from ui.file_dnd_widget import DragDropWidget
from ui.DragDropPathMixin import DragDropPathMixin
import qtawesome as qta
import os
import html
import json

from ui.theme_system import theme
from config import BASE_PATH
from helpers.video_proxy_helper import VIDEO_EXTENSIONS
from concurrent.futures import ThreadPoolExecutor, as_completed


class NoDataWidget(QWidget):
    """Widget to display 'No files to load' message consistently across all tabs"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        icon_color = QColor(theme.get_color('primary'))
        icon_color.setAlpha(int(0.85 * 255))
        self.icon_label.setPixmap(qta.icon("fa6s.folder-open", color=icon_color).pixmap(72, 72))
        
        self.text_label = QLabel("No files to load")
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setStyleSheet(f"color: {theme.get_color('primary')}; font-size: 14pt; font-weight: bold;")
        
        self.sub_text = QLabel("Import files or drag and drop files here")
        self.sub_text.setAlignment(Qt.AlignCenter)
        self.sub_text.setStyleSheet(f"color: {theme.get_color('text_dark')}; font-size: 10pt;")
        
        layout.addStretch(1)
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        layout.addWidget(self.sub_text)
        layout.addStretch(1)
        
        video_exts = {
            ".mp4", ".mpeg", ".mov", ".avi", ".flv",
            ".mpg", ".webm", ".wmv", ".3gp", ".3gpp"
        }
        extra_exts = {'.svg', '.eps', '.pdf', '.ai'}
        self._supported_exts = PILLOW_FORMATS | video_exts | extra_exts
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls()]
            for p in paths:
                ext = os.path.splitext(p)[1].lower()
                if ext not in self._supported_exts:
                    event.ignore()
                    return
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls()]
            mainwin = self.window()
            if hasattr(mainwin, "db") and hasattr(mainwin, "table"):
                from helpers.file_importer import import_files
                if import_files(mainwin, mainwin.db, file_paths=paths):
                    mainwin.table.refresh_table()

try:
    from PIL import Image
    PILLOW_FORMATS = set()
    for ext, fmt in Image.registered_extensions().items():
        PILLOW_FORMATS.add(ext.lower())
except ImportError:
    PILLOW_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp', '.eps', '.svg', '.pdf'}

SUPPORTED_IMPORT_EXTENSIONS = PILLOW_FORMATS | set(VIDEO_EXTENSIONS) | {'.svg', '.eps', '.pdf', '.ai'}


def _load_image_qimage(filepath, ext, target_size):
    """Load image from disk into QImage (thread-safe, no QPixmap). Returns QImage or None."""
    if not filepath or not os.path.isfile(filepath):
        return None
    video_exts = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.mpeg', '.mpg', '.3gp', '.3gpp'}
    try:
        if ext in video_exts:
            try:
                import cv2
                cap = cv2.VideoCapture(filepath)
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None:
                    import numpy as np
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = frame_rgb.shape
                    return QImage(frame_rgb.tobytes(), w, h, ch * w, QImage.Format_RGB888).copy()
            except Exception as e:
                print(f"[Thumbnail] Video decode error {filepath}: {e}")
                return None
        elif ext in {'.svg', '.eps', '.pdf', '.ai'}:
            try:
                from helpers.image_compression_helper import ensure_temp_folder, convert_eps_pdf_to_jpg, convert_svg_to_jpg, get_compression_quality, MissingToolError
                temp_folder = ensure_temp_folder()
                quality = get_compression_quality()
                filename = os.path.splitext(os.path.basename(filepath))[0] + "_preview.jpg"
                temp_jpg_path = os.path.join(temp_folder, filename)
                if not os.path.exists(temp_jpg_path):
                    if ext == '.svg':
                        temp_jpg = convert_svg_to_jpg(filepath, temp_jpg_path, quality)
                    else:
                        temp_jpg = convert_eps_pdf_to_jpg(filepath, temp_jpg_path, quality)
                else:
                    temp_jpg = temp_jpg_path
                if temp_jpg and os.path.exists(temp_jpg):
                    from PIL import Image as PilImage
                    with PilImage.open(temp_jpg) as img:
                        img.thumbnail((target_size, target_size))
                        img = img.convert("RGBA")
                        data = img.tobytes("raw", "RGBA")
                        return QImage(data, img.width, img.height, img.width * 4, QImage.Format_RGBA8888).copy()
            except MissingToolError:
                # Tool not installed — skip thumbnail silently (user will be prompted from UI layer)
                return None
            except Exception as e:
                print(f"[Thumbnail] Vector decode error {filepath}: {e}")
                return None
        else:
            try:
                from PIL import Image as PilImage
                with PilImage.open(filepath) as img:
                    img.thumbnail((target_size, target_size))
                    img = img.convert("RGBA")
                    data = img.tobytes("raw", "RGBA")
                    return QImage(data, img.width, img.height, img.width * 4, QImage.Format_RGBA8888).copy()
            except Exception as e:
                print(f"[Thumbnail] Pillow decode error {filepath}: {e}")
                return None
    except Exception as e:
        print(f"[Thumbnail] Unexpected error {filepath}: {e}")
        return None


class ThumbnailLoaderThread(QThread):
    thumbnail_ready = Signal(str, object)   # filepath, QImage or None
    progress_updated = Signal(int, int)     # current, total
    all_done = Signal()

    def __init__(self, files_data, target_size, parent=None):
        super().__init__(parent)
        self.files_data = files_data
        self.target_size = target_size
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def run(self):
        total = len(self.files_data)
        max_workers = min(os.cpu_count() or 2, 4)

        def load_one(file_info):
            filepath = file_info['filepath']
            ext = os.path.splitext(filepath)[1].lower()
            return filepath, _load_image_qimage(filepath, ext, self.target_size)

        completed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(load_one, fi): fi for fi in self.files_data}
            for future in as_completed(futures):
                if self.cancelled:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    filepath, qimage = future.result()
                except Exception as e:
                    fi = futures[future]
                    filepath = fi['filepath']
                    qimage = None
                    print(f"[Thumbnail] Future error {filepath}: {e}")
                completed += 1
                self.progress_updated.emit(completed, total)
                self.thumbnail_ready.emit(filepath, qimage)
        self.all_done.emit()


class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        self._itemList = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing if spacing >= 0 else 0)

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._itemList.append(item)
        self.updateGeometry()
        self.invalidate()

    def count(self):
        return len(self._itemList)

    def itemAt(self, index):
        if 0 <= index < len(self._itemList):
            return self._itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._itemList):
            return self._itemList.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)
        self.update()

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._itemList:
            size = size.expandedTo(item.minimumSize())
        margin = self.contentsMargins()
        size += QSize(margin.left() + margin.right(), margin.top() + margin.bottom())
        return size

    def doLayout(self, rect, testOnly):
        # Respect contents margins when positioning items so top/bottom spacing is correct
        margin = self.contentsMargins()
        x = rect.x() + margin.left()
        y = rect.y() + margin.top()
        lineHeight = 0
        right = rect.x() + rect.width() - margin.right()
        
        if right <= x:
            return 0
        
        for item in self._itemList:
            widget = item.widget()
            if widget and not widget.isVisible():
                continue
                
            spaceX = self.spacing()
            spaceY = self.spacing()
            itemSize = item.sizeHint()
            nextX = x + itemSize.width() + spaceX
            
            if nextX - spaceX > right and x > rect.x() + margin.left():
                x = rect.x() + margin.left()
                y = y + lineHeight + spaceY
                nextX = x + itemSize.width() + spaceX
                lineHeight = 0
                
            if not testOnly:
                item.setGeometry(QRect(QtQPoint(x, y), itemSize))
                if widget:
                    widget.move(x, y)
                    widget.resize(itemSize)
                
            x = nextX
            lineHeight = max(lineHeight, itemSize.height())
            
        # include bottom margin in reported height
        return y + lineHeight + margin.bottom() - rect.y()

    def invalidate(self):
        super().invalidate()
        self.updateGeometry()
                                                               
        if self.parent():
            self.parent().update()

    def updateGeometry(self):
        parent = self.parentWidget()
        if parent is not None:
            parent.updateGeometry()
            self.update()

class GridManager:
    def __init__(self):
        self.image_items = []
        self.image_size = 150
                                                                                         
        self._pixmap_cache_size = max(300, self.image_size * 2)
        self.grid_spacing = 10
        self.active_images = set()
        self._widget_cache = {}
        self._pixmap_cache = {}
        self._status_color_func = None
        self._checked_filepaths = set()
        self._preview_cache = {}

    def set_status_color_func(self, func):
        self._status_color_func = func

    def set_image_size(self, new_size):
        """Update image_size and resize widgets.

        If regenerate_cache is False, only resize widgets and reuse existing cached pixmaps (fast).
        If regenerate_cache is True, clear and rebuild high-res cache then update widgets (slower).
        """
        def _clamp_size(s):
            try:
                s = int(s)
            except Exception:
                return None
            return max(48, s)

        size = _clamp_size(new_size)
        if size is None:
            return
        if size == self.image_size:
            return

        regenerate_cache = True
        self.image_size = size

        self._pixmap_cache_size = max(300, min(1200, int(self.image_size * 2)))

        for filepath, widget in list(self._widget_cache.items()):
            try:
                image_label = None
                text_label = None
                lbls = [c for c in widget.findChildren(QLabel)]
                if lbls:
                    image_label = lbls[0]
                    if len(lbls) > 1:
                        text_label = lbls[1]

                if image_label:
                    image_label.setFixedSize(self.image_size, self.image_size)
                    try:
                        if filepath in self._pixmap_cache and self._pixmap_cache[filepath] is not None:
                            cache_pix = self._pixmap_cache[filepath]
                            pix = cache_pix.scaled(self.image_size, self.image_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            image_label.setPixmap(pix)
                        else:
                                                                                   
                            pm = QPixmap(filepath)
                            if not pm.isNull():
                                pm = pm.scaled(self.image_size, self.image_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                                image_label.setPixmap(pm)
                    except Exception:
                        pass
                if text_label:
                    text_label.setFixedWidth(self.image_size)
                widget.setFixedWidth(self.image_size + 10)
            except Exception as e:
                print(f"Error resizing widget for {filepath}: {e}")

    def regenerate_pixmap_cache(self, done_callback=None):
        """Regenerate high-resolution pixmap cache in background after user stops resizing."""
        self._pixmap_cache_size = max(300, min(1200, int(self.image_size * 2)))
        self._pixmap_cache.clear()
        self._regen_done_callback = done_callback

    def set_checked_filepaths(self, checked_filepaths):
        self._checked_filepaths = set(checked_filepaths)
        self._update_checked_thumbnail_styles()

    def _update_checked_thumbnail_styles(self):
        for filepath, widget in self._widget_cache.items():
            file_info = widget.property("file_info")
            status = file_info.get('status', '') if file_info else ''
            label = None
            for child in widget.children():
                if isinstance(child, QLabel):
                    label = child
                    break
            if label:
                if filepath in self._checked_filepaths:
                    _pr_q = QColor(theme.get_color('primary'))
                    _pr_rgb = f"{_pr_q.red()},{_pr_q.green()},{_pr_q.blue()}"
                    label.setStyleSheet(f"""
                        QLabel {{
                            border: 2.5px solid rgba({_pr_rgb},0.85);
                            border-radius: 4px;
                            padding: 2px;
                            background-color: rgba({_pr_rgb},0.10);
                        }}
                        QLabel:hover {{
                            border: 2.5px solid rgba({_pr_rgb},1.0);
                            background-color: rgba({_pr_rgb},0.18);
                        }}
                    """)
                else:
                    self._set_image(label, filepath, status)

    def _clear_grid(self, grid_widget):
        for item in self.image_items:
            if item:
                try:
                    item.deleteLater()
                except Exception as e:
                    print(f"Error deleting widget: {e}")
        self.image_items.clear()

    def _create_image_widget(self, file_info, load_image=True):
        filepath = file_info['filepath']
        filename = file_info['filename']
        extension = file_info['extension']
        status = file_info.get('status', '')
        cache_key = filepath

        if cache_key in self._widget_cache:
            widget = self._widget_cache[cache_key]
            if load_image:
                self._set_image(widget.findChild(QLabel), filepath, status)
            widget.setProperty("file_info", file_info)
            return widget

        container = QWidget()
        item_width = self.image_size + 10
        container.setFixedWidth(item_width)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setFixedSize(self.image_size, self.image_size)
        image_label.setAttribute(Qt.WA_Hover, True)
        image_label.setCursor(Qt.PointingHandCursor)
        if load_image:
            self._set_image(image_label, filepath, status)
        else:
            image_label.setText("...")
            self._apply_thumbnail_style(image_label, status)
        container._image_label = image_label
        
        full_name = f"{filename}{extension}" if not filename.endswith(extension) else filename
        
        MAX_NAME_LENGTH = 18
        if len(full_name) > MAX_NAME_LENGTH:
            display_name = f"{full_name[:MAX_NAME_LENGTH-3]}..."
        else:
            display_name = full_name
        text_label = QLabel(display_name)
        text_label.setAlignment(Qt.AlignCenter)
        text_label.setWordWrap(False)
        text_label.setFixedWidth(self.image_size)
        text_label.setStyleSheet("font-size: 9pt;")
        text_label.setToolTip(full_name)
        layout.addWidget(image_label)
        layout.addWidget(text_label)
        container.setProperty("file_info", file_info)
        container.setContextMenuPolicy(Qt.CustomContextMenu)
        container.mousePressEvent = lambda event: self._handle_image_click(container, event)
        image_label.mousePressEvent = lambda event: self._handle_image_click(container, event)
        container.mouseDoubleClickEvent = lambda event: self._handle_image_double_click(container)
        image_label.mouseDoubleClickEvent = lambda event: self._handle_image_double_click(container)
        container.customContextMenuEvent = lambda event: self._show_context_menu(container, event)
        image_label.customContextMenuEvent = lambda event: self._show_context_menu(container, event)
        self._widget_cache[cache_key] = container
        return container

    def _set_image(self, label, image_path, status=''):
        parent_widget = label.parent()
        preview_func = None
        while parent_widget is not None:
            if hasattr(parent_widget, "_get_preview_pixmap"):
                preview_func = parent_widget._get_preview_pixmap
                break
            parent_widget = parent_widget.parent()
        pixmap = None
        if preview_func:
            try:
                cache_target = getattr(self, '_pixmap_cache_size', max(self.image_size * 2, 300))
                preview_pm = preview_func(image_path, cache_target)
            except Exception:
                preview_pm = preview_func(image_path, self.image_size)

            if preview_pm and not preview_pm.isNull():
                try:
                    if image_path not in self._pixmap_cache:
                        cached = preview_pm.scaled(self._pixmap_cache_size, self._pixmap_cache_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self._pixmap_cache[image_path] = cached
                except Exception:
                    pass
                cache_pix = self._pixmap_cache.get(image_path, preview_pm)
                if cache_pix and not cache_pix.isNull():
                    pixmap = cache_pix.scaled(self.image_size, self.image_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        else:
            cache_pix = None
            if image_path in self._pixmap_cache:
                cache_pix = self._pixmap_cache[image_path]
            else:
                orig = QPixmap(image_path)
                if not orig.isNull():
                    try:
                        cache_pix = orig.scaled(self._pixmap_cache_size, self._pixmap_cache_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    except Exception:
                        cache_pix = orig.scaled(self.image_size, self.image_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self._pixmap_cache[image_path] = cache_pix
            if cache_pix and not cache_pix.isNull():
                pixmap = cache_pix.scaled(self.image_size, self.image_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        if pixmap and not pixmap.isNull():
            label.setPixmap(pixmap)
        else:
            label.setText("Cannot preview image")
        self._apply_thumbnail_style(label, status)

    def _apply_thumbnail_style(self, label, status=''):
        color = None
        if self._status_color_func:
            color = self._status_color_func(status)
        if color is None:
            _blk_def = QColor(theme.get_color('black'))
            _blk_def.setAlpha(int(0.1 * 255))
            color = _blk_def
        border_rgba = f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()/255:.2f})"
        _pr_q_local = QColor(theme.get_color('primary'))
        _pr_rgb_local = f"{_pr_q_local.red()},{_pr_q_local.green()},{_pr_q_local.blue()}"
        status_alpha = 0.0
        if status == "success":
            status_alpha = 0.18
        elif status in ("processing", "stopping"):
            status_alpha = 0.18
        elif status == "failed":
            status_alpha = 0.18
        elif status == "stopped":
            status_alpha = 0.18
        bg_color = f"transparent" if status_alpha == 0 else f"rgba({color.red()}, {color.green()}, {color.blue()}, {status_alpha})"
        label.setStyleSheet(f"""
            QLabel {{
                border: 2px solid {border_rgba};
                border-radius: 4px;
                padding: 2px;
                background-color: {bg_color};
            }}
            QLabel:hover {{
                border: 2.5px solid rgba({_pr_rgb_local},0.7);
                background-color: rgba({_pr_rgb_local},0.12);
            }}
        """)

    def update_thumbnail_status(self, filepath, status):
        widget = self._widget_cache.get(filepath)
        if widget:
            file_info = widget.property("file_info")
            if file_info is not None:
                file_info['status'] = status
                widget.setProperty("file_info", file_info)
            
            label = None
            for child in widget.children():
                if isinstance(child, QLabel):
                    label = child
                    break
            if label:
                self._set_image(label, filepath, status)

    def _update_active_images(self, new_active_widgets):
        try:
            for old_widget in self.active_images:
                for child in old_widget.children():
                    if isinstance(child, QLabel) and child.objectName() != "filename_label":
                        file_info = old_widget.property("file_info")
                        status = file_info.get('status', '') if file_info else ''
                        color = None
                        if self._status_color_func:
                            color = self._status_color_func(status)
                        if color is None:
                            _blk_def2 = QColor(theme.get_color('black'))
                            _blk_def2.setAlpha(int(0.1 * 255))
                            color = _blk_def2
                        border_rgba = f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()/255:.2f})"
                        _pr_q2 = QColor(theme.get_color('primary'))
                        _pr_rgb2 = f"{_pr_q2.red()},{_pr_q2.green()},{_pr_q2.blue()}"
                        status_alpha = 0.0
                        if status == "success":
                            status_alpha = 0.18
                        elif status in ("processing", "stopping"):
                            status_alpha = 0.18
                        elif status == "failed":
                            status_alpha = 0.18
                        elif status == "stopped":
                            status_alpha = 0.18
                        bg_color = f"transparent" if status_alpha == 0 else f"rgba({color.red()}, {color.green()}, {color.blue()}, {status_alpha})"
                        child.setStyleSheet(f"""
                            QLabel {{
                                border: 2px solid {border_rgba};
                                border-radius: 4px;
                                padding: 2px;
                                background-color: {bg_color};
                            }}
                            QLabel:hover {{
                                border: 2.5px solid rgba({_pr_rgb2},0.7);
                                background-color: rgba({_pr_rgb2},0.12);
                            }}
                        """)
                        break
            self.active_images = set(new_active_widgets) if new_active_widgets else set()
            for active_widget in self.active_images:
                for child in active_widget.children():
                    if isinstance(child, QLabel) and child.objectName() != "filename_label":
                        _pr_q3 = QColor(theme.get_color('primary'))
                        _pr_rgb3 = f"{_pr_q3.red()},{_pr_q3.green()},{_pr_q3.blue()}"
                        child.setStyleSheet(f"""
                            QLabel {{
                                border: 2px solid rgba({_pr_rgb3},0.7);
                                border-radius: 4px;
                                padding: 2px;
                                background-color: rgba({_pr_rgb3},0.20);
                            }}
                            QLabel:hover {{
                                border: 2.5px solid rgba({_pr_rgb3},1.0);
                                background-color: rgba({_pr_rgb3},0.30);
                            }}
                        """)
                        break
        except Exception as e:
            print(f"Error updating active images styling: {e}")

    def _handle_image_click(self, widget, event):
        try:
            if event.button() == Qt.RightButton:
                self._show_context_menu(widget, event)
                return
            if event.type() == QEvent.MouseButtonDblClick:
                self._handle_image_double_click(widget)
                return
            file_info = widget.property("file_info")
            if not file_info:
                return
            self._update_active_images([widget])
            parent_widget = widget.parent()
            while parent_widget and not hasattr(parent_widget, '_callback_function'):
                parent_widget = parent_widget.parent()
            if parent_widget and hasattr(parent_widget, '_callback_function'):
                callback_function = parent_widget._callback_function
                if callback_function:
                    callback_function(0, 0, file_info)
        except Exception as e:
            print(f"Error handling grid image click: {e}")

    def _handle_image_double_click(self, widget):
        try:
            file_info = widget.property("file_info")
            if not file_info:
                return
            parent_widget = widget.parent()
            while parent_widget and not hasattr(parent_widget, '_open_metadata_dialog'):
                parent_widget = parent_widget.parent()
            if parent_widget and hasattr(parent_widget, '_open_metadata_dialog'):
                parent_widget._open_metadata_dialog_by_filepath(file_info['filepath'])
        except Exception as e:
            print(f"Error handling grid image double click: {e}")

    def _show_context_menu(self, widget, event):
        try:
            file_info = widget.property("file_info")
            if not file_info:
                return

            backend_row = None

            current_rows = getattr(self, '_current_rows', None)
            db = getattr(self, 'db', None)
            parent = widget.parent()
            while parent is not None and (current_rows is None or db is None):
                if current_rows is None and hasattr(parent, '_current_rows'):
                    current_rows = getattr(parent, '_current_rows')
                if db is None and hasattr(parent, 'db'):
                    db = getattr(parent, 'db')
                parent = parent.parent()

            if current_rows:
                for row in current_rows:
                    try:
                        if row[1] == file_info['filepath']:
                            backend_row = row
                            break
                    except Exception:
                        continue

            if backend_row is None and db is not None:
                all_files = db.get_all_files()
                for row in all_files:
                    if row[1] == file_info['filepath']:
                        backend_row = row
                        break

            if backend_row is None:
                print(f"Error: backend_row not found for filepath {file_info['filepath']}")
                return

            menu = QMenu(widget)
            edit_icon = qta.icon("fa6s.pen-to-square")
            edit_action = QAction(edit_icon, "Edit metadata", widget)
            edit_action.triggered.connect(lambda: self._open_metadata_dialog_from_grid(widget))
            menu.addAction(edit_action)

            filename = backend_row[2]
            title = backend_row[3]
            description = backend_row[4]
            tags = backend_row[5]

            copy_filename_action = QAction(qta.icon("fa6s.copy"), "Copy Filename", widget)
            copy_filename_action.triggered.connect(lambda: self._copy_to_clipboard_with_tooltip(filename, "Filename", event))
            menu.addAction(copy_filename_action)

            copy_title_action = QAction(qta.icon("fa6s.copy"), "Copy Title", widget)
            copy_title_action.triggered.connect(lambda: self._copy_to_clipboard_with_tooltip(title, "Title", event))
            menu.addAction(copy_title_action)

            copy_desc_action = QAction(qta.icon("fa6s.copy"), "Copy Description", widget)
            copy_desc_action.triggered.connect(lambda: self._copy_to_clipboard_with_tooltip(description, "Description", event))
            menu.addAction(copy_desc_action)

            copy_tags_action = QAction(qta.icon("fa6s.copy"), "Copy Keyword", widget)
            copy_tags_action.triggered.connect(lambda: self._copy_to_clipboard_with_tooltip(tags, "Keyword", event))
            menu.addAction(copy_tags_action)

            menu.exec(event.globalPos() if hasattr(event, "globalPos") else widget.mapToGlobal(event.pos()))
        except Exception as e:
            print(f"Error showing context menu in grid: {e}")

    def _copy_to_clipboard_with_tooltip(self, text, label, event):
        QGuiApplication.clipboard().setText("" if text is None else text)
        def shorten(val, maxlen=60):
            if val is None:
                return ""
            val = val.strip()
            if len(val) > maxlen:
                return val[:maxlen-3] + "..."
            return val
        value = shorten(text)
        tooltip = f"Copied {label}: {value}" if value else f"Copied {label}: (empty)"
        global_pos = event.globalPos() if hasattr(event, "globalPos") else None
        QToolTip.showText(global_pos, tooltip)
        QTimer.singleShot(1200, QToolTip.hideText)

    def _open_metadata_dialog_from_grid(self, widget):
        try:
            file_info = widget.property("file_info")
            if not file_info:
                return
            parent_widget = widget.parent()
            while parent_widget and not hasattr(parent_widget, '_open_metadata_dialog'):
                parent_widget = parent_widget.parent()
            if parent_widget and hasattr(parent_widget, '_open_metadata_dialog'):
                parent_widget._open_metadata_dialog_by_filepath(file_info['filepath'])
        except Exception as e:
            print(f"Error opening metadata dialog from grid: {e}")

    def setup_grid_click_handler(self, grid_widget, callback_function):
        if not grid_widget:
            print("Grid widget not provided, can't set up click handler")
            return
        grid_widget._callback_function = callback_function

class DragDropScrollArea(QScrollArea):
    """Scroll area that supports drag and drop"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        
        video_exts = {
            ".mp4", ".mpeg", ".mov", ".avi", ".flv",
            ".mpg", ".webm", ".wmv", ".3gp", ".3gpp"
        }
        extra_exts = {'.svg', '.eps', '.pdf', '.ai'}
        self._supported_exts = PILLOW_FORMATS | video_exts | extra_exts
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls()]
            for p in paths:
                ext = os.path.splitext(p)[1].lower()
                if ext not in self._supported_exts:
                    event.ignore()
                    return
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls()]
            mainwin = self.window()
            if hasattr(mainwin, "db") and hasattr(mainwin, "table"):
                from helpers.file_importer import import_files
                if import_files(mainwin, mainwin.db, file_paths=paths):
                    mainwin.table.refresh_table()

class DragDropThumbnailTab(QWidget):
    """Thumbnail tab widget with drag and drop support"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._parent_table = parent
        
        video_exts = {
            ".mp4", ".mpeg", ".mov", ".avi", ".flv",
            ".mpg", ".webm", ".wmv", ".3gp", ".3gpp"
        }
        extra_exts = {'.svg', '.eps', '.pdf', '.ai'}
        self._supported_exts = PILLOW_FORMATS | video_exts | extra_exts
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls()]
            for p in paths:
                ext = os.path.splitext(p)[1].lower()
                if ext not in self._supported_exts:
                    event.ignore()
                    return
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls()]
            mainwin = self.window()
            if hasattr(mainwin, "db") and hasattr(mainwin, "table"):
                from helpers.file_importer import import_files
                if import_files(mainwin, mainwin.db, file_paths=paths):
                    mainwin.table.refresh_table()

class DragDropTableTab(QWidget):
    """Table tab widget with drag and drop support"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._parent_table = parent
        
        video_exts = {
            ".mp4", ".mpeg", ".mov", ".avi", ".flv",
            ".mpg", ".webm", ".wmv", ".3gp", ".3gpp"
        }
        extra_exts = {'.svg', '.eps', '.pdf', '.ai'}
        self._supported_exts = PILLOW_FORMATS | video_exts | extra_exts
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls()]
            for p in paths:
                ext = os.path.splitext(p)[1].lower()
                if ext not in self._supported_exts:
                    event.ignore()
                    return
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls()]
            mainwin = self.window()
            if hasattr(mainwin, "db") and hasattr(mainwin, "table"):
                from helpers.file_importer import import_files
                if import_files(mainwin, mainwin.db, file_paths=paths):
                    mainwin.table.refresh_table()


class DragDropDetailsTab(QWidget):
    """Details tab widget with drag and drop support"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._parent_table = parent
        
        video_exts = {
            ".mp4", ".mpeg", ".mov", ".avi", ".flv",
            ".mpg", ".webm", ".wmv", ".3gp", ".3gpp"
        }
        extra_exts = {'.svg', '.eps', '.pdf', '.ai'}
        self._supported_exts = PILLOW_FORMATS | video_exts | extra_exts
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls()]
            for p in paths:
                ext = os.path.splitext(p)[1].lower()
                if ext not in self._supported_exts:
                    event.ignore()
                    return
            event.acceptProposedAction()
        else:
            event.ignore()
            
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [url.toLocalFile() for url in event.mimeData().urls()]
            mainwin = self.window()
            if hasattr(mainwin, "db") and hasattr(mainwin, "table"):
                from helpers.file_importer import import_files
                if import_files(mainwin, mainwin.db, file_paths=paths):
                    mainwin.table.refresh_table()

class ImageTableWidget(QWidget):
    stats_changed = Signal(int, int, int, int, int)
    data_refreshed = Signal()

    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        self.db = db
        self._properties_widget = getattr(parent, "properties_widget", None)
        self._main_window = parent
        
        self.current_page = 1
        self.page_size = 20
        self.total_count = 0
        self.search_text = ""
        self._page_cache = {}
        self._current_rows = []
        self._refreshing_details = False
        self._refreshing_thumbnails = False
        self._checkbox_dragging = False
        self._drag_check_state = None
        self.flow_mode_enabled = False
        self.flow_mode_source_path = ""
        self.flow_mode_files = []
        self.flow_mode_imported_files = set()
        self.flow_mode_last_scan_error = ""
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Search...")
        self.search_edit.setClearButtonEnabled(False)
        
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_search)
        
        self.search_edit.textChanged.connect(self._on_search_text_changed_delayed)
        search_icon_btn = QPushButton(self)
        search_icon_btn.setIcon(qta.icon("fa6s.magnifying-glass"))
        search_icon_btn.setFlat(True)
        search_icon_btn.setFocusPolicy(Qt.NoFocus)
        search_icon_btn.setEnabled(False)
        search_icon_btn.setFixedWidth(28)
        paste_btn = QPushButton(self)
        paste_btn.setIcon(qta.icon("fa6s.clipboard"))
        paste_btn.setFlat(True)
        paste_btn.setFocusPolicy(Qt.NoFocus)
        paste_btn.setFixedWidth(28)
        paste_btn.setToolTip("Paste text from clipboard to search field")
        paste_btn.clicked.connect(self._on_paste_clicked)
        clear_btn = QPushButton(self)
        clear_btn.setIcon(qta.icon("fa6s.xmark"))
        clear_btn.setFlat(True)
        clear_btn.setFocusPolicy(Qt.NoFocus)
        clear_btn.setFixedWidth(28)
        clear_btn.setToolTip("Clear the search field")
        clear_btn.clicked.connect(self._on_clear_search)
        reload_btn = QPushButton(self)
        reload_btn.setIcon(qta.icon("fa6s.rotate-right"))
        reload_btn.setFlat(True)
        reload_btn.setFocusPolicy(Qt.NoFocus)
        reload_btn.setFixedWidth(28)
        reload_btn.setToolTip("Reload/refresh data from database")
        reload_btn.clicked.connect(self._on_reload_clicked)
        
        self.prev_btn = QPushButton(self)
        self.prev_btn.setIcon(qta.icon("fa6s.chevron-left"))
        self.prev_btn.setFlat(True)
        self.prev_btn.setFocusPolicy(Qt.NoFocus)
        self.prev_btn.setFixedWidth(32)
        self.prev_btn.setToolTip("Previous page")
        self.prev_btn.clicked.connect(self._on_prev_page)
        
        self.page_spinner = QSpinBox(self)
        self.page_spinner.setMinimum(1)
        self.page_spinner.setMaximum(1)
        self.page_spinner.setValue(1)
        self.page_spinner.setFixedWidth(60)
        self.page_spinner.setToolTip("Current page")
        self.page_spinner.valueChanged.connect(self._on_page_spinner_changed)
        
        self.total_pages_label = QLabel("/1")
        self.total_pages_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.total_pages_label.setMinimumWidth(30)
        self.total_pages_label.setStyleSheet(f"font-weight: bold; color: {theme.get_color('text_dark')};")
        
        self.next_btn = QPushButton(self)
        self.next_btn.setIcon(qta.icon("fa6s.chevron-right"))
        self.next_btn.setFlat(True)
        self.next_btn.setFocusPolicy(Qt.NoFocus)
        self.next_btn.setFixedWidth(32)
        self.next_btn.setToolTip("Next page")
        self.next_btn.clicked.connect(self._on_next_page)
        
        self.page_size_combo = QComboBox(self)
        self.page_size_combo.addItems(["10", "20", "30", "50", "100"])
        self.page_size_combo.setCurrentText("20")
        self.page_size_combo.setFixedWidth(60)
        self.page_size_combo.setToolTip("Items per page")
        self.page_size_combo.currentTextChanged.connect(self._on_page_size_changed)
        
        self.sort_filter_combo = QComboBox(self)
        self.sort_filter_combo.addItems(["All Files", "Success Only", "Failed Only", "Draft Only"])
        self.sort_filter_combo.setCurrentText("All Files")
        self.sort_filter_combo.setFixedWidth(120)
        self.sort_filter_combo.setToolTip("Filter files by status")
        self.sort_filter_combo.currentTextChanged.connect(self._on_sort_filter_changed)
        
        search_layout.addWidget(search_icon_btn)
        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(paste_btn)
        search_layout.addWidget(clear_btn)
        search_layout.addWidget(reload_btn)
        search_layout.addWidget(self.prev_btn)
        search_layout.addWidget(self.page_spinner)
        search_layout.addWidget(self.total_pages_label)
        search_layout.addWidget(self.next_btn)
        search_layout.addWidget(self.page_size_combo)
        search_layout.addWidget(self.sort_filter_combo)
        self.layout.addLayout(search_layout)
        self.tab_widget = QTabWidget(self)
        self.layout.addWidget(self.tab_widget)
        
        self.table_tab = DragDropTableTab(self)
        self.table_tab_layout = QVBoxLayout(self.table_tab)
        self.table_tab_layout.setContentsMargins(0, 0, 0, 0)
        
        self.add_files_tab = QWidget()
        self.add_files_tab_layout = QVBoxLayout(self.add_files_tab)
        self.add_files_tab_layout.setContentsMargins(0, 0, 0, 0)
        
        self.dnd_widget = DragDropWidget(self.add_files_tab)
        self.add_files_tab_layout.addWidget(self.dnd_widget)

        self.flow_mode_tab = QWidget()
        self.flow_mode_tab_layout = QVBoxLayout(self.flow_mode_tab)
        self.flow_mode_tab_layout.setContentsMargins(10, 10, 10, 10)
        self.flow_mode_tab_layout.setSpacing(10)

        flow_path_layout = QHBoxLayout()
        self.flow_mode_path_edit = QLineEdit(self.flow_mode_tab)
        self.flow_mode_path_edit.setPlaceholderText("Select or drop a source folder...")
        self.flow_mode_path_edit.setAcceptDrops(True)
        self.flow_mode_path_edit.setToolTip("Source folder for Flow Mode. Files remain on disk and are imported to DB automatically per batch.")
        self.flow_mode_path_edit.dragEnterEvent = DragDropPathMixin.make_drag_enter_handler(self.flow_mode_path_edit)
        self.flow_mode_path_edit.dropEvent = DragDropPathMixin.make_drop_handler(self.flow_mode_path_edit, 'folder', self._on_flow_mode_path_dropped)
        flow_path_layout.addWidget(self.flow_mode_path_edit)

        self.flow_mode_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), "Browse Folder")
        self.flow_mode_browse_btn.clicked.connect(self._browse_flow_mode_folder)
        flow_path_layout.addWidget(self.flow_mode_browse_btn)

        self.flow_mode_refresh_btn = QPushButton(qta.icon('fa6s.rotate-right'), "Refresh")
        self.flow_mode_refresh_btn.clicked.connect(self.refresh_flow_mode_source)
        flow_path_layout.addWidget(self.flow_mode_refresh_btn)
        self.flow_mode_tab_layout.addLayout(flow_path_layout)

        flow_header = QLabel("Flow Mode helps scan a folder and auto-import files to the database only when generation needs them.")
        flow_header.setWordWrap(True)
        flow_header.setStyleSheet(f"color: {theme.get_color('text_dark')}; font-size: 10pt;")
        self.flow_mode_tab_layout.addWidget(flow_header)

        flow_source_layout = QVBoxLayout()
        flow_source_layout.setSpacing(2)
        self.flow_mode_source_title_label = QLabel("Source Path")
        self.flow_mode_source_title_label.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 9pt; font-weight: bold;")
        flow_source_layout.addWidget(self.flow_mode_source_title_label)
        self.flow_mode_source_label = QLabel("-")
        self.flow_mode_source_label.setStyleSheet(f"color: {theme.get_color('text_dark')}; font-size: 9pt;")
        self.flow_mode_source_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.flow_mode_source_label.setWordWrap(False)
        self.flow_mode_source_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        flow_source_layout.addWidget(self.flow_mode_source_label)
        self.flow_mode_tab_layout.addLayout(flow_source_layout)

        flow_stats_layout = QHBoxLayout()
        self.flow_mode_total_label = QLabel("Total Files: 0")
        self.flow_mode_pending_label = QLabel("Pending Import: 0")
        self.flow_mode_db_label = QLabel("Already In DB: 0")
        for label in [self.flow_mode_total_label, self.flow_mode_pending_label, self.flow_mode_db_label]:
            label.setStyleSheet(f"color: {theme.get_color('text_dark')}; font-size: 9pt;")
            flow_stats_layout.addWidget(label)
        flow_stats_layout.addStretch()
        self.flow_mode_tab_layout.addLayout(flow_stats_layout)

        self.flow_mode_status_label = QLabel("Choose a folder to start Flow Mode.")
        self.flow_mode_status_label.setWordWrap(True)
        self.flow_mode_status_label.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 9pt;")
        self.flow_mode_tab_layout.addWidget(self.flow_mode_status_label)

        self.flow_mode_table = QTableWidget(0, 1, self.flow_mode_tab)
        self.flow_mode_table.setHorizontalHeaderLabels(["Files"])
        self.flow_mode_table.verticalHeader().setVisible(True)
        self.flow_mode_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.flow_mode_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.flow_mode_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.flow_mode_tab_layout.addWidget(self.flow_mode_table)
        
        table_container = QWidget()
        table_container_layout = QVBoxLayout(table_container)
        table_container_layout.setContentsMargins(0, 0, 0, 0)
        
        self.table = QTableWidget(0, 9, self)
        headers = ["", "Filepath", "Filename", "Title", "Description", "Tags", "Title Length", "Tag Count", "Status"]
        icon_color = theme.get_color('text_dark')
        icons = [
            None,
            qta.icon("fa6s.folder-open", color=icon_color),
            qta.icon("fa6s.file", color=icon_color),
            qta.icon("fa6s.heading", color=icon_color),
            qta.icon("fa6s.align-left", color=icon_color),
            qta.icon("fa6s.tags", color=icon_color),
            qta.icon("fa6s.text-height", color=icon_color),
            qta.icon("fa6s.hashtag", color=icon_color),
            qta.icon("fa6s.circle-info", color=icon_color),
        ]
        for col, text in enumerate(headers):
            if icons[col] is not None:
                item = QTableWidgetItem(icons[col], text)
            else:
                item = QTableWidgetItem(text)
            self.table.setHorizontalHeaderItem(col, item)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for col in range(0, 9):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        table_container_layout.addWidget(self.table)
        
        self.table_no_data_overlay = NoDataWidget()
        self.table_no_data_overlay.setVisible(False)
        table_container_layout.addWidget(self.table_no_data_overlay)
        
        self.table_tab_layout.addWidget(table_container)
        
        self.thumbnail_tab = DragDropThumbnailTab(self)
        self.thumbnail_tab_layout = QVBoxLayout(self.thumbnail_tab)
        self.thumbnail_tab_layout.setContentsMargins(0, 0, 0, 0)
        self.thumbnail_tab_layout.setSpacing(2)
        
        thumbnail_controls_layout = QHBoxLayout()
        thumbnail_controls_layout.setContentsMargins(4, 2, 4, 2)
        thumbnail_controls_layout.setSpacing(8)
        thumbnail_controls_layout.setAlignment(Qt.AlignVCenter)

        self.zoom_label = QLabel("Columns per Row:")
        self.zoom_label.setStyleSheet(f"font-size: 9pt; color: {theme.get_color('text_dark')};")
        self.zoom_label.setFixedHeight(22)
        self.zoom_label.setContentsMargins(0, 0, 0, 0)
        thumbnail_controls_layout.addWidget(self.zoom_label)
        
        self.zoom_preset_combo = QComboBox(self)
        self.zoom_preset_combo.addItems(["1 Column", "2 Columns", "3 Columns", "4 Columns", "5 Columns", "6 Columns", "7 Columns", "8 Columns", "9 Columns", "10 Columns", "11 Columns", "12 Columns", "13 Columns", "14 Columns", "15 Columns"])
        self.zoom_preset_combo.setCurrentText("4 Columns")
        self.zoom_preset_combo.setFixedWidth(120)
        self.zoom_preset_combo.setFixedHeight(22)
        self.zoom_preset_combo.setToolTip("Select number of thumbnail columns per row (or use Ctrl+Scroll to zoom)")
        self.zoom_preset_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.zoom_preset_combo.currentTextChanged.connect(self._on_zoom_preset_changed)
        thumbnail_controls_layout.addWidget(self.zoom_preset_combo)
        
        self.zoom_slider = QSlider(Qt.Horizontal, self)
        self.zoom_slider.setRange(48, 800)
        self.zoom_slider.setSingleStep(4)
        self.zoom_slider.setPageStep(16)
        self.zoom_slider.setValue(150)
        self.zoom_slider.setFixedWidth(220)
        self.zoom_slider.setFixedHeight(22)
        self.zoom_slider.setToolTip("Zoom thumbnails")
        self.zoom_slider.valueChanged.connect(self._on_zoom_slider_changed)
        self.zoom_slider.setStyleSheet(theme.get_slider_style())
        thumbnail_controls_layout.addWidget(self.zoom_slider)
        
        self._current_column_count = 4
        
        thumbnail_controls_layout.addStretch()
        self.thumbnail_tab_layout.addLayout(thumbnail_controls_layout)
        
        self.thumbnail_scroll = DragDropScrollArea(self.thumbnail_tab)
        self.thumbnail_scroll.setContentsMargins(0, 0, 0, 0)
        self.thumbnail_scroll.setWidgetResizable(True)
        self.thumbnail_scroll.setFrameShape(QFrame.NoFrame)
        self.thumbnail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.thumbnail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.thumbnail_scroll.viewport().setContentsMargins(0, 0, 0, 0)
        self.thumbnail_tab_layout.addWidget(self.thumbnail_scroll)
        self.thumbnail_content = QWidget()
        self.thumbnail_content.setContentsMargins(0, 0, 0, 0)
        self.thumbnail_content.setAcceptDrops(True)
        self.thumbnail_scroll.setWidget(self.thumbnail_content)
        self.thumbnail_flow = FlowLayout(margin=2, spacing=6)
        self.thumbnail_content.setLayout(self.thumbnail_flow)
        
        self.thumbnail_no_data_overlay = NoDataWidget()
        self.thumbnail_no_data_overlay.setVisible(False)
        self.thumbnail_tab_layout.addWidget(self.thumbnail_no_data_overlay)
        
        self.details_tab = DragDropDetailsTab(self)
        self.details_tab_layout = QVBoxLayout(self.details_tab)
        self.details_tab_layout.setContentsMargins(0, 0, 0, 0)
        
        self.details_scroll = QScrollArea(self.details_tab)
        self.details_scroll.setWidgetResizable(True)
        self.details_scroll.setFrameShape(QFrame.NoFrame)
        self.details_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.details_tab_layout.addWidget(self.details_scroll)
        self.details_content = QWidget()
        self.details_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.details_scroll.setWidget(self.details_content)
        self.details_vbox = QVBoxLayout(self.details_content)
        self.details_vbox.setContentsMargins(10, 10, 10, 10)
        self.details_vbox.setSpacing(10)
        self.details_vbox.setAlignment(Qt.AlignTop)
        
        self.details_no_data_overlay = NoDataWidget()
        self.details_no_data_overlay.setVisible(False)
        self.details_tab_layout.addWidget(self.details_no_data_overlay)
        
        self.tab_widget.addTab(self.details_tab, "Details")
        
        self.tab_widget.clear()
        self.tab_widget.addTab(self.table_tab, qta.icon("fa6s.table"), "Table")
        self.tab_widget.addTab(self.thumbnail_tab, qta.icon("fa6s.images"), "Thumbnail") 
        self.tab_widget.addTab(self.details_tab, qta.icon("fa6s.list"), "Details")
        self.tab_widget.addTab(self.add_files_tab, qta.icon("fa6s.folder-plus"), "Add Files")
        self.tab_widget.addTab(self.flow_mode_tab, qta.icon("fa6s.diagram-project"), "Flow Mode")
        self.tab_widget.currentChanged.connect(self._update_tab_icons)
        self._update_tab_icons(self.tab_widget.currentIndex())
        
                                                                               
        progress_layout = QVBoxLayout()
        progress_layout.setContentsMargins(4, 4, 4, 4)
        progress_layout.setSpacing(2)
        
        self.progress_label = QLabel("Ready")
        self.progress_label.setAlignment(Qt.AlignLeft)
        self.progress_label.setStyleSheet(f"font-size: 9pt; color: {theme.get_color('text_dark')};")
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(20)
        self.progress_bar.setVisible(False)
        self.progress_bar.setToolTip("Shows progress for batch operations")
        self.progress_bar.setStyleSheet("QProgressBar { margin-left: 2px; margin-right: 2px; }")
        progress_layout.addWidget(self.progress_bar)
        
        self.layout.addLayout(progress_layout)
        
        self.details_card_cache = {}
        self._donation_dialog_shown = False
        self.table.selectionModel().selectionChanged.connect(self._emit_stats)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.viewport().installEventFilter(self)
        self.table.setMouseTracking(True)
                                                                    
        self._last_hover_row = None
                                                           
        self._tooltip_max_width = 360
        self._current_rows = []
        self.grid_manager = GridManager()
        self.grid_manager.set_status_color_func(self._status_color)
        self.grid_manager.setup_grid_click_handler(self.thumbnail_content, self._on_thumbnail_clicked)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self._inject_open_metadata_dialog_for_grid()
        self.thumbnail_scroll.installEventFilter(self)
                                                                   
        self.thumbnail_scroll.viewport().installEventFilter(self)

                                                                                               
        self._pending_thumb_size = None
        self._thumb_resize_timer = QTimer(self)
        self._thumb_resize_timer.setSingleShot(True)
        self._thumb_resize_timer.setInterval(500)
        self._thumb_resize_timer.timeout.connect(self._apply_debounced_thumbnail_resize)
        
        self._resize_recalc_timer = QTimer(self)
        self._resize_recalc_timer.setSingleShot(True)
        self._resize_recalc_timer.setInterval(150)
        self._resize_recalc_timer.timeout.connect(self._recalculate_thumbnail_size_from_columns)

                                                          
        self._pending_hover_row = None
        self._pending_tooltip_global_pos = None
        self._pending_tooltip_content = ""
        self._tooltip_timer = QTimer(self)
        self._tooltip_timer.setSingleShot(True)
        self._tooltip_timer.setInterval(0)
        self._tooltip_timer.timeout.connect(self._show_pending_tooltip)

        self.refresh_table()
        QTimer.singleShot(0, self._init_thumbnail_column_count)

    def _update_zoom_controls_visibility(self):
        has_files = self.total_count > 0
        if hasattr(self, 'zoom_label'):
            self.zoom_label.setVisible(has_files)
        if hasattr(self, 'zoom_preset_combo'):
            self.zoom_preset_combo.setVisible(has_files)
        if hasattr(self, 'zoom_slider'):
            self.zoom_slider.setVisible(has_files)

    def eventFilter(self, obj, event):
        """Handle resize events to force thumbnail layout refresh and checkbox drag selection"""
                                                 
        if obj == self.table.viewport():
            if event.type() == QEvent.MouseButtonPress:
                pos = event.pos()
                index = self.table.indexAt(pos)
                if index.isValid() and index.column() == 0:
                    item = self.table.item(index.row(), 0)
                    if item:
                        self._checkbox_dragging = True
                        self._drag_check_state = item.checkState() == Qt.Unchecked
                        new_state = Qt.Checked if self._drag_check_state else Qt.Unchecked
                        item.setCheckState(new_state)
                        self._update_thumbnail_checklist_style()
                        return True
            elif event.type() == QEvent.MouseMove and self._checkbox_dragging:
                pos = event.pos()
                index = self.table.indexAt(pos)
                if index.isValid() and index.column() == 0:
                    item = self.table.item(index.row(), 0)
                    if item:
                        new_state = Qt.Checked if self._drag_check_state else Qt.Unchecked
                        if item.checkState() != new_state:
                            item.setCheckState(new_state)
                            self._update_thumbnail_checklist_style()
                return True
            elif event.type() == QEvent.MouseButtonRelease:
                if self._checkbox_dragging:
                    self._checkbox_dragging = False
                    self._drag_check_state = None
                    return True
        
                                                                                   
        if obj == self.table.viewport() and event.type() == QEvent.MouseMove and not self._checkbox_dragging:
            pos = event.pos()
            index = self.table.indexAt(pos)
            if index.isValid():
                row = index.row()
                                                                          
                if row == self._last_hover_row:
                    pass
                elif row == getattr(self, '_pending_hover_row', None):
                                                                            
                    self._pending_tooltip_global_pos = self.table.viewport().mapToGlobal(pos)
                else:
                                                                                           
                    if row != getattr(self, '_pending_hover_row', None):
                        try:
                            self._tooltip_timer.stop()
                        except Exception:
                            pass
                                                                                                           
                        try:
                            QToolTip.hideText()
                        except Exception:
                            pass
                                                                                   
                        self._last_hover_row = None

                        tooltip = self._get_tooltip_for_row_index(row)
                        global_pos = self.table.viewport().mapToGlobal(pos)
                        if tooltip:
                                                                                
                            self._pending_hover_row = row
                            self._pending_tooltip_global_pos = global_pos
                            self._pending_tooltip_content = tooltip
                            try:
                                self._show_pending_tooltip()
                            except Exception as e:
                                print(f"[Tooltip] Failed to show tooltip immediately: {e}")
                        else:
                                                                                           
                            self._pending_hover_row = None
                            self._pending_tooltip_global_pos = None
                            self._pending_tooltip_content = ""
            else:
                                                                                          
                try:
                    self._tooltip_timer.stop()
                except Exception:
                    pass
                if self._last_hover_row is not None:
                    QToolTip.hideText()
                    self._last_hover_row = None
                self._pending_hover_row = None
                self._pending_tooltip_global_pos = None
                self._pending_tooltip_content = ""

                                  
        if obj == self.thumbnail_scroll and event.type() == QEvent.Resize:
            if self.tab_widget.currentIndex() == 1:
                self._resize_recalc_timer.start()
                return True

                                              
        if event.type() == QEvent.Wheel and self.tab_widget.currentIndex() == 1:
                                                                    
            if obj in (self.thumbnail_scroll, self.thumbnail_scroll.viewport(), self.thumbnail_content):
                from PySide6.QtWidgets import QApplication
                mods = QApplication.keyboardModifiers()
                if mods & Qt.ControlModifier:
                                                                    
                    delta = 0
                    try:
                        delta = event.angleDelta().y()
                    except Exception:
                        pass
                    if delta == 0:
                        return True
                    steps = delta / 120.0
                    step_size = 12
                    new_size = int(self.grid_manager.image_size + steps * step_size)
                           
                    new_size = max(48, min(600, new_size))

                    self.grid_manager.set_image_size(new_size)
                    
                    self._update_zoom_preset_dropdown(new_size)
                    
                    self._pending_thumb_size = new_size
                    self._thumb_resize_timer.start()

                    QTimer.singleShot(0, self._force_thumbnail_layout_refresh)
                    return True

        return super().eventFilter(obj, event)

    def _show_pending_tooltip(self):
        """Show tooltip scheduled by hover debounce timer."""
        try:
            pending_row = getattr(self, '_pending_hover_row', None)
            tooltip = getattr(self, '_pending_tooltip_content', '')
            pos = getattr(self, '_pending_tooltip_global_pos', None)
            if pending_row is None or not tooltip or pos is None:
                return
            QToolTip.showText(pos, tooltip, self.table.viewport())
                                                                
            self._last_hover_row = pending_row
        finally:
                                 
            self._pending_hover_row = None
            self._pending_tooltip_global_pos = None
            self._pending_tooltip_content = ""

    def _update_tab_icons(self, current_index=None):
        if current_index is None:
            current_index = self.tab_widget.currentIndex()
        icon_names = ["fa6s.table", "fa6s.images", "fa6s.list", "fa6s.folder-plus", "fa6s.diagram-project"]
        for idx, name in enumerate(icon_names):
            if idx == current_index:
                icon = qta.icon(name, color=theme.get_color('primary'))
            else:
                icon = qta.icon(name)
            self.tab_widget.setTabIcon(idx, icon)

    def _inject_open_metadata_dialog_for_grid(self):
        def _open_metadata_dialog_by_filepath(filepath):
            if not filepath:
                return
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 1)
                if item and (item.data(Qt.UserRole) == filepath or item.text() == filepath):
                    self._open_metadata_dialog(row)
                    break
        self._open_metadata_dialog_by_filepath = _open_metadata_dialog_by_filepath

    def _on_reload_clicked(self):
        self._page_cache.clear()
        self.refresh_table()
        if self.flow_mode_enabled:
            self._sync_flow_mode_with_database()
                                                                   
        if self.tab_widget.currentIndex() == 1:
            QTimer.singleShot(100, self._force_thumbnail_layout_refresh)


    def _on_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.page_spinner.setValue(self.current_page)
            self._load_page_data()
            self._update_pagination_ui()

    def _on_next_page(self):
        total_pages = max(1, (self.total_count + self.page_size - 1) // self.page_size)
        if self.current_page < total_pages:
            self.current_page += 1
            self.page_spinner.setValue(self.current_page)
            self._load_page_data()
            self._update_pagination_ui()

    def _on_page_spinner_changed(self, page_num):
        if page_num != self.current_page:
            self.current_page = page_num
            self._load_page_data()
            self._update_pagination_ui()

    def _on_page_size_changed(self, size_text):
        new_size = int(size_text)
        if new_size != self.page_size:
            self.page_size = new_size
            self.current_page = 1
            self.page_spinner.setValue(1)
            self._page_cache.clear()
            self._load_page_data()
            self._update_pagination_ui()
    
    def _on_sort_filter_changed(self, filter_text):
        self.current_page = 1
        self.page_spinner.setValue(1)
        self._page_cache.clear()
        self._load_page_data()
        self._update_pagination_ui()

    def _on_zoom_preset_changed(self, preset_text):
        """Handle zoom preset selection from dropdown - calculate size based on columns"""
        column_map = {
            "1 Column": 1,
            "2 Columns": 2,
            "3 Columns": 3,
            "4 Columns": 4,
            "5 Columns": 5,
            "6 Columns": 6,
            "7 Columns": 7,
            "8 Columns": 8,
            "9 Columns": 9,
            "10 Columns": 10,
            "11 Columns": 11,
            "12 Columns": 12,
            "13 Columns": 13,
            "14 Columns": 14,
            "15 Columns": 15
        }
        
        columns = column_map.get(preset_text)
        if columns:
            self._current_column_count = columns
            new_size = self._calculate_thumbnail_size_from_columns(columns)
            
            if new_size != self.grid_manager.image_size:
                self.grid_manager.set_image_size(new_size)

                if hasattr(self, 'zoom_slider'):
                    self.zoom_slider.blockSignals(True)
                    self.zoom_slider.setValue(min(800, max(48, int(new_size))))
                    self.zoom_slider.blockSignals(False)

                self._pending_thumb_size = new_size
                self._thumb_resize_timer.start()

                QTimer.singleShot(0, self._force_thumbnail_layout_refresh)

    def _on_zoom_slider_changed(self, value):
        self._pending_thumb_size = int(value)
        self.grid_manager.set_image_size(self._pending_thumb_size)
        self._update_zoom_preset_dropdown(self._pending_thumb_size)
        self._thumb_resize_timer.start()
        QTimer.singleShot(0, self._force_thumbnail_layout_refresh)

    def _update_zoom_preset_dropdown(self, current_size):
        """Update dropdown to match current thumbnail size (called from Ctrl+Scroll)"""
        columns = self._calculate_columns_from_size(current_size)
        
        column_text_map = {
            1: "1 Column",
            2: "2 Columns",
            3: "3 Columns",
            4: "4 Columns",
            5: "5 Columns",
            6: "6 Columns",
            7: "7 Columns",
            8: "8 Columns",
            9: "9 Columns",
            10: "10 Columns",
            11: "11 Columns",
            12: "12 Columns",
            13: "13 Columns",
            14: "14 Columns",
            15: "15 Columns"
        }
        
        selected_preset = column_text_map.get(columns, "4 Columns")
        
        if selected_preset != self.zoom_preset_combo.currentText():
            self._current_column_count = columns
            self.zoom_preset_combo.blockSignals(True)
            self.zoom_preset_combo.setCurrentText(selected_preset)
            self.zoom_preset_combo.blockSignals(False)
        if hasattr(self, 'zoom_slider'):
            self.zoom_slider.blockSignals(True)
            self.zoom_slider.setValue(min(800, max(48, int(current_size))))
            self.zoom_slider.blockSignals(False)
    
    def _calculate_thumbnail_size_from_columns(self, columns):
        """Calculate thumbnail size based on desired number of columns"""
        available_width = self.thumbnail_scroll.viewport().width()
        
        margin = 10
        spacing = 10
        
        total_spacing = spacing * (columns - 1)
        total_margins = margin * 2
        
        usable_width = available_width - total_spacing - total_margins
        thumbnail_size = max(48, int(usable_width / columns) - 10)
        
        return thumbnail_size
    
    def _calculate_columns_from_size(self, size):
        """Calculate approximate column count from thumbnail size"""
        available_width = self.thumbnail_scroll.viewport().width()
        
        margin = 10
        spacing = 10
        item_width = size + 10
        
        usable_width = available_width - (margin * 2)
        
        columns = min(15, max(1, int((usable_width + spacing) / (item_width + spacing))))
        columns = min(8, columns)
        
        return columns
    
    def _init_thumbnail_column_count(self):
        """Set default 4-column layout on startup regardless of active tab."""
        self._current_column_count = 4
        self.zoom_preset_combo.blockSignals(True)
        self.zoom_preset_combo.setCurrentText("4 Columns")
        self.zoom_preset_combo.blockSignals(False)

    def _recalculate_thumbnail_size_from_columns(self):
        """Recalculate thumbnail size based on current column count (called on window resize)"""
        if self.tab_widget.currentIndex() != 1:
            return

        new_size = self._calculate_thumbnail_size_from_columns(self._current_column_count)
        if new_size != self.grid_manager.image_size:
            self.grid_manager.set_image_size(new_size)
            if hasattr(self, 'zoom_slider'):
                self.zoom_slider.blockSignals(True)
                self.zoom_slider.setValue(min(800, max(48, int(new_size))))
                self.zoom_slider.blockSignals(False)
            QTimer.singleShot(10, self._force_thumbnail_layout_refresh)

    def _update_pagination_ui(self):
        total_pages = max(1, (self.total_count + self.page_size - 1) // self.page_size)
        
        self.page_spinner.setMaximum(total_pages)
        self.page_spinner.setValue(self.current_page)
        
        self.total_pages_label.setText(f"/{total_pages}")
        
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < total_pages)

    def _load_page_data(self):
        """Load data for current page"""
        filter_text = self.sort_filter_combo.currentText()
        
        status_filter = None
        if filter_text == "Success Only":
            status_filter = "success"
        elif filter_text == "Failed Only":
            status_filter = "failed"
        elif filter_text == "Draft Only":
            status_filter = "draft"
        
        cache_key = (self.current_page, self.page_size, self.search_text, filter_text)
        
        if cache_key in self._page_cache:
            self._current_rows = self._page_cache[cache_key]
        else:
            self._current_rows = list(self.db.get_files_paginated(
                page=self.current_page, 
                page_size=self.page_size, 
                search_text=self.search_text if self.search_text.strip() else None,
                status_filter=status_filter
            ))
            self._page_cache[cache_key] = self._current_rows
        
        self._populate_table_with_rows(self._current_rows)
        self._emit_stats()
        if self.flow_mode_enabled:
            self._sync_flow_mode_with_database()
        
        if self.tab_widget.currentIndex() == 1:
            self.refresh_thumbnail_grid()
            QTimer.singleShot(50, self._force_thumbnail_layout_refresh)
        elif self.tab_widget.currentIndex() == 2:
            self._refresh_details_cards()

    def _populate_table_with_rows(self, rows):
        """Populate table with given rows"""
        # Rescue any in-progress typewriter state before row destruction.
        # _tw_queue and _typewriter_timers use row_idx which becomes invalid after setRowCount(0).
        # Convert them to filepath-based tracking and re-add to _typewriter_pending.
        _tw_queue_now = getattr(self, '_tw_queue', [])
        _tw_timers_now = getattr(self, '_typewriter_timers', {})
        if _tw_queue_now or _tw_timers_now:
            rescued_fps = set()
            for row_idx, col, _full_text in _tw_queue_now:
                fp_item = self.table.item(row_idx, 1)
                if fp_item:
                    fp = fp_item.data(Qt.UserRole) or fp_item.text()
                    if fp:
                        rescued_fps.add(fp)
            for (row_idx, col) in list(_tw_timers_now.keys()):
                timer = _tw_timers_now[(row_idx, col)]
                timer.stop()
                timer.deleteLater()
                fp_item = self.table.item(row_idx, 1)
                if fp_item:
                    fp = fp_item.data(Qt.UserRole) or fp_item.text()
                    if fp:
                        rescued_fps.add(fp)
            self._typewriter_timers = {}
            self._tw_queue = []
            if rescued_fps:
                if not hasattr(self, '_typewriter_pending'):
                    self._typewriter_pending = set()
                self._typewriter_pending.update(rescued_fps)

        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)

        # Explicitly stop all spinner animations before rebuilding rows
        for r in range(self.table.rowCount()):
            widget = self.table.cellWidget(r, 0)
            if widget is not None:
                anim = getattr(widget, '_spin_anim', None)
                if anim:
                    try:
                        anim.stop()
                    except Exception:
                        pass
                self.table.removeCellWidget(r, 0)
                widget.hide()
                widget.setParent(None)
        if hasattr(self, '_spinner_saved_items'):
            self._spinner_saved_items.clear()

        self.table.setRowCount(0)
        
        if not rows:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
            self.table.setVisible(False)
            self.table_no_data_overlay.setVisible(True)
            return
        else:
            self.table.setVisible(True)
            self.table_no_data_overlay.setVisible(False)
        
        self.table.setRowCount(len(rows))
        
        for row_idx, row in enumerate(rows):
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            checkbox_item.setCheckState(Qt.Unchecked)
            checkbox_item.setTextAlignment(Qt.AlignCenter)
            checkbox_item.setData(Qt.UserRole, row[0])
            self.table.setItem(row_idx, 0, checkbox_item)
            display_values = list(row[1:7])
            _pending_fps = getattr(self, '_typewriter_pending', set())
            _row_fp = row[1] if len(row) > 1 else None
            _is_pending = bool(_row_fp and _row_fp in _pending_fps)
            status_val = row[6] if len(row) > 6 and row[6] is not None else ""
            if len(display_values) > 0:
                short_fp = self._shorten_filepath(display_values[0])
                fp_item = QTableWidgetItem(short_fp)
                fp_item.setData(Qt.UserRole, display_values[0])
                self.table.setItem(row_idx, 1, fp_item)
                for col, val in enumerate(display_values[1:], start=2):
                    is_processing_col = col in (3, 4, 5)
                    should_blank = is_processing_col and (
                        _is_pending or status_val in ("processing", "stopping")
                    )
                    if col == 2:
                        filepath = display_values[0]
                        try:
                            size_bytes = os.path.getsize(filepath)
                            if size_bytes >= 1024 * 1024:
                                size_str = f"{size_bytes / (1024 * 1024):.1f}MB"
                            else:
                                size_str = f"{size_bytes / 1024:.0f}KB"
                            display_val = f"{val} ({size_str})"
                        except Exception:
                            display_val = str(val) if val is not None else ""
                        item = QTableWidgetItem(display_val)
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    elif should_blank:
                        item = QTableWidgetItem("")
                        item.setData(Qt.UserRole + 1, str(val) if val is not None else "")
                    else:
                        item = QTableWidgetItem(str(val) if val is not None else "")
                    self.table.setItem(row_idx, col, item)
            title_val = row[3] if len(row) > 3 and row[3] is not None else ""
            title_len = len(title_val)
            title_len_item = QTableWidgetItem(str(title_len))
            title_len_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 6, title_len_item)
            tags_val = row[5] if len(row) > 5 and row[5] is not None else ""
            tag_count = len([t for t in tags_val.split(",") if t.strip()]) if tags_val else 0
            tag_count_item = QTableWidgetItem(str(tag_count))
            tag_count_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 7, tag_count_item)
            status_item = QTableWidgetItem(str(status_val))
            status_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 8, status_item)
            color = self._status_color(status_val)
            for col in range(self.table.columnCount()):
                item = self.table.item(row_idx, col)
                if item:
                    item.setBackground(QBrush(color))
                                                                                             
            tooltip = self._format_row_tooltip(row, max_width_px=self._tooltip_max_width)
            for col in range(self.table.columnCount()):
                item = self.table.item(row_idx, col)
                if item:
                    item.setToolTip(tooltip)
            if status_val in ("processing", "stopping"):
                self._show_row_spinner(row_idx)
            else:
                self._hide_row_spinner(row_idx)
        
        self.table.blockSignals(False)
        self.table.setUpdatesEnabled(True)

        pending = getattr(self, '_typewriter_pending', set())
        if pending:
            queue = []
            for row_idx in range(self.table.rowCount()):
                fp_item = self.table.item(row_idx, 1)
                if not fp_item:
                    continue
                fp = fp_item.data(Qt.UserRole) or fp_item.text()
                if fp not in pending:
                    continue
                for col in (3, 4, 5):
                    item = self.table.item(row_idx, col)
                    if item:
                        full_text = item.data(Qt.UserRole + 1) or ""
                        queue.append((row_idx, col, full_text))
            self._typewriter_pending.clear()
            if queue:
                self._tw_queue = queue
                QTimer.singleShot(0, self._run_typewriter_queue)

    def _on_tab_changed(self, idx):
        if self.tab_widget.tabText(idx) == "Thumbnail":
                                                                            
            QTimer.singleShot(0, self._force_thumbnail_layout_refresh)
            self.refresh_thumbnail_grid()
            self._sync_thumbnail_selection_with_table()
        elif self.tab_widget.tabText(idx) == "Details":
            self._refresh_details_cards()

    def _apply_debounced_thumbnail_resize(self):
        """Reload thumbnails at HD quality after user stops resizing."""
        if getattr(self, '_pending_thumb_size', None) is None:
            return
        target = int(self._pending_thumb_size)
        self._pending_thumb_size = None

        self.grid_manager.image_size = target
        self.grid_manager._pixmap_cache_size = max(300, min(1200, target * 2))
        self.grid_manager._pixmap_cache.clear()

        if hasattr(self, '_thumbnail_loader') and self._thumbnail_loader and self._thumbnail_loader.isRunning():
            self._thumbnail_loader.cancel()

        files_data = []
        for filepath, widget in self.grid_manager._widget_cache.items():
            file_info = widget.property('file_info')
            if file_info:
                files_data.append(file_info)

        if not files_data:
            return

        self._thumbnail_label_map = {}
        for fi in files_data:
            widget = self.grid_manager._widget_cache.get(fi['filepath'])
            if widget and hasattr(widget, '_image_label'):
                self._thumbnail_label_map[fi['filepath']] = widget._image_label

        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(files_data))
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"Rendering thumbnails... (0/{len(files_data)})")

        self._thumbnail_loader = ThumbnailLoaderThread(files_data, self.grid_manager._pixmap_cache_size, self)
        self._thumbnail_loader.thumbnail_ready.connect(self._on_thumbnail_ready)
        self._thumbnail_loader.progress_updated.connect(self._on_thumbnail_progress)
        self._thumbnail_loader.all_done.connect(self._on_thumbnails_done)
        self._thumbnail_loader.start()

        QTimer.singleShot(0, self._force_thumbnail_layout_refresh)

    def _force_thumbnail_layout_refresh(self):
        """Force thumbnail layout to refresh properly"""
        if hasattr(self, 'thumbnail_content') and hasattr(self, 'thumbnail_flow'):
                                  
            content_rect = self.thumbnail_content.rect()
            
                                        
            self.thumbnail_flow.invalidate()
            
                                              
            if content_rect.width() > 0 and content_rect.height() > 0:
                self.thumbnail_flow.setGeometry(content_rect)
            
                                   
            self.thumbnail_content.updateGeometry()
            self.thumbnail_content.update()
            self.thumbnail_scroll.updateGeometry()
            
                                             
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()

    def _on_paste_clicked(self):
                                       
        self.search_timer.stop()
        
        clipboard = QGuiApplication.clipboard()
        text = clipboard.text()
        self.search_edit.setText(text)
        
                                                
        self._pending_search_text = text.strip()
        self._perform_search()

    def _on_clear_search(self):
                                       
        self.search_timer.stop()
        
                                
        self.search_edit.clear()
        
                                                    
        self._pending_search_text = ''
        self._perform_search()

    def _on_search_text_changed_delayed(self, text):
        """Handle search text change with delay - restart timer on each keystroke"""
                                       
        self.search_timer.stop()
        
                                           
        self._pending_search_text = text.strip()
        
                                                                          
        self.search_timer.start(800)

    def _perform_search(self):
        """Perform the actual search after delay"""
                                     
        text = getattr(self, '_pending_search_text', '')
        
                            
        self.search_text = text
        self.current_page = 1
        self._page_cache.clear()
        self.total_count = self.db.get_files_count(self.search_text if self.search_text else None)
        self._load_page_data()
        self._update_pagination_ui()

    def _on_search_text_changed(self, text):
        """Legacy method - now handled by delayed search"""
                                                            
        pass

    def _filter_table(self, text):
                                                         
        pass

    def _row_matches_search(self, row, text):
        for value in row[1:6]:
            if value and text in str(value).lower():
                return True
        return False

    def _shorten_filepath(self, path):
        if not path:
            return ""
        norm_path = os.path.normpath(path)
        parts = norm_path.split(os.sep)
        if len(parts) >= 2:
            drive = parts[0]
            last_dir = parts[-2]
            filename = parts[-1]
            last10 = filename[-10:] if len(filename) > 10 else filename
            return f"{drive}{os.sep}...{os.sep}{last_dir}{os.sep}...{last10}"
        elif len(parts) == 1:
            filename = parts[0]
            last10 = filename[-10:] if len(filename) > 10 else filename
            return f"...{os.sep}{last10}"
        return path

    def _format_row_tooltip(self, row, max_width_px=360):
                                                                  
        if not row or len(row) < 2:
            return ""
        filepath = row[1] if len(row) > 1 and row[1] else ""
        filename = row[2] if len(row) > 2 and row[2] else ""
        title = row[3] if len(row) > 3 and row[3] else ""
        desc = row[4] if len(row) > 4 and row[4] else ""
        tags = row[5] if len(row) > 5 and row[5] else ""
        status = row[6] if len(row) > 6 and row[6] else ""

        def esc(val):
            return html.escape(str(val)) if val is not None else ""

        parts = []
                                           
        parts.append(f"<b>Filename:</b> {esc(filename)}")
        if title:
            parts.append(f"<b>Title:</b> {esc(title)}")
        if desc:
            parts.append(f"<b>Description:</b> {esc(desc)}")
        if tags:
            parts.append(f"<b>Tags:</b> {esc(tags)}")
        if status:
            parts.append(f"<b>Status:</b> {esc(status)}")
        parts.append(f"<b>Filepath:</b> {esc(filepath)}")

        inner = "<br/><br/>".join(parts)
        html_tooltip = f'<div style="max-width: {int(max_width_px)}px; white-space: pre-wrap; word-wrap: break-word;">{inner}</div>'
        return html_tooltip

    def _get_tooltip_for_row_index(self, row_idx):
        if 0 <= row_idx < len(self._current_rows):
            return self._format_row_tooltip(self._current_rows[row_idx], max_width_px=self._tooltip_max_width)
        return ""

    def _get_tooltip_for_filepath(self, filepath):
                                                        
        for row in self._current_rows:
            if len(row) > 1 and row[1] == filepath:
                return self._format_row_tooltip(row, max_width_px=self._tooltip_max_width)
                                          
        return self._format_row_tooltip([None, filepath], max_width_px=self._tooltip_max_width) if filepath else ""

    def _update_widget_tooltip_for_filepath(self, filepath):
        if not filepath:
            return
        tooltip = self._get_tooltip_for_filepath(filepath)
        widget = self.grid_manager._widget_cache.get(filepath)
        if widget:
            widget.setToolTip(tooltip)
                                                                             
            lbls = [c for c in widget.findChildren(QLabel)]
            for lbl in lbls:
                lbl.setToolTip(tooltip)

    def _show_context_menu(self, pos: QPoint):
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        menu = QMenu(self)
        edit_icon = qta.icon("fa6s.pen-to-square")
        edit_action = QAction(edit_icon, "Edit metadata", self)
        edit_action.triggered.connect(lambda: self._open_metadata_dialog(index.row()))
        menu.addAction(edit_action)
        
        menu.addSeparator()
        
        select_menu = menu.addMenu(qta.icon("fa6s.list-check"), "Selection")
        select_all_action = QAction(qta.icon("fa6s.square-check"), "Select All", self)
        select_all_action.triggered.connect(self._select_all_rows)
        select_menu.addAction(select_all_action)
        
        deselect_all_action = QAction(qta.icon("fa6s.square"), "Deselect All", self)
        deselect_all_action.triggered.connect(self._deselect_all_rows)
        select_menu.addAction(deselect_all_action)
        
        select_invert_action = QAction(qta.icon("fa6s.arrows-rotate"), "Invert Selection", self)
        select_invert_action.triggered.connect(self._invert_selection)
        select_menu.addAction(select_invert_action)
        
        select_menu.addSeparator()
        
        select_failed_action = QAction(qta.icon("fa6s.square-check"), "Select Failed Only", self)
        select_failed_action.triggered.connect(self._select_failed_only)
        select_menu.addAction(select_failed_action)
        
        select_draft_action = QAction(qta.icon("fa6s.square-check"), "Select Draft Only", self)
        select_draft_action.triggered.connect(self._select_draft_only)
        select_menu.addAction(select_draft_action)
        
        check_menu = menu.addMenu(qta.icon("fa6s.square-check"), "Checkboxes")
        check_all_action = QAction(qta.icon("fa6s.square-check"), "Check All", self)
        check_all_action.triggered.connect(self._check_all)
        check_menu.addAction(check_all_action)
        
        uncheck_all_action = QAction(qta.icon("fa6s.square"), "Uncheck All", self)
        uncheck_all_action.triggered.connect(self._uncheck_all)
        check_menu.addAction(uncheck_all_action)
        
        check_invert_action = QAction(qta.icon("fa6s.arrows-rotate"), "Invert Checks", self)
        check_invert_action.triggered.connect(self._check_invert)
        check_menu.addAction(check_invert_action)
        
        check_menu.addSeparator()
        
        check_failed_action = QAction(qta.icon("fa6s.square-check"), "Check Failed Only", self)
        check_failed_action.triggered.connect(self._check_failed_only)
        check_menu.addAction(check_failed_action)
        
        check_draft_action = QAction(qta.icon("fa6s.square-check"), "Check Draft Only", self)
        check_draft_action.triggered.connect(self._check_draft_only)
        check_menu.addAction(check_draft_action)
        
        check_menu.addSeparator()
        
        uncheck_failed_action = QAction(qta.icon("fa6s.square"), "Uncheck Failed", self)
        uncheck_failed_action.triggered.connect(self._uncheck_failed)
        check_menu.addAction(uncheck_failed_action)
        
        uncheck_draft_action = QAction(qta.icon("fa6s.square"), "Uncheck Draft", self)
        uncheck_draft_action.triggered.connect(self._uncheck_draft)
        check_menu.addAction(uncheck_draft_action)
        
        menu.addSeparator()

        row_idx = index.row()
        filename_item = self.table.item(row_idx, 2)
        title_item = self.table.item(row_idx, 3)
        desc_item = self.table.item(row_idx, 4)
        tags_item = self.table.item(row_idx, 5)

        copy_filename_action = QAction(qta.icon("fa6s.copy"), "Copy Filename", self)
        copy_filename_action.triggered.connect(lambda: self._copy_to_clipboard_with_tooltip(filename_item.text() if filename_item else "", "Filename", pos))
        menu.addAction(copy_filename_action)

        copy_title_action = QAction(qta.icon("fa6s.copy"), "Copy Title", self)
        copy_title_action.triggered.connect(lambda: self._copy_to_clipboard_with_tooltip(title_item.text() if title_item else "", "Title", pos))
        menu.addAction(copy_title_action)

        copy_desc_action = QAction(qta.icon("fa6s.copy"), "Copy Description", self)
        copy_desc_action.triggered.connect(lambda: self._copy_to_clipboard_with_tooltip(desc_item.text() if desc_item else "", "Description", pos))
        menu.addAction(copy_desc_action)

        copy_tags_action = QAction(qta.icon("fa6s.copy"), "Copy Keyword", self)
        copy_tags_action.triggered.connect(lambda: self._copy_to_clipboard_with_tooltip(tags_item.text() if tags_item else "", "Keyword", pos))
        menu.addAction(copy_tags_action)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _copy_to_clipboard_with_tooltip(self, text, label, pos):
        QGuiApplication.clipboard().setText(text)
        def shorten(val, maxlen=60):
            val = val.strip()
            if len(val) > maxlen:
                return val[:maxlen-3] + "..."
            return val
        value = shorten(text)
        tooltip = f"Copied {label}: {value}" if value else f"Copied {label}: (empty)"
        global_pos = pos.globalPos() if hasattr(pos, "globalPos") else self.table.viewport().mapToGlobal(pos)
        QToolTip.showText(global_pos, tooltip, self.table.viewport())
        QTimer.singleShot(1200, QToolTip.hideText)

    def _copy_to_clipboard(self, text):
        QGuiApplication.clipboard().setText(text)

    def _on_cell_double_clicked(self, row, column):
        self._open_metadata_dialog(row)

    def _open_metadata_dialog(self, row):
        filepath_item = self.table.item(row, 1)
        if not filepath_item:
            return
        filepath = filepath_item.data(Qt.UserRole)
        if not filepath:
            filepath = filepath_item.text()
        parent_for_dialog = self._main_window if self._main_window is not None else self
        dialog = FileMetadataDialog(filepath, parent=parent_for_dialog)
        dialog.exec()

    def set_row_status_color(self, row_idx, status):
        color = self._status_color(status)
        for col in range(self.table.columnCount()):
            item = self.table.item(row_idx, col)
            if item:
                item.setBackground(QBrush(color))
        status_col = 8
        status_item = self.table.item(row_idx, status_col)
        if status_item:
            status_item.setText(status.capitalize())
        if status in ("processing", "stopping"):
            self._show_row_spinner(row_idx)
        else:
            self._hide_row_spinner(row_idx)
        if status == "success":
            fp_item = self.table.item(row_idx, 1)
            if fp_item:
                fp = fp_item.data(Qt.UserRole) or fp_item.text()
                if fp:
                    if not hasattr(self, '_typewriter_pending'):
                        self._typewriter_pending = set()
                    self._typewriter_pending.add(fp)
        
                                            
        if 0 <= row_idx < len(self._current_rows):
            row_list = list(self._current_rows[row_idx])
            if len(row_list) > 6:
                row_list[6] = status
                self._current_rows[row_idx] = tuple(row_list)
                
                                               
                cache_key = (self.current_page, self.page_size, self.search_text)
                if cache_key in self._page_cache:
                    cache_rows = list(self._page_cache[cache_key])
                    if 0 <= row_idx < len(cache_rows):
                        cache_row_list = list(cache_rows[row_idx])
                        if len(cache_row_list) > 6:
                            cache_row_list[6] = status
                            cache_rows[row_idx] = tuple(cache_row_list)
                            self._page_cache[cache_key] = cache_rows
        
        filepath = None
        item = self.table.item(row_idx, 1)
        if item:
            filepath = item.data(Qt.UserRole)
            if not filepath:
                filepath = item.text()
        if filepath:
            self.grid_manager.update_thumbnail_status(filepath, status)
                                                  
            self._update_widget_tooltip_for_filepath(filepath)

    def _status_color(self, status):
        if status == "processing":
            _warn_col = QColor(theme.get_color('warning'))
            _warn_col.setAlpha(int(0.45 * 255))
            return _warn_col
        elif status == "success":
            _succ_col = QColor(theme.get_color('success'))
            _succ_col.setAlpha(int(0.45 * 255))
            return _succ_col
        elif status == "failed":
            _err_col = QColor(theme.get_color('error'))
            _err_col.setAlpha(int(0.18 * 255))
            return _err_col
        elif status == "stopping":
            _warn_col2 = QColor(theme.get_color('warning'))
            _warn_col2.setAlpha(int(0.18 * 255))
            return _warn_col2
        elif status == "stopped":
            _err_col2 = QColor(theme.get_color('error'))
            _err_col2.setAlpha(int(0.18 * 255))
            return _err_col2
        elif status == "draft":
            _gray_col = QColor(theme.get_color('gray'))
            _gray_col.setAlpha(int(0.18 * 255))
            return _gray_col
        _blk_col = QColor(theme.get_color('black'))
        _blk_col.setAlpha(int(0.1 * 255))
        return _blk_col

    def _hide_all_spinners(self):
        for row_idx in range(self.table.rowCount()):
            widget = self.table.cellWidget(row_idx, 0)
            if widget is not None:
                anim = getattr(widget, '_spin_anim', None)
                if anim:
                    try:
                        anim.stop()
                    except Exception:
                        pass
                self.table.removeCellWidget(row_idx, 0)
                widget.hide()
                widget.setParent(None)
                if hasattr(self, '_spinner_saved_items') and row_idx in self._spinner_saved_items:
                    checkbox_item = self._spinner_saved_items.pop(row_idx)
                    checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                    self.table.setItem(row_idx, 0, checkbox_item)
                else:
                    new_cb = QTableWidgetItem()
                    new_cb.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                    new_cb.setCheckState(Qt.Unchecked)
                    new_cb.setTextAlignment(Qt.AlignCenter)
                    self.table.setItem(row_idx, 0, new_cb)
        if hasattr(self, '_spinner_saved_items'):
            self._spinner_saved_items.clear()

    def _show_row_spinner(self, row_idx):
        if self.table.cellWidget(row_idx, 0) is not None:
            return
        checkbox_item = self.table.takeItem(row_idx, 0)
        if checkbox_item:
            if not hasattr(self, '_spinner_saved_items'):
                self._spinner_saved_items = {}
            self._spinner_saved_items[row_idx] = checkbox_item
        warn_q = QColor(theme.get_color('warning'))
        warn_q.setAlpha(int(0.45 * 255))
        bg_css = f"rgba({warn_q.red()},{warn_q.green()},{warn_q.blue()},{warn_q.alpha()/255:.2f})"
        btn = QPushButton(self.table)
        btn.setFlat(True)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setEnabled(False)
        btn.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        btn.setStyleSheet(f"background-color: {bg_css}; border: none;")
        spin_anim = qta.Spin(btn, autostart=True, interval=50, step=45)
        spin_icon = qta.icon('fa6s.spinner', color=theme.get_color('warning'), animation=spin_anim)
        btn._spin_anim = spin_anim
        btn.setIcon(spin_icon)
        btn.setIconSize(QSize(14, 14))
        self.table.setCellWidget(row_idx, 0, btn)

    def _hide_row_spinner(self, row_idx):
        widget = self.table.cellWidget(row_idx, 0)
        if widget is not None:
            anim = getattr(widget, '_spin_anim', None)
            if anim:
                try:
                    anim.stop()
                except Exception:
                    pass
            self.table.removeCellWidget(row_idx, 0)
            widget.hide()
            widget.setParent(None)
        if hasattr(self, '_spinner_saved_items') and row_idx in self._spinner_saved_items:
            checkbox_item = self._spinner_saved_items.pop(row_idx)
            checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            self.table.setItem(row_idx, 0, checkbox_item)

    def _is_typewriter_enabled(self):
        """Check if typewriter animation is enabled in config"""
        try:
            config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get("typewriter_animation_enabled", True)
        except Exception:
            return True

    def _start_typewriter(self, row_idx, col, full_text):
        if not self._is_typewriter_enabled():
            item = self.table.item(row_idx, col)
            if item:
                item.setText(full_text)
            return
        if not hasattr(self, '_typewriter_timers'):
            self._typewriter_timers = {}
        key = (row_idx, col)
        existing = self._typewriter_timers.get(key)
        if existing:
            existing.stop()
            existing.deleteLater()
            self._typewriter_timers.pop(key, None)
        if not full_text:
            item = self.table.item(row_idx, col)
            if item:
                item.setText("")
            return
        state = [0]
        timer = QTimer(self)
        timer.setInterval(40)
        def _tick():
            pos = state[0]
            item = self.table.item(row_idx, col)
            if item is None:
                timer.stop()
                timer.deleteLater()
                self._typewriter_timers.pop(key, None)
                return
            end = min(pos + 2, len(full_text))
            item.setText(full_text[:end])
            state[0] = end
            if end >= len(full_text):
                timer.stop()
                timer.deleteLater()
                self._typewriter_timers.pop(key, None)
        timer.timeout.connect(_tick)
        self._typewriter_timers[key] = timer
        item = self.table.item(row_idx, col)
        if item:
            item.setText("")
        timer.start()

    def _run_typewriter_queue(self):
        if not self._is_typewriter_enabled():
            if hasattr(self, '_tw_queue') and self._tw_queue:
                for row_idx, col, full_text in self._tw_queue:
                    item = self.table.item(row_idx, col)
                    if item:
                        item.setText(full_text)
                self._tw_queue = []
            self.table.scrollToItem(
                self.table.item(self.table.currentRow() if self.table.currentRow() >= 0 else 0, 0)
                or self.table.item(0, 0),
                QAbstractItemView.PositionAtCenter
            )
            self.table.horizontalScrollBar().setValue(0)
            if hasattr(self, '_pending_result_dialog') and self._pending_result_dialog is not None:
                dlg = self._pending_result_dialog
                self._pending_result_dialog = None
                self._hide_all_spinners()
                dlg.exec()
            return
        if not hasattr(self, '_tw_queue') or not self._tw_queue:
            self.table.scrollToItem(
                self.table.item(self.table.currentRow() if self.table.currentRow() >= 0 else 0, 0)
                or self.table.item(0, 0),
                QAbstractItemView.PositionAtCenter
            )
            self.table.horizontalScrollBar().setValue(0)
            if hasattr(self, '_pending_result_dialog') and self._pending_result_dialog is not None:
                dlg = self._pending_result_dialog
                self._pending_result_dialog = None
                self._hide_all_spinners()
                dlg.exec()
            return
        row_idx, col, full_text = self._tw_queue.pop(0)
        item = self.table.item(row_idx, col)
        if item:
            self.table.scrollToItem(item, QAbstractItemView.EnsureVisible)
        if not hasattr(self, '_typewriter_timers'):
            self._typewriter_timers = {}
        key = (row_idx, col)
        existing = self._typewriter_timers.get(key)
        if existing:
            existing.stop()
            existing.deleteLater()
            self._typewriter_timers.pop(key, None)
        if not full_text:
            if item:
                item.setText("")
            self._run_typewriter_queue()
            return
        words = full_text.split(" ")
        state = [0]
        interval = max(20, 667 // max(1, len(words)))
        timer = QTimer(self)
        timer.setInterval(interval)
        def _tick():
            pos = state[0]
            it = self.table.item(row_idx, col)
            if it is None:
                timer.stop()
                timer.deleteLater()
                self._typewriter_timers.pop(key, None)
                self._run_typewriter_queue()
                return
            end = min(pos + 1, len(words))
            it.setText(" ".join(words[:end]))
            state[0] = end
            if end >= len(words):
                timer.stop()
                timer.deleteLater()
                self._typewriter_timers.pop(key, None)
                self._run_typewriter_queue()
        timer.timeout.connect(_tick)
        self._typewriter_timers[key] = timer
        if item:
            item.setText("")
        timer.start()

    def update_row_data(self, row_idx, row_data):
        display_values = list(row_data[1:7])
        if len(display_values) > 0:
            display_values[0] = self._shorten_filepath(display_values[0])
        _animated_cols = {2, 3, 4}
        for col, val in enumerate(display_values):
            table_col = col + 1
            item = self.table.item(row_idx, table_col)
            if item:
                text = str(val) if val is not None else ""
                if col in _animated_cols:
                    self._start_typewriter(row_idx, table_col, text)
                else:
                    item.setText(text)
        title_val = row_data[3] if len(row_data) > 3 and row_data[3] is not None else ""
        title_len = len(title_val)
        title_len_item = self.table.item(row_idx, 6)
        if title_len_item:
            title_len_item.setText(str(title_len))
        tags_val = row_data[5] if len(row_data) > 5 and row_data[5] is not None else ""
        tag_count = len([t for t in tags_val.split(",") if t.strip()]) if tags_val else 0
        tag_count_item = self.table.item(row_idx, 7)
        if tag_count_item:
            tag_count_item.setText(str(tag_count))
        status_val = row_data[6] if len(row_data) > 6 and row_data[6] is not None else ""
        status_item = self.table.item(row_idx, 8)
        if status_item:
            status_item.setText(str(status_val))
                                                    
        filepath = row_data[1] if len(row_data) > 1 else None
        if filepath:
            self._update_widget_tooltip_for_filepath(filepath)
                                                                     
            tooltip = self._format_row_tooltip(row_data, max_width_px=self._tooltip_max_width)
            for col in range(self.table.columnCount()):
                item = self.table.item(row_idx, col)
                if item:
                    item.setToolTip(tooltip)

    def refresh_table(self):
        self.total_count = self.db.get_files_count(self.search_text if self.search_text else None)
        self._page_cache.clear()                          
        self._load_page_data()
        self._update_pagination_ui()
        self._update_zoom_controls_visibility()
        
                                                        
        if self.total_count >= 100:
            if not self._donation_dialog_shown and not is_donation_optout_today():
                self._donation_dialog_shown = True
                dialog = DonateDialog(self, show_not_today=True)
                dialog.setWindowTitle("Support the Development")
                label = dialog.findChild(QLabel)
                if label:
                    label.setText(
                        "Thank you for trusting Image Tea for your metadata needs!\n\n"
                        "You're awesome!\n\n"
                        "Image Tea is possible thanks to the support of users like you.\n"
                        "If you really love using Image Tea to generate metadata,\nconsider supporting its development!"
                    )
                dialog.exec()
        else:
            self._donation_dialog_shown = False
        
        self.data_refreshed.emit()
        if self.tab_widget.currentIndex() == 2:
            self._refresh_details_cards()

    def refresh_thumbnail_grid(self):
        if self._refreshing_thumbnails:
            return

        if hasattr(self, '_thumbnail_loader') and self._thumbnail_loader and self._thumbnail_loader.isRunning():
            self._thumbnail_loader.cancel()
            self._thumbnail_loader.wait()

        self._refreshing_thumbnails = True
        self.grid_manager.active_images.clear()

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Preparing thumbnails...")

        files_data = []
        for row in self._current_rows:
            file_info = {
                'filepath': row[1],
                'filename': row[2],
                'extension': os.path.splitext(row[2])[1],
                'status': row[6] if len(row) > 6 else ""
            }
            files_data.append(file_info)

        self.progress_bar.setMaximum(len(files_data) if files_data else 1)

        current_keys = set(self.grid_manager._widget_cache.keys())
        new_keys = set(f['filepath'] for f in files_data)
        for key in current_keys - new_keys:
            widget = self.grid_manager._widget_cache.pop(key, None)
            if widget:
                widget.deleteLater()
        while self.thumbnail_flow.count():
            item = self.thumbnail_flow.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        if not files_data:
            self.thumbnail_scroll.setVisible(False)
            self.thumbnail_no_data_overlay.setVisible(True)
            self.progress_bar.setVisible(False)
            self.progress_label.setText("Ready")
            self._refreshing_thumbnails = False
            return

        self.thumbnail_scroll.setVisible(True)
        self.thumbnail_no_data_overlay.setVisible(False)

        self._thumbnail_label_map = {}
        for file_info in files_data:
            widget = self.grid_manager._create_image_widget(file_info, load_image=False)
            tooltip = self._get_tooltip_for_filepath(file_info.get('filepath', ''))
            if tooltip:
                widget.setToolTip(tooltip)
                for lbl in widget.findChildren(QLabel):
                    lbl.setToolTip(tooltip)
            self.thumbnail_flow.addWidget(widget)
            if hasattr(widget, '_image_label'):
                self._thumbnail_label_map[file_info['filepath']] = widget._image_label

        self.thumbnail_flow.invalidate()
        self.thumbnail_content.updateGeometry()
        self.thumbnail_scroll.updateGeometry()
        content_rect = self.thumbnail_content.rect()
        if content_rect.width() > 0:
            self.thumbnail_flow.setGeometry(content_rect)
        self.thumbnail_content.update()
        self._update_thumbnail_checklist_style()

        self.progress_label.setText(f"Loading thumbnails... (0/{len(files_data)})")

        target_size = self.grid_manager._pixmap_cache_size
        self._thumbnail_loader = ThumbnailLoaderThread(files_data, target_size, self)
        self._thumbnail_loader.thumbnail_ready.connect(self._on_thumbnail_ready)
        self._thumbnail_loader.progress_updated.connect(self._on_thumbnail_progress)
        self._thumbnail_loader.all_done.connect(self._on_thumbnails_done)
        self._thumbnail_loader.start()

        if self.tab_widget.currentIndex() == 1:
            QTimer.singleShot(0, self._sync_thumbnail_selection_with_table)

    def _on_thumbnail_ready(self, filepath, qimage):
        label = getattr(self, '_thumbnail_label_map', {}).get(filepath)
        if not label:
            return
        if qimage and not qimage.isNull():
            hd_pixmap = QPixmap.fromImage(qimage)
            self.grid_manager._pixmap_cache[filepath] = hd_pixmap
            self._preview_cache[filepath] = hd_pixmap
            display_pixmap = hd_pixmap.scaled(
                self.grid_manager.image_size, self.grid_manager.image_size,
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            label.setPixmap(display_pixmap)
        else:
            label.setText("Cannot preview image")

    def _on_thumbnail_progress(self, current, total):
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"Loading thumbnails... ({current}/{total})")

    def _on_thumbnails_done(self):
        self.progress_bar.setVisible(False)
        self.progress_label.setText("Ready")
        self._refreshing_thumbnails = False

    def _sync_thumbnail_selection_with_table(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            self.grid_manager._update_active_images([])
            return
        
        selected_filepaths = set()
        for selected_idx in selected_rows:
            row_idx = selected_idx.row()
            item = self.table.item(row_idx, 1)
            if item:
                filepath = item.data(Qt.UserRole)
                if not filepath:
                    filepath = item.text()
                if filepath:
                    selected_filepaths.add(filepath)
        
        if not selected_filepaths:
            self.grid_manager._update_active_images([])
            return
        
        matching_widgets = []
        for i in range(self.thumbnail_flow.count()):
            widget = self.thumbnail_flow.itemAt(i).widget()
            if widget and widget.property("file_info"):
                file_info = widget.property("file_info")
                if file_info.get("filepath") in selected_filepaths:
                    matching_widgets.append(widget)
        
        self.grid_manager._update_active_images(matching_widgets)

    def get_selected_row_data(self):
        selected = self.table.selectedItems()
        if selected:
            row = selected[0].row()
            return [self.table.item(row, col).data(Qt.DisplayRole) if self.table.item(row, col) else "" for col in range(self.table.columnCount())]
        return None
    
    def get_all_checked_rows(self):
        """Get all checked rows from current page and return their data"""
        checked_rows = []
        for row in range(self.table.rowCount()):
            checkbox_item = self.table.item(row, 0)
            if checkbox_item and checkbox_item.checkState() == Qt.Checked:
                if row < len(self._current_rows):
                    checked_rows.append(self._current_rows[row])
        return checked_rows
    
    def get_all_files_for_processing(self, mode="all"):
        """Get files for batch processing based on mode"""
        if mode == "all":
            return list(self.db.get_all_files())
        elif mode == "selected":
            return self.get_all_checked_rows()
        elif mode == "failed":
            all_files = self.db.get_all_files()
            return [row for row in all_files if len(row) > 6 and row[6] and row[6].strip().lower() == "failed"]
        return []

    def _emit_stats(self):
                                                                          
                                                      
        page_total = self.table.rowCount()
        checked = 0
        status_col = 8
        for row in range(page_total):
            checkbox_item = self.table.item(row, 0)
            if checkbox_item and checkbox_item.checkState() == Qt.Checked:
                checked += 1
        
                                                    
        all_files = self.db.get_all_files()
        total = len(all_files)
        failed = sum(1 for row in all_files if len(row) > 6 and row[6] and row[6].strip().lower() == "failed")
        success = sum(1 for row in all_files if len(row) > 6 and row[6] and row[6].strip().lower() == "success")
        draft = sum(1 for row in all_files if len(row) > 6 and row[6] and row[6].strip().lower() == "draft")
        
        self.stats_changed.emit(total, checked, failed, success, draft)

    def _on_item_changed(self, item):
        if item.column() == 0:
            self._emit_stats()
            self._update_thumbnail_checklist_style()
                                                                

    def _on_selection_changed(self, selected, deselected):
        if self._properties_widget is None:
            self._properties_widget = getattr(self.parent(), "properties_widget", None)
        if self._properties_widget is None:
            return
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            idx = selected_rows[0].row()
            if 0 <= idx < len(self._current_rows):
                row = self._current_rows[idx]
                title = row[3] if len(row) > 3 and row[3] is not None else ""
                tags = row[5] if len(row) > 5 and row[5] is not None else ""
                title_length = len(title)
                tag_count = len([t for t in tags.split(",") if t.strip()]) if tags else 0
                row_data = [row[0]] + list(row[1:7]) + [row[7] if len(row) > 7 else ""] + [str(title_length), str(tag_count)]
                self._properties_widget.set_properties(row_data)
            else:
                self._properties_widget.set_properties(None)
        else:
            self._properties_widget.set_properties(None)
        if self.tab_widget.currentIndex() == 1:
            self._sync_thumbnail_selection_with_table()
                                                              
        self._highlight_selected_row()
    
    def _select_all_rows(self):
        self.table.selectAll()
    
    def _deselect_all_rows(self):
        self.table.clearSelection()
    
    def _invert_selection(self):
        selected_rows = set(index.row() for index in self.table.selectionModel().selectedRows())
        selection_model = self.table.selectionModel()
        selection_model.clear()
        for row in range(self.table.rowCount()):
            if row not in selected_rows:
                index = self.table.model().index(row, 0)
                selection_model.select(index, QItemSelectionModel.Select | QItemSelectionModel.Rows)
    
    def _select_failed_only(self):
        selection_model = self.table.selectionModel()
        selection_model.clear()
        status_col = 8
        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, status_col)
            if status_item and status_item.text().strip().lower() == "failed":
                index = self.table.model().index(row, 0)
                selection_model.select(index, QItemSelectionModel.Select | QItemSelectionModel.Rows)
    
    def _select_draft_only(self):
        selection_model = self.table.selectionModel()
        selection_model.clear()
        status_col = 8
        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, status_col)
            if status_item and status_item.text().strip().lower() == "draft":
                index = self.table.model().index(row, 0)
                selection_model.select(index, QItemSelectionModel.Select | QItemSelectionModel.Rows)
    
    def _check_all(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.Checked)
        self._update_thumbnail_checklist_style()
    
    def _uncheck_all(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.Unchecked)
        self._update_thumbnail_checklist_style()
    
    def _check_invert(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                new_state = Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked
                item.setCheckState(new_state)
        self._update_thumbnail_checklist_style()
    
    def _check_failed_only(self):
        status_col = 8
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            status_item = self.table.item(row, status_col)
            if item:
                if status_item and status_item.text().strip().lower() == "failed":
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
        self._update_thumbnail_checklist_style()
    
    def _check_draft_only(self):
        status_col = 8
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            status_item = self.table.item(row, status_col)
            if item:
                if status_item and status_item.text().strip().lower() == "draft":
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
        self._update_thumbnail_checklist_style()
    
    def _uncheck_failed(self):
        status_col = 8
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            status_item = self.table.item(row, status_col)
            if item and status_item and status_item.text().strip().lower() == "failed":
                item.setCheckState(Qt.Unchecked)
        self._update_thumbnail_checklist_style()
    
    def _uncheck_draft(self):
        status_col = 8
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            status_item = self.table.item(row, status_col)
            if item and status_item and status_item.text().strip().lower() == "draft":
                item.setCheckState(Qt.Unchecked)
        self._update_thumbnail_checklist_style()

    def _highlight_selected_row(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            _pr_q3 = QColor(theme.get_color('primary'))
            _pr_rgb3 = f"{_pr_q3.red()},{_pr_q3.green()},{_pr_q3.blue()}"
            self.table.setStyleSheet(
                f"QTableWidget::item:selected {{"
                f"background-color: rgba({_pr_rgb3},0.2);"
                f"color: {theme.get_color('black')};"
                "}"
            )
        else:
            self.table.setStyleSheet("")
        for row in range(self.table.rowCount()):
            status_item = self.table.item(row, 8)
            status_val = status_item.text().lower() if status_item else ""
            if not (selected_rows and row == selected_rows[0].row()):
                status_color = self._status_color(status_val)
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        item.setBackground(QBrush(status_color))

    def _on_thumbnail_clicked(self, row, col, file_info):
        filepath = file_info.get('filepath', '')
        if not filepath:
            return
        for row_idx in range(self.table.rowCount()):
            item = self.table.item(row_idx, 1)
            if item and (item.data(Qt.UserRole) == filepath or item.text() == filepath):
                self.table.selectRow(row_idx)
                break
        if self._properties_widget:
            for row in self._current_rows:
                if row[1] == filepath:
                    title = row[3] if len(row) > 3 and row[3] is not None else ""
                    tags = row[5] if len(row) > 5 and row[5] is not None else ""
                    title_length = len(title)
                    tag_count = len([t for t in tags.split(",") if t.strip()]) if tags else 0
                    row_data = [row[0]] + list(row[1:7]) + [row[7] if len(row) > 7 else ""] + [str(title_length), str(tag_count)]
                    self._properties_widget.set_properties(row_data)
                    break
                                                             

    def _update_thumbnail_checklist_style(self):
        checked_filepaths = []
        for row in range(self.table.rowCount()):
            checkbox_item = self.table.item(row, 0)
            filepath_item = self.table.item(row, 1)
            if checkbox_item and checkbox_item.checkState() == Qt.Checked and filepath_item:
                filepath = filepath_item.data(Qt.UserRole)
                if not filepath:
                    filepath = filepath_item.text()
                checked_filepaths.append(filepath)
        self.grid_manager.set_checked_filepaths(checked_filepaths)

    def delete_selected(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            mb = QMessageBox(self)
            mb.setWindowTitle("Delete")
            mb.setIcon(QMessageBox.Information)
            mb.setText("No rows selected.")
            btn_ok = QPushButton("OK")
            btn_ok.setIcon(qta.icon('fa6s.xmark'))
            mb.addButton(btn_ok, QMessageBox.AcceptRole)
            mb.exec()
            return
        for idx in selected:
            filepath = self.table.item(idx.row(), 1).data(Qt.UserRole)
            if not filepath:
                filepath = self.table.item(idx.row(), 1).text()
            self.db.delete_file(filepath)
        self.refresh_table()

    def clear_all(self):
        self.db.clear_files()
        self.refresh_table()

    def clear_existing_metadata(self):
        """Confirm and clear all metadata entries from the database (does not touch file-embedded metadata)."""
        msg = (
            "Are you sure you want to clear all metadata (title, description, tags, status and categories)?\n\n"
            "This will NOT remove metadata embedded in the image files, only metadata stored in the database."
        )
        mb = QMessageBox(self)
        mb.setWindowTitle("Clear Metadata")
        mb.setIcon(QMessageBox.Warning)
        mb.setText(msg)
        btn_yes = QPushButton("Yes")
        btn_yes.setIcon(qta.icon('fa6s.check'))
        btn_no = QPushButton("No")
        btn_no.setIcon(qta.icon('fa6s.xmark'))
        mb.addButton(btn_yes, QMessageBox.AcceptRole)
        mb.addButton(btn_no, QMessageBox.RejectRole)
        mb.exec()
        if mb.clickedButton() == btn_yes:
            self.db.clear_all_metadata()
            self.refresh_table()
    
    def clear_success(self):
        self.db.clear_files_by_status('success')
        self.refresh_table()
    
    def clear_failed(self):
        self.db.clear_files_by_status('failed')
        self.refresh_table()

    def _refresh_details_cards(self):
                                             
        if self._refreshing_details:
            return
        
        self._refreshing_details = True
        
        try:
                               
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_label.setText("Loading details...")
            
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            
                                                            
            for i in reversed(range(self.details_vbox.count())):
                item = self.details_vbox.itemAt(i)
                widget = item.widget()
                if widget:
                    widget.setParent(None)
            
            rows = self._current_rows
            self.progress_bar.setMaximum(len(rows) if rows else 1)
            
                                                        
            current_filepaths = set(row[1] for row in rows)
            for filepath in list(self.details_card_cache.keys()):
                if filepath not in current_filepaths:
                    widget = self.details_card_cache.pop(filepath)
                    if widget:
                        widget.setParent(None)
                    if filepath in self.grid_manager._pixmap_cache:
                        del self.grid_manager._pixmap_cache[filepath]
            
            if not rows:
                                                            
                self.details_scroll.setVisible(False)
                self.details_no_data_overlay.setVisible(True)
                self.progress_bar.setVisible(False)
                self.progress_label.setText("Ready")
                return
            else:
                                                            
                self.details_scroll.setVisible(True)
                self.details_no_data_overlay.setVisible(False)
            
            for i, row in enumerate(rows):
                filepath = row[1]
                if filepath in self.details_card_cache:
                    card = self.details_card_cache[filepath]
                    self._update_details_card(card, row, self.grid_manager)
                else:
                    card = self._create_details_card(row, self.grid_manager)
                    self.details_card_cache[filepath] = card
                self.details_vbox.addWidget(card)
                
                                                      
                self.progress_bar.setValue(i + 1)
                self.progress_label.setText(f"Loading details... ({i + 1}/{len(rows)})")
                
                                                                          
                if i % 2 == 0:                                                            
                    QApplication.processEvents()
            
                               
            self.progress_bar.setVisible(False)
            self.progress_label.setText("Ready")
            
        finally:
            self._refreshing_details = False

    def _create_details_card(self, row, grid_manager):
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setFrameShadow(QFrame.Raised)
        card_hbox = QHBoxLayout(frame)
        card_hbox.setContentsMargins(8, 8, 8, 8)
        card_hbox.setSpacing(12)

        thumb = QLabel()
        thumb.setFixedSize(150, 150)
        thumb.setAlignment(Qt.AlignCenter)
        filepath = row[1]
        pixmap = self._get_preview_pixmap(filepath, 150)
        if pixmap and not pixmap.isNull():
            thumb.setPixmap(pixmap)
        else:
            thumb.setText("Cannot preview image")
        card_hbox.addWidget(thumb)

        vbox = QVBoxLayout()
        vbox.setSpacing(8)

        filename = row[2]
        title = row[3] if len(row) > 3 and row[3] is not None else ""
        desc = row[4] if len(row) > 4 and row[4] is not None else ""
        tags = row[5] if len(row) > 5 and row[5] is not None else ""
        status = row[6] if len(row) > 6 and row[6] is not None else ""

        db = self.db
        shutterstock_image_map = {}
        shutterstock_video_map = {}
        adobe_map = {}
        primary_val = "-"
        secondary_val = "-"
        adobe_val = "-"
        if db:
            shutterstock_image_map, shutterstock_video_map, adobe_map = db.get_category_maps()
            file_id = row[0]
            if file_id is not None:
                mapping = db.get_category_mapping_for_file(file_id)
                filepath = row[1]
                ext = os.path.splitext(filepath)[1].lower()
                is_video = ext in VIDEO_EXTENSIONS
                shutterstock_map = shutterstock_video_map if is_video else shutterstock_image_map
                for m in mapping:
                    if m["platform"] == "shutterstock":
                        cat_name = str(m["category_name"])
                        if cat_name.lower().endswith("(primary)"):
                            primary_val = shutterstock_map.get(str(m["category_id"]), "-")
                        elif cat_name.lower().endswith("(secondary)"):
                            secondary_val = shutterstock_map.get(str(m["category_id"]), "-")
                    elif m["platform"] == "adobe_stock":
                        adobe_val = adobe_map.get(str(m["category_id"]), "-")

                                                                       
        def make_row(icon_name, label_text, value_text):
            row_widget = QWidget()
            row_h = QHBoxLayout(row_widget)
            row_h.setContentsMargins(0, 0, 0, 0)
            row_h.setSpacing(8)

            icon_lbl = QLabel()
            icon_pix = qta.icon(icon_name).pixmap(16, 16)
            icon_lbl.setPixmap(icon_pix)
            icon_lbl.setFixedWidth(20)

            name_lbl = QLabel(f"{label_text}:")
            f = QFont()
            f.setBold(True)
            name_lbl.setFont(f)
            name_lbl.setFixedWidth(120)

            value_lbl = QLabel(value_text)
            value_lbl.setWordWrap(True)

            row_h.addWidget(icon_lbl)
            row_h.addWidget(name_lbl)
            row_h.addWidget(value_lbl, 1)

            return row_widget, value_lbl

                     
        r1, val_filename = make_row("fa6s.file", "Filename", filename)
        r2, val_title = make_row("fa6s.heading", "Title", title)
        r3, val_desc = make_row("fa6s.align-left", "Description", desc)
        r4, val_tags = make_row("fa6s.tags", "Tags", tags)
        r5, val_status = make_row("fa6s.circle-info", "Status", status)

                                         
        color = self._status_color(status)
        val_status.setStyleSheet(f"color: rgb({color.red()}, {color.green()}, {color.blue()});")

        vbox.addWidget(r1)
        vbox.addWidget(r2)
        vbox.addWidget(r3)
        vbox.addWidget(r4)
        vbox.addWidget(r5)

                                  
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        vbox.addWidget(sep)

                    
        r6, val_cat_primary = make_row("fa6s.shapes", "Shutterstock Primary", primary_val)
        r7, val_cat_secondary = make_row("fa6s.layer-group", "Shutterstock Secondary", secondary_val)
        r8, val_cat_adobe = make_row("fa6s.briefcase", "Adobe Stock Category", adobe_val)
        vbox.addWidget(r6)
        vbox.addWidget(r7)
        vbox.addWidget(r8)

        card_hbox.addLayout(vbox)

                                                          
        frame._details_thumb = thumb
        frame._details_label_filename = val_filename
        frame._details_label_title = val_title
        frame._details_label_desc = val_desc
        frame._details_label_tags = val_tags
        frame._details_label_status = val_status
        frame._details_label_cat_primary = val_cat_primary
        frame._details_label_cat_secondary = val_cat_secondary
        frame._details_label_cat_adobe = val_cat_adobe
        frame._details_filepath = filepath
        return frame

    def _update_details_card(self, card, row, grid_manager):
        filepath = row[1]
        pixmap = self._get_preview_pixmap(filepath, 150)
        if pixmap and not pixmap.isNull():
            card._details_thumb.setPixmap(pixmap)
            card._details_thumb.setText("")
        else:
            card._details_thumb.setPixmap(QPixmap())
            card._details_thumb.setText("Cannot preview image")
        filename = row[2]
        title = row[3] if len(row) > 3 and row[3] is not None else ""
        desc = row[4] if len(row) > 4 and row[4] is not None else ""
        tags = row[5] if len(row) > 5 and row[5] is not None else ""
        status = row[6] if len(row) > 6 and row[6] is not None else ""
        db = self.db
        shutterstock_image_map = {}
        shutterstock_video_map = {}
        adobe_map = {}
        primary_val = "-"
        secondary_val = "-"
        adobe_val = "-"
        if db:
            shutterstock_image_map, shutterstock_video_map, adobe_map = db.get_category_maps()
            file_id = row[0]
            if file_id is not None:
                mapping = db.get_category_mapping_for_file(file_id)
                filepath = row[1]
                ext = os.path.splitext(filepath)[1].lower()
                is_video = ext in VIDEO_EXTENSIONS
                shutterstock_map = shutterstock_video_map if is_video else shutterstock_image_map
                for m in mapping:
                    if m["platform"] == "shutterstock":
                        cat_name = str(m["category_name"])
                        if cat_name.lower().endswith("(primary)"):
                            primary_val = shutterstock_map.get(str(m["category_id"]), "-")
                        elif cat_name.lower().endswith("(secondary)"):
                            secondary_val = shutterstock_map.get(str(m["category_id"]), "-")
                    elif m["platform"] == "adobe_stock":
                        adobe_val = adobe_map.get(str(m["category_id"]), "-")
                                                              
        card._details_label_filename.setText(filename)
        card._details_label_title.setText(title)
        card._details_label_desc.setText(desc)
        card._details_label_tags.setText(tags)
        card._details_label_status.setText(status)
                          
        color = self._status_color(status)
        card._details_label_status.setStyleSheet(f"color: rgb({color.red()}, {color.green()}, {color.blue()});")
        card._details_label_cat_primary.setText(primary_val)
        card._details_label_cat_secondary.setText(secondary_val)
        card._details_label_cat_adobe.setText(adobe_val)

    def _get_preview_pixmap(self, filepath, target_size):
        if not filepath or not os.path.exists(filepath):
            return None
        ext = os.path.splitext(filepath)[1].lower()
        video_exts = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
        if filepath in getattr(self, "_preview_cache", {}):
            pixmap = self._preview_cache[filepath]
            if pixmap and not pixmap.isNull():
                return pixmap.scaled(target_size, target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if not hasattr(self, "_preview_cache"):
            self._preview_cache = {}
        try:
            if ext in video_exts:
                try:
                    import cv2
                    cap = cv2.VideoCapture(filepath)
                    ret, frame = cap.read()
                    cap.release()
                    if ret and frame is not None:
                        import numpy as np
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        h, w, ch = frame_rgb.shape
                        bytes_per_line = ch * w
                        qimg = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                        pixmap = QPixmap.fromImage(qimg)
                        pixmap = pixmap.scaled(target_size, target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self._preview_cache[filepath] = pixmap
                        return pixmap
                except Exception as e:
                    print(f"Video preview error: {e}")
            elif ext in {'.svg', '.eps', '.pdf', '.ai'}:
                try:
                    from helpers.image_compression_helper import ensure_temp_folder, convert_eps_pdf_to_jpg, convert_svg_to_jpg, get_compression_quality, MissingToolError
                    temp_folder = ensure_temp_folder()
                    quality = get_compression_quality()
                    filename = os.path.splitext(os.path.basename(filepath))[0] + "_preview.jpg"
                    temp_jpg_path = os.path.join(temp_folder, filename)
                    if not os.path.exists(temp_jpg_path):
                        if ext == '.svg':
                            temp_jpg = convert_svg_to_jpg(filepath, temp_jpg_path, quality)
                        elif ext in ('.eps', '.pdf', '.ai'):
                            temp_jpg = convert_eps_pdf_to_jpg(filepath, temp_jpg_path, quality)
                    else:
                        temp_jpg = temp_jpg_path
                    if temp_jpg and os.path.exists(temp_jpg):
                        pixmap = QPixmap(temp_jpg)
                        if not pixmap.isNull():
                            pixmap = pixmap.scaled(target_size, target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            self._preview_cache[filepath] = pixmap
                            return pixmap
                except MissingToolError as e:
                    # Smart: open Tools Manager for missing tool
                    from helpers.tools_dependency_helper import check_tools_available
                    check_tools_available([e.tool_name], parent=self)
                except Exception as e:
                    print(f"Vector preview error: {e}")
            elif ext in PILLOW_FORMATS:
                pixmap = QPixmap(filepath)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(target_size, target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self._preview_cache[filepath] = pixmap
                    return pixmap
                else:
                    try:
                        from PIL import Image
                        with Image.open(filepath) as img:
                            img = img.convert("RGBA")
                            data = img.tobytes("raw", "RGBA")
                            qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
                            pixmap = QPixmap.fromImage(qimg)
                            pixmap = pixmap.scaled(target_size, target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            self._preview_cache[filepath] = pixmap
                            return pixmap
                    except Exception as e:
                        print(f"Pillow preview error: {e}")
            else:
                pixmap = QPixmap(filepath)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(target_size, target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self._preview_cache[filepath] = pixmap
                    return pixmap
        except Exception as e:
            print(f"Preview error: {e}")
        self._preview_cache[filepath] = None
        return None

    def _browse_flow_mode_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Flow Mode Folder", self.flow_mode_path_edit.text().strip() or os.path.expanduser("~"))
        if folder:
            self.flow_mode_path_edit.setText(folder)
            self.refresh_flow_mode_source()

    def _on_flow_mode_path_dropped(self, path):
        self.flow_mode_path_edit.setText(path)
        self.refresh_flow_mode_source()

    def refresh_flow_mode_source(self):
        source_path = self.flow_mode_path_edit.text().strip()
        self.flow_mode_source_path = source_path
        self.flow_mode_enabled = bool(source_path)
        self.flow_mode_last_scan_error = ""

        if not source_path:
            self.flow_mode_files = []
            self.flow_mode_imported_files = set()
            self._update_flow_mode_ui("Choose a folder to start Flow Mode.")
            return

        if not os.path.isdir(source_path):
            self.flow_mode_files = []
            self.flow_mode_imported_files = set()
            self.flow_mode_last_scan_error = "Selected path is not a valid folder."
            self._update_flow_mode_ui(self.flow_mode_last_scan_error)
            return

        scanned_files = []
        for root, _dirs, files in os.walk(source_path):
            for filename in files:
                full_path = os.path.normpath(os.path.join(root, filename))
                if os.path.splitext(full_path)[1].lower() in SUPPORTED_IMPORT_EXTENSIONS:
                    scanned_files.append(full_path)

        scanned_files.sort(key=lambda path: (os.path.basename(path).lower(), path.lower()))
        self.flow_mode_files = scanned_files
        self._sync_flow_mode_with_database()
        self._update_flow_mode_ui(f"Flow Mode ready. {len(scanned_files)} supported file(s) found.")

    def _sync_flow_mode_with_database(self):
        imported = set()
        flow_mode_files_set = set(self.flow_mode_files)
        if flow_mode_files_set and self.db:
            try:
                for row in self.db.get_all_files():
                    filepath = os.path.normpath(row[1])
                    if filepath in flow_mode_files_set:
                        imported.add(filepath)
            except Exception as e:
                print(f"[Flow Mode] Failed to sync DB state: {e}")
        self.flow_mode_imported_files = imported
        self._populate_flow_mode_table()

    def _populate_flow_mode_table(self):
        if not hasattr(self, 'flow_mode_table'):
            return
        self.flow_mode_table.setRowCount(len(self.flow_mode_files))
        for index, file_path in enumerate(self.flow_mode_files):
            display_name = os.path.basename(file_path)
            item = QTableWidgetItem(display_name)
            item.setToolTip(file_path)
            if file_path in self.flow_mode_imported_files:
                item.setForeground(QBrush(QColor(theme.get_color('gray'))))
            self.flow_mode_table.setItem(index, 0, item)
        self.flow_mode_table.verticalHeader().setDefaultSectionSize(22)

    def _truncate_flow_mode_path(self, path_text, max_length=90):
        if not path_text:
            return "-"
        if len(path_text) <= max_length:
            return path_text
        keep_tail = max_length - 4
        if keep_tail <= 0:
            return "..."
        return f"...{path_text[-keep_tail:]}"

    def _update_flow_mode_ui(self, status_text=None):
        if hasattr(self, 'flow_mode_source_label'):
            full_source = self.flow_mode_source_path or '-'
            self.flow_mode_source_label.setText(self._truncate_flow_mode_path(full_source))
            self.flow_mode_source_label.setToolTip(full_source if self.flow_mode_source_path else "")
        if hasattr(self, 'flow_mode_total_label'):
            self.flow_mode_total_label.setText(f"Total Files: {len(self.flow_mode_files)}")
        pending_count = max(0, len(self.flow_mode_files) - len(self.flow_mode_imported_files))
        if hasattr(self, 'flow_mode_pending_label'):
            self.flow_mode_pending_label.setText(f"Pending Import: {pending_count}")
        if hasattr(self, 'flow_mode_db_label'):
            self.flow_mode_db_label.setText(f"Already In DB: {len(self.flow_mode_imported_files)}")
        if hasattr(self, 'flow_mode_status_label'):
            self.flow_mode_status_label.setText(status_text or self.flow_mode_status_label.text())

    def get_flow_mode_pending_files(self):
        pending_files = []
        imported = self.flow_mode_imported_files or set()
        for file_path in self.flow_mode_files:
            normalized = os.path.normpath(file_path)
            if normalized not in imported and os.path.isfile(normalized):
                pending_files.append(normalized)
        return pending_files

    def import_flow_mode_files(self, max_files):
        if not self.flow_mode_enabled:
            return []
        pending_files = self.get_flow_mode_pending_files()
        if max_files is not None and max_files > 0:
            pending_files = pending_files[:max_files]
        if not pending_files:
            return []
        try:
            from helpers.file_importer import import_files
            imported_ok = import_files(self.window(), self.db, file_paths=pending_files)
            self._page_cache.clear()
            self.refresh_table()
            self._sync_flow_mode_with_database()
            if imported_ok:
                imported_count = len([path for path in pending_files if path in self.flow_mode_imported_files])
                self._update_flow_mode_ui(f"Imported {imported_count} file(s) from Flow Mode source.")
                return pending_files[:imported_count]
        except Exception as e:
            self.flow_mode_last_scan_error = str(e)
            self._update_flow_mode_ui(f"Flow Mode import failed: {e}")
            print(f"[Flow Mode] Import failed: {e}")
        return []

    def set_progress_info(self, label_text, value=None, maximum=None, visible=True):
        """Set progress information with separate label and bar"""
        if hasattr(self, 'progress_label'):
            self.progress_label.setText(label_text)
        
        if hasattr(self, 'progress_bar'):
            if value is not None:
                self.progress_bar.setValue(value)
            if maximum is not None:
                self.progress_bar.setMaximum(maximum)
            self.progress_bar.setVisible(visible)

    def get_progress_format_text(self, mode, service=None, api_key=None):
        """Generate formatted progress text"""
        mode_text = {
            "all": "for all files",
            "selected": "for selected files", 
            "failed": "for failed files",
            "draft": "starting from first draft file",
            "stopped": "resuming from first stopped file",
            "rolling": "using Rolling APIs"
        }.get(mode, mode)
        
        base_text = f"Generating metadata ({mode_text})"
        
        from helpers.members_helper.members_helper import is_logged_in
        if service and api_key and not is_logged_in():
            masked_key = f"***{api_key[-5:]}" if len(api_key) >= 5 else f"***{api_key}"
            base_text += f" - {service}: {masked_key}"
        
        return base_text
