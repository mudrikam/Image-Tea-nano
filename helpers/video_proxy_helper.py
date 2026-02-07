import os
import subprocess
import json
import time
import threading
import shutil
import platform
from config import BASE_PATH
from PySide6.QtWidgets import QApplication
from dialogs.video_proxy_dialog import VideoProxyDialog
from PySide6.QtCore import QThread, Signal

_video_proxy_invoker = None

def _resolve_binary(name):
    system = platform.system()
    tool_dir = os.path.join(BASE_PATH, "tools", "ffmpeg")
    if system == "Windows":
        candidate = os.path.join(tool_dir, f"{name}.exe")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
        system_path = shutil.which(name)
        if system_path:
            return system_path
        return candidate
    system_path = shutil.which(name)
    return system_path if system_path else name

FFMPEG_PATH = _resolve_binary("ffmpeg")
FFPROBE_PATH = _resolve_binary("ffprobe")

VIDEO_EXTENSIONS = {'.mp4', '.mpeg', '.mov', '.avi', '.flv', '.mpg', '.webm', '.wmv', '.3gp', '.3gpp'}

def get_video_proxy_presets():
    config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg["video_proxy_presets"]

def ensure_video_temp_folder():
    temp_folder = os.path.join(BASE_PATH, "temp", "videos")
    os.makedirs(temp_folder, exist_ok=True)
    return temp_folder

def cleanup_video_temp_folder():
    temp_folder = ensure_video_temp_folder()
    for filename in os.listdir(temp_folder):
        file_path = os.path.join(temp_folder, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error cleaning video temp file {file_path}: {e}")

def get_video_proxy_setting():
    config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config["video_proxy_setting"]

def get_video_info(video_path):
    # Prefer ffprobe for structured metadata parsing if available
    try:
        ffprobe_exec = None
        if platform.system() == "Windows":
            if os.path.isfile(FFPROBE_PATH) and os.access(FFPROBE_PATH, os.X_OK):
                ffprobe_exec = FFPROBE_PATH
        else:
            ffprobe_exec = shutil.which("ffprobe")

        if ffprobe_exec:
            cmd = [
                ffprobe_exec,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                video_path
            ]
            result = _run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=10)
            if result and getattr(result, 'stdout', None):
                try:
                    info = json.loads(result.stdout)
                    duration = None
                    resolution = None
                    bitrate = None
                    fmt = info.get('format', {})
                    streams = info.get('streams', [])
                    if fmt.get('duration'):
                        try:
                            duration = float(fmt.get('duration'))
                        except Exception:
                            duration = None
                    if fmt.get('bit_rate'):
                        bitrate = fmt.get('bit_rate')
                    for s in streams:
                        if s.get('codec_type') == 'video':
                            w = s.get('width')
                            h = s.get('height')
                            if w and h:
                                resolution = f"{w}x{h}"
                            if not bitrate and s.get('bit_rate'):
                                bitrate = s.get('bit_rate')
                            break
                    return {
                        'duration': duration,
                        'resolution': resolution,
                        'bitrate': bitrate,
                        'size': os.path.getsize(video_path)
                    }
                except Exception as e:
                    print(f"[VideoProxy] ffprobe parse error: {e}")

        # Fallback: use ffmpeg -i parsing
        ffmpeg_exec = None
        if platform.system() == "Windows":
            if os.path.isfile(FFMPEG_PATH) and os.access(FFMPEG_PATH, os.X_OK):
                ffmpeg_exec = FFMPEG_PATH
        else:
            ffmpeg_exec = shutil.which("ffmpeg")

        if not ffmpeg_exec:
            print(f"[VideoProxy] ffmpeg/ffprobe not available for parsing: {video_path}")
            return None

        cmd = [ffmpeg_exec, "-i", video_path, "-hide_banner"]
        result = _run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        output = result.stdout

        duration = None
        resolution = None
        bitrate = None
        for line in output.split('\n'):
            if "Duration:" in line:
                parts = line.split("Duration:")[1].split(",")[0].strip()
                try:
                    h, m, s = parts.split(":")
                    duration = int(h) * 3600 + int(m) * 60 + float(s)
                except Exception:
                    duration = None
            if "Video:" in line:
                if " x " in line:
                    res_part = line.split(" x ")[0].split()[-1]
                    width = res_part
                    height = line.split(" x ")[1].split()[0].split(',')[0]
                    resolution = f"{width}x{height}"
            if "bitrate:" in line:
                try:
                    bitrate_str = line.split("bitrate:")[1].split()[0].strip()
                    bitrate = bitrate_str
                except Exception as e:
                    print(f"[VideoProxy] Error parsing bitrate from ffmpeg output for {video_path}: {e}")
        return {
            "duration": duration,
            "resolution": resolution,
            "bitrate": bitrate,
            "size": os.path.getsize(video_path)
        }
    except Exception as e:
        print(f"Error getting video info: {e}")
        return None

def ensure_ffmpeg_exists():
    system = platform.system()
    if system == "Windows":
        if os.path.isfile(FFMPEG_PATH) and os.access(FFMPEG_PATH, os.X_OK):
            return True, None
        if shutil.which("ffmpeg"):
            return True, None
        return False, f"FFmpeg not found at {FFMPEG_PATH} or in PATH"
    if shutil.which("ffmpeg"):
        return True, None
    msg = "FFmpeg not found in PATH. Please install FFmpeg (https://ffmpeg.org/download.html)"
    app = QApplication.instance()
    if app is not None:
        try:
            from tools.tools_checker import show_manual_install_dialog
            show_manual_install_dialog("FFmpeg", os.path.join(BASE_PATH, "tools", "ffmpeg"), "https://ffmpeg.org/download.html", parent=app.activeWindow())
        except Exception as e:
            print(f"[VideoProxy] Could not show install dialog: {e}")
    else:
        print("FFmpeg not found in PATH. Install examples:")
        print("  Ubuntu/Debian: sudo apt update && sudo apt install ffmpeg")
        print("  Fedora: sudo dnf install ffmpeg")
        print("  Arch: sudo pacman -S ffmpeg")
        print("  macOS (Homebrew): brew install ffmpeg")
    return False, msg

def determine_auto_proxy_preset(video_path):
    info = get_video_info(video_path)
    if not info or not info.get("resolution"):
        return "Medium"
    
    resolution = info["resolution"]
    try:
        width = int(resolution.split('x')[0])
        if width >= 1920:
            return "High"
        elif width >= 1280:
            return "Medium"
        else:
            return "Low"
    except Exception:
        return "Medium"


def get_ffmpeg_thread_args():
    """Return ffmpeg threading args that let FFmpeg/codec auto-detect threads.

    Use -threads 0 so encoders (libx264, etc.) decide optimal threading.
    Use -filter_threads 0 to allow filtergraph auto-pick where supported.
    """
    return ["-filter_threads", "0", "-threads", "0"]

def _run(cmd, **kwargs):
    if os.name == 'nt':
        kwargs.setdefault('creationflags', subprocess.CREATE_NO_WINDOW)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs.setdefault('startupinfo', si)
    return subprocess.run(cmd, **kwargs)


def choose_video_encoder():
    """Return (encoder_name, is_hardware_encoder).

    Prefer GPU encoders (NVENC, QSV, AMF, VAAPI) if available; fallback to libx264.
    """
    ffmpeg_exec = None
    if platform.system() == "Windows":
        if os.path.isfile(FFMPEG_PATH) and os.access(FFMPEG_PATH, os.X_OK):
            ffmpeg_exec = FFMPEG_PATH
    else:
        ffmpeg_exec = shutil.which("ffmpeg")
    if not ffmpeg_exec:
        return "libx264", False
    try:
        result = _run(
            [ffmpeg_exec, "-hide_banner", "-encoders"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            timeout=5,
        )
        output = result.stdout or ""
        preferred = ["h264_nvenc", "hevc_nvenc", "h264_qsv", "hevc_qsv", "h264_amf", "h264_vaapi"]
        for enc in preferred:
            if enc in output:
                return enc, True
    except Exception as e:
        print(f"[VideoProxy] Encoder detection failed: {e}")
    return "libx264", False


def detect_gpu_pipeline_support():
    """Detect if ffmpeg build supports a CUDA/NV pipeline (decoding, NPP scaling, NVENC).

    Returns a dict with keys: has_nvenc, has_cuvid, has_scale_npp, has_hwaccel_cuda
    """
    support = {
        'has_nvenc': False,
        'has_cuvid': False,
        'has_scale_npp': False,
        'has_hwaccel_cuda': False
    }
    ffmpeg_exec = None
    if platform.system() == "Windows":
        if os.path.isfile(FFMPEG_PATH) and os.access(FFMPEG_PATH, os.X_OK):
            ffmpeg_exec = FFMPEG_PATH
    else:
        ffmpeg_exec = shutil.which("ffmpeg")
    if not ffmpeg_exec:
        return support
    try:
        result = _run([ffmpeg_exec, '-hide_banner', '-encoders'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=5)
        out = result.stdout or ''
        if 'h264_nvenc' in out or 'hevc_nvenc' in out:
            support['has_nvenc'] = True
    except Exception as e:
        print(f"[VideoProxy] Failed to probe ffmpeg encoders: {e}")
    try:
        result = _run([ffmpeg_exec, '-hide_banner', '-decoders'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=5)
        out = result.stdout or ''
        if 'h264_cuvid' in out or 'hevc_cuvid' in out:
            support['has_cuvid'] = True
    except Exception as e:
        print(f"[VideoProxy] Failed to probe ffmpeg decoders: {e}")
    try:
        result = _run([ffmpeg_exec, '-hide_banner', '-filters'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=5)
        out = result.stdout or ''
        if 'scale_npp' in out:
            support['has_scale_npp'] = True
    except Exception as e:
        print(f"[VideoProxy] Failed to probe ffmpeg filters: {e}")
    try:
        result = _run([ffmpeg_exec, '-hide_banner', '-hwaccels'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=5)
        out = result.stdout or ''
        if 'cuda' in out.lower():
            support['has_hwaccel_cuda'] = True
    except Exception as e:
        print(f"[VideoProxy] Failed to probe ffmpeg hwaccels: {e}")
    return support


def build_ffmpeg_cmd(video_path, output_path, preset, crf, encoder, hw_encoder, prefer_gpu_pipeline=True):
    """Construct ffmpeg command using GPU pipeline if available and requested.

    Returns (cmd_list, used_gpu_pipeline_bool)
    """
    support = detect_gpu_pipeline_support()
    use_gpu_pipeline = False
    cmd = [FFMPEG_PATH, *get_ffmpeg_thread_args()]

    # Decide whether we can and should use a full GPU pipeline
    if hw_encoder and support['has_nvenc'] and prefer_gpu_pipeline:
        # require both hwaccel and scale_npp for full offload
        if support['has_hwaccel_cuda'] and support['has_scale_npp'] and support['has_cuvid']:
            use_gpu_pipeline = True
            # Use CUDA HW accel for decoding and NPP for scaling
            cmd += ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda']
            cmd += ['-i', video_path]
            cmd += ['-vf', f"scale_npp={preset['resolution']}"]
            cmd += ['-c:v', encoder]
            cmd += ['-b:v', preset['bitrate']]
            cmd += ['-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', '-y', output_path]
            return cmd, True

    # Fallback: either GPU encode only or CPU path
    cmd += ['-i', video_path]
    cmd += ['-vf', f"scale={preset['resolution']}"]
    cmd += ['-c:v', encoder]
    cmd += ['-b:v', preset['bitrate']]
    if not hw_encoder:
        cmd += ['-crf', str(crf), '-preset', 'medium']
    cmd += ['-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', '-y', output_path]
    return cmd, False


def _is_hw_encoder_error(err_text: str) -> bool:
    """Return True if ffmpeg error text indicates a hardware encoder/driver problem."""
    if not err_text:
        return False
    checks = [
        "Driver does not support the required nvenc API version",
        "minimum required Nvidia driver",
        "Error while opening encoder",
        "Could not open encoder",
        "Function not implemented",
        "Invalid argument",
    ]
    lower = err_text.lower()
    for c in checks:
        if c.lower() in lower:
            return True
    return False

class VideoProxyWorker(QThread):
    progress_update = Signal(dict)
    finished = Signal(object)
    
    def __init__(self, video_path, proxy_setting):
        super().__init__()
        self.video_path = video_path
        self.proxy_setting = proxy_setting
        self.stop_flag = False
        
    def stop(self):
        self.stop_flag = True
    
    def run(self):
        if self.proxy_setting == "Off":
            self.finished.emit(self.video_path)
            return
        # Ensure ffmpeg is present
        ok, err = ensure_ffmpeg_exists()
        if not ok:
            self.progress_update.emit({"status": "error", "error": err})
            self.finished.emit(None)
            return
        
        cleanup_video_temp_folder()
        temp_folder = ensure_video_temp_folder()
        
        filename = os.path.splitext(os.path.basename(self.video_path))[0] + "_proxy.mp4"
        output_path = os.path.join(temp_folder, filename)
        
        if self.proxy_setting == "Auto":
            preset_name = determine_auto_proxy_preset(self.video_path)
        else:
            preset_name = self.proxy_setting
        try:
            presets = get_video_proxy_presets()
            preset = presets[preset_name]
        except Exception as e:
            self.progress_update.emit({"status": "error", "error": f"Video proxy preset error: {e}"})
            self.finished.emit(None)
            return
        
        crf = preset.get('crf', 23)
        
        video_info = get_video_info(self.video_path)
        
        self.progress_update.emit({
            "status": "starting",
            "preset": preset_name,
            "preset_label": preset["label"],
            "resolution": preset["resolution"],
            "bitrate": preset["bitrate"],
            "crf": crf,
            "input_size": video_info["size"] if video_info else 0,
            "input_resolution": video_info["resolution"] if video_info else "Unknown",
            "duration": video_info["duration"] if video_info else 0
        })
        
        try:
            encoder, hw_encoder = choose_video_encoder()
            print(f"[VideoProxy] Selected encoder: {encoder} (hw={hw_encoder})")
            cmd, used_gpu_pipeline = build_ffmpeg_cmd(self.video_path, output_path, preset, crf, encoder, hw_encoder, prefer_gpu_pipeline=True)
            if not hw_encoder:
                # CRF and preset only for CPU codecs (e.g., libx264)
                cmd[cmd.index("-b:v")+2:cmd.index("-b:v")+2] = ["-crf", str(crf), "-preset", "medium"]
            
            print(f"[VideoProxy] Running ffmpeg command: {' '.join(cmd)}")
            if 'scale_npp' in ' '.join(cmd) and 'hwaccel' in ' '.join(cmd):
                print("[VideoProxy] Using full GPU pipeline: decode(hwaccel) + scale_npp + nvenc")
            elif encoder.startswith('h264_nvenc') or encoder.startswith('hevc_nvenc'):
                print("[VideoProxy] Using NVENC for encoding (CPU decode/scale) — consider enabling full GPU pipeline (nvdec+scale_npp) to reduce CPU load")
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            duration = video_info["duration"] if video_info and video_info["duration"] else 0
            
            tail = []
            for line in process.stdout:
                tail.append(line)
                if self.stop_flag:
                    process.terminate()
                    self.finished.emit(None)
                    return
                
                if "time=" in line:
                    try:
                        time_str = line.split("time=")[1].split()[0]
                        time_parts = time_str.split(":")
                        if len(time_parts) == 3:
                            h, m, s = time_parts
                            current_time = int(h) * 3600 + int(m) * 60 + float(s)
                            
                            if duration > 0:
                                progress = int((current_time / duration) * 100)
                                self.progress_update.emit({
                                    "status": "processing",
                                    "progress": min(progress, 100),
                                    "current_time": current_time,
                                    "duration": duration
                                })
                    except Exception as e:
                        pass

            process.wait()

            if process.returncode != 0:
                err_snippet = "".join(tail[-32:]) if tail else ""
                print(f"FFmpeg error: return code {process.returncode}. Last output: {err_snippet}")
                # If this looks like a hardware encoder/driver problem and we used a HW encoder, retry with CPU encoder
                if hw_encoder and _is_hw_encoder_error(err_snippet):
                    print("[VideoProxy] Hardware encoder failed, retrying with libx264")
                    self.progress_update.emit({"status": "info", "info": "Hardware encoder failed, retrying with CPU encoder"})
                    encoder = "libx264"
                    hw_encoder = False
                    cmd = [
                        FFMPEG_PATH,
                        *get_ffmpeg_thread_args(),
                        "-i", self.video_path,
                        "-vf", f"scale={preset['resolution']}",
                        "-c:v", encoder,
                        "-b:v", preset["bitrate"],
                        "-c:a", "aac",
                        "-b:a", "128k",
                        "-movflags", "+faststart",
                        "-y",
                        output_path
                    ]
                    cmd[cmd.index("-b:v")+2:cmd.index("-b:v")+2] = ["-crf", str(crf), "-preset", "medium"]
                    print(f"[VideoProxy] Retrying ffmpeg with: {' '.join(cmd)}")
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                    tail = []
                    for line in process.stdout:
                        tail.append(line)
                        if self.stop_flag:
                            process.terminate()
                            self.finished.emit(None)
                            return
                        if "time=" in line:
                            try:
                                time_str = line.split("time=")[1].split()[0]
                                time_parts = time_str.split(":")
                                if len(time_parts) == 3:
                                    h, m, s = time_parts
                                    current_time = int(h) * 3600 + int(m) * 60 + float(s)
                                    if duration > 0:
                                        progress = int((current_time / duration) * 100)
                                        self.progress_update.emit({
                                            "status": "processing",
                                            "progress": min(progress, 100),
                                            "current_time": current_time,
                                            "duration": duration
                                        })
                            except Exception as e:
                                pass
                    process.wait()
                    if process.returncode != 0:
                        err_snippet = "".join(tail[-32:]) if tail else ""
                        print(f"FFmpeg retry error: return code {process.returncode}. Last output: {err_snippet}")
                        self.progress_update.emit({"status": "error", "error": f"FFmpeg return code {process.returncode}: {err_snippet}".strip()})
                        self.finished.emit(None)
                        return
                else:
                    self.progress_update.emit({
                        "status": "error",
                        "error": f"FFmpeg return code {process.returncode}: {err_snippet}".strip()
                    })
                    self.finished.emit(None)
                    return
            
            if os.path.exists(output_path):
                output_size = os.path.getsize(output_path)
                self.progress_update.emit({
                    "status": "completed",
                    "output_path": output_path,
                    "output_size": output_size,
                    "input_size": video_info["size"] if video_info else 0,
                    "compression_ratio": (output_size / video_info["size"] * 100) if video_info and video_info["size"] > 0 else 0
                })
                self.finished.emit(output_path)
            else:
                print("FFmpeg failed to create output file")
                self.progress_update.emit({
                    "status": "error",
                    "error": "FFmpeg failed to create output file"
                })
                self.finished.emit(None)
                
        except Exception as e:
            print(f"Error creating video proxy: {e}")
            self.progress_update.emit({
                "status": "error",
                "error": str(e)
            })
            self.finished.emit(None)


class BatchVideoProxyWorker(QThread):
    progress_update = Signal(dict)
    file_completed = Signal(int, str, str)
    all_finished = Signal(dict)
    
    def __init__(self, video_files, proxy_setting):
        super().__init__()
        self.video_files = video_files
        self.proxy_setting = proxy_setting
        self.stop_flag = False
        self.results = {}
        
    def stop(self):
        self.stop_flag = True
    
    def run(self):
        if self.proxy_setting == "Off":
            for video_path in self.video_files:
                self.results[video_path] = video_path
            self.all_finished.emit(self.results)
            return
            
        ok, err = ensure_ffmpeg_exists()
        if not ok:
            self.progress_update.emit({"status": "error", "error": err})
            self.all_finished.emit({})
            return
        
        cleanup_video_temp_folder()
        temp_folder = ensure_video_temp_folder()
        
        total_files = len(self.video_files)
        
        for idx, video_path in enumerate(self.video_files):
            if self.stop_flag:
                self.all_finished.emit(self.results)
                return
                
            filename = os.path.basename(video_path)
            self.progress_update.emit({
                "status": "file_start",
                "file_index": idx,
                "filename": filename,
                "total_files": total_files
            })
            
            proxy_path = self._process_single_video(video_path, temp_folder, idx, total_files)
            
            if proxy_path:
                self.results[video_path] = proxy_path
            else:
                self.results[video_path] = video_path
                
            self.file_completed.emit(idx, video_path, proxy_path if proxy_path else video_path)
            self.progress_update.emit({
                "status": "file_done",
                "file_index": idx,
                "completed_count": idx + 1,
                "total_files": total_files
            })
        
        self.progress_update.emit({"status": "batch_complete"})
        self.all_finished.emit(self.results)
    
    def _process_single_video(self, video_path, temp_folder, file_idx, total_files):
        if self.proxy_setting == "Auto":
            preset_name = determine_auto_proxy_preset(video_path)
        else:
            preset_name = self.proxy_setting
            
        try:
            presets = get_video_proxy_presets()
            preset = presets[preset_name]
        except Exception as e:
            self.progress_update.emit({"status": "error", "error": f"Preset error: {e}"})
            return None
        
        crf = preset.get('crf', 23)
        video_info = get_video_info(video_path)
        
        self.progress_update.emit({
            "status": "starting",
            "preset": preset_name,
            "preset_label": preset["label"],
            "resolution": preset["resolution"],
            "bitrate": preset["bitrate"],
            "crf": crf,
            "input_size": video_info["size"] if video_info else 0,
            "input_resolution": video_info["resolution"] if video_info else "Unknown",
            "duration": video_info["duration"] if video_info else 0
        })
        
        output_filename = os.path.splitext(os.path.basename(video_path))[0] + "_proxy.mp4"
        output_path = os.path.join(temp_folder, output_filename)
        
        try:
            encoder, hw_encoder = choose_video_encoder()
            print(f"[BatchVideoProxy] File {file_idx + 1}/{total_files}: {os.path.basename(video_path)} using {encoder}")
            
            cmd, used_gpu_pipeline = build_ffmpeg_cmd(video_path, output_path, preset, crf, encoder, hw_encoder, prefer_gpu_pipeline=True)
            if not hw_encoder:
                cmd[cmd.index("-b:v")+2:cmd.index("-b:v")+2] = ["-crf", str(crf), "-preset", "medium"]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            duration = video_info["duration"] if video_info and video_info["duration"] else 0
            tail = []
            
            for line in process.stdout:
                tail.append(line)
                if self.stop_flag:
                    process.terminate()
                    return None
                
                if "time=" in line:
                    try:
                        time_str = line.split("time=")[1].split()[0]
                        time_parts = time_str.split(":")
                        if len(time_parts) == 3:
                            h, m, s = time_parts
                            current_time = int(h) * 3600 + int(m) * 60 + float(s)
                            if duration > 0:
                                progress = int((current_time / duration) * 100)
                                self.progress_update.emit({
                                    "status": "processing",
                                    "progress": min(progress, 100),
                                    "current_time": current_time,
                                    "duration": duration
                                })
                    except Exception:
                        pass
            
            process.wait()
            
            if process.returncode != 0:
                err_snippet = "".join(tail[-32:]) if tail else ""
                print(f"[BatchVideoProxy] FFmpeg error for {os.path.basename(video_path)}: {process.returncode}")
                
                if hw_encoder and _is_hw_encoder_error(err_snippet):
                    print("[BatchVideoProxy] Hardware encoder failed, retrying with libx264")
                    self.progress_update.emit({"status": "info", "info": "Hardware encoder failed, retrying with CPU encoder"})
                    return self._retry_with_cpu_encoder(video_path, output_path, preset, crf, duration)
                
                self.progress_update.emit({"status": "error", "error": f"FFmpeg error: {err_snippet[:200]}"})
                return None
            
            if os.path.exists(output_path):
                output_size = os.path.getsize(output_path)
                self.progress_update.emit({
                    "status": "completed",
                    "output_path": output_path,
                    "output_size": output_size
                })
                return output_path
            else:
                self.progress_update.emit({"status": "error", "error": "FFmpeg failed to create output file"})
                return None
                
        except Exception as e:
            print(f"[BatchVideoProxy] Error processing {os.path.basename(video_path)}: {e}")
            self.progress_update.emit({"status": "error", "error": str(e)})
            return None
    
    def _retry_with_cpu_encoder(self, video_path, output_path, preset, crf, duration):
        cmd = [
            FFMPEG_PATH,
            *get_ffmpeg_thread_args(),
            "-i", video_path,
            "-vf", f"scale={preset['resolution']}",
            "-c:v", "libx264",
            "-b:v", preset["bitrate"],
            "-crf", str(crf),
            "-preset", "medium",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            "-y",
            output_path
        ]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        tail = []
        for line in process.stdout:
            tail.append(line)
            if self.stop_flag:
                process.terminate()
                return None
            if "time=" in line:
                try:
                    time_str = line.split("time=")[1].split()[0]
                    time_parts = time_str.split(":")
                    if len(time_parts) == 3:
                        h, m, s = time_parts
                        current_time = int(h) * 3600 + int(m) * 60 + float(s)
                        if duration > 0:
                            progress = int((current_time / duration) * 100)
                            self.progress_update.emit({
                                "status": "processing",
                                "progress": min(progress, 100),
                                "current_time": current_time,
                                "duration": duration
                            })
                except Exception:
                    pass
        
        process.wait()
        
        if process.returncode != 0 or not os.path.exists(output_path):
            return None
        
        return output_path


def batch_process_videos_with_dialog(video_files, stop_flag=None):
    if not video_files:
        return {}
    
    proxy_setting = get_video_proxy_setting()
    if proxy_setting == "Off":
        return {vf: vf for vf in video_files}
    
    result_container = [None]
    finished_event = threading.Event()
    
    def dialog_factory(video_files, proxy_setting, stop_flag, result_container, finished_event):
        try:
            from dialogs.video_proxy_dialog import VideoProxyDialog
            parent = QApplication.instance().activeWindow() if QApplication.instance() else None
            dlg = VideoProxyDialog(parent=parent, batch_info={'total_files': len(video_files)})
            
            worker = BatchVideoProxyWorker(video_files, proxy_setting)
            
            def on_progress(data):
                try:
                    status = data.get("status")
                    if status == "file_start":
                        file_idx = data.get("file_index", 0)
                        filename = data.get("filename", "")
                        dlg.set_current_file(file_idx, filename)
                    elif status == "file_done":
                        completed = data.get("completed_count", 0)
                        dlg.update_batch_progress(completed)
                    else:
                        dlg.update_progress(data)
                    QApplication.processEvents()
                except Exception as e:
                    print(f"[BatchVideoProxy] Dialog progress update error: {e}")
            
            def on_all_finished(results):
                result_container[0] = results
                try:
                    if dlg and dlg.isVisible():
                        dlg.close()
                except Exception as e:
                    print(f"[BatchVideoProxy] Error closing dialog: {e}")
                finished_event.set()
            
            worker.progress_update.connect(on_progress)
            worker.all_finished.connect(on_all_finished)
            
            def on_cancel_clicked():
                worker.stop()
                if stop_flag:
                    stop_flag['stop'] = True
                dlg.request_stop()
            
            try:
                dlg.cancel_button.clicked.disconnect()
            except Exception:
                pass
            dlg.cancel_button.clicked.connect(on_cancel_clicked)
            
            worker.start()
            dlg.exec()
            
        except Exception as e:
            print(f"[BatchVideoProxy] Dialog factory error: {e}")
            result_container[0] = {}
            finished_event.set()
    
    invoked = invoke_in_main_thread(dialog_factory, (video_files, proxy_setting, stop_flag, result_container, finished_event))
    
    if not invoked:
        print("[BatchVideoProxy] Could not invoke dialog on main thread")
        return {vf: vf for vf in video_files}
    
    if not finished_event.wait(1800):
        print("[BatchVideoProxy] Timeout waiting for batch proxy completion")
        return {vf: vf for vf in video_files}
    
    return result_container[0] if result_container[0] else {}


def create_video_proxy(video_path, proxy_setting, progress_callback=None, stop_flag=None):
    if proxy_setting == "Off":
        return video_path
    
    cleanup_video_temp_folder()
    temp_folder = ensure_video_temp_folder()
    
    filename = os.path.splitext(os.path.basename(video_path))[0] + "_proxy.mp4"
    output_path = os.path.join(temp_folder, filename)
    
    if proxy_setting == "Auto":
        preset_name = determine_auto_proxy_preset(video_path)
    else:
        preset_name = proxy_setting
    try:
        presets = get_video_proxy_presets()
        preset = presets[preset_name]
    except Exception as e:
        if progress_callback:
            progress_callback({"status": "error", "error": f"Video proxy preset error: {e}"})
        print(f"[VideoProxy] Preset error: {e}")
        return None
    
    crf = preset.get('crf', 23)
    
    video_info = get_video_info(video_path)
    
    if progress_callback:
        progress_callback({
            "status": "starting",
            "preset": preset_name,
            "preset_label": preset["label"],
            "resolution": preset["resolution"],
            "bitrate": preset["bitrate"],
            "crf": crf,
            "input_size": video_info["size"] if video_info else 0,
            "input_resolution": video_info["resolution"] if video_info else "Unknown",
            "duration": video_info["duration"] if video_info else 0
        })
    
    try:
        ok, err = ensure_ffmpeg_exists()
        if not ok:
            print(f"[VideoProxy] {err}")
            if progress_callback:
                progress_callback({"status": "error", "error": err})
            return None
        encoder, hw_encoder = choose_video_encoder()
        print(f"[VideoProxy] Selected encoder: {encoder} (hw={hw_encoder})")
        cmd, used_gpu_pipeline = build_ffmpeg_cmd(video_path, output_path, preset, crf, encoder, hw_encoder, prefer_gpu_pipeline=True)
        if not hw_encoder:
            cmd[cmd.index("-b:v")+2:cmd.index("-b:v")+2] = ["-crf", str(crf), "-preset", "medium"]
        
        print(f"[VideoProxy] Running ffmpeg command: {' '.join(cmd)}")
        if 'scale_npp' in ' '.join(cmd) and 'hwaccel' in ' '.join(cmd):
            print("[VideoProxy] Using full GPU pipeline: decode(hwaccel) + scale_npp + nvenc")
        elif encoder.startswith('h264_nvenc') or encoder.startswith('hevc_nvenc'):
            print("[VideoProxy] Using NVENC for encoding (CPU decode/scale) — consider enabling full GPU pipeline (nvdec+scale_npp) to reduce CPU load")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        duration = video_info["duration"] if video_info and video_info["duration"] else 0
        
        tail = []
        for line in process.stdout:
            tail.append(line)
            if stop_flag and stop_flag.get('stop'):
                process.terminate()
                return None
            
            if "time=" in line:
                try:
                    time_str = line.split("time=")[1].split()[0]
                    time_parts = time_str.split(":")
                    if len(time_parts) == 3:
                        h, m, s = time_parts
                        current_time = int(h) * 3600 + int(m) * 60 + float(s)
                        
                        if duration > 0:
                            progress = int((current_time / duration) * 100)
                            if progress_callback:
                                progress_callback({
                                    "status": "processing",
                                    "progress": min(progress, 100),
                                    "current_time": current_time,
                                    "duration": duration
                                })
                except Exception as e:
                    pass
        
        process.wait()

        if process.returncode != 0:
            err_snippet = "".join(tail[-32:]) if tail else ""
            print(f"FFmpeg error: return code {process.returncode}. Last output: {err_snippet}")
            # If hardware encoder failed, retry with CPU encoder
            if hw_encoder and _is_hw_encoder_error(err_snippet):
                print("[VideoProxy] Hardware encoder failed, retrying with libx264")
                if progress_callback:
                    progress_callback({"status": "info", "info": "Hardware encoder failed, retrying with CPU encoder"})
                encoder = "libx264"
                hw_encoder = False
                cmd = [
                    FFMPEG_PATH,
                    *get_ffmpeg_thread_args(),
                    "-i", video_path,
                    "-vf", f"scale={preset['resolution']}",
                    "-c:v", encoder,
                    "-b:v", preset["bitrate"],
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-movflags", "+faststart",
                    "-y",
                    output_path
                ]
                cmd[cmd.index("-b:v")+2:cmd.index("-b:v")+2] = ["-crf", str(crf), "-preset", "medium"]
                print(f"[VideoProxy] Retrying ffmpeg with: {' '.join(cmd)}")
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                tail = []
                for line in process.stdout:
                    tail.append(line)
                    if stop_flag and stop_flag.get('stop'):
                        process.terminate()
                        return None
                    if "time=" in line:
                        try:
                            time_str = line.split("time=")[1].split()[0]
                            time_parts = time_str.split(":")
                            if len(time_parts) == 3:
                                h, m, s = time_parts
                                current_time = int(h) * 3600 + int(m) * 60 + float(s)
                                if duration > 0 and progress_callback:
                                    progress = int((current_time / duration) * 100)
                                    progress_callback({
                                        "status": "processing",
                                        "progress": min(progress, 100),
                                        "current_time": current_time,
                                        "duration": duration
                                    })
                        except Exception as e:
                            pass
                process.wait()
                if process.returncode != 0:
                    err_snippet = "".join(tail[-32:]) if tail else ""
                    print(f"FFmpeg retry error: return code {process.returncode}. Last output: {err_snippet}")
                    if progress_callback:
                        progress_callback({"status": "error", "error": f"FFmpeg return code {process.returncode}: {err_snippet}".strip()})
                    return None
            else:
                if progress_callback:
                    progress_callback({
                        "status": "error",
                        "error": f"FFmpeg return code {process.returncode}: {err_snippet}".strip()
                    })
                return None
        
        if os.path.exists(output_path):
            output_size = os.path.getsize(output_path)
            if progress_callback:
                progress_callback({
                    "status": "completed",
                    "output_path": output_path,
                    "output_size": output_size,
                    "input_size": video_info["size"] if video_info else 0,
                    "compression_ratio": (output_size / video_info["size"] * 100) if video_info and video_info["size"] > 0 else 0
                })
            return output_path
        else:
            print("FFmpeg failed to create output file")
            return None
            
    except Exception as e:
        print(f"Error creating video proxy: {e}")
        if progress_callback:
            progress_callback({
                "status": "error",
                "error": str(e)
            })
        return None

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QObject, Qt


class VideoProxyInvoker(QObject):
    run_callable = Signal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.run_callable.connect(self._run_callable_slot)

    def _run_callable_slot(self, callable_obj, args):
        try:
            callable_obj(*args)
        except Exception as e:
            print(f"[VideoProxy] Invoker callable raised: {e}")


def get_video_proxy_invoker(timeout=5):
    """Return a singleton VideoProxyInvoker created on the main GUI thread.
    If called from a worker thread, schedules creation on the main thread and waits up to `timeout` seconds.
    """
    global _video_proxy_invoker
    if _video_proxy_invoker is not None:
        return _video_proxy_invoker

    app = QApplication.instance()
    if app is None:
        return None

    creation_done = threading.Event()

    def _create_invoker():
        global _video_proxy_invoker
        try:
            if _video_proxy_invoker is None:
                _video_proxy_invoker = VideoProxyInvoker(parent=app.activeWindow())
        except Exception as e:
            print(f"[VideoProxy] Failed to create invoker on main thread: {e}")
        finally:
            creation_done.set()

    try:
        from PySide6.QtCore import QThread
        if QThread.currentThread() == app.thread():
            _create_invoker()
            return _video_proxy_invoker
    except Exception as e:
        print(f"[VideoProxy] Could not verify QThread current thread: {e}")

    QTimer.singleShot(0, _create_invoker)
    creation_done.wait(timeout=timeout)
    return _video_proxy_invoker


def process_video_for_api(video_path, stop_flag=None, progress_callback=None):
    ext = os.path.splitext(video_path)[1].lower()
    if ext not in VIDEO_EXTENSIONS:
        return video_path

    proxy_setting = get_video_proxy_setting()

    if proxy_setting == "Off":
        return video_path

    return create_video_proxy(video_path, proxy_setting, progress_callback, stop_flag)

def invoke_in_main_thread(callable_obj, args=(), timeout=600):
    """Run a callable on the main GUI thread via the invoker and return True if invoked, False otherwise."""
    invoker = get_video_proxy_invoker()
    if invoker is None:
        return False
    done = threading.Event()

    def wrapper(*a):
        try:
            callable_obj(*a)
        except Exception as e:
            try:
                for arg in a:
                    if isinstance(arg, list) and len(arg) and hasattr(arg, '__setitem__'):
                        try:
                            arg[0] = (None, f"invoker callable error: {e}")
                        except Exception as e2:
                            print(f"[VideoProxy] Failed to set invoker list result for arg: {e2}")
                    if isinstance(arg, threading.Event):
                        try:
                            arg.set()
                        except Exception as e2:
                            print(f"[VideoProxy] Failed to set event arg after invoker error: {e2}")
            except Exception as e2:
                print(f"[VideoProxy] Error handling invoker callback args after callable exception: {e2}")
            print(f"[VideoProxy] Invoker callable raised: {e}")
        finally:
            done.set()

    try:
        invoker.run_callable.emit(wrapper, args)
    except Exception as exc:
        print(f"[VideoProxy] Failed to emit run_callable: {exc}")
        return False

    done.wait(timeout=timeout)
    return done.is_set()
