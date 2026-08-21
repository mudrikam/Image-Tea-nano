"""Shared handling for OpenAI-compatible SDK responses.

Providers are not consistent about reasoning fields, content parts, or usage
objects. Keep that compatibility code in one place so individual tools do not
mistake a reasoning-only chunk (or an SDK repr) for the final answer.
"""


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def content_to_text(content) -> str:
    """Convert common OpenAI/Gemini content representations to plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (list, tuple)):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            else:
                text = _get(part, "text")
                if text is None:
                    text = _get(part, "output_text")
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return str(content)


def extract_response_text(response) -> str:
    """Extract answer text without exposing private reasoning or SDK reprs."""
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        output = response.get("output")
        if output:
            if isinstance(output, list):
                parts = []
                for item in output:
                    if not isinstance(item, dict):
                        continue
                    item_content = item.get("content")
                    if item_content:
                        parts.append(content_to_text(item_content))
                    elif item.get("text"):
                        parts.append(content_to_text(item.get("text")))
                    elif item.get("output_text"):
                        parts.append(content_to_text(item.get("output_text")))
                if parts:
                    return "".join(parts)
            return content_to_text(output)
        choices = response.get("choices") or []
        if choices:
            choice = choices[0] or {}
            message = choice.get("message") or {}
            text = content_to_text(message.get("content"))
            if text:
                return text
            return content_to_text(choice.get("text"))
        candidates = response.get("candidates") or []
        if candidates:
            candidate = candidates[0] or {}
            content = candidate.get("content") or {}
            if isinstance(content, dict):
                return content_to_text(content.get("parts") or content.get("text"))
            return content_to_text(content)
        return content_to_text(response.get("text") or response.get("output_text"))

    choices = _get(response, "choices") or []
    if choices:
        choice = choices[0]
        message = _get(choice, "message")
        text = content_to_text(_get(message, "content")) if message else ""
        if text:
            return text
        return content_to_text(_get(choice, "text"))
    candidates = _get(response, "candidates") or []
    if candidates:
        candidate = candidates[0]
        content = _get(candidate, "content")
        text = content_to_text(_get(content, "parts")) if content else ""
        if text:
            return text
        return content_to_text(_get(candidate, "text"))
    output = _get(response, "output")
    if output:
        if isinstance(output, (list, tuple)) and output:
            for item in output:
                if not item:
                    continue
                item_content = _get(item, "content")
                if item_content:
                    text = content_to_text(item_content)
                    if text:
                        return text
        return content_to_text(output)
    text = _get(response, "text")
    return content_to_text(text)


def extract_usage(usage) -> tuple:
    if not usage:
        return 0, 0, 0
    token_input = _get(usage, "prompt_tokens", 0) or _get(usage, "input_tokens", 0) or 0
    token_output = _get(usage, "completion_tokens", 0) or _get(usage, "output_tokens", 0) or 0
    token_total = _get(usage, "total_tokens", 0) or (token_input + token_output)
    return token_input, token_output, token_total


def consume_openai_stream(response):
    """Return ``(content, usage)`` while keeping reasoning separate.

    ``response`` is an iterable of SDK chunks. Reasoning chunks are counted
    for diagnostics only; only content is returned to the metadata parser.
    """
    content_parts = []
    usage = (0, 0, 0)
    reasoning_events = 0
    reasoning_chars = 0
    content_events = 0
    content_chars = 0
    finish_reasons = []

    for chunk in response:
        choices = _get(chunk, "choices", None) or []
        choice = choices[0] if choices else None
        chunk_usage = _get(chunk, "usage", None)
        if chunk_usage:
            usage = extract_usage(chunk_usage)
        if choice is None:
            continue

        delta = _get(choice, "delta", None)
        reasoning = _get(delta, "reasoning", None) if delta else None
        if reasoning is None and delta:
            reasoning = _get(delta, "reasoning_content", None)
        if reasoning:
            reasoning_events += 1
            reasoning_chars += len(str(reasoning))

        content = _get(delta, "content", None) if delta else None
        if content:
            content_parts.append(content_to_text(content))
            content_events += 1
            content_chars += len(content_to_text(content))

        # A few OpenAI-compatible servers put the answer in a message object
        # even when stream=True, or expose it as output_text.
        if not delta:
            message_text = extract_response_text(chunk)
            if message_text:
                content_parts.append(message_text)

        finish_reason = _get(choice, "finish_reason", None)
        if finish_reason is not None and finish_reason not in finish_reasons:
            finish_reasons.append(finish_reason)

    print(
        "[SSE] completed: "
        f"reasoning_events={reasoning_events}, reasoning_chars={reasoning_chars}, "
        f"content_events={content_events}, content_chars={content_chars}, "
        f"finish_reason={','.join(map(str, finish_reasons)) or 'none'}, done=True"
    )
    return "".join(content_parts), usage
