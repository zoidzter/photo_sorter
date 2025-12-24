"""Background preview builder."""
from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Dict

from photo_sorter.services.job_store import preview_jobs, now_ts
from photo_sorter.services.mapping import build_mapping
from photo_sorter.dashboard_support import generate_thumbnail_bytes


def _to_preview_payload(groups: Dict[str, list], files: list) -> Dict[str, object]:
    payload = {"total": len(files), "groups": []}
    for name, paths in groups.items():
        samples = []
        for p in paths[:3]:
            b64 = generate_thumbnail_bytes(Path(p))
            if b64:
                samples.append(f"data:image/jpeg;base64,{b64}")
        payload["groups"].append({"name": name, "count": len(paths), "samples": samples})
    return payload


def _worker(job_id: str, source: str):
    preview_jobs.update(job_id, state="running", start_time=now_ts())

    def progress(done: int, total: int, path: Path):
        preview_jobs.update(job_id,
                             total=total,
                             processed=done,
                             current_file=str(path),
                             last_update=now_ts())

    try:
        groups, files = build_mapping(source, progress_cb=progress)
        preview_jobs.update(job_id,
                             result=_to_preview_payload(groups, files),
                             state="done",
                             finished_time=now_ts())
    except Exception as exc:
        preview_jobs.update(job_id, state="error", error=str(exc), finished_time=now_ts())


def start_preview_job(source: str) -> str:
    job_id = uuid.uuid4().hex
    preview_jobs.create(job_id, {"state": "pending", "processed": 0, "total": 0, "errors": []})
    threading.Thread(target=_worker, args=(job_id, source), daemon=True).start()
    return job_id
