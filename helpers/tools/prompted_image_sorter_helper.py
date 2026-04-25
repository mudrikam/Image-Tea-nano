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
            return None, None

    except Exception as e:
        print(f"[ImageSorterHelper] Classification error: {e}")
        return None, None


def _call_openai(client, model: str, image_path: str, system_prompt: str, valid_folders: list) -> Tuple[Optional[str], str]:
    """Call OpenAI/OpenRouter API with original image (no compression)."""
    try:
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
            max_tokens=100,
            temperature=0.2
        )
        text = response.choices[0].message.content if response.choices else ""
        return _parse_response(text, valid_folders)
    except Exception as e:
        print(f"[ImageSorterHelper] OpenAI call error: {e}")
        return None, None


def _call_gemini(api_key: str, model: str, image_path: str, system_prompt: str, valid_folders: list) -> Tuple[Optional[str], str]:
    """Call Gemini API with original image (no compression)."""
    try:
        import google.genai as genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        with open(image_path, 'rb') as f:
            image_bytes = f.read()

        ext = os.path.splitext(image_path)[1].lower()
        mime_type = 'image/jpeg' if ext in ['.jpg', '.jpeg'] else 'image/png' if ext == '.png' else 'image/jpeg'

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
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
    """Call OpenAI-compatible API (Groq, Blackbox, Maia) with original image (no compression)."""
    try:
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
