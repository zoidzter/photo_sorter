"""Shared helpers used by dashboard routes and services."""
from __future__ import annotations

from pathlib import Path
import base64
import io
from PIL import Image


def generate_thumbnail_bytes(path: Path, max_size=(300, 300)):
    try:
        img = Image.open(path)
        img.convert("RGB")
        img.thumbnail(max_size)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("ascii")
    except Exception:
        return None
