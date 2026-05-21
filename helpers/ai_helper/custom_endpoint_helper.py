import json
import base64
import os
import mimetypes
import requests
from urllib.parse import urlparse


class CustomEndpointHelper:
    """Helper for calling arbitrary AI HTTP endpoints: validate URLs, build payloads,
    encode images, and extract text from common response formats."""

    @staticmethod
    def normalize_endpoint(url: str) -> str:
        """
        Normalize endpoint URL to support both v1 and v1/chat/completions formats.
        If user provides base URL ending with /v1, automatically append /chat/completions.
        
        Examples:
            https://api.example.com/v1 -> https://api.example.com/v1/chat/completions
            https://api.example.com/v1/ -> https://api.example.com/v1/chat/completions
            https://api.example.com/v1/chat/completions -> https://api.example.com/v1/chat/completions (unchanged)
        """
        if not url:
            return url
        
        url = url.rstrip('/')
        url_lower = url.lower()
        
        # If already ends with /chat/completions or /completions, return as-is
        if url_lower.endswith('/chat/completions') or url_lower.endswith('/completions'):
            return url
        
        # If ends with /v1, append /chat/completions
        if url_lower.endswith('/v1'):
            return f"{url}/chat/completions"
        
        # If ends with /api/v1, append /chat/completions
        if url_lower.endswith('/api/v1'):
            return f"{url}/chat/completions"
        
        # Otherwise return as-is (might be a custom path)
        return url

    @staticmethod
    def validate_url(url: str) -> None:
        p = urlparse(url or "")
        if p.scheme not in ("http", "https") or not p.netloc:
            raise ValueError(f"Invalid endpoint URL: {url}")

    @staticmethod
    def _image_path_to_data_url(path: str) -> str:
        if not path or not os.path.exists(path):
            raise ValueError("Image path not found for data URL conversion")
        try:
            from PIL import Image
            import io
            img = Image.open(path)
            # Convert to RGB (required for JPEG)
            if img.mode in ('RGBA', 'LA', 'P'):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = bg
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            # Resize large images to reduce token count (max dimension 1024px)
            max_dim = 1024
            w, h = img.size
            if max(w, h) > max_dim:
                scale = max_dim / max(w, h)
                new_size = (int(w * scale), int(h * scale))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            # Encode as JPEG with good compression
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=85, optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode('ascii')
            return f"data:image/jpeg;base64,{b64}"
        except ImportError:
            # Pillow not available, fall back to original (uncompressed)
            mime, _ = mimetypes.guess_type(path)
            if not mime:
                mime = "application/octet-stream"
            with open(path, "rb") as f:
                b = f.read()
            b64 = base64.b64encode(b).decode("ascii")
            return f"data:{mime};base64,{b64}"
        except Exception as e:
            print(f"[CustomEndpointHelper] Image processing failed, using original: {e}")
            mime, _ = mimetypes.guess_type(path)
            if not mime:
                mime = "application/octet-stream"
            with open(path, "rb") as f:
                b = f.read()
            b64 = base64.b64encode(b).decode("ascii")
            return f"data:{mime};base64,{b64}"

    @staticmethod
    def _extract_text_from_response(resp_json: dict) -> str:
        if isinstance(resp_json, dict):
            out = resp_json.get("output")
            if isinstance(out, list) and out:
                first = out[0]
                if isinstance(first, dict):
                    if "content" in first and isinstance(first["content"], list):
                        for part in first["content"]:
                            if isinstance(part, dict) and part.get("type") == "output_text":
                                return part.get("text", "")
                    return first.get("text") or str(first)
                return str(first)

            choices = resp_json.get("choices")
            if isinstance(choices, list) and choices:
                c0 = choices[0]
                if isinstance(c0, dict):
                    if "message" in c0 and isinstance(c0["message"], dict):
                        return c0["message"].get("content") or c0.get("text") or str(c0["message"])
                    return c0.get("text") or str(c0)

            candidates = resp_json.get("candidates")
            if isinstance(candidates, list) and candidates:
                cand = candidates[0]
                if isinstance(cand, dict):
                    content = cand.get("content")
                    if isinstance(content, dict):
                        for v in ("text", "output_text", "string"):
                            if v in content:
                                return content[v]
                    return cand.get("content") or cand.get("display") or str(cand)

            if "text" in resp_json:
                return resp_json.get("text")
        return json.dumps(resp_json) 

    @staticmethod
    def _build_multi_frame_content(prompt: str, frame_paths: list) -> list:
        content_items = [{"type": "text", "text": prompt}]
        for fp in frame_paths:
            frame_url = CustomEndpointHelper._image_path_to_data_url(fp)
            content_items.append({"type": "image_url", "image_url": {"url": frame_url}})
        return content_items



    @staticmethod
    def _extract_usage_from_response(resp_json: dict) -> tuple:
        if not isinstance(resp_json, dict):
            return 0, 0, 0
        usage = resp_json.get("usage")
        if isinstance(usage, dict):
            token_input = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
            token_output = usage.get("completion_tokens") or usage.get("output_tokens") or 0
            token_total = usage.get("total_tokens") or (token_input + token_output)
            return token_input, token_output, token_total
        return 0, 0, 0

    @staticmethod
    def call_endpoint_with_usage(api_key: str, endpoint: str, provider: str | None, model: str | None, prompt: str, image_path: str | None = None, timeout: int = 180, frame_paths: list | None = None) -> tuple:
        """Same as call_endpoint but returns (text, token_input, token_output, token_total)."""
        # Normalize endpoint URL
        endpoint = CustomEndpointHelper.normalize_endpoint(endpoint)
        CustomEndpointHelper.validate_url(endpoint)
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        prov = (provider or "").lower()
        payload = None

        if image_path:
            data_url = CustomEndpointHelper._image_path_to_data_url(image_path)

        if prov in ("openai", "openrouter", "blackbox", "maia"):
            use_chat_messages = False
            try:
                ep = (endpoint or "").lower()
                if ep.rstrip('/').endswith('/chat/completions') or ep.rstrip('/').endswith('/v1/chat/completions'):
                    use_chat_messages = True
            except Exception:
                use_chat_messages = False

            if use_chat_messages or not use_chat_messages:
                if frame_paths:
                    content_items = CustomEndpointHelper._build_multi_frame_content(prompt, frame_paths)
                    payload = {"model": model or "", "messages": [{"role": "user", "content": content_items}]}
                elif image_path:
                    payload = {"model": model or "", "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": data_url}}]}]}
                else:
                    payload = {"model": model or "", "messages": [{"role": "user", "content": prompt}]}
        elif prov == "gemini":
            contents = [prompt]
            if frame_paths:
                contents = [CustomEndpointHelper._image_path_to_data_url(fp) for fp in frame_paths] + [prompt]
            elif image_path:
                contents = [data_url, prompt]
            payload = {"model": model or "", "contents": contents}
        elif prov == "groq":
            messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
            if frame_paths:
                for fp in frame_paths:
                    messages[0]["content"].append({"type": "image_url", "image_url": {"url": CustomEndpointHelper._image_path_to_data_url(fp)}})
            elif image_path:
                messages[0]["content"].append({"type": "image_url", "image_url": {"url": data_url}})
            payload = {"model": model or "", "messages": messages}
        else:
            if frame_paths:
                content_items = CustomEndpointHelper._build_multi_frame_content(prompt, frame_paths)
                payload = {"model": model or "", "messages": [{"role": "user", "content": content_items}]}
            elif image_path:
                payload = {"model": model or "", "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": data_url}}]}]}
            else:
                payload = {"model": model or "", "messages": [{"role": "user", "content": prompt}]}

        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
        except Exception as e:
            raise RuntimeError(f"Request to custom endpoint failed: {e}")

        if resp.status_code >= 400:
            body = resp.text or "<no body>"
            raise RuntimeError(f"Custom endpoint returned status {resp.status_code}: {body}")

        try:
            j = resp.json()
            text = CustomEndpointHelper._extract_text_from_response(j)
            token_input, token_output, token_total = CustomEndpointHelper._extract_usage_from_response(j)
            return text, token_input, token_output, token_total
        except Exception:
            return resp.text or "", 0, 0, 0

    @staticmethod
    def call_endpoint(api_key: str, endpoint: str, provider: str | None, model: str, prompt: str, image_path: str | None = None, frame_paths: list | None = None, timeout: int = 30) -> str:
        # Normalize endpoint URL
        endpoint = CustomEndpointHelper.normalize_endpoint(endpoint)
        CustomEndpointHelper.validate_url(endpoint)
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        payload = None
        prov = (provider or "").lower()

        data_url = None
        if image_path:
            data_url = CustomEndpointHelper._image_path_to_data_url(image_path)

        if prov in ("openai", "openrouter", "blackbox", "maia"):
            use_chat_messages = False
            try:
                ep = (endpoint or "").lower()
                if ep.rstrip('/').endswith('/chat/completions') or ep.rstrip('/').endswith('/v1/chat/completions'):
                    use_chat_messages = True
            except Exception:
                use_chat_messages = False

            if use_chat_messages:
                if frame_paths:
                    content_items = CustomEndpointHelper._build_multi_frame_content(prompt, frame_paths)
                    payload = {"model": model or "", "messages": [{"role": "user", "content": content_items}]}
                elif image_path:
                    payload = {
                        "model": model or "",
                        "messages": [
                            {"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": data_url}}]}
                        ]
                    }
                else:
                    payload = {"model": model or "", "messages": [{"role": "user", "content": prompt}]}
            else:
                if frame_paths:
                    content_items = CustomEndpointHelper._build_multi_frame_content(prompt, frame_paths)
                    payload = {"model": model or "", "messages": [{"role": "user", "content": content_items}]}
                elif image_path:
                    payload = {
                        "model": model or "",
                        "messages": [
                            {"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": data_url}}]}
                        ]
                    }
                else:
                    payload = {"model": model or "", "input": prompt}
        elif prov == "gemini":
            contents = [prompt]
            if frame_paths:
                contents = [CustomEndpointHelper._image_path_to_data_url(fp) for fp in frame_paths] + [prompt]
            elif image_path:
                contents = [data_url, prompt]
            payload = {"model": model or "", "contents": contents}
        elif prov == "groq":
            messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
            if frame_paths:
                for fp in frame_paths:
                    messages[0]["content"].append({"type": "image_url", "image_url": {"url": CustomEndpointHelper._image_path_to_data_url(fp)}})
            elif image_path:
                messages[0]["content"].append({"type": "image_url", "image_url": {"url": data_url}})
            payload = {"model": model or "", "messages": messages}
        else:
            # For unknown providers (including "custom"), determine format from endpoint URL.
            # Default to chat completions (messages) for modern OpenAI-compatible APIs.
            ep_low = (endpoint or "").lower().rstrip('/')
            is_chat_endpoint = ep_low.endswith('/chat/completions') or ep_low.endswith('/v1/chat/completions')
            if is_chat_endpoint:
                if frame_paths:
                    content_items = CustomEndpointHelper._build_multi_frame_content(prompt, frame_paths)
                    messages = [{"role": "user", "content": content_items}]
                elif image_path:
                    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": data_url}}]}]
                else:
                    messages = [{"role": "user", "content": prompt}]
                payload = {"model": model or "", "messages": messages}
            else:
                # Legacy completions-style endpoint (uses 'prompt' or 'input')
                if frame_paths or image_path:
                    raise ValueError("Image uploads not supported for completions-style endpoints")
                payload = {"model": model or "", "prompt": prompt}

        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
        except Exception as e:
            raise RuntimeError(f"Request to custom endpoint failed: {e}")

        if resp.status_code >= 400:
            body = resp.text or "<no body>"
            raise RuntimeError(f"Custom endpoint returned status {resp.status_code}: {body}")

        try:
            j = resp.json()
            return CustomEndpointHelper._extract_text_from_response(j)
        except Exception:
            return resp.text or ""

    @staticmethod
    def test_connectivity(api_key: str, endpoint: str, provider: str | None = None, model: str | None = None, timeout: int = 30) -> tuple[bool, str]:
        """Simple connectivity + sanity test. Returns (ok, message_or_response)."""
        # Normalize endpoint URL
        endpoint = CustomEndpointHelper.normalize_endpoint(endpoint)
        try:
            CustomEndpointHelper.validate_url(endpoint)
        except Exception as e:
            return False, str(e)
        try:
            # Use longer timeout for localhost endpoints
            ep_low = endpoint.lower()
            is_local = '127.0.0.1' in ep_low or 'localhost' in ep_low or ep_low.startswith('http://localhost')
            local_timeout = 120 if is_local else timeout
            txt = CustomEndpointHelper.call_endpoint(api_key, endpoint, provider, model or "", "Just say OK.", None, timeout=local_timeout)
            ok = bool(txt and ("ok" in txt.lower() or len(txt.strip()) > 0))
            return ok, txt
        except Exception as e:
            return False, str(e)
