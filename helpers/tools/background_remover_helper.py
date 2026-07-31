import os
import numpy as np
from PIL import Image


def apply_levels_to_mask(mask_image, black_point=0, mid_point=128, white_point=255):
    if isinstance(mask_image, str):
        mask = Image.open(mask_image).convert('L')
    else:
        mask = mask_image.convert('L')

    mask_array = np.array(mask, dtype=np.float32)
    input_black = float(black_point)
    input_white = float(white_point)

    mask_array = np.clip(mask_array, input_black, input_white)
    mask_array = (mask_array - input_black) / max(1.0, (input_white - input_black))

    if mid_point != 128:
        if mid_point < 128:
            gamma = 1.0 + (128.0 - mid_point) / 128.0
        else:
            gamma = 128.0 / float(mid_point)
        mask_array = np.power(mask_array, gamma)

    mask_array = mask_array * 255.0
    mask_array = np.clip(mask_array, 0, 255).astype(np.uint8)
    return Image.fromarray(mask_array)


def create_binary_mask(mask_image, threshold=128):
    mask = mask_image.convert("L")
    mask_array = np.array(mask, dtype=np.uint8)
    binary_mask = np.zeros_like(mask_array)
    binary_mask[mask_array > threshold] = 255
    return Image.fromarray(binary_mask)


def enhance_transparency_with_levels(image_path, mask_path, output_path,
                                     black_point=0, mid_point=128, white_point=255,
                                     save_adjusted_mask=False):
    adjusted_mask_path = None
    try:
        main_image = Image.open(image_path)
        mask_image = Image.open(mask_path)

        if main_image.size != mask_image.size:
            mask_image = mask_image.resize(main_image.size, Image.LANCZOS)

        using_extreme = (white_point < 10) or (black_point > 240) or (mid_point < 10)

        if using_extreme:
            threshold = 127
            if white_point < 10:
                threshold = max(10, white_point * 10)
            elif black_point > 240:
                threshold = min(240, black_point)
            adjusted_mask = create_binary_mask(mask_image, threshold=threshold)
        else:
            adjusted_mask = apply_levels_to_mask(
                mask_image, black_point=black_point,
                mid_point=mid_point, white_point=white_point
            )

        # Always save the adjusted mask (needed for auto crop), even if user doesn't want to keep it
        base = os.path.splitext(output_path)[0]
        adjusted_mask_path = base + "_mask.png"
        adjusted_mask.save(adjusted_mask_path)

        rgb = main_image.convert("RGB")
        r, g, b = rgb.split()
        result = Image.merge("RGBA", (r, g, b, adjusted_mask))
        result.save(output_path)

        return output_path, adjusted_mask_path
    except Exception:
        return None, None


def get_crop_bounds(mask_image, detection_threshold=30, margin=10):
    mask = mask_image.convert("L")
    mask_array = np.array(mask, dtype=np.uint8)
    height, width = mask_array.shape

    left = 0
    while left < width:
        if np.max(mask_array[:, left]) > detection_threshold:
            break
        left += 1

    right = width - 1
    while right >= 0:
        if np.max(mask_array[:, right]) > detection_threshold:
            break
        right -= 1

    top = 0
    while top < height:
        if np.max(mask_array[top, :]) > detection_threshold:
            break
        top += 1

    bottom = height - 1
    while bottom >= 0:
        if np.max(mask_array[bottom, :]) > detection_threshold:
            break
        bottom -= 1

    if left >= right or top >= bottom:
        return None

    left = max(0, left - margin)
    top = max(0, top - margin)
    right = min(width, right + 1 + margin)
    bottom = min(height, bottom + 1 + margin)

    return (left, top, right, bottom)


def crop_transparent_image(image_path, mask_path, margin=10, output_path=None):
    try:
        if not os.path.exists(mask_path):
            return image_path

        image = Image.open(image_path)
        mask = Image.open(mask_path)

        bounds = get_crop_bounds(mask, detection_threshold=30, margin=margin)
        if not bounds:
            return image_path

        cropped = image.crop(bounds)
        target = output_path or image_path
        cropped.save(target)
        return target
    except Exception:
        return image_path


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def add_solid_background(image_path, output_path, bg_color="#FFFFFF"):
    try:
        if not os.path.exists(image_path):
            return None

        img = Image.open(image_path).convert("RGBA")
        bg_rgb = hex_to_rgb(bg_color)
        background = Image.new("RGBA", img.size, (*bg_rgb, 255))

        fg_array = np.array(img, dtype=np.float32) / 255.0
        bg_array = np.array(background, dtype=np.float32) / 255.0

        fg_rgb = fg_array[:, :, :3]
        fg_alpha = fg_array[:, :, 3, np.newaxis]
        bg_rgb = bg_array[:, :, :3]

        out_rgb = fg_rgb * fg_alpha + bg_rgb * (1.0 - fg_alpha)
        out_array = np.zeros((fg_array.shape[0], fg_array.shape[1], 3), dtype=np.float32)
        out_array[:, :, :3] = out_rgb
        out_array_8bit = (out_array * 255.0).astype(np.uint8)

        result = Image.fromarray(out_array_8bit, mode="RGB")
        result.save(output_path)
        return output_path
    except Exception:
        return None


def convert_to_jpg(image_path, output_path, quality=90):
    try:
        if not os.path.exists(image_path):
            return None

        img = Image.open(image_path)
        if img.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        img.save(output_path, "JPEG", quality=quality, optimize=True)
        return output_path
    except Exception:
        return None


def recommend_alpha_matting_params(image):
    grayscale = image.convert("L")
    np_img = np.array(grayscale)
    img_std = np.std(np_img)
    img_min = np.min(np_img)
    img_max = np.max(np_img)
    contrast_ratio = (img_max - img_min) / 255

    if contrast_ratio < 0.4 or img_std < 30:
        return {
            "alpha_matting_foreground_threshold": 220,
            "alpha_matting_background_threshold": 20,
            "alpha_matting_erode_size": 15,
            "alpha_matting_discard_threshold": 0.0001,
            "alpha_matting_shift": 0.02
        }
    elif contrast_ratio < 0.7:
        return {
            "alpha_matting_foreground_threshold": 240,
            "alpha_matting_background_threshold": 10,
            "alpha_matting_erode_size": 10,
            "alpha_matting_discard_threshold": 0.0001,
            "alpha_matting_shift": 0.01
        }
    else:
        return {
            "alpha_matting_foreground_threshold": 250,
            "alpha_matting_background_threshold": 5,
            "alpha_matting_erode_size": 5,
            "alpha_matting_discard_threshold": 0.0001,
            "alpha_matting_shift": 0.001
        }