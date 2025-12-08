from PySide6.QtWidgets import QWidget, QHBoxLayout, QSpinBox, QSizePolicy, QLabel, QSpacerItem, QVBoxLayout, QFrame
from PySide6.QtCore import Qt
import qtawesome as qta
import json
import os
from config import BASE_PATH

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

        icon_color = "#4e9e20"
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
        min_title_label.setStyleSheet("color: #666; font-size: 10px;")
        min_title_header.addWidget(min_title_icon)
        min_title_header.addWidget(min_title_label)
        min_title_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        min_title_group.addLayout(min_title_header)
        self.min_title_spin = QSpinBox()
        self.min_title_spin.setRange(1, 1000)
        self.min_title_spin.setFixedWidth(fixed_width)
        self.min_title_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.min_title_spin.setToolTip("Minimum title length in characters.\nShorter titles may be less descriptive.")
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
        max_title_label.setStyleSheet("color: #666; font-size: 10px;")
        max_title_header.addWidget(max_title_icon)
        max_title_header.addWidget(max_title_label)
        max_title_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        max_title_group.addLayout(max_title_header)
        self.max_title_spin = QSpinBox()
        self.max_title_spin.setRange(1, 1000)
        self.max_title_spin.setFixedWidth(fixed_width)
        self.max_title_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.max_title_spin.setToolTip("Maximum title length in characters.\nTitles longer than this will be truncated.")
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
        max_desc_label.setStyleSheet("color: #666; font-size: 10px;")
        max_desc_header.addWidget(max_desc_icon)
        max_desc_header.addWidget(max_desc_label)
        max_desc_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        max_desc_group.addLayout(max_desc_header)
        self.max_desc_spin = QSpinBox()
        self.max_desc_spin.setRange(1, 2000)
        self.max_desc_spin.setFixedWidth(fixed_width)
        self.max_desc_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.max_desc_spin.setToolTip("Maximum description length in characters.\nKeep descriptions concise and clear.")
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
        tag_count_label.setStyleSheet("color: #666; font-size: 10px;")
        tag_count_header.addWidget(tag_count_icon)
        tag_count_header.addWidget(tag_count_label)
        tag_count_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        tag_count_group.addLayout(tag_count_header)
        self.tag_count_spin = QSpinBox()
        self.tag_count_spin.setRange(1, 100)
        self.tag_count_spin.setFixedWidth(fixed_width)
        self.tag_count_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.tag_count_spin.setToolTip("Number of keywords/tags to generate.\nExactly this many tags will be used.")
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
        batch_size_label.setStyleSheet("color: #666; font-size: 10px;")
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
        compression_label = QLabel("Compression")
        compression_label.setStyleSheet("color: #666; font-size: 10px;")
        compression_header.addWidget(compression_icon)
        compression_header.addWidget(compression_label)
        compression_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        compression_group.addLayout(compression_header)
        self.cache_spin = QSpinBox()
        self.cache_spin.setRange(1, 100)
        self.cache_spin.setFixedWidth(fixed_width)
        self.cache_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.cache_spin.setToolTip("Compression quality (1-100).\nLower value = higher compression, more efficient internet data usage.")
        compression_group.addWidget(self.cache_spin)
        
        compression_wrapper = QWidget()
        compression_wrapper.setLayout(compression_group)
        compression_wrapper.setFixedWidth(fixed_width)
        main_layout.addWidget(compression_wrapper)

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
        self.load_prompt_config()

    def load_prompt_config(self):
        self._loading = True
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.min_title_spin.setValue(data["min_title_length"])
            self.max_title_spin.setValue(data["max_title_length"])
            self.max_desc_spin.setValue(data["max_description_length"])
            self.tag_count_spin.setValue(data["required_tag_count"])
            self.batch_size_spin.setValue(min(max(data["batch_size"], 1), 20))
            self.cache_spin.setValue(data["compression_quality"])
        except Exception as e:
            print(f"Failed to load prompt config: {e}")
        self._loading = False

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
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save prompt config: {e}")