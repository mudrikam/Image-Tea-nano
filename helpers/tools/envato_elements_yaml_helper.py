import os
from config import BASE_PATH


def load_description_template():
    import yaml
    yaml_path = os.path.join(BASE_PATH, 'configs', 'description.yaml')
    if os.path.exists(yaml_path):
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data.get('template', '')
    return ''


def load_data_yaml():
    import yaml
    yaml_path = os.path.join(BASE_PATH, 'temp', 'elements_mockup', 'data.yaml')
    if os.path.exists(yaml_path):
        with open(yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {
        'image_data': None,
        'items_count': 1,
        'ai_description': '',
        'ai_features': [],
        'results': {
            'title': '',
            'tagline': '',
            'dpi': '300',
            'width': '4500',
            'height': '3000',
            'tags': [],
            'description': ''
        }
    }


def save_data_yaml(data):
    import yaml
    yaml_path = os.path.join(BASE_PATH, 'temp', 'elements_mockup', 'data.yaml')
    os.makedirs(os.path.dirname(yaml_path), exist_ok=True)
    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=1000)


def replace_placeholders(text, items_count, dpi, width, height):
    if not text:
        return text
    text = text.replace('_ITEM_COUNT_', str(items_count))
    text = text.replace('_DPI_', str(dpi))
    text = text.replace('_WIDTH_', str(width))
    text = text.replace('_HEIGHT_', str(height))
    return text


def generate_final_description(ai_description, ai_features, items_count, dpi, width, height):
    template = load_description_template()
    if not template:
        return ai_description
    
    description_with_placeholders = replace_placeholders(ai_description, items_count, dpi, width, height)
    
    features_text = '\n'.join([f'- {replace_placeholders(f, items_count, dpi, width, height)}' for f in ai_features])
    
    final = template.replace('_ADDITIONAL_DETAILS_', description_with_placeholders)
    final = final.replace('_PRODUCT_FEATURES_', features_text)
    
    return final
