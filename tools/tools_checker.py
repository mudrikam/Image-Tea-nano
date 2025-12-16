import os
import urllib.request
import zipfile
import sys
import shutil
import subprocess
from config import BASE_PATH

expected = [
    "exiftool",
    "ghostscript",
    "cairo",
    "ffmpeg"
]
expected_full = [os.path.join(BASE_PATH, "tools", f) for f in expected]

def print_progress_bar(downloaded, total_length):
    if total_length > 0:
        percent = int(downloaded * 100 / total_length)
        bar_length = 40
        filled_length = int(bar_length * percent // 100)
        green = '\033[92m'
        red = '\033[91m'
        reset = '\033[0m'
        bar = f"{green}{'+' * filled_length}{reset}{red}{'-' * (bar_length - filled_length)}{reset}"
        print(f"\r|{bar}| {percent}% ({downloaded}/{total_length} bytes)", end='', flush=True)
        if downloaded >= total_length:
            print()
    else:
        print(f"\rDownloading... ({downloaded} bytes)", end='', flush=True)

def download_with_progress(url, filename):
    def reporthook(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0 and downloaded > total_size:
            downloaded = total_size
        print_progress_bar(downloaded, total_size)
    print(f"Downloading from {url} to {filename} ...")
    try:
        urllib.request.urlretrieve(url, filename, reporthook)
        print("Download finished.")
    except Exception as e:
        print(f"Failed to download: {e}")

def check_folders():
    for folder in expected_full:
        if not os.path.isdir(folder):
            print(f"Missing folder: {folder}")
            os.makedirs(folder, exist_ok=True)
            if folder.endswith("ghostscript"):
                download_and_extract_ghostscript(folder)
            elif folder.endswith("exiftool"):
                download_and_extract_exiftool(folder)
            elif folder.endswith("cairo"):
                download_and_extract_cairo(folder)
            elif folder.endswith("ffmpeg"):
                download_and_extract_ffmpeg(folder)

def download_and_extract_ghostscript(target_folder):
    url = "https://github.com/mudrikam/ghostscript-for-image-tea/archive/refs/heads/main.zip"
    zip_path = os.path.join(target_folder, "ghostscript.zip")
    print(f"Downloading Ghostscript to {zip_path} ...")
    try:
        download_with_progress(url, zip_path)
        print("Download complete. Extracting...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_folder)
            extracted_root = None
            for name in zip_ref.namelist():
                root = name.split('/')[0]
                if root:
                    extracted_root = os.path.join(target_folder, root)
                    break
            if extracted_root and os.path.isdir(extracted_root):
                for item in os.listdir(extracted_root):
                    src = os.path.join(extracted_root, item)
                    dst = os.path.join(target_folder, item)
                    if os.path.isdir(src):
                        if not os.path.exists(dst):
                            os.rename(src, dst)
                    else:
                        os.replace(src, dst)
                try:
                    os.rmdir(extracted_root)
                except Exception:
                    pass
        os.remove(zip_path)
        print("Ghostscript extracted successfully.")
    except Exception as e:
        print(f"Failed to download or extract Ghostscript: {e}")

def download_and_extract_exiftool(target_folder):
    url = "https://github.com/mudrikam/exiftool-for-image-tea/archive/refs/heads/main.zip"
    zip_path = os.path.join(target_folder, "exiftool.zip")
    print(f"Downloading Exiftool to {zip_path} ...")
    try:
        download_with_progress(url, zip_path)
        print("Download complete. Extracting...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_folder)
            extracted_root = None
            for name in zip_ref.namelist():
                root = name.split('/')[0]
                if root:
                    extracted_root = os.path.join(target_folder, root)
                    break
            if extracted_root and os.path.isdir(extracted_root):
                for item in os.listdir(extracted_root):
                    src = os.path.join(extracted_root, item)
                    dst = os.path.join(target_folder, item)
                    if os.path.isdir(src):
                        if not os.path.exists(dst):
                            os.rename(src, dst)
                    else:
                        os.replace(src, dst)
                try:
                    os.rmdir(extracted_root)
                except Exception:
                    pass
        os.remove(zip_path)
        print("Exiftool extracted successfully.")
    except Exception as e:
        print(f"Failed to download or extract Exiftool: {e}")

def download_and_extract_cairo(target_folder):
    url = "https://github.com/preshing/cairo-windows/releases/download/with-tee/cairo-windows-1.17.2.zip"
    zip_path = os.path.join(target_folder, "cairo.zip")
    print(f"Downloading Cairo to {zip_path} ...")
    try:
        download_with_progress(url, zip_path)
        print("Download complete. Extracting...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_folder)
        os.remove(zip_path)
        print("Cairo extracted successfully.")
    except Exception as e:
        print(f"Failed to download or extract Cairo: {e}")

def download_and_extract_ffmpeg(target_folder):
    url = "https://github.com/mudrikam/ffmpeg-for-image-tea/archive/refs/heads/main.zip"
    zip_path = os.path.join(target_folder, "ffmpeg.zip")
    print(f"Downloading FFmpeg to {zip_path} ...")
    try:
        download_with_progress(url, zip_path)
        print("Download complete. Extracting...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_folder)
            extracted_root = None
            for name in zip_ref.namelist():
                root = name.split('/')[0]
                if root:
                    extracted_root = os.path.join(target_folder, root)
                    break
            if extracted_root and os.path.isdir(extracted_root):
                for item in os.listdir(extracted_root):
                    src = os.path.join(extracted_root, item)
                    dst = os.path.join(target_folder, item)
                    if os.path.isdir(src):
                        if not os.path.exists(dst):
                            os.rename(src, dst)
                    else:
                        os.replace(src, dst)
                try:
                    os.rmdir(extracted_root)
                except Exception:
                    pass
        os.remove(zip_path)
        print("FFmpeg extracted successfully.")
    except Exception as e:
        print(f"Failed to download or extract FFmpeg: {e}")

def install_pyautogui(python_exe: str | None = None, version: str = '0.9.53') -> bool:
    """Upgrade pip/tools and install a specific PyAutoGUI version using the given python executable.

    If no executable is provided, the embedded Python under BASE_PATH\\python\\Windows\\python.exe is used when present,
    otherwise the current running interpreter is used.
    """
    if python_exe is None:
        candidate = os.path.join(BASE_PATH, "python", "Windows", "python.exe")
        if os.path.exists(candidate):
            python_exe = candidate
        else:
            python_exe = sys.executable
    if not os.path.exists(python_exe):
        print("Error: Python executable not found; cannot install pyautogui.")
        return False
    try:
        subprocess.check_call([python_exe, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    except subprocess.CalledProcessError as e:
        print(f"Error upgrading pip/setuptools/wheel: {e}")
        # continue and attempt install anyway
    try:
        subprocess.check_call([python_exe, "-m", "pip", "install", f"pyautogui=={version}", "--no-warn-script-location"])
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error installing pyautogui: {e}")
        return False


def is_pyautogui_installed(python_exe: str | None = None) -> tuple[bool, str]:
    """Return (True, version) if PyAutoGUI can be imported with the selected python executable,
    otherwise return (False, error_message).
    """
    if python_exe is None:
        candidate = os.path.join(BASE_PATH, "python", "Windows", "python.exe")
        if os.path.exists(candidate):
            python_exe = candidate
        else:
            python_exe = sys.executable
    try:
        out = subprocess.check_output(
            [python_exe, "-c", "import pyautogui; print(pyautogui.__version__)"],
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            timeout=15,
        )
        ver = out.strip().splitlines()[-1].strip()
        return True, ver
    except subprocess.CalledProcessError as e:
        return False, (e.output or str(e)).strip()
    except Exception as e:
        return False, str(e)


def ensure_pyautogui(python_exe: str | None = None, version: str = '0.9.53') -> bool:
    """Ensure PyAutoGUI is installed and importable. If missing, attempt installation.

    Returns True if PyAutoGUI is importable after this call, otherwise False.
    """
    installed, info = is_pyautogui_installed(python_exe)
    if installed:
        return True
    ok = install_pyautogui(python_exe, version)
    if not ok:
        print("Error: PyAutoGUI installation command failed.")
        return False
    # verify installation
    installed2, info2 = is_pyautogui_installed(python_exe)
    if installed2:
        return True
    else:
        print(f"Error: PyAutoGUI not importable after install: {info2}")
        return False


def ensure_tools_ready(python_exe: str | None = None, pyautogui_version: str = '0.9.53') -> bool:
    """Perform the standard tool checks and ensure PyAutoGUI is available.

    Returns True if basic tooling appears ready (folders present and PyAutoGUI importable).
    """
    check_folders()
    ok = ensure_pyautogui(python_exe, pyautogui_version)
    return ok


if __name__ == "__main__":
    # Support explicit commands:
    #   --install-pyautogui  : install the pinned version
    #   --ensure-pyautogui   : install if missing
    # Running with no args will run the normal folder checks and ensure PyAutoGUI.
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd in ("--install-pyautogui", "install-pyautogui"):
            ok = install_pyautogui()
            if not ok:
                print("Error: PyAutoGUI installation failed.")
        elif cmd in ("--ensure-pyautogui", "ensure-pyautogui"):
            ok = ensure_pyautogui()
            if not ok:
                print("Error: PyAutoGUI is not ready after attempted installation.")
        else:
            check_folders()
    else:
        # Default startup: ensure folders + pyautogui
        ok = ensure_tools_ready()
        if not ok:
            print("Error: One or more tool checks failed; see messages above.")