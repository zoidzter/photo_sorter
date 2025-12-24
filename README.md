Photo Sorter CLI (MVP)

This tool groups and copies photos/videos from a source folder into destination folders based on date and location metadata.

Quick start (PowerShell):

```powershell
# create virtualenv (optional)
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# dry-run to see grouping
python cli.py --source "C:\Users\patri\Pictures\to-sort" --dest "D:\SortedPhotos" --dry-run

# do the real copy
python cli.py --source "C:\Users\patri\Pictures\to-sort" --dest "D:\SortedPhotos"
```

Notes:
- The CLI currently uses `Pillow` + `piexif` to read EXIF metadata. For HEIC/RAW formats you may need additional system packages or `exiftool`.
 - The CLI currently uses `Pillow` + `piexif` to read EXIF metadata. For HEIC/HEIF files the tool will try to use `pillow-heif` (registers a HEIF opener for Pillow) or `pyheif` to extract embedded EXIF. On some platforms `pillow-heif` may require additional system libraries; if HEIC files still aren't processed, installing `exiftool` and using it via a wrapper is a robust alternative.
- Reverse geocoding uses `reverse_geocoder` (offline) if installed; otherwise locations may be labeled `NoLocation` or `Unknown`.
- The tool copies files (never moves) and preserves file timestamps where possible.

Important: the app does NOT perform automatic location inference from nearby photos. If an image has no GPS metadata it will be grouped as `NoLocation` (or by date/event where applicable). A separate helper script for manual inference was removed to avoid implicit changes to grouping.

Next steps:
- Tune grouping heuristics (include day, events like Xmas/Halloween)
- Add a `--concurrency` option to speed up metadata extraction and copying for large datasets
- Add tests and a small sample dataset for verification

Dashboard
---------
A small web dashboard is included to preview dry-run groupings and confirm running the actual copy.

Run locally (PowerShell):

```powershell
# create virtualenv (optional)
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# start the dashboard
python -m photo_sorter.dashboard
# open http://127.0.0.1:5000 in your browser
```

The dashboard allows you to enter a source folder and a destination folder, run a dry-run preview (shows proposed folders, counts and sample thumbnails), then confirm to run the copy.

Key Files Overview
-------------------
- [photo_sorter/dashboard.py](photo_sorter/dashboard.py): Flask app exposing API endpoints, Explorer listing, preview/copy orchestration, and template rendering.
- [photo_sorter/services/mapping.py](photo_sorter/services/mapping.py): Scans source folders, extracts EXIF metadata, builds caching, and feeds progress callbacks.
- [photo_sorter/services/preview_runner.py](photo_sorter/services/preview_runner.py) & [photo_sorter/services/copy_runner.py](photo_sorter/services/copy_runner.py): Background workers that handle previews and copy jobs asynchronously while persisting state in the job store.
- [photo_sorter/templates/index.html](photo_sorter/templates/index.html): Frontend dashboard with Explorer UI, preview cards, and progress modal logic.
- [photo_sorter/utils/paths.py](photo_sorter/utils/paths.py): Normalizes Windows vs. WSL paths and supplies display helpers for breadcrumbs and job status responses.
- [photo_sorter/grouper.py](photo_sorter/grouper.py) & [photo_sorter/grouping_rules.json](photo_sorter/grouping_rules.json): Generate destination folder names (year/month/location/event) and allow user-defined aliases/custom events.
