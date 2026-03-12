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
    QListWidgetItem, QFileDialog, QSizePolicy, QMessageBox, QLineEdit, QApplication, QSpinBox, QMenu, QCheckBox, QTabWidget
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize
from PIL import Image
import itertools
from PySide6.QtGui import QIcon, QFont, QPainter, QColor, QPalette
import qtawesome as qta
import traceback

from ui.theme_system import theme

class FileDropListWidget(QListWidget):
    files_dropped = Signal(list)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = []
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    paths.append(url.toLocalFile())
            if paths:
                self.files_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.count() == 0:
            painter = QPainter(self.viewport())
            painter.save()
            painter.setPen(QColor(120, 120, 120))
            vp = self.viewport()
            cx = vp.width() // 2
            cy = vp.height() // 2
            icon_pix = qta.icon('fa6s.file-arrow-up', color=theme.get_color('text_dark')).pixmap(36, 36)
            painter.drawPixmap(cx - 18, cy - 36, icon_pix)
            font = painter.font()
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(0, cy + 8, vp.width(), 20, Qt.AlignCenter, "Drag and drop files here")
            painter.restore()

from config import BASE_PATH
from database.db_operation import ImageTeaDB
from dialogs.tools.upscaler_model_manager_dialog import UpscalerModelManager, UpscalerModelManagerDialog
from tools.tools_checker import is_vulkan_available


def get_realesrgan_path():
    system = platform.system()
    bin_name = "realesrgan-ncnn-vulkan.exe" if system == "Windows" else "realesrgan-ncnn-vulkan"
    return Path(BASE_PATH) / "tools" / "realesrgan" / bin_name


def get_waifu2x_path():
    system = platform.system()
    bin_name = "waifu2x-ncnn-vulkan.exe" if system == "Windows" else "waifu2x-ncnn-vulkan"
    return Path(BASE_PATH) / "tools" / "waifu2x" / bin_name


def get_models_dir():
    return Path(BASE_PATH) / "tools" / "realesrgan" / "models"


TEMP_DIR = Path(BASE_PATH) / "temp" / "image_upscaler"
BATCH_INPUT_DIR = TEMP_DIR / "batch_input"
BATCH_OUTPUT_DIR = TEMP_DIR / "batch_output"
RESULTS_DIR = TEMP_DIR / "results"
CONFIG_FILE = Path(BASE_PATH) / "configs" / "image_upscale_config.json"
HW_CAP_MARKER = Path(BASE_PATH) / "temp" / ".hw_cap_tested"


class ImageUpscaleWorker(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int)
    stats_signal = Signal(int, int, float, int, float)
    finished_signal = Signal(bool, str)
    image_completed_signal = Signal(str, bool)

    def __init__(self, image_paths: List[str], model: str, scale: int, batch_size: int = 10,
                 output_format: str = "png", output_dir: str = None, tint_adjustment: tuple = (0, 0, 0),
                 resolution_preset: str = "Original (use Scale factor)", gpu_id: int = -2):
        super().__init__()
        self.image_paths = image_paths
        self.model = model
        self.scale = scale
        self.batch_size = batch_size
        self.output_format = output_format.lower()
        self.output_dir = output_dir
        self.tint_adjustment = tint_adjustment
        self.resolution_preset = resolution_preset
        self.gpu_id = gpu_id
        self._stop_requested = False
        
        self.realesrgan_bin = get_realesrgan_path()
        self.waifu2x_bin = get_waifu2x_path()
        self.models_dir = get_models_dir()
        
        from dialogs.tools.upscaler_model_manager_dialog import UpscalerModelManager
        self.model_manager = UpscalerModelManager()
        model_info = self.model_manager.get_model_by_name(model)
        self.model_type = model_info['type'] if model_info else 'ncnn'
        self.model_info = model_info
        self.target_crop_size = None

    def stop(self):
        self._stop_requested = True

    def _apply_preset_crop(self, img_arr):
        if self.target_crop_size is None:
            return img_arr
        import cv2
        target_w, target_h = self.target_crop_size
        h, w = img_arr.shape[:2]
        scale_w = target_w / w
        scale_h = target_h / h
        fill_scale = max(scale_w, scale_h)
        if abs(fill_scale - 1.0) > 0.001:
            new_w = max(target_w, round(w * fill_scale))
            new_h = max(target_h, round(h * fill_scale))
            img_arr = cv2.resize(img_arr, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
            h, w = img_arr.shape[:2]
        x = (w - target_w) // 2
        y = (h - target_h) // 2
        return img_arr[y:y + target_h, x:x + target_w]

    def _preflight_waifu2x(self) -> bool:
        if not self.waifu2x_bin.exists():
            self.log_signal.emit(f"❌ Waifu2x executable missing: {self.waifu2x_bin}")
            print(f"System Error: Waifu2x executable missing at {self.waifu2x_bin}")
            return False
        if platform.system() != 'Windows' and not os.access(self.waifu2x_bin, os.X_OK):
            try:
                st = os.stat(self.waifu2x_bin).st_mode
                os.chmod(self.waifu2x_bin, st | 0o755)
            except Exception as e:
                print(f"System Error: Cannot set executable bit on {self.waifu2x_bin}: {e}")
                self.log_signal.emit(f"❌ OS error: permission issue on {self.waifu2x_bin}")
                return False
            if not os.access(self.waifu2x_bin, os.X_OK):
                self.log_signal.emit(f"❌ OS error: permission denied: {self.waifu2x_bin}")
                return False
        return True

    def _preflight_realesrgan(self) -> bool:
        if not self.realesrgan_bin.exists():
            self.log_signal.emit(f"❌ RealESRGAN executable missing: {self.realesrgan_bin}")
            print(f"System Error: RealESRGAN executable missing at {self.realesrgan_bin}")
            return False
        if platform.system() != 'Windows' and not os.access(self.realesrgan_bin, os.X_OK):
            print(f"System Notice: RealESRGAN binary not executable, attempting to set +x: {self.realesrgan_bin}")
            try:
                st = os.stat(self.realesrgan_bin).st_mode
                os.chmod(self.realesrgan_bin, st | 0o755)
                print(f"Set executable bit on {self.realesrgan_bin}")
            except Exception as e:
                print(f"System Error: Cannot set executable bit on {self.realesrgan_bin}: {e}")
                self.log_signal.emit(f"❌ OS error launching RealESRGAN: permission issue on {self.realesrgan_bin}")
                return False
            if not os.access(self.realesrgan_bin, os.X_OK):
                print(f"System Error: RealESRGAN not executable after chmod: {self.realesrgan_bin}")
                self.log_signal.emit(f"❌ OS error launching RealESRGAN: permission denied: {self.realesrgan_bin}")
                return False
        # Check Vulkan availability deterministically on non-Windows
        if platform.system() != 'Windows':
            if not is_vulkan_available():
                msg = ("Vulkan not available or not configured correctly on this system. "
                       "RealESRGAN requires Vulkan GPU drivers (or proper MoltenVK on macOS).")
                print(f"System Error: {msg}")
                self.log_signal.emit(f"❌ System Error: {msg}")
                return False
        return True
    
    def _init_upscaler_backend(self):
        if self.model_type == 'ncnn':
            return None
        elif self.model_type == 'pth':
            try:
                import torch
                
                device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                use_half = device.type != 'cpu'
                tile_size = 128 if device.type == 'cpu' else 256
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
                        tile=tile_size,
                        tile_pad=10,
                        pre_pad=0,
                        half=use_half,
                        device=device
                    )
                    precision_label = "FP16" if use_half else "FP32"
                    self.log_signal.emit(f"✅ PyTorch backend initialized via RealESRGANer (Device: {device}, Precision: {precision_label}, Tile: {tile_size})")
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
                import onnxruntime as ort
                sess_opts = ort.SessionOptions()
                sess_opts.intra_op_num_threads = max(1, (__import__('os').cpu_count() or 2))
                sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                session = ort.InferenceSession(model_path, sess_options=sess_opts, providers=providers)
                
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

    def _normalize_and_save_image(self, img_arr, output_path: str, ref_path: str | None = None) -> bool:
        if not isinstance(img_arr, np.ndarray):
            print(f"ERROR: Upscaler produced non-numpy output for {output_path}")
            self.log_signal.emit(f"❌ Upscaler produced invalid output for {os.path.basename(output_path)}")
            return False

        arr = img_arr
        if arr.ndim == 2:
            arr = np.stack([arr, arr, arr], axis=-1)
            self.log_signal.emit(f"ℹ️ Converted single-channel output for {os.path.basename(output_path)}")
        if arr.ndim == 3 and arr.shape[2] == 4:
            arr = arr[:, :, :3]
            self.log_signal.emit(f"ℹ️ Dropped alpha channel for {os.path.basename(output_path)}")

        if np.issubdtype(arr.dtype, np.floating):
            arr_u8 = np.clip(arr * 255.0, 0, 255).round().astype(np.uint8)
        else:
            arr_u8 = np.clip(arr, 0, 255).astype(np.uint8)

        r_adj, g_adj, b_adj = self.tint_adjustment
        if r_adj != 0 or g_adj != 0 or b_adj != 0:
            arr_float = arr_u8.astype(np.float32)
            arr_float[:, :, 0] += b_adj
            arr_float[:, :, 1] += g_adj
            arr_float[:, :, 2] += r_adj
            arr_u8 = np.clip(arr_float, 0, 255).astype(np.uint8)

        arr_u8 = self._apply_preset_crop(arr_u8)

        if self.output_format == 'png':
            ok = cv2.imwrite(output_path, arr_u8, [cv2.IMWRITE_PNG_COMPRESSION, 0])
        elif self.output_format in ['jpg', 'jpeg']:
            ok = cv2.imwrite(output_path, arr_u8, [cv2.IMWRITE_JPEG_QUALITY, 95])
        else:
            ok = cv2.imwrite(output_path, arr_u8)

        if not ok:
            print(f"ERROR: Failed to write image to {output_path}")
            self.log_signal.emit(f"❌ Failed to write image: {os.path.basename(output_path)}")
            return False
        return True

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
                    
                    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=self.scale)
                    model.to(device)
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
                        
                        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        
                        h, w = img.shape[:2]
                        pad_h = (4 - h % 4) % 4
                        pad_w = (4 - w % 4) % 4
                        if pad_h > 0 or pad_w > 0:
                            img = np.pad(img, ((0, pad_h), (0, pad_w), (0, 0)), mode='reflect')
                        
                        img = img.astype(np.float32) / 255.0
                        img = np.transpose(img, (2, 0, 1))
                        img = np.expand_dims(img, axis=0)
                        tensor = torch.from_numpy(img).to(device)
                        if next(model.parameters()).dtype == torch.float16:
                            tensor = tensor.half()
                        output = model(tensor)
                        if isinstance(output, (tuple, list)):
                            output = output[0]
                        output = output.squeeze(0).float().cpu().clamp(0, 1).numpy()
                        output = np.transpose(output, (1, 2, 0))
                        
                        if pad_h > 0 or pad_w > 0:
                            output_h = h * self.scale
                            output_w = w * self.scale
                            output = output[:output_h, :output_w, :]
                        
                        output = (output * 255.0).astype(np.uint8)
                        output = cv2.cvtColor(output, cv2.COLOR_RGB2BGR)
                        
                        return self._normalize_and_save_image(output, output_path)
                except Exception as e:
                    self.log_signal.emit(f"   ❌ PyTorch direct upscale error: {e}")
                    tb = traceback.format_exc()
                    for l in tb.splitlines()[-20:]:
                        self.log_signal.emit(f"      {l}")
                    return False
                
        except Exception as e:
            self.log_signal.emit(f"   ❌ PyTorch upscale error: {e}")
            tb = traceback.format_exc()
            for l in tb.splitlines()[-20:]:
                self.log_signal.emit(f"      {l}")
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

            preset_dims = {
                "HD (1280×720)": (1280, 720),
                "FullHD (1920×1080)": (1920, 1080),
                "2K (2560×1440)": (2560, 1440),
                "4K (3840×2160)": (3840, 2160),
            }
            if self.resolution_preset in preset_dims and self.image_paths:
                target_w, target_h = preset_dims[self.resolution_preset]
                try:
                    import math
                    first_img = Image.open(self.image_paths[0])
                    src_w, src_h = first_img.size
                    first_img.close()
                    is_vertical = src_h > src_w
                    if is_vertical:
                        target_w, target_h = target_h, target_w
                    if src_w > 0 and src_h > 0:
                        orientation = "vertical" if is_vertical else "horizontal"
                        self.log_signal.emit(f"   📐 Preset '{self.resolution_preset}' [{orientation}] {src_w}x{src_h} → post-process output to {target_w}x{target_h}")
                    self.target_crop_size = (target_w, target_h)
                except Exception as e:
                    print(f"Resolution preset scale calc error: {e}")

            self.log_signal.emit(f"   🧩 Model: {self.model} (Type: {self.model_type.upper()}) | Scale: {self.scale}x | Batch: {self.batch_size}")
            self.log_signal.emit(f"   📁 Output format: {self.output_format.upper()}")
            self.log_signal.emit("")
            
            if self.model_type == 'waifu2x':
                if not self._preflight_waifu2x():
                    self.finished_signal.emit(False, "❌ Waifu2x executable not available")
                    return
                
                waifu2x_models_subdir = self.model_info.get('models_dir', '') if self.model_info else ''
                noise = self.model_info.get('noise_level', 3) if self.model_info else 3
                
                self.log_signal.emit(f"   Using Waifu2x-NCNN-Vulkan backend")
                self.log_signal.emit("")
                
                BATCH_INPUT_DIR.mkdir(parents=True, exist_ok=True)
                BATCH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                RESULTS_DIR.mkdir(parents=True, exist_ok=True)
                
                num_batches = (total_images + self.batch_size - 1) // self.batch_size
                start_time = time.time()
                processed = 0
                
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
                        str(self.waifu2x_bin),
                        "-i", str(BATCH_INPUT_DIR),
                        "-o", str(BATCH_OUTPUT_DIR),
                        "-n", str(noise),
                        "-s", str(self.scale),
                        "-f", self.output_format,
                    ]
                    if waifu2x_models_subdir:
                        cmd += ["-m", waifu2x_models_subdir]
                    if self.gpu_id != -2:
                        cmd += ["-g", str(self.gpu_id)]
                    
                    startupinfo = None
                    creationflags = 0
                    if platform.system() == "Windows":
                        try:
                            si = subprocess.STARTUPINFO()
                            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                            si.wShowWindow = subprocess.SW_HIDE
                            startupinfo = si
                            creationflags = subprocess.CREATE_NO_WINDOW
                        except Exception:
                            pass
                    
                    try:
                        proc = subprocess.Popen(
                            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, cwd=str(self.waifu2x_bin.parent),
                            startupinfo=startupinfo, creationflags=creationflags
                        )
                    except (FileNotFoundError, OSError) as e:
                        self.log_signal.emit(f"❌ Error launching Waifu2x: {e}")
                        self.finished_signal.emit(False, f"❌ Error launching Waifu2x: {e}")
                        return
                    
                    last_stdout = []
                    for line in proc.stdout:
                        if self._stop_requested:
                            proc.terminate()
                            self.finished_signal.emit(False, "⚠️ Process stopped by user")
                            return
                        ll = line.strip()
                        if ll:
                            last_stdout.append(ll)
                    proc.wait()
                    
                    if proc.returncode != 0:
                        self.log_signal.emit(f"❌ Waifu2x failed on batch {batch_num} (code={proc.returncode})")
                        for ln in last_stdout[-20:]:
                            self.log_signal.emit(f"   {ln}")
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
                            waifu_img = cv2.imread(str(out_file), cv2.IMREAD_UNCHANGED)
                            if waifu_img is not None:
                                ok = self._normalize_and_save_image(waifu_img, str(final_path), original_path)
                                if not ok:
                                    shutil.copy2(out_file, final_path)
                            else:
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
                    eta = (elapsed / processed) * remaining if processed > 0 else 0.0
                    self.progress_signal.emit(min(100, int((processed / total_images) * 100)))
                    self.stats_signal.emit(processed, total_images, elapsed, remaining, float(eta))
                
                self.progress_signal.emit(100)
                elapsed = time.time() - start_time
                self.log_signal.emit("")
                self.log_signal.emit(f"{'='*60}")
                if overall_success:
                    self.finished_signal.emit(True, f"✅ All {total_images} images upscaled (Waifu2x) in {elapsed:.2f}s!")
                elif succeeded == 0:
                    self.finished_signal.emit(False, "❌ All images failed; see logs for details")
                else:
                    self.finished_signal.emit(False, f"⚠️ Completed {succeeded}/{total_images} images in {elapsed:.2f}s; some failed.")
                return
            
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
            if re.search(r"x([1-8])", model_to_use, re.IGNORECASE):
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
                    "-t", "128",
                    "-j", "1:2:2",
                    "-f", self.output_format,
                ]
                if self.gpu_id != -2:
                    cmd += ["-g", str(self.gpu_id)]
                
                startupinfo = None
                creationflags = 0
                if platform.system() == "Windows":
                    try:
                        si = subprocess.STARTUPINFO()
                        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        si.wShowWindow = subprocess.SW_HIDE
                        startupinfo = si
                        creationflags = subprocess.CREATE_NO_WINDOW
                    except Exception:
                        startupinfo = None
                # Preflight permission check
                if not self._preflight_realesrgan():
                    self.finished_signal.emit(False, f"❌ Error launching RealESRGAN: permission or missing binary: {self.realesrgan_bin}")
                    return

                try:
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            text=True, cwd=str(self.realesrgan_bin.parent), startupinfo=startupinfo, creationflags=creationflags)
                except FileNotFoundError as e:
                    print(f"System Error: RealESRGAN executable not found: {e} - {self.realesrgan_bin}")
                    self.log_signal.emit(f"❌ Error launching RealESRGAN: {e} (executable not found)")
                    self.log_signal.emit(f"   Executable: {self.realesrgan_bin}")
                    self.log_signal.emit(f"   Working dir: {self.realesrgan_bin.parent}")
                    self.log_signal.emit(f"   Command: {cmd}")
                    self.finished_signal.emit(False, f"❌ Error launching RealESRGAN: executable not found: {self.realesrgan_bin}")
                    return
                except OSError as e:
                    print(f"System Error launching RealESRGAN: {e} - Executable: {self.realesrgan_bin}")
                    self.log_signal.emit(f"❌ OS error launching RealESRGAN: {e}")
                    self.log_signal.emit(f"   Executable: {self.realesrgan_bin}")
                    self.log_signal.emit(f"   Working dir: {self.realesrgan_bin.parent}")
                    self.log_signal.emit(f"   Command: {cmd}")
                    self.finished_signal.emit(False, f"❌ Error launching RealESRGAN: {e}")
                    return

                last_stdout = []
                for line in proc.stdout:
                    if self._stop_requested:
                        proc.terminate()
                        self.finished_signal.emit(False, "⚠️ Process stopped by user")
                        return
                    ll = line.strip()
                    if not ll:
                        continue
                    last_stdout.append(ll)
                    low = ll.lower()
                    if 'fail' in low or 'error' in low:
                        self.log_signal.emit(f"   ❗ ERROR: {ll}")
                
                proc.wait()
                
                # If the process failed, emit helpful diagnostics (return code + last lines)
                if proc.returncode != 0:
                    self.log_signal.emit(f"❌ RealESRGAN failed on batch {batch_num} (returncode={proc.returncode})")
                    if last_stdout:
                        tail = last_stdout[-50:]
                        self.log_signal.emit("   🔎 Recent RealESRGAN output:")
                        combined = "\n".join(tail).lower()
                        for l in tail:
                            self.log_signal.emit(f"      {l}")

                        # Detect Vulkan/driver specific failure signatures to give clearer system guidance
                        if 'llvmpipe' in combined or 'llvm error' in combined or 'cannot select' in combined or 'fild' in combined:
                            hint = ("System Error: Vulkan/driver failure detected in RealESRGAN output (llvmpipe/LLVM). "
                                    "This indicates the system's Vulkan runtime or GPU drivers are missing or incompatible.")
                            print(hint)
                            self.log_signal.emit(f"   ❗ {hint}")
                    else:
                        self.log_signal.emit("   🔎 No RealESRGAN stdout captured")

                    # show files present in output folder to help debugging
                    outputs = sorted([p.name for p in BATCH_OUTPUT_DIR.glob("*")]) if BATCH_OUTPUT_DIR.exists() else []
                    if outputs:
                        self.log_signal.emit(f"   ℹ️ BATCH_OUTPUT_DIR contains: {', '.join(outputs[:20])}{'...' if len(outputs)>20 else ''}")
                    else:
                        self.log_signal.emit("   ℹ️ BATCH_OUTPUT_DIR is empty")

                    for img_path in batch_images:
                        self.image_completed_signal.emit(img_path, False)
                    overall_success = False
                    processed = end_idx
                    continue

                # If process succeeded but no outputs produced, show recent output to help debugging
                produced_files = list(BATCH_OUTPUT_DIR.glob(f"*.{self.output_format}"))
                if not produced_files:
                    self.log_signal.emit(f"❌ RealESRGAN finished but produced no outputs for batch {batch_num}")
                    if last_stdout:
                        tail = last_stdout[-50:]
                        self.log_signal.emit("   🔎 Recent RealESRGAN output:")
                        for l in tail:
                            self.log_signal.emit(f"      {l}")
                    outputs = sorted([p.name for p in BATCH_OUTPUT_DIR.glob("*")]) if BATCH_OUTPUT_DIR.exists() else []
                    if outputs:
                        self.log_signal.emit(f"   ℹ️ BATCH_OUTPUT_DIR contains: {', '.join(outputs[:20])}{'...' if len(outputs)>20 else ''}")
                    else:
                        self.log_signal.emit("   ℹ️ BATCH_OUTPUT_DIR is empty")

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
                        
                        # Read produced image and attempt deterministic normalization/correction
                        img = cv2.imread(str(out_file), cv2.IMREAD_UNCHANGED)
                        if img is None:
                            print(f"ERROR: Could not read produced file {out_file}")
                            self.log_signal.emit(f"   ❗ Could not read produced file {out_file.name}; copying raw file")
                            shutil.copy2(out_file, final_path)
                            self.image_completed_signal.emit(original_path, True)
                            succeeded += 1
                        else:
                            before_means = img.mean(axis=(0,1)).tolist() if img.ndim==3 else [img.mean()]
                            self.log_signal.emit(f"   ℹ️ Output channel means (BGR): {before_means}")
                            ok = self._normalize_and_save_image(img, str(final_path), str(original_path))
                            if ok:
                                after = cv2.imread(str(final_path), cv2.IMREAD_UNCHANGED)
                                after_means = after.mean(axis=(0,1)).tolist() if after is not None and after.ndim==3 else []
                                print(f"INFO: Normalized {out_file.name} -> {final_path.name}; means {before_means} -> {after_means}")
                                self.log_signal.emit(f"   ✅ {Path(original_path).name} → {final_path.name}")
                                self.image_completed_signal.emit(original_path, True)
                                succeeded += 1
                            else:
                                self.log_signal.emit(f"   ❗ Normalization failed for {out_file.name}; copying raw file")
                                shutil.copy2(out_file, final_path)
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
            self.log_signal.emit(f"   ❌ Exception: {e}")
            tb = traceback.format_exc()
            for l in tb.splitlines()[-40:]:
                self.log_signal.emit(f"      {l}")
            self.finished_signal.emit(False, f"❌ Error: {str(e)}")


class ImageHardwareCapTestWorker(QThread):
    log_signal = Signal(str)
    stage_signal = Signal(str)
    finished_signal = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            test_dir = Path(BASE_PATH) / "temp" / ".hw_cap_test"
            test_dir.mkdir(parents=True, exist_ok=True)

            # Stage 1: Tool binaries
            self.stage_signal.emit("Checking binaries...")
            self.log_signal.emit("[ 1/5 ]  Tool Binaries")
            realesrgan_bin = get_realesrgan_path()
            waifu2x_bin = get_waifu2x_path()
            self.log_signal.emit(f"   RealESRGAN : {realesrgan_bin}")
            realesrgan_exists = realesrgan_bin.exists()
            self.log_signal.emit(f"   {'✅ RealESRGAN found' if realesrgan_exists else '❌ RealESRGAN missing'}")
            self.log_signal.emit(f"   Waifu2x    : {waifu2x_bin}")
            waifu2x_exists = waifu2x_bin.exists()
            self.log_signal.emit(f"   {'✅ Waifu2x found' if waifu2x_exists else '⚠️ Waifu2x not installed'}")

            # Stage 2: GPU probe
            self.stage_signal.emit("Detecting GPU...")
            self.log_signal.emit("[ 2/5 ]  GPU Detection")
            self.log_signal.emit(f"   Probe  : {realesrgan_bin.name} --help")
            gpu_ok = self._detect_gpu()
            self.log_signal.emit(f"   {'✅ GPU probe OK' if gpu_ok else '⚠️ No dedicated GPU found'}")

            # Stage 3: Models
            self.stage_signal.emit("Checking models...")
            self.log_signal.emit("[ 3/5 ]  Model Files")
            models_dir = get_models_dir()
            model_files = list(models_dir.glob("*.param")) if models_dir.exists() else []
            self.log_signal.emit(f"   Models dir : {models_dir}")
            self.log_signal.emit(f"   Found      : {len(model_files)} model(s)")
            models_ok = len(model_files) > 0
            if models_ok:
                for mf in model_files[:5]:
                    self.log_signal.emit(f"   ✅ {mf.stem}")
                if len(model_files) > 5:
                    self.log_signal.emit(f"   ... and {len(model_files) - 5} more")
            else:
                self.log_signal.emit("   ❌ No models found in models directory")

            # Stage 4: RealESRGAN upscale test
            self.stage_signal.emit("Testing RealESRGAN inference...")
            self.log_signal.emit("[ 4/5 ]  RealESRGAN Upscale Test")
            realesrgan_ok = False
            output_size = None
            if realesrgan_exists and models_ok:
                model_name = model_files[0].stem
                self.log_signal.emit(f"   Model  : {model_name}")
                self.log_signal.emit(f"   Input  : 64x64 px blank PNG")
                self.log_signal.emit(f"   Scale  : 2x -> expected 128x128")
                realesrgan_ok, output_size = self._test_realesrgan(test_dir, model_name)
                if realesrgan_ok and output_size:
                    self.log_signal.emit(f"   ✅ Output: {output_size[0]}x{output_size[1]} px")
                    self.log_signal.emit(f"   ✅ Output is readable by PIL")
                else:
                    self.log_signal.emit(f"   ❌ RealESRGAN upscale failed or output invalid")
            else:
                self.log_signal.emit("   ⚠️ Skipped (binary or models missing)")

            # Stage 5: Progressive scale capability
            self.stage_signal.emit("Testing progressive scale...")
            self.log_signal.emit("[ 5/6 ]  Progressive Scale Capability")
            targets = [("HD", 1280, 720), ("Full HD", 1920, 1080), ("2K", 2560, 1440), ("4K", 3840, 2160)]
            if realesrgan_ok and output_size:
                base_w, base_h = 640, 480
                for label, tw, th in targets:
                    needed_scale = max(tw / base_w, th / base_h)
                    passes = needed_scale <= 8
                    self.log_signal.emit(f"   {label} ({tw}x{th}): scale ~{needed_scale:.1f}x -> {'✅ OK' if passes else '⚠️ Requires tiling'}")
            else:
                self.log_signal.emit("   ⚠️ Skipped (upscale test did not pass)")

            # Stage 6: Waifu2x inference test
            self.stage_signal.emit("Testing Waifu2x...")
            self.log_signal.emit("[ 6/6 ]  Waifu2x Upscale Test")
            waifu2x_ok = False
            if waifu2x_exists:
                self.log_signal.emit(f"   Binary : {waifu2x_bin}")
                self.log_signal.emit(f"   Input  : 64x64 px blank PNG")
                self.log_signal.emit(f"   Scale  : 2x -> expected 128x128")
                waifu2x_ok, waifu2x_size = self._test_waifu2x(test_dir)
                if waifu2x_ok and waifu2x_size:
                    self.log_signal.emit(f"   ✅ Output: {waifu2x_size[0]}x{waifu2x_size[1]} px")
                    self.log_signal.emit(f"   ✅ Output is readable by PIL")
                else:
                    self.log_signal.emit(f"   ❌ Waifu2x upscale failed or output invalid")
            else:
                self.log_signal.emit("   ⚠️ Waifu2x not installed, skipped")

            overall_ok = realesrgan_exists and realesrgan_ok and models_ok
            self.log_signal.emit("")
            if overall_ok:
                self.log_signal.emit("✅ Hardware capability test passed")
                HW_CAP_MARKER.parent.mkdir(parents=True, exist_ok=True)
                HW_CAP_MARKER.write_text("ok")
            else:
                self.log_signal.emit("❌ Hardware capability test FAILED, device may be unsupported")
                HW_CAP_MARKER.parent.mkdir(parents=True, exist_ok=True)
                HW_CAP_MARKER.write_text("fail")

            self.finished_signal.emit(overall_ok)
        except Exception as e:
            print(f"ImageHardwareCapTestWorker error: {e}")
            self.log_signal.emit(f"❌ Test error: {e}")
            self.finished_signal.emit(False)

    def _detect_gpu(self) -> bool:
        try:
            realesrgan_bin = get_realesrgan_path()
            if not realesrgan_bin.exists():
                return False
            result = subprocess.run(
                [str(realesrgan_bin), "--help"],
                capture_output=True, text=True, timeout=10,
                cwd=str(realesrgan_bin.parent)
            )
            return result.returncode == 0 or "usage" in (result.stdout + result.stderr).lower()
        except Exception as e:
            print(f"ImageHardwareCapTestWorker._detect_gpu error: {e}")
            return False

    def _test_realesrgan(self, test_dir: Path, model_name: str):
        try:
            realesrgan_bin = get_realesrgan_path()
            models_dir = get_models_dir()
            test_in = test_dir / "test_in.png"
            test_out = test_dir / "test_out.png"
            if test_out.exists():
                test_out.unlink()
            img = np.zeros((64, 64, 3), dtype=np.uint8)
            cv2.imwrite(str(test_in), img)
            cmd = [
                str(realesrgan_bin),
                "-i", str(test_in),
                "-o", str(test_out),
                "-m", str(models_dir),
                "-n", model_name,
                "-s", "2",
                "-f", "png",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                                    cwd=str(realesrgan_bin.parent))
            if result.returncode != 0 or not test_out.exists():
                return False, None
            pil_img = Image.open(str(test_out))
            pil_img.verify()
            pil_img = Image.open(str(test_out))
            return True, pil_img.size
        except Exception as e:
            print(f"ImageHardwareCapTestWorker._test_realesrgan error: {e}")
            return False, None

    def _test_waifu2x(self, test_dir: Path):
        try:
            waifu2x_bin = get_waifu2x_path()
            test_in = test_dir / "test_in.png"
            test_out_w = test_dir / "test_out_waifu2x.png"
            if test_out_w.exists():
                test_out_w.unlink()
            img = np.zeros((64, 64, 3), dtype=np.uint8)
            cv2.imwrite(str(test_in), img)
            cmd = [
                str(waifu2x_bin),
                "-i", str(test_in),
                "-o", str(test_out_w),
                "-s", "2",
                "-f", "png",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                                    cwd=str(waifu2x_bin.parent))
            if result.returncode != 0 or not test_out_w.exists():
                return False, None
            pil_img = Image.open(str(test_out_w))
            pil_img.verify()
            pil_img = Image.open(str(test_out_w))
            return True, pil_img.size
        except Exception as e:
            print(f"ImageHardwareCapTestWorker._test_waifu2x error: {e}")
            return False, None


class ImageUpscalerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Upscaler (RealESRGAN)")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        
        self.db = ImageTeaDB()
        self.worker: Optional[ImageUpscaleWorker] = None
        self.hw_worker: Optional[ImageHardwareCapTestWorker] = None
        self.hw_overlay = None
        self._hw_continue_btn = None
        self._hw_checklist_items = []
        self._hw_current_stage_idx = -1
        self._hw_progress_bar = None
        self._hw_log_view = None
        self._hw_stage_label = None
        self._hw_subtitle_label = None
        self.image_files: List[str] = []
        self.output_dir: Optional[str] = None
        self._last_dir = os.path.expanduser("~")
        self._config_loaded = False
        
        self._remaining_sec = 0.0
        self._remaining_images = 0
        self._elapsed = 0.0
        self._processed = 0
        self._total = 0
        self._success_count = 0
        self._failed_count = 0
        self._failed_files: List[str] = []
        
        self.tint_adjustment = (0, 0, 0)
        
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

        if not HW_CAP_MARKER.exists():
            QTimer.singleShot(500, self._run_hw_cap_test)

    def _run_hw_cap_test(self):
        self._show_hw_overlay()
        self.hw_worker = ImageHardwareCapTestWorker(self)
        self.hw_worker.log_signal.connect(self._hw_overlay_log)
        self.hw_worker.stage_signal.connect(self._hw_overlay_stage)
        self.hw_worker.finished_signal.connect(self._on_hw_test_finished)
        self.hw_worker.start()

    def _rerun_hw_cap_test(self):
        if HW_CAP_MARKER.exists():
            HW_CAP_MARKER.unlink()
        self._run_hw_cap_test()

    def _show_hw_overlay(self):
        win_bg = self.palette().color(QPalette.ColorRole.Window).name()
        bg_light = theme.get_color('background_light')
        text_light = theme.get_color('text_light')
        foreground = theme.get_color('foreground')
        primary = theme.get_color('primary')

        self._hw_checklist_items = []
        self._hw_current_stage_idx = -1

        self.hw_overlay = QWidget(self)
        self.hw_overlay.setObjectName("hw_overlay")
        self.hw_overlay.setStyleSheet(f"#hw_overlay {{ background: {win_bg}; }}")

        outer_layout = QVBoxLayout(self.hw_overlay)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.addStretch()

        h_wrap = QHBoxLayout()
        h_wrap.setContentsMargins(0, 0, 0, 0)
        h_wrap.addStretch()

        card = QWidget()
        card.setObjectName("hw_card")
        card.setFixedWidth(500)
        card.setStyleSheet(
            f"#hw_card {{ background: {win_bg}; border-radius: 0px; border: none; }}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)
        card_layout.setContentsMargins(22, 20, 22, 20)

        title_row = QHBoxLayout()
        title_row.setAlignment(Qt.AlignCenter)
        title_row.setSpacing(8)
        title_icon_lbl = QLabel()
        title_icon_lbl.setStyleSheet("background: transparent;")
        title_icon_lbl.setPixmap(qta.icon('fa6s.microchip', color=primary).pixmap(16, 16))
        title_text = QLabel("Hardware Capability Test")
        title_text.setStyleSheet("font-size: 13px; font-weight: bold; background: transparent;")
        title_row.addWidget(title_icon_lbl)
        title_row.addWidget(title_text)
        card_layout.addLayout(title_row)

        subtitle = QLabel("Testing hardware on first launch, please wait...")
        subtitle.setStyleSheet("font-size: 10px; background: transparent;")
        subtitle.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(subtitle)
        self._hw_subtitle_label = subtitle

        self._hw_progress_bar = QProgressBar()
        self._hw_progress_bar.setRange(0, 100)
        self._hw_progress_bar.setValue(0)
        self._hw_progress_bar.setFixedHeight(4)
        self._hw_progress_bar.setTextVisible(False)
        card_layout.addWidget(self._hw_progress_bar)

        checklist_frame = QWidget()
        checklist_frame.setObjectName("hw_checklist")
        checklist_frame.setStyleSheet(f"#hw_checklist {{ background: {win_bg}; border-radius: 6px; }}")
        checklist_layout = QVBoxLayout(checklist_frame)
        checklist_layout.setSpacing(5)
        checklist_layout.setContentsMargins(12, 8, 12, 8)

        for stage_name in ["Tool Binaries", "GPU Detection", "Model Files", "RealESRGAN Upscale Test", "Progressive Scale Capability", "Waifu2x Upscale Test"]:
            row = QHBoxLayout()
            row.setSpacing(8)
            icon_lbl = QLabel()
            icon_lbl.setFixedSize(16, 16)
            icon_lbl.setStyleSheet("background: transparent;")
            icon_lbl.setPixmap(qta.icon('fa6s.clock', color=theme.get_color('text_dark')).pixmap(13, 13))
            text_lbl = QLabel(stage_name)
            text_lbl.setStyleSheet("font-size: 11px; background: transparent;")
            status_lbl = QLabel("Pending")
            status_lbl.setStyleSheet("font-size: 10px; background: transparent;")
            row.addWidget(icon_lbl)
            row.addWidget(text_lbl, 1)
            row.addWidget(status_lbl)
            checklist_layout.addLayout(row)
            self._hw_checklist_items.append((icon_lbl, text_lbl, status_lbl))

        card_layout.addWidget(checklist_frame)

        self._hw_log_view = QTextEdit()
        self._hw_log_view.setReadOnly(True)
        self._hw_log_view.setStyleSheet(
            f"QTextEdit {{ font-family: Consolas, 'Courier New', monospace; font-size: 10px; "
            f"border-radius: 4px; }}"
        )
        self._hw_log_view.setFixedHeight(140)
        card_layout.addWidget(self._hw_log_view)

        self._hw_stage_label = QLabel("")
        self._hw_stage_label.setStyleSheet(f"color: {primary}; font-size: 11px; font-weight: bold; background: transparent;")
        self._hw_stage_label.setAlignment(Qt.AlignCenter)
        self._hw_stage_label.setVisible(False)
        card_layout.addWidget(self._hw_stage_label)

        self._hw_continue_btn = QPushButton(qta.icon('fa6s.circle-arrow-right', color='white'), " Continue")
        self._hw_continue_btn.setFixedHeight(32)
        self._hw_continue_btn.setMinimumWidth(120)
        self._hw_continue_btn.setStyleSheet(
            f"QPushButton {{ background: {primary}; color: white; border-radius: 5px; font-weight: bold; padding: 0 16px; }}"
            f"QPushButton:hover {{ background: {theme.get_color('primary_hover')}; }}"
        )
        self._hw_continue_btn.setVisible(False)
        card_layout.addWidget(self._hw_continue_btn, alignment=Qt.AlignCenter)

        h_wrap.addWidget(card)
        h_wrap.addStretch()
        outer_layout.addLayout(h_wrap)
        outer_layout.addStretch()

        self.hw_overlay.resize(self.size())
        self.hw_overlay.move(0, 0)
        self.hw_overlay.show()
        self.hw_overlay.raise_()

    def _hw_overlay_log(self, msg: str):
        if self._hw_log_view:
            self._hw_log_view.append(msg)
        if msg.startswith("   "):
            idx = self._hw_current_stage_idx
            if 0 <= idx < len(self._hw_checklist_items):
                icon_lbl, _, status_lbl = self._hw_checklist_items[idx]
                stripped = msg.strip()
                if '\u2705' in stripped:
                    icon_lbl.setPixmap(qta.icon('fa6s.circle-check', color=theme.get_color('success')).pixmap(13, 13))
                    status_lbl.setText("OK")
                    status_lbl.setStyleSheet(f"color: {theme.get_color('success')}; font-size: 10px; background: transparent;")
                elif '\u274c' in stripped:
                    icon_lbl.setPixmap(qta.icon('fa6s.circle-xmark', color=theme.get_color('error')).pixmap(13, 13))
                    status_lbl.setText("FAILED")
                    status_lbl.setStyleSheet(f"color: {theme.get_color('error')}; font-size: 10px; background: transparent;")
                elif '\u26a0' in stripped:
                    icon_lbl.setPixmap(qta.icon('fa6s.triangle-exclamation', color=theme.get_color('warning')).pixmap(13, 13))
                    status_lbl.setText("N/A")
                    status_lbl.setStyleSheet(f"color: {theme.get_color('warning')}; font-size: 10px; background: transparent;")

    def _hw_overlay_stage(self, stage: str):
        self._hw_current_stage_idx += 1
        idx = self._hw_current_stage_idx
        total = len(self._hw_checklist_items)
        primary = theme.get_color('primary')
        if self._hw_progress_bar and total > 0:
            self._hw_progress_bar.setValue(int((idx / total) * 90))
        if 0 <= idx < total:
            icon_lbl, _, status_lbl = self._hw_checklist_items[idx]
            icon_lbl.setPixmap(qta.icon('fa6s.arrows-rotate', color=primary).pixmap(13, 13))
            status_lbl.setText("Running...")
            status_lbl.setStyleSheet(f"color: {primary}; font-size: 10px; background: transparent;")

    def _hide_hw_overlay(self):
        if self.hw_overlay:
            self.hw_overlay.hide()
            self.hw_overlay.deleteLater()
            self.hw_overlay = None
        self._hw_continue_btn = None
        self._hw_checklist_items = []
        self._hw_current_stage_idx = -1
        self._hw_progress_bar = None
        self._hw_log_view = None
        self._hw_stage_label = None
        self._hw_subtitle_label = None

    def _on_hw_test_finished(self, passed: bool):
        if self._hw_progress_bar:
            self._hw_progress_bar.setValue(100)
        if self._hw_subtitle_label:
            self._hw_subtitle_label.setVisible(False)
        if self._hw_stage_label:
            if passed:
                self._hw_stage_label.setText("All tests passed, hardware is fully supported")
                self._hw_stage_label.setStyleSheet(f"color: {theme.get_color('primary')}; font-size: 11px; font-weight: bold; background: transparent;")
            else:
                self._hw_stage_label.setText("Some tests failed. You can still continue, but some features may not work correctly.")
                self._hw_stage_label.setWordWrap(True)
                self._hw_stage_label.setStyleSheet(f"color: {theme.get_color('warning')}; font-size: 11px; font-weight: bold; background: transparent;")
            self._hw_stage_label.setVisible(True)
        if self._hw_continue_btn:
            self._hw_continue_btn.setVisible(True)
            self._hw_continue_btn.clicked.connect(lambda: self._on_hw_continue(passed))

    def _on_hw_continue(self, passed: bool):
        self._hide_hw_overlay()
        if not passed:
            current_title = self.windowTitle()
            if "(UNSUPPORTED)" not in current_title:
                self.setWindowTitle(f"{current_title} (UNSUPPORTED)")
            self.run_button.setEnabled(False)
            self.run_button.setToolTip("This device did not pass the hardware capability test")
            self.log_viewer.append("Hardware capability test FAILED")
            self.log_viewer.append("   Your device may not support GPU-accelerated upscaling.")
            self.log_viewer.append("   The RUN button has been disabled.")
        else:
            self.log_viewer.append("Hardware capability test passed, upscaler ready to use")

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
                    
                    tint_r = config.get('tint_r', 0)
                    self.tint_r_spin.setValue(tint_r)
                    
                    tint_g = config.get('tint_g',0)
                    self.tint_g_spin.setValue(tint_g)
                    
                    tint_b = config.get('tint_b', 0)
                    self.tint_b_spin.setValue(tint_b)

                    res_preset = config.get('resolution_preset', '')
                    if res_preset:
                        idx = self.resolution_preset_combo.findText(res_preset)
                        if idx >= 0:
                            self.resolution_preset_combo.setCurrentIndex(idx)

                    backend = config.get('backend', '')
                    if backend:
                        idx = self.backend_combo.findText(backend)
                        if idx >= 0:
                            self.backend_combo.setCurrentIndex(idx)
        except Exception:
            pass
        finally:
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
            cfg['tint_r'] = self.tint_r_spin.value()
            cfg['tint_g'] = self.tint_g_spin.value()
            cfg['tint_b'] = self.tint_b_spin.value()
            cfg['resolution_preset'] = self.resolution_preset_combo.currentText()
            cfg['backend'] = self.backend_combo.currentText()

            if self.output_dir:
                cfg['output_dir'] = self.output_dir.replace('\\', '/')
            elif getattr(self, '_config_loaded', False):
                if 'output_dir' in cfg:
                    cfg.pop('output_dir', None)
    
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

        self.btn_test_caps = QPushButton(qta.icon('fa6s.microchip'), " Test Capabilities")
        self.btn_test_caps.setToolTip("Re-run hardware capability test")
        self.btn_test_caps.clicked.connect(self._rerun_hw_cap_test)
        toolbar_layout.addWidget(self.btn_test_caps)
        
        toolbar_layout.addStretch()
        main_layout.addLayout(toolbar_layout)

        settings_tabs = QTabWidget()

        tab_model = QWidget()
        tab_model_layout = QVBoxLayout(tab_model)
        tab_model_layout.setSpacing(4)
        tab_model_layout.setContentsMargins(8, 6, 8, 6)

        model_row = QHBoxLayout()
        model_row.setSpacing(4)
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(150)
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        self.model_combo.currentTextChanged.connect(lambda: self._save_config())
        model_row.addWidget(self.model_combo, 1)
        self.btn_model_manager = QPushButton(qta.icon('fa6s.gear'), "")
        self.btn_model_manager.setToolTip("Open Model Manager")
        self.btn_model_manager.clicked.connect(self._open_model_manager)
        model_row.addWidget(self.btn_model_manager)
        tab_model_layout.addLayout(model_row)

        scale_row = QHBoxLayout()
        scale_row.setSpacing(4)
        scale_row.addWidget(QLabel("Scale:"))
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["1", "2", "3", "4", "5", "6", "7", "8"])
        self.scale_combo.setCurrentText("2")
        self.scale_combo.currentTextChanged.connect(lambda: self._save_config())
        scale_row.addWidget(self.scale_combo)
        scale_row.addWidget(QLabel("Batch:"))
        self.batch_combo = QComboBox()
        self.batch_combo.addItems(["5", "10", "15", "20", "25", "30", "35", "40", "45", "50"])
        self.batch_combo.setCurrentText("10")
        self.batch_combo.setToolTip("Images per batch (higher = faster but more VRAM)")
        self.batch_combo.currentTextChanged.connect(lambda: self._save_config())
        scale_row.addWidget(self.batch_combo)
        scale_row.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPG", "WEBP"])
        self.format_combo.setCurrentText("PNG")
        self.format_combo.setToolTip("Output image format")
        self.format_combo.currentTextChanged.connect(lambda: self._save_config())
        scale_row.addWidget(self.format_combo)
        scale_row.addStretch()
        tab_model_layout.addLayout(scale_row)
        tab_model_layout.addStretch()
        settings_tabs.addTab(tab_model, "Model & Scale")

        tab_output = QWidget()
        tab_output_layout = QVBoxLayout(tab_output)
        tab_output_layout.setSpacing(4)
        tab_output_layout.setContentsMargins(8, 6, 8, 6)

        res_row = QHBoxLayout()
        res_row.setSpacing(4)
        res_row.addWidget(QLabel("Resolution:"))
        self.resolution_preset_combo = QComboBox()
        self.resolution_preset_combo.addItems([
            "Original (use Scale factor)",
            "HD (1280×720)",
            "FullHD (1920×1080)",
            "2K (2560×1440)",
            "4K (3840×2160)",
        ])
        self.resolution_preset_combo.setToolTip(
            "Auto-calculate scale to reach the target resolution.\n"
            "Overrides the Scale setting when a preset is selected."
        )
        self.resolution_preset_combo.currentTextChanged.connect(lambda: self._save_config())
        res_row.addWidget(self.resolution_preset_combo, 1)
        tab_output_layout.addLayout(res_row)

        backend_row = QHBoxLayout()
        backend_row.setSpacing(4)
        backend_row.addWidget(QLabel("Backend:"))
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["Auto (GPU)", "GPU (Force)", "CPU (Force)"])
        self.backend_combo.setToolTip(
            "Auto (GPU): Let the binary choose automatically.\n"
            "GPU (Force): Pass -g 0 to ncnn binaries.\n"
            "CPU (Force): Pass -g -1 to ncnn binaries (slow but compatible)."
        )
        self.backend_combo.currentTextChanged.connect(lambda: self._save_config())
        backend_row.addWidget(self.backend_combo, 1)
        tab_output_layout.addLayout(backend_row)
        tab_output_layout.addStretch()
        settings_tabs.addTab(tab_output, "Output")

        tab_adj = QWidget()
        tab_adj_layout = QVBoxLayout(tab_adj)
        tab_adj_layout.setSpacing(4)
        tab_adj_layout.setContentsMargins(8, 6, 8, 6)

        tint_row = QHBoxLayout()
        tint_row.setSpacing(4)
        tint_row.addWidget(QLabel("Tint R:"))
        self.tint_r_spin = QSpinBox()
        self.tint_r_spin.setRange(-50, 50)
        self.tint_r_spin.setValue(2)
        self.tint_r_spin.setToolTip("Red channel adjustment (-50 to +50)")
        self.tint_r_spin.valueChanged.connect(self._on_tint_changed)
        tint_row.addWidget(self.tint_r_spin)
        tint_row.addWidget(QLabel("G:"))
        self.tint_g_spin = QSpinBox()
        self.tint_g_spin.setRange(-50, 50)
        self.tint_g_spin.setValue(-5)
        self.tint_g_spin.setToolTip("Green channel adjustment (-50 to +50)")
        self.tint_g_spin.valueChanged.connect(self._on_tint_changed)
        tint_row.addWidget(self.tint_g_spin)
        tint_row.addWidget(QLabel("B:"))
        self.tint_b_spin = QSpinBox()
        self.tint_b_spin.setRange(-50, 50)
        self.tint_b_spin.setValue(0)
        self.tint_b_spin.setToolTip("Blue channel adjustment (-50 to +50)")
        self.tint_b_spin.valueChanged.connect(self._on_tint_changed)
        tint_row.addWidget(self.tint_b_spin)
        tint_row.addStretch()
        tab_adj_layout.addLayout(tint_row)

        self.retry_failed_checkbox = QCheckBox("Retry Failed Only")
        self.retry_failed_checkbox.setToolTip("Only process images that failed in previous run")
        tab_adj_layout.addWidget(self.retry_failed_checkbox)
        tab_adj_layout.addStretch()
        settings_tabs.addTab(tab_adj, "Adjustments")

        main_layout.addWidget(settings_tabs)
        
        splitter = QSplitter(Qt.Horizontal)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        
        left_layout.addWidget(QLabel("Loaded Images:"))
        self.image_list = FileDropListWidget()
        self.image_list.setMinimumWidth(300)
        self.image_list.files_dropped.connect(self._on_image_files_dropped)
        self.image_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.image_list.customContextMenuRequested.connect(self._show_image_context_menu)
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
        
        output_layout = QHBoxLayout()
        output_layout.setSpacing(8)
        
        output_layout.addWidget(QLabel("Output:"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Default: temp/image_upscaler/results")
        self.output_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.output_edit.setMinimumWidth(0)
        self.output_edit.textChanged.connect(self._on_output_text_changed)
        self.output_edit.editingFinished.connect(self._save_config)
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
        
        self.success_label = QLabel("Success: 0")
        self.success_label.setStyleSheet("font-weight: bold; color: green;")
        stats_layout.addWidget(self.success_label)
        
        self.failed_label = QLabel("Failed: 0")
        self.failed_label.setStyleSheet("font-weight: bold; color: red;")
        stats_layout.addWidget(self.failed_label)
        
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
        self.run_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.get_color('primary')};
                color: {theme.get_color('white')};
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {theme.get_color('primary_hover')};
            }}
            QPushButton:pressed {{
                background-color: {theme.get_color('primary_pressed')};
            }}
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
                print(f"WARNING - {msg}")
            self.log_viewer.append("")
        else:
            pass

    def _preflight_realesrgan(self):
        # Deterministic permission checks before launching RealESRGAN
        if not self.realesrgan_bin.exists():
            self.log_signal.emit(f"❌ RealESRGAN executable missing: {self.realesrgan_bin}")
            print(f"System Error: RealESRGAN executable missing at {self.realesrgan_bin}")
            return False
        if platform.system() != 'Windows' and not os.access(self.realesrgan_bin, os.X_OK):
            print(f"System Notice: RealESRGAN binary not executable, attempting to set +x: {self.realesrgan_bin}")
            try:
                st = os.stat(self.realesrgan_bin).st_mode
                os.chmod(self.realesrgan_bin, st | 0o755)
                print(f"Set executable bit on {self.realesrgan_bin}")
            except Exception as e:
                print(f"System Error: Cannot set executable bit on {self.realesrgan_bin}: {e}")
                self.log_signal.emit(f"❌ OS error launching RealESRGAN: permission issue on {self.realesrgan_bin}")
                return False
            if not os.access(self.realesrgan_bin, os.X_OK):
                print(f"System Error: RealESRGAN not executable after chmod: {self.realesrgan_bin}")
                self.log_signal.emit(f"❌ OS error launching RealESRGAN: permission denied: {self.realesrgan_bin}")
                return False
        return True
    
    def _on_model_changed(self, model_name: str):
        m = re.search(r"x([1-8])", model_name, re.IGNORECASE)
        if m:
            s = m.group(1)
            self.scale_combo.setCurrentText(s)
            self.scale_combo.setEnabled(False)
        else:
            self.scale_combo.setEnabled(True)
    
    def _on_tint_changed(self):
        self.tint_adjustment = (self.tint_r_spin.value(), self.tint_g_spin.value(), self.tint_b_spin.value())
        self._save_config()
    
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

    def _on_image_files_dropped(self, paths: list):
        self.add_images(paths)

    def add_images(self, paths: list):
        allowed = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif')
        added = 0
        for p in paths:
            try:
                pp = str(Path(p))
                if not Path(pp).exists():
                    continue
                if not pp.lower().endswith(allowed):
                    continue
                if pp not in self.image_files:
                    self.image_files.append(pp)
                    added += 1
            except Exception:
                continue
        if added:
            self._update_image_list()
            self.log_viewer.append(f"📥 Added {added} image(s) via drag-and-drop")

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
    
    def _show_image_context_menu(self, pos):
        item = self.image_list.itemAt(pos)
        if not item:
            return
        image_path = item.data(Qt.UserRole)
        menu = QMenu(self)
        retry_action = menu.addAction(qta.icon('fa6s.rotate-right'), "Retry This File")
        remove_action = menu.addAction(qta.icon('fa6s.trash'), "Remove from List")
        action = menu.exec(self.image_list.mapToGlobal(pos))
        if action == retry_action:
            self._retry_single_file(image_path)
        elif action == remove_action:
            if image_path in self.image_files:
                self.image_files.remove(image_path)
                self._update_image_list()
                self.log_viewer.append(f"🗑️ Removed: {Path(image_path).name}")
    
    def _retry_single_file(self, image_path: str):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Process Running", "Please wait for current process to finish.")
            return
        if image_path not in self.image_files:
            self.image_files.append(image_path)
            self._update_image_list()
        self._run_process_with_files([image_path])

    def _sanitize_path_text(self, text):
        if not isinstance(text, str):
            return text
        t = text.strip()
        if len(t) >= 2 and ((t[0] == '"' and t[-1] == '"') or (t[0] == "'" and t[-1] == "'")):
            return t[1:-1]
        return t

    def _on_output_text_changed(self, text):
        sanitized = self._sanitize_path_text(text)
        if sanitized != text:
            self.output_edit.blockSignals(True)
            self.output_edit.setText(sanitized)
            self.output_edit.blockSignals(False)
            text = sanitized
        self.output_dir = text.strip() if text.strip() else None

    def browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder", self._last_dir)
        if folder:
            folder = self._sanitize_path_text(folder)
            self._last_dir = folder
            self.output_edit.setText(folder)
            self.output_dir = folder
            self._save_config()

    def paste_output(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        sanitized = self._sanitize_path_text(text)
        if sanitized:
            self.output_edit.setText(sanitized)
            self.output_dir = sanitized
            self._save_config()

    def open_output_folder(self):
        path = self._sanitize_path_text(self.output_edit.text())
        if not path:
            p = RESULTS_DIR
            p.mkdir(parents=True, exist_ok=True)
            self.log_viewer.append(f"ℹ️ No output path specified; opening default: {p}")
        else:
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
        
        if self.retry_failed_checkbox.isChecked():
            if not self._failed_files:
                QMessageBox.information(self, "No Failed Files", "No failed files to retry. Run upscale first or uncheck 'Retry Failed Only'.")
                return
            files_to_process = [f for f in self._failed_files if f in self.image_files]
            if not files_to_process:
                QMessageBox.information(self, "No Failed Files", "Failed files are no longer in the list.")
                return
            self.log_viewer.append(f"🔄 Retrying {len(files_to_process)} failed file(s)...")
        else:
            files_to_process = self.image_files[:]
        
        self._run_process_with_files(files_to_process)
    
    def _run_process_with_files(self, files_to_process: List[str]):
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
        self._success_count = 0
        self._failed_count = 0
        self._failed_files = []
        self._update_stats_label()
        
        model = self.model_combo.currentText()
        scale = int(self.scale_combo.currentText())
        batch_size = int(self.batch_combo.currentText())
        output_format = self.format_combo.currentText().lower()
        output_dir = self.output_edit.text().strip() if self.output_edit.text().strip() else None
        resolution_preset = self.resolution_preset_combo.currentText()
        backend_text = self.backend_combo.currentText()
        if backend_text == "GPU (Force)":
            gpu_id = 0
        elif backend_text == "CPU (Force)":
            gpu_id = -1
        else:
            gpu_id = -2
        
        self.worker = ImageUpscaleWorker(
            files_to_process, model, scale, batch_size, output_format, output_dir, self.tint_adjustment,
            resolution_preset=resolution_preset, gpu_id=gpu_id
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
        self.btn_test_caps.setEnabled(not running)
        self.model_combo.setEnabled(not running)
        self.scale_combo.setEnabled(not running and not self._is_scale_locked())
        self.batch_combo.setEnabled(not running)
        self.format_combo.setEnabled(not running)
        self.resolution_preset_combo.setEnabled(not running)
        self.backend_combo.setEnabled(not running)
        self.output_edit.setEnabled(not running)
        self.btn_browse_output.setEnabled(not running)
        self.btn_paste_output.setEnabled(not running)
        self.btn_open_output.setEnabled(not running)
        self.btn_clear_output.setEnabled(not running)
        
        if running:
            self.run_button.setText(" STOP")
            self.run_button.setIcon(qta.icon('fa6s.stop'))
            self.run_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme.get_color('secondary')};
                    color: {theme.get_color('white')};
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: {theme.get_color('secondary_hover')};
                }}
                QPushButton:pressed {{
                    background-color: {theme.get_color('secondary_pressed')};
                }}
            """)
            self.status_label.setText("Status: Running")
        else:
            self.run_button.setText(" RUN UPSCALE")
            self.run_button.setIcon(qta.icon('fa6s.play'))
            self.run_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme.get_color('primary')};
                    color: {theme.get_color('white')};
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: {theme.get_color('primary_hover')};
                }}
                QPushButton:pressed {{
                    background-color: {theme.get_color('primary_pressed')};
                }}
            """)
            self.status_label.setText("Status: Idle")
    
    def _is_scale_locked(self):
        model_name = self.model_combo.currentText()
        return bool(re.search(r"x([1-8])", model_name, re.IGNORECASE))
    
    def append_log(self, message: str):
        self.log_viewer.append(message)
        try:
            text = self.log_viewer.toPlainText()
            lines = text.splitlines()
            if len(lines) > 200:
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
        self.success_label.setText(f"Success: {self._success_count}")
        self.failed_label.setText(f"Failed: {self._failed_count}")
    
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
        if success:
            self._success_count += 1
            if image_path in self._failed_files:
                self._failed_files.remove(image_path)
        else:
            self._failed_count += 1
            if image_path not in self._failed_files:
                self._failed_files.append(image_path)
        self._update_stats_label()
        for i in range(self.image_list.count()):
            item = self.image_list.item(i)
            if item.data(Qt.UserRole) == image_path:
                if success:
                    item.setIcon(qta.icon('fa6s.circle-check', color=theme.get_color('primary')))
                else:
                    item.setIcon(qta.icon('fa6s.circle-xmark', color=theme.get_color('secondary')))
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
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.hw_overlay and self.hw_overlay.isVisible():
            self.hw_overlay.resize(self.size())
            self.hw_overlay.move(0, 0)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(3000)
        if self.hw_worker and self.hw_worker.isRunning():
            self.hw_worker.terminate()
            self.hw_worker.wait(2000)
        event.accept()
