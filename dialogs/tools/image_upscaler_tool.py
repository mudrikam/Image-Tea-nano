import sys
import os
import subprocess
import shutil
import time
import re
import platform
import json
from pathlib import Path
from typing import Optional, List
import numpy as np
import cv2

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, 
    QPushButton, QComboBox, QProgressBar, QTextEdit, QListWidget, 
    QListWidgetItem, QFileDialog, QSizePolicy, QMessageBox, QLineEdit, QApplication
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize
from PIL import Image
from PySide6.QtGui import QIcon, QFont
import qtawesome as qta

from config import BASE_PATH
from database.db_operation import ImageTeaDB
from dialogs.tools.upscaler_model_manager_dialog import UpscalerModelManager, UpscalerModelManagerDialog


def get_realesrgan_path():
    system = platform.system()
    if system == "Windows":
        return Path(BASE_PATH) / "tools" / "realesrgan" / "realesrgan-ncnn-vulkan.exe"
    else:
        result = subprocess.run(["which", "realesrgan-ncnn-vulkan"], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
        return Path("/usr/bin/realesrgan-ncnn-vulkan")


def get_models_dir():
    system = platform.system()
    if system == "Windows":
        return Path(BASE_PATH) / "tools" / "realesrgan" / "models"
    else:
        home = Path.home()
        possible_paths = [
            Path("/usr/share/realesrgan-ncnn-vulkan/models"),
            home / ".local" / "share" / "realesrgan-ncnn-vulkan" / "models",
            Path(BASE_PATH) / "tools" / "realesrgan" / "models"
        ]
        for p in possible_paths:
            if p.exists():
                return p
        return Path(BASE_PATH) / "tools" / "realesrgan" / "models"


TEMP_DIR = Path(BASE_PATH) / "temp" / "image_upscaler"
BATCH_INPUT_DIR = TEMP_DIR / "batch_input"
BATCH_OUTPUT_DIR = TEMP_DIR / "batch_output"
RESULTS_DIR = TEMP_DIR / "results"
CONFIG_FILE = Path(BASE_PATH) / "configs" / "image_upscale_config.json"


class ImageUpscaleWorker(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int)
    stats_signal = Signal(int, int, float, int, float)
    finished_signal = Signal(bool, str)
    image_completed_signal = Signal(str, bool)

    def __init__(self, image_paths: List[str], model: str, scale: int, batch_size: int = 10,
                 output_format: str = "png", output_dir: str = None):
        super().__init__()
        self.image_paths = image_paths
        self.model = model
        self.scale = scale
        self.batch_size = batch_size
        self.output_format = output_format.lower()
        self.output_dir = output_dir
        self._stop_requested = False
        
        self.realesrgan_bin = get_realesrgan_path()
        self.models_dir = get_models_dir()
        
        from dialogs.tools.upscaler_model_manager_dialog import UpscalerModelManager
        self.model_manager = UpscalerModelManager()
        model_info = self.model_manager.get_model_by_name(model)
        self.model_type = model_info['type'] if model_info else 'ncnn'
        self.model_info = model_info

    def stop(self):
        self._stop_requested = True
    
    def _init_upscaler_backend(self):
        if self.model_type == 'ncnn':
            return None
        elif self.model_type == 'pth':
            try:
                import torch
                
                device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                model_path = self.model_info.get('model_file', '')
                
                if not Path(model_path).exists():
                    self.log_signal.emit(f"❌ Model file not found: {model_path}")
                    return None
                
                try:
                    from realesrgan import RealESRGANer
                    from basicsr.archs.rrdbnet_arch import RRDBNet
                    
                    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=self.scale)
                    upsampler = RealESRGANer(
                        scale=self.scale,
                        model_path=model_path,
                        model=model,
                        tile=0,
                        tile_pad=10,
                        pre_pad=0,
                        half=False,
                        device=device
                    )
                    self.log_signal.emit(f"✅ PyTorch backend initialized via RealESRGANer (Device: {device})")
                    return ('realesrgan', upsampler)
                except ImportError:
                    self.log_signal.emit("   ⚠️ RealESRGANer not available, using direct PyTorch loading...")
                    
                    state_dict = torch.load(model_path, map_location=device, weights_only=False)
                    if 'params_ema' in state_dict:
                        state_dict = state_dict['params_ema']
                    elif 'params' in state_dict:
                        state_dict = state_dict['params']
                    
                    self.log_signal.emit(f"✅ PyTorch model loaded directly (Device: {device})")
                    return ('torch_direct', (state_dict, device))
                    
            except ImportError as e:
                self.log_signal.emit(f"❌ PyTorch not installed: {e}")
                self.log_signal.emit("   Install: pip install torch torchvision")
                return None
            except Exception as e:
                self.log_signal.emit(f"❌ Failed to initialize PyTorch backend: {e}")
                return None
        
        elif self.model_type == 'onnx':
            try:
                import onnxruntime as ort
                
                model_path = self.model_info.get('model_file', '')
                if not Path(model_path).exists():
                    self.log_signal.emit(f"❌ Model file not found: {model_path}")
                    return None
                
                providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
                session = ort.InferenceSession(model_path, providers=providers)
                
                provider_used = session.get_providers()[0]
                self.log_signal.emit(f"✅ ONNX backend initialized (Provider: {provider_used})")
                return session
            except ImportError as e:
                self.log_signal.emit(f"❌ ONNX Runtime missing: {e}")
                self.log_signal.emit("   Install: pip install onnxruntime or onnxruntime-gpu")
                return None
            except Exception as e:
                self.log_signal.emit(f"❌ Failed to initialize ONNX backend: {e}")
                return None
        
        return None
    
    def _upscale_image_pytorch(self, backend_tuple, img_path: str, output_path: str) -> bool:
        try:
            backend_type, backend = backend_tuple
            
            if backend_type == 'realesrgan':
                img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
                if img is None:
                    return False
                
                output, _ = backend.enhance(img, outscale=self.scale)
                
                if self.output_format == 'png':
                    cv2.imwrite(output_path, output, [cv2.IMWRITE_PNG_COMPRESSION, 0])
                elif self.output_format in ['jpg', 'jpeg']:
                    cv2.imwrite(output_path, output, [cv2.IMWRITE_JPEG_QUALITY, 95])
                else:
                    cv2.imwrite(output_path, output)
                
                return True
            
            elif backend_type == 'torch_direct':
                try:
                    state_dict, device = backend
                    import torch
                    from basicsr.archs.rrdbnet_arch import RRDBNet
                    
                    # Build model and load weights
                    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=self.scale)
                    model.to(device)
                    # Normalize state dict keys if needed
                    try:
                        model.load_state_dict(state_dict)
                    except Exception:
                        new_sd = {}
                        for k, v in state_dict.items():
                            nk = k
                            if nk.startswith('module.'):
                                nk = nk[len('module.'):]
                            new_sd[nk] = v
                        model.load_state_dict(new_sd, strict=False)
                    
                    model.eval()
                    with torch.no_grad():
                        img = cv2.imread(img_path, cv2.IMREAD_COLOR)
                        if img is None:
                            return False
                        # Convert BGR to RGB
                        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        img = img.astype(np.float32) / 255.0
                        img = np.transpose(img, (2, 0, 1))
                        img = np.expand_dims(img, axis=0)
                        tensor = torch.from_numpy(img).to(device)
                        # If model params are half precision, convert input
                        if next(model.parameters()).dtype == torch.float16:
                            tensor = tensor.half()
                        output = model(tensor)
                        if isinstance(output, (tuple, list)):
                            output = output[0]
                        output = output.squeeze(0).float().cpu().clamp(0, 1).numpy()
                        output = np.transpose(output, (1, 2, 0))
                        output = (output * 255.0).round().astype(np.uint8)
                        # Convert RGB back to BGR for saving
                        output = cv2.cvtColor(output, cv2.COLOR_RGB2BGR)
                        if self.output_format == 'png':
                            cv2.imwrite(output_path, output, [cv2.IMWRITE_PNG_COMPRESSION, 0])
                        elif self.output_format in ['jpg', 'jpeg']:
                            cv2.imwrite(output_path, output, [cv2.IMWRITE_JPEG_QUALITY, 95])
                        else:
                            cv2.imwrite(output_path, output)
                    return True
                except Exception as e:
                    self.log_signal.emit(f"   ❌ PyTorch direct upscale error: {e}")
                    return False
                
        except Exception as e:
            self.log_signal.emit(f"   ❌ PyTorch upscale error: {e}")
            return False
    
    def _upscale_image_onnx(self, session, img_path: str, output_path: str) -> bool:
        try:
            img = cv2.imread(img_path, cv2.IMREAD_COLOR)
            if img is None:
                return False
            
            img = img.astype(np.float32) / 255.0
            img = np.transpose(img, (2, 0, 1))
            img = np.expand_dims(img, axis=0)
            
            input_name = session.get_inputs()[0].name
            output_name = session.get_outputs()[0].name
            
            expected_type = session.get_inputs()[0].type
            if 'float16' in expected_type:
                img = img.astype(np.float16)
            
            result = session.run([output_name], {input_name: img})[0]
            
            result = np.squeeze(result, axis=0)
            result = np.transpose(result, (1, 2, 0))
            result = np.clip(result * 255.0, 0, 255).astype(np.uint8)
            
            if self.output_format == 'png':
                cv2.imwrite(output_path, result, [cv2.IMWRITE_PNG_COMPRESSION, 0])
            elif self.output_format in ['jpg', 'jpeg']:
                cv2.imwrite(output_path, result, [cv2.IMWRITE_JPEG_QUALITY, 95])
            else:
                cv2.imwrite(output_path, result)
            
            return True
        except Exception as e:
            self.log_signal.emit(f"   ❌ ONNX upscale error: {e}")
            return False

    def run(self):
        try:
            total_images = len(self.image_paths)
            overall_success = True
            succeeded = 0
            
            self.log_signal.emit(f"🚀 Starting image upscale process...")
            self.log_signal.emit(f"   📊 Total images: {total_images}")
            self.log_signal.emit(f"   🧩 Model: {self.model} (Type: {self.model_type.upper()}) | Scale: {self.scale}x | Batch: {self.batch_size}")
            self.log_signal.emit(f"   📁 Output format: {self.output_format.upper()}")
            self.log_signal.emit("")
            
            if self.model_type in ['pth', 'onnx']:
                backend = self._init_upscaler_backend()
                if backend is None:
                    self.finished_signal.emit(False, f"❌ Failed to initialize {self.model_type.upper()} backend")
                    return
                
                self.log_signal.emit(f"   Using {self.model_type.upper()} backend for upscaling")
                self.log_signal.emit("")
                
                RESULTS_DIR.mkdir(parents=True, exist_ok=True)
                start_time = time.time()
                
                for idx, img_path in enumerate(self.image_paths):
                    if self._stop_requested:
                        self.finished_signal.emit(False, "⚠️ Process stopped by user")
                        return
                    
                    self.log_signal.emit(f"Processing {idx+1}/{total_images}: {Path(img_path).name}")
                    
                    original_stem = Path(img_path).stem
                    if self.output_dir:
                        output_path = Path(self.output_dir) / f"{original_stem}_upscaled_{self.scale}x.{self.output_format}"
                    else:
                        output_path = RESULTS_DIR / f"{original_stem}_upscaled_{self.scale}x.{self.output_format}"
                    
                    success = False
                    if self.model_type == 'pth':
                        success = self._upscale_image_pytorch(backend, img_path, str(output_path))
                    elif self.model_type == 'onnx':
                        success = self._upscale_image_onnx(backend, img_path, str(output_path))
                    
                    if success:
                        self.log_signal.emit(f"   ✅ {Path(img_path).name} → {output_path.name}")
                        self.image_completed_signal.emit(img_path, True)
                        succeeded += 1
                    else:
                        self.log_signal.emit(f"   ❌ Failed: {Path(img_path).name}")
                        self.image_completed_signal.emit(img_path, False)
                        overall_success = False
                    
                    processed = idx + 1
                    elapsed = time.time() - start_time
                    remaining = max(0, total_images - processed)
                    eta = 0.0
                    if processed > 0:
                        rate = elapsed / processed
                        eta = rate * remaining
                        progress_pct = int((processed / total_images) * 100)
                        self.progress_signal.emit(min(100, progress_pct))
                    
                    self.stats_signal.emit(processed, total_images, elapsed, remaining, float(eta))
                
                self.progress_signal.emit(100)
                elapsed = time.time() - start_time
                
                self.log_signal.emit("")
                self.log_signal.emit(f"{'='*60}")
                
                if overall_success:
                    self.finished_signal.emit(True, f"✅ All {total_images} images upscaled successfully in {elapsed:.2f}s!")
                elif succeeded == 0:
                    self.finished_signal.emit(False, "❌ All images failed; see logs for details")
                else:
                    self.finished_signal.emit(False, f"⚠️ Completed {succeeded}/{total_images} images in {elapsed:.2f}s; some failed.")
                
                return
            
            BATCH_INPUT_DIR.mkdir(parents=True, exist_ok=True)
            BATCH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            
            num_batches = (total_images + self.batch_size - 1) // self.batch_size
            self.log_signal.emit(f"   🔁 Processing {num_batches} batches with NCNN backend")
            self.log_signal.emit("")
            
            start_time = time.time()
            processed = 0
            
            model_to_use = self.model
            if re.search(r"x([234])", model_to_use, re.IGNORECASE):
                self.log_signal.emit(f"   Using model {model_to_use} (contains scale)")
            else:
                candidate = f"{model_to_use}-x{self.scale}"
                if (self.models_dir / f"{candidate}.param").exists():
                    self.log_signal.emit(f"   🔧 Using model {candidate} for scale {self.scale}x")
                    model_to_use = candidate
                else:
                    found = None
                    for p in self.models_dir.glob("*.param"):
                        stem = p.stem
                        if model_to_use in stem and f"x{self.scale}" in stem:
                            found = stem
                            break
                    if found:
                        self.log_signal.emit(f"   🔧 Using model {found} for scale {self.scale}x")
                        model_to_use = found
            
            for batch_idx in range(num_batches):
                if self._stop_requested:
                    self.finished_signal.emit(False, "⚠️ Process stopped by user")
                    return
                
                start_idx = batch_idx * self.batch_size
                end_idx = min(start_idx + self.batch_size, total_images)
                batch_images = self.image_paths[start_idx:end_idx]
                batch_num = batch_idx + 1
                batch_count = len(batch_images)
                
                self.log_signal.emit(f"{'='*60}")
                self.log_signal.emit(f"📦 Batch {batch_num}/{num_batches}: Processing {batch_count} images")
                
                if batch_images:
                    try:
                        first_img = Image.open(batch_images[0])
                        input_width, input_height = first_img.size
                        output_width = input_width * self.scale
                        output_height = input_height * self.scale
                        self.log_signal.emit(f"   📐 Sample size: {input_width}x{input_height} → {output_width}x{output_height}")
                    except Exception:
                        pass
                
                for f in BATCH_INPUT_DIR.glob("*"):
                    f.unlink()
                for f in BATCH_OUTPUT_DIR.glob("*"):
                    f.unlink()
                
                batch_map = {}
                for img_path in batch_images:
                    src = Path(img_path)
                    safe_name = f"{hash(img_path) & 0xFFFFFFFF:08x}{src.suffix}"
                    dst = BATCH_INPUT_DIR / safe_name
                    shutil.copy2(src, dst)
                    batch_map[safe_name] = img_path
                
                cmd = [
                    str(self.realesrgan_bin),
                    "-i", str(BATCH_INPUT_DIR),
                    "-o", str(BATCH_OUTPUT_DIR),
                    "-m", str(self.models_dir),
                    "-n", model_to_use,
                    "-s", str(self.scale),
                    "-t", "0",
                    "-f", self.output_format,
                ]
                
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, cwd=str(self.realesrgan_bin.parent))
                
                for line in proc.stdout:
                    if self._stop_requested:
                        proc.terminate()
                        self.finished_signal.emit(False, "⚠️ Process stopped by user")
                        return
                    ll = line.strip()
                    if not ll:
                        continue
                    low = ll.lower()
                    if 'fail' in low or 'error' in low:
                        self.log_signal.emit(f"   ❗ ERROR: {ll}")
                
                proc.wait()
                
                if proc.returncode != 0:
                    self.log_signal.emit(f"❌ RealESRGAN failed on batch {batch_num}")
                    for img_path in batch_images:
                        self.image_completed_signal.emit(img_path, False)
                    overall_success = False
                    processed = end_idx
                    continue
                
                for safe_name, original_path in batch_map.items():
                    src_stem = Path(safe_name).stem
                    out_file = BATCH_OUTPUT_DIR / f"{src_stem}.{self.output_format}"
                    
                    if out_file.exists():
                        original_stem = Path(original_path).stem
                        if self.output_dir:
                            final_path = Path(self.output_dir) / f"{original_stem}_upscaled_{self.scale}x.{self.output_format}"
                        else:
                            final_path = RESULTS_DIR / f"{original_stem}_upscaled_{self.scale}x.{self.output_format}"
                        
                        shutil.copy2(out_file, final_path)
                        self.log_signal.emit(f"   ✅ {Path(original_path).name} → {final_path.name}")
                        self.image_completed_signal.emit(original_path, True)
                        succeeded += 1
                    else:
                        self.log_signal.emit(f"   ❌ Failed: {Path(original_path).name}")
                        self.image_completed_signal.emit(original_path, False)
                        overall_success = False
                
                processed = end_idx
                elapsed = time.time() - start_time
                remaining = max(0, total_images - processed)
                eta = 0.0
                if processed > 0:
                    rate = elapsed / processed
                    eta = rate * remaining
                    progress_pct = int((processed / total_images) * 100)
                    self.progress_signal.emit(min(100, progress_pct))
                
                self.stats_signal.emit(processed, total_images, elapsed, remaining, float(eta))
            
            for f in BATCH_INPUT_DIR.glob("*"):
                try:
                    f.unlink()
                except Exception:
                    pass
            for f in BATCH_OUTPUT_DIR.glob("*"):
                try:
                    f.unlink()
                except Exception:
                    pass
            
            self.progress_signal.emit(100)
            elapsed = time.time() - start_time
            
            self.log_signal.emit("")
            self.log_signal.emit(f"{'='*60}")
            
            if overall_success:
                self.finished_signal.emit(True, f"✅ All {total_images} images upscaled successfully in {elapsed:.2f}s!")
            elif succeeded == 0:
                self.finished_signal.emit(False, "❌ All images failed; see logs for details")
            else:
                self.finished_signal.emit(False, f"⚠️ Completed {succeeded}/{total_images} images in {elapsed:.2f}s; some failed.")
                
        except Exception as e:
            self.finished_signal.emit(False, f"❌ Error: {str(e)}")


class ImageUpscalerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Upscaler (RealESRGAN)")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        
        self.db = ImageTeaDB()
        self.worker: Optional[ImageUpscaleWorker] = None
        self.image_files: List[str] = []
        self.output_dir: Optional[str] = None
        self._last_dir = os.path.expanduser("~")
        self._config_loaded = False
        
        self._remaining_sec = 0.0
        self._remaining_images = 0
        self._elapsed = 0.0
        self._processed = 0
        self._total = 0
        
        self.model_manager = UpscalerModelManager()
        
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.setup_ui()
        self.populate_models()
        self.check_binaries()
        
        self._rem_timer = QTimer(self)
        self._rem_timer.setInterval(1000)
        self._rem_timer.timeout.connect(self._countdown_tick)
        
        self.resize(900, 600)
        self._load_config()
    
    def _load_config(self):
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    output_dir = config.get('output_dir', '')
                    if output_dir:
                        self.output_edit.setText(output_dir)
                        self.output_dir = output_dir
                    
                    model = config.get('model', '')
                    if model and self.model_combo.findText(model) >= 0:
                        self.model_combo.setCurrentText(model)
                    
                    scale = config.get('scale', '')
                    if scale and self.scale_combo.findText(str(scale)) >= 0:
                        self.scale_combo.setCurrentText(str(scale))
                    
                    batch = config.get('batch', '')
                    if batch and self.batch_combo.findText(str(batch)) >= 0:
                        self.batch_combo.setCurrentText(str(batch))
                    
                    fmt = config.get('format', '')
                    if fmt and self.format_combo.findText(fmt.upper()) >= 0:
                        self.format_combo.setCurrentText(fmt.upper())
        except Exception:
            pass
        finally:
            # mark config loaded so subsequent saves that clear output_dir are considered user intent
            self._config_loaded = True
    
    def _save_config(self):
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            cfg = {}
            if CONFIG_FILE.exists():
                try:
                    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                        cfg = json.load(f)
                except Exception:
                    cfg = {}

            cfg['model'] = self.model_combo.currentText()
            cfg['scale'] = self.scale_combo.currentText()
            cfg['batch'] = self.batch_combo.currentText()
            cfg['format'] = self.format_combo.currentText().lower()

            if self.output_dir:
                cfg['output_dir'] = self.output_dir.replace('\\', '/')
            elif getattr(self, '_config_loaded', False):
                # If config already loaded and output_dir now None, assume user cleared it and remove key
                if 'output_dir' in cfg:
                    cfg.pop('output_dir', None)
            # else: during initial loading/early saves, do not remove existing output_dir

            tmp = CONFIG_FILE.with_suffix('.tmp')
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2)
            tmp.replace(CONFIG_FILE)
        except Exception:
            pass
    
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)
        
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)
        
        self.btn_load_db = QPushButton(qta.icon('fa6s.database'), " Load Database")
        self.btn_load_db.setToolTip("Load image files from the Image-Tea database")
        self.btn_load_db.clicked.connect(self.load_from_database)
        toolbar_layout.addWidget(self.btn_load_db)
        
        self.btn_load_folder = QPushButton(qta.icon('fa6s.folder-open'), " Load Folder")
        self.btn_load_folder.setToolTip("Load all image files from a folder")
        self.btn_load_folder.clicked.connect(self.load_from_folder)
        toolbar_layout.addWidget(self.btn_load_folder)
        
        self.btn_load_file = QPushButton(qta.icon('fa6s.file-image'), " Load File")
        self.btn_load_file.setToolTip("Load a single image file")
        self.btn_load_file.clicked.connect(self.load_single_file)
        toolbar_layout.addWidget(self.btn_load_file)
        
        self.btn_clear = QPushButton(qta.icon('fa6s.trash'), " Clear")
        self.btn_clear.setToolTip("Clear the image list")
        self.btn_clear.clicked.connect(self.clear_images)
        toolbar_layout.addWidget(self.btn_clear)
        
        toolbar_layout.addStretch()
        
        main_layout.addLayout(toolbar_layout)
        
        settings_layout = QHBoxLayout()
        settings_layout.setSpacing(8)
        
        settings_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(180)
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        self.model_combo.currentTextChanged.connect(lambda: self._save_config())
        settings_layout.addWidget(self.model_combo)
        
        self.btn_model_manager = QPushButton(qta.icon('fa6s.gear'), "")
        self.btn_model_manager.setToolTip("Open Model Manager")
        self.btn_model_manager.clicked.connect(self._open_model_manager)
        settings_layout.addWidget(self.btn_model_manager)
        
        settings_layout.addWidget(QLabel("Scale:"))
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["2", "3", "4"])
        self.scale_combo.setCurrentText("2")
        self.scale_combo.currentTextChanged.connect(lambda: self._save_config())
        settings_layout.addWidget(self.scale_combo)
        
        settings_layout.addWidget(QLabel("Batch:"))
        self.batch_combo = QComboBox()
        self.batch_combo.addItems(["5", "10", "15", "20", "25", "30", "35", "40", "45", "50"])
        self.batch_combo.setCurrentText("10")
        self.batch_combo.setToolTip("Images per batch (higher = faster but more VRAM)")
        self.batch_combo.currentTextChanged.connect(lambda: self._save_config())
        settings_layout.addWidget(self.batch_combo)
        
        settings_layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPG", "WEBP"])
        self.format_combo.setCurrentText("PNG")
        self.format_combo.setToolTip("Output image format")
        self.format_combo.currentTextChanged.connect(lambda: self._save_config())
        settings_layout.addWidget(self.format_combo)
        
        settings_layout.addStretch()
        
        main_layout.addLayout(settings_layout)
        
        splitter = QSplitter(Qt.Horizontal)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        
        left_layout.addWidget(QLabel("Loaded Images:"))
        self.image_list = QListWidget()
        self.image_list.setMinimumWidth(300)
        left_layout.addWidget(self.image_list)
        
        left_widget.setLayout(left_layout)
        splitter.addWidget(left_widget)
        
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)
        
        right_layout.addWidget(QLabel("Process Logs:"))
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        right_layout.addWidget(self.log_viewer)
        
        right_widget.setLayout(right_layout)
        splitter.addWidget(right_widget)
        
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 600])
        
        main_layout.addWidget(splitter, 1)
        
        # Output layout - full width above stats
        output_layout = QHBoxLayout()
        output_layout.setSpacing(8)
        
        output_layout.addWidget(QLabel("Output:"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Default: temp/image_upscaler/results")
        # Make output path entry expand full width
        self.output_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.output_edit.setMinimumWidth(0)
        self.output_edit.textChanged.connect(lambda text: setattr(self, 'output_dir', text.strip() if text.strip() else None))
        self.output_edit.editingFinished.connect(self._save_config)
        # Give the QLineEdit stretch so it takes remaining space
        output_layout.addWidget(self.output_edit, 1)
        
        self.btn_browse_output = QPushButton(qta.icon('fa6s.folder'), "")
        self.btn_browse_output.setToolTip("Browse output folder")
        self.btn_browse_output.clicked.connect(self.browse_output)
        output_layout.addWidget(self.btn_browse_output)
        
        self.btn_paste_output = QPushButton(qta.icon('fa6s.paste'), "")
        self.btn_paste_output.setToolTip("Paste output folder path from clipboard")
        self.btn_paste_output.clicked.connect(self.paste_output)
        output_layout.addWidget(self.btn_paste_output)

        self.btn_open_output = QPushButton(qta.icon('fa6s.folder-open'), "")
        self.btn_open_output.setToolTip("Open output folder in file explorer")
        self.btn_open_output.clicked.connect(self.open_output_folder)
        output_layout.addWidget(self.btn_open_output)

        self.btn_clear_output = QPushButton(qta.icon('fa6s.broom'), "")
        self.btn_clear_output.setToolTip("Clear output folder path")
        self.btn_clear_output.clicked.connect(self.clear_output)
        output_layout.addWidget(self.btn_clear_output)
        
        main_layout.addLayout(output_layout)
        
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)
        
        self.files_label = QLabel("Files: 0")
        self.files_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.files_label)
        
        self.elapsed_label = QLabel("Elapsed: 00:00:00")
        self.elapsed_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.elapsed_label)
        
        self.eta_label = QLabel("ETA: --:--:--")
        self.eta_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.eta_label)
        
        self.images_label = QLabel("Images: 0/0")
        self.images_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.images_label)
        
        self.remaining_label = QLabel("Remaining: 0")
        self.remaining_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.remaining_label)
        
        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.status_label)
        
        stats_layout.addStretch()
        
        main_layout.addLayout(stats_layout)
        
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(16)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMaximumHeight(30)
        self.progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        bottom_layout.addWidget(self.progress_bar)
        
        self.run_button = QPushButton(qta.icon('fa6s.play'), " RUN UPSCALE")
        self.run_button.setMinimumHeight(40)
        self.run_button.setMinimumWidth(180)
        self.run_button.clicked.connect(self.run_process)
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #4e9e20;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #3d7307;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        bottom_layout.addWidget(self.run_button)
        
        main_layout.addLayout(bottom_layout)
        
        self.setLayout(main_layout)
    
    def populate_models(self):
        self.model_combo.clear()
        self.model_manager_instance = UpscalerModelManager()
        models = self.model_manager_instance.get_all_models()
        
        if models:
            model_names = [m['name'] for m in models]
            self.model_combo.addItems(model_names)
            ncnn_count = len([m for m in models if m['type'] == 'ncnn'])
            pth_count = len([m for m in models if m['type'] == 'pth'])
            onnx_count = len([m for m in models if m['type'] == 'onnx'])
            self.log_viewer.append(f"✅ Found {len(models)} model(s) (NCNN: {ncnn_count}, PTH: {pth_count}, ONNX: {onnx_count})")
        else:
            defaults = ["realesrgan-x4plus", "realesrgan-x4plus-anime", "realesr-animevideov3"]
            self.model_combo.addItems(defaults)
            self.log_viewer.append(f"⚠️ No model files found; using defaults")
        
        if self.model_combo.count() > 0:
            self._on_model_changed(self.model_combo.currentText())
    
    def _open_model_manager(self):
        dialog = UpscalerModelManagerDialog(self)
        dialog.models_changed.connect(self.populate_models)
        dialog.exec()
    
    def check_binaries(self):
        missing = []
        realesrgan = get_realesrgan_path()
        models_dir = get_models_dir()
        
        if not realesrgan.exists():
            missing.append(f"RealESRGAN not found at: {realesrgan}")
        
        model_files = list(models_dir.glob("*.param")) if models_dir.exists() else []
        if not model_files:
            missing.append(f"Models not found at: {models_dir}")
        
        if missing:
            self.log_viewer.append("⚠️ WARNING - Missing binaries:")
            for msg in missing:
                self.log_viewer.append(f"   {msg}")
            self.log_viewer.append("")
        else:
            self.log_viewer.append("✅ All binaries found")
            self.log_viewer.append(f"   RealESRGAN: {realesrgan}")
            self.log_viewer.append("")
    
    def _on_model_changed(self, model_name: str):
        m = re.search(r"x([234])", model_name, re.IGNORECASE)
        if m:
            s = m.group(1)
            self.scale_combo.setCurrentText(s)
            self.scale_combo.setEnabled(False)
            self.log_viewer.append(f"🔒 Scale auto-set to {s}x from model {model_name}")
        else:
            self.scale_combo.setEnabled(True)
    
    def load_from_database(self):
        images = self.db.get_all_files()
        image_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif')
        image_files = [f[1] for f in images if f[1].lower().endswith(image_extensions)]
        
        if not image_files:
            QMessageBox.information(self, "No Images", "No image files found in the database.")
            return
        
        self.image_files = image_files
        self._update_image_list()
        self.log_viewer.append(f"📂 Loaded {len(image_files)} images from database")
    
    def load_from_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Image Folder", self._last_dir)
        if not folder:
            return
        self._last_dir = folder
        image_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif')
        folder_path = Path(folder)
        image_files = [str(f) for f in folder_path.glob("*") if f.suffix.lower() in image_extensions]
        
        if not image_files:
            QMessageBox.information(self, "No Images", "No image files found in the selected folder.")
            return
        
        self.image_files = image_files
        self._update_image_list()
        self.log_viewer.append(f"📂 Loaded {len(image_files)} images from folder: {folder}")
    
    def load_single_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image File", self._last_dir,
            "Image Files (*.jpg *.jpeg *.png *.webp *.bmp *.tiff *.tif);;All Files (*)"
        )
        if not path:
            return
        self._last_dir = os.path.dirname(path)
        if path not in self.image_files:
            self.image_files.append(path)
        self._update_image_list()
        self.log_viewer.append(f"📁 Added: {path}")
    
    def clear_images(self):
        self.image_files = []
        self._update_image_list()
        self.log_viewer.append("🗑️ Cleared image list")
    
    def _update_image_list(self):
        self.image_list.clear()
        for image_path in self.image_files:
            item = QListWidgetItem(qta.icon('fa6s.file-image'), Path(image_path).name)
            item.setData(Qt.UserRole, image_path)
            item.setToolTip(image_path)
            self.image_list.addItem(item)
        self.files_label.setText(f"Files: {len(self.image_files)}")
    
    def browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder", self._last_dir)
        if folder:
            self._last_dir = folder
            self.output_edit.setText(folder)
            self.output_dir = folder
            self._save_config()
    
    def paste_output(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text().strip()
        if text:
            self.output_edit.setText(text)
            self.output_dir = text
            self._save_config()

    def open_output_folder(self):
        path = self.output_edit.text().strip()
        if not path:
            self.log_viewer.append("⚠️ No output path specified")
            return
        p = Path(path)
        if not p.exists():
            self.log_viewer.append("⚠️ Output folder does not exist")
            return
        try:
            if os.name == 'nt':
                os.startfile(str(p))
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', str(p)])
            else:
                subprocess.Popen(['xdg-open', str(p)])
        except Exception as e:
            self.log_viewer.append(f"⚠️ Failed to open folder: {e}")

    def clear_output(self):
        self.output_edit.clear()
        self.output_dir = None
        self._save_config()
        self.log_viewer.append("🧹 Cleared output path")
    
    def run_process(self):
        if self.worker and self.worker.isRunning():
            self.log_viewer.append("\n⚠️ Stopping process...")
            self.worker.stop()
            self.run_button.setEnabled(False)
            return
        
        if not self.image_files:
            QMessageBox.warning(self, "No Images", "Please load some image files first.")
            return
        
        model_name = self.model_combo.currentText()
        model_info = self.model_manager.get_model_by_name(model_name)
        if model_info:
            model_type = model_info.get('type', 'ncnn')
            if model_type == 'pth':
                from dialogs.tools.upscaler_model_manager_dialog import are_pth_deps_installed, DependencyInstallerDialog
                if not are_pth_deps_installed():
                    reply = QMessageBox.question(
                        self, "PTH Dependencies Required",
                        "PTH models require PyTorch and RealESRGAN packages.\n\n"
                        "Would you like to install them now?\n"
                        "(This may take several minutes)",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply == QMessageBox.Yes:
                        dialog = DependencyInstallerDialog(self, 'pth')
                        dialog.exec()
                        if not are_pth_deps_installed():
                            return
                    else:
                        return
            elif model_type == 'onnx':
                from dialogs.tools.upscaler_model_manager_dialog import are_onnx_deps_installed, DependencyInstallerDialog
                if not are_onnx_deps_installed():
                    reply = QMessageBox.question(
                        self, "ONNX Dependencies Required",
                        "ONNX models require ONNX Runtime package.\n\n"
                        "Would you like to install it now?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply == QMessageBox.Yes:
                        dialog = DependencyInstallerDialog(self, 'onnx')
                        dialog.exec()
                        if not are_onnx_deps_installed():
                            return
                    else:
                        return
        
        self._set_running_state(True)
        
        self.progress_bar.setValue(0)
        self.log_viewer.append("=" * 60)
        
        self._remaining_sec = 0.0
        self._remaining_images = 0
        self._elapsed = 0.0
        self._processed = 0
        self._total = 0
        self._update_stats_label()
        
        model = self.model_combo.currentText()
        scale = int(self.scale_combo.currentText())
        batch_size = int(self.batch_combo.currentText())
        output_format = self.format_combo.currentText().lower()
        output_dir = self.output_edit.text().strip() if self.output_edit.text().strip() else None
        
        self.worker = ImageUpscaleWorker(
            self.image_files, model, scale, batch_size, output_format, output_dir
        )
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.stats_signal.connect(self.update_stats)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.image_completed_signal.connect(self.on_image_completed)
        self.worker.start()
        
        if not self._rem_timer.isActive():
            self._rem_timer.start()
    
    def _set_running_state(self, running: bool):
        self.btn_load_db.setEnabled(not running)
        self.btn_load_folder.setEnabled(not running)
        self.btn_load_file.setEnabled(not running)
        self.btn_clear.setEnabled(not running)
        self.model_combo.setEnabled(not running)
        self.scale_combo.setEnabled(not running and not self._is_scale_locked())
        self.batch_combo.setEnabled(not running)
        self.format_combo.setEnabled(not running)
        self.output_edit.setEnabled(not running)
        self.btn_browse_output.setEnabled(not running)
        self.btn_paste_output.setEnabled(not running)
        self.btn_open_output.setEnabled(not running)
        self.btn_clear_output.setEnabled(not running)
        
        if running:
            self.run_button.setText(" STOP")
            self.run_button.setIcon(qta.icon('fa6s.stop'))
            self.run_button.setStyleSheet("""
                QPushButton {
                    background-color: #cc3333;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #aa2222;
                }
                QPushButton:pressed {
                    background-color: #881111;
                }
            """)
            self.status_label.setText("Status: Running")
        else:
            self.run_button.setText(" RUN UPSCALE")
            self.run_button.setIcon(qta.icon('fa6s.play'))
            self.run_button.setStyleSheet("""
                QPushButton {
                    background-color: #4e9e20;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #3d7307;
                }
                QPushButton:pressed {
                    background-color: #1e7e34;
                }
            """)
            self.status_label.setText("Status: Idle")
    
    def _is_scale_locked(self):
        model_name = self.model_combo.currentText()
        return bool(re.search(r"x([234])", model_name, re.IGNORECASE))
    
    def append_log(self, message: str):
        # Append and keep log size bounded to last 200 lines to avoid huge logs
        self.log_viewer.append(message)
        try:
            text = self.log_viewer.toPlainText()
            lines = text.splitlines()
            if len(lines) > 200:
                # keep only the last 200 lines
                new_text = "\n".join(lines[-200:])
                self.log_viewer.setPlainText(new_text)
        except Exception:
            pass
        self.log_viewer.verticalScrollBar().setValue(
            self.log_viewer.verticalScrollBar().maximum()
        )
    
    def update_stats(self, processed: int, total: int, elapsed: float, remaining: int, remaining_sec: float):
        self._processed = processed
        self._total = total
        self._elapsed = elapsed
        self._remaining_images = remaining
        self._remaining_sec = max(0.0, float(remaining_sec))
        
        if self.worker is not None and self.worker.isRunning() and not self._rem_timer.isActive():
            self._rem_timer.start()
        
        self._update_stats_label()
    
    def _update_stats_label(self):
        elapsed_s = self._fmt_seconds(self._elapsed)
        remaining_time_s = self._fmt_seconds(self._remaining_sec)
        self.elapsed_label.setText(f"Elapsed: {elapsed_s}")
        self.eta_label.setText(f"ETA: {remaining_time_s}")
        self.images_label.setText(f"Images: {self._processed}/{self._total}")
        self.remaining_label.setText(f"Remaining: {self._remaining_images}")
    
    def _fmt_seconds(self, s: float) -> str:
        if s is None or s <= 0:
            return "--:--:--"
        m, sec = divmod(int(s), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{sec:02d}"
    
    def _countdown_tick(self):
        self._elapsed = float(self._elapsed) + 1.0
        if self._remaining_sec > 0:
            self._remaining_sec = max(0.0, self._remaining_sec - 1.0)
        self._update_stats_label()
        
        worker_finished = not (self.worker is not None and self.worker.isRunning())
        if worker_finished and self._remaining_sec <= 0 and self._remaining_images <= 0 and self._rem_timer.isActive():
            self._rem_timer.stop()
    
    def on_image_completed(self, image_path: str, success: bool):
        for i in range(self.image_list.count()):
            item = self.image_list.item(i)
            if item.data(Qt.UserRole) == image_path:
                if success:
                    item.setIcon(qta.icon('fa6s.circle-check', color='#4e9e20'))
                else:
                    item.setIcon(qta.icon('fa6s.circle-xmark', color='#cc3333'))
                break
    
    def on_finished(self, success: bool, message: str):
        self.log_viewer.append("")
        self.log_viewer.append(message)
        self.log_viewer.append("=" * 60)
        
        self._remaining_sec = 0.0
        self._remaining_images = 0
        if self._rem_timer.isActive():
            self._rem_timer.stop()
        self._update_stats_label()
        
        self._set_running_state(False)
        self.run_button.setEnabled(True)
    
    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(3000)
        event.accept()
