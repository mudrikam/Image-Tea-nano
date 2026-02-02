import base64
import hashlib
import time
import json
import re
from google import genai
from google.genai import types
from openai import OpenAI

INSTRUCTION_PROMPT = """You are an image analysis assistant specializing in creating commercial metadata for Envato Elements mockups. Your task is to analyze the product and generate compelling, marketable content that helps customers discover and purchase the item.

IMPORTANT: Every request includes a unique timestamp and hash. You MUST treat each request as entirely new and different, even if the image appears similar or identical to previous ones. NEVER repeat or reuse any previous output. Always generate a fresh, original response for every request, using the timestamp and hash as a uniqueness signal.

BRAND RESTRICTION: Do NOT mention any brand names anywhere in the output (title, tagline, tags, description, features, etc).

CORE PRINCIPLES
- Analyze the actual product/mockup, not decorative elements or placeholder text
- Ignore any visible text, it's demonstration content only
- Focus on commercial potential and practical applications
- Create content that sells the product's value and versatility

FORMATTING REQUIREMENTS
- Use Title Case for all text fields
- No word repetition across title, tagline, and tags
- Do not use the word 'this' anywhere in the output
- Include device or brand names only if clearly identifiable, but DO NOT mention any brand names anywhere in the output

OUTPUT SPECIFICATIONS

TITLE (min _TITLE_MIN_, max _TITLE_MAX_ characters)
- The title must include the word 'Mockup'
- Only add 'Set' if the image clearly shows a set, such as a collage or multiple PSDs visible
- Do not use 'Set' if the image does not visually represent a set
- Create an attractive, marketable title that emphasizes appeal and utility

TAGLINE (max _TAGLINE_MAX_ characters)
- Write a compelling marketing message that highlights customer benefits
- Focus on professional results, ease of use, or unique value
- Make it engaging and action-oriented

TAGS (exactly _TAGS_EXPECTED_ keywords)
- Each tag MUST be exactly 1 single word only - absolutely NO spaces, NO hyphens, NO underscores allowed
- NEVER use compound words or phrases
- Tags must match Envato Elements single-word standards
- Focus on discoverable single-word search terms

DESCRIPTION (2 paragraphs, 3-5 sentences, must be engaging and technical)
- Write a description that is both engaging and technical, not just a plain explanation
- Clearly describe product use, advantages, use cases, and specifications
- When mentioning features, use placeholders such as _ITEM_COUNT_ PSD files, _WIDTH_px width, _HEIGHT_px height, and _DPI_dpi resolution
- Explicitly mention the number of PSD files (_ITEM_COUNT_), and also state that a PDF guide document is included as required by Envato Elements
- Highlight technical advantages like customizable, high quality, easy to use, and documentation included
- Emphasize mockup value for designers and marketers
- Highlight professional results and practical benefits in a way that attracts buyers
- Do not use the word 'this' anywhere in the output
- DO NOT mention any brand names in the description or anywhere else

PRODUCT FEATURES (exactly _EXPECTED_FEATURES_ bullet points, must be technical and engaging)
- Each feature must use placeholders: _ITEM_COUNT_, _WIDTH_, _HEIGHT_, _DPI_
- For width and height, always combine as one list item, for example: _WIDTH_px x _HEIGHT_px resolution (never separate)
- Bullet points must be technical and factual, but also engaging and appealing to buyers. Do not make them stiff or overly formal
- Include technical specifications such as high resolution, customizable elements, smart objects, and organized layers
- Mention file formats like PSD and PDF guide
- Include compatibility information for Adobe Photoshop CC and above
- Focus on user benefits such as time-saving, professional results, and flexibility
- Use clear, technical language that is also attractive and marketable

You must output valid JSON only with exactly _EXPECTED_FEATURES_ features and _TAGS_EXPECTED_ tags:
{{
  "title": "",
  "tagline": "",
  "description": "",
  "features": [... _EXPECTED_FEATURES_ items ...],
  "tags": [... _TAGS_EXPECTED_ items ...]
}}
REMEMBER: Each output must be unique and different from any previous response, even for the same image. Use the timestamp and hash as a signal to always generate new content."""


def _is_openrouter_key(api_key: str) -> bool:
    if not api_key or not isinstance(api_key, str):
        return False
    return bool(re.match(r"^sk-?or-", api_key))


def process_image_with_gemini(image_data, api_key, model, limits, service=None):
    tags_count = limits['tags_expected']
    features_count = limits['expected_features']
    title_min = limits['title_min']
    title_max = limits['title_max']
    tagline_max = limits['tagline_max']
    
    # If caller explicitly requests Blackbox service, use it
    if service and isinstance(service, str) and service.lower() == 'blackbox':
        return process_image_with_blackbox(image_data, api_key, model, title_min, title_max, tagline_max, tags_count, features_count)

    is_openrouter = _is_openrouter_key(api_key) or (service and isinstance(service, str) and service.lower() == 'openrouter')
    
    if is_openrouter:
        return process_image_with_openrouter(image_data, api_key, model, title_min, title_max, tagline_max, tags_count, features_count)
    else:
        return process_image_with_gemini_native(image_data, api_key, model, title_min, title_max, tagline_max, tags_count, features_count)


def process_image_with_openrouter(image_data, api_key, model, title_min, title_max, tagline_max, tags_count, features_count, max_retries=5):
    for attempt in range(1, max_retries + 1):
        try:
            if not api_key:
                raise ValueError("API Key not provided")
            
            image_bytes = base64.b64decode(image_data)
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
            image_data_url = f"data:image/jpeg;base64,{image_b64}"
            
            timestamp = int(time.time())
            request_data = f"{timestamp}_{image_data[:100]}"
            request_hash = hashlib.md5(request_data.encode()).hexdigest()
            
            unique_prefix = f"This is a request with timestamp: {timestamp} and hash: {request_hash}. "
            
            filled_prompt = INSTRUCTION_PROMPT.replace('_TITLE_MIN_', str(title_min))
            filled_prompt = filled_prompt.replace('_TITLE_MAX_', str(title_max))
            filled_prompt = filled_prompt.replace('_TAGLINE_MAX_', str(tagline_max))
            filled_prompt = filled_prompt.replace('_TAGS_EXPECTED_', str(tags_count))
            filled_prompt = filled_prompt.replace('_EXPECTED_FEATURES_', str(features_count))
            
            prompt = unique_prefix + filled_prompt
            
            client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
            
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_data_url}}
                        ]
                    }
                ]
            )
            
            print(f"[DEBUG] RAW OPENROUTER RESPONSE: {response}")
            
            if not response or not response.choices:
                raise ValueError("Empty response from OpenRouter")
            
            response_text = response.choices[0].message.content.strip()
            
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            result = json.loads(response_text)
            
            if 'tags' not in result:
                raise KeyError("AI response missing 'tags' field")
            
            if 'title' not in result:
                raise KeyError("AI response missing 'title' field")
                
            if 'tagline' not in result:
                raise KeyError("AI response missing 'tagline' field")
            
            if 'features' not in result:
                raise KeyError("AI response missing 'features' field")
            
            if len(result['tags']) != tags_count:
                print(f"[WARNING] AI returned {len(result['tags'])} tags instead of {tags_count}")
            
            if len(result.get('features', [])) != features_count:
                print(f"[WARNING] AI returned {len(result.get('features', []))} features instead of {features_count}")
            
            if len(result.get('title', '')) > title_max:
                print(f"[WARNING] AI title is {len(result['title'])} characters (over {title_max} limit)")
                
            if len(result.get('tagline', '')) > tagline_max:
                print(f"[WARNING] AI tagline is {len(result['tagline'])} characters (over {tagline_max} limit)")
            
            def to_title_case(s):
                return s.title() if isinstance(s, str) else s
            
            result['title'] = to_title_case(result['title'])
            result['tagline'] = to_title_case(result['tagline'])
            result['tags'] = [to_title_case(tag) for tag in result['tags']]
            
            return result, None
                
        except Exception as e:
            error_str = str(e)
            print(f"[ERROR] Error processing image with OpenRouter (attempt {attempt}): {error_str}")
            
            if "503" in error_str and "overloaded" in error_str.lower():
                if attempt < max_retries:
                    print(f"[DEBUG] Server overloaded, retrying... ({attempt}/{max_retries})")
                    time.sleep(2)
                    continue
                else:
                    return None, f"Server overloaded after {max_retries} attempts. Please try again later."
            else:
                return None, f"Error processing image: {error_str}"
    
    return None, "Max retries exceeded"


def process_image_with_blackbox(image_data, api_key, model, title_min, title_max, tagline_max, tags_count, features_count, max_retries=5):
    """Generate Envato metadata using Blackbox AI via OpenAI-compatible endpoint"""
    for attempt in range(1, max_retries + 1):
        try:
            if not api_key:
                raise ValueError("API Key not provided")

            image_bytes = base64.b64decode(image_data)
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
            image_data_url = f"data:image/jpeg;base64,{image_b64}"

            timestamp = int(time.time())
            request_data = f"{timestamp}_{image_data[:100]}"
            request_hash = hashlib.md5(request_data.encode()).hexdigest()

            unique_prefix = f"This is a request with timestamp: {timestamp} and hash: {request_hash}. "

            filled_prompt = INSTRUCTION_PROMPT.replace('_TITLE_MIN_', str(title_min))
            filled_prompt = filled_prompt.replace('_TITLE_MAX_', str(title_max))
            filled_prompt = filled_prompt.replace('_TAGLINE_MAX_', str(tagline_max))
            filled_prompt = filled_prompt.replace('_TAGS_EXPECTED_', str(tags_count))
            filled_prompt = filled_prompt.replace('_EXPECTED_FEATURES_', str(features_count))

            prompt = unique_prefix + filled_prompt

            client = OpenAI(api_key=api_key, base_url="https://api.blackbox.ai")

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_data_url}}
                        ]
                    }
                ]
            )

            print(f"[DEBUG] RAW BLACKBOX RESPONSE: {response}")

            if not response or not response.choices:
                raise ValueError("Empty response from Blackbox")

            response_text = response.choices[0].message.content.strip()

            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            result = json.loads(response_text)

            if 'tags' not in result:
                raise KeyError("AI response missing 'tags' field")

            if 'title' not in result:
                raise KeyError("AI response missing 'title' field")

            if 'tagline' not in result:
                raise KeyError("AI response missing 'tagline' field")

            if 'features' not in result:
                raise KeyError("AI response missing 'features' field")

            if len(result['tags']) != tags_count:
                print(f"[WARNING] AI returned {len(result['tags'])} tags instead of {tags_count}")

            if len(result.get('features', [])) != features_count:
                print(f"[WARNING] AI returned {len(result.get('features', []))} features instead of {features_count}")

            if len(result.get('title', '')) > title_max:
                print(f"[WARNING] AI title is {len(result['title'])} characters (over {title_max} limit)")

            if len(result.get('tagline', '')) > tagline_max:
                print(f"[WARNING] AI tagline is {len(result['tagline'])} characters (over {tagline_max} limit)")

            def to_title_case(s):
                return s.title() if isinstance(s, str) else s

            result['title'] = to_title_case(result['title'])
            result['tagline'] = to_title_case(result['tagline'])
            result['tags'] = [to_title_case(tag) for tag in result['tags']]

            return result, None

        except Exception as e:
            error_str = str(e)
            print(f"[ERROR] Error processing image with Blackbox (attempt {attempt}): {error_str}")
            if "503" in error_str and "overloaded" in error_str.lower():
                if attempt < max_retries:
                    print(f"[DEBUG] Server overloaded, retrying... ({attempt}/{max_retries})")
                    time.sleep(2)
                    continue
                else:
                    return None, f"Server overloaded after {max_retries} attempts. Please try again later."
            else:
                return None, f"Error processing image: {error_str}"

    return None, "Max retries exceeded"


def process_image_with_gemini_native(image_data, api_key, model, title_min, title_max, tagline_max, tags_count, features_count, max_retries=5):
    for attempt in range(1, max_retries + 1):
        try:
            if not api_key:
                raise ValueError("API Key not provided")
            
            image_bytes = base64.b64decode(image_data)
            
            client = genai.Client(api_key=api_key)
            
            timestamp = int(time.time())
            request_data = f"{timestamp}_{image_data[:100]}"
            request_hash = hashlib.md5(request_data.encode()).hexdigest()
            
            unique_prefix = f"This is a request with timestamp: {timestamp} and hash: {request_hash}. "
            
            filled_prompt = INSTRUCTION_PROMPT.replace('_TITLE_MIN_', str(title_min))
            filled_prompt = filled_prompt.replace('_TITLE_MAX_', str(title_max))
            filled_prompt = filled_prompt.replace('_TAGLINE_MAX_', str(tagline_max))
            filled_prompt = filled_prompt.replace('_TAGS_EXPECTED_', str(tags_count))
            filled_prompt = filled_prompt.replace('_EXPECTED_FEATURES_', str(features_count))
            
            prompt = unique_prefix + filled_prompt
            
            response = client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type='image/jpeg',
                    ),
                    prompt
                ]
            )
            
            print(f"[DEBUG] RAW GEMINI RESPONSE: {response.text if hasattr(response, 'text') else response}")
            
            if not response or not response.text:
                raise ValueError("Empty response from Gemini AI")
            
            response_text = response.text.strip()
            
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            result = json.loads(response_text)
            
            if 'tags' not in result:
                raise KeyError("AI response missing 'tags' field")
            
            if 'title' not in result:
                raise KeyError("AI response missing 'title' field")
                
            if 'tagline' not in result:
                raise KeyError("AI response missing 'tagline' field")
            
            if 'features' not in result:
                raise KeyError("AI response missing 'features' field")
            
            if len(result['tags']) != tags_count:
                print(f"[WARNING] AI returned {len(result['tags'])} tags instead of {tags_count}")
            
            if len(result.get('features', [])) != features_count:
                print(f"[WARNING] AI returned {len(result.get('features', []))} features instead of {features_count}")
            
            if len(result.get('title', '')) > title_max:
                print(f"[WARNING] AI title is {len(result['title'])} characters (over {title_max} limit)")
                
            if len(result.get('tagline', '')) > tagline_max:
                print(f"[WARNING] AI tagline is {len(result['tagline'])} characters (over {tagline_max} limit)")
            
            def to_title_case(s):
                return s.title() if isinstance(s, str) else s
            
            result['title'] = to_title_case(result['title'])
            result['tagline'] = to_title_case(result['tagline'])
            result['tags'] = [to_title_case(tag) for tag in result['tags']]
            
            return result, None
                
        except Exception as e:
            error_str = str(e)
            print(f"[ERROR] Error processing image (attempt {attempt}): {error_str}")
            
            if "503" in error_str and "overloaded" in error_str.lower():
                if attempt < max_retries:
                    print(f"[DEBUG] Server overloaded, retrying... ({attempt}/{max_retries})")
                    time.sleep(2)
                    continue
                else:
                    return None, f"Server overloaded after {max_retries} attempts. Please try again later."
            else:
                return None, f"Error processing image: {error_str}"
    
    return None, "Max retries exceeded"
