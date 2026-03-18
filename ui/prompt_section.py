from PySide6.QtWidgets import QWidget, QHBoxLayout, QSpinBox, QSizePolicy, QLabel, QSpacerItem, QVBoxLayout, QFrame, QComboBox, QDialog, QSlider, QPushButton
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QFont
import qtawesome as qta
import json
import os
from config import BASE_PATH
from ui.theme_system import theme


class CompressionQualityDialog(QDialog):
    _PREVIEW_PATH = os.path.join(BASE_PATH, "res", "images", "ayam_geprek.jpg")

    def __init__(self, current_value, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Compression Quality")
        self.setFixedWidth(460)

        self._PREVIEW_W = 432
        self._PREVIEW_H = 200
        self._orig_img = None
        self._left_half = None
        try:
            from PIL import Image
            from io import BytesIO
            with Image.open(self._PREVIEW_PATH) as img:
                img_rgb = img.convert("RGB")
                orig_w, orig_h = img_rgb.size
                scale = max(self._PREVIEW_W / orig_w, self._PREVIEW_H / orig_h)
                new_w = int(orig_w * scale)
                new_h = int(orig_h * scale)
                img_rgb = img_rgb.resize((new_w, new_h), Image.LANCZOS)
                left = (new_w - self._PREVIEW_W) // 2
                top = (new_h - self._PREVIEW_H) // 2
                img_rgb = img_rgb.crop((left, top, left + self._PREVIEW_W, top + self._PREVIEW_H))
                self._orig_img = img_rgb.copy()
            buf100 = BytesIO()
            self._orig_img.save(buf100, "JPEG", quality=100)
            orig_pix = QPixmap.fromImage(QImage.fromData(buf100.getvalue()))
            self._left_half = orig_pix.copy(0, 0, self._PREVIEW_W // 2, self._PREVIEW_H)
        except Exception as e:
            print(f"[CompressionQualityDialog] Failed to load preview image: {e}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title_lbl = QLabel("Image Compression Quality")
        title_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {theme.get_color('foreground')};")
        layout.addWidget(title_lbl)

        info_lbl = QLabel("Lower value = higher compression, smaller file size, more efficient data usage.\nHigher value = better visual quality, larger file size.")
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 11px;")
        layout.addWidget(info_lbl)

        warning_row = QHBoxLayout()
        warning_row.setSpacing(5)
        warning_icon = QLabel()
        warning_icon.setPixmap(qta.icon('fa6s.triangle-exclamation', color=theme.get_color('warning')).pixmap(13, 13))
        warning_icon.setFixedWidth(16)
        warning_lbl = QLabel("Does NOT apply to video input. May affect model output quality.")
        warning_lbl.setWordWrap(True)
        warning_lbl.setStyleSheet(f"color: {theme.get_color('warning')}; font-size: 10px;")
        warning_row.addWidget(warning_icon, 0, Qt.AlignTop)
        warning_row.addWidget(warning_lbl, 1)
        layout.addLayout(warning_row)

        method_lbl = QLabel("Uses lossy JPEG compression to reduce file size before upload for AI processing.")
        method_lbl.setWordWrap(True)
        method_lbl.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 10px; font-style: italic;")
        layout.addWidget(method_lbl)

        if self._orig_img is not None:
            preview_container = QWidget()
            preview_container.setFixedHeight(220)
            pc_layout = QVBoxLayout(preview_container)
            pc_layout.setContentsMargins(0, 0, 0, 0)
            pc_layout.setSpacing(2)
            label_row = QHBoxLayout()
            label_row.setContentsMargins(0, 0, 0, 0)
            before_lbl = QLabel("Before (Original)")
            before_lbl.setAlignment(Qt.AlignCenter)
            before_lbl.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 10px;")
            after_lbl = QLabel("After (Compressed)")
            after_lbl.setAlignment(Qt.AlignCenter)
            after_lbl.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 10px;")
            label_row.addWidget(before_lbl)
            label_row.addWidget(after_lbl)
            pc_layout.addLayout(label_row)
            self.preview_lbl = QLabel()
            self.preview_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            self.preview_lbl.setFixedSize(self._PREVIEW_W, self._PREVIEW_H)
            pc_layout.addWidget(self.preview_lbl, 0, Qt.AlignCenter)
            layout.addWidget(preview_container)
        else:
            self.preview_lbl = None

        val_row = QHBoxLayout()
        val_row.setSpacing(8)
        self.value_lbl = QLabel()
        self.value_lbl.setAlignment(Qt.AlignCenter)
        self.value_lbl.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {theme.get_color('foreground')};")
        self.quality_desc = QLabel()
        self.quality_desc.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        val_row.addStretch()
        val_row.addWidget(self.value_lbl)
        val_row.addWidget(self.quality_desc)
        val_row.addStretch()
        layout.addLayout(val_row)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(1, 100)
        self.slider.setValue(current_value)
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.setTickInterval(10)
        layout.addWidget(self.slider)

        ends_layout = QHBoxLayout()
        low_lbl = QLabel("1 — Small")
        low_lbl.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 10px;")
        high_lbl = QLabel("100 — Large")
        high_lbl.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 10px;")
        high_lbl.setAlignment(Qt.AlignRight)
        ends_layout.addWidget(low_lbl)
        ends_layout.addWidget(high_lbl)
        layout.addLayout(ends_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_ok = QPushButton("Apply")
        self.btn_ok.setIcon(qta.icon('fa6s.check'))
        self.btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setIcon(qta.icon('fa6s.xmark'))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        self.slider.valueChanged.connect(self._update_display)
        self._update_display(current_value)

    def _update_display(self, value):
        self.value_lbl.setText(str(value))
        if value >= 80:
            desc = "High Quality"
            color = theme.get_color('success')
        elif value >= 50:
            desc = "Medium Quality"
            color = theme.get_color('warning')
        else:
            desc = "Low Quality"
            color = theme.get_color('error')
        self.quality_desc.setText(desc)
        self.quality_desc.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {color};")

        if self.preview_lbl is not None and self._orig_img is not None and self._left_half is not None:
            try:
                from io import BytesIO
                buf = BytesIO()
                self._orig_img.save(buf, "JPEG", quality=value)
                comp_pix = QPixmap.fromImage(QImage.fromData(buf.getvalue()))
                right_half = comp_pix.copy(self._PREVIEW_W // 2, 0, self._PREVIEW_W - self._PREVIEW_W // 2, self._PREVIEW_H)

                combined = QPixmap(self._PREVIEW_W, self._PREVIEW_H)
                combined.fill(QColor(0, 0, 0, 0))
                painter = QPainter(combined)
                painter.drawPixmap(0, 0, self._left_half)
                painter.drawPixmap(self._PREVIEW_W // 2, 0, right_half)
                painter.setPen(QColor(theme.get_color('gray')))
                painter.drawLine(self._PREVIEW_W // 2, 0, self._PREVIEW_W // 2, self._PREVIEW_H)
                painter.end()

                self.preview_lbl.setPixmap(combined)
            except Exception as e:
                print(f"[CompressionQualityDialog] Preview update error: {e}")

    def get_value(self):
        return self.slider.value()


class ClickableSpinBox(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._showing_dialog = False

    def focusInEvent(self, event):
        super().focusInEvent(event)
        if not self._showing_dialog:
            QTimer.singleShot(0, self._open_dialog)

    def _open_dialog(self):
        if not self.hasFocus() or self._showing_dialog:
            return
        self._showing_dialog = True
        try:
            dlg = CompressionQualityDialog(self.value(), self)
            if dlg.exec() == QDialog.Accepted:
                self.setValue(dlg.get_value())
        finally:
            self._showing_dialog = False
            self.clearFocus()


class PromptSectionWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        main_layout = QHBoxLayout()
        main_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(0, 0, 0, 0)

        icon_color = theme.get_color('primary')
        icon_size = 14
        fixed_width = 80

        min_title_group = QVBoxLayout()
        min_title_group.setSpacing(2)
        min_title_group.setContentsMargins(0, 0, 0, 0)
        min_title_header = QHBoxLayout()
        min_title_header.setSpacing(3)
        min_title_header.setContentsMargins(0, 0, 0, 0)
        min_title_icon = QLabel()
        min_title_icon.setPixmap(qta.icon('fa6s.arrow-down-short-wide', color=icon_color).pixmap(icon_size, icon_size))
        min_title_label = QLabel("Min Title")
        min_title_label.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 10px;")
        min_title_header.addWidget(min_title_icon)
        min_title_header.addWidget(min_title_label)
        min_title_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        min_title_group.addLayout(min_title_header)
        self.min_title_spin = QSpinBox()
        self.min_title_spin.setRange(1, 1000)
        self.min_title_spin.setFixedWidth(fixed_width)
        self.min_title_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.min_title_spin.setToolTip("Minimum title length in characters.\nModels will aim to meet this length.")
        min_title_group.addWidget(self.min_title_spin)
        
        min_title_wrapper = QWidget()
        min_title_wrapper.setLayout(min_title_group)
        min_title_wrapper.setFixedWidth(fixed_width)
        main_layout.addWidget(min_title_wrapper)

        max_title_group = QVBoxLayout()
        max_title_group.setSpacing(2)
        max_title_group.setContentsMargins(0, 0, 0, 0)
        max_title_header = QHBoxLayout()
        max_title_header.setSpacing(3)
        max_title_header.setContentsMargins(0, 0, 0, 0)
        max_title_icon = QLabel()
        max_title_icon.setPixmap(qta.icon('fa6s.arrow-up-wide-short', color=icon_color).pixmap(icon_size, icon_size))
        max_title_label = QLabel("Max Title")
        max_title_label.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 10px;")
        max_title_header.addWidget(max_title_icon)
        max_title_header.addWidget(max_title_label)
        max_title_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        max_title_group.addLayout(max_title_header)
        self.max_title_spin = QSpinBox()
        self.max_title_spin.setRange(1, 1000)
        self.max_title_spin.setFixedWidth(fixed_width)
        self.max_title_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.max_title_spin.setToolTip("Maximum title length in characters.\nModels will aim to not exceed this length.")
        max_title_group.addWidget(self.max_title_spin)
        
        max_title_wrapper = QWidget()
        max_title_wrapper.setLayout(max_title_group)
        max_title_wrapper.setFixedWidth(fixed_width)
        main_layout.addWidget(max_title_wrapper)

        max_desc_group = QVBoxLayout()
        max_desc_group.setSpacing(2)
        max_desc_group.setContentsMargins(0, 0, 0, 0)
        max_desc_header = QHBoxLayout()
        max_desc_header.setSpacing(3)
        max_desc_header.setContentsMargins(0, 0, 0, 0)
        max_desc_icon = QLabel()
        max_desc_icon.setPixmap(qta.icon('fa6s.align-left', color=icon_color).pixmap(icon_size, icon_size))
        max_desc_label = QLabel("Max Desc")
        max_desc_label.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 10px;")
        max_desc_header.addWidget(max_desc_icon)
        max_desc_header.addWidget(max_desc_label)
        max_desc_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        max_desc_group.addLayout(max_desc_header)
        self.max_desc_spin = QSpinBox()
        self.max_desc_spin.setRange(1, 2000)
        self.max_desc_spin.setFixedWidth(fixed_width)
        self.max_desc_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.max_desc_spin.setToolTip("Maximum description length in characters.\nModels will aim to not exceed this length.")
        max_desc_group.addWidget(self.max_desc_spin)
        
        max_desc_wrapper = QWidget()
        max_desc_wrapper.setLayout(max_desc_group)
        max_desc_wrapper.setFixedWidth(fixed_width)
        main_layout.addWidget(max_desc_wrapper)

        tag_count_group = QVBoxLayout()
        tag_count_group.setSpacing(2)
        tag_count_group.setContentsMargins(0, 0, 0, 0)
        tag_count_header = QHBoxLayout()
        tag_count_header.setSpacing(3)
        tag_count_header.setContentsMargins(0, 0, 0, 0)
        tag_count_icon = QLabel()
        tag_count_icon.setPixmap(qta.icon('fa6s.tags', color=icon_color).pixmap(icon_size, icon_size))
        tag_count_label = QLabel("Tag Count")
        tag_count_label.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 10px;")
        tag_count_header.addWidget(tag_count_icon)
        tag_count_header.addWidget(tag_count_label)
        tag_count_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        tag_count_group.addLayout(tag_count_header)
        self.tag_count_spin = QSpinBox()
        self.tag_count_spin.setRange(1, 100)
        self.tag_count_spin.setFixedWidth(fixed_width)
        self.tag_count_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.tag_count_spin.setToolTip("Number of keywords/tags to generate.\nModels will aim to generate exactly this many tags.")
        tag_count_group.addWidget(self.tag_count_spin)
        
        tag_count_wrapper = QWidget()
        tag_count_wrapper.setLayout(tag_count_group)
        tag_count_wrapper.setFixedWidth(fixed_width)
        main_layout.addWidget(tag_count_wrapper)

        batch_size_group = QVBoxLayout()
        batch_size_group.setSpacing(2)
        batch_size_group.setContentsMargins(0, 0, 0, 0)
        batch_size_header = QHBoxLayout()
        batch_size_header.setSpacing(3)
        batch_size_header.setContentsMargins(0, 0, 0, 0)
        batch_size_icon = QLabel()
        batch_size_icon.setPixmap(qta.icon('fa6s.layer-group', color=icon_color).pixmap(icon_size, icon_size))
        batch_size_label = QLabel("Batch Size")
        batch_size_label.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 10px;")
        batch_size_header.addWidget(batch_size_icon)
        batch_size_header.addWidget(batch_size_label)
        batch_size_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        batch_size_group.addLayout(batch_size_header)
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 20)
        self.batch_size_spin.setFixedWidth(fixed_width)
        self.batch_size_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.batch_size_spin.setToolTip("Number of files processed per batch.\nMaximum is 20 per batch.")
        batch_size_group.addWidget(self.batch_size_spin)
        
        batch_size_wrapper = QWidget()
        batch_size_wrapper.setLayout(batch_size_group)
        batch_size_wrapper.setFixedWidth(fixed_width)
        main_layout.addWidget(batch_size_wrapper)

        compression_group = QVBoxLayout()
        compression_group.setSpacing(2)
        compression_group.setContentsMargins(0, 0, 0, 0)
        compression_header = QHBoxLayout()
        compression_header.setSpacing(3)
        compression_header.setContentsMargins(0, 0, 0, 0)
        compression_icon = QLabel()
        compression_icon.setPixmap(qta.icon('fa6s.compress', color=icon_color).pixmap(icon_size, icon_size))
        compression_label = QLabel("Quality")
        compression_label.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 10px;")
        compression_header.addWidget(compression_icon)
        compression_header.addWidget(compression_label)
        compression_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        compression_group.addLayout(compression_header)
        self.cache_spin = ClickableSpinBox()
        self.cache_spin.setRange(1, 100)
        self.cache_spin.setFixedWidth(fixed_width)
        self.cache_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.cache_spin.setToolTip("Image Compression quality (1-100).\nClick to open quality slider.\nLower value = higher image compression, \nmore efficient internet data usage. \nDOES NOT WORK ON VIDEO INPUT. \nMay effect model output quality. \nThis method uses lossy compression \nto reduce file size before upload for processing.")
        compression_group.addWidget(self.cache_spin)
        
        compression_wrapper = QWidget()
        compression_wrapper.setLayout(compression_group)
        compression_wrapper.setFixedWidth(fixed_width)
        main_layout.addWidget(compression_wrapper)

        delay_group = QVBoxLayout()
        delay_group.setSpacing(2)
        delay_group.setContentsMargins(0, 0, 0, 0)
        delay_header = QHBoxLayout()
        delay_header.setSpacing(3)
        delay_header.setContentsMargins(0, 0, 0, 0)
        delay_icon = QLabel()
        delay_icon.setPixmap(qta.icon('fa6s.hourglass-half', color=icon_color).pixmap(icon_size, icon_size))
        delay_label = QLabel("Delay (s)")
        delay_label.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 10px;")
        delay_header.addWidget(delay_icon)
        delay_header.addWidget(delay_label)
        delay_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        delay_group.addLayout(delay_header)
        self.delay_combo = QComboBox()
        self.delay_combo.setEditable(True)
        self.delay_combo.addItems(["No Delay", "Random", "1", "2", "3", "4", "5", "10", "15", "20", "30"])
        self.delay_combo.setFixedWidth(fixed_width)
        self.delay_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.delay_combo.setToolTip("Delay interval between batches.\nNo Delay = 0s, Random = 1-5s, \nor enter custom value in seconds.")
        delay_group.addWidget(self.delay_combo)
        
        delay_wrapper = QWidget()
        delay_wrapper.setLayout(delay_group)
        delay_wrapper.setFixedWidth(fixed_width)
        main_layout.addWidget(delay_wrapper)

        proxy_group = QVBoxLayout()
        proxy_group.setSpacing(2)
        proxy_group.setContentsMargins(0, 0, 0, 0)
        proxy_header = QHBoxLayout()
        proxy_header.setSpacing(3)
        proxy_header.setContentsMargins(0, 0, 0, 0)
        proxy_icon = QLabel()
        proxy_icon.setPixmap(qta.icon('fa6s.video', color=icon_color).pixmap(icon_size, icon_size))
        proxy_label = QLabel("Proxy")
        proxy_label.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 10px;")
        proxy_header.addWidget(proxy_icon)
        proxy_header.addWidget(proxy_label)
        proxy_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        proxy_group.addLayout(proxy_header)
        self.proxy_combo = QComboBox()
        self.proxy_combo.addItems(["Off", "Auto", "Low", "Medium", "High"])
        self.proxy_combo.setFixedWidth(fixed_width)
        self.proxy_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.proxy_combo.setToolTip(
            "Video proxy (FFmpeg) presets for uploading to AI services:\n"
            "Off = upload original file unchanged.\n"
            "Auto = pick Low/Medium/High based on input resolution.\n"
            "Low/Medium/High = preset bitrates and resolutions (see items).\n"
            "Using proxies can greatly reduce upload times and data usage.\n"
            "Proxies are created using FFmpeg and converted to MP4 H.264 format.\n"
            "May affect model output quality depending on compression level."
        )
        self.proxy_combo.setItemData(0, "Off - Upload original file without proxy conversion", Qt.ToolTipRole)
        self.proxy_combo.setItemData(1, "Auto - Choose preset based on input resolution (Low/Medium/High)", Qt.ToolTipRole)
        self.proxy_combo.setItemData(2, "Low - 480p target (~1000k bitrate), converts to MP4 H.264", Qt.ToolTipRole)
        self.proxy_combo.setItemData(3, "Medium - 720p target (~2500k bitrate), converts to MP4 H.264", Qt.ToolTipRole)
        self.proxy_combo.setItemData(4, "High - 1080p target (~5000k bitrate), converts to MP4 H.264", Qt.ToolTipRole)
        proxy_group.addWidget(self.proxy_combo)

        proxy_wrapper = QWidget()
        proxy_wrapper.setLayout(proxy_group)
        proxy_wrapper.setFixedWidth(fixed_width)
        main_layout.addWidget(proxy_wrapper)

        preset_group = QVBoxLayout()
        preset_group.setSpacing(2)
        preset_group.setContentsMargins(0, 0, 0, 0)
        preset_header = QHBoxLayout()
        preset_header.setSpacing(3)
        preset_header.setContentsMargins(0, 0, 0, 0)
        preset_icon = QLabel()
        preset_icon.setPixmap(qta.icon('fa6s.list', color=icon_color).pixmap(icon_size, icon_size))
        preset_label = QLabel("Preset")
        preset_label.setStyleSheet(f"color: {theme.get_color('gray')}; font-size: 10px;")
        preset_header.addWidget(preset_icon)
        preset_header.addWidget(preset_label)
        preset_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        preset_group.addLayout(preset_header)
        self.preset_combo = QComboBox()
        self.preset_combo.setFixedWidth(fixed_width)
        self.preset_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.preset_combo.setToolTip(
            "Select a prompt preset to use for metadata generation.\n"
            "Changing preset updates all prompt templates automatically\n"
            "(Title, Description, Keywords, Guides, Don'ts, Negative, Custom).\n"
            "Presets can be managed in the Edit Prompt dialog."
        )
        preset_group.addWidget(self.preset_combo)

        preset_wrapper = QWidget()
        preset_wrapper.setLayout(preset_group)
        preset_wrapper.setFixedWidth(fixed_width)
        main_layout.addWidget(preset_wrapper)

        main_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))

        outer_layout.addLayout(main_layout)
        self.setLayout(outer_layout)

        self.config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
        self.min_title_spin.valueChanged.connect(self.save_prompt_config)
        self.max_title_spin.valueChanged.connect(self.save_prompt_config)
        self.max_desc_spin.valueChanged.connect(self.save_prompt_config)
        self.tag_count_spin.valueChanged.connect(self.save_prompt_config)
        self.batch_size_spin.valueChanged.connect(self.save_prompt_config)
        self.cache_spin.valueChanged.connect(self.save_prompt_config)
        self.delay_combo.currentTextChanged.connect(self.save_prompt_config)
        self.proxy_combo.currentTextChanged.connect(self.save_prompt_config)
        self.preset_combo.currentTextChanged.connect(self.on_preset_changed)
        self.load_prompt_config()

    def load_prompt_config(self):
        self._loading = True
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if "prompt_presets" not in data:
                data["prompt_presets"] = [{
                    "name": "Default",
                    "title_requirements": data["prompt"].get("title_requirements", ""),
                    "description_requirements": data["prompt"].get("description_requirements", ""),
                    "keywords_requirements": data["prompt"].get("keywords_requirements", ""),
                    "general_guides": data["prompt"].get("general_guides", ""),
                    "strict_donts": data["prompt"].get("strict_donts", ""),
                    "negative_prompt": data["prompt"].get("negative_prompt", ""),
                    "custom_prompt": data["prompt"].get("custom_prompt", "")
                }]
            
            self.preset_combo.clear()
            for preset in data["prompt_presets"]:
                self.preset_combo.addItem(preset["name"])
            
            current_preset = data.get("selected_preset", "Default")
            index = self.preset_combo.findText(current_preset)
            if index >= 0:
                self.preset_combo.setCurrentIndex(index)
            
            self.min_title_spin.setValue(data["min_title_length"])
            self.max_title_spin.setValue(data["max_title_length"])
            self.max_desc_spin.setValue(data["max_description_length"])
            self.tag_count_spin.setValue(data["required_tag_count"])
            self.batch_size_spin.setValue(min(max(data["batch_size"], 1), 20))
            self.cache_spin.setValue(data["compression_quality"])
            delay_value = data.get("delay_interval", "Random")
            self.delay_combo.setCurrentText(str(delay_value))
            proxy_value = data.get("video_proxy_setting", "Auto")
            self.proxy_combo.setCurrentText(str(proxy_value))
        except Exception as e:
            print(f"Failed to load prompt config: {e}")
        self._loading = False

    def refresh_presets(self):
        self._loading = True
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            current_text = self.preset_combo.currentText()
            self.preset_combo.clear()
            
            for preset in data.get("prompt_presets", []):
                self.preset_combo.addItem(preset["name"])
            
            current_preset = data.get("selected_preset", current_text)
            index = self.preset_combo.findText(current_preset)
            if index >= 0:
                self.preset_combo.setCurrentIndex(index)
            elif self.preset_combo.count() > 0:
                self.preset_combo.setCurrentIndex(0)
        except Exception as e:
            print(f"Failed to refresh presets: {e}")
        self._loading = False

    def on_preset_changed(self):
        if getattr(self, "_loading", False):
            return
        
        preset_name = self.preset_combo.currentText()
        if not preset_name:
            return
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for preset in data.get("prompt_presets", []):
                if preset["name"] == preset_name:
                    data["prompt"]["title_requirements"] = preset.get("title_requirements", "")
                    data["prompt"]["description_requirements"] = preset.get("description_requirements", "")
                    data["prompt"]["keywords_requirements"] = preset.get("keywords_requirements", "")
                    data["prompt"]["general_guides"] = preset.get("general_guides", "")
                    data["prompt"]["strict_donts"] = preset.get("strict_donts", "")
                    data["prompt"]["negative_prompt"] = preset.get("negative_prompt", "")
                    data["prompt"]["custom_prompt"] = preset.get("custom_prompt", "")
                    break
            
            data["selected_preset"] = preset_name
            
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error changing preset: {e}")

    def save_prompt_config(self):
        if getattr(self, "_loading", False):
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        data["min_title_length"] = self.min_title_spin.value()
        data["max_title_length"] = self.max_title_spin.value()
        data["max_description_length"] = self.max_desc_spin.value()
        data["required_tag_count"] = self.tag_count_spin.value()
        data["batch_size"] = self.batch_size_spin.value()
        data["compression_quality"] = self.cache_spin.value()
        data["delay_interval"] = self.delay_combo.currentText()
        data["video_proxy_setting"] = self.proxy_combo.currentText()
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save prompt config: {e}")