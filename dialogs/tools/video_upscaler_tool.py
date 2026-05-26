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
    QListWidgetItem, QFileDialog, QSizePolicy, QMessageBox, QLineEdit, QApplication, QCheckBox, QSpinBox, QMenu, QTabWidget
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize
from PIL import Image
import itertools
from PySide6.QtGui import QIcon, QFont, QPainter, QColor, QPalette, QDragEnterEvent, QDropEvent
import qtawesome as qta
import traceback

from ui.theme_system import theme
from ui.DragDropPathMixin import DragDropPathMixin

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


def get_ffmpeg_path():
    system = platform.system()
    if system == "Windows":
        return Path(BASE_PATH) / "tools" / "ffmpeg" / "ffmpeg.exe"
    else:
        result = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True, check=True)
        return Path(result.stdout.strip())


def get_ffprobe_path():
    system = platform.system()
    if system == "Windows":
        return Path(BASE_PATH) / "tools" / "ffmpeg" / "ffprobe.exe"
    else:
        result = subprocess.run(["which", "ffprobe"], capture_output=True, text=True, check=True)
        return Path(result.stdout.strip())


def get_realesrgan_path():
    system = platform.system()
    bin_name = "realesrgan-ncnn-vulkan.exe" if system == "Windows" else "realesrgan-ncnn-vulkan"
    return Path(BASE_PATH) / "tools" / "realesrgan" / bin_name


def get_waifu2x_path():
    system = platform.system()
    bin_name = "waifu2x-ncnn-vulkan.exe" if system == "Windows" else "waifu2x-ncnn-vulkan"
    return Path(BASE_PATH) / "tools" / "waifu2x" / bin_name


def get_rife_path():
    system = platform.system()
    bin_name = "rife-ncnn-vulkan.exe" if system == "Windows" else "rife-ncnn-vulkan"
    return Path(BASE_PATH) / "tools" / "rife" / bin_name


def get_models_dir():
    return Path(BASE_PATH) / "tools" / "realesrgan" / "models"


TEMP_DIR = Path(BASE_PATH) / "temp" / "video_upscaler"
TMP_FRAMES_DIR = TEMP_DIR / "tmp_frames"
OUT_FRAMES_DIR = TEMP_DIR / "out_frames"
BATCH_INPUT_DIR = TEMP_DIR / "batch_input"
BATCH_OUTPUT_DIR = TEMP_DIR / "batch_output"
RIFE_FRAMES_DIR = TEMP_DIR / "rife_frames"
RESULTS_DIR = TEMP_DIR / "results"
CONFIG_FILE = Path(BASE_PATH) / "configs" / "video_upscale_config.json"


class UpscaleWorker(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int)
    stats_signal = Signal(int, int, float, int, float)
    finished_signal = Signal(bool, str)
    video_completed_signal = Signal(str, bool)

    def __init__(self, video_paths: List[str], model: str, scale: int, batch_size: int = 10, 
                 encoder: str = "CPU", hwaccel: str = "Auto", output_dir: str = None, remove_audio: bool = False,
                 tint_adjustment: tuple = (0, 0, 0), resume_mode: bool = False, bitrate_mbps: int = 20,
                 enable_interpolation: bool = False, target_fps: int = 60, gpu_id: int = -2,
                 interpolate_only: bool = False,
                 target_crop_size: tuple = None):
        super().__init__()
        self.video_paths = video_paths
        self.model = model
        self.scale = scale
        self.batch_size = batch_size
        self.encoder = encoder
        self.hwaccel = hwaccel
        self.output_dir = output_dir
        self.remove_audio = remove_audio
        self.tint_adjustment = tint_adjustment
        self.resume_mode = resume_mode
        self.bitrate_mbps = bitrate_mbps
        self.enable_interpolation = enable_interpolation
        self.target_fps = target_fps
        self.gpu_id = gpu_id
        self.interpolate_only = interpolate_only
        self.target_crop_size = target_crop_size
        self._stop_requested = False
        
        self.ffmpeg_bin = get_ffmpeg_path()
        self.ffprobe_bin = get_ffprobe_path()
        self.realesrgan_bin = get_realesrgan_path()
        self.waifu2x_bin = get_waifu2x_path()
        self.rife_bin = get_rife_path()
        self.models_dir = get_models_dir()
        
        from dialogs.tools.upscaler_model_manager_dialog import UpscalerModelManager
        self.model_manager = UpscalerModelManager()
        model_info = self.model_manager.get_model_by_name(model)
        self.model_type = model_info['type'] if model_info else 'ncnn'
        self.model_info = model_info

    def stop(self):
        self._stop_requested = True

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

    def _preflight_rife(self) -> bool:
        if not self.rife_bin.exists():
            self.log_signal.emit(f"❌ RIFE executable missing: {self.rife_bin}")
            print(f"System Error: RIFE executable missing at {self.rife_bin}")
            return False
        if platform.system() != 'Windows' and not os.access(self.rife_bin, os.X_OK):
            try:
                st = os.stat(self.rife_bin).st_mode
                os.chmod(self.rife_bin, st | 0o755)
            except Exception as e:
                print(f"System Error: Cannot set executable bit on {self.rife_bin}: {e}")
                self.log_signal.emit(f"❌ OS error: permission issue on {self.rife_bin}")
                return False
            if not os.access(self.rife_bin, os.X_OK):
                self.log_signal.emit(f"❌ OS error: permission denied: {self.rife_bin}")
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

    def _normalize_and_save_frame(self, img_arr, output_path: str, ref_frame_path: str | None = None) -> bool:
        if not isinstance(img_arr, np.ndarray):
            print(f"ERROR: Upscaler produced non-numpy output for {output_path}")
            self.log_signal.emit(f"❌ Upscaler produced invalid frame output for {os.path.basename(output_path)}")
            return False

        arr = img_arr
        if arr.ndim == 2:
            arr = np.stack([arr, arr, arr], axis=-1)
            self.log_signal.emit(f"ℹ️ Converted single-channel frame for {os.path.basename(output_path)}")
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

        ok = cv2.imwrite(output_path, arr_u8, [cv2.IMWRITE_PNG_COMPRESSION, 0])
        if not ok:
            print(f"ERROR: Failed to write frame to {output_path}")
            self.log_signal.emit(f"❌ Failed to write frame: {os.path.basename(output_path)}")
            return False
        return True

    def _upscale_frame_pytorch(self, backend_tuple, frame_path: str, output_path: str) -> bool:
        try:
            backend_type, backend = backend_tuple
            
            if backend_type == 'realesrgan':
                img = cv2.imread(frame_path, cv2.IMREAD_UNCHANGED)
                if img is None:
                    return False
                
                output, _ = backend.enhance(img, outscale=self.scale)
                cv2.imwrite(output_path, output, [cv2.IMWRITE_PNG_COMPRESSION, 0])
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
                        img = cv2.imread(frame_path, cv2.IMREAD_COLOR)
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
                        
                        return self._normalize_and_save_frame(output, output_path)
                except Exception as e:
                    self.log_signal.emit(f"   ❌ PyTorch direct upscale error: {e}")
                    tb = traceback.format_exc()
                    for l in tb.splitlines()[-20:]:
                        self.log_signal.emit(f"      {l}")
                    return False
                
        except Exception as e:
            self.log_signal.emit(f"   ❌ PyTorch upscale exception: {e}")
            tb = traceback.format_exc()
            for l in tb.splitlines()[-20:]:
                self.log_signal.emit(f"      {l}")
            return False
    
    def _upscale_frame_onnx(self, session, frame_path: str, output_path: str) -> bool:
        try:
            img = cv2.imread(frame_path, cv2.IMREAD_COLOR)
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
            
            input_name = session.get_inputs()[0].name
            output_name = session.get_outputs()[0].name
            
            expected_type = session.get_inputs()[0].type
            if 'float16' in expected_type:
                img = img.astype(np.float16)
            
            result = session.run([output_name], {input_name: img})[0]
            
            result = np.squeeze(result, axis=0)
            result = np.transpose(result, (1, 2, 0))
            
            if pad_h > 0 or pad_w > 0:
                output_h = h * self.scale
                output_w = w * self.scale
                result = result[:output_h, :output_w, :]
            
            result = np.clip(result * 255.0, 0, 255).astype(np.uint8)
            result = cv2.cvtColor(result, cv2.COLOR_RGB2BGR)
            
            cv2.imwrite(output_path, result, [cv2.IMWRITE_PNG_COMPRESSION, 0])
            return True
        except Exception:
            return False

    def _detect_ffmpeg_encoders(self) -> dict:
        enc = {}
        if not self.ffmpeg_bin.exists():
            return {
                'h264_nvenc': False,
                'hevc_nvenc': False,
                'h264_amf': False,
                'h264_qsv': False,
                'libx264': False,
                'nvenc': False,
                'nvidia': False,
            }
        res = subprocess.run([str(self.ffmpeg_bin), "-hide_banner", "-encoders"], capture_output=True, text=True)
        out = (res.stdout or "").lower()
        enc['h264_nvenc'] = 'h264_nvenc' in out
        enc['hevc_nvenc'] = 'hevc_nvenc' in out
        enc['h264_amf'] = 'h264_amf' in out
        enc['h264_qsv'] = 'h264_qsv' in out
        enc['libx264'] = 'libx264' in out
        enc['nvenc'] = 'nvenc' in out
        enc['nvidia'] = shutil.which('nvidia-smi') is not None
        return enc

    def _preferred_encoder_order(self, requested_codec: str) -> List[str]:
        if requested_codec == 'libx264':
            return ['libx264']
        detected = self._detect_ffmpeg_encoders()
        order: List[str] = []
        if detected.get('nvidia') or detected.get('h264_nvenc') or detected.get('hevc_nvenc'):
            if detected.get('h264_nvenc'):
                order.append('h264_nvenc')
            if detected.get('hevc_nvenc') and 'hevc_nvenc' not in order:
                order.append('hevc_nvenc')
            if detected.get('h264_qsv'):
                order.append('h264_qsv')
            if detected.get('h264_amf'):
                order.append('h264_amf')
        elif detected.get('h264_amf'):
            order.append('h264_amf')
            if detected.get('h264_nvenc'):
                order.append('h264_nvenc')
            if detected.get('hevc_nvenc'):
                order.append('hevc_nvenc')
        elif detected.get('h264_qsv'):
            order.append('h264_qsv')
            if detected.get('h264_nvenc'):
                order.append('h264_nvenc')
        if detected.get('libx264') and 'libx264' not in order:
            order.append('libx264')
        if not order:
            order = ['libx264']
        seen = set()
        final: List[str] = []
        for e in order:
            if e not in seen:
                final.append(e)
                seen.add(e)
        detected_list = [k for k, v in detected.items() if v and k in ['h264_nvenc', 'hevc_nvenc', 'h264_amf', 'h264_qsv', 'libx264']]
        self.log_signal.emit(f"   Detected FFmpeg encoders: {', '.join(detected_list) if detected_list else 'none'}")
        return final

    def run(self):
        try:
            total_videos = len(self.video_paths)
            overall_success = True
            succeeded = 0
            for idx, video_path in enumerate(self.video_paths):
                if self._stop_requested:
                    self.finished_signal.emit(False, "⚠️ Process stopped by user")
                    return

                self.log_signal.emit(f"")
                self.log_signal.emit(f"{'='*60}")
                self.log_signal.emit(f"📹 Processing video {idx+1}/{total_videos}: {Path(video_path).name}")
                self.log_signal.emit(f"{'='*60}")

                success = self._upscale_video(video_path)
                self.video_completed_signal.emit(video_path, success)
                if success:
                    succeeded += 1
                else:
                    overall_success = False

                if self._stop_requested:
                    self.finished_signal.emit(False, "⚠️ Process stopped by user")
                    return

            if self._stop_requested:
                self.finished_signal.emit(False, "⚠️ Process stopped by user")
            else:
                if overall_success:
                    self.finished_signal.emit(True, f"✅ All {total_videos} videos upscaled successfully!")
                elif succeeded == 0:
                    self.finished_signal.emit(False, "❌ All videos failed; see logs for details")
                else:
                    self.finished_signal.emit(False, f"⚠️ Completed {succeeded}/{total_videos} videos; some failed. See logs.")
        except Exception as e:
            self.log_signal.emit(f"   ❌ Exception: {e}")
            tb = traceback.format_exc()
            for l in tb.splitlines()[-40:]:
                self.log_signal.emit(f"      {l}")
            self.finished_signal.emit(False, f"❌ Error: {str(e)}")

    def _upscale_video(self, video_path: str) -> bool:
        try:
            TMP_FRAMES_DIR.mkdir(parents=True, exist_ok=True)
            OUT_FRAMES_DIR.mkdir(parents=True, exist_ok=True)
            BATCH_INPUT_DIR.mkdir(parents=True, exist_ok=True)
            BATCH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            RIFE_FRAMES_DIR.mkdir(parents=True, exist_ok=True)
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            
            self.progress_signal.emit(0)
            
            self.log_signal.emit("🔍 Detecting video framerate...")
            
            if not self.ffprobe_bin.exists():
                raise RuntimeError(f"FFprobe not found at: {self.ffprobe_bin}")
            
            ffprobe_cmd = [
                str(self.ffprobe_bin),
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=r_frame_rate",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ]
            result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, check=True)
            fps_rational = result.stdout.strip()
            if '/' in fps_rational:
                num, den = fps_rational.split('/')
                fps = float(num) / float(den)
                fps_str = fps_rational
            else:
                fps = float(fps_rational)
                fps_str = fps_rational
            self.log_signal.emit(f"   Detected FPS: {fps:.2f} ({fps_str})")
            
            self.log_signal.emit("🧹 Cleaning old frames...")
            for f in TMP_FRAMES_DIR.glob("*"):
                f.unlink()
            for f in OUT_FRAMES_DIR.glob("*"):
                f.unlink()
            for f in RIFE_FRAMES_DIR.glob("*"):
                f.unlink()
            
            if self._stop_requested:
                return False
            
            self.log_signal.emit(f"")
            self.log_signal.emit(f"🎬 PHASE 1/3: EXTRACTING FRAMES")
            self.log_signal.emit(f"   📥 Input: {video_path}")
            self.log_signal.emit(f"   ⚙️ Decoder: {self.hwaccel}")
            if self.remove_audio:
                self.log_signal.emit(f"   🔇 Audio will be removed from output")
            else:
                self.log_signal.emit(f"   🔊 Audio will be preserved in output")
            
            if not self.ffmpeg_bin.exists():
                raise RuntimeError(f"FFmpeg not found at: {self.ffmpeg_bin}")
            
            total_frames_cmd = [
                str(self.ffprobe_bin),
                "-v", "error",
                "-select_streams", "v:0",
                "-count_packets",
                "-show_entries", "stream=nb_read_packets",
                "-of", "csv=p=0",
                video_path
            ]
            result = subprocess.run(total_frames_cmd, capture_output=True, text=True, check=True)
            total_frames = int(result.stdout.strip())
            self.log_signal.emit(f"   📐 Total frames to extract: {total_frames}")
            
            extract_cmd = [str(self.ffmpeg_bin)]
            
            hwaccel_map = {
                "CPU Only": None,
                "Auto (Recommended)": "auto",
                "NVIDIA CUDA": "cuda",
                "Intel Quick Sync": "qsv",
                "DirectX 11": "d3d11va",
            }
            hwaccel_method = hwaccel_map.get(self.hwaccel, "auto")
            
            if hwaccel_method:
                extract_cmd.extend(["-hwaccel", hwaccel_method])
                self.log_signal.emit(f"   ⚡ Using hardware acceleration: {hwaccel_method}")
            else:
                self.log_signal.emit(f"   🧠 Using CPU-only decoding")
            
            extract_cmd.extend([
                "-i", video_path,
                "-vsync", "0",
                "-frames:v", "-1",
                str(TMP_FRAMES_DIR / "frame%08d.png")
            ])
            
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
            proc = subprocess.Popen(
                extract_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                startupinfo=startupinfo, creationflags=creationflags
            )
            
            stderr_lines = []
            for line in proc.stderr:
                if self._stop_requested:
                    proc.terminate()
                    return False
                stderr_lines.append(line.rstrip())
                if "frame=" in line:
                    match = re.search(r"frame=\s*(\d+)", line)
                    if match:
                        extracted_frames = int(match.group(1))
                        if total_frames > 0:
                            progress = int((extracted_frames / total_frames) * 100)
                            self.progress_signal.emit(min(100, progress))
            
            proc.wait()
            
            if proc.returncode != 0:
                self.log_signal.emit(f"❌ FFmpeg extraction failed (returncode={proc.returncode})")
                if stderr_lines:
                    tail = stderr_lines[-50:]
                    self.log_signal.emit("   🔎 Recent FFmpeg stderr:")
                    for l in tail:
                        self.log_signal.emit(f"      {l}")
                else:
                    self.log_signal.emit("   🔎 No FFmpeg stderr captured")
                return False
            
            frame_count = len(list(TMP_FRAMES_DIR.glob("*.png")))
            self.progress_signal.emit(100)
            self.log_signal.emit(f"✅ PHASE 1 COMPLETE: Extracted {frame_count} frames")
            
            if self._stop_requested:
                return False

            if self.enable_interpolation:
                if not self._preflight_rife():
                    self.log_signal.emit("❌ RIFE preflight failed; skipping interpolation")
                    print("RIFE preflight failed; interpolation skipped")
                else:
                    self.log_signal.emit(f"")
                    self.log_signal.emit(f"🎥 PHASE 1.5/3: INTERPOLATING FRAMES")
                    self.log_signal.emit(f"   Target FPS: {self.target_fps} (source: {fps:.2f})")

                    RIFE_FRAMES_DIR.mkdir(parents=True, exist_ok=True)
                    for f in RIFE_FRAMES_DIR.glob("*"):
                        f.unlink()

                    input_frame_count = len(list(TMP_FRAMES_DIR.glob("*.png")))
                    if fps > 0:
                        rife_n = max(2, int((self.target_fps + fps - 0.001) / fps))
                        expected_output_frames = max(1, round(input_frame_count * rife_n))
                    else:
                        rife_n = 2
                        expected_output_frames = input_frame_count * 2

                    rife_model_dir = self.rife_bin.parent / "rife-v4.6"
                    rife_cmd = [
                        str(self.rife_bin),
                        "-i", str(TMP_FRAMES_DIR),
                        "-o", str(RIFE_FRAMES_DIR),
                        "-n", str(expected_output_frames),
                        "-m", str(rife_model_dir),
                    ]
                    if self.gpu_id != -2:
                        rife_cmd += ["-g", str(self.gpu_id)]

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

                    self.log_signal.emit(f"   ▶️ Interpolating frames... ({input_frame_count} input frames → ~{expected_output_frames} output frames, {rife_n}x factor)")
                    self.progress_signal.emit(0)

                    rife_proc = subprocess.Popen(
                        rife_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        startupinfo=startupinfo,
                        creationflags=creationflags,
                        cwd=str(self.rife_bin.parent)
                    )

                    import threading
                    rife_stderr_lines = []

                    def _read_rife_stderr():
                        for line in rife_proc.stderr:
                            stripped = line.rstrip()
                            if stripped:
                                rife_stderr_lines.append(stripped)

                    stderr_thread = threading.Thread(target=_read_rife_stderr, daemon=True)
                    stderr_thread.start()

                    last_logged_done = -1
                    while rife_proc.poll() is None:
                        if self._stop_requested:
                            rife_proc.terminate()
                            self.log_signal.emit("⚠️ Frame interpolation stopped by user")
                            break
                        done = len(list(RIFE_FRAMES_DIR.glob("*.png")))
                        if expected_output_frames > 0:
                            pct = min(99, int(done / expected_output_frames * 100))
                            self.progress_signal.emit(pct)
                        if done != last_logged_done and done > 0:
                            self.log_signal.emit(f"   🎞️ Interpolating: {done}/{expected_output_frames} frames")
                            last_logged_done = done
                        import time as _time
                        _time.sleep(0.5)

                    stderr_thread.join(timeout=5)

                    if rife_proc.returncode != 0 and not self._stop_requested:
                        self.log_signal.emit(f"❌ Frame interpolation failed (rc={rife_proc.returncode}); skipped")
                        for line in rife_stderr_lines[-20:]:
                            print(f"RIFE stderr: {line}")
                    else:
                        rife_outputs = sorted(RIFE_FRAMES_DIR.glob("*.png"))
                        if rife_outputs:
                            for f in TMP_FRAMES_DIR.glob("*"):
                                f.unlink()
                            for src in rife_outputs:
                                shutil.copy2(src, TMP_FRAMES_DIR / src.name)
                            rife_output_count = len(rife_outputs)
                            frame_count = rife_output_count
                            if input_frame_count > 0 and fps > 0:
                                actual_rife_fps = fps * rife_output_count / input_frame_count
                            else:
                                actual_rife_fps = float(self.target_fps)
                            fps = actual_rife_fps
                            fps_str = f"{actual_rife_fps:.6f}"
                            self.progress_signal.emit(100)
                            self.log_signal.emit(f"✅ INTERPOLATION COMPLETE: {frame_count} frames, actual fps: {actual_rife_fps:.3f} (target: {self.target_fps})")
                        else:
                            self.log_signal.emit("⚠️ Interpolation produced no output; original frames retained")
                            print("RIFE produced no output frames in RIFE_FRAMES_DIR")

            self.progress_signal.emit(0)
            self.stats_signal.emit(0, frame_count, 0.0, frame_count, 0.0)
            
            self.log_signal.emit(f"")
            skip_upscale = False
            start_time = time.time()
            if self.interpolate_only:
                skip_upscale = True
                self.log_signal.emit("⚡ Interpolate-only mode enabled: skipping upscaling")
                # Copy interpolated frames to output directory for merging
                if OUT_FRAMES_DIR.exists():
                    for f in OUT_FRAMES_DIR.glob("*.png"):
                        try:
                            f.unlink()
                        except Exception:
                            pass
                OUT_FRAMES_DIR.mkdir(parents=True, exist_ok=True)
                for src in TMP_FRAMES_DIR.glob("*.png"):
                    shutil.copy2(src, OUT_FRAMES_DIR / src.name)
                # Rename to frame%08d.png so ffmpeg merge finds the sequence
                output_frames = sorted(OUT_FRAMES_DIR.glob("*.png"))
                for idx, frame_file in enumerate(output_frames, start=1):
                    new_name = OUT_FRAMES_DIR / f"frame{idx:08d}.png"
                    if frame_file != new_name:
                        try:
                            frame_file.rename(new_name)
                        except Exception:
                            pass
                frame_files = sorted(OUT_FRAMES_DIR.glob("frame*.png"))
                total_frames = len(frame_files)
                processed = total_frames
                self.progress_signal.emit(100)
                self.stats_signal.emit(total_frames, total_frames, 0.0, 0, 0.0)
            else:
                self.log_signal.emit(f"🚀 PHASE 2/3: UPSCALING FRAMES")
                self.log_signal.emit(f"   🧩 Model: {self.model} (Type: {self.model_type.upper()}) | Scale: {self.scale}x | Batch: {self.batch_size}")
            
            existing_upscaled = set()
            if self.resume_mode and OUT_FRAMES_DIR.exists():
                existing_upscaled = {f.name for f in OUT_FRAMES_DIR.glob("*.png")}
                if existing_upscaled:
                    self.log_signal.emit(f"   🔄 Resume mode: Found {len(existing_upscaled)} existing upscaled frames")
            else:
                # In interpolate-only mode, we already prepared OUT_FRAMES_DIR and should not delete it
                if not skip_upscale:
                    for f in OUT_FRAMES_DIR.glob("*"):
                        f.unlink()
            
            if not skip_upscale:
                frame_files = sorted(TMP_FRAMES_DIR.glob("*.png"))
                total_frames = len(frame_files)
                start_time = time.time()
                processed = 0
            
            if not skip_upscale and self.model_type in ['pth', 'onnx']:
                backend = self._init_upscaler_backend()
                if backend is None:
                    self.log_signal.emit("❌ Failed to initialize backend")
                    return False
                
                frames_to_process = [f for f in frame_files if f.name not in existing_upscaled]
                skipped_count = len(frame_files) - len(frames_to_process)
                if skipped_count > 0:
                    self.log_signal.emit(f"   ⏭️ Skipping {skipped_count} already upscaled frames")
                    processed = skipped_count
                
                self.log_signal.emit(f"   Processing {len(frames_to_process)} frames with {self.model_type.upper()} backend")
                
                for idx, frame_file in enumerate(frames_to_process):
                    if self._stop_requested:
                        return False
                    
                    output_path = OUT_FRAMES_DIR / frame_file.name
                    
                    success = False
                    if self.model_type == 'pth':
                        success = self._upscale_frame_pytorch(backend, str(frame_file), str(output_path))
                    elif self.model_type == 'onnx':
                        success = self._upscale_frame_onnx(backend, str(frame_file), str(output_path))
                    
                    if not success:
                        self.log_signal.emit(f"   ❌ Failed to upscale frame {frame_file.name}")
                        return False
                    
                    processed = skipped_count + idx + 1
                    elapsed = time.time() - start_time
                    remaining = max(0, total_frames - processed)
                    eta = 0.0
                    if processed > 0:
                        rate = elapsed / (idx + 1) if idx >= 0 else 0
                        eta = rate * (len(frames_to_process) - idx - 1)
                        progress_pct = int((processed / total_frames) * 100)
                        self.progress_signal.emit(min(100, progress_pct))
                    
                    self.stats_signal.emit(processed, total_frames, elapsed, remaining, float(eta))
                    
                    if (idx + 1) % 10 == 0 or (idx + 1) == len(frames_to_process):
                        self.log_signal.emit(f"   Progress: {processed}/{total_frames} frames ({progress_pct}%)")
                
                elapsed = time.time() - start_time
                self.progress_signal.emit(100)
                self.log_signal.emit(f"✅ PHASE 2 COMPLETE: Upscaled {len(frames_to_process)} frames (skipped {skipped_count}) in {elapsed:.2f}s")
            
            elif self.model_type == 'waifu2x':
                if not self._preflight_waifu2x():
                    return False
                
                waifu2x_models_subdir = self.model_info.get('models_dir', '') if self.model_info else ''
                noise = self.model_info.get('noise_level', 3) if self.model_info else 3
                
                frames_to_upscale = [f for f in frame_files if f.name not in existing_upscaled]
                skipped_frames = len(frame_files) - len(frames_to_upscale)
                if skipped_frames > 0:
                    self.log_signal.emit(f"   ⏭️ Skipping {skipped_frames} already upscaled frames")
                
                if not frames_to_upscale:
                    self.log_signal.emit("   ✅ All frames already upscaled, skipping to merge phase")
                    processed = frame_count
                else:
                    num_batches = (len(frames_to_upscale) + self.batch_size - 1) // self.batch_size
                    processed = skipped_frames
                    
                    for batch_idx in range(num_batches):
                        if self._stop_requested:
                            return False
                        
                        start_idx = batch_idx * self.batch_size
                        end_idx = min(start_idx + self.batch_size, len(frames_to_upscale))
                        batch_frames = frames_to_upscale[start_idx:end_idx]
                        batch_num = batch_idx + 1
                        
                        for f in BATCH_INPUT_DIR.glob("*"):
                            f.unlink()
                        for f in BATCH_OUTPUT_DIR.glob("*"):
                            f.unlink()
                        for frame_file in batch_frames:
                            shutil.copy2(frame_file, BATCH_INPUT_DIR / frame_file.name)
                        
                        cmd = [
                            str(self.waifu2x_bin),
                            "-i", str(BATCH_INPUT_DIR),
                            "-o", str(BATCH_OUTPUT_DIR),
                            "-n", str(noise),
                            "-s", str(self.scale),
                            "-f", "png",
                        ]
                        if self.gpu_id != -2:
                            cmd += ["-g", str(self.gpu_id)]
                        if waifu2x_models_subdir:
                            cmd += ["-m", waifu2x_models_subdir]
                        
                        self.log_signal.emit(f"   🔁 Running Waifu2x on batch {batch_num}/{num_batches} ({len(batch_frames)} frames)")
                        
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
                            return False
                        
                        last_stdout = []
                        for line in proc.stdout:
                            if self._stop_requested:
                                proc.terminate()
                                return False
                            ll = line.strip()
                            if ll:
                                last_stdout.append(ll)
                        proc.wait()
                        
                        if proc.returncode != 0:
                            self.log_signal.emit(f"❌ Waifu2x failed on batch {batch_num} (code={proc.returncode})")
                            for ln in last_stdout[-10:]:
                                self.log_signal.emit(f"   {ln}")
                            return False
                        
                        for frame_file in batch_frames:
                            out_file = BATCH_OUTPUT_DIR / frame_file.name
                            if out_file.exists():
                                shutil.copy2(out_file, OUT_FRAMES_DIR / frame_file.name)
                            else:
                                self.log_signal.emit(f"   ❌ Missing output for frame: {frame_file.name}")
                                return False
                        
                        processed = skipped_frames + end_idx
                        elapsed = time.time() - start_time
                        remaining = max(0, total_frames - processed)
                        eta = (elapsed / processed) * remaining if processed > 0 else 0.0
                        progress_pct = int((processed / total_frames) * 100)
                        self.progress_signal.emit(min(100, progress_pct))
                        self.stats_signal.emit(processed, total_frames, elapsed, remaining, float(eta))
                    
                    elapsed = time.time() - start_time
                    self.progress_signal.emit(100)
                    self.log_signal.emit(f"✅ PHASE 2 COMPLETE: Upscaled {len(frames_to_upscale)} frames (Waifu2x) in {elapsed:.2f}s")
            
            elif not skip_upscale:
                model_to_use = self.model
                if re.search(r"x([1-8])", model_to_use, re.IGNORECASE):
                    self.log_signal.emit(f"   Using model {model_to_use} (contains scale)")
                else:
                    candidate = f"{model_to_use}-x{self.scale}"
                    if (self.models_dir / f"{candidate}.param").exists():
                        self.log_signal.emit(f"   Using model {candidate} for scale {self.scale}x")
                        model_to_use = candidate
                    else:
                        found = None
                        for p in self.models_dir.glob("*.param"):
                            stem = p.stem
                            if model_to_use in stem and f"x{self.scale}" in stem:
                                found = stem
                                break
                        if found:
                            self.log_signal.emit(f"   Using model {found} for scale {self.scale}x")
                            model_to_use = found

                # Load optimal tile size from device profile
                _ncnn_tile = 128
                try:
                    import json as _json
                    if HW_PROFILE_FILE.exists():
                        _profile = _json.loads(HW_PROFILE_FILE.read_text())
                        _ncnn_tile = _profile.get('optimal_tile', 128)
                        self.log_signal.emit(f"   ⚙️ Device profile tile: {_ncnn_tile} (from device_profile.json)")
                    else:
                        self.log_signal.emit(f"   ⚙️ No device profile, using default tile: {_ncnn_tile}")
                except Exception as e:
                    print(f"Failed to read device profile for tile: {e}")
                
                num_batches = (total_frames + self.batch_size - 1) // self.batch_size
                self.log_signal.emit(f"   🔁 Processing {num_batches} batches with NCNN backend")
                
                frames_to_upscale = [f for f in frame_files if f.name not in existing_upscaled]
                skipped_frames = len(frame_files) - len(frames_to_upscale)
                if skipped_frames > 0:
                    self.log_signal.emit(f"   ⏭️ Skipping {skipped_frames} already upscaled frames")
                
                if not frames_to_upscale:
                    self.log_signal.emit(f"   ✅ All frames already upscaled, skipping to merge phase")
                    processed = frame_count
                else:
                    num_batches = (len(frames_to_upscale) + self.batch_size - 1) // self.batch_size
                    processed = skipped_frames
                
                    for batch_idx in range(num_batches):
                        if self._stop_requested:
                            return False
                        
                        start_idx = batch_idx * self.batch_size
                        end_idx = min(start_idx + self.batch_size, len(frames_to_upscale))
                        batch_frames = frames_to_upscale[start_idx:end_idx]
                        batch_num = batch_idx + 1
                        batch_frame_count = len(batch_frames)
                    
                        if batch_frames:
                            first_frame = Image.open(batch_frames[0])
                            input_width, input_height = first_frame.size
                            output_width = input_width * self.scale
                            output_height = input_height * self.scale
                            self.log_signal.emit(f"   📦 Batch {batch_num}/{num_batches}: Processing frames {start_idx+1}-{end_idx} ({batch_frame_count} frames)")
                            self.log_signal.emit(f"      📐 Input: {input_width}x{input_height} → Output: {output_width}x{output_height}")
                    
                        for f in BATCH_INPUT_DIR.glob("*"):
                            f.unlink()
                        for f in BATCH_OUTPUT_DIR.glob("*"):
                            f.unlink()
                        
                        for frame_file in batch_frames:
                            shutil.copy2(frame_file, BATCH_INPUT_DIR / frame_file.name)
                        
                        cmd = [
                            str(self.realesrgan_bin),
                            "-i", str(BATCH_INPUT_DIR),
                            "-o", str(BATCH_OUTPUT_DIR),
                            "-m", str(self.models_dir),
                            "-n", model_to_use,
                            "-s", str(self.scale),
                            "-t", str(_ncnn_tile),
                            "-j", "1:2:2",
                            "-f", "png",
                        ]
                        if self.gpu_id != -2:
                            cmd += ["-g", str(self.gpu_id)]
                        
                        input_count = len(list(BATCH_INPUT_DIR.glob("*.png")))
                        self.log_signal.emit(f"   🔁 Running RealESRGAN on batch {batch_num}/{num_batches} ({batch_frame_count} frames)")
                        print(f"[RealESRGAN] tile={_ncnn_tile} scale={self.scale} model={model_to_use} batch={batch_num}/{num_batches} gpu_id={self.gpu_id} cmd={' '.join(cmd)}")

                        attempts = 0
                        max_attempts = 2
                        produced_count = 0
                        last_stdout = []
                        while attempts <= max_attempts:
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
                            if not self._preflight_realesrgan():
                                return False

                            try:
                                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                                        text=True, cwd=str(self.realesrgan_bin.parent),
                                                        startupinfo=startupinfo, creationflags=creationflags)
                            except FileNotFoundError as e:
                                print(f"System Error: RealESRGAN executable not found: {e} - {self.realesrgan_bin}")
                                self.log_signal.emit(f"❌ Error launching RealESRGAN for batch {batch_num}: {e} (executable not found)")
                                self.log_signal.emit(f"   Executable: {self.realesrgan_bin}")
                                self.log_signal.emit(f"   Working dir: {self.realesrgan_bin.parent}")
                                self.log_signal.emit(f"   Command: {cmd}")
                                return False
                            except OSError as e:
                                print(f"System Error launching RealESRGAN for batch {batch_num}: {e} - Executable: {self.realesrgan_bin}")
                                self.log_signal.emit(f"❌ OS error launching RealESRGAN for batch {batch_num}: {e}")
                                self.log_signal.emit(f"   Executable: {self.realesrgan_bin}")
                                self.log_signal.emit(f"   Working dir: {self.realesrgan_bin.parent}")
                                self.log_signal.emit(f"   Command: {cmd}")
                                return False

                            for line in proc.stdout:
                                if self._stop_requested:
                                    proc.terminate()
                                    return False
                                ll = line.strip()
                                last_stdout.append(ll)
                                if not ll:
                                    continue
                                low = ll.lower()
                                if 'fail' in low or 'error' in low:
                                    self.log_signal.emit(f"   ❗ ERROR: {ll}")

                            proc.wait()

                            time.sleep(0.5)
                            produced_files = list(BATCH_OUTPUT_DIR.glob("*.png"))
                            produced_count = len(produced_files)

                            if proc.returncode == 0 and produced_count >= batch_frame_count:
                                break

                            attempts += 1
                            self.log_signal.emit(f"   ⚠️ RealESRGAN produced {produced_count}/{batch_frame_count} outputs (attempt {attempts}/{max_attempts+1})")

                            if last_stdout:
                                tail = last_stdout[-20:]
                                self.log_signal.emit("   🔎 Recent RealESRGAN output:")
                                combined = "\n".join(tail).lower()
                                for l in tail:
                                    self.log_signal.emit(f"      {l}")

                                if 'llvmpipe' in combined or 'llvm error' in combined or 'cannot select' in combined or 'fild' in combined:
                                    hint = ("System Error: Vulkan/driver failure detected in RealESRGAN output (llvmpipe/LLVM). "
                                            "Ensure proper Vulkan GPU drivers are installed; using software rasterizers will fail.")
                                    print(hint)
                                    self.log_signal.emit(f"   ❗ {hint}")

                            if attempts > max_attempts:
                                self.log_signal.emit(f"   ❌ RealESRGAN failed repeatedly on batch {batch_num}; skipping batch")
                                overall_success = False
                                break
                            else:
                                time.sleep(1.0)
                                self.log_signal.emit("   🔁 Retrying batch...")

                        copied_count = 0
                        produced_files = list(BATCH_OUTPUT_DIR.glob("*.png"))
                        produced_count = len(produced_files)
                        self.log_signal.emit(f"   ℹ️ Batch produced {produced_count} output file(s)")

                        for frame_file in batch_frames:
                            out_file = BATCH_OUTPUT_DIR / frame_file.name
                            dest = OUT_FRAMES_DIR / frame_file.name
                            if out_file.exists():
                                img = cv2.imread(str(out_file), cv2.IMREAD_UNCHANGED)
                                if img is None:
                                    try:
                                        shutil.copy2(out_file, dest)
                                        copied_count += 1
                                    except Exception as e:
                                        self.log_signal.emit(f"   ❗ Failed to copy raw output {out_file.name}: {e}")
                                        overall_success = False
                                else:
                                    self.log_signal.emit(f"   ℹ️ Frame output means (BGR): {img.mean(axis=(0,1)).tolist() if img.ndim==3 else [img.mean()]} for {out_file.name}")
                                    ok = self._normalize_and_save_frame(img, str(dest))
                                    if ok:
                                        copied_count += 1
                                    else:
                                        try:
                                            shutil.copy2(out_file, dest)
                                            copied_count += 1
                                        except Exception as e:
                                            self.log_signal.emit(f"   ❗ Failed to copy fallback raw output {out_file.name}: {e}")
                                            overall_success = False
                            else:
                                self.log_signal.emit(f"   ⚠️ Missing upscaled output for: {frame_file.name}")
                                overall_success = False

                        processed += copied_count
                        elapsed = time.time() - start_time
                        remaining = max(0, frame_count - processed)
                        eta = 0.0
                        if processed > 0:
                            rate = elapsed / processed
                            eta = rate * remaining
                            progress_pct = int((processed / frame_count) * 100)
                            self.progress_signal.emit(min(100, progress_pct))

                        self.stats_signal.emit(processed, frame_count, elapsed, remaining, float(eta))
            
                if self._stop_requested:
                    return False
                
                self.log_signal.emit("🔧 Renaming output frames...")
                output_frames = sorted(OUT_FRAMES_DIR.glob("*.png"))
                for idx, frame_file in enumerate(output_frames, start=1):
                    new_name = OUT_FRAMES_DIR / f"frame{idx:08d}.png"
                    if frame_file != new_name:
                        try:
                            frame_file.rename(new_name)
                        except Exception as e:
                            self.log_signal.emit(f"   ❗ Failed renaming {frame_file.name} -> {new_name.name}: {e}")
                            overall_success = False
                
                output_frames_renamed = sorted(OUT_FRAMES_DIR.glob("frame*.png"))
                renamed_count = len(output_frames_renamed)
                if renamed_count != frame_count:
                    missing = frame_count - renamed_count
                    expected_names = [f"frame{i:08d}.png" for i in range(1, frame_count+1)]
                    existing = {p.name for p in output_frames_renamed}
                    missing_examples = [n for n in expected_names if n not in existing][:10]
                    self.log_signal.emit(f"   ⚠️ Found {renamed_count}/{frame_count} upscaled frames (missing {missing})")
                    if missing_examples:
                        self.log_signal.emit(f"   ⚠️ Missing examples: {', '.join(missing_examples)}")
                    self.log_signal.emit("   ❌ Aborting: not enough upscaled frames to merge.")
                    return False
                
                self.progress_signal.emit(100)
                elapsed = time.time() - start_time
                self.log_signal.emit(f"✅ PHASE 2 COMPLETE: Upscaled {processed} frames in {elapsed:.2f}s")

            if self._stop_requested:
                return False

            # If we skipped upscaling, we already set stats and progress above
            if not skip_upscale:
                self.progress_signal.emit(0)
                self.log_signal.emit(f"")
                self.log_signal.emit(f"🎞️ PHASE 3/3: MERGING TO VIDEO")
            else:
                # Still need to enter merge phase but skip redundant logs/reset
                self.progress_signal.emit(0)
                self.log_signal.emit(f"🎞️ PHASE 3/3: MERGING TO VIDEO")
            
            merge_frames = sorted(OUT_FRAMES_DIR.glob("frame*.png"))
            total_merge_frames = len(merge_frames)
            self.log_signal.emit(f"   🔗 Merging {total_merge_frames} frames at {fps:.2f} FPS")
            
            video_name = Path(video_path).stem
            if self.output_dir:
                output_path = Path(self.output_dir) / f"{video_name}_upscaled_{self.scale}x.mp4"
            else:
                output_path = RESULTS_DIR / f"{video_name}_upscaled_{self.scale}x.mp4"
            
            encoder_map = {
                "CPU (x264)": "libx264",
                "GPU - NVIDIA (NVENC H.264)": "h264_nvenc",
                "GPU - NVIDIA (NVENC HEVC) - High Res": "hevc_nvenc",
                "GPU - AMD (AMF)": "h264_amf",
                "GPU - Intel (QSV)": "h264_qsv",
            }
            video_codec = encoder_map.get(self.encoder, "libx264")
            
            self.log_signal.emit(f"   🎛️ Using encoder: {self.encoder} ({video_codec})")
            
            bitrate_kbps = self.bitrate_mbps * 1000
            bitrate_str = f"{bitrate_kbps}k"
            
            import os as _os
            cpu_threads = str(max(1, (_os.cpu_count() or 2)))
            enc_opts = {
                "h264_nvenc": ["-preset", "p4", "-tune", "hq", "-rc", "vbr", "-b:v", bitrate_str, "-maxrate", bitrate_str, "-bf", "2"],
                "hevc_nvenc": ["-preset", "p4", "-tune", "hq", "-rc", "vbr", "-b:v", bitrate_str, "-maxrate", bitrate_str, "-bf", "2"],
                "h264_amf": ["-quality", "balanced", "-rc", "vbr_latency", "-b:v", bitrate_str],
                "h264_qsv": ["-preset", "medium", "-b:v", bitrate_str],
                "libx264": ["-preset", "fast", "-b:v", bitrate_str, "-threads", cpu_threads, "-tune", "film"],
            }

            detected = self._detect_ffmpeg_encoders()
            try_encoders = self._preferred_encoder_order(video_codec)
            tried = []
            successful = False

            for try_codec in try_encoders:
                tried.append(try_codec)
                self.log_signal.emit(f"   🎛️ Trying encoder: {try_codec}")

                output_fps = self.target_fps if self.enable_interpolation else fps
                output_fps_str = str(self.target_fps) if self.enable_interpolation else fps_str
                gop_size = max(1, round(output_fps * 2))

                merge_cmd = [
                    str(self.ffmpeg_bin),
                    "-framerate", fps_str,
                    "-start_number", "1",
                    "-i", str(OUT_FRAMES_DIR / "frame%08d.png"),
                ]

                if not self.remove_audio:
                    merge_cmd.extend([
                        "-i", video_path,
                        "-map", "0:v:0",
                        "-map", "1:a:0?",
                        "-c:a", "aac",
                        "-ac", "2",
                        "-movflags", "+faststart",
                    ])
                else:
                    merge_cmd.extend([
                        "-map", "0:v:0",
                        "-an",
                        "-movflags", "+faststart",
                    ])

                if self.remove_audio:
                    self.log_signal.emit("   🔇 Audio will be removed from output")

                vf_parts = []
                if self.enable_interpolation:
                    vf_parts.append(f"fps={self.target_fps}")
                if self.target_crop_size is not None:
                    cw, ch = self.target_crop_size
                    vf_parts.append(f"scale={cw}:{ch}:force_original_aspect_ratio=increase,crop={cw}:{ch}")
                    self.log_signal.emit(f"   ✂️ Scale-to-fill + crop: {cw}x{ch} (center)")
                if vf_parts:
                    merge_cmd.extend(["-vf", ",".join(vf_parts)])

                merge_cmd.extend(["-c:v", try_codec])

                opt_list = enc_opts.get(try_codec, ["-preset", "medium", "-b:v", bitrate_str])
                merge_cmd.extend(opt_list)

                merge_cmd.extend([
                    "-r", output_fps_str,
                    "-vsync", "cfr",
                    "-pix_fmt", "yuv420p",
                    "-g", str(gop_size),
                    "-max_muxing_queue_size", "1024",
                    "-y",
                    str(output_path)
                ])

                self.log_signal.emit(f"   ⏺️ Encoding video...")

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

                proc = subprocess.Popen(
                    merge_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    startupinfo=startupinfo, creationflags=creationflags
                )

                stderr_lines = []
                for line in proc.stderr:
                    if self._stop_requested:
                        proc.terminate()
                        return False
                    if "frame=" in line:
                        match = re.search(r"frame=\s*(\d+)", line)
                        if match:
                            merged_frames = int(match.group(1))
                            if total_merge_frames > 0:
                                progress = int((merged_frames / total_merge_frames) * 100)
                                self.progress_signal.emit(min(100, progress))
                    stderr_lines.append(line)

                proc.wait()

                if proc.returncode == 0:
                    video_codec = try_codec
                    successful = True
                    break

                self.log_signal.emit(f"⚠️ FFmpeg merge failed with {try_codec}")
                last_err = "".join(stderr_lines[-40:])
                for line in last_err.strip().splitlines():
                    self.log_signal.emit(f"   🧩 {line}")
                if try_codec != "libx264":
                    self.log_signal.emit("   🔁 Trying next fallback encoder...")
                else:
                    self.log_signal.emit("   ❌ All encoders failed; aborting merge")

            if not successful:
                return False

            self.progress_signal.emit(100)
            
            self.progress_signal.emit(100)
            
            self.log_signal.emit("🔍 Verifying output file...")
            if not output_path.exists():
                self.log_signal.emit(f"❌ Output file not created: {output_path}")
                return False
            
            max_wait = 10
            for i in range(max_wait):
                if self._stop_requested:
                    return False
                time.sleep(0.5)
                try:
                    size = output_path.stat().st_size
                    if size > 0:
                        time.sleep(0.5)
                        new_size = output_path.stat().st_size
                        if size == new_size:
                            size_mb = size / (1024 * 1024)
                            self.log_signal.emit(f"   📦 Output file size: {size_mb:.2f} MB")
                            break
                except Exception:
                    pass
            else:
                self.log_signal.emit(f"⚠️ Warning: Could not verify output file stability")
            
            self.log_signal.emit(f"✅ PHASE 3 COMPLETE: {output_path}")
            
            self.log_signal.emit("🧹 Cleaning up temporary frames...")
            time.sleep(1.0)
            
            for attempt in range(3):
                failed_files = []
                
                for f in TMP_FRAMES_DIR.glob("*"):
                    try:
                        f.unlink()
                    except Exception as e:
                        failed_files.append(str(f))
                
                for f in OUT_FRAMES_DIR.glob("*"):
                    try:
                        f.unlink()
                    except Exception as e:
                        failed_files.append(str(f))
                
                for f in BATCH_INPUT_DIR.glob("*"):
                    try:
                        f.unlink()
                    except Exception as e:
                        failed_files.append(str(f))
                
                for f in BATCH_OUTPUT_DIR.glob("*"):
                    try:
                        f.unlink()
                    except Exception as e:
                        failed_files.append(str(f))
                
                if not failed_files:
                    break
                
                if attempt < 2:
                    self.log_signal.emit(f"   ⚠️ {len(failed_files)} files locked, retrying cleanup...")
                    time.sleep(2.0)
                else:
                    self.log_signal.emit(f"   ⚠️ Warning: Could not delete {len(failed_files)} files (they may be locked)")
            
            return True
            
        except Exception as e:
            self.log_signal.emit(f"❌ Error: {str(e)}")
            return False


HW_CAP_MARKER = Path(BASE_PATH) / "temp" / ".hw_cap_tested"
HW_PROFILE_FILE = Path(BASE_PATH) / "temp" / "device_profile.json"

class HardwareCapTestWorker(QThread):
    log_signal = Signal(str)
    stage_signal = Signal(str)
    finished_signal = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            import json as _json
            import datetime as _dt
            test_dir = Path(BASE_PATH) / "temp" / ".hw_cap_test"
            test_dir.mkdir(parents=True, exist_ok=True)

            # Stage 1: Tool binaries
            self.stage_signal.emit("Checking binaries...")
            self.log_signal.emit("[ 1/9 ]  Tool Binaries")
            realesrgan_bin = get_realesrgan_path()
            waifu2x_bin = get_waifu2x_path()
            ffmpeg_bin = get_ffmpeg_path()
            ffprobe_bin = get_ffprobe_path()
            rife_bin = get_rife_path()
            realesrgan_exists = realesrgan_bin.exists()
            waifu2x_exists = waifu2x_bin.exists()
            ffmpeg_exists = ffmpeg_bin.exists()
            ffprobe_exists = ffprobe_bin.exists()
            rife_exists = rife_bin.exists()
            self.log_signal.emit(f"   {'✅' if realesrgan_exists else '❌'} RealESRGAN : {realesrgan_bin.name}")
            self.log_signal.emit(f"   {'✅' if waifu2x_exists else '⚠️'} Waifu2x    : {waifu2x_bin.name}")
            self.log_signal.emit(f"   {'✅' if ffmpeg_exists else '❌'} FFmpeg     : {ffmpeg_bin.name}")
            self.log_signal.emit(f"   {'✅' if ffprobe_exists else '❌'} FFprobe    : {ffprobe_bin.name}")
            self.log_signal.emit(f"   {'✅' if rife_exists else '⚠️'} RIFE       : {rife_bin.name}")
            binaries_ok = realesrgan_exists and ffmpeg_exists and ffprobe_exists

            # Stage 2: Hardware probe (RAM, VRAM, GPU name)
            self.stage_signal.emit("Probing hardware...")
            self.log_signal.emit("[ 2/9 ]  Hardware Probe")
            hw_info = self._probe_hardware_info()
            ram_gb = hw_info['ram_mb'] / 1024.0
            self.log_signal.emit(f"   RAM      : {hw_info['ram_mb']:,} MB ({ram_gb:.1f} GB)")
            self.log_signal.emit(f"   GPU      : {hw_info['gpu_name']}")
            if hw_info['vram_mb'] > 0:
                self.log_signal.emit(f"   VRAM     : {hw_info['vram_mb']:,} MB ({hw_info['vram_mb']/1024:.1f} GB)")
            else:
                self.log_signal.emit(f"   VRAM     : Not detected (may be AMD/Intel/CPU-only)")
            self.log_signal.emit(f"   {'✅ Dedicated GPU detected' if hw_info['gpu_detected'] else '⚠️ No dedicated GPU (CPU-only mode)'}")
            gpu_ok = hw_info['gpu_detected']

            # Stage 3: Models
            self.stage_signal.emit("Checking models...")
            self.log_signal.emit("[ 3/9 ]  Model Files")
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

            # Stage 4: RealESRGAN upscale test + tile benchmark
            self.stage_signal.emit("Testing RealESRGAN inference...")
            self.log_signal.emit("[ 4/9 ]  RealESRGAN Upscale Test")
            realesrgan_ok = False
            test_out_path = None
            output_size = None
            optimal_tile = 128
            if realesrgan_exists and models_ok:
                model_name = model_files[0].stem
                self.log_signal.emit(f"   Model  : {model_name}")
                self.log_signal.emit(f"   Input  : 64x64 px blank PNG")
                self.log_signal.emit(f"   Scale  : 2x -> expected 128x128")
                realesrgan_ok, test_out_path, output_size = self._test_realesrgan(test_dir, model_name)
                if realesrgan_ok and output_size:
                    self.log_signal.emit(f"   ✅ Output: {output_size[0]}x{output_size[1]} px")
                    self.log_signal.emit(f"   ✅ Output is readable by PIL")
                    self.log_signal.emit(f"   🔍 Benchmarking optimal tile size (256x256 test image)...")
                    optimal_tile = self._benchmark_tile_size(test_dir, model_name)
                    self.log_signal.emit(f"   ✅ Optimal tile size: {optimal_tile}")
                else:
                    self.log_signal.emit(f"   ❌ RealESRGAN upscale failed or output invalid")
            else:
                self.log_signal.emit("   ⚠️ Skipped (binary or models missing)")

            # Stage 5: FFmpeg encode test
            self.stage_signal.emit("Testing FFmpeg encode...")
            self.log_signal.emit("[ 5/9 ]  FFmpeg Encode Test")
            encode_ok = False
            encoded_video = None
            if ffmpeg_exists and test_out_path and test_out_path.exists():
                self.log_signal.emit(f"   Input  : upscaled frame ({output_size[0]}x{output_size[1]})")
                self.log_signal.emit(f"   Codec  : libx264, 1 frame")
                encode_ok, encoded_video = self._test_ffmpeg_encode(test_dir, test_out_path)
                self.log_signal.emit(f"   {'✅ FFmpeg encode OK' if encode_ok else '❌ FFmpeg encode failed'}")
            else:
                self.log_signal.emit("   ⚠️ Skipped (FFmpeg missing or no upscaled frame)")

            # Stage 6: FFprobe readability
            self.stage_signal.emit("Verifying output video...")
            self.log_signal.emit("[ 6/9 ]  Output Video Readability")
            probe_ok = False
            if ffprobe_exists and encoded_video and encoded_video.exists():
                self.log_signal.emit(f"   Video  : {encoded_video.name}")
                probe_ok = self._test_ffprobe_read(encoded_video)
                self.log_signal.emit(f"   {'✅ FFprobe can read video' if probe_ok else '❌ FFprobe failed to read video'}")
            else:
                self.log_signal.emit("   ⚠️ Skipped (FFprobe missing or no encoded video)")

            # Stage 7: RIFE binary
            self.stage_signal.emit("Testing RIFE...")
            self.log_signal.emit("[ 7/9 ]  RIFE Interpolation Binary")
            self.log_signal.emit(f"   Binary : {rife_bin}")
            if rife_exists:
                self.log_signal.emit(f"   Input  : 2x 64x64 px test frames")
                rife_ok = self._test_rife(test_dir)
                if rife_ok:
                    self.log_signal.emit(f"   ✅ RIFE interpolation test passed")
                else:
                    self.log_signal.emit(f"   ❌ RIFE interpolation test failed")
            else:
                self.log_signal.emit(f"   ⚠️ RIFE not installed, skipped")

            # Stage 8: Progressive scale capability
            self.stage_signal.emit("Testing progressive scale...")
            self.log_signal.emit("[ 8/9 ]  Progressive Scale Capability")
            targets = [("HD", 1280, 720), ("Full HD", 1920, 1080), ("2K", 2560, 1440), ("4K", 3840, 2160)]
            if realesrgan_ok and output_size:
                base_w, base_h = 640, 480
                for label, tw, th in targets:
                    needed_scale = max(tw / base_w, th / base_h)
                    passes = needed_scale <= 8
                    self.log_signal.emit(f"   {label} ({tw}x{th}): scale ~{needed_scale:.1f}x -> {'✅ OK' if passes else '⚠️ Requires tiling'}")
            else:
                self.log_signal.emit("   ⚠️ Skipped (upscale test did not pass)")

            # Stage 9: Waifu2x inference test
            self.stage_signal.emit("Testing Waifu2x...")
            self.log_signal.emit("[ 9/9 ]  Waifu2x Upscale Test")
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

            # Derive recommended_batch from vram / tile
            vram_mb = hw_info['vram_mb']
            if not hw_info['gpu_detected']:
                recommended_batch = 5
            elif vram_mb >= 10000:
                recommended_batch = 30
            elif vram_mb >= 6000:
                recommended_batch = 20
            elif vram_mb >= 4000:
                recommended_batch = 10
            elif vram_mb >= 2000:
                recommended_batch = 8
            else:
                recommended_batch = 5

            # Save device profile JSON
            profile = {
                "tested_at": _dt.datetime.now().isoformat(),
                "ram_mb": hw_info['ram_mb'],
                "gpu_detected": hw_info['gpu_detected'],
                "gpu_name": hw_info['gpu_name'],
                "vram_mb": hw_info['vram_mb'],
                "optimal_tile": optimal_tile,
                "recommended_batch": recommended_batch,
                "realesrgan_ok": realesrgan_ok,
                "waifu2x_ok": waifu2x_ok,
            }
            try:
                HW_PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
                HW_PROFILE_FILE.write_text(_json.dumps(profile, indent=2))
                self.log_signal.emit(f"")
                self.log_signal.emit(f"💾 Device profile saved: {HW_PROFILE_FILE.name}")
                self.log_signal.emit(f"   Tile: {optimal_tile} | Batch: {recommended_batch} | VRAM: {vram_mb} MB | RAM: {hw_info['ram_mb']} MB")
            except Exception as e:
                print(f"Failed to save device profile: {e}")

            overall_ok = realesrgan_ok and encode_ok
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
            print(f"HardwareCapTestWorker error: {e}")
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
            print(f"_detect_gpu error: {e}")
            return False

    def _probe_hardware_info(self) -> dict:
        info = {
            'ram_mb': 0,
            'gpu_detected': False,
            'gpu_name': 'Unknown',
            'vram_mb': 0,
        }

        # RAM detection
        try:
            import psutil
            info['ram_mb'] = psutil.virtual_memory().total // (1024 * 1024)
        except ImportError:
            try:
                if platform.system() == 'Windows':
                    result = subprocess.run(
                        ['wmic', 'computersystem', 'get', 'TotalPhysicalMemory'],
                        capture_output=True, text=True, timeout=5
                    )
                    lines = [l.strip() for l in result.stdout.splitlines() if l.strip().isdigit()]
                    if lines:
                        info['ram_mb'] = int(lines[0]) // (1024 * 1024)
                else:
                    with open('/proc/meminfo') as f:
                        for line in f:
                            if line.startswith('MemTotal'):
                                info['ram_mb'] = int(line.split()[1]) // 1024
                                break
            except Exception as e:
                print(f"RAM probe error: {e}")
        except Exception as e:
            print(f"RAM psutil error: {e}")

        # GPU + VRAM via nvidia-smi (NVIDIA)
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=8
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(',')
                if len(parts) >= 2:
                    info['gpu_name'] = parts[0].strip()
                    info['vram_mb'] = int(parts[1].strip())
                    info['gpu_detected'] = True
        except Exception:
            pass

        # Fallback: WMIC for AMD/Intel VRAM on Windows
        if info['vram_mb'] == 0 and platform.system() == 'Windows':
            try:
                result = subprocess.run(
                    ['wmic', 'path', 'win32_VideoController', 'get', 'AdapterRAM,Name', '/format:csv'],
                    capture_output=True, text=True, timeout=8
                )
                for line in result.stdout.splitlines():
                    if ',' in line and not line.strip().startswith('Node'):
                        parts = line.strip().split(',')
                        if len(parts) >= 3 and parts[1].strip().isdigit() and int(parts[1].strip()) > 0:
                            info['vram_mb'] = int(parts[1].strip()) // (1024 * 1024)
                            if info['gpu_name'] == 'Unknown':
                                info['gpu_name'] = parts[2].strip()
                            info['gpu_detected'] = True
                            break
            except Exception as e:
                print(f"WMIC VRAM probe error: {e}")

        # Final fallback: check if realesrgan binary runs (indicates Vulkan/GPU accessible)
        if not info['gpu_detected']:
            try:
                realesrgan_bin = get_realesrgan_path()
                if realesrgan_bin.exists():
                    result = subprocess.run(
                        [str(realesrgan_bin), '--help'],
                        capture_output=True, text=True, timeout=10,
                        cwd=str(realesrgan_bin.parent)
                    )
                    out = (result.stdout + result.stderr).lower()
                    if 'vulkan' in out or 'gpu' in out or result.returncode == 0:
                        info['gpu_detected'] = True
                        if info['gpu_name'] == 'Unknown':
                            info['gpu_name'] = 'GPU (Vulkan / non-NVIDIA)'
            except Exception:
                pass

        return info

    def _benchmark_tile_size(self, test_dir: Path, model_name: str) -> int:
        realesrgan_bin = get_realesrgan_path()
        models_dir = get_models_dir()
        test_img_path = test_dir / "tile_bench.png"
        bench_out = test_dir / "tile_bench_out.png"

        bench_img = np.zeros((256, 256, 3), dtype=np.uint8)
        cv2.imwrite(str(test_img_path), bench_img)

        for tile in [512, 256, 128, 64]:
            if bench_out.exists():
                try:
                    bench_out.unlink()
                except Exception:
                    pass
            cmd = [
                str(realesrgan_bin),
                "-i", str(test_img_path),
                "-o", str(bench_out),
                "-m", str(models_dir),
                "-n", model_name,
                "-s", "2",
                "-t", str(tile),
                "-f", "png",
            ]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                                        cwd=str(realesrgan_bin.parent))
                if result.returncode == 0 and bench_out.exists():
                    self.log_signal.emit(f"   Tile {tile}: ✅ passed")
                    return tile
                out_combined = (result.stdout + result.stderr).lower()
                if 'out of memory' in out_combined or 'oom' in out_combined:
                    self.log_signal.emit(f"   Tile {tile}: ❌ out of memory, trying smaller")
                else:
                    self.log_signal.emit(f"   Tile {tile}: ❌ failed, trying smaller")
            except subprocess.TimeoutExpired:
                self.log_signal.emit(f"   Tile {tile}: ⏱️ timeout, trying smaller")
            except Exception as e:
                self.log_signal.emit(f"   Tile {tile}: ❌ error: {e}")

        self.log_signal.emit(f"   Tile 64: using as minimum fallback")
        return 64

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
                return False, None, None
            pil_img = Image.open(str(test_out))
            pil_img.verify()
            pil_img = Image.open(str(test_out))
            return True, test_out, pil_img.size
        except Exception as e:
            print(f"_test_realesrgan error: {e}")
            return False, None, None

    def _test_ffmpeg_encode(self, test_dir: Path, frame_path: Path):
        try:
            ffmpeg_bin = get_ffmpeg_path()
            encoded_video = test_dir / "test_out.mp4"
            if encoded_video.exists():
                encoded_video.unlink()
            cmd = [
                str(ffmpeg_bin),
                "-y",
                "-loop", "1",
                "-i", str(frame_path),
                "-c:v", "libx264",
                "-t", "0.1",
                "-pix_fmt", "yuv420p",
                str(encoded_video),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                                    cwd=str(ffmpeg_bin.parent))
            return result.returncode == 0 and encoded_video.exists(), encoded_video
        except Exception as e:
            print(f"_test_ffmpeg_encode error: {e}")
            return False, None

    def _test_ffprobe_read(self, video_path: Path) -> bool:
        try:
            ffprobe_bin = get_ffprobe_path()
            cmd = [
                str(ffprobe_bin),
                "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                str(video_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15,
                                    cwd=str(ffprobe_bin.parent))
            return result.returncode == 0 and "codec_name" in result.stdout
        except Exception as e:
            print(f"_test_ffprobe_read error: {e}")
            return False

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
            print(f"_test_waifu2x error: {e}")
            return False, None

    def _test_rife(self, test_dir: Path) -> bool:
        try:
            rife_bin = get_rife_path()
            rife_in = test_dir / "rife_in"
            rife_out = test_dir / "rife_out"
            rife_in.mkdir(parents=True, exist_ok=True)
            rife_out.mkdir(parents=True, exist_ok=True)
            img = np.zeros((64, 64, 3), dtype=np.uint8)
            cv2.imwrite(str(rife_in / "00000000.png"), img)
            cv2.imwrite(str(rife_in / "00000001.png"), img)
            cmd = [
                str(rife_bin),
                "-i", str(rife_in),
                "-o", str(rife_out),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                                    cwd=str(rife_bin.parent))
            output_frames = list(rife_out.glob("*.png"))
            return result.returncode == 0 and len(output_frames) > 0
        except Exception as e:
            print(f"_test_rife error: {e}")
            return False


class VideoUpscalerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video Upscaler (RealESRGAN)")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        
        self.db = ImageTeaDB()
        self.worker: Optional[UpscaleWorker] = None
        self.hw_worker: Optional[HardwareCapTestWorker] = None
        self.hw_overlay: Optional[QWidget] = None
        self._hw_continue_btn = None
        self._hw_checklist_items = []
        self._hw_current_stage_idx = -1
        self._hw_progress_bar = None
        self._hw_log_view = None
        self._hw_stage_label = None
        self._hw_subtitle_label = None
        self.video_files: List[str] = []
        self.output_dir: Optional[str] = None
        self._last_dir = os.path.expanduser("~")
        self._config_loaded = False
        self._last_video_had_error = False
        
        self._remaining_sec = 0.0
        self._remaining_frames = 0
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
        self.apply_styles()
        self.populate_models()
        self.check_binaries()
        
        self._rem_timer = QTimer(self)
        self._rem_timer.setInterval(1000)
        self._rem_timer.timeout.connect(self._countdown_tick)
        
        self.resize(900, 600)
        self._load_config()

        if not HW_CAP_MARKER.exists():
            QTimer.singleShot(500, self._run_hw_cap_test)
    
    def _load_config(self):
        # Load from disk without triggering save callbacks until complete
        self._config_loaded = False
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)

                # temporarily block signals while we populate controls
                widgets_to_block = [
                    self.model_combo, self.scale_combo, self.batch_combo,
                    self.encoder_combo, self.decoder_combo,
                    self.remove_audio_checkbox, self.tint_r_spin,
                    self.tint_g_spin, self.tint_b_spin,
                    self.bitrate_spin, self.interpolation_checkbox,
                    self.fps_combo, self.fps_custom_spin, self.backend_combo,
                    self.output_edit
                ]
                for w in widgets_to_block:
                    w.blockSignals(True)
                try:
                    if 'model' in cfg and cfg['model']:
                        idx = self.model_combo.findText(cfg['model'])
                        if idx >= 0:
                            self.model_combo.setCurrentIndex(idx)

                    if 'scale' in cfg:
                        self.scale_combo.setCurrentText(str(cfg['scale']))

                    if 'batch' in cfg:
                        self.batch_combo.setCurrentText(str(cfg['batch']))

                    if 'encoder' in cfg:
                        idx = self.encoder_combo.findText(cfg['encoder'])
                        if idx >= 0:
                            self.encoder_combo.setCurrentIndex(idx)

                    if 'decoder' in cfg:
                        idx = self.decoder_combo.findText(cfg['decoder'])
                        if idx >= 0:
                            self.decoder_combo.setCurrentIndex(idx)

                    if 'remove_audio' in cfg:
                        self.remove_audio_checkbox.setChecked(cfg['remove_audio'])

                    if 'tint_r' in cfg:
                        self.tint_r_spin.setValue(cfg['tint_r'])
                    if 'tint_g' in cfg:
                        self.tint_g_spin.setValue(cfg['tint_g'])
                    if 'tint_b' in cfg:
                        self.tint_b_spin.setValue(cfg['tint_b'])

                    if 'bitrate' in cfg:
                        self.bitrate_spin.setValue(cfg['bitrate'])

                    if 'enable_interpolation' in cfg:
                        self.interpolation_checkbox.setChecked(bool(cfg['enable_interpolation']))
                    if 'interpolate_only' in cfg:
                        self.interpolate_only_checkbox.setChecked(bool(cfg['interpolate_only']))
                    if 'fps_preset' in cfg:
                        idx = self.fps_combo.findText(cfg['fps_preset'])
                        if idx >= 0:
                            self.fps_combo.setCurrentIndex(idx)
                    if 'fps_custom' in cfg:
                        self.fps_custom_spin.setValue(int(cfg['fps_custom']))
                    if 'backend' in cfg:
                        idx = self.backend_combo.findText(cfg['backend'])
                        if idx >= 0:
                            self.backend_combo.setCurrentIndex(idx)

                    if 'output_dir' in cfg and cfg['output_dir']:
                        self.output_edit.setText(cfg['output_dir'])
                        self.output_dir = cfg['output_dir']
                finally:
                    for w in widgets_to_block:
                        w.blockSignals(False)

                # Ensure target FPS controls reflect loaded interpolation state
                interp_on = self.interpolation_checkbox.isChecked()
                self.fps_combo.setEnabled(interp_on)
                self.fps_custom_spin.setEnabled(interp_on and self.fps_combo.currentText() == "Custom")

                # Apply the same logic as if the user toggled interpolation manually
                # so toggling via config reload does not leave FPS controls disabled.
                self._on_interpolation_toggled(self.interpolation_checkbox.checkState())

        except Exception:
            pass
        finally:
            self._config_loaded = True
    
    def _save_config(self):
        # don't write config while we're still loading previous settings
        if not getattr(self, '_config_loaded', False):
            return
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
            cfg['encoder'] = self.encoder_combo.currentText()
            cfg['decoder'] = self.decoder_combo.currentText()
            cfg['remove_audio'] = self.remove_audio_checkbox.isChecked()
            cfg['tint_r'] = self.tint_r_spin.value()
            cfg['tint_g'] = self.tint_g_spin.value()
            cfg['tint_b'] = self.tint_b_spin.value()
            cfg['bitrate'] = self.bitrate_spin.value()
            cfg['enable_interpolation'] = self.interpolation_checkbox.isChecked()
            cfg['interpolate_only'] = self.interpolate_only_checkbox.isChecked()
            cfg['fps_preset'] = self.fps_combo.currentText()
            cfg['fps_custom'] = self.fps_custom_spin.value()
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
        self.btn_load_db.setToolTip("Load video files from the Image-Tea database")
        self.btn_load_db.clicked.connect(self.load_from_database)
        toolbar_layout.addWidget(self.btn_load_db)
        
        self.btn_load_folder = QPushButton(qta.icon('fa6s.folder-open'), " Load Folder")
        self.btn_load_folder.setToolTip("Load all video files from a folder")
        self.btn_load_folder.clicked.connect(self.load_from_folder)
        toolbar_layout.addWidget(self.btn_load_folder)
        
        self.btn_load_file = QPushButton(qta.icon('fa6s.file-video'), " Load File")
        self.btn_load_file.setToolTip("Load a single video file")
        self.btn_load_file.clicked.connect(self.load_single_file)
        toolbar_layout.addWidget(self.btn_load_file)
        
        self.btn_clear = QPushButton(qta.icon('fa6s.trash'), " Clear")
        self.btn_clear.setToolTip("Clear the video list")
        self.btn_clear.clicked.connect(self.clear_videos)
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
        self.batch_combo.setToolTip("Frames per batch (higher = faster but more VRAM)")
        self.batch_combo.currentTextChanged.connect(lambda: self._save_config())
        scale_row.addWidget(self.batch_combo)

        self.interpolate_only_checkbox = QCheckBox("Interpolate Only")
        self.interpolate_only_checkbox.setToolTip("Only run frame interpolation (RIFE) and skip the upscaling step")
        self.interpolate_only_checkbox.stateChanged.connect(lambda _: self._save_config())
        scale_row.addWidget(self.interpolate_only_checkbox)

        scale_row.addStretch()
        tab_model_layout.addLayout(scale_row)

        tint_row = QHBoxLayout()
        tint_row.setSpacing(4)
        tint_row.addWidget(QLabel("Tint R:"))
        self.tint_r_spin = QSpinBox()
        self.tint_r_spin.setRange(-50, 50)
        self.tint_r_spin.setValue(0)
        self.tint_r_spin.setToolTip("Red channel adjustment (-50 to +50)")
        self.tint_r_spin.valueChanged.connect(self._on_tint_changed)
        tint_row.addWidget(self.tint_r_spin)
        tint_row.addWidget(QLabel("G:"))
        self.tint_g_spin = QSpinBox()
        self.tint_g_spin.setRange(-50, 50)
        self.tint_g_spin.setValue(0)
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
        tab_model_layout.addLayout(tint_row)
        tab_model_layout.addStretch()
        settings_tabs.addTab(tab_model, "Model & Scale")

        tab_enc = QWidget()
        tab_enc_layout = QVBoxLayout(tab_enc)
        tab_enc_layout.setSpacing(4)
        tab_enc_layout.setContentsMargins(8, 6, 8, 6)

        enc_row = QHBoxLayout()
        enc_row.setSpacing(4)
        enc_row.addWidget(QLabel("Encoder:"))
        self.encoder_combo = QComboBox()
        self.encoder_combo.addItems([
            "CPU (x264)",
            "GPU - NVIDIA (NVENC H.264)",
            "GPU - NVIDIA (NVENC HEVC) - High Res",
            "GPU - AMD (AMF)",
            "GPU - Intel (QSV)"
        ])
        self.encoder_combo.setCurrentText("GPU - NVIDIA (NVENC H.264)")
        self.encoder_combo.setToolTip("Video encoder for merging")
        self.encoder_combo.currentTextChanged.connect(lambda: self._save_config())
        enc_row.addWidget(self.encoder_combo, 1)
        tab_enc_layout.addLayout(enc_row)

        dec_row = QHBoxLayout()
        dec_row.setSpacing(4)
        dec_row.addWidget(QLabel("Decoder:"))
        self.decoder_combo = QComboBox()
        self.decoder_combo.addItems([
            "Auto (Recommended)",
            "NVIDIA CUDA",
            "Intel Quick Sync",
            "DirectX 11",
            "CPU Only"
        ])
        self.decoder_combo.setCurrentText("Auto (Recommended)")
        self.decoder_combo.setToolTip("Hardware acceleration for extraction")
        self.decoder_combo.currentTextChanged.connect(lambda: self._save_config())
        dec_row.addWidget(self.decoder_combo, 1)
        dec_row.addWidget(QLabel("Bitrate:"))
        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(1, 200)
        self.bitrate_spin.setValue(20)
        self.bitrate_spin.setSuffix(" Mbps")
        self.bitrate_spin.setToolTip("Output video bitrate in Mbps (1-200)")
        self.bitrate_spin.valueChanged.connect(lambda: self._save_config())
        dec_row.addWidget(self.bitrate_spin)
        tab_enc_layout.addLayout(dec_row)

        checks_row = QHBoxLayout()
        checks_row.setSpacing(8)
        self.remove_audio_checkbox = QCheckBox("Remove Audio")
        self.remove_audio_checkbox.setToolTip("Remove audio track from output video")
        self.remove_audio_checkbox.stateChanged.connect(lambda: self._save_config())
        checks_row.addWidget(self.remove_audio_checkbox)
        self.retry_failed_checkbox = QCheckBox("Retry Failed Only")
        self.retry_failed_checkbox.setToolTip("Only process files that failed in previous run")
        checks_row.addWidget(self.retry_failed_checkbox)
        checks_row.addStretch()
        tab_enc_layout.addLayout(checks_row)
        tab_enc_layout.addStretch()
        settings_tabs.addTab(tab_enc, "Encoding")

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

        tab_rife = QWidget()
        tab_rife_layout = QVBoxLayout(tab_rife)
        tab_rife_layout.setSpacing(4)
        tab_rife_layout.setContentsMargins(8, 6, 8, 6)

        rife_enable_row = QHBoxLayout()
        rife_enable_row.setSpacing(4)
        self.interpolation_checkbox = QCheckBox("Enable RIFE Interpolation")
        self.interpolation_checkbox.setToolTip("Use RIFE to increase frame rate before upscaling")
        self.interpolation_checkbox.stateChanged.connect(self._on_interpolation_toggled)
        rife_enable_row.addWidget(self.interpolation_checkbox)
        rife_enable_row.addStretch()
        tab_rife_layout.addLayout(rife_enable_row)

        fps_row = QHBoxLayout()
        fps_row.setSpacing(4)
        fps_row.addWidget(QLabel("Target FPS:"))
        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["24", "30", "60", "120", "Custom"])
        self.fps_combo.setCurrentText("60")
        self.fps_combo.setEnabled(False)
        self.fps_combo.setToolTip("Target frame rate after interpolation")
        self.fps_combo.currentTextChanged.connect(self._on_fps_combo_changed)
        self.fps_combo.currentTextChanged.connect(lambda: self._save_config())
        fps_row.addWidget(self.fps_combo)
        self.fps_custom_spin = QSpinBox()
        self.fps_custom_spin.setRange(1, 240)
        self.fps_custom_spin.setValue(60)
        self.fps_custom_spin.setSuffix(" fps")
        self.fps_custom_spin.setEnabled(False)
        self.fps_custom_spin.setToolTip("Custom target FPS (1-240)")
        self.fps_custom_spin.valueChanged.connect(lambda: self._save_config())
        fps_row.addWidget(self.fps_custom_spin)
        fps_row.addStretch()
        tab_rife_layout.addLayout(fps_row)
        tab_rife_layout.addStretch()
        settings_tabs.addTab(tab_rife, "Frame Interpolation (RIFE)")

        main_layout.addWidget(settings_tabs)
        
        splitter = QSplitter(Qt.Horizontal)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        
        left_layout.addWidget(QLabel("Loaded Videos:"))
        self.video_list = FileDropListWidget()
        self.video_list.setMinimumWidth(300)
        self.video_list.files_dropped.connect(self._on_files_dropped)
        self.video_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.video_list.customContextMenuRequested.connect(self._show_video_context_menu)
        left_layout.addWidget(self.video_list)
        
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
        self.output_edit.setPlaceholderText("Default: temp/video_upscaler/results")
        self.output_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.output_edit.setMinimumWidth(0)
        self.output_edit.textChanged.connect(self._on_output_text_changed)
        self.output_edit.editingFinished.connect(self._save_config)
        self.output_edit.setAcceptDrops(True)
        self.output_edit.dragEnterEvent = DragDropPathMixin.make_drag_enter_handler(self.output_edit)
        self.output_edit.dropEvent = DragDropPathMixin.make_drop_handler(self.output_edit, 'output', self._on_output_dropped)
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
        
        self.frames_label = QLabel("Frames: 0/0")
        self.frames_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.frames_label)
        
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
    
    def apply_styles(self):
        pass
    
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
            defaults = ["realesr-animevideov3", "realesrgan-x4plus", "realesrgan-x4plus-anime"]
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
        ffmpeg = get_ffmpeg_path()
        realesrgan = get_realesrgan_path()
        models_dir = get_models_dir()
        
        if not ffmpeg.exists():
            missing.append(f"FFmpeg not found at: {ffmpeg}")
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
            self.log_viewer.append(f"❌ RealESRGAN executable missing: {self.realesrgan_bin}")
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
                self.log_viewer.append(f"❌ OS error launching RealESRGAN: permission issue on {self.realesrgan_bin}")
                return False
            if not os.access(self.realesrgan_bin, os.X_OK):
                print(f"System Error: RealESRGAN not executable after chmod: {self.realesrgan_bin}")
                self.log_viewer.append(f"❌ OS error launching RealESRGAN: permission denied: {self.realesrgan_bin}")
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
        videos = self.db.get_all_files()
        video_extensions = ('.mp4', '.mov', '.mkv', '.avi', '.webm', '.wmv', '.flv')
        video_files = [f[1] for f in videos if f[1].lower().endswith(video_extensions)]
        
        if not video_files:
            QMessageBox.information(self, "No Videos", "No video files found in the database.")
            return
        
        self.video_files = video_files
        self._update_video_list()
        self.log_viewer.append(f"📂 Loaded {len(video_files)} videos from database")
    
    def load_from_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Video Folder", self._last_dir)
        if not folder:
            return
        self._last_dir = folder
        video_extensions = ('.mp4', '.mov', '.mkv', '.avi', '.webm', '.wmv', '.flv')
        folder_path = Path(folder)
        video_files = [str(f) for f in folder_path.glob("*") if f.suffix.lower() in video_extensions]
        
        if not video_files:
            QMessageBox.information(self, "No Videos", "No video files found in the selected folder.")
            return
        
        self.video_files = video_files
        self._update_video_list()
        self.log_viewer.append(f"📂 Loaded {len(video_files)} videos from folder: {folder}")
    
    def load_single_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", self._last_dir,
            "Video Files (*.mp4 *.mov *.mkv *.avi *.webm *.wmv *.flv);;All Files (*)"
        )
        if not path:
            return
        self._last_dir = os.path.dirname(path)
        if path not in self.video_files:
            self.video_files.append(path)
        self._update_video_list()
        self.log_viewer.append(f"📁 Added: {path}")

    def _on_files_dropped(self, paths: list):
        self.add_videos(paths)

    def add_videos(self, paths: list):
        allowed = ('.mp4', '.mov', '.mkv', '.avi', '.webm', '.wmv', '.flv')
        added = 0
        for p in paths:
            try:
                pp = str(Path(p))
                if not Path(pp).exists():
                    continue
                if not pp.lower().endswith(allowed):
                    continue
                if pp not in self.video_files:
                    self.video_files.append(pp)
                    added += 1
            except Exception:
                continue
        if added:
            self._update_video_list()
            self.log_viewer.append(f"📥 Added {added} video(s) via drag-and-drop")

    def clear_videos(self):
        self.video_files = []
        self._update_video_list()
        self.log_viewer.append("🗑️ Cleared video list")
    
    def _update_video_list(self):
        self.video_list.clear()
        for video_path in self.video_files:
            item = QListWidgetItem(qta.icon('fa6s.file-video'), Path(video_path).name)
            item.setData(Qt.UserRole, video_path)
            item.setToolTip(video_path)
            self.video_list.addItem(item)
        self.files_label.setText(f"Files: {len(self.video_files)}")
    
    def _show_video_context_menu(self, pos):
        item = self.video_list.itemAt(pos)
        if not item:
            return
        video_path = item.data(Qt.UserRole)
        menu = QMenu(self)
        retry_action = menu.addAction(qta.icon('fa6s.rotate-right'), "Retry This File")
        remove_action = menu.addAction(qta.icon('fa6s.trash'), "Remove from List")
        action = menu.exec(self.video_list.mapToGlobal(pos))
        if action == retry_action:
            self._retry_single_file(video_path)
        elif action == remove_action:
            if video_path in self.video_files:
                self.video_files.remove(video_path)
                self._update_video_list()
                self.log_viewer.append(f"🗑️ Removed: {Path(video_path).name}")
    
    def _retry_single_file(self, video_path: str):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Process Running", "Please wait for current process to finish.")
            return
        if video_path not in self.video_files:
            self.video_files.append(video_path)
            self._update_video_list()
        self._run_process_with_files([video_path])

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

    def _on_output_dropped(self, path):
        """Handle folder dropped onto output field."""
        self._last_dir = path
        self.output_dir = path
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
        
        if not self.video_files:
            QMessageBox.warning(self, "No Videos", "Please load some video files first.")
            return
        
        if self.retry_failed_checkbox.isChecked():
            if not self._failed_files:
                QMessageBox.information(self, "No Failed Files", "No failed files to retry. Run upscale first or uncheck 'Retry Failed Only'.")
                return
            files_to_process = [f for f in self._failed_files if f in self.video_files]
            if not files_to_process:
                QMessageBox.information(self, "No Failed Files", "Failed files are no longer in the list.")
                return
            self.log_viewer.append(f"🔄 Retrying {len(files_to_process)} failed file(s)...")
        else:
            files_to_process = self.video_files[:]
        
        self._run_process_with_files(files_to_process)

    def _detect_video_height(self, video_path: str):
        try:
            ffprobe = get_ffprobe_path()
            if not ffprobe.exists():
                return None
            cmd = [
                str(ffprobe), "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=height",
                "-of", "csv=p=0",
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip())
        except Exception as e:
            print(f"_detect_video_height error: {e}")
        return None

    def _detect_video_dimensions(self, video_path: str):
        try:
            ffprobe = get_ffprobe_path()
            if not ffprobe.exists():
                return None, None
            cmd = [
                str(ffprobe), "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0",
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(',')
                if len(parts) >= 2:
                    return int(parts[0]), int(parts[1])
        except Exception as e:
            print(f"_detect_video_dimensions error: {e}")
        return None, None

    def _on_interpolation_toggled(self, state):
        enabled = bool(state)
        self.fps_combo.setEnabled(enabled)
        self.fps_custom_spin.setEnabled(enabled and self.fps_combo.currentText() == "Custom")
        self._save_config()

    def _on_fps_combo_changed(self, text):
        self.fps_custom_spin.setEnabled(self.interpolation_checkbox.isChecked() and text == "Custom")

    def _run_hw_cap_test(self):
        self._show_hw_overlay()
        self.hw_worker = HardwareCapTestWorker(self)
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

        for stage_name in ["Tool Binaries", "Hardware Probe", "Model Files", "RealESRGAN Upscale Test", "FFmpeg Encode Test", "Output Video Readability", "RIFE Binary", "Progressive Scale Capability", "Waifu2x Upscale Test"]:
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
        self.log_viewer.append("🚀 Starting upscale process...")
        self.log_viewer.append("")
        
        self._remaining_sec = 0.0
        self._remaining_frames = 0
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
        encoder = self.encoder_combo.currentText()
        hwaccel = self.decoder_combo.currentText()
        remove_audio = self.remove_audio_checkbox.isChecked()
        output_dir = self.output_edit.text().strip() if self.output_edit.text().strip() else None
        resume_mode = self.retry_failed_checkbox.isChecked()
        bitrate_mbps = self.bitrate_spin.value()
        enable_interpolation = self.interpolation_checkbox.isChecked()
        if self.fps_combo.currentText() == "Custom":
            target_fps = self.fps_custom_spin.value()
        else:
            target_fps = int(self.fps_combo.currentText())

        res_preset = self.resolution_preset_combo.currentText()
        preset_dims = {
            "HD (1280×720)": (1280, 720),
            "FullHD (1920×1080)": (1920, 1080),
            "2K (2560×1440)": (2560, 1440),
            "4K (3840×2160)": (3840, 2160),
        }
        target_crop_size = None
        if res_preset in preset_dims:
            target_w, target_h = preset_dims[res_preset]
            src_w, src_h = self._detect_video_dimensions(files_to_process[0])
            if src_w and src_h and src_w > 0 and src_h > 0:
                is_vertical = src_h > src_w
                if is_vertical:
                    target_w, target_h = target_h, target_w
                orientation = "vertical" if is_vertical else "horizontal"
                self.log_viewer.append(f"📐 Preset '{res_preset}' [{orientation}] → post-process output to {target_w}x{target_h}")
                target_crop_size = (target_w, target_h)

        backend_text = self.backend_combo.currentText()
        if backend_text == "GPU (Force)":
            gpu_id = 0
        elif backend_text == "CPU (Force)":
            gpu_id = -1
        else:
            gpu_id = -2

        self.worker = UpscaleWorker(
            files_to_process, model, scale, batch_size, encoder, hwaccel, output_dir, remove_audio,
            self.tint_adjustment, resume_mode, bitrate_mbps,
            enable_interpolation=enable_interpolation, target_fps=target_fps, gpu_id=gpu_id,
            interpolate_only=self.interpolate_only_checkbox.isChecked(),
            target_crop_size=target_crop_size
        )
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.stats_signal.connect(self.update_stats)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.video_completed_signal.connect(self.on_video_completed)
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
        self.encoder_combo.setEnabled(not running)
        self.decoder_combo.setEnabled(not running)
        self.remove_audio_checkbox.setEnabled(not running)
        self.retry_failed_checkbox.setEnabled(not running)
        self.bitrate_spin.setEnabled(not running)
        self.interpolation_checkbox.setEnabled(not running)
        self.backend_combo.setEnabled(not running)
        if not running:
            interp_on = self.interpolation_checkbox.isChecked()
            self.fps_combo.setEnabled(interp_on)
            self.fps_custom_spin.setEnabled(interp_on and self.fps_combo.currentText() == "Custom")
        else:
            self.fps_combo.setEnabled(False)
            self.fps_custom_spin.setEnabled(False)
        self.output_edit.setEnabled(not running)
        self.btn_browse_output.setEnabled(not running)
        self.btn_paste_output.setEnabled(not running)
        self.btn_open_output.setEnabled(not running)
        self.btn_clear_output.setEnabled(not running)
        
        if running:
            self.run_button.setText(" STOP")
            self.run_button.setIcon(qta.icon('fa6s.stop'))
            
            # Apply red/danger styling for stop button using error color
            from PySide6.QtGui import QColor
            error_base = theme.get_color('error')
            error_hover = QColor(error_base).darker(115).name()
            error_pressed = QColor(error_base).darker(130).name()
            white = theme.get_color('white')
            
            self.run_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {error_base};
                    color: {white};
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: {error_hover};
                }}
                QPushButton:pressed {{
                    background-color: {error_pressed};
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
        try:
            m = re.search(r'Processing video (\d+)/(\d+)', message)
            if m:
                idx = int(m.group(1))
                if idx > 1 and not getattr(self, '_last_video_had_error', False):
                    self.log_viewer.clear()
        except Exception:
            pass

        self.log_viewer.append(message)
        self.log_viewer.verticalScrollBar().setValue(
            self.log_viewer.verticalScrollBar().maximum()
        )
    
    def update_stats(self, processed: int, total: int, elapsed: float, remaining: int, remaining_sec: float):
        self._processed = processed
        self._total = total
        self._elapsed = elapsed
        self._remaining_frames = remaining
        self._remaining_sec = max(0.0, float(remaining_sec))
        
        if self.worker is not None and self.worker.isRunning() and not self._rem_timer.isActive():
            self._rem_timer.start()
        
        self._update_stats_label()
    
    def _update_stats_label(self):
        elapsed_s = self._fmt_seconds(self._elapsed)
        remaining_time_s = self._fmt_seconds(self._remaining_sec)
        self.elapsed_label.setText(f"Elapsed: {elapsed_s}")
        self.eta_label.setText(f"ETA: {remaining_time_s}")
        self.frames_label.setText(f"Frames: {self._processed}/{self._total}")
        self.remaining_label.setText(f"Remaining: {self._remaining_frames}")
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
        if worker_finished and self._remaining_sec <= 0 and self._remaining_frames <= 0 and self._rem_timer.isActive():
            self._rem_timer.stop()
    
    def on_video_completed(self, video_path: str, success: bool):
        self._last_video_had_error = not success
        if success:
            self._success_count += 1
            if video_path in self._failed_files:
                self._failed_files.remove(video_path)
        else:
            self._failed_count += 1
            if video_path not in self._failed_files:
                self._failed_files.append(video_path)
        self._update_stats_label()
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            if item.data(Qt.UserRole) == video_path:
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
        self._remaining_frames = 0
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
