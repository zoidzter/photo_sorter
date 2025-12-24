"""Thread-safe job store utilities."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any
import threading
import time


def now_ts() -> int:
    return int(time.time())


@dataclass
class Job:
    job_id: str
    data: Dict[str, Any] = field(default_factory=dict)


class JobStore:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, job_id: str, initial: Dict[str, Any] | None = None) -> Job:
        with self._lock:
            job = Job(job_id=job_id, data=initial.copy() if initial else {})
            self._jobs[job_id] = job
            return job

    def update(self, job_id: str, **kwargs) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.data.update(kwargs)

    def get(self, job_id: str) -> Dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.data.copy() if job else None

    def raw(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)


preview_jobs = JobStore()
copy_jobs = JobStore()
