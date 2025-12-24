from flask import Flask, render_template, request, jsonify
from pathlib import Path
import time
from urllib.parse import unquote

from photo_sorter.dashboard_support import generate_thumbnail_bytes
from photo_sorter.services.mapping import build_mapping
from photo_sorter.services.preview_runner import start_preview_job
from photo_sorter.services.copy_runner import start_copy_job
from photo_sorter.services.job_store import preview_jobs, copy_jobs, now_ts
from photo_sorter.utils.paths import normalize_user_path, display_path, default_start_path

app = Flask(__name__)


@app.route('/api/list_dir', methods=['GET'])
def api_list_dir():
    # path may be URL-encoded
    raw = request.args.get('path')
    if not raw:
        start = default_start_path()
    else:
        start = normalize_user_path(unquote(raw))

    try:
        p = Path(start)
        if not p.exists() or not p.is_dir():
            return jsonify({'error': 'not found or not a directory', 'path': start}), 404
        entries = []
        for child in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            try:
                entries.append({
                    'name': child.name,
                    'is_dir': child.is_dir(),
                    'path': str(child),
                    'display': display_path(str(child))
                })
            except Exception:
                continue
        return jsonify({
            'path': str(p),
            'display': display_path(str(p)),
            'entries': entries,
            'breadcrumbs': _build_breadcrumbs(p)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@app.route('/api/home', methods=['GET'])
def api_home():
    start = default_start_path()
    return jsonify({'path': start, 'display': display_path(start)})


def _build_breadcrumbs(path_obj: Path):
    crumbs = []
    current = path_obj
    seen = set()
    while True:
        crumbs.append(current)
        parent = current.parent
        if parent == current or str(parent) in seen:
            break
        seen.add(str(current))
        current = parent
    crumbs.reverse()
    formatted = []
    for crumb in crumbs:
        disp = display_path(str(crumb)) or str(crumb)
        label = disp.rstrip("\\/")
        if not label:
            label = disp
        if label and ("/" in label or "\\" in label):
            label = label.split("\\")[-1].split("/")[-1] or label
        formatted.append({'path': str(crumb), 'label': label or disp or str(crumb)})
    return formatted


@app.route("/api/preview_async", methods=["POST"])
def api_preview_async():
    data = request.get_json() or {}
    source = data.get("source")
    if not source:
        return jsonify({"error": "source required"}), 400
    job_id = start_preview_job(source)
    return jsonify({"job": job_id})


@app.route("/api/preview_status", methods=["GET"])
def api_preview_status():
    job_id = request.args.get("job")
    if not job_id:
        return jsonify({"error": "job id required"}), 400
    job = preview_jobs.get(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    total = job.get("total") or (job.get("result") or {}).get("total") or 0
    processed = job.get("processed") or 0
    payload = dict(job)
    if total:
        payload["percent"] = round(processed / total * 100, 2)
    return jsonify(payload)


@app.route("/api/run_async", methods=["POST"])
def api_run_async():
    data = request.get_json() or {}
    source = data.get("source")
    dest = data.get("dest")
    group = data.get("group")
    if not source or not dest:
        return jsonify({"error": "source and dest required"}), 400
    job_id = start_copy_job(source, dest, group)
    return jsonify({"job": job_id})


@app.route("/api/status", methods=["GET"])
def api_status():
    job_id = request.args.get("job")
    if not job_id:
        return jsonify({"error": "job id required"}), 400
    job = copy_jobs.get(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    total = job.get("total") or 0
    processed = job.get("processed") or 0
    elapsed = None
    start = job.get("start_time")
    if start:
        elapsed = now_ts() - start
    response = dict(job)
    response["elapsed_seconds"] = elapsed
    if elapsed and elapsed > 0:
        response["speed_fps"] = round(processed / elapsed, 3)
    else:
        response["speed_fps"] = None
    accounted = (job.get("copied") or 0) + (job.get("duplicates") or 0) + (job.get("failed") or 0)
    response["accounted"] = accounted
    if total:
        response["percent"] = round(processed / total * 100, 2)
        remaining = max(0, total - accounted)
        response["remaining"] = remaining
        speed = response.get("speed_fps")
        response["eta_seconds"] = int(remaining / speed) if speed else None
    else:
        response["percent"] = None
        response["remaining"] = None
        response["eta_seconds"] = None
    if job.get("current_file"):
        response["current_file_display"] = display_path(job["current_file"])
    if job.get("dest"):
        response["dest_display"] = display_path(job["dest"])
    if job.get("duplicates_dir"):
        response["duplicates_dir_display"] = display_path(job["duplicates_dir"])
    return jsonify(response)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/preview", methods=["POST"])
def preview():
    source = request.form.get("source")
    dest = request.form.get("dest")
    if not source:
        return "Source path required", 400
    try:
        mapping, files = build_mapping(source, use_cache=False)
    except Exception as e:
        return f"Error building mapping: {e}", 500

    groups = []
    total = len(files)
    for name, paths in mapping.items():
        sample_thumbs = []
        for p in paths[:3]:
            b64 = generate_thumbnail_bytes(p)
            if b64:
                sample_thumbs.append(f"data:image/jpeg;base64,{b64}")
        groups.append({"name": name, "count": len(paths), "samples": sample_thumbs})

    accounted = sum(g["count"] for g in groups)
    remaining = max(0, total - accounted)

    # Render preview with confirmation button and API-style stats at top
    return render_template(
        "preview.html",
        source=source,
        dest=dest or "",
        total=total,
        groups=groups,
        accounted=accounted,
        remaining=remaining,
    )


@app.route("/run", methods=["POST"])
def run():
    source = request.form.get("source")
    dest = request.form.get("dest")
    if not source or not dest:
        return "Both source and destination are required to run the copy.", 400
    try:
        mapping, files = build_mapping(source)
    except Exception as e:
        return f"Error building mapping: {e}", 500

    dest_root = Path(normalize_user_path(dest))
    summary = {"processed": 0, "copied": 0, "duplicates": 0, "failed": 0, "errors": []}
    start_time = _now_ts()
    for group, paths in mapping.items():
        dest_dir = dest_root / group
        for p in paths:
            summary["processed"] += 1
            try:
                res = copy_file(p, dest_dir, dry_run=False, return_status=True)
                if isinstance(res, tuple):
                    _dest, status = res
                else:
                    _dest, status = res, "copied"
                if status == "skipped_identical":
                    summary["duplicates"] += 1
                else:
                    summary["copied"] += 1
            except Exception as e:
                summary["failed"] += 1
                summary["errors"].append(str(e))
    finished_time = _now_ts()
    summary["start_time"] = start_time
    summary["finished_time"] = finished_time
    summary["accounted"] = summary["copied"] + summary["duplicates"] + summary["failed"]
    summary["remaining"] = max(0, len(files) - summary["accounted"])
    # Human readable
    try:
        summary["start_time_readable"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time))
        summary["finished_time_readable"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(finished_time))
    except Exception:
        summary["start_time_readable"] = str(start_time)
        summary["finished_time_readable"] = str(finished_time)

    return render_template("run_result.html", summary=summary, total=len(files))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
