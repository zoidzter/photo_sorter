"""Photo Sorter package - core modules for scanning, extracting metadata, grouping and copying photos."""

from .scanner import scan_images
from .extractor import extract_metadata

# Optional modules; may be implemented later
try:
    from .grouper import make_group_name
    from .copier import copy_file
    from .geocoder import reverse_geocode
except Exception:
    # Provide placeholders if modules aren't ready yet
    def make_group_name(meta):
        return None

    def copy_file(src, dest, dry_run=False):
        raise NotImplementedError("copyer not implemented")

    def reverse_geocode(lat, lon):
        return None

__all__ = ["scan_images", "extract_metadata", "make_group_name", "copy_file", "reverse_geocode"]
