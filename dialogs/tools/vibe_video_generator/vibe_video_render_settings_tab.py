import os
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QGroupBox, QComboBox, QSpinBox,
    QDoubleSpinBox, QCheckBox, QFormLayout, QScrollArea, QFrame,
    QTextEdit
)
from PySide6.QtCore import Qt, Signal
import qtawesome as qta
from config import BASE_PATH


CONFIG_PATH = os.path.join(BASE_PATH, "configs", "remotion_config.json")

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)


def get_preset_data(key):
    config = load_config()
    if key == "custom":
        return config.get("custom_preset")
    return config.get("presets", {}).get(key)


def get_active_preset():
    return load_config().get("active_preset", "1080p30")


def set_active_preset(key, data=None):
    config = load_config()
    config["active_preset"] = key
    if data is not None:
        config["custom_preset"] = data
    save_config(config)


class RenderSettingsTabWidget(QWidget):
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading_preset = False
        self._setup_ui()
        self._load_preset(get_active_preset())

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)
        preset_row.addWidget(QLabel("Preset:"))

        self.preset_combo = QComboBox()
        self._refresh_combo()
        self.preset_combo.setToolTip("Select a resolution/fps/video bitrate preset.\n"
                                        "Built-in presets: 720p30, 1080p30, 2K60, 4K30, etc.\n"
                                        "Custom presets can be saved with the 'Save' button.")
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        preset_row.addWidget(self.preset_combo, 1)

        self.save_btn = QPushButton(qta.icon('fa6s.floppy-disk'), 'Save')
        self.save_btn.setToolTip("Save current Width/Height/FPS/Video Bitrate as a new custom preset.")
        self.save_btn.clicked.connect(self._on_save)
        preset_row.addWidget(self.save_btn)

        self.reset_btn = QPushButton(qta.icon('fa6s.rotate-left'), 'Reset')
        self.reset_btn.setToolTip("Reset to the default 1080p30 preset.")
        self.reset_btn.clicked.connect(self._on_reset)
        preset_row.addWidget(self.reset_btn)

        layout.addLayout(preset_row)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setSpacing(12)
        cl.setContentsMargins(12, 12, 12, 12)

        cl.addWidget(self._video_group())
        cl.addWidget(self._audio_group())
        cl.addWidget(self._quality_group())
        cl.addWidget(self._perf_group())
        cl.addWidget(self._browser_group())
        cl.addWidget(self._advanced_group())
        cl.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

    def _refresh_combo(self):
        self.preset_combo.clear()
        config = load_config()
        active = config.get("active_preset", "1080p30")
        for key, p in config.get("presets", {}).items():
            self.preset_combo.addItem(p.get("label", key), key)
        if config.get("custom_preset"):
            self.preset_combo.addItem("Custom", "custom")
        idx = self.preset_combo.findData(active)
        if idx >= 0:
            self.preset_combo.setCurrentIndex(idx)

    def _on_preset_changed(self, text):
        key = self.preset_combo.currentData()
        if key:
            set_active_preset(key)
            self._load_preset(key)

    def _load_preset(self, key):
        p = get_preset_data(key)
        if not p:
            return
        self._loading_preset = True
        self.width_spin.setValue(p.get("width", 0))
        self.height_spin.setValue(p.get("height", 0))
        self.fps_spin.setValue(p.get("fps", 0))
        self.video_bitrate_edit.setText(p.get("video_bitrate", ""))
        self._loading_preset = False

    def _on_save(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if ok and name.strip():
            data = self._current_preset_data()
            config = load_config()
            if "custom_presets" not in config:
                config["custom_presets"] = {}
            key = name.strip().lower().replace(" ", "_")
            config["custom_presets"][key] = {"label": name.strip(), **data}
            config["custom_preset"] = data
            config["active_preset"] = "custom"
            save_config(config)
            self._refresh_combo()
            idx = self.preset_combo.findData("custom")
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
            self.settings_changed.emit()

    def _on_reset(self):
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(self, "Reset", "Reset ke 1080p30?") == QMessageBox.StandardButton.Yes:
            self._load_preset("1080p30")
            set_active_preset("1080p30")
            idx = self.preset_combo.findData("1080p30")
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
            self.settings_changed.emit()

    def _current_preset_data(self):
        return {
            "width": self.width_spin.value(),
            "height": self.height_spin.value(),
            "fps": self.fps_spin.value(),
            "video_bitrate": self.video_bitrate_edit.text(),
        }

    def get_all_render_settings(self):
        """Get all render settings as a dictionary.
        Note: duration is in seconds (user-facing). The helper will convert to frames for CLI."""
        return {
            # Video settings
            'codec': self.codec_combo.currentText(),
            'pixel_format': self.pixel_format_combo.currentText(),
            'width': self.width_spin.value(),
            'height': self.height_spin.value(),
            'fps': self.fps_spin.value(),
            'duration': self.duration_spin.value(),  # seconds
            'scale': self.scale_spin.value(),
            'image_format': self.image_format_combo.currentText(),
            'sequence': self.sequence_checkbox.isChecked(),
            'frames': self.frames_edit.text().strip() or None,
            'every_nth_frame': self.every_nth_spin.value(),

            # Audio settings
            'audio_codec': self.audio_codec_combo.currentText(),
            'audio_bitrate': self.audio_bitrate_edit.text().strip() or None,
            'sample_rate': self.sample_rate_spin.value(),
            'muted': self.muted_checkbox.isChecked(),
            'enforce_audio_track': self.enforce_audio_checkbox.isChecked(),
            'separate_audio_to': self.separate_audio_edit.text().strip() or None,
            'for_seamless_aac_concatenation': self.for_seamless_aac_checkbox.isChecked(),

            # Quality settings
            'crf': self.crf_spin.value(),
            'video_bitrate': self.video_bitrate_edit.text().strip() or None,
            'buffer_size': self.buffer_size_edit.text().strip() or None,
            'max_rate': self.max_rate_edit.text().strip() or None,
            'jpeg_quality': self.jpeg_quality_spin.value(),
            'prores_profile': self.prores_profile_combo.currentText(),
            'x264_preset': self.x264_preset_combo.currentText(),
            'gif_loops': self.gif_loops_spin.value(),

            # Performance settings
            'concurrency': self.concurrency_spin.value(),
            'hardware_acceleration': self.hardware_accel_combo.currentText(),
            'disallow_parallel_encoding': self.disallow_parallel_checkbox.isChecked(),

            # Browser settings
            'browser_executable': self.browser_exec_edit.text().strip() or None,
            'chrome_mode': self.chrome_mode_combo.currentData(),
            'timeout': self.timeout_spin.value(),
            'ignore_certificate_errors': self.ignore_cert_checkbox.isChecked(),
            'disable_web_security': self.disable_web_security_checkbox.isChecked(),
            'disable_headless': self.disable_headless_checkbox.isChecked(),
            'dark_mode': self.dark_mode_checkbox.isChecked(),
            'user_agent': self.user_agent_edit.text().strip() or None,
            'gl': self.gl_combo.currentData(),

            # Advanced settings
            'config_file': self.config_edit.text().strip() or None,
            'env_file': self.env_file_edit.text().strip() or None,
            'props': self.props_edit.text().strip() or None,
            'bundle_cache': self.bundle_cache_checkbox.isChecked(),
            'log': self.log_combo.currentText(),
            'port': self.port_spin.value(),
            'public_dir': self.public_dir_edit.text().strip() or None,
            'media_cache_size_in_bytes': self.media_cache_size_edit.text().strip() or None,
            'offthreadvideo_cache_size_in_bytes': self.offthreadvideo_cache_edit.text().strip() or None,
            'offthreadvideo_video_threads': self.offthreadvideo_threads_spin.value(),
            'enable_multiprocess_on_linux': self.enable_multiprocess_checkbox.isChecked(),
            'repro': self.repro_checkbox.isChecked(),
            'binaries_directory': self.binaries_dir_edit.text().strip() or None,
            'experimental_rspack': self.experimental_rspack_checkbox.isChecked(),
            'metadata': self.metadata_edit.toPlainText().strip() or None,
            'color_space': self.color_space_combo.currentText(),
            'image_sequence_pattern': self.image_sequence_pattern_edit.text().strip() or None,
            'overwrite': self.overwrite_checkbox.isChecked(),
        }

    def _autosave_custom(self):
        if self._loading_preset:
            return
        config = load_config()
        active = config.get("active_preset", "1080p30")
        data = self._current_preset_data()
        if active in config.get("presets", {}):
            config["custom_preset"] = data
            config["active_preset"] = "custom"
            save_config(config)
            self._refresh_combo()
            idx = self.preset_combo.findData("custom")
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
        elif active == "custom":
            config["custom_preset"] = data
            save_config(config)

    def _cb(self, emit=False):
        def fn(*args):
            if emit:
                self.settings_changed.emit()
            self._autosave_custom()
        return fn

    def _video_group(self):
        g = QGroupBox("Video Settings")
        l = QFormLayout()
        l.setSpacing(8)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        g.setLayout(l)

        self.codec_combo = QComboBox()
        self.codec_combo.addItems(['h264', 'h265', 'av1', 'vp8', 'vp9', 'prores', 'h264-mkv'])
        self.codec_combo.setToolTip("Video codec for output.\n"
                                     "• h264: Most compatible, widely supported (default)\n"
                                     "• h265/AV1: ~50% smaller files, need modern players/ browsers\n"
                                     "• ProRes: High-quality intermediate format for post-production\n"
                                     "• h264-mkv: H.264 in MKV container")
        self.codec_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('Codec:', self.codec_combo)

        self.pixel_format_combo = QComboBox()
        self.pixel_format_combo.addItems(['yuv420p', 'yuv422p', 'yuv444p', 'yuva420p', 'yuva422p', 'yuva444p'])
        self.pixel_format_combo.setCurrentText('yuv420p')  # default to widely compatible format
        self.pixel_format_combo.setToolTip("Chroma subsampling format.\n"
                                            "• yuv420p: Standard for web/YouTube (most compatible)\n"
                                            "• yuv422p/yuv444p: Higher color fidelity, larger files\n"
                                            "• yuva*: Includes alpha channel for transparency")
        self.pixel_format_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('Pixel Format:', self.pixel_format_combo)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(0, 99999)
        self.width_spin.setSpecialValueText('Auto')
        self.width_spin.setToolTip("Output width in pixels.\n"
                                     "0 = auto (uses the composition's natural width).")
        self.width_spin.valueChanged.connect(self._cb(True))
        l.addRow('Width:', self.width_spin)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(0, 99999)
        self.height_spin.setSpecialValueText('Auto')
        self.height_spin.setToolTip("Output height in pixels.\n"
                                      "0 = auto (uses the composition's natural height).")
        self.height_spin.valueChanged.connect(self._cb(True))
        l.addRow('Height:', self.height_spin)

        self.fps_spin = QDoubleSpinBox()
        self.fps_spin.setRange(0, 1000)
        self.fps_spin.setDecimals(2)
        self.fps_spin.setSpecialValueText('Auto')
        self.fps_spin.setToolTip("Frames per second.\n"
                                   "0 = auto (uses the composition's fps).\n"
                                   "Common values: 24 (film), 25 (PAL), 30 (NTSC/online), 60 (smooth motion).")
        self.fps_spin.valueChanged.connect(self._cb(True))
        l.addRow('FPS:', self.fps_spin)

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 3600)
        self.duration_spin.setValue(5)
        self.duration_spin.setSuffix(" s")
        self.duration_spin.setSpecialValueText('Auto')
        self.duration_spin.setToolTip("Duration in seconds.\n"
                                        "0 = auto (defaults to 10 seconds).\n"
                                        "Actual frame count = duration × fps.")
        self.duration_spin.valueChanged.connect(self._cb(True))
        l.addRow('Duration (seconds):', self.duration_spin)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.01, 16.0)
        self.scale_spin.setValue(1.0)
        self.scale_spin.setDecimals(2)
        self.scale_spin.setToolTip("Scale factor applied to the composition.\n"
                                     "1.0 = original size, 0.5 = half size, 2.0 = double size.")
        self.scale_spin.valueChanged.connect(self._cb(True))
        l.addRow('Scale:', self.scale_spin)

        self.image_format_combo = QComboBox()
        self.image_format_combo.addItems(['png', 'jpeg'])
        self.image_format_combo.setToolTip("Format for capturing individual frames.\n"
                                             "PNG = lossless, large files, best quality.\n"
                                             "JPEG = lossy compression, smaller files, faster.")
        self.image_format_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('Image Format:', self.image_format_combo)

        self.sequence_checkbox = QCheckBox('Output as image sequence')
        self.sequence_checkbox.setToolTip("Render frames as individual image files instead of a single video.\n"
                                            "Useful for frame-by-frame inspection, manual editing, or external encoding.")
        self.sequence_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.sequence_checkbox)

        self.frames_edit = QLineEdit()
        self.frames_edit.setPlaceholderText('e.g., 0-100, 200-300')
        self.frames_edit.setToolTip("Specific frame ranges to render.\n"
                                      "Examples: '0-100' (first 100 frames), '0-100,200-300' (two ranges).\n"
                                      "Overrides Duration setting when specified.")
        self.frames_edit.textChanged.connect(self._cb(True))
        l.addRow('Frames:', self.frames_edit)

        self.every_nth_spin = QSpinBox()
        self.every_nth_spin.setRange(1, 1000)
        self.every_nth_spin.setValue(1)
        self.every_nth_spin.setToolTip("Render every Nth frame only.\n"
                                         "1 = every frame (normal). 2 = every other frame.\n"
                                         "Useful for speed-testing or creating time-lapses.")
        self.every_nth_spin.valueChanged.connect(self._cb(True))
        l.addRow('Every Nth Frame:', self.every_nth_spin)

        return g

    def _audio_group(self):
        g = QGroupBox("Audio Settings")
        l = QFormLayout()
        l.setSpacing(8)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        g.setLayout(l)

        self.audio_codec_combo = QComboBox()
        self.audio_codec_combo.addItems(['aac', 'mp3', 'wav', 'opus'])
        self.audio_codec_combo.setToolTip("Audio codec for the output.\n"
                                            "• AAC: Standard for MP4/Web (default recommendation)\n"
                                            "• MP3: Legacy compatibility\n"
                                            "• WAV: Uncompressed, huge files, highest quality\n"
                                            "• Opus: Best quality-to-size ratio, ideal for WebM")
        self.audio_codec_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('Audio Codec:', self.audio_codec_combo)

        self.audio_bitrate_edit = QLineEdit()
        self.audio_bitrate_edit.setPlaceholderText('e.g., 128k, 192k')
        self.audio_bitrate_edit.setToolTip("Audio bitrate (e.g., 128k, 192k, 320k).\n"
                                             "Higher = better quality, larger file.\n"
                                             "128k adequate for speech/music, 192k+ recommended for high-fidelity.")
        self.audio_bitrate_edit.textChanged.connect(self._cb(True))
        l.addRow('Audio Bitrate:', self.audio_bitrate_edit)

        self.muted_checkbox = QCheckBox('Mute audio')
        self.muted_checkbox.setToolTip("Remove all audio from the output video.")
        self.muted_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.muted_checkbox)

        self.enforce_audio_checkbox = QCheckBox('Enforce silent audio track')
        self.enforce_audio_checkbox.setToolTip("Ensure the output file contains an audio track even if silent.\n"
                                                 "Some platforms (YouTube, social media) require an audio stream.")
        self.enforce_audio_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.enforce_audio_checkbox)

        self.separate_audio_edit = QLineEdit()
        self.separate_audio_edit.setPlaceholderText('Path for separate audio file')
        self.separate_audio_edit.setToolTip("Save audio to a separate file while rendering video.\n"
                                              "Useful for audio-only deliverables, re-mixing, or separate processing.")
        self.separate_audio_edit.textChanged.connect(self._cb(True))
        l.addRow('Separate Audio To:', self.separate_audio_edit)

        self.for_seamless_aac_checkbox = QCheckBox('For seamless AAC concatenation')
        self.for_seamless_aac_checkbox.setToolTip("Optimizes AAC encoding to avoid gaps when concatenating multiple outputs.\n"
                                                    "Only needed if you plan to join multiple rendered videos together.")
        self.for_seamless_aac_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.for_seamless_aac_checkbox)

        self.sample_rate_spin = QSpinBox()
        self.sample_rate_spin.setRange(8000, 192000)
        self.sample_rate_spin.setValue(48000)
        self.sample_rate_spin.setSuffix(" Hz")
        self.sample_rate_spin.setToolTip("Audio sample rate in Hertz.\n"
                                           "48000 Hz = standard for video/streaming (default).\n"
                                           "44100 Hz = CD quality. Range: 8000–192000 Hz.\n"
                                           "Higher rates capture more frequency detail but increase file size.")
        self.sample_rate_spin.valueChanged.connect(self._cb(True))
        l.addRow('Sample Rate (Hz):', self.sample_rate_spin)

        return g

    def _quality_group(self):
        g = QGroupBox("Quality Settings")
        l = QFormLayout()
        l.setSpacing(8)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        g.setLayout(l)

        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(0, 51)
        self.crf_spin.setSpecialValueText('Auto')
        self.crf_spin.setToolTip("Constant Rate Factor (quality-based encoding).\n"
                                   "0 = lossless (huge files). 18–23 = visually lossless.\n"
                                   "Higher values increase compression (smaller files) but may introduce artifacts.\n"
                                   "Only used with h264/h265/av1 codecs. Leave at Auto when using bitrate-based encoding.")
        self.crf_spin.valueChanged.connect(self._cb(True))
        l.addRow('CRF:', self.crf_spin)

        self.video_bitrate_edit = QLineEdit()
        self.video_bitrate_edit.setPlaceholderText('e.g., 5M, 10M, 20M')
        self.video_bitrate_edit.setToolTip("Target video bitrate (e.g., 5M = 5 Mbps, 20M = 20 Mbps).\n"
                                              "Higher bitrate = better quality, larger file size.\n"
                                              "Used for bitrate-based encoding (CBR/VBR). Ignored if CRF is set.")
        self.video_bitrate_edit.textChanged.connect(self._cb(True))
        l.addRow('Video Bitrate:', self.video_bitrate_edit)

        self.buffer_size_edit = QLineEdit()
        self.buffer_size_edit.setPlaceholderText('e.g., 10M')
        self.buffer_size_edit.setToolTip("Video buffer size for rate-control smoothing.\n"
                                           "Typically set equal to bitrate (e.g., bitrate=10M → buffer=10M).\n"
                                           "Affects how bursty video data is smoothed during playback.")
        self.buffer_size_edit.textChanged.connect(self._cb(True))
        l.addRow('Buffer Size:', self.buffer_size_edit)

        self.max_rate_edit = QLineEdit()
        self.max_rate_edit.setPlaceholderText('e.g., 5M')
        self.max_rate_edit.setToolTip("Maximum video bitrate ceiling.\n"
                                        "Prevents bitrate spikes that could exceed target or cause playback issues.\n"
                                        "Useful for constrained streaming scenarios.")
        self.max_rate_edit.textChanged.connect(self._cb(True))
        l.addRow('Max Rate:', self.max_rate_edit)

        self.jpeg_quality_spin = QSpinBox()
        self.jpeg_quality_spin.setRange(0, 100)
        self.jpeg_quality_spin.setValue(80)
        self.jpeg_quality_spin.setToolTip("JPEG quality for image sequence output.\n"
                                             "0–30: very low quality, 40–60: acceptable, 70–90: good quality,\n"
                                             "90–100: near-lossless (larger files). Default 80 is a good balance.")
        self.jpeg_quality_spin.valueChanged.connect(self._cb(True))
        l.addRow('JPEG Quality:', self.jpeg_quality_spin)

        self.prores_profile_combo = QComboBox()
        self.prores_profile_combo.addItems(['auto', '4444', '4444-xq', 'hq', 'standard', 'light', 'proxy'])
        self.prores_profile_combo.setToolTip("ProRes codec profile (for professional intermediate files).\n"
                                                "• auto: let ffmpeg choose (usually 4444)\n"
                                                "• 4444: highest quality, preserves alpha\n"
                                                "• 4444-xq: extreme quality, massive files\n"
                                                "• hq/standard: good quality, smaller than 4444\n"
                                                "• light/proxy: lower quality for proxies/quick edits")
        self.prores_profile_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('ProRes Profile:', self.prores_profile_combo)

        self.x264_preset_combo = QComboBox()
        self.x264_preset_combo.addItems(['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'])
        self.x264_preset_combo.setToolTip("H.264 encoding preset: speed vs compression trade-off.\n"
                                             "• ultrafast–fast: fastest encode, larger files (use for quick tests)\n"
                                                "• medium: balanced default\n"
                                             "• slow–veryslow: slowest encode, smallest files (best for final renders)")
        self.x264_preset_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('x264 Preset:', self.x264_preset_combo)

        self.gif_loops_spin = QSpinBox()
        self.gif_loops_spin.setRange(0, 9999)
        self.gif_loops_spin.setSpecialValueText('Infinite')
        self.gif_loops_spin.setToolTip("Number of times a GIF animation repeats.\n"
                                          "0 = loop forever (infinite).\n"
                                          "1–n = play exactly N times then stop.")
        self.gif_loops_spin.valueChanged.connect(self._cb(True))
        l.addRow('GIF Loops:', self.gif_loops_spin)

        return g

    def _perf_group(self):
        g = QGroupBox("Performance Settings")
        l = QFormLayout()
        l.setSpacing(8)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        g.setLayout(l)

        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 256)
        self.concurrency_spin.setSpecialValueText('Auto')
        self.concurrency_spin.setToolTip("Number of parallel encoding workers.\n"
                                            "Higher values speed up encoding on multi-core CPUs but use more memory and disk I/O.\n"
                                            "'Auto' lets Remotion decide based on your CPU.")
        self.concurrency_spin.valueChanged.connect(self._cb(True))
        l.addRow('Concurrency:', self.concurrency_spin)

        self.hardware_accel_combo = QComboBox()
        self.hardware_accel_combo.addItems(['if-possible', 'disabled', 'required'])
        # Default to 'if-possible' to try GPU first, fallback to CPU automatically
        self.hardware_accel_combo.setCurrentText('if-possible')
        self.hardware_accel_combo.setToolTip("GPU hardware acceleration for encoding.\n"
                                                 "• if-possible: try GPU; fall back to CPU if unavailable\n"
                                                 "• disabled: CPU encoding only\n"
                                                 "• required: fail if GPU is not available")
        self.hardware_accel_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('Hardware Acceleration:', self.hardware_accel_combo)

        self.disallow_parallel_checkbox = QCheckBox('Disallow parallel encoding')
        self.disallow_parallel_checkbox.setToolTip("Prevents multiple encoding jobs from running in parallel.\n"
                                                     "Enable only if you encounter encoder errors or resource conflicts.")
        self.disallow_parallel_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.disallow_parallel_checkbox)

        return g

    def _browser_group(self):
        g = QGroupBox("Browser Settings")
        l = QFormLayout()
        l.setSpacing(8)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        g.setLayout(l)

        self.browser_exec_edit = QLineEdit()
        self.browser_exec_edit.setPlaceholderText('Path to browser executable')
        self.browser_exec_edit.setToolTip("Custom path to a Chromium/Chrome/Chrome for Testing executable.\n"
                                            "Leave empty to use Remotion's auto-detected browser.\n"
                                            "Useful if you have a specific browser version or custom build.")
        self.browser_exec_edit.textChanged.connect(self._cb(True))
        l.addRow('Browser Executable:', self.browser_exec_edit)

        self.browser_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), 'Browse')
        self.browser_browse_btn.setMaximumWidth(100)
        self.browser_browse_btn.setToolTip("Browse for a browser executable file (chromium, chrome, chrome-for-testing).")
        self.browser_browse_btn.clicked.connect(self._browse_browser)
        l.addRow('', self.browser_browse_btn)

        self.chrome_mode_combo = QComboBox()
        headless_shell_item = self.chrome_mode_combo.addItem('Chrome Headless Shell (default)', 'headless-shell')
        self.chrome_mode_combo.setItemData(self.chrome_mode_combo.count() - 1, "Default. Fast CPU rendering. Use for most cases.", Qt.ToolTipRole)
        chrome_testing_item = self.chrome_mode_combo.addItem('Chrome for Testing (GPU, Linux only)', 'chrome-for-testing')
        self.chrome_mode_combo.setItemData(self.chrome_mode_combo.count() - 1, "GPU-accelerated. Only on Linux with GPU. Slower startup, needs `npx remotion browser ensure --chrome-mode=chrome-for-testing`", Qt.ToolTipRole)
        self.chrome_mode_combo.setCurrentIndex(0)  # default
        self.chrome_mode_combo.setToolTip("Select the headless Chromium implementation.\n"
                                             "Headless Shell is lighter and faster. Chrome for Testing enables GPU acceleration (Linux only).")
        self.chrome_mode_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('Chrome Mode:', self.chrome_mode_combo)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1000, 999999999)
        self.timeout_spin.setValue(30000)
        self.timeout_spin.setSuffix(' ms')
        self.timeout_spin.setToolTip("Timeout for browser operations (page load, rendering) in milliseconds.\n"
                                       "Default 30000 (30 seconds). Increase for complex compositions that take longer to load/execute.")
        self.timeout_spin.valueChanged.connect(self._cb(True))
        l.addRow('Timeout:', self.timeout_spin)

        self.ignore_cert_checkbox = QCheckBox('Ignore certificate errors')
        self.ignore_cert_checkbox.setToolTip("Skip SSL/TLS certificate validation.\n"
                                               "Useful for self-signed HTTPS sources, but reduces security.\n"
                                               "Only enable when necessary.")
        self.ignore_cert_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.ignore_cert_checkbox)

        self.disable_web_security_checkbox = QCheckBox('Disable web security')
        self.disable_web_security_checkbox.setToolTip("Disable CORS and same-origin policies in the browser.\n"
                                                        "Allows loading local files or cross-origin resources.\n"
                                                        "Insecure — use only for trusted/local content.")
        self.disable_web_security_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.disable_web_security_checkbox)

        self.disable_headless_checkbox = QCheckBox('Disable headless mode')
        self.disable_headless_checkbox.setToolTip("Run browser in headed (visible) mode instead of headless.\n"
                                                    "Shows the browser window while rendering — useful for debugging.\n"
                                                    "Slower and requires a display; not recommended for server/CI use.")
        self.disable_headless_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.disable_headless_checkbox)

        self.dark_mode_checkbox = QCheckBox('Enable dark mode')
        self.dark_mode_checkbox.setToolTip("Force browser dark mode (where supported by the page/composition).\n"
                                              "Some compositions adapt styles based on prefers-color-scheme.")
        self.dark_mode_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.dark_mode_checkbox)

        self.user_agent_edit = QLineEdit()
        self.user_agent_edit.setPlaceholderText('Custom user agent string')
        self.user_agent_edit.setToolTip("Override the browser's User-Agent header.\n"
                                          "Useful for testing mobile sites, bypassing bot detection, or imitating specific browsers.\n"
                                          "Leave empty to use default.")
        self.user_agent_edit.textChanged.connect(self._cb(True))
        l.addRow('User Agent:', self.user_agent_edit)

        self.gl_combo = QComboBox()
        self.gl_combo.addItem('Default (auto)', '')
        self.gl_combo.setItemData(self.gl_combo.count() - 1, "Use Remotion's default GL backend", Qt.ToolTipRole)
        self.gl_combo.addItem('ANGLE (desktop WebGL)', 'angle')
        self.gl_combo.setItemData(self.gl_combo.count() - 1, "Desktop OpenGL via ANGLE. Best for Windows/macOS with GPU", Qt.ToolTipRole)
        self.gl_combo.addItem('ANGLE-EGL (Linux GPU)', 'angle-egl')
        self.gl_combo.setItemData(self.gl_combo.count() - 1, "ANGLE with EGL. Use on Linux with dedicated GPU", Qt.ToolTipRole)
        self.gl_combo.addItem('Swangle (no GPU / Lambda)', 'swangle')
        self.gl_combo.setItemData(self.gl_combo.count() - 1, "Software ANGLE. For headless servers without GPU (AWS Lambda, etc.)", Qt.ToolTipRole)
        self.gl_combo.addItem('EGL', 'egl')
        self.gl_combo.setItemData(self.gl_combo.count() - 1, "Native EGL. For Linux with proper EGL support", Qt.ToolTipRole)
        self.gl_combo.addItem('SwiftShader (software)', 'swiftshader')
        self.gl_combo.setItemData(self.gl_combo.count() - 1, "Pure software renderer. Slowest but most compatible", Qt.ToolTipRole)
        self.gl_combo.addItem('Vulkan (experimental)', 'vulkan')
        self.gl_combo.setItemData(self.gl_combo.count() - 1, "Vulkan backend. Experimental - may not work with all compositions", Qt.ToolTipRole)
        self.gl_combo.setCurrentIndex(0)  # default empty
        self.gl_combo.setToolTip("OpenGL backend for browser rendering.\n"
                                   "Default = auto-select best available.\n"
                                   "Use Swangle/SwiftShader for headless servers without GPU. Use ANGLE for desktop GPU acceleration.")
        self.gl_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('GL Backend:', self.gl_combo)

        return g

    def _advanced_group(self):
        g = QGroupBox("Advanced Settings")
        l = QFormLayout()
        l.setSpacing(8)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        g.setLayout(l)

        self.config_edit = QLineEdit()
        self.config_edit.setPlaceholderText('Path to config file')
        self.config_edit.setToolTip("Path to a Remotion config file (.ts, .js, or .json).\n"
                                      "Used to override project-wide Remotion settings.")
        self.config_edit.textChanged.connect(self._cb(True))
        l.addRow('Config File:', self.config_edit)

        self.config_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), 'Browse')
        self.config_browse_btn.setMaximumWidth(100)
        self.config_browse_btn.setToolTip("Browse for a Remotion config file.")
        self.config_browse_btn.clicked.connect(self._browse_config)
        l.addRow('', self.config_browse_btn)

        self.env_file_edit = QLineEdit()
        self.env_file_edit.setPlaceholderText('Path to .env file')
        self.env_file_edit.setToolTip("Path to a .env file containing environment variables.\n"
                                        "Variables are loaded and available in your composition code.")
        self.env_file_edit.textChanged.connect(self._cb(True))
        l.addRow('Env File:', self.env_file_edit)

        self.env_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), 'Browse')
        self.env_browse_btn.setMaximumWidth(100)
        self.env_browse_btn.setToolTip("Browse for a .env file.")
        self.env_browse_btn.clicked.connect(self._browse_env)
        l.addRow('', self.env_browse_btn)

        self.props_edit = QLineEdit()
        self.props_edit.setPlaceholderText('Path to props JSON file')
        self.props_edit.setToolTip("JSON file or inline JSON string passed as props to the root composition.\n"
                                     "Allows parameterizing renders (e.g., text, colors, asset paths).\n"
                                     "Use a file path or paste raw JSON directly.")
        self.props_edit.textChanged.connect(self._cb(True))
        l.addRow('Props File:', self.props_edit)

        self.props_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), 'Browse')
        self.props_browse_btn.setMaximumWidth(100)
        self.props_browse_btn.setToolTip("Browse for a JSON props file.")
        self.props_browse_btn.clicked.connect(self._browse_props)
        l.addRow('', self.props_browse_btn)

        self.bundle_cache_checkbox = QCheckBox('Enable bundle cache')
        self.bundle_cache_checkbox.setChecked(True)
        self.bundle_cache_checkbox.setToolTip("Cache npm bundles between renders to speed up subsequent renders after code changes.\n"
                                                 "Keep enabled unless you suspect the cache is stale or causing issues.")
        self.bundle_cache_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.bundle_cache_checkbox)

        self.log_combo = QComboBox()
        self.log_combo.addItems(['error', 'warn', 'info', 'verbose'])
        self.log_combo.setToolTip("Remotion CLI log level.\n"
                                    "• error: only errors\n"
                                    "• warn: warnings + errors\n"
                                    "• info: normal informative messages\n"
                                    "• verbose: debug-level output (use for bug reports)")
        self.log_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('Log Level:', self.log_combo)

        self.port_spin = QSpinBox()
        self.port_spin.setRange(0, 65535)
        self.port_spin.setSpecialValueText('Auto')
        self.port_spin.setToolTip("Port for Remotion's internal development server.\n"
                                    "0 = auto-assign a free port. Set a fixed port if required by firewall rules.")
        self.port_spin.valueChanged.connect(self._cb(True))
        l.addRow('Port:', self.port_spin)

        self.public_dir_edit = QLineEdit()
        self.public_dir_edit.setPlaceholderText('Path to public directory')
        self.public_dir_edit.setToolTip("Path to a 'public' directory of static assets.\n"
                                          "Files here are served at http://localhost:<port>/\n"
                                          "and can be imported in your composition without bundling.")
        self.public_dir_edit.textChanged.connect(self._cb(True))
        l.addRow('Public Directory:', self.public_dir_edit)

        self.public_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), 'Browse')
        self.public_browse_btn.setMaximumWidth(100)
        self.public_browse_btn.setToolTip("Browse for a public directory.")
        self.public_browse_btn.clicked.connect(self._browse_public_dir)
        l.addRow('', self.public_browse_btn)

        self.media_cache_size_edit = QLineEdit()
        self.media_cache_size_edit.setPlaceholderText('Size in bytes')
        self.media_cache_size_edit.setToolTip("Size of the media cache in bytes (e.g., 5000000000 = ~5 GB).\n"
                                                "Larger cache reduces re-downloads for remote media assets.\n"
                                                "Examples: 2G ≈ 2GB, 500M ≈ 500MB.")
        self.media_cache_size_edit.textChanged.connect(self._cb(True))
        l.addRow('Media Cache Size:', self.media_cache_size_edit)

        self.offthreadvideo_cache_edit = QLineEdit()
        self.offthreadvideo_cache_edit.setPlaceholderText('Size in bytes')
        self.offthreadvideo_cache_edit.setToolTip("OffthreadVideo cache size in bytes.\n"
                                                    "Caches decoded video frames between renders to speed up subsequent renders.\n"
                                                    "Set based on available RAM and video size.")
        self.offthreadvideo_cache_edit.textChanged.connect(self._cb(True))
        l.addRow('OffthreadVideo Cache:', self.offthreadvideo_cache_edit)

        self.offthreadvideo_threads_spin = QSpinBox()
        self.offthreadvideo_threads_spin.setRange(1, 128)
        self.offthreadvideo_threads_spin.setToolTip("Number of threads OffthreadVideo uses for decoding.\n"
                                                      "Set to the number of CPU cores for best performance.\n"
                                                      "Higher values increase RAM usage.")
        self.offthreadvideo_threads_spin.valueChanged.connect(self._cb(True))
        l.addRow('OffthreadVideo Threads:', self.offthreadvideo_threads_spin)

        self.enable_multiprocess_checkbox = QCheckBox('Enable multiprocess on Linux')
        self.enable_multiprocess_checkbox.setToolTip("Enable multiprocessing on Linux for better CPU utilization.\n"
                                                        "Only needed on Linux if you experience poor performance.\n"
                                                        "No effect on Windows/macOS.")
        self.enable_multiprocess_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.enable_multiprocess_checkbox)

        self.repro_checkbox = QCheckBox('Generate repro')
        self.repro_checkbox.setToolTip("Generate a reproducible archive containing all assets, logs, and config.\n"
                                         "Useful for bug reports, audits, or recreating exact render conditions.")
        self.repro_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.repro_checkbox)

        self.binaries_dir_edit = QLineEdit()
        self.binaries_dir_edit.setPlaceholderText('Path to binaries directory')
        self.binaries_dir_edit.setToolTip("Directory containing pre-built ffmpeg/ffprobe binaries.\n"
                                             "Overrides system defaults. Use only if you need specific versions.")
        self.binaries_dir_edit.textChanged.connect(self._cb(True))
        l.addRow('Binaries Directory:', self.binaries_dir_edit)

        self.binaries_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), 'Browse')
        self.binaries_browse_btn.setMaximumWidth(100)
        self.binaries_browse_btn.setToolTip("Browse for a binaries directory (containing ffmpeg/ffprobe).")
        self.binaries_browse_btn.clicked.connect(self._browse_binaries_dir)
        l.addRow('', self.binaries_browse_btn)

        self.experimental_rspack_checkbox = QCheckBox('Enable experimental Rspack')
        self.experimental_rspack_checkbox.setToolTip("Use Rspack (Rust-based webpack alternative) for faster bundling.\n"
                                                        "Experimental — may break on complex projects. Use only if you are comfortable troubleshooting.")
        self.experimental_rspack_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.experimental_rspack_checkbox)

        self.metadata_edit = QTextEdit()
        self.metadata_edit.setPlaceholderText('Metadata JSON')
        self.metadata_edit.setMaximumHeight(80)
        self.metadata_edit.setToolTip("JSON metadata to embed in the output file (if supported by codec/container).\n"
                                        "Example: {\"project\":\"myvideo\",\"version\":\"1\",\"author\":\"you\"}")
        self.metadata_edit.textChanged.connect(self._cb(True))
        l.addRow('Metadata:', self.metadata_edit)

        self.color_space_combo = QComboBox()
        self.color_space_combo.addItems(['default', 'srgb', 'rec2020', 'display-p3'])
        self.color_space_combo.setToolTip("Output color space.\n"
                                             "• default: composition's native color space\n"
                                             "• srgb: standard web/sRGB (most compatible)\n"
                                             "• rec2020: UHD/HDR wide gamut\n"
                                             "• display-p3: Apple devices, wide gamut")
        self.color_space_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('Color Space:', self.color_space_combo)

        self.image_sequence_pattern_edit = QLineEdit()
        self.image_sequence_pattern_edit.setPlaceholderText('e.g., frame-%04d.png')
        self.image_sequence_pattern_edit.setToolTip("Filename pattern for image sequences.\n"
                                                       "Use %04d (or similar) as frame number placeholder.\n"
                                                       "Example: frame-%04d.png → frame-0001.png, frame-0002.png, …")
        self.image_sequence_pattern_edit.textChanged.connect(self._cb(True))
        l.addRow('Image Sequence Pattern:', self.image_sequence_pattern_edit)

        self.overwrite_checkbox = QCheckBox('Overwrite existing file')
        self.overwrite_checkbox.setChecked(True)
        self.overwrite_checkbox.setToolTip("Automatically replace existing output file without prompting.\n"
                                              "Keep enabled for normal operation. Disable to be asked before overwriting.")
        self.overwrite_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.overwrite_checkbox)

        return g

    def _browse_browser(self):
        f, _ = QFileDialog.getOpenFileName(self, 'Select Browser', '', 'Executable Files (*.exe);;All Files (*)')
        if f:
            self.browser_exec_edit.setText(f)

    def _browse_config(self):
        f, _ = QFileDialog.getOpenFileName(self, 'Select Config', '', 'Config Files (*.ts *.js *.json);;All Files (*)')
        if f:
            self.config_edit.setText(f)

    def _browse_env(self):
        f, _ = QFileDialog.getOpenFileName(self, 'Select Env', '', 'Env Files (.env*);;All Files (*)')
        if f:
            self.env_file_edit.setText(f)

    def _browse_props(self):
        f, _ = QFileDialog.getOpenFileName(self, 'Select Props', '', 'JSON Files (*.json);;All Files (*)')
        if f:
            self.props_edit.setText(f)

    def _browse_public_dir(self):
        import os
        current = self.public_dir_edit.text()
        start_dir = current if current else os.path.expanduser('~')
        f = QFileDialog.getExistingDirectory(self, 'Select Public Directory', start_dir)
        if f:
            self.public_dir_edit.setText(f)

    def _browse_binaries_dir(self):
        import os
        current = self.binaries_dir_edit.text()
        start_dir = current if current else os.path.expanduser('~')
        f = QFileDialog.getExistingDirectory(self, 'Select Binaries Directory', start_dir)
        if f:
            self.binaries_dir_edit.setText(f)
