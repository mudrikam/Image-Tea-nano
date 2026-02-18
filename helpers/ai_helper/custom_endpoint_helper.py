import json
import base64
import os
import mimetypes
import requests
from urllib.parse import urlparse


class CustomEndpointHelper:
    """Universal helper to call arbitrary AI HTTP endpoints.

    - Validates endpoint URL
    - Builds common request payloads for OpenAI-compatible, Gemini-like, and Groq-like endpoints
    - Encodes image files as data URLs when an image path is provided
    - Parses common response shapes and returns the response text

    NOTE: This helper performs *connectivity and request formation*. It does not
    attempt to perfectly emulate every provider SDK – it targets common, OpenAI-
    compatible and GenAI-compatible JSON formats that many routers/bridge services
    expose.
    """

    @staticmethod
    def validate_url(url: str) -> None:
        p = urlparse(url or "")
        if p.scheme not in ("http", "https") or not p.netloc:
            raise ValueError(f"Invalid endpoint URL: {url}")

    @staticmethod
    def _image_path_to_data_url(path: str) -> str:
        if not path or not os.path.exists(path):
            raise ValueError("Image path not found for data URL conversion")
        mime, _ = mimetypes.guess_type(path)
        if not mime:
            mime = "application/octet-stream"
        with open(path, "rb") as f:
            b = f.read()
        b64 = base64.b64encode(b).decode("ascii")
        return f"data:{mime};base64,{b64}"

    @staticmethod
    def _extract_text_from_response(resp_json: dict) -> str:
        # OpenAI Responses API (output / choices)
        if isinstance(resp_json, dict):
            # new Responses API
            out = resp_json.get("output")
            if isinstance(out, list) and out:
                # try to find text in the first output
                first = out[0]
                if isinstance(first, dict):
                    if "content" in first and isinstance(first["content"], list):
                        # look for a text part
                        for part in first["content"]:
                            if isinstance(part, dict) and part.get("type") == "output_text":
                                return part.get("text", "")
                    # fallback to 'text' or 'string' keys
                    return first.get("text") or str(first)
                return str(first)
            # OpenAI "choices" legacy
            choices = resp_json.get("choices")
            if isinstance(choices, list) and choices:
                c0 = choices[0]
                if isinstance(c0, dict):
                    if "message" in c0 and isinstance(c0["message"], dict):
                        return c0["message"].get("content") or c0.get("text") or str(c0["message"])
                    return c0.get("text") or str(c0)
            # Google GenAI style
            candidates = resp_json.get("candidates")
            if isinstance(candidates, list) and candidates:
                cand = candidates[0]
                if isinstance(cand, dict):
                    # genai candidate
                    content = cand.get("content")
                    if isinstance(content, dict):
                        # try to find text inside
                        for v in ("text", "output_text", "string"):
                            if v in content:
                                return content[v]
                    return cand.get("content") or cand.get("display") or str(cand)
            # Fallback: attempt to stringify
            if "text" in resp_json:
                return resp_json.get("text")
        # Last resort
        return json.dumps(resp_json)

    @staticmethod
    def call_endpoint(api_key: str, endpoint: str, provider: str | None, model: str | None, prompt: str, image_path: str | None = None, timeout: int = 10) -> str:
        CustomEndpointHelper.validate_url(endpoint)
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        # Build payloads for common formats
        payload = None
        prov = (provider or "").lower()

        if image_path:
            # embed image as data URL inside messages/content
            data_url = CustomEndpointHelper._image_path_to_data_url(image_path)

        if prov in ("openai", "openrouter", "blackbox", "maia"):
            # OpenAI "Responses" style preferred
            payload = {"model": model or "", "input": prompt}
            # if image included, provide a message-like structure with image_url
            if image_path:
                payload = {
                    "model": model or "", 
                    "messages": [
                        {"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": data_url}}]}
                    ]
                }
        elif prov == "gemini":
            # Gemini/GenAI-like payload
            contents = [prompt]
            if image_path:
                # include data_url as an image_url type inside a single text field (many routers accept it)
                contents = [data_url, prompt]
            payload = {"model": model or "", "contents": contents}
        elif prov == "groq":
            # Groq typical chat format
            messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
            if image_path:
                messages[0]["content"].append({"type": "image_url", "image_url": {"url": data_url}})
            payload = {"model": model or "", "messages": messages}
        else:
            # Generic: try OpenAI-compatible 'model'/'input' payload with optional image as data URL
            payload = {"model": model or "", "input": prompt}
            if image_path:
                payload = {"model": model or "", "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": data_url}}]}]}

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
            # Not JSON or cannot parse; return raw text
            return resp.text or ""

    @staticmethod
    def test_connectivity(api_key: str, endpoint: str, provider: str | None = None, model: str | None = None, timeout: int = 8) -> tuple[bool, str]:
        """Simple connectivity + sanity test. Returns (ok, message_or_response)."""
        try:
            CustomEndpointHelper.validate_url(endpoint)
        except Exception as e:
            return False, str(e)
        try:
            txt = CustomEndpointHelper.call_endpoint(api_key, endpoint, provider, model or "", "Just say OK.", None, timeout=timeout)
            ok = bool(txt and ("ok" in txt.lower() or len(txt.strip()) > 0))
            return ok, txt
        except Exception as e:
            return False, str(e)
