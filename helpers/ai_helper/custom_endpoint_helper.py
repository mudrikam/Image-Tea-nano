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
    def call_endpoint(api_key: str, endpoint: str, provider: str | None, model: str | None, prompt: str, image_path: str | None = None, timeout: int = 180) -> str:
        CustomEndpointHelper.validate_url(endpoint)
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        payload = None
        prov = (provider or "").lower()

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
                payload = {"model": model or "", "messages": [{"role": "user", "content": prompt}]}
                if image_path:
                    payload = {
                        "model": model or "",
                        "messages": [
                            {"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": data_url}}]}
                        ]
                    }
            else:
                payload = {"model": model or "", "input": prompt}
                if image_path:
                    payload = {
                        "model": model or "",
                        "messages": [
                            {"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": data_url}}]}
                        ]
                    }
        elif prov == "gemini":
            contents = [prompt]
            if image_path:
                contents = [data_url, prompt]
            payload = {"model": model or "", "contents": contents}
        elif prov == "groq":
            messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
            if image_path:
                messages[0]["content"].append({"type": "image_url", "image_url": {"url": data_url}})
            payload = {"model": model or "", "messages": messages}
        else:
            payloads_to_try = []

            chat_payload = {"model": model or "", "messages": [{"role": "user", "content": prompt}]}
            if image_path:
                chat_payload = {"model": model or "", "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": data_url}}]}]}
            payloads_to_try.append(("chat", chat_payload))

            responses_payload = {"model": model or "", "input": prompt}
            if image_path:
                responses_payload = {"model": model or "", "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": data_url}}]}]}
            payloads_to_try.append(("responses", responses_payload))

            completion_payload = {"model": model or "", "prompt": prompt}
            payloads_to_try.append(("completion", completion_payload))

            last_error = None
            for format_name, try_payload in payloads_to_try:
                try:
                    resp = requests.post(endpoint, headers=headers, json=try_payload, timeout=timeout)
                    if resp.status_code < 400:
                        try:
                            j = resp.json()
                            return CustomEndpointHelper._extract_text_from_response(j)
                        except Exception:
                            return resp.text or ""
                    else:
                        body = resp.text or ""
                        if "unsupported" in body.lower() or "missing" in body.lower():
                            last_error = f"Format {format_name} failed: {body}"
                            continue
                        else:
                            raise RuntimeError(f"Custom endpoint returned status {resp.status_code}: {body}")
                except RuntimeError:
                    raise
                except Exception as e:
                    last_error = str(e)
                    continue

            raise RuntimeError(f"All payload formats failed. Last error: {last_error}")

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
