import os
import sys
import json
import subprocess
from PIL import Image
import config

BASE_PATH = config.BASE_PATH

CAIRO_DLL_DIR = os.path.join(BASE_PATH, "tools", "cairo", "cairo-windows-1.17.2", "lib", "x64")
if os.name == "nt":
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

# Ambil Ghostscript dari tools/ghostscript/gswin64c.exe
GHOSTSCRIPT_PATH = os.path.join(BASE_PATH, "tools", "ghostscript", "gswin64c.exe")

def ensure_temp_folder():
    temp_folder = os.path.join(BASE_PATH, "temp", "images")
    os.makedirs(temp_folder, exist_ok=True)
    return temp_folder

def get_compression_quality():
    config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config_json = json.load(f)
    return config_json["compression_quality"]

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
        # First, get the bounding box of the input using Ghostscript bbox device
        # Ghostscript prints a line like: "%%BoundingBox: llx lly urx ury"
        bbox_args = [
            GHOSTSCRIPT_PATH,
            "-dBATCH",
            "-dNOPAUSE",
            "-sDEVICE=bbox",
            input_path
        ]
        proc = subprocess.run(bbox_args, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output = proc.stdout + proc.stderr
        # Parse the last BoundingBox found
        bbox = None
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("%%BoundingBox:") or line.startswith("%%HiResBoundingBox:"):
                parts = line.split()
                # expect 5 tokens: %%BoundingBox: llx lly urx ury
                if len(parts) >= 5:
                    try:
                        llx, lly, urx, ury = map(float, parts[-4:])
                        bbox = (llx, lly, urx, ury)
                    except Exception:
                        continue

        # If no bbox found, fall back to default rasterization
        if not bbox:
            args = [
                GHOSTSCRIPT_PATH,
                "-dBATCH",
                "-dNOPAUSE",
                "-sDEVICE=jpeg",
                f"-dJPEGQ={quality}",
                "-r300",
                f"-sOutputFile={output_path}",
                input_path
            ]
            subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if os.path.exists(output_path):
                return output_path
            else:
                print(f"Ghostscript did not produce output: {output_path}")
                return None

        # Compute width and height in points
        llx, lly, urx, ury = bbox
        width_pt = max(1, urx - llx)
        height_pt = max(1, ury - lly)

        # Choose DPI and compute pixel size
        dpi = 300
        width_px = int(round(width_pt * dpi / 72.0))
        height_px = int(round(height_pt * dpi / 72.0))

        # Estimate memory usage: QImage typically uses 4 bytes per pixel (RGBA/32-bit)
        # Add a small safety factor to account for alignment/overhead used by Qt
        try:
            safety_factor = float(os.environ.get("IMAGE_SAFETY_FACTOR", "1.05"))
        except Exception:
            safety_factor = 1.05
        bytes_per_pixel = 4
        estimated_bytes = int(width_px * height_px * bytes_per_pixel * safety_factor)

        # Allow overriding max bytes via environment var IMAGE_MAX_BYTES (MB)
        try:
            max_mb = int(os.environ.get("IMAGE_MAX_BYTES", "256"))
        except Exception:
            max_mb = 256
        max_bytes = max_mb * 1024 * 1024

        # Also cap dimensions to a sane maximum to avoid extremely large images
        try:
            max_dim = int(os.environ.get("IMAGE_MAX_DIM", "10000"))
        except Exception:
            max_dim = 10000

        # If estimated memory is too big or dimensions exceed cap, downscale
        if estimated_bytes > max_bytes or width_px > max_dim or height_px > max_dim:
            scale_mem = (max_bytes / float(estimated_bytes)) ** 0.5 if estimated_bytes > 0 else 1.0
            scale_dim = min(1.0, float(max_dim) / float(width_px), float(max_dim) / float(height_px))
            scale = min(scale_mem, scale_dim, 1.0)
            new_width_px = max(1, int(width_px * scale))
            new_height_px = max(1, int(height_px * scale))
            new_dpi = max(72, int(dpi * scale))
            # scaled to fit memory/dimension limits
            width_px, height_px, dpi = new_width_px, new_height_px, new_dpi
        else:
            pass

        # Use Ghostscript to rasterize to exact device width/height to capture full bbox
        # We set -c translate so that llx/lly becomes origin.
        # translate by negative llx/lly so the bbox' lower-left corner maps to origin (0,0)
        tx = -llx
        ty = -lly

        gs_args = [
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

        subprocess.run(gs_args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if os.path.exists(output_path):
            return output_path
        else:
            print(f"Ghostscript did not produce output after bbox rasterize: {output_path}")
            return None
    except subprocess.CalledProcessError as e:
        print(f"Ghostscript subprocess error: {e}\nstdout: {getattr(e, 'stdout', '')}\nstderr: {getattr(e, 'stderr', '')}")
        return None
    except Exception as e:
        print(f"Ghostscript error: {e}")
        return None

def convert_svg_to_jpg(input_path, output_path, quality):
    try:
        import cairosvg
        temp_png = output_path.replace(".jpg", ".png")
        cairosvg.svg2png(url=input_path, write_to=temp_png)
        with Image.open(temp_png) as img:
            rgb_img = img.convert("RGB")
            rgb_img.save(output_path, "JPEG", quality=quality, optimize=True)
        os.remove(temp_png)
        return output_path
    except Exception as e:
        print(f"CairoSVG error: {e}")
        return None

def compress_and_save_image(image_path):
    cleanup_temp_folder()
    temp_folder = ensure_temp_folder()
    quality = get_compression_quality()
    ext = os.path.splitext(image_path)[1].lower()
    filename = os.path.splitext(os.path.basename(image_path))[0] + ".jpg"
    save_path = os.path.join(temp_folder, filename)

    if ext in (".eps", ".pdf"):
        return convert_eps_pdf_to_jpg(image_path, save_path, quality)
    elif ext == ".svg":
        return convert_svg_to_jpg(image_path, save_path, quality)
    elif ext in PILLOW_FORMATS:
        try:
            with Image.open(image_path) as img:
                rgb_img = img.convert("RGB")
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