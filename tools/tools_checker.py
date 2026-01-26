import os
import urllib.request
import zipfile
import sys
import shutil
import subprocess
import platform
import webbrowser
import time
from PySide6.QtWidgets import QMessageBox, QApplication

# Add parent directory to path so config can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BASE_PATH

expected = [
    "exiftool",
    "ghostscript",
    "cairo",
    "ffmpeg",
    "realesrgan"
]
expected_full = [os.path.join(BASE_PATH, "tools", f) for f in expected]

EXECUTABLE_REQUIREMENTS = {
    "ffmpeg": ["ffmpeg", "ffprobe"],
    "realesrgan": ["realesrgan-ncnn-vulkan"]
}

def get_embedded_python_path():
    system = platform.system()
    if system == "Windows":
        candidate = os.path.join(BASE_PATH, "python", "Windows", "python.exe")
    elif system == "Darwin":
        candidate = os.path.join(BASE_PATH, "python", "MacOS", "bin", "python3.12")
    else:
        candidate = os.path.join(BASE_PATH, "python", "Linux", "bin", "python3.12")
    
    if os.path.exists(candidate):
        return candidate
    return sys.executable

def check_system_tool(tool_name):
    system = platform.system()
    if system == "Windows":
        return False
    
    tool_commands = {
        "ghostscript": "gs",
        "exiftool": "exiftool",
        "ffmpeg": "ffmpeg",
    }
    
    cmd = tool_commands.get(tool_name)
    if not cmd:
        return False
    
    try:
        result = subprocess.run(["which", cmd], capture_output=True, text=True)
        return result.returncode == 0 and result.stdout.strip()
    except Exception:
        return False

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

def _powershell_download(url, filename, timeout: int = 120) -> bool:
    if not shutil.which("powershell"):
        return False
    # Force TLS1.2 in the PowerShell session for older Windows builds that default to older TLS
    ps_cmd = (
        "Try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; "
        "$wc = New-Object System.Net.WebClient; $wc.DownloadFile(\"%s\", \"%s\"); exit 0 } Catch { exit 1 }" % (url, filename)
    )
    cmd = [
        "powershell",
        "-NoProfile",
        "-Command",
        ps_cmd
    ]
    try:
        res = subprocess.run(cmd, check=False, timeout=timeout)
        return res.returncode == 0 and os.path.exists(filename) and os.path.getsize(filename) > 0
    except subprocess.TimeoutExpired:
        print("PowerShell download timed out")
        return False
    except Exception as e:
        print(f"PowerShell download error: {e}")
        return False


def _bitsadmin_download(url, filename, timeout: int = 120) -> bool:
    if not shutil.which("bitsadmin"):
        return False
    cmd = ["bitsadmin", "/transfer", "downloadjob", url, filename]
    try:
        res = subprocess.run(cmd, check=False, timeout=timeout)
        return res.returncode == 0 and os.path.exists(filename) and os.path.getsize(filename) > 0
    except subprocess.TimeoutExpired:
        print("BitsAdmin download timed out")
        return False
    except Exception as e:
        print(f"bitsadmin download error: {e}")
        return False


def download_with_progress(url, filename, overall_timeout: int = 300, progress_reporter=None) -> bool:
    def _stream_download(timeout_per_op: int = 30) -> bool:
        req = urllib.request.Request(url, headers={"User-Agent": "Image-Tea/1.0"})
        with urllib.request.urlopen(req, timeout=timeout_per_op) as resp:
            total = resp.getheader('Content-Length')
            try:
                total_length = int(total) if total else 0
            except Exception:
                total_length = 0
            downloaded = 0
            last_percent = -1
            chunk_size = 8192
            with open(filename, 'wb') as out:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    out.write(chunk)
                    downloaded += len(chunk)
                    percent = int((downloaded * 100) / total_length) if total_length else 0
                    if percent != last_percent:
                        last_percent = percent
                        print_progress_bar(downloaded, total_length)
                        if callable(progress_reporter):
                            try:
                                progress_reporter(percent)
                            except Exception:
                                pass
            if os.path.exists(filename) and os.path.getsize(filename) > 0:
                if callable(progress_reporter):
                    try:
                        progress_reporter(100)
                    except Exception:
                        pass
                return True
            else:
                print("Downloaded file is empty or missing after streaming retrieval.")
                return False

    print(f"Downloading from {url} to {filename} ...")
    start = time.time()
    try:
        if _stream_download():
            print("Download finished.")
            return True
    except Exception as e:
        print(f"Primary stream download failed: {e}")

    if time.time() - start >= overall_timeout:
        print("Overall download timeout exceeded; aborting automatic attempts.")
        return False

    if platform.system() == "Windows":
        remaining = max(10, int(overall_timeout - (time.time() - start)))
        print("Attempting PowerShell download (Windows fallback)...")
        ok = _powershell_download(url, filename, timeout=remaining)
        if ok:
            print("PowerShell download finished.")
            if callable(progress_reporter):
                try:
                    progress_reporter(100)
                except Exception:
                    pass
            return True
        if time.time() - start >= overall_timeout:
            print("Overall download timeout exceeded after PowerShell attempt; aborting.")
            return False
        remaining = max(10, int(overall_timeout - (time.time() - start)))
        print("PowerShell download failed; attempting BitsAdmin...")
        ok = _bitsadmin_download(url, filename, timeout=remaining)
        if ok:
            print("BitsAdmin download finished.")
            if callable(progress_reporter):
                try:
                    progress_reporter(100)
                except Exception:
                    pass
            return True

    print("All automatic download methods failed.")
    return False

def show_manual_install_dialog(tool_name, target_folder, download_url=None, parent=None):
    app = QApplication.instance()
    abs_folder = os.path.abspath(target_folder)
    if app is None:
        raise RuntimeError("QApplication instance is required for GUI dialogs")
    if parent is None:
        parent = app.activeWindow()
    if parent is None:
        candidates = [w for w in app.topLevelWidgets() if w.isVisible() and not isinstance(w, QMessageBox)]
        main_candidates = [w for w in candidates if w.__class__.__name__ == 'QMainWindow']
        if main_candidates:
            parent = main_candidates[0]
        elif candidates:
            parent = candidates[0]
        else:
            raise RuntimeError("An active window is required as parent for the install dialog")
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle(f"{tool_name} - Manual Install Required")
    if not parent.windowIcon().isNull():
        msg.setWindowIcon(parent.windowIcon())
    app_launch_path = os.path.abspath(BASE_PATH)
    system = platform.system()
    extra_note = ""
    if system == "Windows":
        drive = os.path.splitdrive(app_launch_path)[0]
        if drive and drive.upper().startswith("C:"):
            extra_note = (
                "\n\nNote: Image-Tea is currently located on drive C:. "
                "On some systems, running or extracting tools on C: can be restricted by Windows security. "
                "Please try running Image-Tea from a different drive (e.g., D:) or ensure permissions and antivirus allow writes to the application folder."
            )
    elif system in ("Darwin", "Linux"):
        if any(app_launch_path.startswith(p) for p in ("/Applications", "/usr", "/opt", "/var", "/snap")):
            extra_note = (
                "\n\nNote: Image-Tea appears to be installed in a system location. "
                "System locations may restrict write/execute permissions. "
                "Try running from a user-writable location (e.g., your home directory) or another disk."
            )
    text = f"Download or extraction of {tool_name} failed.\n\n"
    text += f"App launch path: {app_launch_path}\n\n"
    if download_url:
        text += f"Please download manually from:\n{download_url}\n\n"
    text += f"Steps:\n1) Download the package appropriate for your operating system.\n2) Extract the package contents.\n3) Move the extracted files into:\n{abs_folder}\n4) Ensure the executable (e.g., ffmpeg.exe) is present in that folder.\n5) Restart the application if necessary.{extra_note}"

    # Add quick install commands / tips for macOS and major Linux distributions when applicable
    system = platform.system()
    if system in ("Darwin", "Linux"):
        text += "\n\nQuick install (macOS / Linux) - common package manager commands:\n"
        lower_tool = tool_name.lower()
        if lower_tool.startswith("ffmpeg"):
            text += (
                "  Ubuntu/Debian: sudo apt update && sudo apt install ffmpeg\n"
                "  Fedora: sudo dnf install ffmpeg\n"
                "  Arch: sudo pacman -S ffmpeg\n"
                "  macOS (Homebrew): brew install ffmpeg\n"
                "  Snap (if available): sudo snap install ffmpeg\n"
            )
        elif "exif" in lower_tool:
            text += (
                "  Ubuntu/Debian: sudo apt update && sudo apt install libimage-exiftool-perl\n"
                "  Fedora: sudo dnf install perl-Image-ExifTool\n"
                "  Arch: sudo pacman -S perl-image-exiftool\n"
                "  macOS (Homebrew): brew install exiftool\n"
            )
        elif "ghostscript" in lower_tool or lower_tool.startswith("ghostscript"):
            text += (
                "  Ubuntu/Debian: sudo apt update && sudo apt install ghostscript\n"
                "  Fedora: sudo dnf install ghostscript\n"
                "  Arch: sudo pacman -S ghostscript\n"
                "  macOS (Homebrew): brew install ghostscript\n"
            )
        elif "cairo" in lower_tool:
            text += (
                "  Ubuntu/Debian: sudo apt update && sudo apt install libcairo2 libcairo2-dev\n"
                "  Fedora: sudo dnf install cairo cairo-devel\n"
                "  Arch: sudo pacman -S cairo\n"
                "  macOS (Homebrew): brew install cairo\n"
            )
        else:
            text += f"  For {tool_name}, please use your distribution package manager (apt/dnf/pacman) or Homebrew on macOS.\n"

    msg.setText(text)
    open_btn = msg.addButton("Open Tools Folder", QMessageBox.ActionRole)
    guide_btn = None
    if download_url:
        guide_btn = msg.addButton("Open Download Page", QMessageBox.ActionRole)
    msg.addButton(QMessageBox.Ok)
    msg.exec()
    clicked = msg.clickedButton()
    if clicked == open_btn:
        system = platform.system()
        if system == "Windows":
            os.startfile(abs_folder)
        elif system == "Darwin":
            subprocess.run(["open", abs_folder])
        else:
            subprocess.run(["xdg-open", abs_folder])
    if download_url and guide_btn is not None and clicked == guide_btn:
        webbrowser.open(download_url)

def _emit(reporter, message: str):
    if callable(reporter):
        try:
            reporter(message)
        except Exception:
            print(message)
    else:
        print(message)


def compute_tools_work_units() -> dict:
    units = {}
    for tool in expected:
        folder = os.path.join(BASE_PATH, 'tools', tool)
        if is_executable_available(tool, folder):
            units[tool] = 1
        else:
            units[tool] = 4
    return units


class ProgressAggregator:
    def __init__(self, progress_reporter=None):
        self.progress_reporter = progress_reporter
        self.total_units = 0
        self.completed_units = 0.0
        self._partial_units = 0.0

    def add_total_units(self, n: int):
        self.total_units += int(n)

    def unit_completed(self):
        self.completed_units += 1.0
        self._partial_units = 0.0
        self._report()

    def make_unit_progress_reporter(self, units_for_task: float = 1.0):
        def _reporter(percent: int):
            try:
                frac = max(0.0, min(1.0, float(percent) / 100.0))
                self._partial_units = units_for_task * frac
                self._report()
            except Exception:
                pass
        return _reporter

    def _report(self):
        if not self.total_units:
            return
        completed = float(self.completed_units) + float(self._partial_units)
        pct = int(min(100, (completed / float(self.total_units)) * 100.0))
        if callable(self.progress_reporter):
            try:
                self.progress_reporter(pct)
            except Exception:
                print(f"Progress: {pct}%")

    def reset(self):
        self.total_units = 0
        self.completed_units = 0.0
        self._partial_units = 0.0


def check_folders(reporter=None, progress_reporter=None, unit_callback=None):
    system = platform.system()
    
    for folder in expected_full:
        tool_name = os.path.basename(folder)

        _emit(reporter, f"Preparing tools (checking {tool_name})")

        if not os.path.isdir(folder):
            if system != "Windows" and tool_name in ["ghostscript", "exiftool", "ffmpeg"]:
                if check_system_tool(tool_name):
                    os.makedirs(folder, exist_ok=True)
                    _emit(reporter, f"Preparing tools ({tool_name} found in system PATH)")
                    if callable(unit_callback):
                        unit_callback()
                    continue
                if tool_name == "ffmpeg":
                    app = QApplication.instance()
                    if app is not None:
                        try:
                            show_manual_install_dialog("FFmpeg", folder, "https://ffmpeg.org/download.html", parent=app.activeWindow())
                        except Exception as e:
                            print(f"[ToolsChecker] Could not show FFmpeg install dialog: {e}")
                    else:
                        print("FFmpeg not found in PATH. Install examples:")
                        print("  Ubuntu/Debian: sudo apt update && sudo apt install ffmpeg")
                        print("  Fedora: sudo dnf install ffmpeg")
                        print("  Arch: sudo pacman -S ffmpeg")
                        print("  macOS (Homebrew): brew install ffmpeg")
                    continue

            _emit(reporter, f"Preparing tools (downloading {tool_name})")
            os.makedirs(folder, exist_ok=True)
            if callable(unit_callback):
                unit_callback()

            if system == "Windows":
                if folder.endswith("ghostscript"):
                    download_and_extract_ghostscript(folder, reporter=reporter, progress_reporter=progress_reporter, unit_callback=unit_callback)
                elif folder.endswith("exiftool"):
                    download_and_extract_exiftool(folder, reporter=reporter, progress_reporter=progress_reporter, unit_callback=unit_callback)
                elif folder.endswith("cairo"):
                    download_and_extract_cairo(folder, reporter=reporter, progress_reporter=progress_reporter, unit_callback=unit_callback)
                elif folder.endswith("ffmpeg"):
                    download_and_extract_ffmpeg(folder, reporter=reporter, progress_reporter=progress_reporter, unit_callback=unit_callback)
                elif folder.endswith("realesrgan"):
                    download_and_extract_realesrgan(folder, reporter=reporter, progress_reporter=progress_reporter, unit_callback=unit_callback)
            else:
                # For non-Windows we also attempt deterministic download of RealESRGAN into the local tools folder
                if folder.endswith("realesrgan"):
                    download_and_extract_realesrgan(folder, reporter=reporter, progress_reporter=progress_reporter, unit_callback=unit_callback)
                else:
                    print(f"{tool_name} not found. Please ensure it's installed via system package manager.")
                    if folder.endswith("cairo"):
                        print("Note: Cairo is typically included with PySide6/Qt on Linux/Mac.")

        else:
            # Folder exists; verify the tool is actually present and usable. If the top-level folder exists but
            # executables or DLLs are missing, attempt deterministic download+extract (Windows) or warn the user (non-Windows).
            if tool_name in ["ffmpeg", "realesrgan", "exiftool", "ghostscript", "cairo"]:
                ok = is_executable_available(tool_name, folder)
                if ok:
                    _emit(reporter, f"Preparing tools ({tool_name} ready)")
                    if callable(unit_callback):
                        unit_callback()
                else:
                    _emit(reporter, f"Preparing tools ({tool_name} incomplete; downloading)")
                    if callable(unit_callback):
                        unit_callback()
                    print(f"Folder exists but {tool_name} appears incomplete or missing required files: {folder}")
                    if system == "Windows":
                        _emit(reporter, f"Preparing tools (downloading {tool_name})")
                        if tool_name == "ghostscript":
                            download_and_extract_ghostscript(folder, reporter=reporter, progress_reporter=progress_reporter, unit_callback=unit_callback)
                        elif tool_name == "exiftool":
                            download_and_extract_exiftool(folder, reporter=reporter, progress_reporter=progress_reporter, unit_callback=unit_callback)
                        elif tool_name == "cairo":
                            download_and_extract_cairo(folder, reporter=reporter, progress_reporter=progress_reporter, unit_callback=unit_callback)
                        elif tool_name == "ffmpeg":
                            download_and_extract_ffmpeg(folder, reporter=reporter, progress_reporter=progress_reporter, unit_callback=unit_callback)
                        elif tool_name == "realesrgan":
                            download_and_extract_realesrgan(folder, reporter=reporter, progress_reporter=progress_reporter, unit_callback=unit_callback)
                    else:
                        print(f"{tool_name} appears incomplete. Please install or extract the tool into: {folder}")

def download_and_extract_ghostscript(target_folder, reporter=None, progress_reporter=None, unit_callback=None) -> bool:
    url = "https://github.com/mudrikam/ghostscript-for-image-tea/archive/refs/heads/main.zip"
    zip_path = os.path.join(target_folder, "ghostscript.zip")
    _emit(reporter, f"Preparing tools (downloading ghostscript)")

    ok = download_with_progress(url, zip_path, progress_reporter=progress_reporter)
    if not ok:
        _emit(reporter, "Preparing tools (failed to download ghostscript)")
        print("Failed to download Ghostscript; check network, TLS and system policies.")
        return False
    if callable(unit_callback):
        unit_callback()

    _emit(reporter, "Preparing tools (extracting ghostscript)")
    ok = _extract_and_flatten_zip(zip_path, target_folder)
    if not ok:
        _emit(reporter, "Preparing tools (failed to extract ghostscript)")
        print("Failed to extract Ghostscript archive; please extract manually.")
        return False
    if callable(unit_callback):
        unit_callback()

    _emit(reporter, "Preparing tools (ghostscript installed successfully)")
    if callable(unit_callback):
        unit_callback()
    return True

def download_and_extract_exiftool(target_folder, reporter=None, progress_reporter=None, unit_callback=None) -> bool:
    url = "https://github.com/mudrikam/exiftool-for-image-tea/archive/refs/heads/main.zip"
    zip_path = os.path.join(target_folder, "exiftool.zip")
    _emit(reporter, f"Preparing tools (downloading exiftool)")

    ok = download_with_progress(url, zip_path, progress_reporter=progress_reporter)
    if not ok:
        _emit(reporter, "Preparing tools (failed to download exiftool)")
        print("Failed to download Exiftool; check network, TLS and system policies.")
        return False
    if callable(unit_callback):
        unit_callback()

    _emit(reporter, "Preparing tools (extracting exiftool)")
    ok = _extract_and_flatten_zip(zip_path, target_folder)
    if not ok:
        _emit(reporter, "Preparing tools (failed to extract exiftool)")
        print("Failed to extract Exiftool archive; please extract manually.")
        return False
    if callable(unit_callback):
        unit_callback()

    _emit(reporter, "Preparing tools (exiftool installed successfully)")
    if callable(unit_callback):
        unit_callback()
    return True

def download_and_extract_cairo(target_folder, reporter=None, progress_reporter=None, unit_callback=None) -> bool:
    url = "https://github.com/preshing/cairo-windows/releases/download/with-tee/cairo-windows-1.17.2.zip"
    zip_path = os.path.join(target_folder, "cairo.zip")
    _emit(reporter, f"Preparing tools (downloading cairo)")

    ok = download_with_progress(url, zip_path, progress_reporter=progress_reporter)
    if not ok:
        _emit(reporter, "Preparing tools (failed to download cairo)")
        print("Failed to download Cairo; check network, TLS and system policies.")
        return False
    if callable(unit_callback):
        unit_callback()

    _emit(reporter, "Preparing tools (extracting cairo)")
    ok = _extract_and_flatten_zip(zip_path, target_folder)
    if not ok:
        _emit(reporter, "Preparing tools (failed to extract cairo)")
        print("Failed to extract Cairo archive; please extract manually.")
        return False
    if callable(unit_callback):
        unit_callback()

    _emit(reporter, "Preparing tools (cairo installed successfully)")
    if callable(unit_callback):
        unit_callback()
    return True

def download_and_extract_ffmpeg(target_folder, reporter=None, progress_reporter=None, unit_callback=None) -> bool:
    url = "https://github.com/mudrikam/ffmpeg-for-image-tea/archive/refs/heads/main.zip"
    zip_path = os.path.join(target_folder, "ffmpeg.zip")
    _emit(reporter, f"Preparing tools (downloading ffmpeg)")

    ok = download_with_progress(url, zip_path, progress_reporter=progress_reporter)
    if not ok:
        _emit(reporter, "Preparing tools (failed to download ffmpeg)")
        print("Failed to download FFmpeg; check network, TLS and system policies.")
        return False
    if callable(unit_callback):
        unit_callback()

    _emit(reporter, "Preparing tools (extracting ffmpeg)")
    ok = _extract_and_flatten_zip(zip_path, target_folder)
    if not ok:
        _emit(reporter, "Preparing tools (failed to extract ffmpeg)")
        print("Failed to extract FFmpeg archive; please extract manually.")
        return False
    if callable(unit_callback):
        unit_callback()

    if not is_executable_available("ffmpeg", target_folder):
        _emit(reporter, "Preparing tools (ffmpeg verification failed)")
        print(f"Error: FFmpeg executables not found in {target_folder} after extraction")
        return False
    if callable(unit_callback):
        unit_callback()

    _emit(reporter, "Preparing tools (ffmpeg installed successfully)")
    return True

def _extract_and_flatten_zip(zip_path, target_folder) -> bool:
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_folder)
    except Exception as e:
        print(f"Failed to extract {zip_path}: {e}")
        return False

    try:
        entries = [e for e in os.listdir(target_folder) if e not in ("realesrgan.zip", "ffmpeg.zip", "ghostscript.zip", "exiftool.zip", "cairo.zip")]
        if len(entries) == 1:
            root = os.path.join(target_folder, entries[0])
            if os.path.isdir(root):
                for name in os.listdir(root):
                    src = os.path.join(root, name)
                    dst = os.path.join(target_folder, name)
                    if os.path.exists(dst):
                        if os.path.isdir(dst):
                            shutil.rmtree(dst)
                        else:
                            os.remove(dst)
                    shutil.move(src, dst)
                try:
                    os.rmdir(root)
                except Exception:
                    pass
        if os.path.exists(zip_path):
            os.remove(zip_path)
        return True
    except Exception as e:
        print(f"Error while flattening extracted files: {e}")
        return False


def download_and_extract_realesrgan(target_folder, reporter=None, progress_reporter=None, unit_callback=None) -> bool:
    system = platform.system()
    urls = {
        "Windows": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip",
        "Darwin": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-macos.zip",
        "Linux": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip"
    }

    url = urls.get(system)
    if not url:
        print(f"No RealESRGAN download URL available for platform: {system}")
        return False

    zip_path = os.path.join(target_folder, "realesrgan.zip")
    _emit(reporter, f"Preparing tools (downloading realesrgan)")
    ok = download_with_progress(url, zip_path, progress_reporter=progress_reporter)
    if not ok:
        _emit(reporter, "Preparing tools (failed to download realesrgan)")
        print("Failed to download RealESRGAN; check network, TLS and system policies.")
        return False
    if callable(unit_callback):
        unit_callback()

    _emit(reporter, "Preparing tools (extracting realesrgan)")
    ok = _extract_and_flatten_zip(zip_path, target_folder)
    if not ok:
        _emit(reporter, "Preparing tools (failed to extract realesrgan)")
        print("Failed to extract RealESRGAN archive; please extract manually.")
        return False
    if callable(unit_callback):
        unit_callback()

    # Ensure the extracted RealESRGAN binary has execute permissions on non-Windows systems
    executable_candidate = find_executable_in_folder(target_folder, ["realesrgan-ncnn-vulkan", "realesrgan-ncnn-vulkan.exe"])
    if executable_candidate and os.name != 'nt':
        try:
            st = os.stat(executable_candidate).st_mode
            if not (st & 0o111):
                os.chmod(executable_candidate, st | 0o755)
                print(f"Set executable permission on {executable_candidate}")
        except Exception as e:
            print(f"Failed to set executable bit on {executable_candidate}: {e}")

    if not is_executable_available("realesrgan", target_folder):
        _emit(reporter, "Preparing tools (realesrgan verification failed)")
        print(f"Error: RealESRGAN executables not found or not executable in {target_folder} after extraction")
        return False
    if callable(unit_callback):
        unit_callback()

    _emit(reporter, "Preparing tools (realesrgan installed successfully)")
    return True


def find_executable_in_folder(folder, names):
    for root, dirs, files in os.walk(folder):
        for name in names:
            if name in files:
                path = os.path.join(root, name)
                if os.path.isfile(path):
                    return path
    return None


def _candidate_exists_in_path(candidate_names):
    for name in candidate_names:
        if shutil.which(name):
            return True
    return False


def is_vulkan_available() -> bool:
    """Deterministic check for Vulkan availability on non-Windows platforms.

    Returns True if there's reasonable evidence Vulkan is available (vulkaninfo present
    and runnable, or ICD files present, or /dev/dri devices exist). False otherwise.
    """
    if platform.system() == 'Windows':
        return True

    # Prefer explicit 'vulkaninfo' if available
    if shutil.which('vulkaninfo'):
        try:
            res = subprocess.run(['vulkaninfo'], capture_output=True, text=True, timeout=5)
            return res.returncode == 0 and bool(res.stdout.strip())
        except subprocess.TimeoutExpired:
            print("System Notice: 'vulkaninfo' timed out during Vulkan check")
            return False
        except Exception as e:
            print(f"System Notice: 'vulkaninfo' check failed: {e}")
            return False

    # Check for ICD files
    icd_paths = ['/etc/vulkan/icd.d', '/usr/share/vulkan/icd.d']
    for p in icd_paths:
        try:
            if os.path.isdir(p) and any(f.endswith('.json') for f in os.listdir(p)):
                return True
        except Exception:
            pass

    # Check for /dev/dri presence as a heuristic for GPU drivers
    try:
        if os.path.isdir('/dev/dri') and any(os.path.exists(os.path.join('/dev/dri', f)) for f in os.listdir('/dev/dri')):
            return True
    except Exception:
        pass

    return False


def is_executable_available(tool_name, tool_folder):
    if tool_name == "cairo":
        for root, dirs, files in os.walk(tool_folder):
            for f in files:
                name = f.lower()
                if os.name == 'nt' and name.endswith('.dll') and ('cairo' in name or 'libcairo' in name):
                    return True
                if os.name != 'nt' and (name.endswith('.dylib') or name.endswith('.so')) and 'cairo' in name:
                    return True
        return False

    reqs = EXECUTABLE_REQUIREMENTS.get(tool_name, [])
    for base in reqs:
        candidates = [base, f"{base}.exe"]
        if tool_name == "realesrgan":
            found_in_folder = find_executable_in_folder(tool_folder, candidates)
            if not found_in_folder:
                return False
            # On non-Windows ensure the file is executable
            if os.name != 'nt' and not os.access(found_in_folder, os.X_OK):
                return False
            continue
        if _candidate_exists_in_path(candidates):
            continue
        found_in_folder = find_executable_in_folder(tool_folder, candidates)
        if not found_in_folder:
            return False
    return True


def ensure_tool_executable(tool_name, tool_folder, reporter=None, progress_reporter=None, unit_callback=None):
    if is_executable_available(tool_name, tool_folder):
        _emit(reporter, f"Preparing tools ({tool_name} ready)")
        return True
    _emit(reporter, f"Preparing tools ({tool_name} missing; attempting install)")

    if tool_name == "ffmpeg":
        if platform.system() == "Windows":
            ok = download_and_extract_ffmpeg(tool_folder, reporter=reporter, progress_reporter=progress_reporter, unit_callback=unit_callback)
            if not ok:
                print("Failed to install ffmpeg via automatic method.")
        else:
            app = QApplication.instance()
            if app is not None:
                try:
                    show_manual_install_dialog("FFmpeg", tool_folder, "https://ffmpeg.org/download.html", parent=app.activeWindow())
                except Exception as e:
                    print(f"[ToolsChecker] Could not show FFmpeg install dialog: {e}")
            else:
                print("FFmpeg not found. Please install FFmpeg: https://ffmpeg.org/download.html")
                print("Install examples:\n  Ubuntu/Debian: sudo apt update && sudo apt install ffmpeg\n  Fedora: sudo dnf install ffmpeg\n  Arch: sudo pacman -S ffmpeg\n  macOS (Homebrew): brew install ffmpeg")
            return False
    elif tool_name == "realesrgan":
        ok = download_and_extract_realesrgan(tool_folder, reporter=reporter, progress_reporter=progress_reporter, unit_callback=unit_callback)
        if not ok:
            print("Failed to install realesrgan via automatic method.")
    else:
        print(f"No auto-install handler for {tool_name}")
        return False

    if is_executable_available(tool_name, tool_folder):
        _emit(reporter, f"Preparing tools ({tool_name} installed successfully)")
        return True

    print(f"Error: {tool_name} executable(s) still missing after attempted extraction.")
    dl_url = None
    if tool_name == "ffmpeg":
        dl_url = "https://github.com/mudrikam/ffmpeg-for-image-tea/archive/refs/heads/main.zip"
    elif tool_name == "realesrgan":
        system = platform.system()
        urls = {
            "Windows": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip",
            "Darwin": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-macos.zip",
            "Linux": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-ubuntu.zip"
        }
        dl_url = urls.get(system)
    print(f"Manual install required. Please download and install {tool_name} from: {dl_url}")
    return False


def ensure_executables_for_tools(reporter=None, progress_reporter=None, unit_callback=None):
    overall_ok = True
    targets = {
        "ffmpeg": os.path.join(BASE_PATH, "tools", "ffmpeg"),
        "realesrgan": os.path.join(BASE_PATH, "tools", "realesrgan"),
    }
    for name, folder in targets.items():
        if not ensure_tool_executable(name, folder, reporter=reporter, progress_reporter=progress_reporter, unit_callback=unit_callback):
            overall_ok = False
    return overall_ok


def install_pyautogui(python_exe: str | None = None, version: str = '0.9.53') -> bool:
    """Upgrade pip/tools and install a specific PyAutoGUI version using the given python executable.

    If no executable is provided, uses embedded Python if available, otherwise current interpreter.
    """
    if python_exe is None:
        python_exe = get_embedded_python_path()
    if not os.path.exists(python_exe):
        print("Error: Python executable not found; cannot install pyautogui.")
        return False
    try:
        res = subprocess.run([python_exe, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], capture_output=True, timeout=300)
        if res.returncode != 0:
            print(f"Error upgrading pip/setuptools/wheel: {res.stderr.decode('utf-8', errors='ignore')}")
    except subprocess.TimeoutExpired:
        print("Timeout while upgrading pip/setuptools/wheel")
    except Exception as e:
        print(f"Error upgrading pip/setuptools/wheel: {e}")
    try:
        res = subprocess.run([python_exe, "-m", "pip", "install", f"pyautogui=={version}", "--no-warn-script-location"], capture_output=True, timeout=600)
        if res.returncode == 0:
            return True
        print(f"Error installing pyautogui: {res.stderr.decode('utf-8', errors='ignore')} | {res.stdout.decode('utf-8', errors='ignore')}")
        return False
    except subprocess.TimeoutExpired:
        print("Timeout while installing pyautogui")
        return False
    except Exception as e:
        print(f"Error installing pyautogui: {e}")
        return False


def is_pyautogui_installed(python_exe: str | None = None) -> tuple[bool, str]:
    """Return (True, version) if PyAutoGUI can be imported with the selected python executable,
    otherwise return (False, error_message).
    """
    if python_exe is None:
        python_exe = get_embedded_python_path()
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


def install_requirements(python_exe: str | None = None) -> bool:
    """Install all packages from requirements.txt if missing.
    
    Returns True if all packages are available after this call.
    """
    requirements_marker = os.path.join(BASE_PATH, "temp", ".requirements_verified")
    
    if os.path.exists(requirements_marker):
        return True
    
    if python_exe is None:
        python_exe = get_embedded_python_path()
    
    if not os.path.exists(python_exe):
        print("Error: Python executable not found; cannot install requirements.")
        return False
    
    requirements_path = os.path.join(BASE_PATH, "requirements.txt")
    if not os.path.exists(requirements_path):
        print(f"Warning: requirements.txt not found at {requirements_path}")
        return True
    
    print("Checking required packages from requirements.txt...")
    
    try:
        result = subprocess.run(
            [python_exe, "-m", "pip", "install", "-r", requirements_path, "--no-warn-script-location"],
            capture_output=True,
            timeout=300
        )
        
        if result.returncode == 0:
            print("All required packages verified/installed successfully.")
            os.makedirs(os.path.dirname(requirements_marker), exist_ok=True)
            with open(requirements_marker, 'w') as f:
                f.write("Requirements verified")
            return True
        else:
            print(f"Error installing requirements: {result.stderr.decode('utf-8', errors='ignore')}")
            return False
            
    except Exception as e:
        print(f"Error checking requirements: {e}")
        return False


def ensure_tools_ready(python_exe: str | None = None, pyautogui_version: str = '0.9.53', reporter=None, progress_reporter=None, unit_callback=None) -> bool:
    """Perform the standard tool checks and ensure PyAutoGUI is available.

    Returns True if basic tooling appears ready (folders present and PyAutoGUI importable).
    """
    check_folders(reporter=reporter, progress_reporter=progress_reporter, unit_callback=unit_callback)
    exe_ok = ensure_executables_for_tools(reporter=reporter, progress_reporter=progress_reporter, unit_callback=unit_callback)
    if not exe_ok:
        return False
    ok = ensure_pyautogui(python_exe, pyautogui_version)
    if not ok:
        return False
    
    ok_req = install_requirements(python_exe)
    if not ok_req:
        return False
    
    return True


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