"""Path normalization helpers for cross-platform (Windows/WSL) usage."""
from __future__ import annotations

from pathlib import Path
import os
import re
from functools import lru_cache

_WINDOWS_DRIVE_PATTERN = re.compile(r"^([A-Za-z]):\\(.*)")
_WSL_PATTERN = re.compile(r"^/mnt/([a-zA-Z])/(.*)")
_LEADING_SLASH_DRIVE_PATTERN = re.compile(r"^/+([A-Za-z]:[\\/].*)")


def _windows_to_wsl(path: str) -> str:
    match = _WINDOWS_DRIVE_PATTERN.match(path)
    if not match:
        return path
    drive = match.group(1).lower()
    rest = match.group(2).replace('\\', '/')
    return f"/mnt/{drive}/{rest}"


def _wsl_to_windows(path: str) -> str:
    match = _WSL_PATTERN.match(path)
    if not match:
        return path
    drive = match.group(1).upper()
    rest = match.group(2).replace('/', '\\')
    return f"{drive}:\\{rest}"


def normalize_user_path(value: str | None) -> str | None:
    """Normalize a user-supplied path for the current runtime."""
    if not value:
        return value

    value = os.path.expanduser(value.strip())
    if not value:
        return value

    if os.name == 'posix':
        try:
            return _windows_to_wsl(value)
        except Exception:
            return value

    # Windows-specific cleanup so `/C:/Users/...` and `/mnt/c/...` work
    match = _LEADING_SLASH_DRIVE_PATTERN.match(value)
    if match:
        value = match.group(1)
    value = _wsl_to_windows(value)
    return value.replace('/', '\\')


def display_path(value: str | None) -> str | None:
    if not value:
        return value
    return _wsl_to_windows(value)


@lru_cache(maxsize=4)
def default_start_path() -> str:
    """Best-effort default explorer root."""
    if os.name == 'posix' and os.path.exists('/mnt/c/Users'):
        cwd = os.getcwd()
        match = re.search(r'/mnt/c/Users/([^/]+)', cwd)
        if match:
            candidate = f"/mnt/c/Users/{match.group(1)}"
            if os.path.isdir(candidate):
                return candidate
        try:
            candidates = [
                d for d in os.listdir('/mnt/c/Users')
                if os.path.isdir(os.path.join('/mnt/c/Users', d))
                and d not in {'All Users', 'Default', 'Default User', 'Public', 'desktop.ini'}
            ]
            if candidates:
                return os.path.join('/mnt/c/Users', candidates[0])
        except Exception:
            pass
    return os.path.expanduser('~')
