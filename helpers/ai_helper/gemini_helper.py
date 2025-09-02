import time
import os
import json
import re
import google.genai as genai
from google.genai import types
from config import BASE_PATH
from helpers.ai_helper.ai_variation_helper import generate_timestamp, generate_token
from helpers.image_compression_helper import compress_and_save_image

_generation_times_gemini = []

def track_gemini_generation_time(duration_ms):
    _generation_times_gemini.append(duration_ms)
    if len(_generation_times_gemini) > 1000:
        _generation_times_gemini.pop(0)
    gen_time = duration_ms
    avg_time = int(sum(_generation_times_gemini) / len(_generation_times_gemini)) if _generation_times_gemini else 0
    longest_time = max(_generation_times_gemini) if _generation_times_gemini else 0
    last_time = _generation_times_gemini[-1] if _generation_times_gemini else 0
    return gen_time, avg_time, longest_time, last_time

def load_gemini_prompt_vars():
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

def format_gemini_prompt(
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
    # print("Gemini Prompt:")
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

def generate_metadata_gemini(api_key, model, image_path, prompt=None, stop_flag=None):
    if stop_flag and stop_flag.get('stop'):
        return '', '', '', '', 0, 0, 0
    start_time = time.perf_counter()
    try:
        client = genai.Client(api_key=api_key)
        ext = os.path.splitext(image_path)[1].lower()
        is_video = ext in ['.mp4', '.mpeg', '.mov', '.avi', '.flv', '.mpg', '.webm', '.wmv', '.3gp', '.3gpp']
        filename = os.path.basename(image_path)
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
            ) = load_gemini_prompt_vars()
            prompt = format_gemini_prompt(
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
        if is_video:
            myfile = client.files.upload(file=image_path)
            file_id = myfile.name if hasattr(myfile, 'name') else getattr(myfile, 'id', None)
            status = None
            max_wait_seconds = 600
            poll_interval = 1
            waited = 0
            while waited < max_wait_seconds:
                if stop_flag and stop_flag.get('stop'):
                    return '', '', '', '', 0, 0, 0
                fileinfo = client.files.get(name=file_id)
                status = getattr(fileinfo, 'state', None) or getattr(fileinfo, 'status', None)
                if status == 'ACTIVE':
                    break
                time.sleep(poll_interval)
                waited += poll_interval
            if status != 'ACTIVE':
                print(f"[Gemini ERROR] File {file_id} not ACTIVE after upload, status: {status}")
                return '', '', '', '', 0, 0, 0
            contents = [myfile, prompt]
        else:
            compressed_path = compress_and_save_image(image_path)
            if not compressed_path:
                print(f"[Gemini ERROR] Failed to compress image: {image_path}")
                return '', '', '', '', 0, 0, 0
            with open(compressed_path, 'rb') as f:
                image_bytes = f.read()
            contents = [types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'), prompt]
        if stop_flag and stop_flag.get('stop'):
            return '', '', '', '', 0, 0, 0
        response = client.models.generate_content(
            model=model,
            contents=contents
        )
        # Do not remove
        # print("Gemini RAW response:")
        # print(response)
        token_input = 0
        token_output = 0
        token_total = 0
        usage = getattr(response, "usage_metadata", None)
        if usage:
            token_input = getattr(usage, "prompt_token_count", 0)
            token_output = getattr(usage, "candidates_token_count", 0)
            token_total = getattr(usage, "total_token_count", 0)
        text = None
        if hasattr(response, "candidates") and response.candidates:
            try:
                text = response.candidates[0].content.parts[0].text
            except Exception:
                text = str(response)
        elif hasattr(response, "text"):
            text = response.text
        elif isinstance(response, dict) and 'text' in response:
            text = response['text']
        else:
            text = str(response)
        # Do not remove
        # print("Gemini RAW text:")
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
            print(f"[Gemini JSON PARSE ERROR] {e}")
            title = description = tags = ''
            category = {}
            error_message = f"[Gemini JSON PARSE ERROR] {e}"
        if title:
            title = title_case_except(title)
            title = sanitize_text(title)
        if description:
            description = sanitize_text(description)
        return title, description, tags, category, error_message, token_input, token_output, token_total
    except Exception as e:
        print(f"[Gemini ERROR] {e}")
        return '', '', '', {}, f"[Gemini ERROR] {e}", 0, 0, 0
    finally:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        track_gemini_generation_time(duration_ms)