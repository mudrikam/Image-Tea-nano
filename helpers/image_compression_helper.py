import os
import sys
import json
import subprocess
import platform
from PIL import Image
import config
import ctypes
import ctypes.util
import importlib
import shutil

BASE_PATH = config.BASE_PATH


class MissingToolError(Exception):
    """Raised when a required tool (cairo, ghostscript) is not installed."""
    def __init__(self, tool_name, message=None):
        self.tool_name = tool_name
        if message is None:
            message = f"Required tool '{tool_name}' is not installed. Install it via Tools > Tools Manager."
        super().__init__(message)


def check_image_tools_available(file_paths, parent=None) -> bool:
    """
    Check if required image processing tools are available for the given file paths.
    If any tools are missing, opens Tools Manager and returns False.
    
    Call this from UI layer BEFORE processing images that need Cairo or Ghostscript.
    
    Args:
        file_paths: Single path (str) or list of file paths to check
        parent: Parent widget for the Tools Manager dialog
        
    Returns:
        True if all required tools are available, False if any are missing.
    """
    if isinstance(file_paths, str):
        file_paths = [file_paths]
    
    required_tools = set()
    for path in file_paths:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".svg":
            required_tools.add("cairo")
        elif ext in (".eps", ".pdf", ".ai"):
            required_tools.add("ghostscript")
    
    if not required_tools:
        return True
    
    from helpers.tools_dependency_helper import check_tools_available
    return check_tools_available(list(required_tools), parent=parent)


def is_ghostscript_available() -> bool:
    """Check if Ghostscript is installed and accessible."""
    # Quick check: if we already found the path at module load
    if GHOSTSCRIPT_PATH is not None:
        return True
    # Recheck via tools_checker
    from tools.tools_checker import get_tool_status
    status = get_tool_status("ghostscript")
    if status['installed']:
        return True
    # Also check if gs is in PATH (non-Windows)
    if platform.system() != "Windows":
        return shutil.which("gs") is not None
    return False


def is_cairo_available() -> bool:
    """Check if Cairo is installed and accessible."""
    from tools.tools_checker import get_tool_status
    status = get_tool_status("cairo")
    return status['installed']

_NO_WINDOW = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}

CAIRO_DLL_DIR = os.path.join(BASE_PATH, "tools", "cairo", "cairo-windows-1.17.2", "lib", "x64")
_CAIRO_AVAILABLE = True  # Will be set to False if Cairo not found at module load

if os.name == "nt":
    if not os.path.exists(CAIRO_DLL_DIR):
        # Search for Cairo DLLs in the tools/cairo folder (may have been extracted differently)
        tools_folder = os.path.join(BASE_PATH, "tools", "cairo")
        found_dir = None
        if os.path.isdir(tools_folder):
            for root, dirs, files in os.walk(tools_folder):
                for f in files:
                    name = f.lower()
                    if name.endswith('.dll') and ('cairo' in name or 'libcairo' in name):
                        found_dir = root
                        break
                if found_dir:
                    break
        if found_dir:
            CAIRO_DLL_DIR = found_dir
        else:
            _CAIRO_AVAILABLE = False

    if os.path.isdir(CAIRO_DLL_DIR):
        if CAIRO_DLL_DIR not in os.environ.get("PATH", ""):
            os.environ["PATH"] = CAIRO_DLL_DIR + ";" + os.environ.get("PATH", "")
        try:
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(CAIRO_DLL_DIR)
        except Exception as e:
            print(f"Error setting Cairo DLL directory: {e}")

PILLOW_FORMATS = set()
for ext, fmt in Image.registered_extensions().items():
    PILLOW_FORMATS.add(ext.lower())

def get_ghostscript_path():
    system = platform.system()
    if system == "Windows":
        path = os.path.join(BASE_PATH, "tools", "ghostscript", "gswin64c.exe")
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path
        # Not found — will be caught by is_ghostscript_available() check
        return None

    gs = shutil.which("gs")
    if gs:
        return gs

    candidates = [
        "/opt/homebrew/bin/gs",
        "/usr/local/bin/gs",
        "/opt/local/bin/gs",
        "/usr/bin/gs",
    ]
    for p in candidates:
        if os.path.exists(p) and os.access(p, os.X_OK):
            return p

    bundled_path = os.path.join(BASE_PATH, "tools", "ghostscript", "gs")
    if os.path.exists(bundled_path) and os.access(bundled_path, os.X_OK):
        return bundled_path

    # Not found — will be caught by is_ghostscript_available() check
    return None

GHOSTSCRIPT_PATH = get_ghostscript_path()


def _create_cairo_shim(lib_path):
    try:
        shim_dir = os.path.join(BASE_PATH, "temp", "cairo_shims")
        os.makedirs(shim_dir, exist_ok=True)
        base_name = os.path.basename(lib_path)
        sonames = [
            base_name,
            "libcairo.2.dylib",
            "libcairo.dylib",
            "libcairo.so.2",
            "cairo-2.dylib",
            "cairo.dylib",
        ]
        created = []
        for name in sonames:
            dest = os.path.join(shim_dir, name)
            try:
                if os.path.exists(dest):
                    created.append(dest)
                    continue
                try:
                    os.symlink(lib_path, dest)
                except Exception:
                    shutil.copy2(lib_path, dest)
                created.append(dest)
            except Exception as e:
                print(f"Warning: failed to create shim {dest}: {e}")

        prev_fb = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
        if shim_dir not in prev_fb.split(":"):
            os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = shim_dir + (":" + prev_fb if prev_fb else "")
            print(f"Added shim dir to DYLD_FALLBACK_LIBRARY_PATH: {shim_dir}")
        prev = os.environ.get("DYLD_LIBRARY_PATH", "")
        if shim_dir not in prev.split(":"):
            os.environ["DYLD_LIBRARY_PATH"] = shim_dir + (":" + prev if prev else "")
            print(f"Added shim dir to DYLD_LIBRARY_PATH: {shim_dir}")

        rtld_flags = (getattr(ctypes, 'RTLD_GLOBAL', 0x100) | getattr(ctypes, 'RTLD_NOW', 0x2))
        for path in created:
            try:
                ctypes.CDLL(path, mode=rtld_flags)
                print(f"Loaded cairo shim {path} (RTLD_GLOBAL|RTLD_NOW)")
            except Exception as e:
                print(f"Warning: failed to dlopen shim {path}: {e}")

        if created:
            print(f"Cairo shims created: {created}")
            return True
        else:
            print("No cairo shims could be created")
            return False
    except Exception as e:
        print(f"Failed to create cairo shims: {e}")
        return False


def _ensure_cairo_loaded():
    if sys.platform != "darwin":
        return True

    try:
        libname = ctypes.util.find_library('cairo') or ctypes.util.find_library('cairo-2')
        if libname:
            try:
                rtld_flags = (getattr(ctypes, 'RTLD_GLOBAL', 0x100) | getattr(ctypes, 'RTLD_NOW', 0x2))
                ctypes.CDLL(libname, mode=rtld_flags)
                print(f"Loaded cairo library: {libname} (RTLD_GLOBAL|RTLD_NOW)")
                if os.path.isabs(libname) and os.path.exists(libname):
                    _create_cairo_shim(libname)
                return True
            except Exception as e:
                print(f"Found cairo name '{libname}' but failed to load it as RTLD_GLOBAL: {e}")
    except Exception as e:
        print(f"ctypes.util.find_library check failed: {e}")

    candidates = [
        "/opt/homebrew/lib/libcairo.dylib",
        "/usr/local/lib/libcairo.dylib",
        "/opt/local/lib/libcairo.dylib",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                rtld_flags = (getattr(ctypes, 'RTLD_GLOBAL', 0x100) | getattr(ctypes, 'RTLD_NOW', 0x2))
                ctypes.CDLL(p, mode=rtld_flags)
                print(f"Loaded cairo library from {p} (RTLD_GLOBAL|RTLD_NOW)")
                _create_cairo_shim(p)
                return True
            except Exception as e:
                print(f"Failed to load cairo from {p} as RTLD_GLOBAL: {e}")

    try:
        res = subprocess.run(["pkg-config", "--variable=libdir", "cairo"], capture_output=True, text=True, check=False, **_NO_WINDOW)
        libdir = res.stdout.strip()
        if libdir:
            candidate = os.path.join(libdir, "libcairo.dylib")
            if os.path.exists(candidate):
                try:
                    rtld_flags = (getattr(ctypes, 'RTLD_GLOBAL', 0x100) | getattr(ctypes, 'RTLD_NOW', 0x2))
                    ctypes.CDLL(candidate, mode=rtld_flags)
                    print(f"Loaded cairo via pkg-config from {candidate} (RTLD_GLOBAL|RTLD_NOW)")
                    _create_cairo_shim(candidate)
                    return True
                except Exception as e:
                    print(f"Failed to load cairo via pkg-config from {candidate}: {e}")
    except Exception as e:
        print(f"pkg-config check failed: {e}")

    for prefix in ["/opt/homebrew/lib", "/usr/local/lib", "/opt/local/lib"]:
        if os.path.isdir(prefix):
            prev_fb = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
            if prefix not in prev_fb.split(":"):
                os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = prefix + (":" + prev_fb if prev_fb else "")
                print(f"Prepended {prefix} to DYLD_FALLBACK_LIBRARY_PATH to help find cairo")
            prev = os.environ.get("DYLD_LIBRARY_PATH", "")
            if prefix not in prev.split(":"):
                os.environ["DYLD_LIBRARY_PATH"] = prefix + (":" + prev if prev else "")
                print(f"Prepended {prefix} to DYLD_LIBRARY_PATH to help find cairo")

    try:
        libname2 = ctypes.util.find_library('cairo') or ctypes.util.find_library('cairo-2')
        if libname2:
            try:
                rtld_flags = (getattr(ctypes, 'RTLD_GLOBAL', 0x100) | getattr(ctypes, 'RTLD_NOW', 0x2))
                ctypes.CDLL(libname2, mode=rtld_flags)
                print(f"Loaded cairo library after env change: {libname2} (RTLD_GLOBAL|RTLD_NOW)")
                if os.path.isabs(libname2) and os.path.exists(libname2):
                    _create_cairo_shim(libname2)
                return True
            except Exception as e:
                print(f"Found cairo name '{libname2}' after env update but failed to load as RTLD_GLOBAL: {e}")
    except Exception as e:
        print(f"Final attempt to load cairo failed: {e}")

    print("Cairo library not found on this system (macOS). Install cairo (e.g., 'brew install cairo') or ensure the installation's lib dir is discoverable.")
    return False


def ensure_temp_folder():
    temp_folder = os.path.join(BASE_PATH, "temp", "images")
    os.makedirs(temp_folder, exist_ok=True)
    return temp_folder

def get_compression_quality():
    config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config_json = json.load(f)
    return config_json["compression_quality"]

def get_compression_max_size():
    config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config_json = json.load(f)
    return config_json["compression_max_size"]

def get_transparency_background():
    config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config_json = json.load(f)
    return config_json["transparency_background"]

def _make_checker_bg(width, height, square=16):
    from PIL import ImageDraw
    tile_size = square * 2
    tile = Image.new("RGB", (tile_size, tile_size), (255, 255, 255))
    draw = ImageDraw.Draw(tile)
    draw.rectangle([0, 0, square - 1, square - 1], fill=(200, 200, 200))
    draw.rectangle([square, square, tile_size - 1, tile_size - 1], fill=(200, 200, 200))
    bg = Image.new("RGB", (width, height), (255, 255, 255))
    for y in range(0, height, tile_size):
        for x in range(0, width, tile_size):
            bg.paste(tile, (x, y))
    return bg

def _composite_on_background(img_path, quality):
    bg_mode = get_transparency_background()
    with Image.open(img_path) as img:
        if img.mode not in ("RGBA", "LA", "PA"):
            img = img.convert("RGBA")
        w, h = img.size
        if bg_mode == "checker":
            bg = _make_checker_bg(w, h)
        elif bg_mode == "black":
            bg = Image.new("RGB", (w, h), (0, 0, 0))
        else:
            bg = Image.new("RGB", (w, h), (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        out_path = img_path.replace(".png", ".jpg")
        if out_path == img_path:
            out_path = img_path + ".composited.jpg"
        bg.save(out_path, "JPEG", quality=quality, optimize=True)
    try:
        os.remove(img_path)
    except Exception:
        pass
    return out_path

def _resize_if_needed(path, max_size, quality):
    try:
        with Image.open(path) as img:
            w, h = img.size
            if w <= max_size and h <= max_size:
                return path
            mode = img.mode
            img_copy = img.copy()
        img_copy.thumbnail((max_size, max_size), Image.LANCZOS)
        print(f"[Compression] Resized from {w}x{h} to {img_copy.size[0]}x{img_copy.size[1]}")
        if path.endswith(".png"):
            if mode in ("RGBA", "LA", "PA"):
                img_copy.save(path, "PNG", optimize=True)
            else:
                img_copy = img_copy.convert("RGB")
                jpg_path = path[:-4] + ".jpg"
                img_copy.save(jpg_path, "JPEG", quality=quality, optimize=True)
                try:
                    os.remove(path)
                except Exception:
                    pass
                return jpg_path
        else:
            img_copy = img_copy.convert("RGB")
            img_copy.save(path, "JPEG", quality=quality, optimize=True)
        return path
    except Exception as e:
        print(f"[Compression] Error resizing {path}: {e}")
        return path

def cleanup_temp_folder():
    temp_folder = ensure_temp_folder()
    for filename in os.listdir(temp_folder):
        file_path = os.path.join(temp_folder, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error cleaning temp file {file_path}: {e}")

def _gs_render_png(input_path, png_path, width_px=None, height_px=None, dpi=300, tx=None, ty=None, extra_flags=None):
    global GHOSTSCRIPT_PATH
    # Re-resolve path if it was None (tool may have been installed during session)
    if GHOSTSCRIPT_PATH is None:
        GHOSTSCRIPT_PATH = get_ghostscript_path()
    if GHOSTSCRIPT_PATH is None:
        raise MissingToolError("ghostscript",
            "Ghostscript is required but not installed. Install it via Tools > Tools Manager.")
    args = [
        GHOSTSCRIPT_PATH,
        "-dBATCH",
        "-dNOPAUSE",
        "-dAutoRotatePages=/None",
    ]
    if extra_flags:
        args.extend(extra_flags)
    if width_px and height_px:
        args.extend([f"-g{width_px}x{height_px}", f"-r{dpi}"])
    else:
        args.extend(["-r300"])
    args.extend(["-sDEVICE=pngalpha", f"-sOutputFile={png_path}"])
    if tx is not None and ty is not None:
        args.extend(["-c", f"{tx} {ty} translate", "-f", input_path])
    else:
        args.append(input_path)
    subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **_NO_WINDOW)


def _parse_bbox_from_gs_output(output):
    hires_bbox = None
    int_bbox = None
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("%%HiResBoundingBox:"):
            parts = line.split()
            if len(parts) >= 5:
                try:
                    hires_bbox = tuple(map(float, parts[-4:]))
                except Exception:
                    pass
        elif line.startswith("%%BoundingBox:"):
            parts = line.split()
            if len(parts) >= 5:
                try:
                    int_bbox = tuple(map(float, parts[-4:]))
                except Exception:
                    pass
    return hires_bbox or int_bbox


def _parse_bbox_from_file(input_path):
    hires_bbox = None
    int_bbox = None
    try:
        with open(input_path, "rb") as f:
            header = f.read(512)
        try:
            header_str = header.decode("latin-1", errors="replace")
        except Exception:
            header_str = ""
        for line in header_str.splitlines():
            line = line.strip()
            if line.startswith("%%HiResBoundingBox:"):
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        hires_bbox = tuple(map(float, parts[-4:]))
                    except Exception:
                        pass
            elif line.startswith("%%BoundingBox:"):
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        vals = list(map(float, parts[-4:]))
                        if vals != [0, 0, 0, 0]:
                            int_bbox = tuple(vals)
                    except Exception:
                        pass
    except Exception as e:
        print(f"[EPS] Could not read header from {input_path}: {e}")
    return hires_bbox or int_bbox


def convert_eps_pdf_to_jpg(input_path, output_path, quality):
    global GHOSTSCRIPT_PATH
    if not is_ghostscript_available():
        raise MissingToolError("ghostscript", 
            "Ghostscript is required to process EPS/PDF/AI files. Install it via Tools > Tools Manager.")
    # Re-resolve path in case tool was installed during session
    if GHOSTSCRIPT_PATH is None:
        GHOSTSCRIPT_PATH = get_ghostscript_path()
    try:
        png_path = output_path.replace(".jpg", ".png")
        ext = os.path.splitext(input_path)[1].lower()
        is_eps = ext == ".eps"

        bbox = None
        if is_eps:
            bbox = _parse_bbox_from_file(input_path)
            if not bbox:
                try:
                    bbox_args = [
                        GHOSTSCRIPT_PATH, "-dBATCH", "-dNOPAUSE",
                        "-dAutoRotatePages=/None", "-sDEVICE=bbox", input_path
                    ]
                    proc = subprocess.run(bbox_args, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **_NO_WINDOW)
                    bbox = _parse_bbox_from_gs_output(proc.stdout + proc.stderr)
                except Exception as e:
                    print(f"[EPS] bbox detection failed: {e}")

        if ext in (".pdf", ".ai"):
            try:
                _gs_render_png(input_path, png_path)
            except subprocess.CalledProcessError as e:
                print(f"[PDF/AI] GS failed: {e}")
                return None
            if not os.path.exists(png_path):
                print(f"[PDF/AI] Ghostscript produced no output: {png_path}")
                return None
            if image_has_transparency(png_path):
                return png_path
            with Image.open(png_path) as img:
                rgb = img.convert("RGB")
                rgb.save(output_path, "JPEG", quality=quality, optimize=True)
            try:
                os.remove(png_path)
            except Exception:
                pass
            return output_path

        if not bbox:
            print(f"[EPS] No bounding box found, trying simple render for {input_path}")
            eps_flags = ["-dEPSCrop"] if is_eps else []
            rendered = False
            try:
                _gs_render_png(input_path, png_path, extra_flags=eps_flags)
                rendered = os.path.exists(png_path)
            except subprocess.CalledProcessError as e:
                print(f"[EPS] Simple render failed: {e}")
            if not rendered:
                print(f"[EPS] Trying PIL fallback for {input_path}")
                try:
                    gs_dir = os.path.dirname(GHOSTSCRIPT_PATH)
                    env = os.environ.copy()
                    if gs_dir and gs_dir not in env.get("PATH", ""):
                        env["PATH"] = gs_dir + (os.pathsep + env.get("PATH", ""))
                    old_env = {}
                    for k, v in env.items():
                        if k not in os.environ or os.environ[k] != v:
                            old_env[k] = os.environ.get(k)
                            os.environ[k] = v
                    with Image.open(input_path) as img:
                        img.load(scale=2)
                        rgb = img.convert("RGB")
                        rgb.thumbnail((2000, 2000), Image.LANCZOS)
                        rgb.save(output_path, "JPEG", quality=quality, optimize=True)
                    for k, v in old_env.items():
                        if v is None:
                            os.environ.pop(k, None)
                        else:
                            os.environ[k] = v
                    if os.path.exists(output_path):
                        return output_path
                except Exception as e2:
                    print(f"[EPS] PIL fallback failed: {e2}")
                return None
            if image_has_transparency(png_path):
                return png_path
            with Image.open(png_path) as img:
                rgb = img.convert("RGB")
                rgb.save(output_path, "JPEG", quality=quality, optimize=True)
            try:
                os.remove(png_path)
            except Exception:
                pass
            return output_path

        llx, lly, urx, ury = bbox
        width_pt = max(1, urx - llx)
        height_pt = max(1, ury - lly)
        dpi = 300
        width_px = int(round(width_pt * dpi / 72.0))
        height_px = int(round(height_pt * dpi / 72.0))
        try:
            safety_factor = float(os.environ.get("IMAGE_SAFETY_FACTOR", "1.05"))
        except Exception:
            safety_factor = 1.05
        bytes_per_pixel = 4
        estimated_bytes = int(width_px * height_px * bytes_per_pixel * safety_factor)
        try:
            max_mb = int(os.environ.get("IMAGE_MAX_BYTES", "256"))
        except Exception:
            max_mb = 256
        max_bytes = max_mb * 1024 * 1024
        try:
            max_dim = int(os.environ.get("IMAGE_MAX_DIM", "10000"))
        except Exception:
            max_dim = 10000
        if estimated_bytes > max_bytes or width_px > max_dim or height_px > max_dim:
            scale_mem = (max_bytes / float(estimated_bytes)) ** 0.5 if estimated_bytes > 0 else 1.0
            scale_dim = min(1.0, float(max_dim) / float(width_px), float(max_dim) / float(height_px))
            scale = min(scale_mem, scale_dim, 1.0)
            width_px = max(1, int(width_px * scale))
            height_px = max(1, int(height_px * scale))
            dpi = max(72, int(dpi * scale))
        tx = -llx
        ty = -lly
        eps_flags = ["-dEPSCrop"] if is_eps else []
        rendered = False
        try:
            _gs_render_png(input_path, png_path, width_px=width_px, height_px=height_px, dpi=dpi, tx=tx, ty=ty, extra_flags=eps_flags)
            rendered = os.path.exists(png_path)
        except subprocess.CalledProcessError as e:
            print(f"[EPS] bbox render failed ({e}), retrying without translate")
        if not rendered:
            try:
                _gs_render_png(input_path, png_path, extra_flags=["-dEPSCrop"] if is_eps else [])
                rendered = os.path.exists(png_path)
            except subprocess.CalledProcessError as e2:
                print(f"[EPS] fallback render also failed: {e2}")
        if not rendered:
            print(f"[EPS] All GS render attempts failed for {input_path}")
            return None
        if image_has_transparency(png_path):
            return png_path
        with Image.open(png_path) as img:
            rgb = img.convert("RGB")
            rgb.save(output_path, "JPEG", quality=quality, optimize=True)
        try:
            os.remove(png_path)
        except Exception:
            pass
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"Ghostscript subprocess error: {e}\nstdout: {getattr(e, 'stdout', '')}\nstderr: {getattr(e, 'stderr', '')}")
        return None
    except Exception as e:
        print(f"Ghostscript error: {e}")
        return None

def image_has_transparency(path):
    try:
        from PIL import ImageFile
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        with Image.open(path) as img:
            img.load()
            mode = img.mode
            if mode in ("RGBA", "LA", "PA"):
                alpha = img.getchannel("A")
                extrema = alpha.getextrema()
                return extrema[0] < 255
            if mode == "P":
                return 'transparency' in img.info
            return False
    except Exception as e:
        print(f"Error checking transparency for {path}: {e}")
        return False
    finally:
        try:
            from PIL import ImageFile
            ImageFile.LOAD_TRUNCATED_IMAGES = False
        except Exception:
            pass


def convert_svg_to_jpg(input_path, output_path, quality):
    global _CAIRO_AVAILABLE, CAIRO_DLL_DIR
    # Check Cairo availability (Windows uses DLL, macOS/Linux uses system lib)
    if os.name == "nt" and not _CAIRO_AVAILABLE:
        # Re-check in case Cairo was installed during session
        if is_cairo_available():
            # Reload Cairo DLL path
            tools_folder = os.path.join(BASE_PATH, "tools", "cairo")
            found_dir = None
            if os.path.isdir(tools_folder):
                for root, dirs, files in os.walk(tools_folder):
                    for f in files:
                        name = f.lower()
                        if name.endswith('.dll') and ('cairo' in name or 'libcairo' in name):
                            found_dir = root
                            break
                    if found_dir:
                        break
            if found_dir:
                CAIRO_DLL_DIR = found_dir
                if CAIRO_DLL_DIR not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = CAIRO_DLL_DIR + ";" + os.environ.get("PATH", "")
                try:
                    if hasattr(os, "add_dll_directory"):
                        os.add_dll_directory(CAIRO_DLL_DIR)
                except Exception:
                    pass
                _CAIRO_AVAILABLE = True
            else:
                raise MissingToolError("cairo",
                    "Cairo is required to process SVG files. Install it via Tools > Tools Manager.")
        else:
            raise MissingToolError("cairo",
                "Cairo is required to process SVG files. Install it via Tools > Tools Manager.")
    
    dlopen_original_flags = None
    if sys.platform == "darwin":  # noqa: E501
        if not _ensure_cairo_loaded():
            raise MissingToolError("cairo",
                "Cairo native library is not available on macOS. Install it via 'brew install cairo' or Tools > Tools Manager.")

        if hasattr(sys, 'getdlopenflags') and hasattr(sys, 'setdlopenflags'):
            try:
                dlopen_original_flags = sys.getdlopenflags()
                sys.setdlopenflags(dlopen_original_flags | getattr(ctypes, 'RTLD_GLOBAL', 0x100) | getattr(ctypes, 'RTLD_NOW', 0x2))
                print("Set dlopen flags to include RTLD_GLOBAL for cairosvg import")
            except Exception as e:
                print(f"Warning: unable to set dlopen flags: {e}")

    try:
        import cairosvg
    except Exception as e:
        print(f"CairoSVG import error: {e}")
        if sys.platform == "darwin":
            if _ensure_cairo_loaded():
                try:
                    for mod in ('cairosvg', 'cairocffi', 'cairocffi.cairo'):
                        if mod in sys.modules:
                            del sys.modules[mod]
                    importlib.invalidate_caches()
                    cairosvg = importlib.import_module('cairosvg')
                except Exception as e2:
                    print(f"CairoSVG reload after loading cairo failed: {e2}")
                    if dlopen_original_flags is not None:
                        try:
                            sys.setdlopenflags(dlopen_original_flags)
                        except Exception as e3:
                            print(f"Warning: failed to restore dlopen flags: {e3}")
                    raise MissingToolError("cairo",
                        "Cairo/CairoSVG failed to load. Install Cairo via Tools > Tools Manager.") from e2
            else:
                if dlopen_original_flags is not None:
                    try:
                        sys.setdlopenflags(dlopen_original_flags)
                    except Exception as e3:
                        print(f"Warning: failed to restore dlopen flags: {e3}")
                raise MissingToolError("cairo",
                    "Cairo native library not available. Install Cairo via Tools > Tools Manager.") from e
        else:
            if dlopen_original_flags is not None:
                try:
                    sys.setdlopenflags(dlopen_original_flags)
                except Exception as e3:
                    print(f"Warning: failed to restore dlopen flags: {e3}")
            raise MissingToolError("cairo",
                "CairoSVG/Cairo is not available. Install Cairo via Tools > Tools Manager.") from e

    if sys.platform == "darwin" and dlopen_original_flags is not None:
        try:
            sys.setdlopenflags(dlopen_original_flags)
        except Exception as e:
            print(f"Warning: failed to restore dlopen flags after import: {e}")

    try:
        temp_png = output_path.replace(".jpg", ".png")
        cairosvg.svg2png(url=input_path, write_to=temp_png)
        if image_has_transparency(temp_png):
            return temp_png
        with Image.open(temp_png) as img:
            rgb_img = img.convert("RGB")
            rgb_img.save(output_path, "JPEG", quality=quality, optimize=True)
        try:
            os.remove(temp_png)
        except Exception:
            pass
        return output_path
    except Exception as e:
        print(f"CairoSVG rendering error: {e}")
        return None

def compress_and_save_image(image_path):
    temp_folder = ensure_temp_folder()
    quality = get_compression_quality()
    max_size = get_compression_max_size()
    ext = os.path.splitext(image_path)[1].lower()
    filename = os.path.splitext(os.path.basename(image_path))[0] + ".jpg"
    save_path = os.path.join(temp_folder, filename)

    if ext in (".eps", ".pdf", ".ai"):
        result = convert_eps_pdf_to_jpg(image_path, save_path, quality)
        if result:
            result = _resize_if_needed(result, max_size, quality)
            if result and image_has_transparency(result):
                result = _composite_on_background(result, quality)
        return result
    elif ext == ".svg":
        result = convert_svg_to_jpg(image_path, save_path, quality)
        if result:
            result = _resize_if_needed(result, max_size, quality)
            if result and image_has_transparency(result):
                result = _composite_on_background(result, quality)
        return result
    elif ext in PILLOW_FORMATS:
        try:
            with Image.open(image_path) as img:
                has_alpha = img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)
                if has_alpha:
                    img_copy = img.convert("RGBA")
                else:
                    img_copy = img.convert("RGB")
                w, h = img_copy.size
                if w > max_size or h > max_size:
                    img_copy.thumbnail((max_size, max_size), Image.LANCZOS)
                    print(f"[Compression] Resized from {w}x{h} to {img_copy.size[0]}x{img_copy.size[1]}")
                if has_alpha:
                    tmp_png = save_path.replace(".jpg", "_tmp.png")
                    img_copy.save(tmp_png, "PNG")
                    result = _composite_on_background(tmp_png, quality)
                    return result
                else:
                    img_copy.save(save_path, "JPEG", quality=quality, optimize=True)
                    return save_path
        except Exception as e:
            print(f"Error compressing image: {e}")
            return None
    else:
        print(f"Error: File extension {ext} is not supported by Pillow or converters.")
        return None