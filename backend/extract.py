from .extract_modules.scanner import scan_progress, scan_and_update, get_scan_progress

# Export these for background thread or router usage
__all__ = ["scan_progress", "scan_and_update", "get_scan_progress"]
