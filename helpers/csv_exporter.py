from database.db_operation import ImageTeaDB
import os
import datetime
import re

def get_next_index(base_name, output_path):
    if not os.path.isdir(output_path):
        raise FileNotFoundError(f"Output path does not exist: {output_path}")
    base = base_name
    try:
        if base.lower().endswith('.csv'):
            base = base[:-4]
        if not base.endswith('_'):
            base = base + '_'
        idx = 1
        while True:
            name_lower = f"{base}{idx:03d}.csv"
            path_lower = os.path.join(output_path, name_lower)
            name_upper = f"{base}{idx:03d}.CSV"
            path_upper = os.path.join(output_path, name_upper)
            if not (os.path.exists(path_lower) or os.path.exists(path_upper)):
                return idx
            idx += 1
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

def _freepik_format(file):
    filename = file[2]
    title = file[3] if file[3] is not None else ""
    tags = file[5] if file[5] is not None else ""
    prompt = ""
    model = ""
    return f'"{filename}";"{title}";"{tags}";"{prompt}";"{model}"'

def _adobe_stock_format(file, adobe_map, category_mapping):
    filename = file[2]
    title = file[3] if file[3] is not None else ""
    tags = file[5] if file[5] is not None else ""
    file_id = file[0]
    adobe_cat_id = None
    for mapping in category_mapping:
        if mapping['file_id'] == file_id and mapping['platform'] == 'adobe_stock':
            adobe_cat_id = mapping['category_id']
            break
    category_text = str(adobe_cat_id) if adobe_cat_id is not None else ""
    return f'{filename},"{title}","{tags}","{category_text}",'

def _shutterstock_format(file, shutterstock_map, category_mapping, db):
    filename = file[2]
    description = file[4] if file[4] is not None else ""
    tags = file[5] if file[5] is not None else ""
    file_id = file[0]
    primary = None
    secondary = None
    for mapping in category_mapping:
        if mapping['file_id'] == file_id and mapping['platform'] == 'shutterstock':
            if mapping['category_name'].endswith('(primary)'):
                primary = mapping['category_id']
            elif mapping['category_name'].endswith('(secondary)'):
                secondary = mapping['category_id']
    categories = ""
    if primary and secondary:
        categories = f"{shutterstock_map.get(str(primary), '')},{shutterstock_map.get(str(secondary), '')}"
    elif primary:
        categories = shutterstock_map.get(str(primary), '')
    elif secondary:
        categories = shutterstock_map.get(str(secondary), '')
    
    illustration = "yes"
    try:
        file_types = db.get_file_types(file_id)
        if file_types:
            file_type = file_types[0][1]
            if file_type.lower() == "photo":
                illustration = "no"
            elif file_type.lower() == "illustration":
                illustration = "yes"
    except Exception as e:
        print(f"Error getting file type for file {file_id}: {e}")
    
    editorial = "no"
    mature_content = "no"
    return f'{filename},"{description}","{tags}","{categories}",{editorial},{mature_content},{illustration}'

def _123rf_format(file):
    filename = file[2]
    title = file[3] if file[3] is not None else ""
    description = file[4] if file[4] is not None else ""
    keywords = file[5] if file[5] is not None else ""
    country = ""
    return f'"{filename}","{title}","{description}","{keywords}","{country}"'

def _vecteezy_format(file):
    filename = file[2]
    title = file[3] if file[3] is not None else ""
    description = file[4] if file[4] is not None else ""
    keywords = file[5] if file[5] is not None else ""
    license_type = "Pro"
    return f'{filename},"{title}","{description}","{keywords}",{license_type}'

def _istock_format(file):
    filename = file[2]
    today = datetime.datetime.now()
    created_date = today.strftime("%m/%d/%Y")
    description = file[4] if file[4] is not None else ""
    country = ""
    title = file[3] if file[3] is not None else ""
    keywords = file[5] if file[5] is not None else ""
    poster_timecode = ""
    shot_speed = "Real Time"
    return f'{filename},"{description}","{country}","{title}","{keywords}","{poster_timecode}","{shot_speed}",{created_date}'

def _pond5_format(file):
    filename = file[2]
    title = file[3] if file[3] is not None else ""
    description = file[4] if file[4] is not None else ""
    keywords = file[5] if file[5] is not None else ""
    city = ""
    region = ""
    country = ""
    specifysource = ""
    modelreleased = ""
    propertyreleased = ""
    release = ""
    copyright_owner = ""
    price = ""
    editorial = ""
    return f'"{filename}","{title}","{description}","{keywords}","{city}","{region}","{country}","{specifysource}","{modelreleased}","{propertyreleased}","{release}","{copyright_owner}","{price}","{editorial}"'

def _depositphotos_format(file):
    filename = file[2]
    description = file[4] if file[4] is not None else ""
    keywords = file[5] if file[5] is not None else ""
    nudity = "no"
    editorial = "no"
    return f'"{filename}","{description}","{keywords}","{nudity}","{editorial}"'

def _canva_format(file):
    filename = file[2]
    title = file[3] if file[3] is not None else ""
    keywords = file[5] if file[5] is not None else ""
    artist = ""
    locale = "en"
    description = file[4] if file[4] is not None else ""
    return f'{filename},"{title}","{keywords}",{artist},{locale},"{description}"'

def _miricanvas_format(file):
    filename = file[2]
    # Remove extension for MiriCanvas
    filename_no_ext = re.sub(r'\.[^.]+$', '', filename)
    unique_id = ""
    element_name = file[3] if file[3] is not None else ""
    keywords = file[5] if file[5] is not None else ""
    tier = ""
    content_type = ""
    return f'"{filename_no_ext}","{unique_id}","{element_name}","{keywords}","{tier}","{content_type}"'

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
    shutterstock_map, adobe_map = db.get_category_maps()
    category_mapping = db.get_category_mapping()
    if "Freepik" in platforms and output_path:
        rows = []
        header = 'File name;Title;Keywords;Prompt;Model'
        for file in files:
            rows.append(_freepik_format(file))
            if progress_callback:
                progress_callback()
        if rows:
            if "Freepik" not in name_map:
                print("[csv_exporter] Missing base name for Freepik in name_map, skipping")
            else:
                csv_filename = generate_export_filename(name_map["Freepik"], output_path)
                csv_path = os.path.join(output_path, csv_filename)
                try:
                    with open(csv_path, "w", encoding="utf-8") as f:
                        f.write(header + "\n")
                        for row in rows:
                            f.write(row + "\n")
                    print(f"[csv_exporter] Freepik CSV exported to: {csv_path}")
                except Exception as e:
                    print(f"[csv_exporter] Error exporting Freepik CSV: {e}")
    if "Adobe Stock" in platforms and output_path:
        rows = []
        header = "Filename,Title,Keywords,Category,Releases"
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
                    with open(csv_path, "w", encoding="utf-8") as f:
                        f.write(header + "\n")
                        for row in rows:
                            f.write(row + "\n")
                    print(f"[csv_exporter] Adobe Stock CSV exported to: {csv_path}")
                except Exception as e:
                    print(f"[csv_exporter] Error exporting Adobe Stock CSV: {e}")
    if "Shutterstock" in platforms and output_path:
        rows = []
        header = "Filename,Description,Keywords,Categories,Editorial,Mature content,illustration"
        for file in files:
            rows.append(_shutterstock_format(file, shutterstock_map, category_mapping, db))
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
                    with open(csv_path, "w", encoding="utf-8") as f:
                        f.write(header + "\n")
                        for row in rows:
                            f.write(row + "\n")
                    print(f"[csv_exporter] Shutterstock CSV exported to: {csv_path}")
                except Exception as e:
                    print(f"[csv_exporter] Error exporting Shutterstock CSV: {e}")
    if "123RF" in platforms and output_path:
        rows = []
        header = '"oldfilename","123rf_filename","description","keywords","country"'
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
                    with open(csv_path, "w", encoding="utf-8") as f:
                        f.write(header + "\n")
                        for row in rows:
                            f.write(row + "\n")
                    print(f"[csv_exporter] 123rf CSV exported to: {csv_path}")
                except Exception as e:
                    print(f"[csv_exporter] Error exporting 123rf CSV: {e}")
    if "Vecteezy" in platforms and output_path:
        rows = []
        header = "Filename,Title,Description,Keywords,License"
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
                    with open(csv_path, "w", encoding="utf-8") as f:
                        f.write(header + "\n")
                        for row in rows:
                            f.write(row + "\n")
                    print(f"[csv_exporter] Vecteezy CSV exported to: {csv_path}")
                except Exception as e:
                    print(f"[csv_exporter] Error exporting Vecteezy CSV: {e}")
    if "iStock" in platforms and output_path:
        rows = []
        header = "file name,description,country,title,keywords,poster timecode,shot speed,date created"
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
                    with open(csv_path, "w", encoding="utf-8") as f:
                        f.write(header + "\n")
                        for row in rows:
                            f.write(row + "\n")
                    print(f"[csv_exporter] iStock CSV exported to: {csv_path}")
                except Exception as e:
                    print(f"[csv_exporter] Error exporting iStock CSV: {e}")
    if "Pond5" in platforms and output_path:
        rows = []
        header = '"OriginalFilename","Title","Description","Keywords","City","Region","Country","Specifysource","Modelreleased","Propertyreleased","Release","Copyright","Price","Editorial"'
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
                    with open(csv_path, "w", encoding="utf-8") as f:
                        f.write(header + "\n")
                        for row in rows:
                            f.write(row + "\n")
                    print(f"[csv_exporter] Pond5 CSV exported to: {csv_path}")
                except Exception as e:
                    print(f"[csv_exporter] Error exporting Pond5 CSV: {e}")
    if "Depositphotos" in platforms and output_path:
        rows = []
        header = '"Filename","description","Keywords","Nudity","Editorial"'
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
                    with open(csv_path, "w", encoding="utf-8") as f:
                        f.write(header + "\n")
                        for row in rows:
                            f.write(row + "\n")
                    print(f"[csv_exporter] Depositphotos CSV exported to: {csv_path}")
                except Exception as e:
                    print(f"[csv_exporter] Error exporting Depositphotos CSV: {e}")
    if "Canva" in platforms and output_path:
        rows = []
        header = "filename,title,keywords,Artist,locale,description"
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
                    with open(csv_path, "w", encoding="utf-8") as f:
                        f.write(header + "\n")
                        for row in rows:
                            f.write(row + "\n")
                    print(f"[csv_exporter] Canva CSV exported to: {csv_path}")
                except Exception as e:
                    print(f"[csv_exporter] Error exporting Canva CSV: {e}")
    if "MiriCanvas" in platforms and output_path:
        rows = []
        header = '"fileName","uniqueId","elementName","keywords","tier","contentType"'
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
                    with open(csv_path, "w", encoding="utf-8") as f:
                        f.write(header + "\n")
                        for row in rows:
                            f.write(row + "\n")
                    print(f"[csv_exporter] MiriCanvas CSV exported to: {csv_path}")
                except Exception as e:
                    print(f"[csv_exporter] Error exporting MiriCanvas CSV: {e}")

