import os
import json
import base64
import time
import re
from openai import OpenAI
from config import BASE_PATH
from helpers.ai_helper.ai_variation_helper import generate_timestamp, generate_token
from helpers.image_compression_helper import compress_and_save_image

_generation_times_openai = []

def track_openai_generation_time(duration_ms):
    _generation_times_openai.append(duration_ms)
    if len(_generation_times_openai) > 1000:
        _generation_times_openai.pop(0)
    gen_time = duration_ms
    avg_time = int(sum(_generation_times_openai) / len(_generation_times_openai)) if _generation_times_openai else 0
    longest_time = max(_generation_times_openai) if _generation_times_openai else 0
    last_time = _generation_times_openai[-1] if _generation_times_openai else 0
    return gen_time, avg_time, longest_time, last_time

def load_openai_prompt_vars():
    prompt_path = os.path.join(BASE_PATH, "configs", "ai_config.json")
    with open(prompt_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    prompt_data = data["prompt"]
    shutterstock_map = data["shutterstock_category_map"]
    adobe_map = data["adobe_stock_category_map"]
    return (
        prompt_data["title_requirements"],
        prompt_data["description_requirements"],
        prompt_data["keywords_requirements"],
        prompt_data["general_guides"],
        prompt_data["strict_donts"],
        prompt_data["unique_token"],
        prompt_data["negative_prompt"],
        prompt_data["system_prompt"],
        prompt_data["custom_prompt"],
        data["min_title_length"],
        data["max_title_length"],
        data["max_description_length"],
        data["required_tag_count"],
        shutterstock_map,
        adobe_map
    )

def format_openai_prompt(
    title_requirements,
    description_requirements,
    keywords_requirements,
    general_guides,
    strict_donts,
    unique_token,
    negative_prompt,
    system_prompt,
    custom_prompt,
    min_title_length,
    max_title_length,
    max_description_length,
    required_tag_count,
    shutterstock_map,
    adobe_map,
    filename=None
):
    prompt = (
        "Create high-quality image or video digital assets metadata following these guidelines:\n\n"
        f"1. Title Requirements:\n{title_requirements}\n\n"
        f"2. Description Requirements:\n{description_requirements}\n\n"
        f"3. Keywords Requirements:\n{keywords_requirements}\n\n"
        f"4. General Guidelines:\n{general_guides}\n\n"
        f"5. Strict Don'ts:\n{strict_donts}\n\n"
        f"6. Uniqueness:\n{unique_token}\n"
    )
    prompt = prompt.replace("_MIN_LEN_", str(min_title_length))
    prompt = prompt.replace("_MAX_LEN_", str(max_title_length))
    prompt = prompt.replace("_MAX_DESC_LEN_", str(max_description_length))
    prompt = prompt.replace("_TAGS_COUNT_", str(required_tag_count))
    prompt = prompt.replace("_TIMESTAMP_", generate_timestamp())
    prompt = prompt.replace("_TOKEN_", generate_token())
    prompt += (
        "\n\nShutterstock categories (number:name):\n"
        "Select TWO relevant categories for Shutterstock: one as PRIMARY (the most relevant), and one as SECONDARY (the next most relevant). Both must be chosen from the list below and must be related to the content.\n"
        f"{json.dumps(shutterstock_map, indent=2)}\n"
        "Adobe Stock categories (number:name):\n"
        f"{json.dumps(adobe_map, indent=2)}\n"
    )
    if filename:
        prompt = f"Filename: {filename}\n{prompt}"
    if custom_prompt and custom_prompt.strip():
        prompt = f"{prompt}\n\nMANDATORY: {custom_prompt.strip()}\n"
    full_prompt = f"{prompt}\n\nNegative Prompt:\n{negative_prompt}\n\n{system_prompt}"
    # Do not remove
    # print("OpenAI Prompt:")
    # print(full_prompt)
    return full_prompt

def title_case_except(text):
    exceptions = {"to", "and", "at", "in", "on", "for", "with", "of", "the", "a", "an", "but", "or", "nor", "so", "yet", "as", "by", "from", "into", "over", "per", "via"}
    words = text.split()
    if not words:
        return text
    result = [words[0].capitalize()]
    for w in words[1:]:
        lw = w.lower()
        if lw in exceptions:
            result.append(lw)
        else:
            result.append(w.capitalize())
    return " ".join(result)

def sanitize_text(text):
    if not text:
        return text
    text = text.replace('"', '').replace("'", "")
    # Replace all punctuation except comma with space
    text = re.sub(r'[^\w\s,]', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text

def generate_metadata_openai(api_key, model, image_path, prompt=None, stop_flag=None):
    if stop_flag and stop_flag.get('stop'):
        return '', '', '', {}, '', 0, 0, 0
    start_time = time.perf_counter()
    try:
        ext = os.path.splitext(image_path)[1].lower()
        is_video = ext in ['.mp4', '.mpeg', '.mov', '.avi', '.flv', '.mpg', '.webm', '.wmv', '.3gp', '.3gpp']
        filename = os.path.basename(image_path)
        if is_video:
            error_message = (
                "OpenAI Vision API belum mendukung input video secara langsung. "
                "Silakan gunakan gambar atau pilih layanan Gemini untuk video. "
                "Jika di masa depan OpenAI sudah mendukung video, fitur ini akan segera ditambahkan."
            )
            return '', '', '', {}, error_message, 0, 0, 0
        client = OpenAI(api_key=api_key)
        if not prompt:
            (
                title_requirements,
                description_requirements,
                keywords_requirements,
                general_guides,
                strict_donts,
                unique_token,
                negative_prompt,
                system_prompt,
                custom_prompt,
                min_title_length,
                max_title_length,
                max_description_length,
                required_tag_count,
                shutterstock_map,
                adobe_map
            ) = load_openai_prompt_vars()
            prompt = format_openai_prompt(
                title_requirements,
                description_requirements,
                keywords_requirements,
                general_guides,
                strict_donts,
                unique_token,
                negative_prompt,
                system_prompt,
                custom_prompt,
                min_title_length,
                max_title_length,
                max_description_length,
                required_tag_count,
                shutterstock_map,
                adobe_map,
                filename=filename
            )
        compressed_path = compress_and_save_image(image_path)
        if not compressed_path:
            error_message = f"[OpenAI ERROR] Failed to compress image: {image_path}"
            return '', '', '', {}, error_message, 0, 0, 0
        with open(compressed_path, "rb") as f:
            image_bytes = f.read()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        image_data_url = f"data:image/jpeg;base64,{image_b64}"
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": image_data_url}
                ]
            }
        ]
        if stop_flag and stop_flag.get('stop'):
            return '', '', '', {}, '', 0, 0, 0
        response = client.responses.create(
            model=model,
            input=messages
        )
        # Do not remove
        # print("OpenAI RAW response:")
        # print(response)
        token_input = 0
        token_output = 0
        token_total = 0
        usage = getattr(response, "usage", None)
        if usage:
            token_input = getattr(usage, "input_tokens", 0)
            token_output = getattr(usage, "output_tokens", 0)
            token_total = getattr(usage, "total_tokens", 0)
        text = None
        if hasattr(response, "output") and response.output:
            for msg in response.output:
                if hasattr(msg, "content") and msg.content:
                    for part in msg.content:
                        if hasattr(part, "text"):
                            text = part.text
                            break
                    if text:
                        break
        if not text:
            text = getattr(response, "output_text", None)
        if not text:
            text = str(response)
        # Do not remove
        # print("OpenAI RAW text:")
        # print(text)
        try:
            if text.strip().startswith('```'):
                text = text.strip().lstrip('`').lstrip('json').strip()
                if text.endswith('```'):
                    text = text[:text.rfind('```')].strip()
            meta = json.loads(text)
            title = meta.get('title', '')
            description = meta.get('description', '')
            tags = meta.get('tags', [])
            if isinstance(tags, list):
                tags = ', '.join([str(tag).strip() for tag in tags])
            else:
                tags = str(tags)
            tags = tags.lower()
            category = meta.get('category', {})
            error_message = ''
        except Exception as e:
            print(f"[OpenAI JSON PARSE ERROR] {e}")
            title = description = tags = ''
            category = {}
            error_message = f"[OpenAI JSON PARSE ERROR] {e}"
        if title:
            title = title_case_except(title)
            title = sanitize_text(title)
        if description:
            description = sanitize_text(description)
        return title, description, tags, category, error_message, token_input, token_output, token_total
    except Exception as e:
        error_message = f"[OpenAI ERROR] {e}"
        print(error_message)
        return '', '', '', {}, error_message, 0, 0, 0
    finally:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        track_openai_generation_time(duration_ms)