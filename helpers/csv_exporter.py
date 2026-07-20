from database.db_operation import ImageTeaDB
import os
import datetime
import re
import csv
from helpers.video_proxy_helper import VIDEO_EXTENSIONS

def _sanitize_text_for_csv(text):
    if not text:
        return text
    pattern = r'[^a-zA-Z0-9\s]'
    sanitized = re.sub(pattern, '', text)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    return sanitized

SHARED_FORMATS = {
    "Magnific": {
        "delimiter": ";",
        "header": ['File name', 'Title', 'Keywords', 'Prompt', 'Model'],
        "fields": ['filename', 'title', 'keywords', 'prompt', 'model'],
        "quote_fields": "all",
        "quote_header": False
    },
    "Adobe Stock": {
        "delimiter": ',',
        "header": ['Filename', 'Title', 'Keywords', 'Category', 'Releases'],
        "fields": ['filename', 'title', 'keywords', 'category', 'releases'],
        "quote_fields": ['filename', 'keywords', 'releases'],
        "quote_header": False
    },
    "Shutterstock": {
        "delimiter": ',',
        "header": ['Filename', 'Description', 'Keywords', 'Categories', 'Editorial', 'Mature content', 'illustration'],
        "fields": ['filename', 'description', 'keywords', 'categories', 'editorial', 'mature_content', 'illustration'],
        "quote_fields": ['filename', 'description', 'keywords', 'categories'],
        "quote_header": False
    },
    "123RF": {
        "delimiter": ',',
        "header": ['oldfilename', '123rf_filename', 'description', 'keywords', 'country'],
        "fields": ['filename', 'title', 'description', 'keywords', 'country'],
        "quote_fields": "all",
        "quote_header": True
    },
    "Vecteezy": {
        "delimiter": ',',
        "header": ['Filename', 'Title', 'Description', 'Keywords', 'License'],
        "fields": ['filename', 'title', 'description', 'keywords', 'license'],
        "quote_fields": ['filename', 'keywords'],
        "quote_header": False
    },
    "iStock": {
        "delimiter": ',',
        "header": ['file name', 'description', 'country', 'title', 'keywords', 'poster timecode', 'shot speed', 'date created'],
        "fields": ['filename', 'description', 'country', 'title', 'keywords', 'poster_timecode', 'shot_speed', 'date_created'],
        "quote_fields": ['filename', 'description', 'title', 'keywords', 'poster_timecode', 'shot_speed'],
        "quote_header": False
    },
    "Pond5": {
        "delimiter": ',',
        "header": ['OriginalFilename', 'Title', 'Description', 'Keywords', 'City', 'Region', 'Country', 'Specifysource', 'Modelreleased', 'Propertyreleased', 'Release', 'Copyright', 'Price', 'Editorial'],
        "fields": ['filename', 'title', 'description', 'keywords', 'city', 'region', 'country', 'specifysource', 'modelreleased', 'propertyreleased', 'release', 'copyright', 'price', 'editorial'],
        "quote_fields": "all",
        "quote_header": True
    },
    "Depositphotos": {
        "delimiter": ',',
        "header": ['Filename', 'description', 'Keywords', 'Nudity', 'Editorial'],
        "fields": ['filename', 'description', 'keywords', 'nudity', 'editorial'],
        "quote_fields": "all",
        "quote_header": True
    },
    "Canva": {
        "delimiter": ',',
        "header": ['filename', 'title', 'keywords', 'Artist', 'locale', 'description'],
        "fields": ['filename', 'title', 'keywords', 'artist', 'locale', 'description'],
        "quote_fields": ['filename', 'title', 'keywords', 'description'],
        "quote_header": False
    },
    "MiriCanvas": {
        "delimiter": ',',
        "header": ['fileName', 'elementName', 'keywords', 'tier', 'contentType'],
        "fields": ['filename', 'elementName', 'keywords', 'tier', 'contentType'],
        "quote_fields": "all",
        "quote_header": True
    }
}

def _write_csv_with_custom_quoting(file_path, header, rows, delimiter, quote_fields, quote_header):
    with open(file_path, "w", encoding="utf-8", newline='') as f:
        if quote_header:
            header_line = delimiter.join([f'"{h}"' for h in header])
        else:
            header_line = delimiter.join(header)
        f.write(header_line + '\n')
        
        for row in rows:
            if quote_fields == "all":
                line = delimiter.join([f'"{v}"' for v in row])
            elif quote_fields == "none":
                line = delimiter.join(row)
            else:
                formatted_fields = []
                for i, v in enumerate(row):
                    field_key = header[i].lower().replace(' ', '_') if i < len(header) else ""
                    if isinstance(quote_fields, list) and any(qf in field_key for qf in quote_fields):
                        formatted_fields.append(f'"{v}"')
                    else:
                        formatted_fields.append(v)
                line = delimiter.join(formatted_fields)
            f.write(line + '\n')

def get_next_index(base_name, output_path):
    if not os.path.isdir(output_path):
        raise FileNotFoundError(f"Output path does not exist: {output_path}")
    base = base_name
    try:
        if base.lower().endswith('.csv'):
            base = base[:-4]
        if not base.endswith('_'):
            base = base + '_'
        
        # Scan all existing files matching the pattern to find max index
        max_idx = 0
        pattern = re.compile(rf"^{re.escape(base)}(\d{{3}})\.csv$", re.IGNORECASE)
        
        try:
            for filename in os.listdir(output_path):
                match = pattern.match(filename)
                if match:
                    idx = int(match.group(1))
                    max_idx = max(max_idx, idx)
        except Exception as e:
            print(f"[csv_exporter] Error scanning directory: {e}")
        
        return max_idx + 1
    except Exception as e:
        print(f"[csv_exporter] get_next_index error: {e}")
        raise


def generate_export_filename(base_name, output_path):
    try:
        idx = get_next_index(base_name, output_path)
        base = base_name
        if base.lower().endswith('.csv'):
            base = base[:-4]
        if not base.endswith('_'):
            base = base + '_'
        return f"{base}{idx:03d}.csv"
    except Exception as e:
        print(f"[csv_exporter] generate_export_filename error: {e}")
        raise

def _magnific_format(file):
    return {
        'filename': file[2],
        'title': _sanitize_text_for_csv(file[3] if file[3] is not None else ""),
        'keywords': file[5] if file[5] is not None else "",
        'prompt': "",
        'model': ""
    }

def _adobe_stock_format(file, adobe_map, category_mapping):
    file_id = file[0]
    category_text = ""
    for mapping in category_mapping:
        if mapping['file_id'] == file_id and mapping['platform'] == 'adobe_stock':
            category_text = str(mapping['category_id'])
            break
    return {
        'filename': file[2],
        'title': _sanitize_text_for_csv(file[3] if file[3] is not None else ""),
        'keywords': file[5] if file[5] is not None else "",
        'category': category_text,
        'releases': ""
    }

def _shutterstock_format(file, shutterstock_image_map, shutterstock_video_map, category_mapping, db):
    file_id = file[0]
    filepath = file[1]
    filename = file[2]

    # Choose map deterministically based on extension
    ext = os.path.splitext(filepath)[1].lower()
    is_video = ext in VIDEO_EXTENSIONS
    shutterstock_map = shutterstock_video_map if is_video else shutterstock_image_map

    primary = None
    secondary = None
    for mapping in category_mapping:
        if mapping['file_id'] == file_id and mapping['platform'] == 'shutterstock':
            if str(mapping['category_name']).lower().endswith('(primary)'):
                primary = mapping['category_id']
            elif str(mapping['category_name']).lower().endswith('(secondary)'):
                secondary = mapping['category_id']

    categories = ""
    if primary and secondary:
        categories = f"{shutterstock_map.get(str(primary), '')},{shutterstock_map.get(str(secondary), '')}"
    elif primary:
        categories = shutterstock_map.get(str(primary), '')
    elif secondary:
        categories = shutterstock_map.get(str(secondary), '')

    # Determine illustration flag from stored file types
    illustration = "yes"
    file_types = db.get_file_types(file_id)
    if file_types:
        file_type = file_types[0][1]
        if file_type.lower() == "photo":
            illustration = "no"
        elif file_type.lower() == "illustration":
            illustration = "yes"

    return {
        'filename': filename,
        'description': _sanitize_text_for_csv(file[4] if file[4] is not None else ""),
        'keywords': file[5] if file[5] is not None else "",
        'categories': categories,
        'editorial': 'no',
        'mature_content': 'no',
        'illustration': illustration
    }

def _123rf_format(file):
    return {
        'filename': file[2],
        'title': _sanitize_text_for_csv(file[3] if file[3] is not None else ""),
        'description': _sanitize_text_for_csv(file[4] if file[4] is not None else ""),
        'keywords': file[5] if file[5] is not None else "",
        'country': ''
    }

def _sanitize_filename_for_vecteezy(filename):
    """
    Sanitize filename for Vecteezy export using project rules:
    - Remove existing underscores from the original name.
    - Convert spaces to underscores.
    - Convert any special character (non-alphanumeric, excluding hyphen) to underscore.
    - Preserve hyphens ("-").
    - Do not collapse consecutive underscores ("comma + space" -> "__").
    """
    base, ext = os.path.splitext(filename)
    # Remove existing underscores from original filename
    base = base.replace('_', '')

    out_chars = []
    for ch in base:
        if ch.isalnum():
            out_chars.append(ch)
        elif ch == '-':
            # preserve hyphen
            out_chars.append(ch)
        elif ch.isspace():
            # spaces -> underscore
            out_chars.append('_')
        else:
            # special characters -> underscore
            out_chars.append('_')

    sanitized = ''.join(out_chars)

    if not sanitized:
        print(f"[csv_exporter] _sanitize_filename_for_vecteezy: sanitized name empty for '{filename}'")
        sanitized = 'file'
        print(f"[csv_exporter] _sanitize_filename_for_vecteezy: fallback to '{sanitized}' for '{filename}'")

    if ext:
        return sanitized + ext
    return sanitized


def _vecteezy_format(file):
    filename = _sanitize_filename_for_vecteezy(file[2])
    return {
        'filename': filename,
        'title': _sanitize_text_for_csv(file[3] if file[3] is not None else ""),
        'description': _sanitize_text_for_csv(file[4] if file[4] is not None else ""),
        'keywords': file[5] if file[5] is not None else "",
        'license': 'Pro'
    }

def _istock_format(file):
    today = datetime.datetime.now()
    created_date = today.strftime("%m/%d/%Y")
    return {
        'filename': file[2],
        'description': _sanitize_text_for_csv(file[4] if file[4] is not None else ""),
        'country': '',
        'title': _sanitize_text_for_csv(file[3] if file[3] is not None else ""),
        'keywords': file[5] if file[5] is not None else "",
        'poster_timecode': '',
        'shot_speed': 'Real Time',
        'date_created': created_date
    }

def _pond5_format(file):
    return {
        'filename': file[2],
        'title': _sanitize_text_for_csv(file[3] if file[3] is not None else ""),
        'description': _sanitize_text_for_csv(file[4] if file[4] is not None else ""),
        'keywords': file[5] if file[5] is not None else "",
        'city': '',
        'region': '',
        'country': '',
        'specifysource': '',
        'modelreleased': '',
        'propertyreleased': '',
        'release': '',
        'copyright': '',
        'price': '',
        'editorial': ''
    }

def _depositphotos_format(file):
    return {
        'filename': file[2],
        'description': _sanitize_text_for_csv(file[4] if file[4] is not None else ""),
        'keywords': file[5] if file[5] is not None else "",
        'nudity': 'no',
        'editorial': 'no'
    }

def _canva_format(file):
    return {
        'filename': file[2],
        'title': _sanitize_text_for_csv(file[3] if file[3] is not None else ""),
        'keywords': file[5] if file[5] is not None else "",
        'artist': '',
        'locale': 'en',
        'description': _sanitize_text_for_csv(file[4] if file[4] is not None else "")
    }
def _miricanvas_format(file):
    filename = file[2]
    filename_no_ext = re.sub(r'\.[^.]+$', '', filename)
    return {
        'filename': filename_no_ext,
        'elementName': _sanitize_text_for_csv(file[3] if file[3] is not None else ""),
        'keywords': file[5] if file[5] is not None else "",
        'tier': '',
        'contentType': ''
    }

def export_csv_for_platforms(platforms, output_path=None, progress_callback=None, name_map=None):
    print(f"[csv_exporter] Exporting CSV for platforms: {platforms}")
    print(f"[csv_exporter] Output path: {output_path}")
    if output_path is None or not os.path.isdir(output_path):
        print(f"[csv_exporter] Invalid output path: {output_path}")
        return
    if name_map is None:
        print("[csv_exporter] name_map is required (platform -> base_name)")
        return
    db = ImageTeaDB()
    files = db.get_all_files()
    shutterstock_image_map, shutterstock_video_map, adobe_map = db.get_category_maps()
    category_mapping = db.get_category_mapping()


    if "Magnific" in platforms and output_path:
        fmt = SHARED_FORMATS['Magnific']
        rows = []
        for file in files:
            rows.append(_magnific_format(file))
            if progress_callback:
                progress_callback()
        if rows:
            if "Magnific" not in name_map:
                print("[csv_exporter] Missing base name for Magnific in name_map, skipping")
            else:
                csv_filename = generate_export_filename(name_map["Magnific"], output_path)
                csv_path = os.path.join(output_path, csv_filename)
                try:
                    row_data = [[row.get(k, '') for k in fmt['fields']] for row in rows]
                    _write_csv_with_custom_quoting(csv_path, fmt['header'], row_data, fmt['delimiter'], fmt['quote_fields'], fmt['quote_header'])
                    print(f"[csv_exporter] Magnific CSV exported to: {csv_path}")
                except Exception as e:
                    print(f"[csv_exporter] Error exporting Magnific CSV: {e}")
    if "Adobe Stock" in platforms and output_path:
        fmt = SHARED_FORMATS['Adobe Stock']
        rows = []
        for file in files:
            rows.append(_adobe_stock_format(file, adobe_map, category_mapping))
            if progress_callback:
                progress_callback()
        if rows:
            key = "Adobe Stock"
            if key not in name_map:
                print(f"[csv_exporter] Missing base name for {key} in name_map, skipping")
            else:
                csv_filename = generate_export_filename(name_map[key], output_path)
                csv_path = os.path.join(output_path, csv_filename)
                try:
                    row_data = [[row.get(k, '') for k in fmt['fields']] for row in rows]
                    _write_csv_with_custom_quoting(csv_path, fmt['header'], row_data, fmt['delimiter'], fmt['quote_fields'], fmt['quote_header'])
                    print(f"[csv_exporter] Adobe Stock CSV exported to: {csv_path}")
                except Exception as e:
                    print(f"[csv_exporter] Error exporting Adobe Stock CSV: {e}")
    if "Shutterstock" in platforms and output_path:
        fmt = SHARED_FORMATS['Shutterstock']
        rows = []
        for file in files:
            rows.append(_shutterstock_format(file, shutterstock_image_map, shutterstock_video_map, category_mapping, db))
            if progress_callback:
                progress_callback()
        if rows:
            key = "Shutterstock"
            if key not in name_map:
                print(f"[csv_exporter] Missing base name for {key} in name_map, skipping")
            else:
                csv_filename = generate_export_filename(name_map[key], output_path)
                csv_path = os.path.join(output_path, csv_filename)
                try:
                    row_data = [[row.get(k, '') for k in fmt['fields']] for row in rows]
                    _write_csv_with_custom_quoting(csv_path, fmt['header'], row_data, fmt['delimiter'], fmt['quote_fields'], fmt['quote_header'])
                    print(f"[csv_exporter] Shutterstock CSV exported to: {csv_path}")
                except Exception as e:
                    print(f"[csv_exporter] Error exporting Shutterstock CSV: {e}")
    if "123RF" in platforms and output_path:
        fmt = SHARED_FORMATS['123RF']
        rows = []
        for file in files:
            rows.append(_123rf_format(file))
            if progress_callback:
                progress_callback()
        if rows:
            key = "123RF"
            if key not in name_map:
                print(f"[csv_exporter] Missing base name for {key} in name_map, skipping")
            else:
                csv_filename = generate_export_filename(name_map[key], output_path)
                csv_path = os.path.join(output_path, csv_filename)
                try:
                    row_data = [[row.get(k, '') for k in fmt['fields']] for row in rows]
                    _write_csv_with_custom_quoting(csv_path, fmt['header'], row_data, fmt['delimiter'], fmt['quote_fields'], fmt['quote_header'])
                    print(f"[csv_exporter] 123rf CSV exported to: {csv_path}")
                except Exception as e:
                    print(f"[csv_exporter] Error exporting 123rf CSV: {e}")
    if "Vecteezy" in platforms and output_path:
        fmt = SHARED_FORMATS['Vecteezy']
        rows = []
        for file in files:
            rows.append(_vecteezy_format(file))
            if progress_callback:
                progress_callback()
        if rows:
            key = "Vecteezy"
            if key not in name_map:
                print(f"[csv_exporter] Missing base name for {key} in name_map, skipping")
            else:
                csv_filename = generate_export_filename(name_map[key], output_path)
                csv_path = os.path.join(output_path, csv_filename)
                try:
                    row_data = [[row.get(k, '') for k in fmt['fields']] for row in rows]
                    _write_csv_with_custom_quoting(csv_path, fmt['header'], row_data, fmt['delimiter'], fmt['quote_fields'], fmt['quote_header'])
                    print(f"[csv_exporter] Vecteezy CSV exported to: {csv_path}")
                except Exception as e:
                    print(f"[csv_exporter] Error exporting Vecteezy CSV: {e}")
    if "iStock" in platforms and output_path:
        fmt = SHARED_FORMATS['iStock']
        rows = []
        for file in files:
            rows.append(_istock_format(file))
            if progress_callback:
                progress_callback()
        if rows:
            key = "iStock"
            if key not in name_map:
                print(f"[csv_exporter] Missing base name for {key} in name_map, skipping")
            else:
                csv_filename = generate_export_filename(name_map[key], output_path)
                csv_path = os.path.join(output_path, csv_filename)
                try:
                    row_data = [[row.get(k, '') for k in fmt['fields']] for row in rows]
                    _write_csv_with_custom_quoting(csv_path, fmt['header'], row_data, fmt['delimiter'], fmt['quote_fields'], fmt['quote_header'])
                    print(f"[csv_exporter] iStock CSV exported to: {csv_path}")
                except Exception as e:
                    print(f"[csv_exporter] Error exporting iStock CSV: {e}")
    if "Pond5" in platforms and output_path:
        fmt = SHARED_FORMATS['Pond5']
        rows = []
        for file in files:
            rows.append(_pond5_format(file))
            if progress_callback:
                progress_callback()
        if rows:
            key = "Pond5"
            if key not in name_map:
                print(f"[csv_exporter] Missing base name for {key} in name_map, skipping")
            else:
                csv_filename = generate_export_filename(name_map[key], output_path)
                csv_path = os.path.join(output_path, csv_filename)
                try:
                    row_data = [[row.get(k, '') for k in fmt['fields']] for row in rows]
                    _write_csv_with_custom_quoting(csv_path, fmt['header'], row_data, fmt['delimiter'], fmt['quote_fields'], fmt['quote_header'])
                    print(f"[csv_exporter] Pond5 CSV exported to: {csv_path}")
                except Exception as e:
                    print(f"[csv_exporter] Error exporting Pond5 CSV: {e}")
    if "Depositphotos" in platforms and output_path:
        fmt = SHARED_FORMATS['Depositphotos']
        rows = []
        for file in files:
            rows.append(_depositphotos_format(file))
            if progress_callback:
                progress_callback()
        if rows:
            key = "Depositphotos"
            if key not in name_map:
                print(f"[csv_exporter] Missing base name for {key} in name_map, skipping")
            else:
                csv_filename = generate_export_filename(name_map[key], output_path)
                csv_path = os.path.join(output_path, csv_filename)
                try:
                    row_data = [[row.get(k, '') for k in fmt['fields']] for row in rows]
                    _write_csv_with_custom_quoting(csv_path, fmt['header'], row_data, fmt['delimiter'], fmt['quote_fields'], fmt['quote_header'])
                    print(f"[csv_exporter] Depositphotos CSV exported to: {csv_path}")
                except Exception as e:
                    print(f"[csv_exporter] Error exporting Depositphotos CSV: {e}")
    if "Canva" in platforms and output_path:
        fmt = SHARED_FORMATS['Canva']
        rows = []
        for file in files:
            rows.append(_canva_format(file))
            if progress_callback:
                progress_callback()
        if rows:
            key = "Canva"
            if key not in name_map:
                print(f"[csv_exporter] Missing base name for {key} in name_map, skipping")
            else:
                csv_filename = generate_export_filename(name_map[key], output_path)
                csv_path = os.path.join(output_path, csv_filename)
                try:
                    row_data = [[row.get(k, '') for k in fmt['fields']] for row in rows]
                    _write_csv_with_custom_quoting(csv_path, fmt['header'], row_data, fmt['delimiter'], fmt['quote_fields'], fmt['quote_header'])
                    print(f"[csv_exporter] Canva CSV exported to: {csv_path}")
                except Exception as e:
                    print(f"[csv_exporter] Error exporting Canva CSV: {e}")
    if "MiriCanvas" in platforms and output_path:
        fmt = SHARED_FORMATS['MiriCanvas']
        rows = []
        for file in files:
            rows.append(_miricanvas_format(file))
            if progress_callback:
                progress_callback()
        if rows:
            key = "MiriCanvas"
            if key not in name_map:
                print(f"[csv_exporter] Missing base name for {key} in name_map, skipping")
            else:
                csv_filename = generate_export_filename(name_map[key], output_path)
                csv_path = os.path.join(output_path, csv_filename)
                try:
                    row_data = [[row.get(k, '') for k in fmt['fields']] for row in rows]
                    _write_csv_with_custom_quoting(csv_path, fmt['header'], row_data, fmt['delimiter'], fmt['quote_fields'], fmt['quote_header'])
                    print(f"[csv_exporter] MiriCanvas CSV exported to: {csv_path}")
                except Exception as e:
                    print(f"[csv_exporter] Error exporting MiriCanvas CSV: {e}")

