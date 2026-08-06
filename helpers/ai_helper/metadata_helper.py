"""Shared normalization for metadata returned by AI providers."""


def normalize_tags(tags) -> str:
    """Return comma-separated, human-readable tags.

    The AI response is authoritative for word boundaries. The only conversion
    performed here is replacing the underscore delimiter requested in the
    prompt. Compound words without an underscore are intentionally not guessed.
    """
    if tags is None:
        return ""
    if isinstance(tags, (list, tuple)):
        values = tags
    else:
        values = str(tags).split(",")

    raw_values = list(values)
    print(f"[AI TAGS RAW] {raw_values}")
    invalid_delimiter_tags = [
        str(value).strip() for value in raw_values
        if " " in str(value).strip()
    ]
    if invalid_delimiter_tags:
        print(
            "[AI TAGS FORMAT WARNING] Multi-word tags must use underscore: "
            f"{invalid_delimiter_tags}"
        )
    normalized = []
    for value in raw_values:
        tag = str(value).strip()
        if not tag:
            continue
        tag = tag.replace("_", " ")
        tag = " ".join(tag.split()).lower()
        if tag and tag not in normalized:
            normalized.append(tag)
    return ", ".join(normalized)
