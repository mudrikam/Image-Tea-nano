from PySide6.QtCore import QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent


class DragDropPathMixin:
    """Mixin providing drag-and-drop support for QLineEdit path inputs."""
    
    @staticmethod
    def make_drag_enter_handler(widget):
        """Create a drag enter event handler for a widget."""
        def handler(event: QDragEnterEvent):
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
            else:
                event.ignore()
        return handler
    
    @staticmethod
    def make_drop_handler(widget, field_type, on_drop_callback=None):
        """Create a drop event handler for a widget.
        
        Args:
            widget: The QLineEdit to update with the dropped path
            field_type: One of 'source', 'output', 'overlay', 'folder', 'file'
            on_drop_callback: Optional callback function(path) to invoke after setting path
        """
        def handler(event: QDropEvent):
            if event.mimeData().hasUrls():
                urls = event.mimeData().urls()
                if urls:
                    path = urls[0].toLocalFile()
                    
                    # Sanitize path (remove quotes)
                    path = DragDropPathMixin._sanitize_path(path)
                    
                    # Determine the path to use based on field type
                    target_path = DragDropPathMixin._resolve_dropped_path(path, field_type)
                    
                    if target_path:
                        widget.setText(target_path)
                        if on_drop_callback:
                            on_drop_callback(target_path)
                        event.acceptProposedAction()
                    else:
                        event.ignore()
                else:
                    event.ignore()
            else:
                event.ignore()
        return handler
    
    @staticmethod
    def _sanitize_path(path: str) -> str:
        """Remove surrounding quotes from path."""
        if not isinstance(path, str):
            return path
        t = path.strip()
        if len(t) >= 2 and ((t[0] == '"' and t[-1] == '"') or (t[0] == "'" and t[-1] == "'")):
            return t[1:-1]
        return t
    
    @staticmethod
    def _resolve_dropped_path(path: str, field_type: str):
        """Resolve the dropped path based on field type.
        
        Returns the appropriate path or None if invalid.
        """
        import os
        
        if field_type in ('source', 'output', 'folder'):
            # For folder fields, accept folder directly
            if os.path.isdir(path):
                return path
            elif os.path.isfile(path):
                # If file dropped on folder field, use its directory
                return os.path.dirname(path)
            return None
        
        elif field_type == 'overlay':
            # For overlay, accept PNG file specifically
            if os.path.isfile(path) and path.lower().endswith('.png'):
                return path
            return None
        
        elif field_type == 'file':
            # For file fields, accept file or folder
            if os.path.isfile(path):
                return path
            elif os.path.isdir(path):
                return path
            return None
        
        return None