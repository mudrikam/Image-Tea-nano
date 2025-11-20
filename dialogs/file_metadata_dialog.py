from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QLineEdit, QTextEdit, QHBoxLayout, QFormLayout, QSpacerItem, QSizePolicy, QToolTip, QComboBox
from PySide6.QtGui import QPixmap, QImage, QGuiApplication
from PySide6.QtCore import Qt, QTimer
import qtawesome as qta
import os

class FileMetadataDialog(QDialog):
    def __init__(self, filepath, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Metadata")
        self.setFixedWidth(400)
        self.filepath = filepath
        self.db = getattr(parent, 'db', None)
        self._properties_widget = getattr(parent, "properties_widget", None)
        file_data = None
        if self.db:
            for row in self.db.get_all_files():
                if row[1] == filepath:
                    file_data = row
                    break
        if not file_data:
            file_data = (None, filepath, "", "", "", "", "", "")

        _, filepath, filename, title, description, tags, status, original_filename = file_data
        title = title or ""
        description = description or ""
        tags = tags or ""
        filename = filename or ""

        layout = QVBoxLayout(self)

        img_label = QLabel()
        img_label.setAlignment(Qt.AlignCenter)
        video_exts = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
        ext = os.path.splitext(filepath)[1].lower()
        if os.path.exists(filepath):
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
                        pixmap = pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        img_label.setPixmap(pixmap)
                    else:
                        img_label.setText("Cannot preview video")
                except Exception as e:
                    img_label.setText("Cannot preview video")
            else:
                pixmap = QPixmap(filepath)
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    img_label.setPixmap(pixmap)
                else:
                    img_label.setText("Cannot preview image")
        else:
            img_label.setText("Image/Video not found")
        layout.addWidget(img_label)

        form = QFormLayout()

        title_row = QHBoxLayout()
        self.title_edit = QLineEdit(title)
        title_row.addWidget(self.title_edit)
        copy_title_btn = QPushButton()
        copy_title_btn.setIcon(qta.icon("fa6s.copy"))
        copy_title_btn.setToolTip("Copy Title")
        copy_title_btn.setFlat(True)
        copy_title_btn.setFixedWidth(28)
        copy_title_btn.clicked.connect(lambda: self.copy_with_tooltip(self.title_edit.text(), copy_title_btn, "Title"))
        title_row.addWidget(copy_title_btn)
        form.addRow("Title:", title_row)

        desc_row = QHBoxLayout()
        self.description_edit = QTextEdit(description)
        self.description_edit.setFixedHeight(60)
        self.description_edit.setLineWrapMode(QTextEdit.WidgetWidth)
        desc_row.addWidget(self.description_edit)
        copy_desc_btn = QPushButton()
        copy_desc_btn.setIcon(qta.icon("fa6s.copy"))
        copy_desc_btn.setToolTip("Copy Description")
        copy_desc_btn.setFlat(True)
        copy_desc_btn.setFixedWidth(28)
        copy_desc_btn.clicked.connect(lambda: self.copy_with_tooltip(self.description_edit.toPlainText(), copy_desc_btn, "Description"))
        desc_row.addWidget(copy_desc_btn)
        form.addRow("Description:", desc_row)

        tags_row = QHBoxLayout()
        self.tags_edit = QTextEdit(tags)
        self.tags_edit.setFixedHeight(60)
        self.tags_edit.setLineWrapMode(QTextEdit.WidgetWidth)
        tags_row.addWidget(self.tags_edit)
        copy_tags_btn = QPushButton()
        copy_tags_btn.setIcon(qta.icon("fa6s.copy"))
        copy_tags_btn.setToolTip("Copy Tags")
        copy_tags_btn.setFlat(True)
        copy_tags_btn.setFixedWidth(28)
        copy_tags_btn.clicked.connect(lambda: self.copy_with_tooltip(self.tags_edit.toPlainText(), copy_tags_btn, "Tags"))
        tags_row.addWidget(copy_tags_btn)
        form.addRow("Tags:", tags_row)

        filename_row = QHBoxLayout()
        filename_label = QLabel(filename)
        filename_label.setWordWrap(True)
        filename_row.addWidget(filename_label)
        copy_filename_btn = QPushButton()
        copy_filename_btn.setIcon(qta.icon("fa6s.copy"))
        copy_filename_btn.setToolTip("Copy Filename")
        copy_filename_btn.setFlat(True)
        copy_filename_btn.setFixedWidth(28)
        copy_filename_btn.clicked.connect(lambda: self.copy_with_tooltip(filename, copy_filename_btn, "Filename"))
        filename_row.addWidget(copy_filename_btn)
        form.addRow("Filename:", filename_row)

        # --- CATEGORY COMBOS ---
        self.shutterstock_primary_combo = QComboBox()
        self.shutterstock_secondary_combo = QComboBox()
        self.adobe_combo = QComboBox()
        self.shutterstock_primary_combo.setEditable(False)
        self.shutterstock_secondary_combo.setEditable(False)
        self.adobe_combo.setEditable(False)

        shutterstock_map = {}
        adobe_map = {}
        primary_val = None
        secondary_val = None
        adobe_val = None
        if self.db:
            shutterstock_map, adobe_map = self.db.get_category_maps()
            file_id = file_data[0]
            if file_id is not None:
                mapping = self.db.get_category_mapping_for_file(file_id)
                for m in mapping:
                    if m["platform"] == "shutterstock":
                        cat_name = str(m["category_name"]).lower()
                        if cat_name.endswith("(primary)"):
                            primary_val = str(m["category_id"])
                        elif cat_name.endswith("(secondary)"):
                            secondary_val = str(m["category_id"])
                    elif m["platform"] == "adobe_stock":
                        adobe_val = str(m["category_id"])

        self.shutterstock_primary_combo.addItem("-", "")
        for k, v in shutterstock_map.items():
            self.shutterstock_primary_combo.addItem(v, k)
        if primary_val:
            idx = self.shutterstock_primary_combo.findData(primary_val)
            if idx >= 0:
                self.shutterstock_primary_combo.setCurrentIndex(idx)

        self.shutterstock_secondary_combo.addItem("-", "")
        for k, v in shutterstock_map.items():
            self.shutterstock_secondary_combo.addItem(v, k)
        if secondary_val:
            idx = self.shutterstock_secondary_combo.findData(secondary_val)
            if idx >= 0:
                self.shutterstock_secondary_combo.setCurrentIndex(idx)

        self.adobe_combo.addItem("-", "")
        for k, v in adobe_map.items():
            self.adobe_combo.addItem(v, k)
        if adobe_val:
            idx = self.adobe_combo.findData(adobe_val)
            if idx >= 0:
                self.adobe_combo.setCurrentIndex(idx)

        form.addRow("Shutterstock Primary:", self.shutterstock_primary_combo)
        form.addRow("Shutterstock Secondary:", self.shutterstock_secondary_combo)
        form.addRow("Adobe Stock Category:", self.adobe_combo)

        # --- FILE TYPE COMBO ---
        self.filetype_combo = QComboBox()
        self.filetype_combo.setEditable(False)
        self.filetype_combo.addItem("-", "")
        self.filetype_combo.addItem("Photo", "Photo")
        self.filetype_combo.addItem("Illustration", "Illustration")
        
        # Get current file type
        current_filetype = ""
        if self.db and file_data[0] is not None:
            file_types = self.db.get_file_types(file_data[0])
            if file_types:
                current_filetype = file_types[0][1]
        
        if current_filetype:
            idx = self.filetype_combo.findData(current_filetype)
            if idx >= 0:
                self.filetype_combo.setCurrentIndex(idx)
                
        form.addRow("File Type:", self.filetype_combo)

        layout.addLayout(form)
        layout.addItem(QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setIcon(qta.icon("fa6s.floppy-disk"))
        close_btn = QPushButton("Close")
        close_btn.setIcon(qta.icon("fa6s.xmark"))
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        close_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self.save_metadata)

    def copy_with_tooltip(self, text, btn, label):
        QGuiApplication.clipboard().setText(text)
        def shorten(val, maxlen=60):
            val = val.strip()
            if len(val) > maxlen:
                return val[:maxlen-3] + "..."
            return val
        if label == "Tags":
            value = shorten(text)
            tooltip = f"Copied: {value}" if value else "Copied: (empty)"
        elif label == "Filename":
            tooltip = f"Copied: {shorten(text)}" if text else "Copied: (empty)"
        elif label == "Title":
            tooltip = f"Copied: {shorten(text)}" if text else "Copied: (empty)"
        elif label == "Description":
            tooltip = f"Copied: {shorten(text)}" if text else "Copied: (empty)"
        else:
            tooltip = "Copied"
        old_tooltip = btn.toolTip()
        btn.setToolTip(tooltip)
        pos = btn.mapToGlobal(btn.rect().center())
        QToolTip.showText(pos, tooltip, btn)
        QTimer.singleShot(1200, lambda: btn.setToolTip(old_tooltip))

    def save_metadata(self):
        if not self.db:
            return
        title = self.title_edit.text()
        description = self.description_edit.toPlainText()
        tags = self.tags_edit.toPlainText()
        self.db.update_metadata(self.filepath, title, description, tags)
        file_id = None
        for row in self.db.get_all_files():
            if row[1] == self.filepath:
                file_id = row[0]
                break
        if file_id is not None:
            cat_dict = {}
            primary_val = self.shutterstock_primary_combo.currentData()
            secondary_val = self.shutterstock_secondary_combo.currentData()
            adobe_val = self.adobe_combo.currentData()
            if primary_val or secondary_val:
                cat_dict["shutterstock"] = {}
                if primary_val:
                    cat_dict["shutterstock"]["primary"] = int(primary_val)
                if secondary_val:
                    cat_dict["shutterstock"]["secondary"] = int(secondary_val)
            if adobe_val:
                cat_dict["adobe_stock"] = int(adobe_val)
            if cat_dict:
                self.db.save_category_mapping(file_id, cat_dict)
            
            # Save file type
            filetype_val = self.filetype_combo.currentData()
            if filetype_val:
                # Clear existing file types first
                self.db.delete_file_types_for_file(file_id)
                # Add new file type
                self.db.add_file_type(file_id, filetype_val)
            else:
                # If no file type selected, clear existing ones
                self.db.delete_file_types_for_file(file_id)
        if self._properties_widget is None and self.parent() is not None:
            self._properties_widget = getattr(self.parent(), "properties_widget", None)
        if self._properties_widget is not None:
            for row in self.db.get_all_files():
                if row[1] == self.filepath:
                    title = row[3] if len(row) > 3 and row[3] is not None else ""
                    tags = row[5] if len(row) > 5 and row[5] is not None else ""
                    title_length = len(title)
                    tag_count = len([t for t in tags.split(",") if t.strip()]) if tags else 0
                    row_data = [row[0]] + list(row[1:7]) + [row[7] if len(row) > 7 else ""] + [str(title_length), str(tag_count)]
                    self._properties_widget.set_properties(row_data)
                    break
        # Refresh table and thumbnails after saving metadata
        parent = self.parent()
        if parent is not None:
            if hasattr(parent, "refresh_table"):
                parent.refresh_table()
            elif hasattr(parent, "table") and hasattr(parent.table, "refresh_table"):
                parent.table.refresh_table()
        self.accept()