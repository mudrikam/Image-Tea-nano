"""Shared handling for OpenAI-compatible SDK streaming responses."""


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
        choices = getattr(chunk, "choices", None) or []
        choice = choices[0] if choices else None
        chunk_usage = getattr(chunk, "usage", None)
        if chunk_usage:
            usage = (
                getattr(chunk_usage, "prompt_tokens", 0) or getattr(chunk_usage, "input_tokens", 0),
                getattr(chunk_usage, "completion_tokens", 0) or getattr(chunk_usage, "output_tokens", 0),
                getattr(chunk_usage, "total_tokens", 0),
            )
        if choice is None:
            continue

        delta = getattr(choice, "delta", None)
        reasoning = getattr(delta, "reasoning", None) if delta else None
        if reasoning is None and delta:
            reasoning = getattr(delta, "reasoning_content", None)
        if reasoning:
            reasoning_events += 1
            reasoning_chars += len(str(reasoning))

        content = getattr(delta, "content", None) if delta else None
        if content:
            content_parts.append(str(content))
            content_events += 1
            content_chars += len(str(content))

        finish_reason = getattr(choice, "finish_reason", None)
        if finish_reason is not None and finish_reason not in finish_reasons:
            finish_reasons.append(finish_reason)

    print(
        "[SSE] completed: "
        f"reasoning_events={reasoning_events}, reasoning_chars={reasoning_chars}, "
        f"content_events={content_events}, content_chars={content_chars}, "
        f"finish_reason={','.join(map(str, finish_reasons)) or 'none'}, done=True"
    )
    return "".join(content_parts), usage
