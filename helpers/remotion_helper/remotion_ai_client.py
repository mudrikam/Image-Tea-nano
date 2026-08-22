import json
import os
import time


TRANSPORT_MAX_ATTEMPTS = 3
TRANSPORT_BACKOFF = 2.0
_TRANSIENT_HINTS = (
    '502', '503', '504', '500', 'server_error', 'upstream error',
    'rate limit', '429', 'overloaded', 'bad gateway', 'service unavailable',
    'temporarily', 'timeout', 'timed out', 'connection reset', 'connection aborted',
)


def _is_transient_failure(response_text, raised):
    if raised is not None:
        msg = str(raised).lower()
        if 'status 4' in msg:
            return False
        return True
    if response_text:
        text = response_text.strip()
        if '<<<SEARCH' in text or '<<<TOOL_CALL_RESPONSE' in text:
            return False
        try:
            payload = json.loads(text)
        except (TypeError, ValueError):
            return False
        if not isinstance(payload, dict):
            return False
        error = payload.get('error')
        if not error:
            return False
        if isinstance(error, dict):
            error_text = ' '.join(
                str(error.get(key, ''))
                for key in ('code', 'type', 'message', 'status')
            ).lower()
        else:
            error_text = str(error).lower()
        return any(hint in error_text for hint in _TRANSIENT_HINTS)
    return False


def call_remotion_ai(api_key, endpoint, service, model, prompt, timeout=45):
    service = (service or '').lower()
    endpoint = (endpoint or '').strip()

    def _request():
        if endpoint:
            from helpers.ai_helper.custom_endpoint_helper import CustomEndpointHelper
            return CustomEndpointHelper.call_endpoint(
                api_key, endpoint, service, model, prompt, timeout=timeout
            )
        if service == 'gemini':
            import google.genai as genai
            client = genai.Client(api_key=api_key)
            return client.models.generate_content(model=model, contents=[prompt]).text or ''
        if service in ('openai', 'openrouter', 'maia', 'blackbox'):
            from openai import OpenAI
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                'configs', 'ai_config.json'
            )
            with open(config_path, 'r', encoding='utf-8') as handle:
                config = json.load(handle)
            from helpers.ai_helper.openai_stream_helper import extract_response_text
            response = OpenAI(
                api_key=api_key,
                base_url=config['provider_endpoints'][service],
            ).chat.completions.create(
                model=model,
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.2,
            )
            return extract_response_text(response) or ''
        if service == 'groq':
            from groq import Groq
            from helpers.ai_helper.openai_stream_helper import extract_response_text
            response = Groq(api_key=api_key).chat.completions.create(
                model=model,
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.2,
            )
            return extract_response_text(response) or ''
        raise ValueError(f'Unsupported service: {service}')

    last_exc = None
    last_text = ''
    for attempt in range(TRANSPORT_MAX_ATTEMPTS):
        try:
            last_text = _request()
            last_exc = None
            if not _is_transient_failure(last_text, None):
                return last_text
            print(f'[remotion_ai_client] transient response (attempt {attempt + 1}), retrying...')
        except Exception as exc:
            last_exc = exc
            if not _is_transient_failure('', exc):
                raise
            print(f'[remotion_ai_client] transient error (attempt {attempt + 1}): {exc}, retrying...')
        if attempt + 1 < TRANSPORT_MAX_ATTEMPTS:
            time.sleep(TRANSPORT_BACKOFF)
    if last_exc is not None:
        raise last_exc
    return last_text
