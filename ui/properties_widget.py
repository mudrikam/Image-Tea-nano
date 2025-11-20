from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy, QScrollArea, QFrame, QHBoxLayout, QLayout, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtCore import Qt, QRect, QPoint, QSize, QEvent, Signal
from PySide6.QtGui import QPixmap, QImage, QDesktopServices, QMouseEvent, QWheelEvent, QCursor
from PySide6.QtCore import QUrl
import os

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
    # Only consider substring if length > 3
    if len(tag_l) > 3 and tag_l in other_l:
        return True
    if len(other_l) > 3 and other_l in tag_l:
        return True
    # Only consider Levenshtein for words longer than 4 and distance <= 2
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

class TagsPillWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.flow_layout = FlowLayout(self, spacing=4)
        self.flow_layout.setContentsMargins(0, 0, 0, 0)
        self.tags = []
        self.similar_indices = set()

    def set_tags(self, tags_text):
        self.clear_tags()
        if not tags_text:
            return
        tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()]
        self.tags = tags
        self.similar_indices = set()
        # Detect similar tags
        for i, tag in enumerate(tags):
            for j in range(i + 1, len(tags)):
                if _is_similar(tag, tags[j]):
                    self.similar_indices.add(i)
                    self.similar_indices.add(j)
        for i, tag in enumerate(tags):
            pill = self._create_pill(tag, i)
            self.flow_layout.addWidget(pill)

    def _create_pill(self, tag_text, index):
        pill = QLabel(tag_text)
        pill.setAlignment(Qt.AlignCenter)
        pill.setWordWrap(False)
        if index in getattr(self, "similar_indices", set()):
            bg_color = "rgba(244, 67, 54, 0.25)"
            border_color = "rgba(244, 67, 54, 0.7)"
            style = f"""
                QLabel {{
                    background-color: {bg_color};
                    border: 1px solid {border_color};
                    border-radius: 10px;
                    padding: 3px 8px;
                    font-size: 8pt;
                    font-weight: 500;
                }}
            """
        elif index < 5:
            bg_color = "rgba(255, 235, 59, 0.2)"
            border_color = "rgba(255, 193, 7, 0.5)"
            style = f"""
                QLabel {{
                    background-color: {bg_color};
                    border: 1px solid {border_color};
                    border-radius: 10px;
                    padding: 3px 8px;
                    font-size: 8pt;
                    font-weight: 500;
                }}
            """
        elif index < 15:
            bg_color = "rgba(113, 204, 0, 0.3)"
            border_color = "rgba(113, 204, 0, 0.5)"
            style = f"""
                QLabel {{
                    background-color: {bg_color};
                    border: 1px solid {border_color};
                    border-radius: 10px;
                    padding: 3px 8px;
                    font-size: 8pt;
                    font-weight: 500;
                }}
            """
        else:
            bg_color = "rgba(158, 158, 158, 0.2)"
            border_color = "rgba(158, 158, 158, 0.5)"
            style = f"""
                QLabel {{
                    background-color: {bg_color};
                    border: 1px solid {border_color};
                    border-radius: 10px;
                    padding: 3px 8px;
                    font-size: 8pt;
                    font-weight: 500;
                }}
            """
        pill.setStyleSheet(style)
        pill.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        pill.adjustSize()
        return pill

    def clear_tags(self):
        while self.flow_layout.count():
            child = self.flow_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.tags = []
        self.similar_indices = set()



class ImagePreviewWidget(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(160)
        self.setMaximumHeight(220)
        self.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.NoFrame)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = None
        self._current_pixmap = None
        self._filepath = None
        self._zoom = 1.0
        self._panning = False
        self._pan_start = QPoint()
        self._fit_done = False
        self.setCursor(Qt.ArrowCursor)
        self._no_preview_text = self._scene.addText("")
        self._no_preview_text.setVisible(False)

    def set_pixmap(self, pixmap, filepath=None):
        self._scene.clear()
        self._pixmap_item = None
        self._current_pixmap = pixmap
        self._filepath = filepath
        self._zoom = 1.0
        self._fit_done = False
        if pixmap:
            self._pixmap_item = self._scene.addPixmap(pixmap)
            self._scene.setSceneRect(self._pixmap_item.boundingRect())
            self.resetTransform()
            self._fit_to_view()
            self._no_preview_text = self._scene.addText("")
            self._no_preview_text.setVisible(False)
        else:
            self._scene.setSceneRect(0, 0, self.width(), self.height())
            self.resetTransform()
            self._no_preview_text = self._scene.addText("No Preview")
            self._no_preview_text.setDefaultTextColor(Qt.gray)
            self._no_preview_text.setPos(self.width() / 2 - 40, self.height() / 2 - 10)
            self._no_preview_text.setVisible(True)

    def clear(self):
        self._scene.clear()
        self._pixmap_item = None
        self._current_pixmap = None
        self._filepath = None
        self._zoom = 1.0
        self._fit_done = False
        self.resetTransform()
        self._no_preview_text = self._scene.addText("No Preview")
        self._no_preview_text.setDefaultTextColor(Qt.gray)
        self._no_preview_text.setPos(self.width() / 2 - 40, self.height() / 2 - 10)
        self._no_preview_text.setVisible(True)

    def _fit_to_view(self):
        if self._pixmap_item and not self._fit_done:
            pix_rect = self._pixmap_item.boundingRect()
            view_width = self.viewport().width()
            if pix_rect.width() > 0 and view_width > 0:
                scale_factor = view_width / pix_rect.width()
                self.resetTransform()
                self.scale(scale_factor, scale_factor)
            else:
                self.resetTransform()
            try:
                self.centerOn(self._pixmap_item)
                h = self.horizontalScrollBar()
                v = self.verticalScrollBar()
                h.setValue((h.minimum() + h.maximum()) // 2)
                v.setValue((v.minimum() + v.maximum()) // 2)
            except Exception:
                pass

            self._fit_done = True

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_to_view()
        if self._no_preview_text:
            self._no_preview_text.setPos(self.width() / 2 - 40, self.height() / 2 - 10)

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
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.scale(factor, factor)
        self._fit_done = True

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._pixmap_item is not None:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
        elif event.button() == Qt.RightButton:
            self.reset_zoom()
        super().mousePressEvent(event)

    def reset_zoom(self):
        self.resetTransform()
        self._zoom = 1.0
        self._fit_done = False
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

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setAlignment(Qt.AlignTop)
        self.content_layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel("<b>Properties</b>")
        self.content_layout.addWidget(self.title_label)

        self.preview_widget = ImagePreviewWidget()
        self.content_layout.addWidget(self.preview_widget)

        self.fields = []
        self.labels = []
        self.label_widgets = []
        field_names = [
            "Filepath", "Filename", "Title", "Description", "Tags", "Status", "File Type", "Original Filename",
            "Shutterstock Category", "Adobe Stock Category"
        ]
        
        # Create tags pill widget
        self.tags_pill_widget = TagsPillWidget()
        
        for idx, label_text in enumerate(field_names):
            label = QLabel(f"<b>{label_text}:</b>")
            label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            
            if label_text == "Tags":
                # Use pill widget for tags
                self.content_layout.addWidget(label)
                self.content_layout.addWidget(self.tags_pill_widget)
                self.fields.append(self.tags_pill_widget)  # Store pill widget
            else:
                # Use regular label for other fields
                value_label = QLabel("")
                value_label.setWordWrap(True)
                value_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
                value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                if label_text in ("Title", "Description", "Shutterstock Category", "Adobe Stock Category"):
                    value_label.setStyleSheet("font-size: 11pt;")
                else:
                    value_label.setStyleSheet("font-size: 8pt;")
                self.content_layout.addWidget(label)
                self.content_layout.addWidget(value_label)
                self.fields.append(value_label)
                setattr(self, f"{label_text.lower().replace(' ', '_')}_val", value_label)
            
            self._add_separator()
            self.labels.append(label_text)
            self.label_widgets.append(label)

        content.setLayout(self.content_layout)
        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

        self.setLayout(outer_layout)

        self._preview_cache = {}
        self._last_preview_filepath = None

    def _add_separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setFixedHeight(8)
        sep.setStyleSheet("border-top: 1px solid rgba(128,128,128,0.3);")
        self.content_layout.addWidget(sep)

    def set_properties(self, row_data):
        if not row_data:
            self.preview_widget.clear()
            for i, field in enumerate(self.fields):
                if isinstance(field, TagsPillWidget):
                    field.clear_tags()
                else:
                    field.setText("")
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
                shutterstock_map, adobe_map = db.get_category_maps()
                primary = None
                secondary = None
                for mapping in category_mapping:
                    if mapping['platform'] == 'shutterstock':
                        cat_name = str(mapping['category_name']).lower()
                        if cat_name.endswith('(primary)'):
                            primary = mapping['category_id']
                        elif cat_name.endswith('(secondary)'):
                            secondary = mapping['category_id']
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

        for i, (field, val) in enumerate(zip(self.fields, values)):
            if isinstance(field, TagsPillWidget):
                field.set_tags(val)
            else:
                field.setText(val)

        filepath = values[0]
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
            elif ext in {'.svg', '.eps', '.pdf'}:
                try:
                    temp_jpg = None
                    from helpers.image_compression_helper import ensure_temp_folder, convert_eps_pdf_to_jpg, convert_svg_to_jpg, get_compression_quality
                    temp_folder = ensure_temp_folder()
                    quality = get_compression_quality()
                    filename = os.path.splitext(os.path.basename(filepath))[0] + "_preview.jpg"
                    temp_jpg_path = os.path.join(temp_folder, filename)
                    if not os.path.exists(temp_jpg_path):
                        if ext == '.svg':
                            temp_jpg = convert_svg_to_jpg(filepath, temp_jpg_path, quality)
                        elif ext in ('.eps', '.pdf'):
                            temp_jpg = convert_eps_pdf_to_jpg(filepath, temp_jpg_path, quality)
                    else:
                        temp_jpg = temp_jpg_path
                    if temp_jpg and os.path.exists(temp_jpg):
                        pixmap = QPixmap(temp_jpg)
                        if not pixmap.isNull():
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
                    self._preview_cache[filepath] = pixmap
                    self.preview_widget.set_pixmap(pixmap, filepath)
                else:
                    try:
                        with Image.open(filepath) as img:
                            img = img.convert("RGBA")
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