"""Extractor: read EXIF metadata (date/time, GPS) from image files.

This module prefers Pillow + piexif when available, and falls back to file modification time.
"""
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict
import os

try:
    from PIL import Image
    import piexif
except Exception:
    Image = None
    piexif = None

# Optional HEIC support: try to register a HEIF opener for Pillow, or
# use pyheif to extract EXIF bytes when Pillow can't open HEIC files.
try:
    import pillow_heif  # type: ignore
    try:
        pillow_heif.register_heif_opener()
    except Exception:
        pass
except Exception:
    pillow_heif = None

try:
    import pyheif  # type: ignore
except Exception:
    pyheif = None

try:
    import exifread
except Exception:
    exifread = None

def _dms_to_decimal(dms, ref):
    # dms is a tuple of tuples like ((deg_num, deg_den), (min_num, min_den), (sec_num, sec_den))
    def to_float(t):
        num, den = t
        return float(num) / float(den) if den else float(num)

    deg = to_float(dms[0])
    minute = to_float(dms[1])
    sec = to_float(dms[2])
    dec = deg + (minute / 60.0) + (sec / 3600.0)
    if ref in ("S", "W"):
        dec = -dec
    return dec


def extract_metadata(path: Path) -> Dict:
    """Extracts metadata: returns dict with keys `datetime` (datetime) and `gps` (lat, lon) or None.

    The function never raises on missing EXIF; it will fallback to file mtime.
    """
    path = Path(path)
    meta = {"datetime": None, "gps": None}

    # Try Pillow + piexif if available
    if Image is not None:
        try:
            with Image.open(path) as img:
                exif_bytes = img.info.get("exif")
                if exif_bytes and piexif is not None:
                    exif = piexif.load(exif_bytes)
                else:
                    exif = None

                # DateTimeOriginal
                try:
                    dto = None
                    if exif:
                        dto = exif.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal)
                        if dto:
                            if isinstance(dto, bytes):
                                dto = dto.decode(errors="ignore")
                    if not dto:
                        dto = img.info.get("DateTime")
                    if dto:
                        # common format: 'YYYY:MM:DD HH:MM:SS'
                        dto = dto.replace(b"\x00", b"").decode() if isinstance(dto, bytes) else str(dto)
                        dto = dto.replace("\u0000", "")
                        try:
                            meta["datetime"] = datetime.strptime(dto, "%Y:%m:%d %H:%M:%S")
                        except Exception:
                            try:
                                meta["datetime"] = datetime.fromisoformat(dto)
                            except Exception:
                                pass
                except Exception:
                    pass

                # GPS
                try:
                    if exif:
                        gps_ifd = exif.get("GPS", {})
                        if gps_ifd:
                            gps_lat = gps_ifd.get(piexif.GPSIFD.GPSLatitude)
                            gps_lat_ref = gps_ifd.get(piexif.GPSIFD.GPSLatitudeRef)
                            gps_lon = gps_ifd.get(piexif.GPSIFD.GPSLongitude)
                            gps_lon_ref = gps_ifd.get(piexif.GPSIFD.GPSLongitudeRef)
                            if gps_lat and gps_lon and gps_lat_ref and gps_lon_ref:
                                lat = _dms_to_decimal(gps_lat, gps_lat_ref.decode() if isinstance(gps_lat_ref, bytes) else gps_lat_ref)
                                lon = _dms_to_decimal(gps_lon, gps_lon_ref.decode() if isinstance(gps_lon_ref, bytes) else gps_lon_ref)
                                meta["gps"] = (lat, lon)
                except Exception:
                    pass
        except Exception:
            # Pillow couldn't open or exif not present; fall back below
            pass

    # If we didn't get EXIF from Pillow and the file is HEIC/HEIF,
    # try pyheif to extract EXIF bytes (many HEICs embed an Exif box).
    if (meta.get("datetime") is None or meta.get("gps") is None) and pyheif is not None:
        try:
            heif = pyheif.read(path)
            exif_bytes = None
            for m in getattr(heif, "metadata", []) or []:
                if m.get("type") == "Exif":
                    exif_bytes = m.get("data")
                    break
            if exif_bytes and piexif is not None:
                try:
                    exif = piexif.load(exif_bytes)
                    # DateTimeOriginal
                    try:
                        dto = exif.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal)
                        if dto:
                            if isinstance(dto, bytes):
                                dto = dto.decode(errors="ignore")
                            dto = dto.replace("\u0000", "")
                            try:
                                meta["datetime"] = datetime.strptime(dto, "%Y:%m:%d %H:%M:%S")
                            except Exception:
                                try:
                                    meta["datetime"] = datetime.fromisoformat(dto)
                                except Exception:
                                    pass
                    except Exception:
                        pass

                    # GPS
                    try:
                        gps_ifd = exif.get("GPS", {})
                        if gps_ifd:
                            gps_lat = gps_ifd.get(piexif.GPSIFD.GPSLatitude)
                            gps_lat_ref = gps_ifd.get(piexif.GPSIFD.GPSLatitudeRef)
                            gps_lon = gps_ifd.get(piexif.GPSIFD.GPSLongitude)
                            gps_lon_ref = gps_ifd.get(piexif.GPSIFD.GPSLongitudeRef)
                            if gps_lat and gps_lon and gps_lat_ref and gps_lon_ref:
                                lat = _dms_to_decimal(gps_lat, gps_lat_ref.decode() if isinstance(gps_lat_ref, bytes) else gps_lat_ref)
                                lon = _dms_to_decimal(gps_lon, gps_lon_ref.decode() if isinstance(gps_lon_ref, bytes) else gps_lon_ref)
                                meta["gps"] = (lat, lon)
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            pass

    # If still missing metadata, try exifread (pure Python reader) as a fallback
    if (meta.get("datetime") is None or meta.get("gps") is None) and exifread is not None:
        try:
            with open(path, "rb") as fh:
                tags = exifread.process_file(fh, details=False)

            # DateTimeOriginal or Image DateTime
            dto = None
            for tag_name in ("EXIF DateTimeOriginal", "EXIF DateTimeDigitized", "Image DateTime"):
                if tag_name in tags:
                    dto = str(tags[tag_name])
                    break
            if dto:
                try:
                    meta["datetime"] = datetime.strptime(dto, "%Y:%m:%d %H:%M:%S")
                except Exception:
                    try:
                        meta["datetime"] = datetime.fromisoformat(dto)
                    except Exception:
                        pass

            # GPS parsing helpers
            def _to_float_from_ratio(val):
                # val can be exifread.utils.Ratio or a string like '12/1'
                try:
                    s = str(val)
                    if "/" in s:
                        num, den = s.split("/")
                        return float(num) / float(den) if float(den) != 0 else float(num)
                    return float(s)
                except Exception:
                    return None

            def _dms_from_tag(dms_tag):
                # dms_tag often is a list of Ratio objects
                try:
                    parts = [ _to_float_from_ratio(x) for x in dms_tag ]
                    if len(parts) >= 3 and None not in parts:
                        deg, minute, sec = parts[0], parts[1], parts[2]
                        return deg + (minute/60.0) + (sec/3600.0)
                except Exception:
                    pass
                return None

            if "GPS GPSLatitude" in tags and "GPS GPSLongitude" in tags:
                lat = _dms_from_tag(tags.get("GPS GPSLatitude"))
                lon = _dms_from_tag(tags.get("GPS GPSLongitude"))
                lat_ref = str(tags.get("GPS GPSLatitudeRef")) if "GPS GPSLatitudeRef" in tags else None
                lon_ref = str(tags.get("GPS GPSLongitudeRef")) if "GPS GPSLongitudeRef" in tags else None
                if lat is not None and lon is not None:
                    if lat_ref and lat_ref.upper().startswith("S"):
                        lat = -lat
                    if lon_ref and lon_ref.upper().startswith("W"):
                        lon = -lon
                    meta["gps"] = (lat, lon)
        except Exception:
            pass

    # Fallback for datetime
    if meta["datetime"] is None:
        try:
            ts = path.stat().st_mtime
            meta["datetime"] = datetime.fromtimestamp(ts)
        except Exception:
            meta["datetime"] = None

    return meta


if __name__ == "__main__":
    # quick local test
    import sys
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    if p.is_file():
        print(extract_metadata(p))
    else:
        print("Provide a path to an image file to test")
