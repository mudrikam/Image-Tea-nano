import os
import json
import base64
import re
import io
from typing import Optional, Tuple, Dict, Any
from config import BASE_PATH

MAX_DIM = 500
COMPRESS_QUALITY = 80


def _prepare_image(image_path: str) -> Optional[bytes]:
    """
    Resize image so largest dimension is MAX_DIM, then compress to COMPRESS_QUALITY%.
    Returns JPEG bytes ready for base64 encoding.
    """
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            # Convert to RGB if needed
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            # Resize maintaining aspect ratio
            w, h = img.size
            if max(w, h) > MAX_DIM:
                ratio = MAX_DIM / max(w, h)
                img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
            # Compress to JPEG
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=COMPRESS_QUALITY, optimize=True)
            return buf.getvalue()
    except Exception as e:
        print(f"[ImageSorterHelper] Image prepare error: {e}")
        return None


def classify_image(
    image_path: str,
    api_key: str,
    service: str,
    model: str,
    system_prompt: str,
    valid_folders: list = None,
    provider_endpoint: Optional[str] = None,
    db=None
) -> Optional[str]:
    """
    Classify a single image using the specified AI service.
    Returns the folder name determined by AI, or None on failure.

    Args:
        image_path: Path to compressed image
        api_key: API key for the service
        service: Service name (openai, gemini, groq, blackbox, maia, openrouter, custom)
        model: Model name
        system_prompt: Full system prompt to send
        valid_folders: List of folder dicts for validation
        provider_endpoint: Custom endpoint URL (if stored in DB)
        db: Database instance for looking up provider_endpoint if not provided

    Returns:
        Folder name string or None
    """
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
                text = CustomEndpointHelper.call_endpoint(
                    api_key=api_key,
                    endpoint=provider_endpoint,
                    provider=service,
                    model=model,
                    prompt=system_prompt,
                    image_path=image_path,
                    timeout=60
                )
                return _parse_response(text, valid_folders)
            except Exception as e:
                print(f"[ImageSorterHelper] Custom endpoint error: {e}")
                # Fall through to standard handlers

        # Standard service handlers
        service_lower = service.lower()

        if service_lower == 'openai' or service_lower == 'openrouter':
            from helpers.ai_helper.openai_helper import create_openai_client
            client = create_openai_client(api_key)
            return _call_openai(client, model, image_path, system_prompt, valid_folders)

        elif service_lower == 'gemini':
            return _call_gemini(api_key, model, image_path, system_prompt, valid_folders)

        elif service_lower == 'groq':
            from groq import Groq
            client = Groq(api_key=api_key)
            return _call_openai_compatible(client, model, image_path, system_prompt, valid_folders)

        elif service_lower == 'blackbox':
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url="https://api.blackbox.ai")
            return _call_openai_compatible(client, model, image_path, system_prompt, valid_folders)

        elif service_lower == 'maia':
            from helpers.ai_helper.maia_helper import create_maia_client
            client = create_maia_client(api_key)
            return _call_openai_compatible(client, model, image_path, system_prompt, valid_folders)

        else:
            print(f"[ImageSorterHelper] Unknown service: {service}")
            return None

    except Exception as e:
        print(f"[ImageSorterHelper] Classification error: {e}")
        return None


def _call_openai(client, model: str, image_path: str, system_prompt: str, valid_folders: list) -> Optional[str]:
    """Call OpenAI/OpenRouter API with resized+compressed image."""
    try:
        image_bytes = _prepare_image(image_path)
        if not image_bytes:
            return None
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
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
            max_tokens=100,
            temperature=0.2
        )
        text = response.choices[0].message.content if response.choices else ""
        return _parse_response(text, valid_folders)
    except Exception as e:
        print(f"[ImageSorterHelper] OpenAI call error: {e}")
        return None


def _call_gemini(api_key: str, model: str, image_path: str, system_prompt: str, valid_folders: list) -> Optional[str]:
    """Call Gemini API with resized+compressed image."""
    try:
        import google.genai as genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        image_bytes = _prepare_image(image_path)
        if not image_bytes:
            return None

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
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
        return None


def _call_openai_compatible(client, model: str, image_path: str, system_prompt: str, valid_folders: list) -> Optional[str]:
    """Call OpenAI-compatible API (Groq, Blackbox, Maia) with resized+compressed image."""
    try:
        image_bytes = _prepare_image(image_path)
        if not image_bytes:
            return None
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
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
            max_tokens=100,
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
        return None


def _parse_response(response_text: str, valid_folders: list = None) -> Optional[str]:
    """
    Parse AI response to extract folder name.
    Tries JSON first, then regex fallback. Validates against valid_folders if provided.
    Uses fuzzy matching for folder names (case-insensitive, trimmed).
    """
    if not response_text:
        print("[ImageSorterHelper] _parse_response: empty response")
        return None
    text = response_text.strip()
    
    print(f"[ImageSorterHelper] Raw response: {text[:200]}...")  # Debug
    
    # Remove markdown code blocks
    text = re.sub(r'^```json\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^```\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text, flags=re.IGNORECASE)
    text = text.strip()
    
    extracted_folder = None
    
    try:
        data = json.loads(text)
        folder = data.get('folder', '')
        print(f"[ImageSorterHelper] JSON parsed, folder: '{folder}'")
        extracted_folder = folder
    except json.JSONDecodeError:
        # Regex fallback
        patterns = [
            r'"folder"\s*:\s*"([^"]+)"',
            r'folder["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            r'"folder"\s*:\s*([a-zA-Z0-9_\s\-/\\]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted_folder = match.group(1).strip()
                print(f"[ImageSorterHelper] Regex matched, folder: '{extracted_folder}'")
                break
    
    # Validate against valid_folders with fuzzy matching
    if extracted_folder and valid_folders:
        folder_lower = extracted_folder.lower().strip()
        for f in valid_folders:
            valid_lower = f['folder_name'].lower().strip()
            # Exact match
            if folder_lower == valid_lower:
                print(f"[ImageSorterHelper] Exact match found: '{f['folder_name']}'")
                return f['folder_name']
            # Partial match (folder name is contained in response or vice versa)
            if folder_lower in valid_lower or valid_lower in folder_lower:
                print(f"[ImageSorterHelper] Partial match found: '{f['folder_name']}'")
                return f['folder_name']
        print(f"[ImageSorterHelper] No valid folder match for: '{extracted_folder}'")
        return None
    elif extracted_folder:
        return extracted_folder
    
    print("[ImageSorterHelper] No folder extracted from response")
    return None
