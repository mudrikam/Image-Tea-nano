from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy, QScrollArea, QFrame, QHBoxLayout, QLayout, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QPushButton, QMenu
from PySide6.QtCore import Qt, QRect, QPoint, QSize, QEvent, Signal, QTimer
from PySide6.QtGui import QPixmap, QImage, QDesktopServices, QMouseEvent, QWheelEvent, QCursor, QColor, QAction, QPainter
from PySide6.QtCore import QUrl
import os
import json
import qtawesome as qta

from ui.theme_system import theme
from dialogs.edit_tag_dialog import EditTagDialog
from helpers.video_proxy_helper import VIDEO_EXTENSIONS
import config as _app_config

try:
    from PIL import Image
    PILLOW_FORMATS = set()
    for ext, fmt in Image.registered_extensions().items():
        PILLOW_FORMATS.add(ext.lower())
except ImportError:
    PILLOW_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp', '.eps', '.svg', '.pdf'}

def _levenshtein(a, b):
    if a == b:
        return 0
    if len(a) == 0:
        return len(b)
    if len(b) == 0:
        return len(a)
    v0 = list(range(len(b) + 1))
    v1 = [0] * (len(b) + 1)
    for i in range(len(a)):
        v1[0] = i + 1
        for j in range(len(b)):
            cost = 0 if a[i] == b[j] else 1
            v1[j + 1] = min(v1[j] + 1, v0[j + 1] + 1, v0[j] + cost)
        v0, v1 = v1, v0
    return v0[len(b)]

def _is_similar(tag, other_tag):
    tag_l = tag.lower()
    other_l = other_tag.lower()
    if tag_l == other_l:
        return True
    if len(tag_l) > 3 and tag_l in other_l:
        return True
    if len(other_l) > 3 and other_l in tag_l:
        return True
    if len(tag_l) > 4 and len(other_l) > 4:
        dist = _levenshtein(tag_l, other_l)
        if dist <= 2:
            return True
    return False

class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super(FlowLayout, self).__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if index >= 0 and index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if index >= 0 and index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        size += QSize(2 * self.contentsMargins().top(), 2 * self.contentsMargins().top())
        return size

    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0

        for item in self.itemList:
            wid = item.widget()
            spaceX = self.spacing() + wid.style().layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Horizontal)
            spaceY = self.spacing() + wid.style().layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Vertical)
            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0

            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())

        return y + lineHeight - rect.y()

class TagDeleteButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._normal_icon = qta.icon('fa6s.xmark', color=theme.get_color('text_dark'))
        self._hover_icon = qta.icon('fa6s.xmark', color=theme.get_color('error'))
        self.setIcon(self._normal_icon)
        self.setFixedSize(18, 18)
        self.setIconSize(QSize(12, 12))
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("background: transparent; border: none;")

    def enterEvent(self, event):
        self.setIcon(self._hover_icon)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setIcon(self._normal_icon)
        super().leaveEvent(event)


class TagsPillWidget(QWidget):
    tag_deleted = Signal(str)
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.flow_layout = FlowLayout(self, spacing=4)
        self.flow_layout.setContentsMargins(0, 0, 0, 0)
        self.tags = []
        self.similar_indices = set()
        self.file_id = None
        self.filepath = None
        self.db = None

    def set_file_info(self, file_id, filepath, db):
        self.file_id = file_id
        self.filepath = filepath
        self.db = db

    def set_tags(self, tags_text):
        self.clear_tags()
        if not tags_text:
            return
        tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
        self.tags = tags
        self.similar_indices = set()
        for i, tag in enumerate(tags):
            for j in range(i + 1, len(tags)):
                if _is_similar(tag, tags[j]):
                    self.similar_indices.add(i)
                    self.similar_indices.add(j)
        for i, tag in enumerate(tags):
            pill = self._create_pill(tag, i)
            self.flow_layout.addWidget(pill)
        self.setMinimumHeight(0)

    def _create_pill(self, tag_text, index):
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)

        label = QLabel(tag_text)
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(False)

        delete_btn = TagDeleteButton()
        delete_btn.clicked.connect(lambda: self._delete_tag(tag_text))

        if index in getattr(self, "similar_indices", set()):
            _err_q = QColor(theme.get_color('error'))
            _err_rgb = f"{_err_q.red()},{_err_q.green()},{_err_q.blue()}"
            bg_color = f"rgba({_err_rgb},0.25)"
            border_color = f"rgba({_err_rgb},0.7)"
            btn_style = f"QPushButton {{ background: transparent; border: none; }}"
            label_style = f"QLabel {{ background-color: transparent; border: none; padding: 3px 4px 3px 8px; font-size: 8pt; font-weight: 500; }}"
            container_style = f"QWidget {{ background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 10px; }}"
        elif index < 5:
            _succ_q = QColor(theme.get_color('success'))
            _succ_rgb = f"{_succ_q.red()},{_succ_q.green()},{_succ_q.blue()}"
            bg_color = f"rgba({_succ_rgb},0.3)"
            border_color = f"rgba({_succ_rgb},0.5)"
            btn_style = f"QPushButton {{ background: transparent; border: none; }}"
            label_style = f"QLabel {{ background-color: transparent; border: none; padding: 3px 4px 3px 8px; font-size: 8pt; font-weight: 500; }}"
            container_style = f"QWidget {{ background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 10px; }}"
        elif index < 15:
            _warn_q = QColor(theme.get_color('warning'))
            _warn_rgb = f"{_warn_q.red()},{_warn_q.green()},{_warn_q.blue()}"
            bg_color = f"rgba({_warn_rgb},0.2)"
            border_color = f"rgba({_warn_rgb},0.5)"
            btn_style = f"QPushButton {{ background: transparent; border: none; }}"
            label_style = f"QLabel {{ background-color: transparent; border: none; padding: 3px 4px 3px 8px; font-size: 8pt; font-weight: 500; }}"
            container_style = f"QWidget {{ background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 10px; }}"
        else:
            _gray_q = QColor(theme.get_color('gray'))
            _gray_rgb = f"{_gray_q.red()},{_gray_q.green()},{_gray_q.blue()}"
            bg_color = f"rgba({_gray_rgb},0.2)"
            border_color = f"rgba({_gray_rgb},0.5)"
            btn_style = f"QPushButton {{ background: transparent; border: none; }}"
            label_style = f"QLabel {{ background-color: transparent; border: none; padding: 3px 4px 3px 8px; font-size: 8pt; font-weight: 500; }}"
            container_style = f"QWidget {{ background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 10px; }}"

        label.setStyleSheet(label_style)
        delete_btn.setStyleSheet(btn_style)
        container.setStyleSheet(container_style)

        container_layout.addWidget(label)
        container_layout.addWidget(delete_btn)

        container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        container.adjustSize()
        container.setContextMenuPolicy(Qt.CustomContextMenu)
        container.customContextMenuRequested.connect(lambda pos: self._show_context_menu(pos, tag_text, container))
        label.setCursor(Qt.PointingHandCursor)
        label.mouseDoubleClickEvent = lambda event, t=tag_text: self._edit_tag(t)
        container.mouseDoubleClickEvent = lambda event, t=tag_text: self._edit_tag(t)
        container.tag_text = tag_text
        return container

    def clear_tags(self):
        while self.flow_layout.count():
            child = self.flow_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.tags = []
        self.similar_indices = set()
        self.setMinimumHeight(18)

    def _delete_tag(self, tag_text):
        self.tags = [t for t in self.tags if t.strip() != tag_text.strip()]
        new_tags_str = ', '.join(self.tags)
        files = self.db.get_all_files()
        for file_row in files:
            if file_row[1] == self.filepath:
                current_title = file_row[3]
                current_description = file_row[4]
                current_status = file_row[6]
                self.db.update_metadata(self.filepath, current_title, current_description, new_tags_str, current_status)
                print(f"Tag deleted: '{tag_text}' from {self.filepath}")
                break
        self.data_changed.emit()
        self.clear_tags()
        self.set_tags(new_tags_str)

    def _edit_tag(self, old_tag_text):
        dialog = EditTagDialog(old_tag_text, self)
        if dialog.exec() == EditTagDialog.Accepted:
            new_tag_text = dialog.get_tag_text()
            if new_tag_text and new_tag_text != old_tag_text:
                self.tags = [new_tag_text if t.strip() == old_tag_text.strip() else t for t in self.tags]
                new_tags_str = ', '.join(self.tags)
                files = self.db.get_all_files()
                for file_row in files:
                    if file_row[1] == self.filepath:
                        current_title = file_row[3]
                        current_description = file_row[4]
                        current_status = file_row[6]
                        self.db.update_metadata(self.filepath, current_title, current_description, new_tags_str, current_status)
                        print(f"Tag edited: '{old_tag_text}' -> '{new_tag_text}' in {self.filepath}")
                        break
                self.data_changed.emit()
                self.clear_tags()
                self.set_tags(new_tags_str)

    def _show_context_menu(self, pos, tag_text, widget):
        menu = QMenu(self)
        edit_action = QAction(qta.icon('fa6s.pen-to-square'), 'Edit Tag', self)
        edit_action.triggered.connect(lambda: self._edit_tag(tag_text))
        menu.addAction(edit_action)
        menu.addSeparator()
        delete_action = QAction(qta.icon('fa6s.trash'), 'Delete Tag', self)
        delete_action.triggered.connect(lambda: self._delete_tag(tag_text))
        menu.addAction(delete_action)
        menu.exec(widget.mapToGlobal(pos))



class ImagePreviewWidget(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(60)
        self.setMaximumHeight(16777215)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = None
        self._current_pixmap = None
        self._filepath = None
        self._zoom = 1.0
        self._panning = False
        self._pan_start = QPoint()
        self._user_zoomed = False
        self.setCursor(Qt.ArrowCursor)
        self._no_preview_text = None
        self.setBackgroundBrush(Qt.NoBrush)

    def _get_transparency_bg(self):
        try:
            config_path = os.path.join(_app_config.BASE_PATH, "configs", "ai_config.json")
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            return cfg.get("transparency_background", "checker")
        except Exception:
            return "checker"

    def _build_checker_pixmap(self, sq=8):
        tile_size = sq * 2
        img = QImage(tile_size, tile_size, QImage.Format_RGB32)
        light = QColor(255, 255, 255)
        dark = QColor(204, 204, 204)
        p = QPainter(img)
        p.fillRect(0,        0,        sq, sq, light)
        p.fillRect(sq,       0,        sq, sq, dark)
        p.fillRect(0,        sq,       sq, sq, dark)
        p.fillRect(sq,       sq,       sq, sq, light)
        p.end()
        return QPixmap.fromImage(img)

    def drawBackground(self, painter, rect):
        if not self._pixmap_item:
            super().drawBackground(painter, rect)
            return
        vw = self.viewport().width()
        vh = self.viewport().height()
        bg_mode = self._get_transparency_bg()
        painter.save()
        painter.resetTransform()
        painter.setClipping(False)
        if bg_mode == "checker":
            if not hasattr(self, '_checker_pixmap') or self._checker_pixmap is None:
                self._checker_pixmap = self._build_checker_pixmap(8)
            painter.drawTiledPixmap(0, 0, vw, vh, self._checker_pixmap)
        elif bg_mode == "black":
            painter.fillRect(0, 0, vw, vh, QColor(0, 0, 0))
        else:
            painter.fillRect(0, 0, vw, vh, QColor(255, 255, 255))
        painter.restore()

    def refresh_bg(self):
        self.viewport().update()

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self.viewport().update()

    def set_pixmap(self, pixmap, filepath=None):
        self._scene.clear()
        self._pixmap_item = None
        self._no_preview_text = None
        self._current_pixmap = pixmap
        self._filepath = filepath
        self._zoom = 1.0
        self._user_zoomed = False
        if pixmap:
            self._pixmap_item = self._scene.addPixmap(pixmap)
            self._scene.setSceneRect(self._pixmap_item.boundingRect())
            self.resetTransform()
            self._update_height()
            QTimer.singleShot(0, self._fit_to_view)
        else:
            self._scene.setSceneRect(0, 0, self.width(), self.height())
            self.resetTransform()
            self._show_no_preview_message("No Preview")

    def clear(self):
        self._scene.clear()
        self._pixmap_item = None
        self._no_preview_text = None
        self._current_pixmap = None
        self._filepath = None
        self._zoom = 1.0
        self._user_zoomed = False
        self.resetTransform()
        self._scene.setSceneRect(0, 0, self.width(), self.height())
        self._show_no_preview_message("No Preview")

    def _update_height(self):
        if not self._pixmap_item:
            self.setFixedHeight(max(60, self.width()))
            return
        pix_rect = self._pixmap_item.boundingRect()
        pw = pix_rect.width()
        ph = pix_rect.height()
        vw = self.viewport().width()
        if pw <= 0 or vw <= 0:
            return
        new_h = int(vw * ph / pw)
        self.setFixedHeight(max(60, new_h))

    def _fit_to_view(self):
        if not self._pixmap_item or self._user_zoomed:
            return
        vw = self.viewport().width()
        vh = self.viewport().height()
        pix_rect = self._pixmap_item.boundingRect()
        pw = pix_rect.width()
        ph = pix_rect.height()
        if vw <= 0 or vh <= 0 or pw <= 0 or ph <= 0:
            return
        scale = min(vw / pw, vh / ph)
        self.resetTransform()
        self.scale(scale, scale)
        self.centerOn(self._pixmap_item)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._fit_to_view)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_height()
        self._fit_to_view()
        self._position_no_preview_text()

    def wheelEvent(self, event: QWheelEvent):
        if self._pixmap_item is None:
            return
        angle = event.angleDelta().y()
        factor = 1.25 if angle > 0 else 0.8
        self._zoom *= factor
        if self._zoom < 0.1:
            self._zoom = 0.1
            return
        elif self._zoom > 10.0:
            self._zoom = 10.0
            return
        self._user_zoomed = True
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.scale(factor, factor)
        self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._pixmap_item is not None:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
        elif event.button() == Qt.RightButton:
            self.reset_zoom()
        super().mousePressEvent(event)

    def reset_zoom(self):
        self._user_zoomed = False
        self._zoom = 1.0
        self._fit_to_view()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._panning and self._pixmap_item is not None:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._panning:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if self._filepath and os.path.exists(self._filepath):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._filepath))
        super().mouseDoubleClickEvent(event)

    def _show_no_preview_message(self, message: str):
        if self._no_preview_text:
            try:
                self._scene.removeItem(self._no_preview_text)
            except Exception:
                pass
        self._no_preview_text = self._scene.addText(message)
        self._no_preview_text.setDefaultTextColor(QColor(theme.get_color('text_dark')))
        self._no_preview_text.setVisible(True)
        self._position_no_preview_text()

    def _position_no_preview_text(self):
        if not self._no_preview_text:
            return
        try:
            scene_rect = self._scene.sceneRect()
            text_rect = self._no_preview_text.boundingRect()
            if scene_rect.width() <= 0 or scene_rect.height() <= 0:
                return
            x = scene_rect.x() + max((scene_rect.width() - text_rect.width()) / 2, 0)
            y = scene_rect.y() + max((scene_rect.height() - text_rect.height()) / 2, 0)
            self._no_preview_text.setPos(x, y)
        except RuntimeError:
            self._no_preview_text = None


class PropertiesWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = None
        self.setMinimumWidth(260)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        outer_layout.setAlignment(Qt.AlignTop)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll = scroll

        content = QWidget()
        content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setAlignment(Qt.AlignTop)
        self.content_layout.setContentsMargins(0, 0, 0, 0)

        title_widget, title_label = self._create_icon_label("<b>Preview</b>", "fa6s.image")
        self.content_layout.addWidget(title_widget)

        self.preview_widget = ImagePreviewWidget()
        self.content_layout.addWidget(self.preview_widget)

        self.fields = []
        self.labels = []
        self.label_widgets = []
        field_names = [
            "Filepath", "Filename", "Title", "Description", "Tags", "Status", "File Type", "Original Filename",
            "Shutterstock Category", "Adobe Stock Category"
        ]

        icon_map = {
            "Filepath": "fa6s.folder",
            "Filename": "fa6s.file",
            "Title": "fa6s.heading",
            "Description": "fa6s.align-left",
            "Tags": "fa6s.tags",
            "Status": "fa6s.circle-info",
            "File Type": "fa6s.file-lines",
            "Original Filename": "fa6s.file-signature",
            "Shutterstock Category": "fa6s.image",
            "Adobe Stock Category": "fa6s.pencil"
        }

        self.tags_pill_widget = TagsPillWidget()
        self.tags_pill_widget.tag_deleted.connect(self._on_tag_deleted)

        # Create legend for tags
        self.tags_legend = QLabel("")
        self.tags_legend.setStyleSheet("font-size: 6pt; color: " + theme.get_color('text_dark') + ";")
        self.tags_legend.setAlignment(Qt.AlignCenter)
        self.tags_legend.setVisible(False)

        for idx, label_text in enumerate(field_names):
            icon_name = icon_map.get(label_text, "fa6s.tag")
            label_widget_container, label_widget = self._create_icon_label(f"<b>{label_text}:</b>", icon_name)
            label_widget.setAlignment(Qt.AlignLeft | Qt.AlignTop)

            if label_text == "Tags":
                self.content_layout.addWidget(label_widget_container)
                self.content_layout.addWidget(self.tags_pill_widget)
                self.content_layout.addWidget(self.tags_legend)
                self.fields.append(self.tags_pill_widget)
            else:
                value_label = QLabel("")
                value_label.setWordWrap(True)
                value_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
                value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                value_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
                value_label.setMinimumWidth(0)
                if label_text in ("Title", "Description", "Shutterstock Category", "Adobe Stock Category"):
                    value_label.setStyleSheet("font-size: 11pt;")
                else:
                    value_label.setStyleSheet("font-size: 8pt;")
                self.content_layout.addWidget(label_widget_container)
                self.content_layout.addWidget(value_label)
                self.fields.append(value_label)
                setattr(self, f"{label_text.lower().replace(' ', '_')}_val", value_label)

            self._add_separator()
            self.labels.append(label_text)
            self.label_widgets.append(label_widget)

        content.setLayout(self.content_layout)
        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

        self.setLayout(outer_layout)

        self._preview_cache = {}
        self._last_preview_filepath = None

    def refresh_transparency_bg(self):
        self.preview_widget.refresh_bg()

    def _add_separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setFixedHeight(8)
        _gray_q2 = QColor(theme.get_color('gray'))
        _gray_rgb2 = f"{_gray_q2.red()},{_gray_q2.green()},{_gray_q2.blue()}"
        sep.setStyleSheet(f"border-top: 1px solid rgba({_gray_rgb2},0.3);")
        self.content_layout.addWidget(sep)

    def _create_icon_label(self, text, icon_name):
        """Return (container_widget, text_label) where container has icon on left and label on right."""
        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        icon_label = QLabel()
        try:
            icon = qta.icon(icon_name, color=theme.get_color('text_dark'))
            icon_label.setPixmap(icon.pixmap(14, 14))
        except Exception:
            pass
        text_label = QLabel(text)
        text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        h.addWidget(icon_label)
        h.addWidget(text_label)
        h.addStretch()
        return container, text_label

    def _on_tag_deleted(self, filepath):
        files = self.db.get_all_files()
        for file_row in files:
            if file_row[1] == filepath:
                row_data = list(file_row)
                title = row_data[3] if len(row_data) > 3 and row_data[3] is not None else ""
                tags = row_data[5] if len(row_data) > 5 and row_data[5] is not None else ""
                description = row_data[4] if len(row_data) > 4 and row_data[4] is not None else ""
                title_length = len(title)
                tag_count = len([t for t in tags.split(",") if t.strip()]) if tags else 0
                desc_length = len(description)
                row_data = [row_data[0]] + list(row_data[1:7]) + [row_data[7] if len(row_data) > 7 else ""] + [str(title_length), str(tag_count), str(desc_length)]
                self.set_properties(row_data)
                break

    def set_properties(self, row_data):
        if not row_data:
            self.preview_widget.clear()
            for i, field in enumerate(self.fields):
                if isinstance(field, TagsPillWidget):
                    field.clear_tags()
                    self.tags_legend.setVisible(False)
                else:
                    field.setText("")
            reset_label_texts = [
                "Filepath", "Filename", "Title", "Description", "Tags",
                "Status", "File Type", "Original Filename",
                "Shutterstock Category", "Adobe Stock Category"
            ]
            for label_widget, label_text in zip(self.label_widgets, reset_label_texts):
                label_widget.setText(f"<b>{label_text}:</b>")
            if self.db:
                files = self.db.get_all_files()
                if files:
                    first_row = files[0]
                    title = first_row[3] if len(first_row) > 3 and first_row[3] is not None else ""
                    tags = first_row[5] if len(first_row) > 5 and first_row[5] is not None else ""
                    description = first_row[4] if len(first_row) > 4 and first_row[4] is not None else ""
                    title_length = len(title)
                    tag_count = len([t for t in tags.split(",") if t.strip()]) if tags else 0
                    desc_length = len(description)
                    row_data = [first_row[0]] + list(first_row[1:7]) + [first_row[7] if len(first_row) > 7 else ""] + [str(title_length), str(tag_count), str(desc_length)]
                    self.set_properties(row_data)
            return

        title = str(row_data[3]) if len(row_data) > 3 else ""
        tags = str(row_data[5]) if len(row_data) > 5 else ""
        description = str(row_data[4]) if len(row_data) > 4 else ""
        title_length = int(row_data[8]) if len(row_data) > 8 and str(row_data[8]).isdigit() else len(title)
        tag_count = int(row_data[9]) if len(row_data) > 9 and str(row_data[9]).isdigit() else len([t for t in tags.split(",") if t.strip()]) if tags else 0
        desc_length = len(description)

        label_texts = [
            "Filepath",
            "Filename",
            f"Title ({title_length})",
            f"Description ({desc_length})",
            f"Tags ({tag_count})",
            "Status",
            "File Type",
            "Original Filename",
            "Shutterstock Category",
            "Adobe Stock Category"
        ]

        shutterstock_cat_text = ""
        adobe_cat_text = ""
        filetype_text = ""

        db = self.db
        file_id = row_data[0]
        if db is not None:
            try:
                category_mapping = db.get_category_mapping_for_file(file_id)
                shutterstock_image_map, shutterstock_video_map, adobe_map = db.get_category_maps()
                primary = None
                secondary = None
                for mapping in category_mapping:
                    if mapping['platform'] == 'shutterstock':
                        cat_name = str(mapping['category_name']).lower()
                        if cat_name.endswith('(primary)'):
                            primary = mapping['category_id']
                        elif cat_name.endswith('(secondary)'):
                            secondary = mapping['category_id']
                # Determine whether file is a video by extension
                filepath = row_data[1] if len(row_data) > 1 else ""
                ext = os.path.splitext(filepath)[1].lower()
                is_video = ext in VIDEO_EXTENSIONS
                shutterstock_map = shutterstock_video_map if is_video else shutterstock_image_map
                if primary and secondary:
                    shutterstock_cat_text = f"{shutterstock_map.get(str(primary), str(primary))}, {shutterstock_map.get(str(secondary), str(secondary))}"
                elif primary:
                    shutterstock_cat_text = shutterstock_map.get(str(primary), str(primary))
                elif secondary:
                    shutterstock_cat_text = shutterstock_map.get(str(secondary), str(secondary))
                adobe_cat_id = None
                for mapping in category_mapping:
                    if mapping['platform'] == 'adobe_stock':
                        adobe_cat_id = mapping['category_id']
                        break
                if adobe_cat_id:
                    adobe_cat_text = adobe_map.get(str(adobe_cat_id), str(adobe_cat_id))
                # Get file type
                file_types = db.get_file_types(file_id)
                if file_types:
                    filetype_text = file_types[0][1]  # Get the first file type
            except Exception as e:
                print(f"Error loading category mapping: {e}")

        values = [
            str(row_data[1]) if len(row_data) > 1 else "",  # Filepath
            str(row_data[2]) if len(row_data) > 2 else "",  # Filename
            title,                                          # Title
            description,                                    # Description
            tags,                                          # Tags
            str(row_data[6]) if len(row_data) > 6 else "",  # Status
            filetype_text,                                 # File Type
            str(row_data[7]) if len(row_data) > 7 else "",  # Original Filename
            shutterstock_cat_text,                         # Shutterstock Category
            adobe_cat_text                                 # Adobe Stock Category
        ]

        for label_widget, label_text in zip(self.label_widgets, label_texts):
            label_widget.setText(f"<b>{label_text}:</b>")

        file_id = row_data[0]
        filepath = values[0]
        
        self.tags_pill_widget.set_file_info(file_id, filepath, self.db)
        
        for i, (field, val) in enumerate(zip(self.fields, values)):
            if isinstance(field, TagsPillWidget):
                field.set_tags(val)
                # Show/hide legend based on whether there are tags
                tags_text = str(val) if len(values) > 4 else ""
                tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
                self.tags_legend.setVisible(len(tags) > 0)
                
                # Create colored legend using theme colors
                success_color = theme.get_color('success')
                warning_color = theme.get_color('warning')
                gray_color = theme.get_color('gray')
                error_color = theme.get_color('error')
                
                legend_html = f'<span style="color: {success_color}">●</span> SEO Meta 5  <span style="color: {warning_color}">●</span> SEO Meta 15  <span style="color: {error_color}">●</span> Duplicates  <span style="color: {gray_color}">●</span> Additional tags'
                self.tags_legend.setText(legend_html)
            else:
                field.setText(val)
        
        if filepath == self._last_preview_filepath and filepath in self._preview_cache:
            pixmap = self._preview_cache[filepath]
            self.preview_widget.set_pixmap(pixmap, filepath)
            return

        self.preview_widget.clear()
        self._last_preview_filepath = filepath

        if filepath and os.path.exists(filepath):
            ext = os.path.splitext(filepath)[1].lower()
            video_exts = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
            if ext in video_exts:
                try:
                    import cv2
                    cap = cv2.VideoCapture(filepath)
                    ret, frame = cap.read()
                    cap.release()
                    if ret and frame is not None:
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        h, w, ch = frame_rgb.shape
                        bytes_per_line = ch * w
                        qimg = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                        pixmap = QPixmap.fromImage(qimg)
                        self._preview_cache[filepath] = pixmap
                        self.preview_widget.set_pixmap(pixmap, filepath)
                    else:
                        self._preview_cache[filepath] = None
                        self.preview_widget.clear()
                except Exception as e:
                    print(f"Video preview error: {e}")
                    self._preview_cache[filepath] = None
                    self.preview_widget.clear()
            elif ext in {'.svg', '.eps', '.pdf', '.ai'}:
                try:
                    from helpers.image_compression_helper import (
                        ensure_temp_folder, convert_eps_pdf_to_jpg, convert_svg_to_jpg,
                        get_compression_quality, _resize_if_needed
                    )
                    temp_folder = ensure_temp_folder()
                    quality = get_compression_quality()
                    base_name = os.path.splitext(os.path.basename(filepath))[0] + "_preview"
                    temp_jpg_path = os.path.join(temp_folder, base_name + ".jpg")
                    temp_png_path = os.path.join(temp_folder, base_name + ".png")

                    if os.path.exists(temp_jpg_path):
                        temp_result = temp_jpg_path
                    elif os.path.exists(temp_png_path):
                        temp_result = temp_png_path
                    else:
                        if ext == '.svg':
                            temp_result = convert_svg_to_jpg(filepath, temp_jpg_path, quality)
                        else:
                            temp_result = convert_eps_pdf_to_jpg(filepath, temp_jpg_path, quality)
                        if temp_result:
                            temp_result = _resize_if_needed(temp_result, 2000, quality)

                    if temp_result and os.path.exists(temp_result):
                        pixmap = QPixmap(temp_result)
                        if not pixmap.isNull():
                            if pixmap.width() > 2000 or pixmap.height() > 2000:
                                pixmap = pixmap.scaled(2000, 2000, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            self._preview_cache[filepath] = pixmap
                            self.preview_widget.set_pixmap(pixmap, filepath)
                        else:
                            self._preview_cache[filepath] = None
                            self.preview_widget.clear()
                    else:
                        self._preview_cache[filepath] = None
                        self.preview_widget.clear()
                except Exception as e:
                    print(f"Vector preview error: {e}")
                    self._preview_cache[filepath] = None
                    self.preview_widget.clear()
            elif ext in PILLOW_FORMATS:
                pixmap = QPixmap(filepath)
                if not pixmap.isNull():
                    if pixmap.width() > 2000 or pixmap.height() > 2000:
                        pixmap = pixmap.scaled(2000, 2000, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self._preview_cache[filepath] = pixmap
                    self.preview_widget.set_pixmap(pixmap, filepath)
                else:
                    try:
                        with Image.open(filepath) as img:
                            img = img.convert("RGBA")
                            if img.width > 2000 or img.height > 2000:
                                img.thumbnail((2000, 2000), Image.LANCZOS)
                            data = img.tobytes("raw", "RGBA")
                            qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
                            pixmap = QPixmap.fromImage(qimg)
                            self._preview_cache[filepath] = pixmap
                            self.preview_widget.set_pixmap(pixmap, filepath)
                    except Exception as e:
                        print(f"Pillow preview error: {e}")
                        self._preview_cache[filepath] = None
                        self.preview_widget.clear()
            else:
                self._preview_cache[filepath] = None
                self.preview_widget.clear()
        else:
            self._preview_cache[filepath] = None
            self.preview_widget.clear()