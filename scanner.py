"""Scanner: walk a source directory and yield image file paths."""
from pathlib import Path
from typing import Iterator, List

DEFAULT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".webp", ".heic", ".mov", ".mp4"}


def scan_images(source: str, extensions: List[str] = None, recursive: bool = True) -> Iterator[Path]:
    """Yield Path objects for files that look like images/videos in `source`.

    Args:
        source: directory to scan
        extensions: optional list of extensions to include (case-insensitive)
        recursive: whether to walk subdirectories
    """
    p = Path(source)
    if not p.exists():
        raise FileNotFoundError(f"Source path not found: {source}")

    exts = {e.lower() for e in (extensions or [])} or DEFAULT_EXTENSIONS

    if recursive:
        iterator = p.rglob("*")
    else:
        iterator = p.iterdir()

    for fp in iterator:
        if not fp.is_file():
            continue
        if fp.suffix.lower() in exts:
            yield fp
