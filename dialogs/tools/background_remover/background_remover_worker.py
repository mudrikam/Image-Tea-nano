import os
import time
from pathlib import Path
from PIL import Image
from PySide6.QtCore import QThread, Signal
from dialogs.tools.background_remover import models_manager

from helpers.tools.background_remover_helper import (
    enhance_transparency_with_levels, crop_transparent_image,
    add_solid_background, convert_to_jpg, recommend_alpha_matting_params
)

SUPPORTED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tif', '.avif', '.heic', '.heif'}


def get_onnx_providers():
    """Return available ONNX Runtime providers in GPU-first order."""
    try:
        import onnxruntime as ort
        available = set(ort.get_available_providers())
    except Exception as exc:
        print(f"ONNX Runtime provider detection failed: {exc}")
        return []

    preferred = ('CUDAExecutionProvider', 'DmlExecutionProvider',
                 'ROCMExecutionProvider', 'CPUExecutionProvider')
    providers = [provider for provider in preferred if provider in available]
    if providers and providers[-1] != 'CPUExecutionProvider' and 'CPUExecutionProvider' in available:
        providers.append('CPUExecutionProvider')
    print(f"ONNX Runtime providers available: {providers or sorted(available)}")
    return providers


def create_rembg_session(rembg, model_name, model_path=None):
    """Create a rembg session with GPU preference and safe model fallbacks."""
    providers = get_onnx_providers()
    provider_sets = []
    if providers:
        provider_sets.append(providers)
    if 'CPUExecutionProvider' in providers:
        provider_sets.append(['CPUExecutionProvider'])
    if not provider_sets:
        provider_sets.append([])
    attempts = []
    if model_name:
        attempts.append(('model name', model_name))
    if model_path and os.path.exists(model_path):
        attempts.append(('model file', model_path))
    for family in ('isnet-general-use', 'u2net', 'u2netp', 'u2net_human_seg', 'u2net_cloth_seg'):
        if family != model_name:
            attempts.append(('fallback model', family))

    errors = []
    for provider_set in provider_sets:
        provider_kwargs = {'providers': provider_set} if provider_set else {}
        for description, candidate in attempts:
            try:
                session = rembg.new_session(candidate, **provider_kwargs)
                print(f"rembg session created using {description}: {candidate}; providers={provider_set or 'default'}")
                return session
            except Exception as exc:
                errors.append(f"{description}={candidate}, providers={provider_set or 'default'}: {exc}")

    try:
        session = rembg.new_session()
        print("rembg session created using default model and runtime defaults")
        return session
    except Exception as exc:
        errors.append(f"default model: {exc}")
        raise RuntimeError("Unable to create rembg session. " + " | ".join(errors[-3:])) from exc


class BackgroundRemoverWorker(QThread):
    progress_updated = Signal(int, int)
    status_updated = Signal(str, str)
    completed = Signal(int, int)
    stopped = Signal(int, int)
    error_occurred = Signal(str)
    step_progress = Signal(int, str)

    def __init__(self, file_paths, output_dir, options):
        super().__init__()
        self.file_paths = file_paths
        self.output_dir = output_dir
        self.options = options
        self.should_stop = False
        self.temp_files = []

    def stop(self):
        self.should_stop = True

    def run(self):
        total = len(self.file_paths)
        processed = 0
        success_count = 0

        for idx, file_path in enumerate(self.file_paths):
            if self.should_stop:
                break

            filename = os.path.basename(file_path)
            self.status_updated.emit(filename, "Processing")
            self.progress_updated.emit(idx, total)

            try:
                ok = self._process_image(file_path)
                if ok:
                    success_count += 1
                    self.status_updated.emit(filename, "Completed")
                else:
                    self.status_updated.emit(filename, "Failed")
                processed += 1
            except Exception as e:
                self.status_updated.emit(filename, f"Error: {str(e)[:80]}")
                processed += 1
            finally:
                self._cleanup_temp()

            self.progress_updated.emit(processed, total)

        if self.should_stop:
            self.stopped.emit(success_count, processed)
        else:
            self.completed.emit(success_count, processed)

    def _process_image(self, file_path):
        self.step_progress.emit(0, "Converting to PNG...")
        ext = Path(file_path).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return False

        output_dir = self.output_dir or os.path.join(os.path.dirname(file_path), 'PNG')
        os.makedirs(output_dir, exist_ok=True)

        base_name = Path(file_path).stem
        timestamp = int(time.time() * 1000) % 100000

        png_path = self._ensure_png(file_path)
        if not png_path:
            return False

        self.step_progress.emit(5, "Preparing model...")
        model_name = self.options.get('model_name') or models_manager.DEFAULT_MODEL

        try:
            with Image.open(png_path) as img:
                input_img = img.copy()
        except Exception:
            return False

        try:
            models_manager.set_model_path()
            if not models_manager.prepare_model(model_name):
                self.error_occurred.emit(f"Unable to prepare rembg model: {model_name}")
                return False
            model_path = models_manager.get_model_path(model_name)
            import rembg
            session = create_rembg_session(rembg, model_name, model_path)
        except ImportError:
            self.error_occurred.emit("rembg or ONNX Runtime is not installed. Install via Tools Manager.")
            return False
        except Exception as exc:
            self.error_occurred.emit(f"Unable to initialize rembg: {str(exc)[:160]}")
            return False

        self.step_progress.emit(10, "Removing background...")
        alpha_params = recommend_alpha_matting_params(input_img)

        output_img = None
        for attempt in range(5):
            try:
                params = [
                    alpha_params,
                    {**alpha_params, "alpha_matting_shift": 0.02},
                    {**alpha_params, "alpha_matting_shift": 0.05},
                    {**alpha_params, "alpha_matting_discard_threshold": 1e-5},
                    {**alpha_params, "alpha_matting_discard_threshold": 1e-6, "alpha_matting_shift": 0.1}
                ][attempt]
                output_img = rembg.remove(
                    input_img, alpha_matting=True,
                    alpha_matting_foreground_threshold=params["alpha_matting_foreground_threshold"],
                    alpha_matting_background_threshold=params["alpha_matting_background_threshold"],
                    alpha_matting_erode_size=params["alpha_matting_erode_size"],
                    alpha_matting_discard_threshold=params["alpha_matting_discard_threshold"],
                    alpha_matting_shift=params["alpha_matting_shift"],
                    session=session
                )
                break
            except Exception:
                continue

        if output_img is None:
            output_img = rembg.remove(input_img, session=session)

        if output_img.size[0] > input_img.size[0] * 2 or output_img.size[1] > input_img.size[1] * 2:
            output_img = output_img.resize(input_img.size, Image.LANCZOS)

        self.step_progress.emit(30, "Alpha matting...")
        # Save initial output and mask
        temp_output = os.path.join(output_dir, f"{base_name}_temp_{timestamp}.png")
        mask_path = os.path.join(output_dir, f"{base_name}_mask_{timestamp}.png")
        output_img.save(temp_output)
        self.temp_files.append(temp_output)

        output_mask = rembg.remove(input_img, only_mask=True, session=session)
        output_mask.save(mask_path)
        self.temp_files.append(mask_path)

        self.step_progress.emit(50, "Enhancing transparency...")
        # Levels enhancement
        final_output = os.path.join(output_dir, f"{base_name}.png")
        black = self.options.get('black_point', 20)
        mid = self.options.get('mid_point', 128)
        white = self.options.get('white_point', 235)
        save_mask = self.options.get('save_mask', False)

        enhanced_path, adj_mask_path = enhance_transparency_with_levels(
            temp_output, mask_path, final_output,
            black_point=black, mid_point=mid, white_point=white,
            save_adjusted_mask=save_mask
        )

        if not enhanced_path:
            return False

        current_path = enhanced_path

        self.step_progress.emit(65, "Adjusting levels...")

        # Auto crop
        if self.options.get('auto_crop', True) and adj_mask_path and os.path.exists(adj_mask_path):
            self.step_progress.emit(75, "Auto cropping...")
            margin = self.options.get('margin', 10)
            cropped = crop_transparent_image(current_path, adj_mask_path, margin=margin)
            if cropped != current_path:
                current_path = cropped

        # Cleanup adjusted mask if user doesn't want to save it (must happen after auto crop)
        if not save_mask and adj_mask_path and os.path.exists(adj_mask_path):
            try:
                os.remove(adj_mask_path)
            except Exception:
                pass

        # Solid background
        if self.options.get('solid_bg', False):
            self.step_progress.emit(85, "Solid background...")
            bg_color = self.options.get('solid_bg_color', '#FFFFFF')
            solid_path = os.path.join(output_dir, f"{base_name}_solid_{timestamp}.jpg")
            sb_result = add_solid_background(current_path, solid_path, bg_color=bg_color)
            if sb_result:
                current_path = sb_result

        # JPG export
        if self.options.get('jpg_export', False):
            self.step_progress.emit(90, "JPG export...")
            quality = self.options.get('jpg_quality', 90)
            jpg_path = os.path.join(output_dir, f"{base_name}.jpg")
            convert_to_jpg(current_path, jpg_path, quality=quality)

        self.step_progress.emit(95, "Saving...")
        self.step_progress.emit(100, "Done")
        return True

    def _ensure_png(self, file_path):
        ext = Path(file_path).suffix.lower()
        if ext == '.png':
            return file_path

        try:
            img = Image.open(file_path)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            temp_png = file_path + '_temp_processing.png'
            img.save(temp_png, 'PNG')
            self.temp_files.append(temp_png)
            return temp_png
        except Exception:
            return None

    def _cleanup_temp(self):
        for f in self.temp_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass
        self.temp_files = []
