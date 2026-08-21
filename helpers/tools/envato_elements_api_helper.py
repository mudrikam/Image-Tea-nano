import base64
import hashlib
import time
import json
import re
import os
from config import BASE_PATH
from google import genai
from google.genai import types
from openai import OpenAI
from helpers.ai_helper.openai_stream_helper import extract_response_text

INSTRUCTION_PROMPT = """You are an Envato Elements metadata specialist for mockup products. Analyze the preview and create accurate, search-focused metadata that helps the right buyers discover and evaluate the item.

UNIQUENESS: Treat every timestamp and hash as a new request. Produce fresh metadata without reusing earlier wording, even for similar images.

BRANDS: Never mention brands, trademarks, companies, or product lines. The required Adobe Photoshop compatibility statement is the only exception.

CORE TASK:
- Identify the actual physical item being presented first: what is it, what does it hold, display, wrap, wear, or contain?
- Identify both the buyer's mockup asset type and the represented item; never treat "mockup" as the complete product identity
- Describe the actual mockup product, not decorative props, logos, or preview text
- Treat visible designs and text as demonstration content, not included assets
- Prioritize product identity and buyer search intent over promotion

ITEM IDENTIFICATION:
- Explicitly classify the primary item before writing metadata, using the most specific visually supported common noun rather than a broad asset category
- If the item has a clear subtype, use the specific buyer-recognized subtype only when it is visibly supported
- If several objects appear, identify the hero item first and list secondary items only when they are part of the actual mockup product or materially define the product's search intent
- Do not replace the item name with a broad category, workflow term, scene label, or abstract design term
- Do not confuse printed artwork or its subject with the physical item; identify the object that receives or displays the design
- When the item is genuinely ambiguous, use the safest accurate category rather than guessing a material, contents, brand, device model, or industry

VISUAL ANALYSIS WORKFLOW:
- First determine the physical item and editable presentation surface
- Ask silently what real-world item a buyer would search for, and make that answer the primary metadata noun
- Separate the primary mockup subject from props, background surfaces, shadows, hands, plants, furniture, and other scene styling
- Determine whether the preview shows one product, several views of one product, or a genuine set of different mockup files
- Note only visible differentiators that affect search intent, including object specificity, viewpoint, environment, physical attributes, composition, lighting, and presentation style
- Infer a commercial use only when the product and scene make that use clear; do not infer a business niche from placeholder artwork or decorative copy
- Perform the analysis silently and return only the required JSON

FORMATTING RULES:
- Use Title Case for title, tagline, and tags; use natural sentence case for description and features
- Keep terminology consistent; repeat the core product keyword where useful, without stuffing
- The physical item must appear naturally in the title, at least one high-priority tag, and the opening of the description; include it in the tagline when it reads naturally
- Do not use the word 'this' anywhere
- Never infer a brand from shape, logo, text, or appearance
- Claim only required or visually supported specifications, assets, editable parts, and functionality

OUTPUT STRUCTURE:
- Output must be a valid JSON object with the following fields: title, tagline, description, features (array), and tags (array)

TITLE: (min _TITLE_MIN_, max _TITLE_MAX_ characters)
- The title must include the word 'Mockup'
- Only add 'Set' if the image clearly shows multiple distinct products or files presented as one collection
- Do not use 'Set' if the image does not visually represent a set
- Front-load the exact product type and strongest search differentiators
- Name the represented physical item explicitly near the beginning, then identify the mockup format
- Add only useful object, scene, viewpoint, style, or use attributes; avoid slogans and keyword lists
- Use the buyer's most common name for the product rather than a clever, vague, or overly technical label
- Use a natural sequence: physical product identity, strongest visual differentiator, then the required mockup format
- Do not repeat Mockup, PSD, product nouns, or the same modifier merely to reach the minimum length
- Do not mention file count, dimensions, DPI, compatibility, or generic quality claims in the title
- Ensure the title remains accurate when viewed without the preview image

TAGLINE: (max _TAGLINE_MAX_ characters)
- Write one natural benefit-led sentence that adds the clearest workflow or presentation value
- Complement rather than repeat the title; avoid hype, commands, clichés, and unsupported superlatives
- Connect the mockup's actual presentation style to a credible buyer outcome
- Prefer a specific workflow, presentation, or buyer benefit only when relevant
- Do not include technical specifications, tag lists, exclamation marks, or calls to action
- Must not exceed _TAGLINE_MAX_ characters

TAGS: (exactly _TAGS_EXPECTED_ keywords)
- Each tag MUST be exactly 1 single word only
- Absolutely NO spaces, NO hyphens, NO underscores allowed
- NEVER invent compound words or concatenate separate words
- Tags must match Envato Elements single-word standards

TAG QUALITY & SEO STRATEGY:
- Rank by likely buyer search value, with the exact product noun and mockup category first
- The first tag must identify the primary physical item whenever a valid single-word item noun is visible; the next strongest tag should identify the mockup or product category
- Then cover only relevant object, industry, use, scene, viewpoint, style, material, and presentation attributes
- Balance broad high-intent terms with specific visual differentiators
- Every tag must describe the product or a strongly supported buyer use; never use filler
- Avoid vague abstract terms unless essential to identify the product
- Use audience terms only for an unambiguous profession or market
- Prefer common evergreen search vocabulary over obscure, trendy, or invented wording
- Avoid singular-plural pairs, near-synonyms, and repeated roots used only to fill the count
- Build the tag list in descending priority from concrete item identity and product category toward supported applications, industry, scene, visual attributes, and explicit audience
- Allocate tags deliberately: item identity first, mockup format second, item subtype or physical attributes next, then supported use, industry, scene, and style
- Choose the canonical singular or plural form buyers most naturally search; never include both forms
- Distinguish visual facts from concepts: concrete product terms rank above style, mood, audience, and use-case terms
- A visible prop may become a tag only when it materially defines the mockup scene or buyer intent; ignore incidental decoration
- Do not derive tags from readable placeholder text, logos, artwork themes, colors inside inserted designs, or imagined contents
- Do not use unsupported commerce, industry, audience, or platform terms unless the mockup genuinely supports that intent
- Do not use subjective quality claims unless the attribute is visually distinctive and useful for search
- Avoid weak format or workflow terms when a more specific product term is available
- Never sacrifice relevance to reach the requested count; use additional factual visual dimensions before supported conceptual terms
- Before finalizing, mentally test every tag as a plausible Envato query that should retrieve the exact displayed product

DESCRIPTION: (2 paragraphs, 3-5 sentences, must be engaging and technical)
- Open with the exact mockup type, visible presentation, and primary buyer use
- State what physical item the mockup represents in the opening clause; do not open with only a format label or broad category
- Explain factual benefits, realistic applications, and distinctive visual qualities
- Mention _ITEM_COUNT_ PSD files and the included PDF guide document
- Integrate primary search terms naturally without repeating the title or listing tags
- Use concrete language; avoid generic praise, stuffing, and unsupported claims
- Emphasize efficient customization, polished presentation, and relevant buyer value
- Do not use the word 'this' or any brand name
- Paragraph one must explain the visible product, scene or composition, and the specific presentation need it solves
- Paragraph two must explain the included PSD files, customization workflow, output quality, and included PDF guide
- Separate the two paragraphs with exactly one blank line inside the JSON string using \\n\\n
- Use the exact core product phrase early, then use natural references instead of repeating it in every sentence
- Make the copy informative enough to answer what the item is, who it helps, how it is used, and what is included
- Do not promise editing behavior, rendering quality, scene control, included assets, or other capabilities unless required below or clearly supported
- Do not claim preview content or decorative elements are included
- Avoid empty sales language, exaggerated claims, and generic calls to value

PRODUCT FEATURES: (exactly _EXPECTED_FEATURES_ bullet points, must be technical and engaging)
- Across the list, preserve all placeholders: _ITEM_COUNT_, _WIDTH_, _HEIGHT_, _DPI_
- Combine width and height in one item as _WIDTH_px x _HEIGHT_px resolution
- Write concise, scannable, non-overlapping technical benefits
- Include _ITEM_COUNT_ PSD files, _WIDTH_px x _HEIGHT_px resolution, _DPI_dpi, smart objects, organized layers, customizable elements, PDF guide, and Adobe Photoshop CC or above compatibility
- State each specification once with its buyer benefit
- Do not invent fonts, dimensions, effects, orientations, files, or controls beyond these required facts
- Return each feature as a plain JSON string without bullets, numbering, headings, periods, or repeated opening phrases
- Lead with the specification or capability, then state its practical benefit concisely
- Keep smart objects, organized layers, customization, dimensions and DPI, included files, guide, and compatibility as distinct feature topics
- Do not state the same benefit using different wording merely to fill the required count

You must output valid JSON only with exactly _EXPECTED_FEATURES_ features and _TAGS_EXPECTED_ tags:
{
  "title": "",
  "tagline": "",
  "description": "",
  "features": [... _EXPECTED_FEATURES_ items ...],
  "tags": [... _TAGS_EXPECTED_ items ...]
}
FINAL QUALITY CHECK:
1. Confirm title length is within _TITLE_MIN_-_TITLE_MAX_ characters and tagline is no more than _TAGLINE_MAX_ characters
2. Confirm title contains Mockup exactly once and Set only when visually justified
3. Confirm description has exactly 2 paragraphs and 3-5 total sentences
4. Confirm features contains exactly _EXPECTED_FEATURES_ non-overlapping strings and all required specifications
5. Confirm tags contains exactly _TAGS_EXPECTED_ unique, single-word search terms in descending buyer-search priority
6. Reject every unsupported, decorative, vague, redundant, brand-related, or filler term
7. Confirm all placeholders remain exact and all fields describe the same product consistently
8. Return valid JSON only, with double quotes, escaped line breaks, no markdown, comments, or extra text

PLACEHOLDERS: Keep _ITEM_COUNT_, _WIDTH_, _HEIGHT_, and _DPI_ exactly as plain text. Never replace or interpret them.
"""


def _is_openrouter_key(api_key: str) -> bool:
    if not api_key or not isinstance(api_key, str):
        return False
    return bool(re.match(r"^sk-?or-", api_key))


def process_image_with_gemini(image_data, api_key, model, limits, service=None, endpoint=None):
    tags_count = limits['tags_expected']
    features_count = limits['expected_features']
    title_min = limits['title_min']
    title_max = limits['title_max']
    tagline_max = limits['tagline_max']
    
    # Normalize service
    svc = (service or '').lower()
    
    # Explicit service routing for known specialized handlers
    if svc == 'blackbox':
        return process_image_with_blackbox(image_data, api_key, model, title_min, title_max, tagline_max, tags_count, features_count)
    
    if svc == 'maia':
        return process_image_with_maia(image_data, api_key, model, title_min, title_max, tagline_max, tags_count, features_count)
    
    # OpenRouter: use dedicated handler (it has special logic for OpenRouter-specific params)
    is_openrouter = _is_openrouter_key(api_key) or svc == 'openrouter'
    if is_openrouter:
        return process_image_with_openrouter(image_data, api_key, model, title_min, title_max, tagline_max, tags_count, features_count)
    
    # Gemini native
    if svc == 'gemini':
        return process_image_with_gemini_native(image_data, api_key, model, title_min, title_max, tagline_max, tags_count, features_count)
    
    # Other OpenAI-compatible services (use OpenAI SDK with their default endpoints)
    openai_compatible_defaults = {
        'kobillm': 'https://api.koboillm.com/v1',
        'openai': 'https://api.openai.com/v1',
        'groq': 'https://api.groq.com/openai/v1',
        'together': 'https://api.together.xyz/v1',
        'deepseek': 'https://api.deepseek.com/v1',
        'perplexity': 'https://api.perplexity.ai/v1',
    }
    
    if svc in openai_compatible_defaults:
        base_url = endpoint or openai_compatible_defaults[svc]
        return process_image_with_custom(image_data, api_key, model, base_url, title_min, title_max, tagline_max, tags_count, features_count)
    
    # Custom/any other service with explicit endpoint → use custom handler
    if endpoint:
        return process_image_with_custom(image_data, api_key, model, endpoint, title_min, title_max, tagline_max, tags_count, features_count)
    
    # Unknown service without endpoint → fallback to Gemini (could be misconfigured)
    print(f"[WARNING] Unknown service '{service}' without endpoint, falling back to Gemini native")
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
            
            # Resolve OpenRouter base URL from config, fallback to built-in
            try:
                cfg_path = os.path.join(BASE_PATH, 'configs', 'ai_config.json')
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                base_url = cfg.get('provider_endpoints', {}).get('openrouter') or "https://openrouter.ai/api/v1"
            except Exception:
                base_url = "https://openrouter.ai/api/v1"

            client = OpenAI(api_key=api_key, base_url=base_url)
            
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
            
            response_text = extract_response_text(response).strip()
            
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

            # Resolve Blackbox base URL from config if available
            try:
                cfg_path = os.path.join(BASE_PATH, 'configs', 'ai_config.json')
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                base_url = cfg.get('provider_endpoints', {}).get('blackbox') or "https://api.blackbox.ai"
            except Exception:
                base_url = "https://api.blackbox.ai"

            client = OpenAI(api_key=api_key, base_url=base_url)

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

            response_text = extract_response_text(response).strip()

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


def process_image_with_maia(image_data, api_key, model, title_min, title_max, tagline_max, tags_count, features_count, max_retries=5):
    """Generate Envato metadata using MAIA Router via OpenAI-compatible endpoint"""
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

            # Resolve MAIA Router base URL from config if available
            try:
                cfg_path = os.path.join(BASE_PATH, 'configs', 'ai_config.json')
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                base_url = cfg.get('provider_endpoints', {}).get('maia') or "https://api.maiarouter.ai/v1"
            except Exception:
                base_url = "https://api.maiarouter.ai/v1"

            client = OpenAI(api_key=api_key, base_url=base_url)

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

            print(f"[DEBUG] RAW MAIA RESPONSE: {response}")

            if not response or not response.choices:
                raise ValueError("Empty response from MAIA Router")

            response_text = extract_response_text(response).strip()

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
            print(f"[ERROR] Error processing image with MAIA Router (attempt {attempt}): {error_str}")
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


def process_image_with_custom(image_data, api_key, model, endpoint, title_min, title_max, tagline_max, tags_count, features_count, max_retries=5):
    """Generate Envato metadata using custom OpenAI-compatible endpoint.
    Endpoint should be base URL (e.g. https://api.example.com/v1) or full chat completions URL.
    If full URL is provided, the base part is extracted automatically."""
    # Strip trailing '/chat/completions' if present to get base_url
    base_url = endpoint
    if endpoint:
        ep_low = endpoint.lower().rstrip('/')
        if ep_low.endswith('/chat/completions') or ep_low.endswith('/v1/chat/completions'):
            base_url = endpoint[:endpoint.rfind('/chat/completions')]
            # Ensure no trailing slash
            base_url = base_url.rstrip('/')
    
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
            
            client = OpenAI(api_key=api_key, base_url=base_url)
            
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
            
            print(f"[DEBUG] RAW CUSTOM ENDPOINT RESPONSE: {response}")
            
            if not response or not response.choices:
                raise ValueError("Empty response from custom endpoint")
            
            response_text = extract_response_text(response).strip()
            
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
            print(f"[ERROR] Error processing image with custom endpoint (attempt {attempt}): {error_str}")
            
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
