"""Geocoder module: offline `reverse_geocoder` first, then `geopy` Nominatim fallback.

Caches results to a JSON file at the user's home directory to avoid repeated lookups.
"""
from typing import Optional
import json
from pathlib import Path
import time
import logging

CACHE_PATH = Path.home() / ".photo_sorter_geocache.json"

try:
    import reverse_geocoder as rg  # offline, fast city-level lookup
except Exception:
    rg = None

try:
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut, GeocoderServiceError
except Exception:
    Nominatim = None

_cache = {}
_last_geopy_call = 0.0


def _load_cache():
    global _cache
    try:
        if CACHE_PATH.exists():
            _cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        _cache = {}


def _save_cache():
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(_cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        logging.exception("Failed to write geocode cache")


def _geopy_reverse(lat: float, lon: float) -> Optional[str]:
    global _last_geopy_call
    if Nominatim is None:
        return None
    # respect polite rate limiting: at least 1 second between calls
    now = time.time()
    delta = now - _last_geopy_call
    if delta < 1.0:
        time.sleep(1.0 - delta)
    try:
        geolocator = Nominatim(user_agent="photo_sorter_app")
        loc = geolocator.reverse((lat, lon), language="en", addressdetails=True, exactly_one=True)
        _last_geopy_call = time.time()
        if not loc:
            return None
        addr = loc.raw.get("address", {})
        parts = []
        for key in ("city", "town", "village", "county", "state", "country"):
            v = addr.get(key)
            if v and v not in parts:
                parts.append(v)
        return ", ".join(parts) if parts else loc.address
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        logging.debug("Geopy reverse failed: %s", e)
        return None
    except Exception:
        logging.exception("Unexpected geopy error")
        return None


def reverse_geocode(lat: float, lon: float) -> Optional[str]:
    """Return a short place name (city, region, country) or None.

    Lookup order:
    1. Cache
    2. `reverse_geocoder` (offline)
    3. `geopy` Nominatim (online)
    """
    if lat is None or lon is None:
        return None
    key = f"{lat:.6f},{lon:.6f}"
    if not _cache:
        _load_cache()
    if key in _cache:
        return _cache[key]

    # Try offline reverse_geocoder first
    if rg is not None:
        try:
            results = rg.search((lat, lon), mode=1)
            if results:
                r = results[0]
                name = ", ".join(filter(None, [r.get("name"), r.get("admin1"), r.get("cc")]))
                _cache[key] = name
                _save_cache()
                return name
        except Exception:
            logging.debug("reverse_geocoder failed, falling back to geopy")

    # Fallback to geopy/Nominatim
    name = _geopy_reverse(lat, lon)
    if name:
        _cache[key] = name
        _save_cache()
        return name

    return None
