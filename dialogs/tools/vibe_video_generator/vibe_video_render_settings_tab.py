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

BUILT_IN_PRESETS = ["720p30", "1080p60", "2K60", "4K60"]


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
    return load_config().get("active_preset", "1080p60")


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
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        preset_row.addWidget(self.preset_combo, 1)

        self.save_btn = QPushButton(qta.icon('fa6s.floppy-disk'), 'Save')
        self.save_btn.clicked.connect(self._on_save)
        preset_row.addWidget(self.save_btn)

        self.reset_btn = QPushButton(qta.icon('fa6s.rotate-left'), 'Reset')
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
        active = config.get("active_preset", "1080p60")
        for key in BUILT_IN_PRESETS:
            p = config.get("presets", {}).get(key)
            if p:
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
        if QMessageBox.question(self, "Reset", "Reset ke 1080p60?") == QMessageBox.StandardButton.Yes:
            self._load_preset("1080p60")
            set_active_preset("1080p60")
            idx = self.preset_combo.findData("1080p60")
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
        """Get all render settings as a dictionary."""
        return {
            # Video settings
            'codec': self.codec_combo.currentText(),
            'pixel_format': self.pixel_format_combo.currentText(),
            'width': self.width_spin.value(),
            'height': self.height_spin.value(),
            'fps': self.fps_spin.value(),
            'duration': self.duration_spin.value(),
            'scale': self.scale_spin.value(),
            'image_format': self.image_format_combo.currentText(),
            'sequence': self.sequence_checkbox.isChecked(),
            'frames': self.frames_edit.text().strip() or None,
            'every_nth_frame': self.every_nth_spin.value(),

            # Audio settings
            'audio_codec': self.audio_codec_combo.currentText(),
            'audio_bitrate': self.audio_bitrate_edit.text().strip() or None,
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
            'chrome_mode': self.chrome_mode_combo.currentText(),
            'timeout': self.timeout_spin.value(),
            'ignore_certificate_errors': self.ignore_cert_checkbox.isChecked(),
            'disable_web_security': self.disable_web_security_checkbox.isChecked(),
            'disable_headless': self.disable_headless_checkbox.isChecked(),
            'dark_mode': self.dark_mode_checkbox.isChecked(),
            'user_agent': self.user_agent_edit.text().strip() or None,
            'gl': self.gl_combo.currentText(),

            # Advanced settings
            'config_file': self.config_edit.text().strip() or None,
            'env_file': self.env_file_edit.text().strip() or None,
            'props_file': self.props_edit.text().strip() or None,
            'bundle_cache': self.bundle_cache_checkbox.isChecked(),
            'log_level': self.log_combo.currentText(),
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
        active = config.get("active_preset", "1080p60")
        data = self._current_preset_data()
        if active in BUILT_IN_PRESETS:
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
        self.codec_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('Codec:', self.codec_combo)

        self.pixel_format_combo = QComboBox()
        self.pixel_format_combo.addItems(['yuv420p', 'yuv422p', 'yuv444p', 'yuva420p', 'yuva422p', 'yuva444p'])
        self.pixel_format_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('Pixel Format:', self.pixel_format_combo)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(0, 99999)
        self.width_spin.setSpecialValueText('Auto')
        self.width_spin.valueChanged.connect(self._cb(True))
        l.addRow('Width:', self.width_spin)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(0, 99999)
        self.height_spin.setSpecialValueText('Auto')
        self.height_spin.valueChanged.connect(self._cb(True))
        l.addRow('Height:', self.height_spin)

        self.fps_spin = QDoubleSpinBox()
        self.fps_spin.setRange(0, 1000)
        self.fps_spin.setDecimals(2)
        self.fps_spin.setSpecialValueText('Auto')
        self.fps_spin.valueChanged.connect(self._cb(True))
        l.addRow('FPS:', self.fps_spin)

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(0, 999999)
        self.duration_spin.setSpecialValueText('Auto')
        self.duration_spin.valueChanged.connect(self._cb(True))
        l.addRow('Duration (frames):', self.duration_spin)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.01, 16.0)
        self.scale_spin.setValue(1.0)
        self.scale_spin.setDecimals(2)
        self.scale_spin.valueChanged.connect(self._cb(True))
        l.addRow('Scale:', self.scale_spin)

        self.image_format_combo = QComboBox()
        self.image_format_combo.addItems(['jpeg', 'png'])
        self.image_format_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('Image Format:', self.image_format_combo)

        self.sequence_checkbox = QCheckBox('Output as image sequence')
        self.sequence_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.sequence_checkbox)

        self.frames_edit = QLineEdit()
        self.frames_edit.setPlaceholderText('e.g., 0-100, 200-300')
        self.frames_edit.textChanged.connect(self._cb(True))
        l.addRow('Frames:', self.frames_edit)

        self.every_nth_spin = QSpinBox()
        self.every_nth_spin.setRange(1, 1000)
        self.every_nth_spin.setValue(1)
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
        self.audio_codec_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('Audio Codec:', self.audio_codec_combo)

        self.audio_bitrate_edit = QLineEdit()
        self.audio_bitrate_edit.setPlaceholderText('e.g., 128k, 192k')
        self.audio_bitrate_edit.textChanged.connect(self._cb(True))
        l.addRow('Audio Bitrate:', self.audio_bitrate_edit)

        self.muted_checkbox = QCheckBox('Mute audio')
        self.muted_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.muted_checkbox)

        self.enforce_audio_checkbox = QCheckBox('Enforce silent audio track')
        self.enforce_audio_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.enforce_audio_checkbox)

        self.separate_audio_edit = QLineEdit()
        self.separate_audio_edit.setPlaceholderText('Path for separate audio file')
        self.separate_audio_edit.textChanged.connect(self._cb(True))
        l.addRow('Separate Audio To:', self.separate_audio_edit)

        self.for_seamless_aac_checkbox = QCheckBox('For seamless AAC concatenation')
        self.for_seamless_aac_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.for_seamless_aac_checkbox)

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
        self.crf_spin.valueChanged.connect(self._cb(True))
        l.addRow('CRF:', self.crf_spin)

        self.video_bitrate_edit = QLineEdit()
        self.video_bitrate_edit.setPlaceholderText('e.g., 5M, 10M, 20M')
        self.video_bitrate_edit.textChanged.connect(self._cb(True))
        l.addRow('Video Bitrate:', self.video_bitrate_edit)

        self.buffer_size_edit = QLineEdit()
        self.buffer_size_edit.setPlaceholderText('e.g., 10M')
        self.buffer_size_edit.textChanged.connect(self._cb(True))
        l.addRow('Buffer Size:', self.buffer_size_edit)

        self.max_rate_edit = QLineEdit()
        self.max_rate_edit.setPlaceholderText('e.g., 5M')
        self.max_rate_edit.textChanged.connect(self._cb(True))
        l.addRow('Max Rate:', self.max_rate_edit)

        self.jpeg_quality_spin = QSpinBox()
        self.jpeg_quality_spin.setRange(0, 100)
        self.jpeg_quality_spin.setValue(80)
        self.jpeg_quality_spin.valueChanged.connect(self._cb(True))
        l.addRow('JPEG Quality:', self.jpeg_quality_spin)

        self.prores_profile_combo = QComboBox()
        self.prores_profile_combo.addItems(['auto', '4444', '4444-xq', 'hq', 'standard', 'light', 'proxy'])
        self.prores_profile_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('ProRes Profile:', self.prores_profile_combo)

        self.x264_preset_combo = QComboBox()
        self.x264_preset_combo.addItems(['ultrafast', 'superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow'])
        self.x264_preset_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('x264 Preset:', self.x264_preset_combo)

        self.gif_loops_spin = QSpinBox()
        self.gif_loops_spin.setRange(0, 9999)
        self.gif_loops_spin.setSpecialValueText('Infinite')
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
        self.concurrency_spin.valueChanged.connect(self._cb(True))
        l.addRow('Concurrency:', self.concurrency_spin)

        self.hardware_accel_combo = QComboBox()
        self.hardware_accel_combo.addItems(['none', 'cuda', 'videotoolbox', 'qsv', 'vaapi'])
        self.hardware_accel_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('Hardware Acceleration:', self.hardware_accel_combo)

        self.disallow_parallel_checkbox = QCheckBox('Disallow parallel encoding')
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
        self.browser_exec_edit.textChanged.connect(self._cb(True))
        l.addRow('Browser Executable:', self.browser_exec_edit)

        self.browser_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), 'Browse')
        self.browser_browse_btn.setMaximumWidth(100)
        self.browser_browse_btn.clicked.connect(self._browse_browser)
        l.addRow('', self.browser_browse_btn)

        self.chrome_mode_combo = QComboBox()
        self.chrome_mode_combo.addItems(['default', 'custom', 'launch'])
        self.chrome_mode_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('Chrome Mode:', self.chrome_mode_combo)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1000, 999999999)
        self.timeout_spin.setValue(30000)
        self.timeout_spin.setSuffix(' ms')
        self.timeout_spin.valueChanged.connect(self._cb(True))
        l.addRow('Timeout:', self.timeout_spin)

        self.ignore_cert_checkbox = QCheckBox('Ignore certificate errors')
        self.ignore_cert_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.ignore_cert_checkbox)

        self.disable_web_security_checkbox = QCheckBox('Disable web security')
        self.disable_web_security_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.disable_web_security_checkbox)

        self.disable_headless_checkbox = QCheckBox('Disable headless mode')
        self.disable_headless_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.disable_headless_checkbox)

        self.dark_mode_checkbox = QCheckBox('Enable dark mode')
        self.dark_mode_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.dark_mode_checkbox)

        self.user_agent_edit = QLineEdit()
        self.user_agent_edit.setPlaceholderText('Custom user agent string')
        self.user_agent_edit.textChanged.connect(self._cb(True))
        l.addRow('User Agent:', self.user_agent_edit)

        self.gl_combo = QComboBox()
        self.gl_combo.addItems(['default', 'egl', 'angle', 'swiftshader', 'gles'])
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
        self.config_edit.textChanged.connect(self._cb(True))
        l.addRow('Config File:', self.config_edit)

        self.config_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), 'Browse')
        self.config_browse_btn.setMaximumWidth(100)
        self.config_browse_btn.clicked.connect(self._browse_config)
        l.addRow('', self.config_browse_btn)

        self.env_file_edit = QLineEdit()
        self.env_file_edit.setPlaceholderText('Path to .env file')
        self.env_file_edit.textChanged.connect(self._cb(True))
        l.addRow('Env File:', self.env_file_edit)

        self.env_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), 'Browse')
        self.env_browse_btn.setMaximumWidth(100)
        self.env_browse_btn.clicked.connect(self._browse_env)
        l.addRow('', self.env_browse_btn)

        self.props_edit = QLineEdit()
        self.props_edit.setPlaceholderText('Path to props JSON file')
        self.props_edit.textChanged.connect(self._cb(True))
        l.addRow('Props File:', self.props_edit)

        self.props_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), 'Browse')
        self.props_browse_btn.setMaximumWidth(100)
        self.props_browse_btn.clicked.connect(self._browse_props)
        l.addRow('', self.props_browse_btn)

        self.bundle_cache_checkbox = QCheckBox('Enable bundle cache')
        self.bundle_cache_checkbox.setChecked(True)
        self.bundle_cache_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.bundle_cache_checkbox)

        self.log_combo = QComboBox()
        self.log_combo.addItems(['error', 'warn', 'info', 'verbose'])
        self.log_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('Log Level:', self.log_combo)

        self.port_spin = QSpinBox()
        self.port_spin.setRange(0, 65535)
        self.port_spin.setSpecialValueText('Auto')
        self.port_spin.valueChanged.connect(self._cb(True))
        l.addRow('Port:', self.port_spin)

        self.public_dir_edit = QLineEdit()
        self.public_dir_edit.setPlaceholderText('Path to public directory')
        self.public_dir_edit.textChanged.connect(self._cb(True))
        l.addRow('Public Directory:', self.public_dir_edit)

        self.public_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), 'Browse')
        self.public_browse_btn.setMaximumWidth(100)
        self.public_browse_btn.clicked.connect(self._browse_public_dir)
        l.addRow('', self.public_browse_btn)

        self.media_cache_size_edit = QLineEdit()
        self.media_cache_size_edit.setPlaceholderText('Size in bytes')
        self.media_cache_size_edit.textChanged.connect(self._cb(True))
        l.addRow('Media Cache Size:', self.media_cache_size_edit)

        self.offthreadvideo_cache_edit = QLineEdit()
        self.offthreadvideo_cache_edit.setPlaceholderText('Size in bytes')
        self.offthreadvideo_cache_edit.textChanged.connect(self._cb(True))
        l.addRow('OffthreadVideo Cache:', self.offthreadvideo_cache_edit)

        self.offthreadvideo_threads_spin = QSpinBox()
        self.offthreadvideo_threads_spin.setRange(1, 128)
        self.offthreadvideo_threads_spin.valueChanged.connect(self._cb(True))
        l.addRow('OffthreadVideo Threads:', self.offthreadvideo_threads_spin)

        self.enable_multiprocess_checkbox = QCheckBox('Enable multiprocess on Linux')
        self.enable_multiprocess_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.enable_multiprocess_checkbox)

        self.repro_checkbox = QCheckBox('Generate repro')
        self.repro_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.repro_checkbox)

        self.binaries_dir_edit = QLineEdit()
        self.binaries_dir_edit.setPlaceholderText('Path to binaries directory')
        self.binaries_dir_edit.textChanged.connect(self._cb(True))
        l.addRow('Binaries Directory:', self.binaries_dir_edit)

        self.binaries_browse_btn = QPushButton(qta.icon('fa6s.folder-open'), 'Browse')
        self.binaries_browse_btn.setMaximumWidth(100)
        self.binaries_browse_btn.clicked.connect(self._browse_binaries_dir)
        l.addRow('', self.binaries_browse_btn)

        self.experimental_rspack_checkbox = QCheckBox('Enable experimental Rspack')
        self.experimental_rspack_checkbox.toggled.connect(self._cb(True))
        l.addRow('', self.experimental_rspack_checkbox)

        self.metadata_edit = QTextEdit()
        self.metadata_edit.setPlaceholderText('Metadata JSON')
        self.metadata_edit.setMaximumHeight(80)
        self.metadata_edit.textChanged.connect(self._cb(True))
        l.addRow('Metadata:', self.metadata_edit)

        self.color_space_combo = QComboBox()
        self.color_space_combo.addItems(['default', 'srgb', 'rec2020', 'display-p3'])
        self.color_space_combo.currentTextChanged.connect(self._cb(True))
        l.addRow('Color Space:', self.color_space_combo)

        self.image_sequence_pattern_edit = QLineEdit()
        self.image_sequence_pattern_edit.setPlaceholderText('e.g., frame-%04d.png')
        self.image_sequence_pattern_edit.textChanged.connect(self._cb(True))
        l.addRow('Image Sequence Pattern:', self.image_sequence_pattern_edit)

        self.overwrite_checkbox = QCheckBox('Overwrite existing file')
        self.overwrite_checkbox.setChecked(True)
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
        f = QFileDialog.getExistingDirectory(self, 'Select Public Directory')
        if f:
            self.public_dir_edit.setText(f)

    def _browse_binaries_dir(self):
        f = QFileDialog.getExistingDirectory(self, 'Select Binaries Directory')
        if f:
            self.binaries_dir_edit.setText(f)

    def get_render_command_args(self):
        args = []
        if self.codec_combo.currentText() != 'h264':
            args.extend(['--codec', self.codec_combo.currentText()])
        if self.pixel_format_combo.currentText() != 'yuv420p':
            args.extend(['--pixel-format', self.pixel_format_combo.currentText()])
        if self.width_spin.value() > 0:
            args.extend(['--width', str(self.width_spin.value())])
        if self.height_spin.value() > 0:
            args.extend(['--height', str(self.height_spin.value())])
        if self.fps_spin.value() > 0:
            args.extend(['--fps', str(self.fps_spin.value())])
        if self.duration_spin.value() > 0:
            args.extend(['--duration', str(self.duration_spin.value())])
        if self.scale_spin.value() != 1.0:
            args.extend(['--scale', str(self.scale_spin.value())])
        if self.image_format_combo.currentText() != 'jpeg':
            args.extend(['--image-format', self.image_format_combo.currentText()])
        if self.sequence_checkbox.isChecked():
            args.append('--sequence')
        if self.frames_edit.text():
            args.extend(['--frames', self.frames_edit.text()])
        if self.every_nth_spin.value() > 1:
            args.extend(['--every-nth-frame', str(self.every_nth_spin.value())])
        if self.audio_codec_combo.currentText() != 'aac':
            args.extend(['--audio-codec', self.audio_codec_combo.currentText()])
        if self.audio_bitrate_edit.text():
            args.extend(['--audio-bitrate', self.audio_bitrate_edit.text()])
        if self.muted_checkbox.isChecked():
            args.append('--muted')
        if self.enforce_audio_checkbox.isChecked():
            args.append('--enforce-audio-track')
        if self.separate_audio_edit.text():
            args.extend(['--separate-audio-to', self.separate_audio_edit.text()])
        if self.for_seamless_aac_checkbox.isChecked():
            args.append('--for-seamless-aac-concatenation')
        if self.crf_spin.value() > 0:
            args.extend(['--crf', str(self.crf_spin.value())])
        if self.video_bitrate_edit.text():
            args.extend(['--video-bitrate', self.video_bitrate_edit.text()])
        if self.buffer_size_edit.text():
            args.extend(['--buffer-size', self.buffer_size_edit.text()])
        if self.max_rate_edit.text():
            args.extend(['--max-rate', self.max_rate_edit.text()])
        if self.jpeg_quality_spin.value() != 80:
            args.extend(['--jpeg-quality', str(self.jpeg_quality_spin.value())])
        if self.prores_profile_combo.currentText() != 'auto':
            args.extend(['--prores-profile', self.prores_profile_combo.currentText()])
        if self.x264_preset_combo.currentText() != 'medium':
            args.extend(['--x264-preset', self.x264_preset_combo.currentText()])
        if self.gif_loops_spin.value() > 0:
            args.extend(['--number-of-gif-loops', str(self.gif_loops_spin.value())])
        if self.concurrency_spin.value() > 0:
            args.extend(['--concurrency', str(self.concurrency_spin.value())])
        if self.hardware_accel_combo.currentText() != 'none':
            args.extend(['--hardware-acceleration', self.hardware_accel_combo.currentText()])
        if self.disallow_parallel_checkbox.isChecked():
            args.append('--disallow-parallel-encoding')
        if self.browser_exec_edit.text():
            args.extend(['--browser-executable', self.browser_exec_edit.text()])
        if self.chrome_mode_combo.currentText() != 'default':
            args.extend(['--chrome-mode', self.chrome_mode_combo.currentText()])
        if self.timeout_spin.value() != 30000:
            args.extend(['--timeout', str(self.timeout_spin.value())])
        if self.ignore_cert_checkbox.isChecked():
            args.append('--ignore-certificate-errors')
        if self.disable_web_security_checkbox.isChecked():
            args.append('--disable-web-security')
        if self.disable_headless_checkbox.isChecked():
            args.append('--disable-headless')
        if self.dark_mode_checkbox.isChecked():
            args.append('--dark-mode')
        if self.user_agent_edit.text():
            args.extend(['--user-agent', self.user_agent_edit.text()])
        if self.gl_combo.currentText() != 'default':
            args.extend(['--gl', self.gl_combo.currentText()])
        if self.config_edit.text():
            args.extend(['--config', self.config_edit.text()])
        if self.env_file_edit.text():
            args.extend(['--env-file', self.env_file_edit.text()])
        if self.props_edit.text():
            args.extend(['--props', self.props_edit.text()])
        if not self.bundle_cache_checkbox.isChecked():
            args.append('--bundle-cache=false')
        if self.log_combo.currentText() != 'info':
            args.extend(['--log', self.log_combo.currentText()])
        if self.port_spin.value() > 0:
            args.extend(['--port', str(self.port_spin.value())])
        if self.public_dir_edit.text():
            args.extend(['--public-dir', self.public_dir_edit.text()])
        if self.media_cache_size_edit.text():
            args.extend(['--media-cache-size-in-bytes', self.media_cache_size_edit.text()])
        if self.offthreadvideo_cache_edit.text():
            args.extend(['--offthreadvideo-cache-size-in-bytes', self.offthreadvideo_cache_edit.text()])
        if self.offthreadvideo_threads_spin.value() != 1:
            args.extend(['--offthreadvideo-video-threads', str(self.offthreadvideo_threads_spin.value())])
        if self.enable_multiprocess_checkbox.isChecked():
            args.append('--enable-multiprocess-on-linux')
        if self.repro_checkbox.isChecked():
            args.append('--repro')
        if self.binaries_dir_edit.text():
            args.extend(['--binaries-directory', self.binaries_dir_edit.text()])
        if self.experimental_rspack_checkbox.isChecked():
            args.append('--experimental-rspack')
        if self.metadata_edit.toPlainText():
            args.extend(['--metadata', self.metadata_edit.toPlainText()])
        if self.color_space_combo.currentText() != 'default':
            args.extend(['--color-space', self.color_space_combo.currentText()])
        if self.image_sequence_pattern_edit.text():
            args.extend(['--image-sequence-pattern', self.image_sequence_pattern_edit.text()])
        if not self.overwrite_checkbox.isChecked():
            args.append('--overwrite=false')
        return args
