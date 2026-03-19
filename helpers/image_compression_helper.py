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

_NO_WINDOW = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}

CAIRO_DLL_DIR = os.path.join(BASE_PATH, "tools", "cairo", "cairo-windows-1.17.2", "lib", "x64")
from tools.tools_checker import download_and_extract_cairo

if os.name == "nt":
    if not os.path.exists(CAIRO_DLL_DIR):
        tools_folder = os.path.join(BASE_PATH, "tools", "cairo")
        print(f"Cairo DLL dir not found at {CAIRO_DLL_DIR}; attempting to ensure tools folder: {tools_folder}")
        ok = download_and_extract_cairo(tools_folder)
        if ok:
            print("Cairo package downloaded/extracted; searching for DLLs...")
            found_dir = None
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
                print(f"Found Cairo DLL directory: {CAIRO_DLL_DIR}")
            else:
                print(f"Cairo DLLs not found after extraction in {tools_folder}")
        else:
            print(f"Cairo not available in {tools_folder}; download/extract did not succeed")

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
        print(f"Ghostscript: bundled Windows executable not found at {path}, will try PATH")
        return "gs"

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
            print(f"Ghostscript found at {p}")
            return p

    bundled_path = os.path.join(BASE_PATH, "tools", "ghostscript", "gs")
    if os.path.exists(bundled_path) and os.access(bundled_path, os.X_OK):
        print(f"Using bundled Ghostscript at {bundled_path}")
        return bundled_path

    print("Ghostscript executable not found in standard locations. Falling back to 'gs' (must be in PATH) — consider installing Ghostscript (e.g., 'brew install ghostscript').")
    return "gs"

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

def cleanup_temp_folder():
    temp_folder = ensure_temp_folder()
    for filename in os.listdir(temp_folder):
        file_path = os.path.join(temp_folder, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error cleaning temp file {file_path}: {e}")

def convert_eps_pdf_to_jpg(input_path, output_path, quality):
    try:
        png_path = output_path.replace(".jpg", ".png")
        bbox_args = [
            GHOSTSCRIPT_PATH,
            "-dBATCH",
            "-dNOPAUSE",
            "-sDEVICE=bbox",
            input_path
        ]
        proc = subprocess.run(bbox_args, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **_NO_WINDOW)
        output = proc.stdout + proc.stderr
        bbox = None
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("%%BoundingBox:") or line.startswith("%%HiResBoundingBox:"):
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        llx, lly, urx, ury = map(float, parts[-4:])
                        bbox = (llx, lly, urx, ury)
                    except Exception:
                        continue
        ext = os.path.splitext(input_path)[1].lower()
        if ext in (".pdf", ".ai"):
            args = [
                GHOSTSCRIPT_PATH,
                "-dBATCH",
                "-dNOPAUSE",
                "-sDEVICE=pngalpha",
                "-r300",
                f"-sOutputFile={png_path}",
                input_path
            ]
            subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **_NO_WINDOW)
            if not os.path.exists(png_path):
                print(f"Ghostscript did not produce output: {png_path}")
                return None
            if image_has_transparency(png_path):
                return png_path
            else:
                jpg_args = [
                    GHOSTSCRIPT_PATH,
                    "-dBATCH",
                    "-dNOPAUSE",
                    "-sDEVICE=jpeg",
                    f"-dJPEGQ={quality}",
                    "-r300",
                    f"-sOutputFile={output_path}",
                    input_path
                ]
                subprocess.run(jpg_args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **_NO_WINDOW)
                if os.path.exists(output_path):
                    try:
                        os.remove(png_path)
                    except Exception:
                        pass
                    return output_path
                else:
                    print(f"Ghostscript did not produce output: {output_path}")
                    return None
        if not bbox:
            args = [
                GHOSTSCRIPT_PATH,
                "-dBATCH",
                "-dNOPAUSE",
                "-sDEVICE=pngalpha",
                "-r300",
                f"-sOutputFile={png_path}",
                input_path
            ]
            subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **_NO_WINDOW)
            if not os.path.exists(png_path):
                print(f"Ghostscript did not produce output: {png_path}")
                return None
            if image_has_transparency(png_path):
                return png_path
            else:
                jpg_args = [
                    GHOSTSCRIPT_PATH,
                    "-dBATCH",
                    "-dNOPAUSE",
                    "-sDEVICE=jpeg",
                    f"-dJPEGQ={quality}",
                    "-r300",
                    f"-sOutputFile={output_path}",
                    input_path
                ]
                subprocess.run(jpg_args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **_NO_WINDOW)
                if os.path.exists(output_path):
                    try:
                        os.remove(png_path)
                    except Exception:
                        pass
                    return output_path
                else:
                    print(f"Ghostscript did not produce output: {output_path}")
                    return None
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
            new_width_px = max(1, int(width_px * scale))
            new_height_px = max(1, int(height_px * scale))
            new_dpi = max(72, int(dpi * scale))
            width_px, height_px, dpi = new_width_px, new_height_px, new_dpi
        tx = -llx
        ty = -lly
        gs_args = [
            GHOSTSCRIPT_PATH,
            "-dBATCH",
            "-dNOPAUSE",
            f"-g{width_px}x{height_px}",
            f"-r{dpi}",
            "-sDEVICE=pngalpha",
            f"-sOutputFile={png_path}",
            "-c",
            f"{tx} {ty} translate",
            "-f",
            input_path
        ]
        subprocess.run(gs_args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **_NO_WINDOW)
        if not os.path.exists(png_path):
            print(f"Ghostscript did not produce output after bbox rasterize: {png_path}")
            return None
        if image_has_transparency(png_path):
            return png_path
        else:
            gs_args_jpg = [
                GHOSTSCRIPT_PATH,
                "-dBATCH",
                "-dNOPAUSE",
                f"-g{width_px}x{height_px}",
                f"-r{dpi}",
                "-sDEVICE=jpeg",
                f"-dJPEGQ={quality}",
                f"-sOutputFile={output_path}",
                "-c",
                f"{tx} {ty} translate",
                "-f",
                input_path
            ]
            subprocess.run(gs_args_jpg, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **_NO_WINDOW)
            if os.path.exists(output_path):
                try:
                    os.remove(png_path)
                except Exception:
                    pass
                return output_path
            else:
                print(f"Ghostscript did not produce output after jpeg rasterize: {output_path}")
                return None
    except subprocess.CalledProcessError as e:
        print(f"Ghostscript subprocess error: {e}\nstdout: {getattr(e, 'stdout', '')}\nstderr: {getattr(e, 'stderr', '')}")
        return None
    except Exception as e:
        print(f"Ghostscript error: {e}")
        return None

def image_has_transparency(path):
    try:
        with Image.open(path) as img:
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


def convert_svg_to_jpg(input_path, output_path, quality):
    dlopen_original_flags = None
    if sys.platform == "darwin":
        if not _ensure_cairo_loaded():
            print("Cannot render SVG: cairo native library not available on macOS.")
            return None
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
                    return None
            else:
                if dlopen_original_flags is not None:
                    try:
                        sys.setdlopenflags(dlopen_original_flags)
                    except Exception as e3:
                        print(f"Warning: failed to restore dlopen flags: {e3}")
                return None
        else:
            if dlopen_original_flags is not None:
                try:
                    sys.setdlopenflags(dlopen_original_flags)
                except Exception as e3:
                    print(f"Warning: failed to restore dlopen flags: {e3}")
            return None

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
        os.remove(temp_png)
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
        return convert_eps_pdf_to_jpg(image_path, save_path, quality)
    elif ext == ".svg":
        return convert_svg_to_jpg(image_path, save_path, quality)
    elif ext in PILLOW_FORMATS:
        try:
            with Image.open(image_path) as img:
                rgb_img = img.convert("RGB")
                w, h = rgb_img.size
                if w > max_size or h > max_size:
                    rgb_img.thumbnail((max_size, max_size), Image.LANCZOS)
                    print(f"[Compression] Resized from {w}x{h} to {rgb_img.size[0]}x{rgb_img.size[1]}")
                rgb_img.save(
                    save_path,
                    "JPEG",
                    quality=quality,
                    optimize=True
                )
                return save_path
        except Exception as e:
            print(f"Error compressing image: {e}")
            return None
    else:
        print(f"Error: File extension {ext} is not supported by Pillow or converters.")
        return None