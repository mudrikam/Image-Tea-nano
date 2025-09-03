from PySide6.QtWidgets import QFileDialog
import os
from helpers.metadata_helper.metadata_operation import read_metadata_pyexiv2, read_metadata_video
from dialogs.import_progress_dialog import ImportProgressDialog

try:
    from PIL import Image
    PILLOW_FORMATS = set()
    for ext, fmt in Image.registered_extensions().items():
        PILLOW_FORMATS.add(ext.lower())
except ImportError:
    PILLOW_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp', '.eps', '.svg', '.pdf'}

def import_files(parent, db, file_paths=None):
    if file_paths is None:
        home_dir = os.path.expanduser("~")
        video_exts = {'.mp4', '.mpeg', '.mov', '.avi', '.flv', '.mpg', '.webm', '.wmv', '.3gp', '.3gpp'}
        extra_exts = {'.svg', '.eps', '.pdf'}
        all_exts = sorted(PILLOW_FORMATS | video_exts | extra_exts)
        filter_str = "Images/Videos (" + " ".join(f"*{ext}" for ext in all_exts) + ")"
        files, _ = QFileDialog.getOpenFileNames(
            parent,
            "Select Images or Videos",
            home_dir,
            filter_str
        )
    else:
        files = file_paths
    
    if not files:
        return False
        
    # Tampilkan progress dialog dan jalankan import
    progress_dialog = ImportProgressDialog(files, db, parent)
    progress_dialog.start_import()
    result = progress_dialog.exec()
    
    # Return True jika import berhasil (dialog accepted atau ada file yang berhasil diimport)
    return result == ImportProgressDialog.Accepted or progress_dialog.imported_files > 0
