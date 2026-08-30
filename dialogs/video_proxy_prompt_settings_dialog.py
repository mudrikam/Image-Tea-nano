from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox, QPushButton, QGroupBox, QMessageBox, QSizePolicy, QCheckBox
from PySide6.QtCore import Qt
import qtawesome as qta
import json
import os
from config import BASE_PATH


class VideoProxyPromptSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video Proxy Presets")
        self.setFixedWidth(350)

        self.config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
        self.presets = {}
        self._load_presets()

        outer = QVBoxLayout()
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(4)
        ic = QLabel()
        ic.setPixmap(qta.icon('fa6s.video').pixmap(14, 14))
        ic.setFixedWidth(14)
        top.addWidget(ic)
        preset_label = QLabel('Preset:')
        preset_label.setFixedWidth(70)
        preset_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top.addWidget(preset_label)
        from PySide6.QtWidgets import QComboBox
        self.preset_combo = QComboBox()
        
        preferred = ['High', 'Medium', 'Low']
        keys = [k for k in preferred if k in self.presets] + [k for k in self.presets.keys() if k not in preferred]
        if not keys:
            keys = ['High', 'Medium', 'Low']
        self.preset_combo.addItems(keys)
        
        if 'Medium' in keys:
            self.preset_combo.setCurrentText('Medium')
        else:
            self.preset_combo.setCurrentText(keys[0])
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        self.preset_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.preset_combo.setToolTip('Select which preset to edit (High/Medium/Low)')
        top.addWidget(self.preset_combo)
        outer.addLayout(top)

        
        def row_widget(icon_name, text, widget):
            h = QHBoxLayout()
            h.setSpacing(4)
            ic = QLabel()
            ic.setPixmap(qta.icon(icon_name).pixmap(14, 14))
            ic.setFixedWidth(14)
            h.addWidget(ic)
            lbl = QLabel(text)
            lbl.setFixedWidth(70)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            h.addWidget(lbl)
            h.addWidget(widget)
            return h

        self.label_edit = QLineEdit('')
        self.label_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.label_edit.setToolTip('Human-readable label shown during upload (e.g. 720p Medium Quality)')
        self.res_edit = QLineEdit('')
        self.res_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.res_edit.setToolTip('FFmpeg scale string for target resolution, e.g. 1280:-2 or 854:480')
        self.bitrate_edit = QLineEdit('')
        self.bitrate_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.bitrate_edit.setToolTip('Target video bitrate, example: 2500k')
        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(0, 51)
        self.crf_spin.setToolTip('FFmpeg CRF (quality) value; lower = higher quality (0-51)')

        self.frame_count_spin = QSpinBox()
        self.frame_count_spin.setRange(1, 30)
        self.frame_count_spin.setToolTip('Number of frames to extract for AI services that do not support video (e.g., Groq, OpenAI, Blackbox)')
        self._load_frame_count()

        outer.addLayout(row_widget('fa6s.tag', 'Label:', self.label_edit))
        outer.addLayout(row_widget('fa6s.expand', 'Resolution:', self.res_edit))
        outer.addLayout(row_widget('fa6s.gauge', 'Bitrate:', self.bitrate_edit))
        outer.addLayout(row_widget('fa6s.sliders', 'CRF:', self.crf_spin))
        outer.addLayout(row_widget('fa6s.images', 'Frames:', self.frame_count_spin))

        pfa_row = QHBoxLayout()
        pfa_row.setSpacing(4)
        pfa_ic = QLabel()
        pfa_ic.setPixmap(qta.icon('fa6s.film').pixmap(14, 14))
        pfa_ic.setFixedWidth(14)
        pfa_row.addWidget(pfa_ic)
        pfa_spacer = QLabel()
        pfa_spacer.setFixedWidth(70)
        pfa_row.addWidget(pfa_spacer)
        self.prefer_frame_check = QCheckBox('Prefer Frame Analysis')
        self.prefer_frame_check.setToolTip(
            'When enabled, frames are extracted from the video and sent to the AI model instead of the full video.\n'
            'Works with all AI providers including Gemini. Default: enabled.'
        )
        pfa_row.addWidget(self.prefer_frame_check)
        pfa_row.addStretch()
        outer.addLayout(pfa_row)
        self._load_prefer_frame()

        hfed_row = QHBoxLayout()
        hfed_row.setSpacing(4)
        hfed_ic = QLabel()
        hfed_ic.setPixmap(qta.icon('fa6s.eye-slash').pixmap(14, 14))
        hfed_ic.setFixedWidth(14)
        hfed_row.addWidget(hfed_ic)
        hfed_spacer = QLabel()
        hfed_spacer.setFixedWidth(70)
        hfed_row.addWidget(hfed_spacer)
        self.hide_frame_dialog_check = QCheckBox('Hide frame extraction dialog')
        self.hide_frame_dialog_check.setToolTip(
            'When enabled, the frame extraction dialog/popup will be hidden during batch processing.'
        )
        hfed_row.addWidget(self.hide_frame_dialog_check)
        hfed_row.addStretch()
        outer.addLayout(hfed_row)
        self._load_hide_frame_dialog()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.save_btn = QPushButton('Save')
        self.save_btn.setIcon(qta.icon('fa6s.floppy-disk'))
        self.save_btn.clicked.connect(self.save)
        self.cancel_btn = QPushButton('Cancel')
        self.cancel_btn.setIcon(qta.icon('fa6s.xmark'))
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        outer.addLayout(btn_layout)

        self.setLayout(outer)

        
        self._on_preset_changed(self.preset_combo.currentText())
    def _load_presets(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            self.presets = cfg.get('video_proxy_presets', {})
        except Exception as e:
            print(f"Failed to load video proxy presets: {e}")
            self.presets = {}

    def _load_frame_count(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            frame_count = cfg.get('video_frame_count', 5)
            self.frame_count_spin.setValue(int(frame_count))
        except Exception as e:
            print(f"Failed to load video frame count: {e}")
            self.frame_count_spin.setValue(5)

    def _load_prefer_frame(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            prefer_frame = cfg.get('prefer_frame_analysis', True)
            self.prefer_frame_check.setChecked(bool(prefer_frame))
        except Exception as e:
            print(f"Failed to load prefer_frame_analysis: {e}")
            self.prefer_frame_check.setChecked(True)

    def _load_hide_frame_dialog(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            hide_dialog = cfg.get('hide_frame_extraction_dialog', False)
            self.hide_frame_dialog_check.setChecked(bool(hide_dialog))
        except Exception as e:
            print(f"Failed to load hide_frame_extraction_dialog: {e}")
            self.hide_frame_dialog_check.setChecked(False)

    def _on_preset_changed(self, name):
        p = self.presets.get(name, {})
        self.label_edit.setText(p.get('label', ''))
        self.res_edit.setText(p.get('resolution', ''))
        self.bitrate_edit.setText(p.get('bitrate', ''))
        try:
            self.crf_spin.setValue(int(p.get('crf', 23)))
        except Exception:
            self.crf_spin.setValue(23)

    def save(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
        
        name = self.preset_combo.currentText()
        presets = cfg.get('video_proxy_presets', {})
        presets[name] = {
            'label': self.label_edit.text(),
            'resolution': self.res_edit.text(),
            'bitrate': self.bitrate_edit.text(),
            'crf': self.crf_spin.value()
        }
        cfg['video_proxy_presets'] = presets
        cfg['video_frame_count'] = self.frame_count_spin.value()
        cfg['prefer_frame_analysis'] = self.prefer_frame_check.isChecked()
        cfg['hide_frame_extraction_dialog'] = self.hide_frame_dialog_check.isChecked()
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            
            self._load_presets()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save presets: {e}")
