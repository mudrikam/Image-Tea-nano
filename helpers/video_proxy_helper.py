import os
import subprocess
import json
import time
import threading
from config import BASE_PATH
from PySide6.QtWidgets import QApplication
from dialogs.video_proxy_dialog import VideoProxyDialog
from PySide6.QtCore import QThread, Signal

_video_proxy_invoker = None

FFMPEG_PATH = os.path.join(BASE_PATH, "tools", "ffmpeg", "ffmpeg.exe")

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
    try:
        cmd = [
            FFMPEG_PATH,
            "-i", video_path,
            "-hide_banner"
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        output = result.stdout
        
        duration = None
        resolution = None
        bitrate = None
        
        for line in output.split('\n'):
            if "Duration:" in line:
                parts = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = parts.split(":")
                duration = int(h) * 3600 + int(m) * 60 + float(s)
            if "Video:" in line:
                if " x " in line:
                    res_part = line.split(" x ")[0].split()[-1]
                    width = res_part
                    height = line.split(" x ")[1].split()[0].split(',')[0]
                    resolution = f"{width}x{height}"
            if "bitrate:" in line:
                bitrate_str = line.split("bitrate:")[1].split()[0].strip()
                bitrate = bitrate_str
        
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
    if not os.path.exists(FFMPEG_PATH):
        print(f"[VideoProxy] FFmpeg not found at {FFMPEG_PATH}")
        return False, f"FFmpeg not found at {FFMPEG_PATH}"
    return True, None

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
            cmd = [
                FFMPEG_PATH,
                "-i", self.video_path,
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
            
            print(f"[VideoProxy] Running ffmpeg command: {' '.join(cmd)}")
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
                        h, m, s = time_str.split(":")
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
                print(f"FFmpeg error: return code {process.returncode}. Last output: {err_snippet}")
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
        cmd = [
            FFMPEG_PATH,
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
        
        print(f"[VideoProxy] Running ffmpeg command: {' '.join(cmd)}")
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
                    h, m, s = time_str.split(":")
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
                except Exception:
                    pass
        
        process.wait()
        
        if process.returncode != 0:
            err_snippet = "".join(tail[-32:]) if tail else ""
            print(f"FFmpeg error: return code {process.returncode}. Last output: {err_snippet}")
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
    except Exception:
        pass

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
                        except Exception:
                            pass
                    if isinstance(arg, threading.Event):
                        try:
                            arg.set()
                        except Exception:
                            pass
            except Exception:
                pass
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
