"""Visual utilities: perceptual hashing for near-duplicate detection."""
from pathlib import Path
from typing import Optional

try:
    import imagehash
    from PIL import Image
except Exception:
    imagehash = None
    Image = None
import json
import time

# persistent cache mapping file path -> {"phash": hexstr, "mtime": float}
CACHE_PATH = Path.home() / ".photo_sorter_phash.json"
_phash_cache = {}


def _load_cache():
    global _phash_cache
    try:
        if CACHE_PATH.exists():
            _phash_cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        _phash_cache = {}


def _save_cache():
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(_phash_cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def compute_phash(path: Path, hash_size: int = 16) -> Optional[object]:
    """Compute a perceptual hash for the image at `path`.

    Returns an `imagehash.ImageHash` object when available, otherwise None.
    """
    if imagehash is None or Image is None:
        return None
    try:
        with Image.open(path) as img:
            ph = imagehash.phash(img, hash_size=hash_size)
            return ph
    except Exception:
        return None


def hamming_distance(h1, h2) -> Optional[int]:
    """Return Hamming distance between two ImageHash objects, or None."""
    try:
        return int(h1 - h2)
    except Exception:
        return None


def get_phash_for_path(path: Path, hash_size: int = 16):
    """Get phash for path, using persistent cache keyed by path and mtime.

    Returns an imagehash.ImageHash object or None.
    """
    if imagehash is None or Image is None:
        return None
    path = Path(path)
    if not _phash_cache:
        _load_cache()
    try:
        mtime = path.stat().st_mtime
    except Exception:
        mtime = None

    key = str(path)
    entry = _phash_cache.get(key)
    if entry and mtime is not None and float(entry.get("mtime")) == float(mtime):
        hexstr = entry.get("phash")
        try:
            return imagehash.hex_to_hash(hexstr)
        except Exception:
            pass

    # compute and cache
    ph = compute_phash(path, hash_size=hash_size)
    if ph is not None:
        try:
            _phash_cache[key] = {"phash": ph.__str__(), "mtime": mtime}
            _save_cache()
        except Exception:
            pass
    return ph
