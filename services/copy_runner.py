"""Async copy job runner."""
from __future__ import annotations

import threading
import uuid
import shutil
import re
from pathlib import Path
from typing import Dict, List
import time

from photo_sorter.copier import copy_file
from photo_sorter.services.mapping import build_mapping
from photo_sorter.services.job_store import copy_jobs, now_ts
from photo_sorter.utils.paths import normalize_user_path, display_path

_DUP_LABEL = re.compile(r"[\\/:*?\"<>|]+")


def _safe_label(value: str | None) -> str:
    if not value:
        return "Ungrouped"
    return _DUP_LABEL.sub("_", value)


def _copy_duplicates(src: Path, dup_dir: Path, group_label: str, job_id: str):
    group_dir = dup_dir / _safe_label(group_label)
    group_dir.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(src, group_dir / src.name)
    except Exception as exc:
        copy_jobs.update(job_id, errors=[*(copy_jobs.get(job_id) or {}).get("errors", []), f"Duplicate copy failed: {exc}"])


def _run(job_id: str, source: str, dest: str, group_name: str | None):
    try:
        mapping, files = build_mapping(source)
    except Exception as exc:
        copy_jobs.update(job_id, state="error", error=str(exc))
        return

    total = len(files)
    copy_jobs.update(job_id,
                     total=total,
                     processed=0,
                     copied=0,
                     failed=0,
                     duplicates=0,
                     state="running",
                     start_time=now_ts(),
                     last_update=now_ts())
    dest_root = Path(normalize_user_path(dest))
    dest_root.mkdir(parents=True, exist_ok=True)
    copy_jobs.update(job_id,
                     dest=str(dest_root),
                     dest_display=display_path(str(dest_root)))

    dup_root: Path | None = None

    groups_to_run = [group_name] if group_name else list(mapping.keys())
    processed = copied = failed = duplicates = 0

    for group in groups_to_run:
        for path in mapping.get(group, []):
            processed += 1
            copy_jobs.update(job_id, processed=processed, current_group=group, current_file=str(path), last_update=now_ts())
            try:
                dest_path, status = copy_file(path, dest_root / group, dry_run=False, return_status=True)
            except Exception as exc:
                failed += 1
                _record_error(job_id, f"Copy failed for {path}: {exc}")
                copy_jobs.update(job_id, failed=failed)
                continue

            if status == "skipped_identical":
                duplicates += 1
                copy_jobs.update(job_id, duplicates=duplicates)
                if dup_root is None:
                    year = time.strftime("%Y")
                    dup_root = dest_root / f"{year}_duplicates"
                    dup_root.mkdir(parents=True, exist_ok=True)
                    copy_jobs.update(job_id,
                                     duplicates_dir=str(dup_root),
                                     duplicates_dir_display=display_path(str(dup_root)))
                _copy_duplicates(path, dup_root, group, job_id)
            else:
                copied += 1
                copy_jobs.update(job_id, copied=copied)

    copy_jobs.update(job_id,
                     state="done",
                     current_file=None,
                     current_group=None,
                     finished_time=now_ts())


def _record_error(job_id: str, message: str) -> None:
    job = copy_jobs.get(job_id) or {}
    errors = job.get("errors", [])
    errors.append(message)
    copy_jobs.update(job_id, errors=errors)


def start_copy_job(source: str, dest: str, group: str | None = None) -> str:
    job_id = uuid.uuid4().hex
    copy_jobs.create(job_id, {"state": "pending", "errors": []})
    threading.Thread(target=_run, args=(job_id, source, dest, group), daemon=True).start()
    return job_id
