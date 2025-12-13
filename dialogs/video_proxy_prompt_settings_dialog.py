from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox, QPushButton, QGroupBox, QMessageBox, QSizePolicy
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
        try:
            ic.setPixmap(qta.icon('fa6s.video').pixmap(14, 14))
        except Exception:
            ic.setText('')
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
            try:
                ic.setPixmap(qta.icon(icon_name).pixmap(14, 14))
            except Exception:
                ic.setText('')
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

        outer.addLayout(row_widget('fa6s.tag', 'Label:', self.label_edit))
        outer.addLayout(row_widget('fa6s.expand', 'Resolution:', self.res_edit))
        outer.addLayout(row_widget('fa6s.gauge', 'Bitrate:', self.bitrate_edit))
        outer.addLayout(row_widget('fa6s.sliders', 'CRF:', self.crf_spin))

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
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            
            self._load_presets()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save presets: {e}")
