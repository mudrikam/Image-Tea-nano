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
    QListWidgetItem, QFileDialog, QSizePolicy, QMessageBox, QLineEdit, QApplication, QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize
from PIL import Image
from PySide6.QtGui import QIcon, QFont
import qtawesome as qta
import traceback

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


def get_models_dir():
    return Path(BASE_PATH) / "tools" / "realesrgan" / "models"


TEMP_DIR = Path(BASE_PATH) / "temp" / "video_upscaler"
TMP_FRAMES_DIR = TEMP_DIR / "tmp_frames"
OUT_FRAMES_DIR = TEMP_DIR / "out_frames"
BATCH_INPUT_DIR = TEMP_DIR / "batch_input"
BATCH_OUTPUT_DIR = TEMP_DIR / "batch_output"
RESULTS_DIR = TEMP_DIR / "results"
CONFIG_FILE = Path(BASE_PATH) / "configs" / "video_upscale_config.json"


class UpscaleWorker(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int)
    stats_signal = Signal(int, int, float, int, float)
    finished_signal = Signal(bool, str)
    video_completed_signal = Signal(str, bool)

    def __init__(self, video_paths: List[str], model: str, scale: int, batch_size: int = 10, 
                 encoder: str = "CPU", hwaccel: str = "Auto", output_dir: str = None, remove_audio: bool = False):
        super().__init__()
        self.video_paths = video_paths
        self.model = model
        self.scale = scale
        self.batch_size = batch_size
        self.encoder = encoder
        self.hwaccel = hwaccel
        self.output_dir = output_dir
        self.remove_audio = remove_audio
        self._stop_requested = False
        
        self.ffmpeg_bin = get_ffmpeg_path()
        self.ffprobe_bin = get_ffprobe_path()
        self.realesrgan_bin = get_realesrgan_path()
        self.models_dir = get_models_dir()
        
        from dialogs.tools.upscaler_model_manager_dialog import UpscalerModelManager
        self.model_manager = UpscalerModelManager()
        model_info = self.model_manager.get_model_by_name(model)
        self.model_type = model_info['type'] if model_info else 'ncnn'
        self.model_info = model_info

    def stop(self):
        self._stop_requested = True

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
                        output = (output * 255.0).round().astype(np.uint8)
                        output = cv2.cvtColor(output, cv2.COLOR_RGB2BGR)
                        cv2.imwrite(output_path, output, [cv2.IMWRITE_PNG_COMPRESSION, 0])
                    return True
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
            fps_str = result.stdout.strip()
            if '/' in fps_str:
                num, den = fps_str.split('/')
                fps = float(num) / float(den)
            else:
                fps = float(fps_str)
            self.log_signal.emit(f"   Detected FPS: {fps:.2f}")
            
            self.log_signal.emit("🧹 Cleaning old frames...")
            for f in TMP_FRAMES_DIR.glob("*"):
                f.unlink()
            for f in OUT_FRAMES_DIR.glob("*"):
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
            
            self.progress_signal.emit(0)
            self.stats_signal.emit(0, frame_count, 0.0, frame_count, 0.0)
            
            self.log_signal.emit(f"")
            self.log_signal.emit(f"🚀 PHASE 2/3: UPSCALING FRAMES")
            self.log_signal.emit(f"   🧩 Model: {self.model} (Type: {self.model_type.upper()}) | Scale: {self.scale}x | Batch: {self.batch_size}")
            
            for f in OUT_FRAMES_DIR.glob("*"):
                f.unlink()
            
            frame_files = sorted(TMP_FRAMES_DIR.glob("*.png"))
            total_frames = len(frame_files)
            start_time = time.time()
            processed = 0
            
            if self.model_type in ['pth', 'onnx']:
                backend = self._init_upscaler_backend()
                if backend is None:
                    self.log_signal.emit("❌ Failed to initialize backend")
                    return False
                
                self.log_signal.emit(f"   Processing {total_frames} frames with {self.model_type.upper()} backend")
                
                for idx, frame_file in enumerate(frame_files):
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
                    
                    processed = idx + 1
                    elapsed = time.time() - start_time
                    remaining = max(0, total_frames - processed)
                    eta = 0.0
                    if processed > 0:
                        rate = elapsed / processed
                        eta = rate * remaining
                        progress_pct = int((processed / total_frames) * 100)
                        self.progress_signal.emit(min(100, progress_pct))
                    
                    self.stats_signal.emit(processed, total_frames, elapsed, remaining, float(eta))
                    
                    if (idx + 1) % 10 == 0 or (idx + 1) == total_frames:
                        self.log_signal.emit(f"   Progress: {processed}/{total_frames} frames ({progress_pct}%)")
                
                elapsed = time.time() - start_time
                self.progress_signal.emit(100)
                self.log_signal.emit(f"✅ PHASE 2 COMPLETE: Upscaled {total_frames} frames in {elapsed:.2f}s")
            
            else:
                model_to_use = self.model
                if re.search(r"x([234])", model_to_use, re.IGNORECASE):
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
                
                num_batches = (total_frames + self.batch_size - 1) // self.batch_size
                self.log_signal.emit(f"   🔁 Processing {num_batches} batches with NCNN backend")
                
                for batch_idx in range(num_batches):
                    if self._stop_requested:
                        return False
                    
                    start_idx = batch_idx * self.batch_size
                    end_idx = min(start_idx + self.batch_size, total_frames)
                    batch_frames = frame_files[start_idx:end_idx]
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
                        "-t", "0",
                    "-f", "png",
                ]
                
                    input_count = len(list(BATCH_INPUT_DIR.glob("*.png")))
                    self.log_signal.emit(f"   🔁 Running RealESRGAN on batch {batch_num}/{num_batches} ({batch_frame_count} frames)")

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
                        # Preflight permission check
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
                        if out_file.exists():
                            try:
                                shutil.copy2(out_file, OUT_FRAMES_DIR / frame_file.name)
                                copied_count += 1
                            except Exception as e:
                                self.log_signal.emit(f"   ❗ Failed to copy output {out_file.name}: {e}")
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
            
            self.progress_signal.emit(0)
            self.log_signal.emit(f"")
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
            
            enc_opts = {
                "h264_nvenc": ["-preset", "p7", "-tune", "hq", "-rc", "vbr", "-cq", "19", "-b:v", "0"],
                "hevc_nvenc": ["-preset", "p7", "-tune", "hq", "-rc", "vbr", "-cq", "21", "-b:v", "0"],
                "h264_amf": ["-quality", "quality", "-rc", "vbr_latency", "-qp_i", "19", "-qp_p", "19"],
                "h264_qsv": ["-preset", "veryslow", "-global_quality", "19"],
                "libx264": ["-preset", "medium", "-crf", "18"],
            }

            detected = self._detect_ffmpeg_encoders()
            try_encoders = self._preferred_encoder_order(video_codec)
            tried = []
            successful = False

            for try_codec in try_encoders:
                tried.append(try_codec)
                self.log_signal.emit(f"   🎛️ Trying encoder: {try_codec}")

                merge_cmd = [
                    str(self.ffmpeg_bin),
                    "-framerate", str(fps),
                    "-start_number", "1",
                    "-i", str(OUT_FRAMES_DIR / "frame%08d.png"),
                ]

                if not self.remove_audio:
                    merge_cmd.extend([
                        "-i", video_path,
                        "-map", "0:v:0",
                        "-map", "1:a:0?",
                        "-c:a", "copy",
                    ])
                else:
                    merge_cmd.extend([
                        "-map", "0:v:0",
                        "-an",
                    ])

                if self.remove_audio:
                    self.log_signal.emit("   🔇 Audio will be removed from output")

                merge_cmd.extend(["-c:v", try_codec])

                opt_list = enc_opts.get(try_codec, ["-preset", "medium", "-crf", "18"])
                merge_cmd.extend(opt_list)

                merge_cmd.extend([
                    "-r", str(fps),
                    "-pix_fmt", "yuv420p",
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
                last_err = "".join(stderr_lines[-20:])
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


class VideoUpscalerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video Upscaler (RealESRGAN)")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        
        self.db = ImageTeaDB()
        self.worker: Optional[UpscaleWorker] = None
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
                    
                    encoder = config.get('encoder', '')
                    if encoder and self.encoder_combo.findText(encoder) >= 0:
                        self.encoder_combo.setCurrentText(encoder)
                    
                    decoder = config.get('decoder', '')
                    if decoder and self.decoder_combo.findText(decoder) >= 0:
                        self.decoder_combo.setCurrentText(decoder)
                    
                    remove_audio = config.get('remove_audio', False)
                    self.remove_audio_checkbox.setChecked(bool(remove_audio))
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
            cfg['encoder'] = self.encoder_combo.currentText()
            cfg['decoder'] = self.decoder_combo.currentText()
            cfg['remove_audio'] = self.remove_audio_checkbox.isChecked()

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
        
        toolbar_layout.addStretch()
        
        main_layout.addLayout(toolbar_layout)
        
        settings_layout_row1 = QHBoxLayout()
        settings_layout_row1.setSpacing(8)
        
        settings_layout_row1.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(180)
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        self.model_combo.currentTextChanged.connect(lambda: self._save_config())
        settings_layout_row1.addWidget(self.model_combo)
        
        self.btn_model_manager = QPushButton(qta.icon('fa6s.gear'), "")
        self.btn_model_manager.setToolTip("Open Model Manager")
        self.btn_model_manager.clicked.connect(self._open_model_manager)
        settings_layout_row1.addWidget(self.btn_model_manager)
        
        settings_layout_row1.addWidget(QLabel("Scale:"))
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["2", "3", "4"])
        self.scale_combo.setCurrentText("2")
        self.scale_combo.currentTextChanged.connect(lambda: self._save_config())
        settings_layout_row1.addWidget(self.scale_combo)
        
        settings_layout_row1.addWidget(QLabel("Batch:"))
        self.batch_combo = QComboBox()
        self.batch_combo.addItems(["5", "10", "15", "20", "25", "30", "35", "40", "45", "50"])
        self.batch_combo.setCurrentText("10")
        self.batch_combo.setToolTip("Frames per batch (higher = faster but more VRAM)")
        self.batch_combo.currentTextChanged.connect(lambda: self._save_config())
        settings_layout_row1.addWidget(self.batch_combo)
        
        self.remove_audio_checkbox = QCheckBox("Remove Audio")
        self.remove_audio_checkbox.setToolTip("Remove audio track from output video")
        self.remove_audio_checkbox.stateChanged.connect(lambda: self._save_config())
        settings_layout_row1.addWidget(self.remove_audio_checkbox)
        
        settings_layout_row1.addStretch()
        
        main_layout.addLayout(settings_layout_row1)
        
        settings_layout_row2 = QHBoxLayout()
        settings_layout_row2.setSpacing(8)
        
        settings_layout_row2.addWidget(QLabel("Encoder:"))
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
        settings_layout_row2.addWidget(self.encoder_combo)
        
        settings_layout_row2.addWidget(QLabel("Decoder:"))
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
        settings_layout_row2.addWidget(self.decoder_combo)
        
        settings_layout_row2.addStretch()
        
        main_layout.addLayout(settings_layout_row2)
        
        splitter = QSplitter(Qt.Horizontal)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        
        left_layout.addWidget(QLabel("Loaded Videos:"))
        self.video_list = FileDropListWidget()
        self.video_list.setMinimumWidth(300)
        self.video_list.files_dropped.connect(self._on_files_dropped)
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
        self.output_edit.textChanged.connect(lambda text: setattr(self, 'output_dir', text.strip() if text.strip() else None))
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
            self.log_viewer.append(f"✅ Found {len(models)} model(s) (NCNN: {ncnn_count}, PTH: {pth_count}, ONNX: {onnx_count})")
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
            self.log_viewer.append("✅ All binaries found")
            self.log_viewer.append(f"   FFmpeg: {ffmpeg}")
            self.log_viewer.append(f"   RealESRGAN: {realesrgan}")
            self.log_viewer.append("")

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
        m = re.search(r"x([234])", model_name, re.IGNORECASE)
        if m:
            s = m.group(1)
            self.scale_combo.setCurrentText(s)
            self.scale_combo.setEnabled(False)
            self.log_viewer.append(f"🔒 Scale auto-set to {s}x from model {model_name}")
        else:
            self.scale_combo.setEnabled(True)
    
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
        self._update_stats_label()
        
        model = self.model_combo.currentText()
        scale = int(self.scale_combo.currentText())
        batch_size = int(self.batch_combo.currentText())
        encoder = self.encoder_combo.currentText()
        hwaccel = self.decoder_combo.currentText()
        remove_audio = self.remove_audio_checkbox.isChecked()
        output_dir = self.output_edit.text().strip() if self.output_edit.text().strip() else None
        
        self.worker = UpscaleWorker(
            self.video_files, model, scale, batch_size, encoder, hwaccel, output_dir, remove_audio
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
        self.model_combo.setEnabled(not running)
        self.scale_combo.setEnabled(not running and not self._is_scale_locked())
        self.batch_combo.setEnabled(not running)
        self.encoder_combo.setEnabled(not running)
        self.decoder_combo.setEnabled(not running)
        self.remove_audio_checkbox.setEnabled(not running)
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
        for i in range(self.video_list.count()):
            item = self.video_list.item(i)
            if item.data(Qt.UserRole) == video_path:
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
        self._remaining_frames = 0
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
