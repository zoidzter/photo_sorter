"""Grouper: produce filesystem-safe folder names from metadata."""
from __future__ import annotations

from datetime import datetime, date
from functools import lru_cache
from pathlib import Path
import json
import re
from typing import Optional, Dict, Any

INVALID_CHARS = re.compile(r'[<>:\"/|?*]')

from .events import detect_event

_CONFIG_PATH = Path(__file__).with_name("grouping_rules.json")


def _default_rules() -> Dict[str, Any]:
    return {
        "location_aliases": {},
        "event_overrides": {},
        "custom_events": [],
    }


@lru_cache(maxsize=1)
def _load_rules() -> Dict[str, Any]:
    base = _default_rules()
    if not _CONFIG_PATH.exists():
        return base
    try:
        raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return base

    aliases = {}
    for key, value in (raw.get("location_aliases") or {}).items():
        if isinstance(key, str) and isinstance(value, str):
            aliases[key.strip().lower()] = value.strip()

    overrides = {}
    for key, value in (raw.get("event_overrides") or {}).items():
        if isinstance(key, str) and isinstance(value, str):
            overrides[key.strip().lower()] = value.strip()

    custom_events = []
    for item in raw.get("custom_events") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        start = item.get("start")
        end = item.get("end") or start
        if not isinstance(name, str) or not isinstance(start, str):
            continue
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d").date()
            end_date = datetime.strptime(end, "%Y-%m-%d").date() if end else start_date
        except Exception:
            continue
        custom_events.append({
            "name": name.strip(),
            "start": start_date,
            "end": end_date,
            "location": (item.get("location") or "").strip().lower() or None,
        })

    base["location_aliases"] = aliases
    base["event_overrides"] = overrides
    base["custom_events"] = custom_events
    return base


def _apply_location_alias(place: str) -> str:
    rules = _load_rules()
    return rules["location_aliases"].get(place.lower(), place)


def _apply_event_override(label: str | None) -> str | None:
    if not label:
        return label
    rules = _load_rules()
    lowered = label.lower()
    overridden = rules["event_overrides"].get(lowered)
    return overridden or label


def _match_custom_event(dt: date | None, place: str | None) -> str | None:
    if not dt:
        return None
    place_key = place.lower() if place else None
    rules = _load_rules()
    for item in rules["custom_events"]:
        if item["start"] <= dt <= item["end"]:
            loc = item.get("location")
            if loc and loc != place_key:
                continue
            return item["name"]
    return None


def _sanitize(name: str) -> str:
    if not name:
        return "Unknown"
    # replace invalid chars with underscore, trim whitespace
    s = INVALID_CHARS.sub("_", name)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def make_group_name(meta: Dict) -> str:
    """Return a folder name in the format 'YYYYMon_Location[_Event]'.

    Example: '2025Dec_Dublin_EnzoBirthday'
    Location is taken as the first token of the reverse-geocoded place (city) with
    spaces removed to keep the folder compact. Event label is appended if present.
    """
    dt: Optional[datetime] = meta.get("datetime")
    gps = meta.get("gps")

    if dt:
        year = dt.strftime("%Y")
        mon = dt.strftime("%b")  # short month name, e.g. Dec
    else:
        # fallback values
        year = "unknown"
        mon = "Mon"

    # attempt to use a provided place label (if geocoder added it to meta)
    place = meta.get("place")
    if not place and gps:
        try:
            from .geocoder import reverse_geocode
            place = reverse_geocode(gps[0], gps[1])
        except Exception:
            place = None

    place = place or "NoLocation"
    place = _sanitize(place)
    # take first token before comma (city)
    place_token = place.split(",")[0].strip()
    place_token = _apply_location_alias(place_token)
    place_token_compact = place_token.replace(" ", "")

    # detect event
    event_label = None
    if dt:
        event_label = _match_custom_event(dt.date(), place_token)
        if not event_label:
            try:
                event_label = detect_event(dt.date())
            except Exception:
                event_label = None
    event_label = _apply_event_override(event_label)

    parts = [f"{year}{mon}", place_token_compact]
    if event_label:
        parts.append(event_label)
    return "_".join(parts)
