import csv
import os
from database.db_operation import ImageTeaDB
from PySide6.QtWidgets import QFileDialog, QMessageBox
from helpers.csv_exporter import SHARED_FORMATS

def import_csv_interactive(parent=None):
    file_path, _ = QFileDialog.getOpenFileName(parent, "Select CSV File", "", "CSV Files (*.csv)")
    if not file_path:
        return None
    try:
        stats = import_csv_metadata(file_path)
        total = stats['total']
        successful = stats['successful']
        failed = stats['failed']
        message = f"Import completed.\n\nTotal files: {total}\nSuccessful: {successful}\nFailed: {failed}"

        success_examples = stats.get('success_examples', [])
        if success_examples:
            message += "\n\nSuccessful files:\n" + "\n".join(success_examples)
            if successful > len(success_examples):
                message += f"\n...and {successful - len(success_examples)} other successful files"

        failures = stats.get('failures', [])
        if failures:
            show_count = 3
            message += "\n\nFailed files:\n" + "\n".join(failures[:show_count])
            if len(failures) > show_count:
                message += f"\n...and {len(failures) - show_count} other failed files"

        QMessageBox.information(parent, "Import Result", message)
        parent.table.refresh_table()
        return stats
    except Exception as e:
        print(f"[csv_importer] Import error: {e}")
        QMessageBox.critical(parent, "Import Error", f"Import failed: {str(e)}")
        return None

def import_csv_metadata(csv_path):
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"CSV file does not exist: {csv_path}")
    
    db = ImageTeaDB()
    files = db.get_all_files()
    filename_to_filepath = {file[2]: file[1] for file in files}
    
    stats = {
        'total': 0,
        'successful': 0,
        'failed': 0,
        'failures': [],
        'success_examples': []
    }

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        first_line = f.readline()
        if not first_line:
            raise ValueError('CSV is empty')

        basename = os.path.basename(csv_path)
        image_tea_marker = '_Image_Tea_Metadata_'
        selected_platform = None
        delimiter = None
        fmt = None

        if image_tea_marker in basename:
            platform_prefix = basename.split(image_tea_marker, 1)[0]
            image_tea_platform = platform_prefix.replace('_', ' ')
            if image_tea_platform not in SHARED_FORMATS:
                raise ValueError(f"Unknown Image Tea export platform: {image_tea_platform}")
            fmt = SHARED_FORMATS[image_tea_platform]
            delimiter = fmt['delimiter']

            f.seek(0)
            reader = csv.reader(f, delimiter=delimiter)
            header = next(reader)
            if [h.strip() for h in header] != [h for h in fmt['header']]:
                raise ValueError(f"CSV header does not match expected exporter header for platform {image_tea_platform}. Expected: {fmt['header']} Got: {header}")

            selected_platform = image_tea_platform
            print(f"[csv_importer] Detected Image Tea export for platform: '{selected_platform}' (basename={basename}), delimiter='{delimiter}'")
        else:
            candidate_delims = sorted(set(v['delimiter'] for v in SHARED_FORMATS.values()))
            header = None
            first_line_parsed = False
            for d in candidate_delims:
                try:
                    parsed = next(csv.reader([first_line], delimiter=d))
                except Exception:
                    continue
                parsed_strip = [h.strip() for h in parsed]
                for platform_name, fmt_candidate in SHARED_FORMATS.items():
                    if parsed_strip == fmt_candidate['header']:
                        selected_platform = platform_name
                        delimiter = d
                        fmt = fmt_candidate
                        header = parsed
                        first_line_parsed = True
                        break
                if first_line_parsed:
                    break

            if not selected_platform:
                raise ValueError('CSV header does not match any supported exporter format. Importer only accepts CSVs with exact exporter headers.')

            print(f"[csv_importer] Header-only detection: selected platform '{selected_platform}', delimiter='{delimiter}'")

        f.seek(0)
        reader = csv.reader(f, delimiter=delimiter)
        header = next(reader)
        expected_header = [h for h in fmt['header']]
        if [h.strip() for h in header] != [h for h in expected_header]:
            raise ValueError(f"CSV header does not match expected exporter header for platform {selected_platform}. Expected: {expected_header} Got: {header}")

        filename_index = None
        for i, key in enumerate(fmt['fields']):
            if 'filename' in key.lower() or 'oldfilename' in key.lower():
                filename_index = i
                break
        if filename_index is None:
            raise ValueError('Exporter format does not define a filename field')

        for row in reader:
            stats['total'] += 1
            if len(row) < len(fmt['fields']):
                row = row + [''] * (len(fmt['fields']) - len(row))
            filename = row[filename_index].strip()
            if not filename:
                stats['failed'] += 1
                stats['failures'].append(f"Row {stats['total']}: Missing filename")
                print(f"[csv_importer] Row {stats['total']} missing filename")
                continue
            if filename not in filename_to_filepath:
                stats['failed'] += 1
                stats['failures'].append(f"Row {stats['total']}: Filename '{filename}' not found in database")
                print(f"[csv_importer] Row {stats['total']}: Filename '{filename}' not found in DB")
                continue
            filepath = filename_to_filepath[filename]
            title = ''
            if 'title' in fmt['fields']:
                title = row[fmt['fields'].index('title')].strip()
            description = ''
            if 'description' in fmt['fields']:
                description = row[fmt['fields'].index('description')].strip()
            tags = ''
            for keyname in ['keywords', 'keywords', 'tag', 'tags']:
                if keyname in fmt['fields']:
                    tags = row[fmt['fields'].index(keyname)].strip()
                    break
            try:
                db.update_metadata(filepath, title, description, tags)
                stats['successful'] += 1
                if len(stats['success_examples']) < 3:
                    stats['success_examples'].append(filename)
            except Exception as e:
                stats['failed'] += 1
                stats['failures'].append(f"Row {stats['total']}: Error updating metadata for '{filename}': {str(e)}")
                print(f"[csv_importer] Error updating metadata for '{filename}': {e}")
    
    return stats
