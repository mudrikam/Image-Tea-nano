import os
import json
import shutil
import platform
import subprocess
import sys
import re
from pathlib import Path
from typing import Optional, List, Dict

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QLineEdit, QTableWidget, QTableWidgetItem,
    QFileDialog, QMessageBox, QHeaderView, QAbstractItemView,
    QGroupBox, QFormLayout, QSpinBox, QCheckBox, QProgressDialog,
    QTextEdit
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QIcon
import qtawesome as qta

from config import BASE_PATH
from ui.theme_system import theme


MODELS_CONFIG_FILE = Path(BASE_PATH) / "configs" / "upscaler_models_config.json"
DEPS_MARKER_FILE = Path(BASE_PATH) / "temp" / ".upscaler_deps_installed"


def get_default_models_dir() -> Path:
    return Path(BASE_PATH) / "tools" / "realesrgan" / "models"


def get_waifu2x_path() -> Path:
    system = platform.system()
    bin_name = "waifu2x-ncnn-vulkan.exe" if system == "Windows" else "waifu2x-ncnn-vulkan"
    return Path(BASE_PATH) / "tools" / "waifu2x" / bin_name


def get_waifu2x_models_dir() -> Path:
    return Path(BASE_PATH) / "tools" / "waifu2x"


def has_nvidia_gpu() -> bool:
    """Check if system has NVIDIA GPU."""
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False


def are_pth_deps_installed() -> bool:
    """Check if PyTorch and required PTH dependencies are installed.

    Returns True when PyTorch is present and at least one of:
    - the RealESRGAN package (providing RealESRGANer), or
    - the basicsr package (providing RRDBNet) is available.
    """
    if DEPS_MARKER_FILE.exists():
        content = DEPS_MARKER_FILE.read_text()
        if "pth_installed" in content:
            return True

    try:
        import torch
    except ImportError:
        return False

    # Accept either realesrgan (high-level helper) or basicsr (low-level RRDBNet implementation)
    try:
        from realesrgan import RealESRGANer  # type: ignore
        return True
    except Exception:
        pass

    try:
        import basicsr  # type: ignore
        return True
    except Exception:
        return False


def are_onnx_deps_installed() -> bool:
    """Check if ONNX Runtime is installed."""
    if DEPS_MARKER_FILE.exists():
        content = DEPS_MARKER_FILE.read_text()
        if "onnx_installed" in content:
            return True
    
    try:
        import onnxruntime
        return True
    except ImportError:
        return False


def get_deps_status() -> Dict[str, bool]:
    """Get installation status of optional dependencies."""
    return {
        'pth': are_pth_deps_installed(),
        'onnx': are_onnx_deps_installed(),
        'nvidia_gpu': has_nvidia_gpu()
    }


class DependencyInstallerWorker(QThread):
    """Worker thread for installing/uninstalling dependencies without blocking UI."""
    progress_signal = Signal(str)
    step_signal = Signal(int, int, str)
    finished_signal = Signal(bool, str)
    
    def __init__(self, dep_type: str, action: str = 'install'):
        super().__init__()
        self.dep_type = dep_type
        self.action = action
        self._stop_requested = False
    
    def stop(self):
        self._stop_requested = True
    
    def run(self):
        python_exe = sys.executable
        
        try:
            if self.action == 'install':
                if self.dep_type == 'pth':
                    self._install_pth_deps(python_exe)
                elif self.dep_type == 'onnx':
                    self._install_onnx_deps(python_exe)
                else:
                    self.finished_signal.emit(False, f"Unknown dependency type: {self.dep_type}")
                    return
                
                self.finished_signal.emit(True, f"{self.dep_type.upper()} dependencies installed successfully!")
            elif self.action == 'uninstall':
                if self.dep_type == 'pth':
                    self._uninstall_pth_deps(python_exe)
                elif self.dep_type == 'onnx':
                    self._uninstall_onnx_deps(python_exe)
                else:
                    self.finished_signal.emit(False, f"Unknown dependency type: {self.dep_type}")
                    return
                
                self.finished_signal.emit(True, f"{self.dep_type.upper()} dependencies uninstalled successfully!")
            
        except Exception as e:
            action_text = "Installation" if self.action == 'install' else "Uninstallation"
            self.finished_signal.emit(False, f"{action_text} failed: {e}")
    
    def _install_pth_deps(self, python_exe: str):
        has_gpu = has_nvidia_gpu()
        total_steps = 7
        current_step = 0
        
        current_step += 1
        self.step_signal.emit(current_step, total_steps, "Checking GPU...")
        
        if has_gpu:
            current_step += 1
            self.step_signal.emit(current_step, total_steps, "Installing PyTorch with CUDA...")
            self.progress_signal.emit("Detected NVIDIA GPU. Installing PyTorch with CUDA support...")
            self.progress_signal.emit("This may take several minutes (downloading ~2.5GB)...")
            
            subprocess.run(
                [python_exe, "-m", "pip", "uninstall", "torch", "torchvision", "-y"],
                capture_output=True, timeout=60
            )
            
            result = subprocess.run(
                [python_exe, "-m", "pip", "install", "torch", "torchvision",
                 "--index-url", "https://download.pytorch.org/whl/cu124",
                 "--no-warn-script-location"],
                capture_output=True, timeout=1200
            )
            if result.returncode != 0:
                raise Exception(f"PyTorch CUDA install failed: {result.stderr.decode('utf-8', errors='ignore')}")
        else:
            current_step += 1
            self.step_signal.emit(current_step, total_steps, "Installing PyTorch CPU...")
            self.progress_signal.emit("No NVIDIA GPU detected. Installing PyTorch CPU version...")
            result = subprocess.run(
                [python_exe, "-m", "pip", "install", "torch", "torchvision",
                 "--no-warn-script-location"],
                capture_output=True, timeout=600
            )
            if result.returncode != 0:
                raise Exception(f"PyTorch CPU install failed: {result.stderr.decode('utf-8', errors='ignore')}")
        
        self.progress_signal.emit("✓ PyTorch installed successfully")
        
        packages = ["basicsr==1.4.2", "facexlib", "gfpgan", "realesrgan"]
        for pkg in packages:
            if self._stop_requested:
                raise Exception("Installation cancelled by user")
            current_step += 1
            self.step_signal.emit(current_step, total_steps, f"Installing {pkg}...")
            self.progress_signal.emit(f"Installing {pkg}...")
            result = subprocess.run(
                [python_exe, "-m", "pip", "install", pkg, "--no-warn-script-location"],
                capture_output=True, timeout=300
            )
            if result.returncode != 0:
                raise Exception(f"Failed to install {pkg}: {result.stderr.decode('utf-8', errors='ignore')}")
            self.progress_signal.emit(f"✓ {pkg} installed")
        
        current_step += 1
        self.step_signal.emit(current_step, total_steps, "Patching basicsr...")
        self.progress_signal.emit("Patching basicsr for torchvision compatibility...")
        self._patch_basicsr(python_exe)
        
        self.step_signal.emit(total_steps, total_steps, "Complete!")
        
        DEPS_MARKER_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(DEPS_MARKER_FILE, 'a') as f:
            f.write("pth_installed\n")
    
    def _install_onnx_deps(self, python_exe: str):
        total_steps = 2
        
        self.step_signal.emit(1, total_steps, "Installing ONNX Runtime...")
        self.progress_signal.emit("Installing ONNX Runtime...")
        result = subprocess.run(
            [python_exe, "-m", "pip", "install", "onnxruntime", "--no-warn-script-location"],
            capture_output=True, timeout=300
        )
        if result.returncode != 0:
            raise Exception(f"ONNX Runtime install failed: {result.stderr.decode('utf-8', errors='ignore')}")
        
        self.progress_signal.emit("✓ ONNX Runtime installed")
        self.step_signal.emit(2, total_steps, "Complete!")
        
        DEPS_MARKER_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(DEPS_MARKER_FILE, 'a') as f:
            f.write("onnx_installed\n")
    
    def _uninstall_pth_deps(self, python_exe: str):
        """Uninstall PyTorch and related packages."""
        total_steps = 6
        packages = ["realesrgan", "gfpgan", "facexlib", "basicsr", "torchvision", "torch"]
        
        for i, pkg in enumerate(packages, start=1):
            if self._stop_requested:
                raise Exception("Uninstallation cancelled by user")
            self.step_signal.emit(i, total_steps, f"Uninstalling {pkg}...")
            self.progress_signal.emit(f"Uninstalling {pkg}...")
            result = subprocess.run(
                [python_exe, "-m", "pip", "uninstall", pkg, "-y"],
                capture_output=True, timeout=60
            )
            if result.returncode == 0:
                self.progress_signal.emit(f"✓ {pkg} uninstalled")
            else:
                self.progress_signal.emit(f"⚠ {pkg} not found or already uninstalled")
        
        self.step_signal.emit(total_steps, total_steps, "Complete!")
        
        if DEPS_MARKER_FILE.exists():
            content = DEPS_MARKER_FILE.read_text()
            content = content.replace("pth_installed\n", "")
            DEPS_MARKER_FILE.write_text(content)
    
    def _uninstall_onnx_deps(self, python_exe: str):
        """Uninstall ONNX Runtime."""
        total_steps = 1
        
        self.step_signal.emit(1, total_steps, "Uninstalling ONNX Runtime...")
        self.progress_signal.emit("Uninstalling ONNX Runtime...")
        result = subprocess.run(
            [python_exe, "-m", "pip", "uninstall", "onnxruntime", "-y"],
            capture_output=True, timeout=60
        )
        if result.returncode == 0:
            self.progress_signal.emit("✓ ONNX Runtime uninstalled")
        else:
            self.progress_signal.emit("⚠ ONNX Runtime not found or already uninstalled")
        
        self.step_signal.emit(total_steps, total_steps, "Complete!")
        
        if DEPS_MARKER_FILE.exists():
            content = DEPS_MARKER_FILE.read_text()
            content = content.replace("onnx_installed\n", "")
            DEPS_MARKER_FILE.write_text(content)
    
    def _patch_basicsr(self, python_exe: str):
        """Patch basicsr for torchvision compatibility."""
        try:
            result = subprocess.run(
                [python_exe, "-c", "import site; print(site.getsitepackages()[0])"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return
            
            site_packages = result.stdout.strip()
            degradations_file = os.path.join(site_packages, "basicsr", "data", "degradations.py")
            
            if not os.path.exists(degradations_file):
                return
            
            with open(degradations_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'from torchvision.transforms.functional_tensor import rgb_to_grayscale' in content:
                content = content.replace(
                    'from torchvision.transforms.functional_tensor import rgb_to_grayscale',
                    'from torchvision.transforms.functional import rgb_to_grayscale'
                )
                with open(degradations_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.progress_signal.emit("basicsr patched successfully.")
        except Exception as e:
            self.progress_signal.emit(f"Warning: Could not patch basicsr: {e}")


class DependencyInstallerDialog(QDialog):
    """Dialog for installing/uninstalling PTH/ONNX dependencies."""
    
    def __init__(self, parent=None, dep_type: str = 'pth', action: str = 'install'):
        super().__init__(parent)
        self.dep_type = dep_type
        self.action = action
        self.worker = None
        self.success = False
        
        action_text = "Install" if action == 'install' else "Uninstall"
        if dep_type == 'pth':
            self.setWindowTitle(f"{action_text} PyTorch Dependencies")
        else:
            self.setWindowTitle(f"{action_text} ONNX Dependencies")
        
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setMinimumSize(550, 400)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        if self.action == 'install':
            if self.dep_type == 'pth':
                info_text = (
                    "PTH models require PyTorch and RealESRGAN Python packages.\n\n"
                    "Packages to install:\n"
                    "• PyTorch (with CUDA if NVIDIA GPU detected)\n"
                    "• torchvision\n"
                    "• basicsr\n"
                    "• facexlib\n"
                    "• gfpgan\n"
                    "• realesrgan\n\n"
                    "Download size: ~2.5GB (CUDA) or ~500MB (CPU)\n"
                    "This may take several minutes."
                )
            else:
                info_text = (
                    "ONNX models require ONNX Runtime package.\n\n"
                    "Packages to install:\n"
                    "• onnxruntime\n\n"
                    "Download size: ~50MB\n"
                    "This should be quick."
                )
        else:
            if self.dep_type == 'pth':
                info_text = (
                    "Uninstall PyTorch and RealESRGAN Python packages.\n\n"
                    "Packages to uninstall:\n"
                    "• realesrgan\n"
                    "• gfpgan\n"
                    "• facexlib\n"
                    "• basicsr\n"
                    "• torchvision\n"
                    "• PyTorch\n\n"
                    "This will remove all PTH model support."
                )
            else:
                info_text = (
                    "Uninstall ONNX Runtime package.\n\n"
                    "Packages to uninstall:\n"
                    "• onnxruntime\n\n"
                    "This will remove ONNX model support."
                )
        
        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        from PySide6.QtWidgets import QProgressBar
        
        action_text = "Installation" if self.action == 'install' else "Uninstallation"
        progress_group = QGroupBox(f"{action_text} Progress")
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(8)
        
        ready_text = "Ready to install" if self.action == 'install' else "Ready to uninstall"
        self.step_label = QLabel(ready_text)
        self.step_label.setStyleSheet("font-weight: bold;")
        progress_layout.addWidget(self.step_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% (%v/%m steps)")
        progress_layout.addWidget(self.progress_bar)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        log_placeholder = "Installation log will appear here..." if self.action == 'install' else "Uninstallation log will appear here..."
        self.log_text.setPlaceholderText(log_placeholder)
        layout.addWidget(self.log_text)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self._cancel)
        button_layout.addWidget(self.btn_cancel)
        
        btn_icon = qta.icon('fa6s.download') if self.action == 'install' else qta.icon('fa6s.trash')
        btn_text = " Install" if self.action == 'install' else " Uninstall"
        self.btn_action = QPushButton(btn_icon, btn_text)
        self.btn_action.clicked.connect(self._start_action)
        button_layout.addWidget(self.btn_action)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def _start_action(self):
        self.btn_action.setEnabled(False)
        self.btn_cancel.setText("Stop")
        action_text = "installation" if self.action == 'install' else "uninstallation"
        self.log_text.append(f"Starting {action_text}...")
        self.step_label.setText("Initializing...")
        
        if self.action == 'install':
            if self.dep_type == 'pth':
                self.progress_bar.setMaximum(7)
            else:
                self.progress_bar.setMaximum(2)
        else:
            if self.dep_type == 'pth':
                self.progress_bar.setMaximum(6)
            else:
                self.progress_bar.setMaximum(1)
        self.progress_bar.setValue(0)
        
        self.worker = DependencyInstallerWorker(self.dep_type, self.action)
        self.worker.progress_signal.connect(self._on_progress)
        self.worker.step_signal.connect(self._on_step)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()
    
    def _on_progress(self, message: str):
        self.log_text.append(message)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _on_step(self, current: int, total: int, step_name: str):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.step_label.setText(f"Step {current}/{total}: {step_name}")
    
    def _on_finished(self, success: bool, message: str):
        self.success = success
        self.log_text.append(message)
        
        action_text = "Installation" if self.action == 'install' else "Uninstallation"
        success_msg = "Complete!" if self.action == 'install' else "Complete!"
        success_detail = f"You can now use this model type." if self.action == 'install' else f"Model support has been removed."
        
        if success:
            self.step_label.setText(f"✓ {action_text} {success_msg}")
            self.step_label.setStyleSheet(f"font-weight: bold; color: {theme.get_color('success')};")
            self.progress_bar.setValue(self.progress_bar.maximum())
            self.log_text.append(f"\n{action_text} complete! {success_detail}")
            self.btn_cancel.setText("Close")
            self.btn_cancel.clicked.disconnect()
            self.btn_cancel.clicked.connect(self.accept)
            
            if self.parent() and hasattr(self.parent(), '_update_deps_status'):
                self.parent()._update_deps_status()
        else:
            self.step_label.setText(f"✗ {action_text} Failed")
            self.step_label.setStyleSheet(f"font-weight: bold; color: {theme.get_color('error')};")
            self.log_text.append(f"\n{action_text} failed. Please check the log above.")
            self.btn_action.setEnabled(True)
            self.btn_cancel.setText("Close")
    
    def _cancel(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(5000)
        self.reject()
    
    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(5000)
        event.accept()


class UpscalerModelManager:
    
    def __init__(self):
        self.models: List[Dict] = []
        self.models_dir = get_default_models_dir()
        self._load_config()
    
    def _load_config(self):
        try:
            if MODELS_CONFIG_FILE.exists():
                with open(MODELS_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.models = data.get('models', [])
                    models_dir = data.get('models_dir', '')
                    if models_dir:
                        self.models_dir = Path(models_dir)
        except Exception as e:
            print(f"Error loading model config: {e}")
            self.models = []
        
        self._sync_with_filesystem()
    
    def _sync_with_filesystem(self):
        if not self.models_dir.exists():
            return
        
        existing_names = {m['name'] for m in self.models}
        
        for param_file in self.models_dir.glob("*.param"):
            model_name = param_file.stem
            if model_name not in existing_names:
                bin_file = param_file.with_suffix(".bin")
                if bin_file.exists():
                    model_info = {
                        'name': model_name,
                        'type': 'ncnn',
                        'scale': self._detect_scale(model_name),
                        'description': f"Auto-detected NCNN model: {model_name}",
                        'param_file': str(param_file),
                        'bin_file': str(bin_file),
                        'custom': False
                    }
                    self.models.append(model_info)
        
        for pth_file in self.models_dir.glob("*.pth"):
            model_name = pth_file.stem
            if model_name not in existing_names:
                model_info = {
                    'name': model_name,
                    'type': 'pth',
                    'scale': self._detect_scale(model_name),
                    'description': f"Auto-detected PTH model: {model_name}",
                    'model_file': str(pth_file),
                    'custom': False
                }
                self.models.append(model_info)
        
        for onnx_file in self.models_dir.glob("*.onnx"):
            model_name = onnx_file.stem
            if model_name not in existing_names:
                model_info = {
                    'name': model_name,
                    'type': 'onnx',
                    'scale': self._detect_scale(model_name),
                    'description': f"Auto-detected ONNX model: {model_name}",
                    'model_file': str(onnx_file),
                    'custom': False
                }
                self.models.append(model_info)
        
        waifu2x_tool_dir = get_waifu2x_models_dir()
        if waifu2x_tool_dir.exists():
            waifu2x_model_map = {
                "models-cunet": ("waifu2x-cunet", "Waifu2x CUNet (best quality, anime)"),
                "models-upconv_7_anime_style_art_rgb": ("waifu2x-upconv-anime", "Waifu2x UpConv7 Anime"),
                "models-upconv_7_photo": ("waifu2x-upconv-photo", "Waifu2x UpConv7 Photo"),
            }
            for subdir_name, (model_name, description) in waifu2x_model_map.items():
                subdir = waifu2x_tool_dir / subdir_name
                if subdir.exists() and list(subdir.glob("*.param")):
                    if model_name not in existing_names:
                        model_info = {
                            'name': model_name,
                            'type': 'waifu2x',
                            'scale': 2,
                            'noise_level': 3,
                            'description': description,
                            'models_dir': str(subdir),
                            'custom': False
                        }
                        self.models.append(model_info)
        
        self._save_config()
    
    def _detect_scale(self, model_name: str) -> int:
        import re
        m = re.search(r'x([1-8])', model_name, re.IGNORECASE)
        if m:
            return int(m.group(1))
        return 4
    
    def _save_config(self):
        try:
            MODELS_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                'models_dir': str(self.models_dir),
                'models': self.models
            }
            tmp = MODELS_CONFIG_FILE.with_suffix('.tmp')
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            tmp.replace(MODELS_CONFIG_FILE)
        except Exception as e:
            print(f"Error saving model config: {e}")
    
    def get_all_models(self) -> List[Dict]:
        return self.models.copy()
    
    def get_model_by_name(self, name: str) -> Optional[Dict]:
        for m in self.models:
            if m['name'] == name:
                return m.copy()
        return None
    
    def get_ncnn_models(self) -> List[str]:
        return [m['name'] for m in self.models if m['type'] == 'ncnn']
    
    def get_pth_models(self) -> List[str]:
        return [m['name'] for m in self.models if m['type'] == 'pth']
    
    def get_onnx_models(self) -> List[str]:
        return [m['name'] for m in self.models if m['type'] == 'onnx']
    
    def get_waifu2x_models(self) -> List[str]:
        return [m['name'] for m in self.models if m['type'] == 'waifu2x']
    
    def add_model(self, model_info: Dict) -> bool:
        if any(m['name'] == model_info['name'] for m in self.models):
            return False
        self.models.append(model_info)
        self._save_config()
        return True
    
    def update_model(self, name: str, model_info: Dict) -> bool:
        for i, m in enumerate(self.models):
            if m['name'] == name:
                self.models[i] = model_info
                self._save_config()
                return True
        return False
    
    def delete_model(self, name: str, delete_files: bool = False) -> bool:
        for i, m in enumerate(self.models):
            if m['name'] == name:
                if delete_files:
                    try:
                        if m['type'] == 'ncnn':
                            param_file = Path(m.get('param_file', ''))
                            bin_file = Path(m.get('bin_file', ''))
                            if param_file.exists():
                                param_file.unlink()
                            if bin_file.exists():
                                bin_file.unlink()
                        else:
                            model_file = Path(m.get('model_file', ''))
                            if model_file.exists():
                                model_file.unlink()
                    except Exception as e:
                        print(f"Error deleting model files: {e}")
                
                self.models.pop(i)
                self._save_config()
                return True
        return False
    
    def import_model(self, file_paths: List[str], model_name: str, model_type: str, 
                     scale: int, description: str) -> bool:
        try:
            self.models_dir.mkdir(parents=True, exist_ok=True)
            
            if model_type == 'ncnn':
                param_file = None
                bin_file = None
                for fp in file_paths:
                    ext = Path(fp).suffix.lower()
                    if ext == '.param':
                        param_file = fp
                    elif ext == '.bin':
                        bin_file = fp
                
                if not param_file or not bin_file:
                    print("NCNN model requires both .param and .bin files")
                    return False
                
                dest_param = self.models_dir / f"{model_name}.param"
                dest_bin = self.models_dir / f"{model_name}.bin"
                shutil.copy2(param_file, dest_param)
                shutil.copy2(bin_file, dest_bin)
                
                model_info = {
                    'name': model_name,
                    'type': 'ncnn',
                    'scale': scale,
                    'description': description,
                    'param_file': str(dest_param),
                    'bin_file': str(dest_bin),
                    'custom': True
                }
            
            elif model_type == 'pth':
                if len(file_paths) != 1 or not file_paths[0].lower().endswith('.pth'):
                    print("PTH model requires exactly one .pth file")
                    return False
                
                dest_file = self.models_dir / f"{model_name}.pth"
                shutil.copy2(file_paths[0], dest_file)
                
                model_info = {
                    'name': model_name,
                    'type': 'pth',
                    'scale': scale,
                    'description': description,
                    'model_file': str(dest_file),
                    'custom': True
                }
            
            elif model_type == 'onnx':
                if len(file_paths) != 1 or not file_paths[0].lower().endswith('.onnx'):
                    print("ONNX model requires exactly one .onnx file")
                    return False
                
                dest_file = self.models_dir / f"{model_name}.onnx"
                shutil.copy2(file_paths[0], dest_file)
                
                model_info = {
                    'name': model_name,
                    'type': 'onnx',
                    'scale': scale,
                    'description': description,
                    'model_file': str(dest_file),
                    'custom': True
                }
            
            else:
                print(f"Unsupported model type: {model_type}")
                return False
            
            return self.add_model(model_info)
            
        except Exception as e:
            print(f"Error importing model: {e}")
            return False
    
    def export_model(self, name: str, dest_dir: str) -> bool:
        try:
            model = self.get_model_by_name(name)
            if not model:
                return False
            
            dest_path = Path(dest_dir)
            dest_path.mkdir(parents=True, exist_ok=True)
            
            if model['type'] == 'ncnn':
                param_file = Path(model.get('param_file', ''))
                bin_file = Path(model.get('bin_file', ''))
                if param_file.exists():
                    shutil.copy2(param_file, dest_path / param_file.name)
                if bin_file.exists():
                    shutil.copy2(bin_file, dest_path / bin_file.name)
            else:
                model_file = Path(model.get('model_file', ''))
                if model_file.exists():
                    shutil.copy2(model_file, dest_path / model_file.name)
            
            meta_file = dest_path / f"{name}_meta.json"
            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(model, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error exporting model: {e}")
            return False
    
    def refresh_models(self):
        self.models = []
        self._sync_with_filesystem()


class AddModelDialog(QDialog):
    
    def __init__(self, parent=None, edit_model: Dict = None):
        super().__init__(parent)
        self.edit_model = edit_model
        self.selected_files: List[str] = []
        
        if edit_model:
            self.setWindowTitle("Edit Model")
        else:
            self.setWindowTitle("Add Model")
        
        self.setMinimumWidth(500)
        self.setup_ui()
        
        if edit_model:
            self._load_model_data()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        form_group = QGroupBox("Model Information")
        form_layout = QFormLayout()
        form_layout.setSpacing(8)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter model name (e.g., my-custom-model-x4)")
        form_layout.addRow("Name:", self.name_edit)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["ncnn", "pth", "onnx"])
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        form_layout.addRow("Type:", self.type_combo)
        
        self.scale_spin = QSpinBox()
        self.scale_spin.setRange(1, 8)
        self.scale_spin.setValue(4)
        form_layout.addRow("Scale:", self.scale_spin)
        
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Enter model description")
        form_layout.addRow("Description:", self.desc_edit)
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        files_group = QGroupBox("Model Files")
        files_layout = QVBoxLayout()
        files_layout.setSpacing(8)
        
        self.files_label = QLabel("No files selected")
        self.files_label.setWordWrap(True)
        files_layout.addWidget(self.files_label)
        
        btn_layout = QHBoxLayout()
        self.btn_select_files = QPushButton(qta.icon('fa6s.folder-open'), " Select Files")
        self.btn_select_files.clicked.connect(self._select_files)
        btn_layout.addWidget(self.btn_select_files)
        btn_layout.addStretch()
        files_layout.addLayout(btn_layout)
        
        files_group.setLayout(files_layout)
        layout.addWidget(files_group)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_cancel)
        
        self.btn_save = QPushButton(qta.icon('fa6s.floppy-disk'), " Save")
        self.btn_save.clicked.connect(self._save)
        button_layout.addWidget(self.btn_save)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def _on_type_changed(self, model_type: str):
        if model_type == 'ncnn':
            self.files_label.setText("NCNN requires .param and .bin files")
        elif model_type == 'pth':
            self.files_label.setText("PTH requires a single .pth file")
        elif model_type == 'onnx':
            self.files_label.setText("ONNX requires a single .onnx file")
        self.selected_files = []
    
    def _select_files(self):
        model_type = self.type_combo.currentText()
        
        if model_type == 'ncnn':
            files, _ = QFileDialog.getOpenFileNames(
                self, "Select NCNN Model Files", "",
                "NCNN Files (*.param *.bin);;All Files (*)"
            )
        elif model_type == 'pth':
            files, _ = QFileDialog.getOpenFileNames(
                self, "Select PTH Model File", "",
                "PTH Files (*.pth);;All Files (*)"
            )
        elif model_type == 'onnx':
            files, _ = QFileDialog.getOpenFileNames(
                self, "Select ONNX Model File", "",
                "ONNX Files (*.onnx);;All Files (*)"
            )
        else:
            files = []
        
        if files:
            self.selected_files = files
            file_names = [Path(f).name for f in files]
            self.files_label.setText("Selected: " + ", ".join(file_names))
    
    def _load_model_data(self):
        if not self.edit_model:
            return
        
        self.name_edit.setText(self.edit_model.get('name', ''))
        self.name_edit.setEnabled(False)
        
        model_type = self.edit_model.get('type', 'ncnn')
        idx = self.type_combo.findText(model_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.type_combo.setEnabled(False)
        
        self.scale_spin.setValue(self.edit_model.get('scale', 4))
        self.desc_edit.setText(self.edit_model.get('description', ''))
        
        self.btn_select_files.setEnabled(False)
        if model_type == 'ncnn':
            param_file = self.edit_model.get('param_file', '')
            bin_file = self.edit_model.get('bin_file', '')
            self.files_label.setText(f"Files: {Path(param_file).name}, {Path(bin_file).name}")
        else:
            model_file = self.edit_model.get('model_file', '')
            self.files_label.setText(f"File: {Path(model_file).name}")
    
    def _save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Model name is required.")
            return
        
        if not self.edit_model and not self.selected_files:
            QMessageBox.warning(self, "Validation Error", "Please select model files.")
            return
        
        self.accept()
    
    def get_model_data(self) -> Dict:
        return {
            'name': self.name_edit.text().strip(),
            'type': self.type_combo.currentText(),
            'scale': self.scale_spin.value(),
            'description': self.desc_edit.text().strip(),
            'files': self.selected_files
        }


class UpscalerModelManagerDialog(QDialog):
    models_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Upscaler Model Manager")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setMinimumSize(800, 500)
        
        self.model_manager = UpscalerModelManager()
        
        icon_path = os.path.join(BASE_PATH, 'res', 'image_tea.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.setup_ui()
        self._refresh_table()
    
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)
        
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)
        
        self.btn_add = QPushButton(qta.icon('fa6s.plus'), " Add Model")
        self.btn_add.setToolTip("Add a new model")
        self.btn_add.clicked.connect(self._add_model)
        toolbar_layout.addWidget(self.btn_add)
        
        self.btn_import = QPushButton(qta.icon('fa6s.file-import'), " Import")
        self.btn_import.setToolTip("Import model from files")
        self.btn_import.clicked.connect(self._import_model)
        toolbar_layout.addWidget(self.btn_import)
        
        self.btn_export = QPushButton(qta.icon('fa6s.file-export'), " Export")
        self.btn_export.setToolTip("Export selected model")
        self.btn_export.clicked.connect(self._export_model)
        toolbar_layout.addWidget(self.btn_export)
        
        self.btn_edit = QPushButton(qta.icon('fa6s.pen-to-square'), " Edit")
        self.btn_edit.setToolTip("Edit selected model")
        self.btn_edit.clicked.connect(self._edit_model)
        toolbar_layout.addWidget(self.btn_edit)
        
        self.btn_delete = QPushButton(qta.icon('fa6s.trash'), " Delete")
        self.btn_delete.setToolTip("Delete selected model")
        self.btn_delete.clicked.connect(self._delete_model)
        toolbar_layout.addWidget(self.btn_delete)
        
        toolbar_layout.addStretch()
        
        self.btn_refresh = QPushButton(qta.icon('fa6s.arrows-rotate'), " Refresh")
        self.btn_refresh.setToolTip("Refresh model list from filesystem")
        self.btn_refresh.clicked.connect(self._refresh_models)
        toolbar_layout.addWidget(self.btn_refresh)
        
        self.btn_open_folder = QPushButton(qta.icon('fa6s.folder-open'), " Open Folder")
        self.btn_open_folder.setToolTip("Open models folder")
        self.btn_open_folder.clicked.connect(self._open_models_folder)
        toolbar_layout.addWidget(self.btn_open_folder)
        
        main_layout.addLayout(toolbar_layout)
        
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)
        
        filter_layout.addWidget(QLabel("Filter:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All Types", "NCNN (.param/.bin)", "PTH (.pth)", "ONNX (.onnx)"])
        self.filter_combo.currentTextChanged.connect(self._refresh_table)
        filter_layout.addWidget(self.filter_combo)
        
        filter_layout.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search models...")
        self.search_edit.textChanged.connect(self._refresh_table)
        filter_layout.addWidget(self.search_edit, 1)
        
        main_layout.addLayout(filter_layout)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Scale", "Description", "Custom"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._edit_model)
        main_layout.addWidget(self.table, 1)
        
        info_layout = QHBoxLayout()
        info_layout.setSpacing(16)
        
        self.total_label = QLabel("Total Models: 0")
        self.total_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.total_label)
        
        self.ncnn_label = QLabel("NCNN: 0")
        info_layout.addWidget(self.ncnn_label)
        
        self.pth_label = QLabel("PTH: 0")
        info_layout.addWidget(self.pth_label)
        
        self.onnx_label = QLabel("ONNX: 0")
        info_layout.addWidget(self.onnx_label)
        
        info_layout.addStretch()
        
        self.models_dir_label = QLabel(f"Models Dir: {self.model_manager.models_dir}")
        self.models_dir_label.setStyleSheet(f"color: {theme.get_color('text_dark')};")
        info_layout.addWidget(self.models_dir_label)
        
        main_layout.addLayout(info_layout)
        
        deps_group = QGroupBox("Optional Dependencies")
        deps_layout = QHBoxLayout()
        deps_layout.setSpacing(16)
        
        self.pth_status_label = QLabel()
        deps_layout.addWidget(self.pth_status_label)
        
        self.btn_install_pth = QPushButton(qta.icon('fa6s.download'), " Install PTH Support")
        self.btn_install_pth.setToolTip("Install PyTorch and RealESRGAN packages for PTH models")
        self.btn_install_pth.clicked.connect(lambda: self._install_deps('pth'))
        deps_layout.addWidget(self.btn_install_pth)
        
        deps_layout.addSpacing(20)
        
        self.onnx_status_label = QLabel()
        deps_layout.addWidget(self.onnx_status_label)
        
        self.btn_install_onnx = QPushButton(qta.icon('fa6s.download'), " Install ONNX Support")
        self.btn_install_onnx.setToolTip("Install ONNX Runtime for ONNX models")
        self.btn_install_onnx.clicked.connect(lambda: self._install_deps('onnx'))
        deps_layout.addWidget(self.btn_install_onnx)
        
        deps_layout.addStretch()
        
        deps_group.setLayout(deps_layout)
        main_layout.addWidget(deps_group)
        
        self._update_deps_status()
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)
        button_layout.addWidget(self.btn_close)
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
    
    def _refresh_table(self):
        models = self.model_manager.get_all_models()
        
        filter_type = self.filter_combo.currentText()
        if "NCNN" in filter_type:
            models = [m for m in models if m['type'] == 'ncnn']
        elif "PTH" in filter_type:
            models = [m for m in models if m['type'] == 'pth']
        elif "ONNX" in filter_type:
            models = [m for m in models if m['type'] == 'onnx']
        
        search_text = self.search_edit.text().strip().lower()
        if search_text:
            models = [m for m in models if search_text in m['name'].lower() or 
                     search_text in m.get('description', '').lower()]
        
        self.table.setRowCount(len(models))
        for row, model in enumerate(models):
            self.table.setItem(row, 0, QTableWidgetItem(model['name']))
            self.table.setItem(row, 1, QTableWidgetItem(model['type'].upper()))
            self.table.setItem(row, 2, QTableWidgetItem(f"{model['scale']}x"))
            self.table.setItem(row, 3, QTableWidgetItem(model.get('description', '')))
            custom_text = "Yes" if model.get('custom', False) else "No"
            self.table.setItem(row, 4, QTableWidgetItem(custom_text))
        
        all_models = self.model_manager.get_all_models()
        ncnn_count = len([m for m in all_models if m['type'] == 'ncnn'])
        pth_count = len([m for m in all_models if m['type'] == 'pth'])
        onnx_count = len([m for m in all_models if m['type'] == 'onnx'])
        
        self.total_label.setText(f"Total Models: {len(all_models)}")
        self.ncnn_label.setText(f"NCNN: {ncnn_count}")
        self.pth_label.setText(f"PTH: {pth_count}")
        self.onnx_label.setText(f"ONNX: {onnx_count}")
    
    def _get_selected_model_name(self) -> Optional[str]:
        selected = self.table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        return self.table.item(row, 0).text()
    
    def _add_model(self):
        dialog = AddModelDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_model_data()
            success = self.model_manager.import_model(
                data['files'], data['name'], data['type'],
                data['scale'], data['description']
            )
            if success:
                self._refresh_table()
                self.models_changed.emit()
            else:
                QMessageBox.warning(self, "Error", "Failed to add model. Check console for details.")
    
    def _import_model(self):
        dialog = AddModelDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_model_data()
            success = self.model_manager.import_model(
                data['files'], data['name'], data['type'],
                data['scale'], data['description']
            )
            if success:
                self._refresh_table()
                self.models_changed.emit()
                QMessageBox.information(self, "Success", f"Model '{data['name']}' imported successfully!")
            else:
                QMessageBox.warning(self, "Error", "Failed to import model. Check console for details.")
    
    def _export_model(self):
        model_name = self._get_selected_model_name()
        if not model_name:
            QMessageBox.warning(self, "No Selection", "Please select a model to export.")
            return
        
        dest_dir = QFileDialog.getExistingDirectory(self, "Select Export Destination")
        if not dest_dir:
            return
        
        success = self.model_manager.export_model(model_name, dest_dir)
        if success:
            QMessageBox.information(self, "Success", f"Model '{model_name}' exported to {dest_dir}")
        else:
            QMessageBox.warning(self, "Error", "Failed to export model.")
    
    def _edit_model(self):
        model_name = self._get_selected_model_name()
        if not model_name:
            QMessageBox.warning(self, "No Selection", "Please select a model to edit.")
            return
        
        model = self.model_manager.get_model_by_name(model_name)
        if not model:
            return
        
        dialog = AddModelDialog(self, edit_model=model)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_model_data()
            model['scale'] = data['scale']
            model['description'] = data['description']
            self.model_manager.update_model(model_name, model)
            self._refresh_table()
            self.models_changed.emit()
    
    def _delete_model(self):
        model_name = self._get_selected_model_name()
        if not model_name:
            QMessageBox.warning(self, "No Selection", "Please select a model to delete.")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete model '{model_name}'?\n\nDo you also want to delete the model files?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
        )
        
        if reply == QMessageBox.Cancel:
            return
        
        delete_files = (reply == QMessageBox.Yes)
        success = self.model_manager.delete_model(model_name, delete_files)
        if success:
            self._refresh_table()
            self.models_changed.emit()
        else:
            QMessageBox.warning(self, "Error", "Failed to delete model.")
    
    def _refresh_models(self):
        self.model_manager.refresh_models()
        self._refresh_table()
        self.models_changed.emit()
    
    def _open_models_folder(self):
        models_dir = self.model_manager.models_dir
        if not models_dir.exists():
            models_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            if os.name == 'nt':
                os.startfile(str(models_dir))
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', str(models_dir)])
            else:
                subprocess.Popen(['xdg-open', str(models_dir)])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open folder: {e}")
    
    def _update_deps_status(self):
        """Update dependency status labels and buttons."""
        deps = get_deps_status()
        
        if deps['pth']:
            self.pth_status_label.setText("✓ PTH Ready")
            self.pth_status_label.setStyleSheet(f"color: {theme.get_color('success')}; font-weight: bold;")
            self.btn_install_pth.setEnabled(True)
            self.btn_install_pth.setIcon(qta.icon('fa6s.trash'))
            self.btn_install_pth.setText(" Uninstall PTH")
            self.btn_install_pth.setToolTip("Uninstall PyTorch and RealESRGAN packages")
            self.btn_install_pth.setStyleSheet("")
        else:
            self.pth_status_label.setText("✗ PTH Not Installed")
            self.pth_status_label.setStyleSheet(f"color: {theme.get_color('gray')};")
            self.btn_install_pth.setEnabled(True)
            self.btn_install_pth.setIcon(qta.icon('fa6s.download'))
            self.btn_install_pth.setText(" Install PTH Support")
            self.btn_install_pth.setToolTip("Install PyTorch and RealESRGAN packages for PTH models")
            self.btn_install_pth.setStyleSheet("")
        
        if deps['onnx']:
            self.onnx_status_label.setText("✓ ONNX Ready")
            self.onnx_status_label.setStyleSheet(f"color: {theme.get_color('success')}; font-weight: bold;")
            self.btn_install_onnx.setEnabled(True)
            self.btn_install_onnx.setIcon(qta.icon('fa6s.trash'))
            self.btn_install_onnx.setText(" Uninstall ONNX")
            self.btn_install_onnx.setToolTip("Uninstall ONNX Runtime")
            self.btn_install_onnx.setStyleSheet("")
        else:
            self.onnx_status_label.setText("✗ ONNX Not Installed")
            self.onnx_status_label.setStyleSheet(f"color: {theme.get_color('gray')};")
            self.btn_install_onnx.setEnabled(True)
            self.btn_install_onnx.setIcon(qta.icon('fa6s.download'))
            self.btn_install_onnx.setText(" Install ONNX Support")
            self.btn_install_onnx.setToolTip("Install ONNX Runtime for ONNX models")
            self.btn_install_onnx.setStyleSheet("")
    
    def _install_deps(self, dep_type: str):
        """Open dependency installer/uninstaller dialog."""
        deps = get_deps_status()
        
        if dep_type == 'pth':
            is_installed = deps['pth']
        else:
            is_installed = deps['onnx']
        
        action = 'uninstall' if is_installed else 'install'
        
        if action == 'uninstall':
            type_name = "PTH" if dep_type == 'pth' else "ONNX"
            reply = QMessageBox.question(
                self, f"Confirm Uninstall",
                f"Are you sure you want to uninstall {type_name} dependencies?\n\n"
                f"This will remove all {type_name} model support.",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        
        dialog = DependencyInstallerDialog(self, dep_type, action)
        dialog.exec()
        self._update_deps_status()
    
    def get_model_manager(self) -> UpscalerModelManager:
        return self.model_manager
