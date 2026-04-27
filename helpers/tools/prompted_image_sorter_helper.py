import os
import json
import base64
import re
from typing import Optional, Tuple, Dict, Any
from config import BASE_PATH


def classify_image(
    image_path: str,
    api_key: str,
    service: str,
    model: str,
    system_prompt: str,
    valid_folders: list = None,
    provider_endpoint: Optional[str] = None,
    db=None
) -> Tuple[Optional[str], str]:
    """
    Classify a single image using the specified AI service.
    Returns (folder_name, reason) tuple. Folder is None on failure; reason may be empty string.
    """
    max_retries = 3
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            # Resolve provider_endpoint from DB if not provided
            if not provider_endpoint and db:
                try:
                    rows = db.get_all_api_keys()
                    for r in rows:
                        if len(r) >= 2 and r[1] == api_key and str(r[0]).lower() == service.lower():
                            provider_endpoint = r[6] if len(r) > 6 else None
                            break
                except Exception as e:
                    print(f"[ImageSorterHelper] Failed to resolve provider_endpoint: {e}")

            # Try custom endpoint first (like prompt_generator does)
            if provider_endpoint:
                try:
                    from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
                    # Use longer timeout for localhost + retry
                    ep_low = provider_endpoint.lower()
                    is_local = '127.0.0.1' in ep_low or 'localhost' in ep_low
                    timeout = 120 if is_local else 60
                    text = CustomEndpointHelper.call_endpoint(
                        api_key=api_key,
                        endpoint=provider_endpoint,
                        provider=service,
                        model=model,
                        prompt=system_prompt,
                        image_path=image_path,
                        timeout=timeout
                    )
                    result = _parse_response(text, valid_folders)
                    if result[0] is not None:
                        return result
                    # If parse failed, treat as error for retry
                    raise ValueError("Failed to parse AI response")
                except Exception as e:
                    print(f"[ImageSorterHelper] Custom endpoint attempt {attempt}/{max_retries} error: {e}")
                    last_error = e
                    if attempt < max_retries:
                        import time
                        time.sleep(min(5 * attempt, 15))  # exponential backoff: 5s, 10s, 15s
                    continue  # retry

            # Standard service handlers
            service_lower = service.lower()

            if service_lower in ('openai', 'openrouter'):
                from helpers.ai_helper.openai_helper import create_openai_client
                client = create_openai_client(api_key)
                result = _call_openai(client, model, image_path, system_prompt, valid_folders)
                if result[0] is not None:
                    return result
                raise ValueError("OpenAI classification failed")

            elif service_lower == 'gemini':
                result = _call_gemini(api_key, model, image_path, system_prompt, valid_folders)
                if result[0] is not None:
                    return result
                raise ValueError("Gemini classification failed")

            elif service_lower == 'groq':
                from groq import Groq
                client = Groq(api_key=api_key)
                result = _call_openai_compatible(client, model, image_path, system_prompt, valid_folders)
                if result[0] is not None:
                    return result
                raise ValueError("Groq classification failed")

            elif service_lower == 'blackbox':
                from openai import OpenAI
                client = OpenAI(api_key=api_key, base_url="https://api.blackbox.ai")
                result = _call_openai_compatible(client, model, image_path, system_prompt, valid_folders)
                if result[0] is not None:
                    return result
                raise ValueError("Blackbox classification failed")

            elif service_lower == 'maia':
                from helpers.ai_helper.maia_helper import create_maia_client
                client = create_maia_client(api_key)
                result = _call_openai_compatible(client, model, image_path, system_prompt, valid_folders)
                if result[0] is not None:
                    return result
                raise ValueError("Maia classification failed")

            else:
                print(f"[ImageSorterHelper] Unknown service: {service}")
                return None, None

        except Exception as e:
            print(f"[ImageSorterHelper] Classification attempt {attempt}/{max_retries} error: {e}")
            last_error = e
            if attempt < max_retries:
                import time
                time.sleep(min(5 * attempt, 15))
            continue

    print(f"[ImageSorterHelper] All {max_retries} attempts failed. Last error: {last_error}")
    return None, None


def _call_openai(client, model: str, image_path: str, system_prompt: str, valid_folders: list) -> Tuple[Optional[str], str]:
    """Call OpenAI/OpenRouter API with compressed image to reduce token usage."""
    try:
        try:
            import io
            from PIL import Image
            # Compress large images
            img = Image.open(image_path)
            max_dim = 1024
            w, h = img.size
            if max(w, h) > max_dim:
                scale = max_dim / max(w, h)
                new_size = (int(w * scale), int(h * scale))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            if img.mode in ('RGBA', 'LA', 'P'):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = bg
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=85, optimize=True)
            image_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            image_data_url = f"data:image/jpeg;base64,{image_b64}"
        except ImportError:
            # Pillow not available, fall back to original image
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            ext = os.path.splitext(image_path)[1].lower()
            mime_type = 'image/jpeg' if ext in ['.jpg', '.jpeg'] else 'image/png' if ext == '.png' else 'image/jpeg'
            image_data_url = f"data:{mime_type};base64,{image_b64}"

        user_content = [
            {"type": "text", "text": "Analyze this image and classify it into one of the folders based on the criteria provided in the system instructions."},
            {"type": "image_url", "image_url": {"url": image_data_url}}
        ]

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            max_tokens=300,
            temperature=0.2
        )
        text = response.choices[0].message.content if response.choices else ""
        return _parse_response(text, valid_folders)
    except Exception as e:
        print(f"[ImageSorterHelper] OpenAI call error: {e}")
        return None, None


def _call_gemini(api_key: str, model: str, image_path: str, system_prompt: str, valid_folders: list) -> Tuple[Optional[str], str]:
    """Call Gemini API with compressed image."""
    try:
        import google.genai as genai
        from google.genai import types
        import io
        from PIL import Image

        client = genai.Client(api_key=api_key)

        # Compress/Resize image to reduce token usage
        img = Image.open(image_path)
        max_dim = 1024
        w, h = img.size
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            new_size = (int(w * scale), int(h * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        if img.mode in ('RGBA', 'LA', 'P'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=85, optimize=True)
        image_bytes = buf.getvalue()

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    types.Part(text=system_prompt)
                ]
            )
        ]

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=types.Part(text="You are an expert image classifier. Analyze each image carefully and classify it into exactly ONE folder based on the criteria provided.")
            )
        )

        text = None
        if hasattr(response, "candidates") and response.candidates:
            try:
                text = response.candidates[0].content.parts[0].text
            except Exception:
                text = str(response)
        elif hasattr(response, "text"):
            text = response.text
        else:
            text = str(response)

        return _parse_response(text, valid_folders)
    except Exception as e:
        print(f"[ImageSorterHelper] Gemini call error: {e}")
        return None, None


def _call_openai_compatible(client, model: str, image_path: str, system_prompt: str, valid_folders: list) -> Tuple[Optional[str], str]:
    """Call OpenAI-compatible API (Groq, Blackbox, Maia) with compressed image."""
    try:
        import io
        from PIL import Image
        img = Image.open(image_path)
        max_dim = max(img.size)
        if max_dim > 1024:
            scale = 1024 / max_dim
            new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        if img.mode in ('RGBA', 'LA', 'P'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=85, optimize=True)
        image_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        image_data_url = f"data:image/jpeg;base64,{image_b64}"

        user_content = [
            {"type": "text", "text": "Analyze this image and classify it into one of the folders based on the criteria provided in the system instructions."},
            {"type": "image_url", "image_url": {"url": image_data_url}}
        ]

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            max_tokens=300,
            temperature=0.2
        )

        text = None
        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message") and hasattr(choice.message, "content"):
                text = choice.message.content
        if not text:
            text = str(response)

        return _parse_response(text, valid_folders)
    except Exception as e:
        print(f"[ImageSorterHelper] API call error: {e}")
        return None, None


def _parse_response(response_text: str, valid_folders: list = None) -> Optional[Tuple[str, str]]:
    """
    Parse AI response to extract folder name and reason.
    Tries JSON first, then regex fallback. Validates against valid_folders if provided.
    Uses fuzzy matching for folder names (case-insensitive, trimmed).
    Returns tuple of (folder_name, reason) or (None, None) on failure.
    """
    if not response_text:
        print("[ImageSorterHelper] _parse_response: empty response")
        return None, None
    text = response_text.strip()
    
    print(f"[ImageSorterHelper] Raw response: {text[:200]}...")  # Debug
    
    # Remove markdown code blocks
    text = re.sub(r'^```json\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^```\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text, flags=re.IGNORECASE)
    text = text.strip()
    
    extracted_folder = None
    extracted_reason = None
    
    try:
        data = json.loads(text)
        folder = data.get('folder', '')
        reason = data.get('reason', '')
        print(f"[ImageSorterHelper] JSON parsed, folder: '{folder}', reason: '{reason}'")
        extracted_folder = folder
        extracted_reason = reason
    except json.JSONDecodeError:
        # Regex fallback for folder
        folder_patterns = [
            r'"folder"\s*:\s*"([^"]+)"',
            r'folder["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            r'"folder"\s*:\s*([a-zA-Z0-9_\s\-/\\]+)',
        ]
        for pattern in folder_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted_folder = match.group(1).strip()
                print(f"[ImageSorterHelper] Regex matched folder: '{extracted_folder}'")
                break
        # Try to extract reason as well
        reason_match = re.search(r'"reason"\s*:\s*"([^"]+)"', text)
        if reason_match:
            extracted_reason = reason_match.group(1).strip()
        else:
            extracted_reason = None
    
    # Validate against valid_folders with fuzzy matching
    if extracted_folder and valid_folders:
        folder_lower = extracted_folder.lower().strip()
        for f in valid_folders:
            valid_lower = f['folder_name'].lower().strip()
            # Exact match
            if folder_lower == valid_lower:
                print(f"[ImageSorterHelper] Exact match found: '{f['folder_name']}'")
                return f['folder_name'], extracted_reason or ""
            # Partial match (folder name is contained in response or vice versa)
            if folder_lower in valid_lower or valid_lower in folder_lower:
                print(f"[ImageSorterHelper] Partial match found: '{f['folder_name']}'")
                return f['folder_name'], extracted_reason or ""
        print(f"[ImageSorterHelper] No valid folder match for: '{extracted_folder}'")
        return None, None
    elif extracted_folder:
        return extracted_folder, extracted_reason or ""
    
    print("[ImageSorterHelper] No folder extracted from response")
    return None, None
