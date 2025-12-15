"""
Imagen Generator Helper

This module will contain helper functions for generating images using AI services.
Currently a placeholder for future implementation.
"""

import os
import json
import random
import time
import base64
from config import BASE_PATH

# Base mapping of OpenRouter supported aspect ratios to recommended base resolution
_OPENROUTER_ASPECT_RES_BASE = {
    '1:1': '1024x1024',
    '2:3': '832x1248',
    '3:2': '1248x832',
    '3:4': '864x1184',
    '4:3': '1184x864',
    '4:5': '896x1152',
    '5:4': '1152x896',
    '9:16': '768x1344',
    '16:9': '1344x768',
    '21:9': '1536x672'
}


def _parse_resolution(res_str: str):
    try:
        w, h = res_str.split('x')
        return int(w), int(h)
    except Exception:
        return None, None


def _format_resolution(w: int, h: int):
    return f"{int(w)}x{int(h)}"


def get_openrouter_resolutions(aspect_ratio: str):
    """Return a list of resolution options for given aspect ratio.

    Includes base resolution and scaled variants (1.5x and 2x) when reasonable.
    """
    base = _OPENROUTER_ASPECT_RES_BASE.get(aspect_ratio)
    if not base:
        return []
    w, h = _parse_resolution(base)
    if not w or not h:
        return [base]
    variants = []
    for factor in (1.0, 1.5, 2.0):
        nw = int(round(w * factor))
        nh = int(round(h * factor))
        variants.append(_format_resolution(nw, nh))
    # Deduplicate while preserving order
    seen = set()
    dedup = []
    for v in variants:
        if v not in seen:
            dedup.append(v)
            seen.add(v)
    return dedup


def get_delay_interval():
    """Get delay interval from config"""
    try:
        config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        delay_value = config.get('delay_interval', 'Random')
        
        if delay_value == 'No Delay':
            return 0
        elif delay_value == 'Random':
            return random.uniform(1, 5)
        else:
            try:
                return float(delay_value)
            except ValueError:
                return random.uniform(1, 5)
    except Exception as e:
        print(f"Error loading delay interval: {e}")
        return random.uniform(1, 5)


def load_imagen_config():
    """Load imagen generator configuration from ai_config.json"""
    try:
        config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("imagen_generator", {})
        return {}
    except Exception as e:
        print(f"Error loading imagen config: {e}")
        return {}


def save_imagen_config(config_data):
    """Save imagen generator configuration to ai_config.json"""
    try:
        config_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
        
        # Load existing config
        full_config = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                full_config = json.load(f)
        
        # Update imagen_generator section
        full_config["imagen_generator"] = config_data
        
        # Save back to file
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(full_config, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        print(f"Error saving imagen config: {e}")


def generate_images_from_prompts(prompts, api_key, service, model, **kwargs):
    """
    Generate images from prompts using specified AI service.
    
    Args:
        prompts (list): List of text prompts to generate images from
        api_key (str): API key for the AI service
        service (str): AI service name (e.g., 'openai', 'google')
        model (str): Model name to use for generation
        **kwargs: Additional parameters like number_of_images, aspect_ratio, image_size, output_mime_type, etc.
    
    Returns:
        list: List of generated image results
    """
    
    print(f"Debug: Starting image generation with service={service}, model={model}")
    print(f"Debug: Number of prompts to process: {len(prompts)}")
    
    # Get callback functions for real-time status updates
    status_callback = kwargs.get('status_callback', None)
    progress_callback = kwargs.get('progress_callback', None)
    
    if service.lower() not in ('google', 'gemini', 'openrouter', 'openrouter.ai', 'openai'):
        error_msg = f'Only Google/Gemini or OpenRouter (or OpenAI via OpenRouter keys) service is supported for image generation. Got: {service}'
        print(f"Debug: Service error: {error_msg}")
        return [{'status': 'error', 'error': error_msg}]
    
    try:
        results = []

        if service.lower() in ('google', 'gemini'):
            print(f"Debug: Importing Google GenAI library...")
            from google import genai
            print(f"Debug: Creating GenAI client...")
            client = genai.Client(api_key=api_key)

            for idx, prompt in enumerate(prompts, 1):
                print(f"Debug: Processing prompt {idx}/{len(prompts)}: {prompt[:100]}...")
                # Get prompt info for status callback
                prompt_info = prompt if isinstance(prompt, dict) else {'prompt': prompt}

                # Update status to processing
                if status_callback:
                    status_callback(prompt_info, 'processing')

                try:
                    # Prepare generation config using proper parameter names
                    config_params = {
                        'number_of_images': kwargs.get('number_of_images', 4),
                    }

                    # Add aspect ratio if provided
                    if 'aspect_ratio' in kwargs:
                        config_params['aspect_ratio'] = kwargs['aspect_ratio']

                    # Add image size if provided (using proper parameter name)
                    if 'image_size' in kwargs:
                        config_params['image_size'] = kwargs['image_size']

                    # Add output format if provided
                    if 'output_mime_type' in kwargs:
                        config_params['output_mime_type'] = kwargs['output_mime_type']

                    print(f"Debug: Config params: {config_params}")

                    print(f"Debug: Calling Gemini API to generate images...")
                    # Generate images using the working method from imagen.py
                    response = client.models.generate_images(
                        model=model,
                        prompt=prompt_info.get('prompt', prompt),
                        config=config_params
                    )

                    print(f"Debug: Got response from Gemini, processing images...")

                    # Save generated images
                    output_folder = kwargs.get('output_folder', '')
                    if output_folder:
                        try:
                            if not os.path.exists(output_folder):
                                os.makedirs(output_folder, exist_ok=True)
                        except Exception as e:
                            print(f"Debug: Failed to create provided output folder '{output_folder}': {e}")
                            output_folder = os.path.join(BASE_PATH, 'temp', 'images')
                            os.makedirs(output_folder, exist_ok=True)
                    else:
                        output_folder = os.path.join(BASE_PATH, 'temp', 'images')
                        os.makedirs(output_folder, exist_ok=True)

                    print(f"Debug: Saving images to: {output_folder}")

                    saved_images = []
                    saved_images_meta = []
                    images_generated = 0

                    # Determine file extension from output_mime_type
                    output_format = kwargs.get('output_mime_type', 'image/png')
                    file_extension = '.png' if output_format == 'image/png' else '.jpg'

                    for i, generated_image in enumerate(response.generated_images, 1):
                        try:
                            # Create filename based on prompt and index
                            safe_prompt = "".join(c for c in prompt_info.get('prompt', prompt) if c.isalnum() or c in (' ', '-', '_')).rstrip()
                            safe_prompt = safe_prompt[:50]  # Limit length
                            filename = f"{safe_prompt}_{i:03d}{file_extension}"
                            filepath = os.path.join(output_folder, filename)

                            print(f"Debug: Saving image {i} as: {filename}")

                            # Save the image
                            generated_image.image.save(filepath)
                            saved_images.append(filepath)
                            images_generated += 1

                        except Exception as e:
                            print(f"Debug: Error saving image {i}: {e}")
                            continue

                    print(f"Debug: Successfully generated {images_generated} images for this prompt")

                    # Update status to success
                    if status_callback:
                        status_callback(prompt_info, 'success', images_generated)

                    results.append({
                        'prompt': prompt_info.get('prompt', prompt),
                        'prompt_info': prompt_info,
                        'status': 'success',
                        'images_generated': images_generated,
                        'saved_images': saved_images,
                        'error': None
                    })

                except Exception as e:
                    error_msg = str(e)
                    print(f"Debug: Error generating images for prompt {idx}: {error_msg}")

                    # Update status to failed
                    if status_callback:
                        status_callback(prompt_info, 'failed', 0, error_msg)

                    results.append({
                        'prompt': prompt_info.get('prompt', prompt),
                        'prompt_info': prompt_info,
                        'status': 'error',
                        'images_generated': 0,
                        'saved_images': [],
                        'error': error_msg
                    })

                # Add delay between prompts (except for the last one)
                if idx < len(prompts):
                    delay_seconds = get_delay_interval()
                    if progress_callback:
                        progress_callback(f"Waiting {delay_seconds:.1f} seconds delay...")
                    time.sleep(delay_seconds)

            print(f"Debug: Completed all prompts. Total results: {len(results)}")
            return results

        # OpenRouter path (also handle service=='openai' when API key indicates OpenRouter)
        try:
            from helpers.ai_helper.openai_helper import _is_openrouter_key
        except Exception:
            def _is_openrouter_key(key):
                return False

        if service.lower() in ('openrouter', 'openrouter.ai') or (service.lower() == 'openai' and _is_openrouter_key(api_key)):
            try:
                import requests
            except Exception as e:
                error_msg = f'Requests library is required for OpenRouter support: {e}'
                print(f"Debug: Import error: {error_msg}")
                return [{'status': 'error', 'error': error_msg}]

            url = 'https://openrouter.ai/api/v1/chat/completions'

            for idx, prompt in enumerate(prompts, 1):
                print(f"Debug: OpenRouter processing prompt {idx}/{len(prompts)}: {str(prompt)[:120]}...")
                prompt_text = prompt if isinstance(prompt, str) else (prompt.get('prompt') or str(prompt))

                if status_callback:
                    status_callback({'prompt': prompt_text}, 'processing')

                image_cfg = {}
                # Respect explicit aspect_ratio when provided
                aspect_ratio = kwargs.get('aspect_ratio') if kwargs.get('aspect_ratio') else None
                if aspect_ratio:
                    image_cfg['aspect_ratio'] = aspect_ratio

                # Resolve resolution preference: explicit > kwargs aliases > auto-select highest supported
                resolution = (kwargs.get('resolution') or kwargs.get('image_resolution') or kwargs.get('output_resolution') or '').strip()
                if not resolution and aspect_ratio:
                    # Default to the largest available OpenRouter variant for the aspect ratio
                    opts = get_openrouter_resolutions(aspect_ratio)
                    if opts:
                        resolution = opts[-1]
                        print(f"Debug: No explicit resolution provided. Defaulting to highest OpenRouter resolution: {resolution}")

                if resolution:
                    image_cfg['resolution'] = resolution

                if image_cfg:
                    # Delay adding to payload until we build the message and the payload dict below
                    pass

                # Helpful debug: show what image_config we will send
                if image_cfg:
                    print(f"Debug: OpenRouter image_config: {json.dumps(image_cfg)}")

                # Augment the user message to explicitly request the chosen resolution so the model sees it
                sent_message = prompt_text
                if image_cfg.get('resolution'):
                    req_res = image_cfg.get('resolution')
                    ar_text = image_cfg.get('aspect_ratio') or ''
                    sent_message = (
                        f"{prompt_text}\n\nPlease generate the image at exact resolution {req_res}"
                        f"{(' (' + ar_text + ')' ) if ar_text else ''}."
                        " If you cannot produce the exact size, return the largest possible image maintaining the same aspect ratio."
                    )
                    print(f"Debug: Augmented prompt to request resolution: {req_res}")

                # Build payload now that message and image_config are finalized
                payload = {
                    'model': model,
                    'messages': [{'role': 'user', 'content': sent_message}],
                    'modalities': ['image', 'text']
                }
                if image_cfg:
                    payload['image_config'] = image_cfg

                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                }

                try:
                    resp = requests.post(url, headers=headers, json=payload, timeout=60)
                    if resp.status_code != 200:
                        error_msg = f'OpenRouter API error: {resp.status_code} {resp.text}'
                        print(f"Debug: {error_msg}")
                        results.append({'prompt': prompt_text, 'status': 'error', 'images_generated': 0, 'saved_images': [], 'error': error_msg})
                        continue

                    data = resp.json()
                    choices = data.get('choices') or []
                    if not choices:
                        results.append({'prompt': prompt_text, 'status': 'error', 'images_generated': 0, 'saved_images': [], 'error': 'No choices in OpenRouter response'})
                        continue

                    message = choices[0].get('message', {})
                    images = message.get('images', []) or message.get('image', [])

                    if not images:
                        # Some responses may include base64 directly in message.content or other fields
                        results.append({'prompt': prompt_text, 'status': 'error', 'images_generated': 0, 'saved_images': [], 'error': 'No images in OpenRouter response'})
                        continue

                    # Prepare output folder - prefer user-provided folder; try to create if missing
                    output_folder = kwargs.get('output_folder', '')
                    if output_folder:
                        try:
                            if not os.path.exists(output_folder):
                                os.makedirs(output_folder, exist_ok=True)
                        except Exception as e:
                            print(f"Debug: Failed to create provided output folder '{output_folder}': {e}")
                            output_folder = os.path.join(BASE_PATH, 'temp', 'images')
                            os.makedirs(output_folder, exist_ok=True)
                    else:
                        output_folder = os.path.join(BASE_PATH, 'temp', 'images')
                        os.makedirs(output_folder, exist_ok=True)

                    saved_images = []
                    saved_images_meta = []
                    warnings = []
                    images_generated = 0

                    for i, image_obj in enumerate(images, 1):
                        try:
                            # Try several fields for image data
                            img_url = None
                            fetched_url = None
                            resp_content_len = None
                            resp_content_type = None
                            if isinstance(image_obj, dict):
                                # image_url may be nested
                                img_url = image_obj.get('image_url', {}).get('url') if image_obj.get('image_url') else image_obj.get('url')
                                # Some responses include b64 directly
                                b64data = image_obj.get('b64_json') or image_obj.get('b64') or image_obj.get('base64')
                                # Capture any provided metadata from OpenRouter response
                                meta_w = image_obj.get('width') or image_obj.get('w') or None
                                meta_h = image_obj.get('height') or image_obj.get('h') or None
                                if meta_w or meta_h:
                                    print(f"Debug: OpenRouter returned image metadata: width={meta_w}, height={meta_h}")
                                else:
                                    meta_w = None
                                    meta_h = None
                            else:
                                img_url = str(image_obj)
                                b64data = None

                            img_bytes = None
                            ext = '.png'

                            if img_url and img_url.startswith('data:'):
                                # data URL
                                try:
                                    meta, b64str = img_url.split(',', 1)
                                    mime = meta.split(';')[0].split(':')[1] if ';' in meta else 'image/png'
                                    if 'png' in mime:
                                        ext = '.png'
                                    elif 'jpeg' in mime or 'jpg' in mime:
                                        ext = '.jpg'
                                    img_bytes = base64.b64decode(b64str)
                                except Exception as e:
                                    print(f"Debug: Failed to decode data URL image: {e}")
                                    img_bytes = None
                            elif b64data:
                                try:
                                    img_bytes = base64.b64decode(b64data)
                                except Exception as e:
                                    print(f"Debug: Failed to decode b64 image: {e}")
                                    img_bytes = None
                            elif img_url and img_url.startswith('http'):
                                try:
                                    r = requests.get(img_url, timeout=30)
                                    fetched_url = getattr(r, 'url', img_url)
                                    resp_content_type = r.headers.get('Content-Type', '')
                                    resp_content_len = int(r.headers.get('Content-Length')) if r.headers.get('Content-Length') else len(r.content)
                                    if r.status_code == 200:
                                        img_bytes = r.content
                                        # try to infer extension
                                        ctype = resp_content_type
                                        if 'png' in ctype:
                                            ext = '.png'
                                        elif 'jpeg' in ctype or 'jpg' in ctype:
                                            ext = '.jpg'
                                        print(f"Debug: Fetched image URL: {fetched_url}, content-type={resp_content_type}, content-length={resp_content_len}")
                                except Exception as e:
                                    print(f"Debug: Failed to fetch image url: {e}")
                                    img_bytes = None

                            if not img_bytes:
                                print(f"Debug: No image bytes for image {i}")
                                continue

                            safe_prompt = "".join(c for c in prompt_text if c.isalnum() or c in (' ', '-', '_')).rstrip()[:50]
                            filename = f"{safe_prompt}_or_{i:03d}{ext}"
                            filepath = os.path.join(output_folder, filename)
                            with open(filepath, 'wb') as out_f:
                                out_f.write(img_bytes)

                            # Post-save verification: ensure file exists and has content
                            try:
                                if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                                    print(f"Debug: Error: file '{filepath}' missing or zero bytes after write")
                                    continue

                                # Try to inspect image dimensions when Pillow is available
                                try:
                                    from PIL import Image
                                    with Image.open(filepath) as im:
                                        actual_w, actual_h = im.size
                                    filesize = os.path.getsize(filepath)
                                    print(f"Debug: Saved OpenRouter image to: {filepath} ({actual_w}x{actual_h}, {filesize} bytes)")

                                    # If we requested a specific resolution, compare actual vs requested
                                    req_res = image_cfg.get('resolution') if isinstance(image_cfg, dict) else None
                                    if req_res:
                                        req_w, req_h = _parse_resolution(req_res)
                                        if req_w and req_h and (actual_w != req_w or actual_h != req_h):
                                            print(f"Debug: Warning: actual image size {actual_w}x{actual_h} differs from requested {req_w}x{req_h}")

                                    # Append metadata for returned image (include fetch info and any claimed metadata)
                                    saved_images.append(filepath)
                                    saved_images_meta.append({'path': filepath, 'width': actual_w, 'height': actual_h, 'bytes': filesize, 'fetched_url': fetched_url, 'response_content_length': resp_content_len, 'response_content_type': resp_content_type, 'claimed_width': meta_w, 'claimed_height': meta_h})
                                    # If the server claimed larger dimensions but returned smaller image, note it
                                    if meta_w and meta_h and (actual_w != int(meta_w) or actual_h != int(meta_h)):
                                        msg = f"OpenRouter claimed {meta_w}x{meta_h} but fetched image is {actual_w}x{actual_h} (likely a preview)."
                                        print(f"Debug: {msg}")
                                        warnings.append(msg)
                                    images_generated += 1

                                except ImportError:
                                    # Pillow not available; at least report file size
                                    filesize = os.path.getsize(filepath)
                                    print(f"Debug: Saved OpenRouter image to: {filepath} (size={filesize} bytes) - Pillow not installed for dimension check")
                                    saved_images.append(filepath)
                                    saved_images_meta.append({'path': filepath, 'width': None, 'height': None, 'bytes': filesize, 'fetched_url': fetched_url, 'response_content_length': resp_content_len, 'response_content_type': resp_content_type, 'claimed_width': meta_w, 'claimed_height': meta_h})
                                    images_generated += 1
                                except Exception as e:
                                    print(f"Debug: Error inspecting saved image {filepath}: {e}")
                                    # still include the file path if present
                                    try:
                                        filesize = os.path.getsize(filepath)
                                    except Exception:
                                        filesize = None
                                    saved_images.append(filepath)
                                    saved_images_meta.append({'path': filepath, 'width': None, 'height': None, 'bytes': filesize, 'fetched_url': fetched_url, 'response_content_length': resp_content_len, 'response_content_type': resp_content_type})
                                    images_generated += 1

                            except Exception as e:
                                print(f"Debug: Post-save verification failed for {filepath}: {e}")
                                continue

                        except Exception as e:
                            print(f"Debug: Error saving OpenRouter image {i}: {e}")
                            continue

                    status = 'success' if images_generated > 0 else 'error'
                    results.append({'prompt': prompt_text, 'status': status, 'images_generated': images_generated, 'saved_images': saved_images, 'saved_images_meta': saved_images_meta, 'requested_resolution': image_cfg.get('resolution') if isinstance(image_cfg, dict) else None, 'sent_message': sent_message, 'warnings': warnings, 'error': None if images_generated > 0 else 'No images saved'})

                except Exception as e:
                    error_msg = str(e)
                    print(f"Debug: OpenRouter request failed: {error_msg}")
                    results.append({'prompt': prompt_text, 'status': 'error', 'images_generated': 0, 'saved_images': [], 'error': error_msg})

                # Delay between prompts
                if idx < len(prompts):
                    delay_seconds = get_delay_interval()
                    if progress_callback:
                        progress_callback(f"Waiting {delay_seconds:.1f} seconds delay...")
                    time.sleep(delay_seconds)

            return results
                
        print(f"Debug: Completed all prompts. Total results: {len(results)}")
        return results
        
    except ImportError as e:
        error_msg = f'Google Generative AI library not installed. Install with: pip install google-generativeai. Error: {e}'
        print(f"Debug: Import error: {error_msg}")
        return [{'status': 'error', 'error': error_msg}]
    except Exception as e:
        error_msg = f'Generation failed: {str(e)}'
        print(f"Debug: General error: {error_msg}")
        return [{'status': 'error', 'error': error_msg}]


def validate_image_generation_params(prompts, api_key, service, model):
    """
    Validate parameters for image generation.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not prompts or len(prompts) == 0:
        return False, "No prompts provided"
    
    if not api_key or not api_key.strip():
        return False, "API key is required"
    
    if not service or not service.strip():
        return False, "AI service must be selected"
    
    if not model or not model.strip():
        return False, "Model must be selected"
    
    return True, None


def get_supported_image_services():
    """
    Get list of supported AI services for image generation.
    
    Returns:
        dict: Dictionary of service names and their capabilities
    """
    return {
        'openai': {
            'name': 'OpenAI DALL-E',
            'models': ['dall-e-3', 'dall-e-2'],
            'supported': True
        },
        'openrouter': {
            'name': 'OpenRouter (image-capable models)',
            'models': ['google/gemini-2.5-flash-image-preview', 'black-forest-labs/flux.2-pro', 'black-forest-labs/flux.2-flex', 'sourceful/riverflow-v2-standard-preview'],
            'supported': True
        },
        'google': {
            'name': 'Google Imagen',
            'models': ['imagen-3.0', 'imagen-2.0'],
            'supported': False  # Placeholder - will be implemented later
        },
        'stability': {
            'name': 'Stability AI',
            'models': ['stable-diffusion-3', 'stable-diffusion-xl'],
            'supported': False  # Placeholder - will be implemented later
        }
    }


def get_default_image_settings():
    """
    Get default settings for image generation.
    
    Returns:
        dict: Default settings
    """
    return {
        'size': '1024x1024',
        'quality': 'standard',
        'style': 'natural',
        'output_format': 'png',
        'save_location': os.path.join(BASE_PATH, 'temp', 'images')
    }