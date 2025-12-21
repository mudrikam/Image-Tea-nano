import os
import subprocess
from config import BASE_PATH

VIDEO_EXTENSIONS = {'.mp4', '.mpeg', '.mov', '.avi', '.flv', '.mpg', '.webm', '.wmv', '.3gp', '.3gpp'}

def get_ffmpeg_path():
    return os.path.join(BASE_PATH, 'tools', 'ffmpeg', 'ffmpeg.exe')

def is_video_file(filepath):
    _, ext = os.path.splitext(filepath)
    return ext.lower() in VIDEO_EXTENSIONS

def scan_directory_for_videos(directory):
    video_files = []
    for root, dirs, files in os.walk(directory):
        for filename in files:
            filepath = os.path.join(root, filename)
            if is_video_file(filepath):
                video_files.append(filepath)
    return video_files

def check_gpu_support():
    ffmpeg_path = get_ffmpeg_path()
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        result = subprocess.run(
            [ffmpeg_path, '-hwaccels'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        output = result.stdout.lower()
        if 'cuda' in output or 'nvenc' in output or 'd3d11va' in output or 'dxva2' in output:
            return True
    except Exception as e:
        print(f"[ERROR] Error checking GPU support: {e}")
    return False

def remove_audio_from_video(source_path, destination_path, use_gpu=True):
    ffmpeg_path = get_ffmpeg_path()
    
    if use_gpu:
        cmd = [
            ffmpeg_path,
            '-hwaccel', 'auto',
            '-i', source_path,
            '-c:v', 'copy',
            '-an',
            '-y',
            destination_path
        ]
    else:
        cmd = [
            ffmpeg_path,
            '-i', source_path,
            '-c:v', 'copy',
            '-an',
            '-y',
            destination_path
        ]
    
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if result.returncode == 0:
            return True, None
        else:
            error_msg = result.stderr
            print(f"[DEBUG] FFmpeg error: {error_msg}")
            return False, error_msg
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] Error executing ffmpeg: {error_msg}")
        return False, error_msg
