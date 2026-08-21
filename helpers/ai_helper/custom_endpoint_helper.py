import json
import base64
import os
import mimetypes
import re
import requests
from urllib.parse import urlparse
from config import BASE_PATH
from helpers.ai_helper.openai_stream_helper import content_to_text


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
                parts = []
                for item in out:
                    if not isinstance(item, dict):
                        continue
                    item_content = item.get("content")
                    if isinstance(item_content, list):
                        for part in item_content:
                            if isinstance(part, dict) and part.get("type") in ("output_text", "text"):
                                parts.append(content_to_text(part.get("text")))
                    else:
                        parts.append(content_to_text(item.get("text") or item.get("output_text")))
                if parts:
                    return "".join(parts)

            choices = resp_json.get("choices")
            if isinstance(choices, list) and choices:
                c0 = choices[0]
                if isinstance(c0, dict):
                    if "message" in c0 and isinstance(c0["message"], dict):
                        return content_to_text(c0["message"].get("content")) or content_to_text(c0.get("text"))
                    return content_to_text(c0.get("text"))

            candidates = resp_json.get("candidates")
            if isinstance(candidates, list) and candidates:
                cand = candidates[0]
                if isinstance(cand, dict):
                    content = cand.get("content")
                    if isinstance(content, dict):
                        for v in ("text", "output_text", "string"):
                            if v in content:
                                return content_to_text(content[v])
                    return content_to_text(cand.get("content") or cand.get("display"))

            if "text" in resp_json:
                return content_to_text(resp_json.get("text"))
            return content_to_text(resp_json.get("output_text"))
        return ""

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
    def _parse_openai_stream(response) -> tuple[str, tuple]:
        """Consume an OpenAI-compatible response, streamed or regular.

        Reasoning and answer content are deliberately accumulated separately.
        Some reasoning models emit all reasoning first and only then emit content;
        a reasoning event must therefore never terminate this loop.
        """
        content_parts = []
        usage = (0, 0, 0)
        saw_sse = False
        pending_data = []
        reasoning_events = 0
        reasoning_chars = 0
        content_events = 0
        content_chars = 0
        finish_reasons = []
        saw_done = False

        def process_payload(payload):
            nonlocal usage, saw_sse, reasoning_events, reasoning_chars
            nonlocal content_events, content_chars
            if not isinstance(payload, dict):
                return
            saw_sse = True
            payload_usage = CustomEndpointHelper._extract_usage_from_response(payload)
            if any(payload_usage):
                usage = payload_usage
            choices = payload.get("choices") or []
            choice = choices[0] if choices and isinstance(choices[0], dict) else {}
            delta = choice.get("delta") or {}
            if not isinstance(delta, dict):
                delta = {}

            reasoning = delta.get("reasoning")
            if reasoning is None:
                reasoning = delta.get("reasoning_content")
            if reasoning:
                reasoning_events += 1
                reasoning_chars += len(str(reasoning))

            content = delta.get("content")
            if content:
                content_text = content_to_text(content)
                content_parts.append(content_text)
                content_events += 1
                content_chars += len(content_text)

            if not delta:
                message = choice.get("message") or {}
                message_content = message.get("content") if isinstance(message, dict) else None
                if message_content:
                    content_parts.append(content_to_text(message_content))
                elif choice.get("text"):
                    content_parts.append(content_to_text(choice.get("text")))

            finish_reason = choice.get("finish_reason")
            if finish_reason is not None:
                if finish_reason not in finish_reasons:
                    finish_reasons.append(finish_reason)

            # Non-streaming OpenAI-compatible responses are also accepted.
            message = choice.get("message") or {}
            if isinstance(message, dict) and message.get("content") and delta:
                # Some servers include both delta and message in one event.
                # Delta is the canonical streamed value; avoid duplication.
                pass

        for raw_line in response.iter_lines(decode_unicode=True):
            if raw_line is None:
                continue
            line = raw_line.strip()
            if not line:
                if pending_data:
                    data = "\n".join(pending_data).strip()
                    pending_data = []
                    if data == "[DONE]":
                        saw_done = True
                        break
                    try:
                        process_payload(json.loads(data))
                    except json.JSONDecodeError:
                        print(f"[SSE] Ignoring non-JSON event: {data[:500]}")
                continue
            if line.startswith(":"):
                continue
            if line.startswith("data:"):
                data = line[5:].lstrip()
                if data == "[DONE]":
                    saw_done = True
                    break
                pending_data.append(data)
            elif not saw_sse and not pending_data:
                # A server may ignore stream=true and return one JSON document.
                pending_data.append(line)

        if pending_data:
            data = "\n".join(pending_data).strip()
            if data == "[DONE]":
                saw_done = True
            else:
                try:
                    process_payload(json.loads(data))
                except json.JSONDecodeError:
                    pass

        print(
            "[SSE] completed: "
            f"reasoning_events={reasoning_events}, reasoning_chars={reasoning_chars}, "
            f"content_events={content_events}, content_chars={content_chars}, "
            f"finish_reason={','.join(map(str, finish_reasons)) or 'none'}, "
            f"done={saw_done}"
        )
        return "".join(content_parts), usage

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
                    payload = {"model": model or "", "messages": [{"role": "user", "content": content_items}], "stream": True}
                elif image_path:
                    payload = {"model": model or "", "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": data_url}}]}], "stream": True}
                else:
                    payload = {"model": model or "", "messages": [{"role": "user", "content": prompt}], "stream": True}
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
                payload = {"model": model or "", "messages": [{"role": "user", "content": content_items}], "stream": True}
            elif image_path:
                payload = {"model": model or "", "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": data_url}}]}], "stream": True}
            else:
                payload = {"model": model or "", "messages": [{"role": "user", "content": prompt}], "stream": True}

        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout, stream=True)
        except Exception as e:
            raise RuntimeError(f"Request to custom endpoint failed: {e}")

        if resp.status_code >= 400:
            body = resp.text or "<no body>"
            raise RuntimeError(f"Custom endpoint returned status {resp.status_code}: {body}")

        try:
            # Cache the body before iterating. This supports both SSE and JSON
            # responses and allows a reliable fallback after iter_lines().
            raw_body = resp.content
            text, usage = CustomEndpointHelper._parse_openai_stream(resp)
            token_input, token_output, token_total = usage
            if not text:
                if raw_body:
                    try:
                        text = CustomEndpointHelper._extract_text_from_response(json.loads(raw_body.decode("utf-8")))
                    except Exception:
                        text = raw_body.decode("utf-8", errors="replace")
            return text, token_input, token_output, token_total
        except Exception as e:
            print(f"[CustomEndpointHelper] Response parsing failed: {e}")
            return "", 0, 0, 0

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
                    payload = {"model": model or "", "messages": [{"role": "user", "content": content_items}], "stream": True}
                elif image_path:
                    payload = {
                        "model": model or "",
                        "messages": [
                            {"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": data_url}}]}
                        ],
                        "stream": True,
                    }
                else:
                    payload = {"model": model or "", "messages": [{"role": "user", "content": prompt}], "stream": True}
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
                payload = {"model": model or "", "messages": messages, "stream": True}
            else:
                # Legacy completions-style endpoint (uses 'prompt' or 'input')
                if frame_paths or image_path:
                    raise ValueError("Image uploads not supported for completions-style endpoints")
                payload = {"model": model or "", "prompt": prompt}

        try:
            resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout, stream=True)
        except Exception as e:
            raise RuntimeError(f"Request to custom endpoint failed: {e}")

        if resp.status_code >= 400:
            body = resp.text or "<no body>"
            raise RuntimeError(f"Custom endpoint returned status {resp.status_code}: {body}")

        try:
            raw_body = resp.content
            text, _ = CustomEndpointHelper._parse_openai_stream(resp)
            if text:
                return text
            try:
                return CustomEndpointHelper._extract_text_from_response(json.loads(raw_body.decode("utf-8")))
            except Exception:
                return raw_body.decode("utf-8", errors="replace") if raw_body else ""
        except Exception:
            return resp.text or ""

    @staticmethod
    def _load_provider_endpoints() -> dict:
        try:
            cfg_path = os.path.join(BASE_PATH, 'configs', 'ai_config.json')
            with open(cfg_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            return cfg.get('provider_endpoints', {}) or {}
        except Exception:
            return {}

    @staticmethod
    def _normalize_models_base_url(endpoint: str) -> str:
        base_url = (endpoint or '').rstrip('/')
        base_url_lower = base_url.lower()
        if base_url_lower.endswith('/chat/completions'):
            return base_url[:-len('/chat/completions')]
        if base_url_lower.endswith('/completions'):
            return base_url[:-len('/completions')]
        if base_url_lower.endswith('/models'):
            return base_url[:-len('/models')]
        return base_url

    @staticmethod
    def _parse_free_flag(model: dict, model_id: str, model_name: str) -> bool:
        is_free = False
        if isinstance(model, dict):
            if 'free' in model:
                is_free = bool(model.get('free'))
            elif 'pricing' in model:
                pricing = model.get('pricing', {})
                if isinstance(pricing, dict):
                    prompt_cost = pricing.get('prompt', pricing.get('input', 1))
                    completion_cost = pricing.get('completion', pricing.get('output', 1))
                    try:
                        is_free = float(prompt_cost) == 0 and float(completion_cost) == 0
                    except Exception:
                        is_free = prompt_cost == 0 and completion_cost == 0
        model_id_lower = str(model_id).lower()
        model_name_lower = str(model_name).lower()
        if any((keyword in model_id_lower) or (keyword in model_name_lower) for keyword in ['free', 'gratis', 'zero-cost']):
            is_free = True
        return is_free

    @staticmethod
    def _sort_models(models: list[dict]) -> list[dict]:
        models.sort(key=lambda m: (not bool(m.get('free')), str(m.get('id', '')).lower()))
        return models

    @staticmethod
    def _fetch_openai_compatible_models(api_key: str, endpoint: str, timeout: int = 30) -> tuple[bool, list[dict], str]:
        try:
            base_url = CustomEndpointHelper._normalize_models_base_url(endpoint)
            models_endpoint = f"{base_url}/models"
            CustomEndpointHelper.validate_url(models_endpoint)
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            resp = requests.get(models_endpoint, headers=headers, timeout=timeout)
            if resp.status_code >= 400:
                body = resp.text or '<no body>'
                return False, [], f"Status {resp.status_code}: {body}"
            j = resp.json()
            models = []
            data = j.get('data', [])
            if isinstance(data, list):
                for model in data:
                    if not isinstance(model, dict):
                        continue
                    model_id = model.get('id', '')
                    model_name = model.get('name') or model_id
                    models.append({
                        'id': model_id,
                        'name': model_name,
                        'free': CustomEndpointHelper._parse_free_flag(model, model_id, model_name)
                    })
            return True, CustomEndpointHelper._sort_models(models), ''
        except requests.exceptions.Timeout:
            return False, [], 'Request timeout - endpoint took too long to respond'
        except requests.exceptions.ConnectionError:
            return False, [], 'Connection error - could not reach endpoint'
        except Exception as e:
            return False, [], str(e)

    @staticmethod
    def _fetch_gemini_models(api_key: str, endpoint: str | None = None, timeout: int = 30) -> tuple[bool, list[dict], str]:
        try:
            base_url = (endpoint or CustomEndpointHelper._load_provider_endpoints().get('gemini') or 'https://generativelanguage.googleapis.com/v1beta').rstrip('/')
            base_url_lower = base_url.lower()
            if 'generative.googleapis.com' in base_url_lower:
                base_url = 'https://generativelanguage.googleapis.com/v1beta'
            elif base_url_lower.endswith('/v1'):
                base_url = f"{base_url[:-3]}/v1beta"
            elif not re.search(r'/v1beta(?:/|$)', base_url_lower):
                base_url = f"{base_url}/v1beta" if '/v1' not in base_url_lower else base_url
            models_endpoint = f"{base_url}/models"
            CustomEndpointHelper.validate_url(models_endpoint)
            resp = requests.get(models_endpoint, params={'key': api_key}, timeout=timeout)
            if resp.status_code >= 400:
                body = resp.text or '<no body>'
                return False, [], f"Status {resp.status_code}: {body}"
            j = resp.json()
            models = []
            data = j.get('models', [])
            if isinstance(data, list):
                for model in data:
                    if not isinstance(model, dict):
                        continue
                    raw_name = model.get('name', '')
                    model_id = raw_name.split('models/', 1)[1] if raw_name.startswith('models/') else raw_name
                    if not model_id:
                        continue
                    display_name = model.get('displayName') or model_id
                    models.append({
                        'id': model_id,
                        'name': display_name,
                        'free': CustomEndpointHelper._parse_free_flag(model, model_id, display_name)
                    })
            return True, CustomEndpointHelper._sort_models(models), ''
        except requests.exceptions.Timeout:
            return False, [], 'Request timeout - endpoint took too long to respond'
        except requests.exceptions.ConnectionError:
            return False, [], 'Connection error - could not reach endpoint'
        except Exception as e:
            return False, [], str(e)

    @staticmethod
    def fetch_models(api_key: str, endpoint: str | None = None, timeout: int = 30, provider: str | None = None) -> tuple[bool, list[dict], str]:
        """
        Fetch available models for built-in or custom providers.
        Returns (success, models_list, error_message)
        models_list is a list of dicts with keys: 'id', 'name', 'free' (bool)
        """
        provider_key = (provider or '').strip().lower()
        provider_endpoints = CustomEndpointHelper._load_provider_endpoints()
        openai_compatible = {'openai', 'openrouter', 'groq', 'blackbox', 'maia', 'custom'}
        if provider_key == 'gemini':
            return CustomEndpointHelper._fetch_gemini_models(api_key, endpoint or provider_endpoints.get('gemini'), timeout)
        if provider_key in openai_compatible:
            resolved_endpoint = endpoint or provider_endpoints.get(provider_key)
            if not resolved_endpoint:
                return False, [], f'No endpoint configured for provider: {provider_key}'
            return CustomEndpointHelper._fetch_openai_compatible_models(api_key, resolved_endpoint, timeout)
        resolved_endpoint = endpoint or provider_endpoints.get(provider_key)
        if resolved_endpoint:
            return CustomEndpointHelper._fetch_openai_compatible_models(api_key, resolved_endpoint, timeout)
        return False, [], f'Unsupported provider for model fetch: {provider_key}'

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
