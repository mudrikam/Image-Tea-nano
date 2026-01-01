"""
Platform format validation helper for Action Sequencer
"""

class PlatformFormatValidator:
    """Validate export formats against platform capabilities"""
    
    PHOTOSHOP_FORMATS = {'PNG', 'JPG', 'JPEG', 'PSD', 'PDF', 'TIFF'}
    ILLUSTRATOR_FORMATS = {'PNG', 'JPG', 'JPEG', 'AI', 'EPS', 'PDF', 'SVG'}
    
    @staticmethod
    def is_format_supported(platform_name, export_format):
        """Check if export format is supported by platform
        
        Args:
            platform_name: Platform name (e.g., 'Photoshop', 'Illustrator')
            export_format: Export format (e.g., 'PNG', 'EPS')
        
        Returns:
            bool: True if format is supported
        """
        if not export_format:
            return True
        
        format_upper = export_format.upper()
        platform_lower = platform_name.lower()
        
        if 'photoshop' in platform_lower:
            return format_upper in PlatformFormatValidator.PHOTOSHOP_FORMATS
        elif 'illustrator' in platform_lower:
            return format_upper in PlatformFormatValidator.ILLUSTRATOR_FORMATS
        
        return True
    
    @staticmethod
    def get_supported_formats(platform_name):
        """Get list of supported formats for platform
        
        Args:
            platform_name: Platform name
        
        Returns:
            set: Supported formats
        """
        platform_lower = platform_name.lower()
        
        if 'photoshop' in platform_lower:
            return PlatformFormatValidator.PHOTOSHOP_FORMATS
        elif 'illustrator' in platform_lower:
            return PlatformFormatValidator.ILLUSTRATOR_FORMATS
        
        return set()
    
    @staticmethod
    def get_unsupported_message(platform_name, export_format):
        """Get user-friendly message for unsupported format
        
        Args:
            platform_name: Platform name
            export_format: Export format
        
        Returns:
            str: User-friendly error message
        """
        supported = PlatformFormatValidator.get_supported_formats(platform_name)
        supported_list = ', '.join(sorted(supported))
        
        return (f"{platform_name} does not support {export_format} format.\n\n"
                f"Supported formats: {supported_list}\n\n"
                f"Please choose an export action with a supported format.")
