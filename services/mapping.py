"""Mapping builder with lightweight caching and progress callbacks."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Tuple
import time

from photo_sorter.scanner import scan_images
from photo_sorter.extractor import extract_metadata
from photo_sorter.grouper import make_group_name
from photo_sorter.utils.paths import normalize_user_path

ProgressCallback = Callable[[int, int, Path], None]


@dataclass
class MappingResult:
    source: str
    built_at: float
    files: List[Path]
    groups: Dict[str, List[Path]]


class MappingCache:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._store: Dict[str, MappingResult] = {}

    def get(self, source: str) -> MappingResult | None:
        entry = self._store.get(source)
        if not entry:
            return None
        if time.time() - entry.built_at > self.ttl:
            self._store.pop(source, None)
            return None
        return entry

    def set(self, source: str, result: MappingResult) -> None:
        self._store[source] = result


cache = MappingCache()


def build_mapping(source_path: str, progress_cb: ProgressCallback | None = None, use_cache: bool = True) -> Tuple[Dict[str, List[Path]], List[Path]]:
    normalized = normalize_user_path(source_path)
    if use_cache:
        cached = cache.get(normalized)
        if cached:
            return cached.groups, cached.files

    groups: Dict[str, List[Path]] = {}
    files: List[Path] = []

    source = Path(normalized)
    scan_list = list(scan_images(source))
    total = len(scan_list)
    if progress_cb:
        try:
            progress_cb(0, total, source)
        except Exception:
            pass

    for idx, path in enumerate(scan_list, start=1):
        files.append(path)
        try:
            meta = extract_metadata(path)
        except Exception:
            meta = {}
        try:
            group = make_group_name(meta)
        except Exception:
            group = "NoLocation"
        groups.setdefault(group, []).append(path)
        if progress_cb:
            try:
                progress_cb(idx, total, path)
            except Exception:
                pass

    result = MappingResult(source=normalized, built_at=time.time(), files=files, groups=groups)
    cache.set(normalized, result)
    return groups, files
