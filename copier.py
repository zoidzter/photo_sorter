"""Copier: copy files into grouped folders with conflict resolution."""
from pathlib import Path
import shutil
import hashlib
import logging


def _hash_file(path: Path, block_size: int = 65536) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(block_size), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_file(src: Path, dest_dir: Path, dry_run: bool = False, return_status: bool = False):
    """Copy `src` into `dest_dir`. Returns destination Path.

    Behavior:
    - Create `dest_dir` if needed
    - If a file with same name exists and is identical (size+md5), skip
    - If a file with same name exists but differs, append suffix `_1`, `_2`, ...
    """
    src = Path(src)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name

    if dest.exists():
        try:
            if dest.stat().st_size == src.stat().st_size:
                src_hash = _hash_file(src)
                dest_hash = _hash_file(dest)
                if src_hash == dest_hash:
                    logging.info("Skipping identical file: %s", src)
                    if return_status:
                        return dest, "skipped_identical"
                    return dest
        except Exception:
            pass

        # find non-conflicting name
        base = src.stem
        suf = src.suffix
        i = 1
        while dest.exists():
            dest = dest_dir / f"{base}_{i}{suf}"
            i += 1

    if dry_run:
        logging.info("Dry run: would copy %s -> %s", src, dest)
        if return_status:
            return dest, "dryrun"
        return dest

    shutil.copy2(src, dest)
    logging.info("Copied %s -> %s", src, dest)
    if return_status:
        # If the dest name differs from src.name it was renamed to avoid conflict
        if dest.name != src.name:
            return dest, "renamed"
        return dest, "copied"
    return dest
