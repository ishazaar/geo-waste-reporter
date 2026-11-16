"""
Geo-Waste Reporter - Main Flask Application
RESTful APIs for citizen reporting, GeoAI analytics, DBSCAN clustering,
waste classification and the municipal admin dashboard.

Configuration (environment variables):
  ADMIN_TOKEN     secret required for admin actions (status updates, reseed). REQUIRED in production.
  FLASK_DEBUG     "1" enables debug mode (local development only; never in production)
  TRUST_PROXY     "1" when behind a reverse proxy (Render, nginx) so client IPs are read correctly
  GEMINI_API_KEY  optional, enables real image classification (server-side only)
  GEMINI_MODEL    optional, defaults to gemini-2.5-flash
  CORS_ORIGINS    optional comma-separated list of allowed origins (default: same-origin only)
"""

import os
import io
import csv
import json
import math
import uuid
import hmac
import base64
import hashlib
import time
import urllib.parse
import urllib.request
import secrets
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory, Response
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from database import (
    init_db, get_all_reports, get_report_by_id, create_report,
    update_report_status, upvote_report, get_analytics_summary,
    get_ward_stats, reset_db, DATA_DIR
)
from geo_analytics import (
    haversine_distance, calculate_priority_score, check_for_duplicate,
    run_dbscan_clustering, optimize_cleanup_route, SENSITIVE_RECEPTORS,
    nearby_receptors, receptor_from_report, find_repeat_dump_sites,
    MUNICIPAL_DEPOTS, lookup_ward_and_address
)
from ai_classifier import classify_waste_image, sniff_mime, CATEGORIES
from seed_data import seed_database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")   # writable location (see database.DATA_DIR)
WARDS_GEOJSON = os.path.join(STATIC_DIR, "data", "bangalore_wards.geojson")
try:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
except OSError as _e:  # read-only filesystem: the app must still start; uploads will return a clean error
    print(f"[app] Upload folder unavailable ({_e}); photo uploads disabled")

# Rough bounding box around Greater Bengaluru: (min_lat, max_lat, min_lon, max_lon)
BLR_BOUNDS = (12.70, 13.30, 77.30, 77.95)
VALID_STATUSES = ["Reported", "In Progress", "Cleared"]
EXT_FOR_MIME = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload

if os.environ.get("TRUST_PROXY") == "1" or os.environ.get("VERCEL"):
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

ALLOWED_ORIGINS = {o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()}


# ---------------------------------------------------------------- errors / validation helpers
class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


@app.errorhandler(ApiError)
def handle_api_error(e):
    return jsonify({"success": False, "error": e.message}), e.status


@app.errorhandler(HTTPException)
def handle_http_error(e):
    return jsonify({"success": False, "error": e.description or e.name}), e.code


@app.errorhandler(Exception)
def handle_unexpected(e):
    app.logger.exception("Unhandled error")
    return jsonify({"success": False, "error": "Internal server error"}), 500


def parse_float(value, field, lo=None, hi=None, default=None):
    if value is None or (isinstance(value, str) and not value.strip()):
        if default is not None:
            return default
        raise ApiError(f"{field} is required")
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ApiError(f"{field} must be a number")
    if math.isnan(v) or math.isinf(v):
        raise ApiError(f"{field} must be a finite number")
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        raise ApiError(f"{field} must be between {lo} and {hi}")
    return v


def parse_int(value, field, lo=None, hi=None, default=None):
    return int(parse_float(value, field, lo, hi, default))


def parse_coords(lat, lon):
    lat = parse_float(lat, "latitude", -90, 90)
    lon = parse_float(lon, "longitude", -180, 180)
    if not (BLR_BOUNDS[0] <= lat <= BLR_BOUNDS[1] and BLR_BOUNDS[2] <= lon <= BLR_BOUNDS[3]):
        raise ApiError("Location must be within Bengaluru")
    return lat, lon


def clean_text(value, field, max_len, required=False):
    text = ("" if value is None else str(value)).strip()
    if required and not text:
        raise ApiError(f"{field} is required")
    if len(text) > max_len:
        raise ApiError(f"{field} must be at most {max_len} characters")
    return text


def json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def read_image(file_storage):
    """Reads an uploaded file and verifies it is a real image. Returns (bytes, mime)."""
    data = file_storage.read()
    mime = sniff_mime(data) if data else None
    if not mime:
        raise ApiError("Unsupported file: please upload a JPEG, PNG, WebP or GIF image")
    return data, mime


def save_image(data, mime, prefix):
    """Saves verified image bytes under a server-generated name with an extension derived from content."""
    name = f"{prefix}_{uuid.uuid4().hex[:12]}{EXT_FOR_MIME[mime]}"
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(os.path.join(UPLOAD_DIR, name), "wb") as f:
            f.write(data)
    except OSError:
        raise ApiError("Photo uploads are not available on this server right now", 503)
    return f"/uploads/{name}"


# ---------------------------------------------------------------- auth
def require_admin(fn):
    """Admin endpoints need the ADMIN_TOKEN via `X-Admin-Token` or `Authorization: Bearer <token>`."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = os.environ.get("ADMIN_TOKEN")
        if not expected:
            raise ApiError("Admin actions are disabled: ADMIN_TOKEN is not configured on the server", 503)
        supplied = request.headers.get("X-Admin-Token", "")
        auth = request.headers.get("Authorization", "")
        if not supplied and auth.startswith("Bearer "):
            supplied = auth[7:]
        if not hmac.compare_digest(supplied.encode(), expected.encode()):
            raise ApiError("Admin authentication required", 401)
        return fn(*args, **kwargs)
    return wrapper


@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    origin = request.headers.get("Origin")
    if origin and origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-Admin-Token"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


# ---------------------------------------------------------------- live priority
def _age_days(reported_at):
    try:
        dt = datetime.fromisoformat(reported_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)
    except Exception:
        return 0.0


def apply_live_priority(report):
    """Recomputes the MCDA score so report AGE and upvotes are always reflected (open reports only)."""
    if report.get("status") != "Cleared":
        calc = calculate_priority_score(
            severity=report.get("severity", 3), lat=report["latitude"], lon=report["longitude"],
            upvotes=report.get("upvotes", 0) or 0, days_open=_age_days(report.get("reported_at")),
            receptor=receptor_from_report(report)
        )
        report["priority_score"] = calc["score"]
        report["priority_level"] = calc["level"]
    return report


def fetch_reports(priority=None, **filters):
    reports = [apply_live_priority(r) for r in get_all_reports(**filters)]
    if priority and priority != "All":
        reports = [r for r in reports if r["priority_level"] == priority]
    return reports


def client_token():
    """Server-derived voter identity. Never trust a token chosen by the browser."""
    raw = f"{request.remote_addr}|{request.headers.get('User-Agent', '')}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


# ---------------------------------------------------------------- static frontend
@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    """Serves user photos from the writable data dir (they no longer live inside /static)."""
    return send_from_directory(UPLOAD_DIR, filename)


# ---------------------------------------------------------------- reports
@app.route("/api/reports", methods=["GET"])
def list_reports():
    reports = fetch_reports(
        status=request.args.get("status"),
        category=request.args.get("category"),
        ward=request.args.get("ward"),
        priority=request.args.get("priority"),
        search=request.args.get("search"),
    )
    return jsonify({"success": True, "count": len(reports), "reports": reports})


@app.route("/api/reports/<report_id>", methods=["GET"])
def get_single_report(report_id):
    report = get_report_by_id(report_id)
    if not report:
        return jsonify({"success": False, "error": "Report not found"}), 404
    return jsonify({"success": True, "report": apply_live_priority(report)})


@app.route("/api/check-duplicate", methods=["POST"])
def duplicate_check_endpoint():
    data = json_body()
    lat, lon = parse_coords(data.get("latitude"), data.get("longitude"))
    threshold_m = parse_float(data.get("threshold_m"), "threshold_m", 5, 500, default=40.0)
    result = check_for_duplicate(lat, lon, get_all_reports(), threshold_m=threshold_m)
    return jsonify({"success": True, **result})


@app.route("/api/reverse-geocode", methods=["GET", "POST"])
def reverse_geocode_endpoint():
    """Returns the ward and a landmark-based address for coordinates."""
    if request.method == "POST":
        data = json_body()
        lat, lon = data.get("latitude"), data.get("longitude")
    else:
        lat = request.args.get("lat") or request.args.get("latitude")
        lon = request.args.get("lon") or request.args.get("longitude")
    lat = parse_float(lat, "latitude", -90, 90)
    lon = parse_float(lon, "longitude", -180, 180)
    geo_info = lookup_ward_and_address(lat, lon, wards_geojson_path=WARDS_GEOJSON)
    return jsonify({"success": True, **geo_info})


@app.route("/api/priority-preview")
def priority_preview():
    """Live priority for a pin: finds nearby schools/hospitals/water bodies and scores the spot."""
    lat = parse_float(request.args.get("lat"), "latitude", -90, 90)
    lon = parse_float(request.args.get("lon"), "longitude", -180, 180)
    severity = parse_int(request.args.get("severity"), "severity", 1, 5, default=3)
    receptors, source = nearby_receptors(lat, lon)
    calc = calculate_priority_score(severity=severity, lat=lat, lon=lon, receptors=receptors)
    return jsonify({"success": True, "source": source, **calc, "receptors": receptors[:25]})


@app.route("/api/ai-classify", methods=["POST"])
def ai_classify_endpoint():
    """Classifies an uploaded image (multipart `photo` or JSON `image_base64`). API keys are server-side only."""
    image_bytes, filename, description = None, "", ""

    if "photo" in request.files:
        f = request.files["photo"]
        filename = f.filename or ""
        description = request.form.get("description", "")
        image_bytes, _ = read_image(f)
    elif request.is_json:
        data = json_body()
        description = str(data.get("description", ""))
        filename = str(data.get("filename", ""))
        b64 = data.get("image_base64")
        if b64:
            if "," in b64:
                b64 = b64.split(",", 1)[1]
            try:
                image_bytes = base64.b64decode(b64, validate=True)
            except Exception:
                raise ApiError("image_base64 is not valid base64")
            if not sniff_mime(image_bytes):
                raise ApiError("Unsupported image type")
    else:
        description = request.form.get("description", "")

    analysis = classify_waste_image(image_bytes=image_bytes, filename=filename, description=description[:2000])
    return jsonify({"success": True, "analysis": analysis})


@app.route("/api/reports", methods=["POST"])
def submit_report():
    """
    Creates a new report: validates input, verifies/stores the photo, classifies it,
    computes the MCDA priority score and rejects duplicates unless force_submit is set.
    """
    is_multipart = request.content_type and "multipart/form-data" in request.content_type
    if is_multipart:
        data = request.form.to_dict()
        photo_file = request.files.get("photo")
    else:
        data = json_body()
        photo_file = None

    lat, lon = parse_coords(data.get("latitude"), data.get("longitude"))
    title = clean_text(data.get("title"), "title", 150)
    description = clean_text(data.get("description"), "description", 2000)
    force_submit = str(data.get("force_submit", "false")).lower() in ("true", "1", "yes")

    category = clean_text(data.get("category"), "category", 80)
    if category and category != "Auto-Detect (AI)" and category not in CATEGORIES:
        raise ApiError("Unknown category")
    severity = parse_int(data.get("severity"), "severity", 1, 5, default=3)

    if not force_submit:
        dup_check = check_for_duplicate(lat, lon, get_all_reports(), threshold_m=40.0)
        if dup_check.get("is_duplicate"):
            return jsonify({
                "success": False, "is_duplicate": True,
                "message": "Potential duplicate dump detected nearby",
                "duplicate_info": dup_check
            }), 409

    # Photo: verified by content, stored under a server-generated name. Client-supplied image URLs are ignored.
    image_url = "/static/images/placeholder_dump.svg"
    ai_classification = None
    photo_bytes = None
    if photo_file and photo_file.filename:
        photo_bytes, mime = read_image(photo_file)
        image_url = save_image(photo_bytes, mime, "report")
        ai_classification = classify_waste_image(
            image_bytes=photo_bytes, filename=photo_file.filename, description=description
        )

    ai_materials, ai_confidence = [], None
    est_vol = clean_text(data.get("estimated_volume"), "estimated_volume", 40) or None

    if ai_classification:
        if not category or category == "Auto-Detect (AI)":
            category = ai_classification["category"]
            severity = ai_classification["severity"]
        ai_materials = ai_classification.get("detected_materials", [])
        ai_confidence = ai_classification.get("confidence")
        est_vol = ai_classification.get("estimated_volume_m3", est_vol)

    if not category or category == "Auto-Detect (AI)":
        category = "Mixed Municipal Solid Waste"

    # Priority is driven by LOCATION: nearby schools / hospitals / water bodies (live OpenStreetMap lookup)
    receptors, receptor_source = nearby_receptors(lat, lon)
    priority_res = calculate_priority_score(severity=severity, lat=lat, lon=lon, upvotes=0, days_open=0.0,
                                            receptors=receptors)

    # Ward + landmark address are derived from the coordinates (authoritative), not trusted from the client.
    geo = lookup_ward_and_address(lat, lon, wards_geojson_path=WARDS_GEOJSON)
    address = clean_text(data.get("address"), "address", 300) or geo["address"]

    receptor = priority_res.get("closest_receptor")
    report_payload = {
        "title": title or f"{category} on Roadside",
        "description": description,
        "category": category,
        "severity": severity,
        "priority_score": priority_res["score"],
        "priority_level": priority_res["level"],
        "latitude": lat,
        "longitude": lon,
        "address": address,
        "ward_id": geo["ward_id"],
        "ward_name": geo["ward_name"],
        "status": "Reported",
        "image_url": image_url,
        "after_image_url": None,
        "upvotes": 0,
        "ai_confidence": ai_confidence,
        "ai_materials": ai_materials,
        "estimated_volume": est_vol,
        "closest_receptor_name": receptor["name"] if receptor else None,
        "closest_receptor_dist": receptor["distance_m"] if receptor else None,
        "closest_receptor_type": receptor["type"] if receptor else None,
        "notes": f"Initial report logged. Proximity: {priority_res.get('proximity_note', '')}"
    }

    created = create_report(report_payload)
    return jsonify({
        "success": True, "message": "Report submitted successfully",
        "report": created, "ai_analysis": ai_classification
    }), 201


@app.route("/api/reports/<report_id>/status", methods=["POST"])
@require_admin
def update_status(report_id):
    """Admin: Reported -> In Progress -> Cleared, optionally with an after-photo as proof."""
    is_multipart = request.content_type and "multipart/form-data" in request.content_type
    if is_multipart:
        data = request.form.to_dict()
        after_file = request.files.get("after_photo")
    else:
        data = json_body()
        after_file = None

    status = data.get("status")
    if status not in VALID_STATUSES:
        raise ApiError("Invalid status value")

    after_image_url = None
    if after_file and after_file.filename:
        after_bytes, mime = read_image(after_file)
        after_image_url = save_image(after_bytes, mime, "cleared")
    elif status == "Cleared":
        after_image_url = "/static/images/cleared_proof.svg"

    updated = update_report_status(
        report_id=report_id,
        status=status,
        after_image_url=after_image_url,
        notes=clean_text(data.get("notes"), "notes", 1000),
        actor=clean_text(data.get("actor"), "actor", 80) or "Municipal SWM Supervisor"
    )
    if not updated:
        return jsonify({"success": False, "error": "Report not found"}), 404
    return jsonify({"success": True, "message": "Status updated successfully", "report": apply_live_priority(updated)})


@app.route("/api/reports/<report_id>/upvote", methods=["POST"])
def upvote(report_id):
    # Voter identity is derived server-side; any token sent by the browser is ignored.
    res = upvote_report(report_id, user_token=client_token())
    return jsonify(res), (200 if res.get("success") else res.get("status_code", 400))


# ---------------------------------------------------------------- analytics
@app.route("/api/hotspots", methods=["GET"])
def hotspots_endpoint():
    eps = parse_float(request.args.get("eps_meters"), "eps_meters", 20, 5000, default=250.0)
    min_pts = parse_int(request.args.get("min_samples"), "min_samples", 2, 50, default=3)

    all_reports = get_all_reports()
    clustering_res = run_dbscan_clustering(all_reports, eps_meters=eps, min_samples=min_pts)

    heatmap_points = []
    for r in all_reports:
        status_mult = 1.0 if r.get("status") == "Reported" else 0.7 if r.get("status") == "In Progress" else 0.2
        intensity = round((r.get("severity", 3) / 5.0) * status_mult, 2)
        heatmap_points.append([float(r["latitude"]), float(r["longitude"]), intensity])

    return jsonify({"success": True, **clustering_res, "heatmap_points": heatmap_points})


_GEOCODE_CACHE = {}


def _http_json(url: str, timeout: float = 6.0):
    req = urllib.request.Request(url, headers={"User-Agent": "geo-waste-reporter/1.0 (student project)",
                                               "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _geocode_bengaluru(q: str):
    min_lat, max_lat, min_lon, max_lon = BLR_BOUNDS
    results = []
    try:   # 1) Nominatim, restricted to the Bengaluru box
        qs = urllib.parse.urlencode({"q": q, "format": "jsonv2", "limit": 6, "countrycodes": "in",
                                     "viewbox": f"{min_lon},{max_lat},{max_lon},{min_lat}", "bounded": 1})
        for it in _http_json("https://nominatim.openstreetmap.org/search?" + qs):
            full = it.get("display_name", "")
            results.append({"name": it.get("name") or full.split(",")[0], "display": full,
                            "lat": float(it["lat"]), "lon": float(it["lon"])})
    except Exception:
        results = []
    if not results:
        try:   # 2) Photon fallback
            qs = urllib.parse.urlencode({"q": q, "limit": 6, "lat": 12.9716, "lon": 77.5946,
                                         "bbox": f"{min_lon},{min_lat},{max_lon},{max_lat}"})
            for f in _http_json("https://photon.komoot.io/api/?" + qs).get("features", []):
                pr, (lon, lat) = f.get("properties", {}), f["geometry"]["coordinates"]
                name = pr.get("name") or pr.get("street") or q
                parts = [name, pr.get("district") or pr.get("locality"), pr.get("city"), pr.get("postcode")]
                results.append({"name": name, "display": ", ".join(x for x in parts if x),
                                "lat": float(lat), "lon": float(lon)})
        except Exception:
            pass
    return [r for r in results if min_lat <= r["lat"] <= max_lat and min_lon <= r["lon"] <= max_lon]


@app.route("/api/geocode", methods=["GET"])
def geocode_place():
    """Place search for the report map (Bengaluru only). Cached to stay polite to the free OSM services."""
    q = (request.args.get("q") or "").strip()[:100]
    if len(q) < 3:
        raise ApiError("Type at least 3 letters to search")
    key = q.lower()
    hit = _GEOCODE_CACHE.get(key)
    if hit and time.time() - hit[0] < 6 * 3600:
        return jsonify({"success": True, "results": hit[1]})
    results = _geocode_bengaluru(q)
    if results:
        if len(_GEOCODE_CACHE) > 500:
            _GEOCODE_CACHE.clear()
        _GEOCODE_CACHE[key] = (time.time(), results)
    return jsonify({"success": True, "results": results})


@app.route("/api/health", methods=["GET"])
def health():
    """Setup check: shows whether env vars reached the server (never reveals their values)."""
    return jsonify({
        "ok": True,
        "admin_token_configured": bool(os.environ.get("ADMIN_TOKEN")),
        "gemini_key_configured": bool(os.environ.get("GEMINI_API_KEY")),
        "vercel_environment": os.environ.get("VERCEL_ENV"),   # production / preview / development
        "vercel_deployment": (os.environ.get("VERCEL_URL") or "")[:80] or None,
    })


@app.route("/api/repeat-sites", methods=["GET"])
def repeat_sites_endpoint():
    """Places that get dirty again after being cleaned, with a prediction of the next relapse."""
    radius = parse_float(request.args.get("radius_m"), "radius_m", 10, 500, default=50.0)
    return jsonify({"success": True, **find_repeat_dump_sites(get_all_reports(), radius_m=radius)})


@app.route("/api/wards", methods=["GET"])
def wards_endpoint():
    if not os.path.exists(WARDS_GEOJSON):
        return jsonify({"success": False, "error": "Ward GeoJSON not found"}), 404

    with open(WARDS_GEOJSON, "r", encoding="utf-8") as f:
        wards_geojson = json.load(f)

    ward_stats = {w["ward_id"]: w for w in get_ward_stats()}

    for feature in wards_geojson.get("features", []):
        wid = feature.get("properties", {}).get("ward_id")
        if wid in ward_stats:
            feature["properties"].update(ward_stats[wid])
        else:
            feature["properties"].update({
                "total_reports": 0, "open_reports": 0, "cleared_reports": 0,
                "clearance_rate": 100.0, "cleanliness_index": 95, "grade": "A (Clean)"
            })

    return jsonify({
        "success": True,
        "geojson": wards_geojson,
        "ward_leaderboard": sorted(ward_stats.values(), key=lambda x: x["cleanliness_index"], reverse=True),
        "worst_wards": sorted(ward_stats.values(), key=lambda x: x["open_reports"], reverse=True)
    })


@app.route("/api/route-optimizer", methods=["GET", "POST"])
def route_optimizer_endpoint():
    """Optimal pickup route for waste trucks across open reports (highest priority first)."""
    depot_key = request.args.get("depot", "central")
    if depot_key not in MUNICIPAL_DEPOTS:
        raise ApiError("Unknown depot")
    cluster_id = request.args.get("cluster_id")
    max_stops = parse_int(request.args.get("max_stops"), "max_stops", 1, 30, default=10)

    open_reports = fetch_reports(status="Reported")

    target_reports = []
    if cluster_id not in (None, ""):
        clustering_res = run_dbscan_clustering(get_all_reports())
        matched = [c for c in clustering_res["clusters"] if str(c["cluster_id"]) == str(cluster_id)]
        if matched:
            rep_ids = set(matched[0]["report_ids"])
            target_reports = [r for r in open_reports if r["id"] in rep_ids]

    if not target_reports:
        target_reports = open_reports

    # Priority order doubles as the honest baseline the optimizer is compared against.
    target_reports = sorted(target_reports, key=lambda x: x["priority_score"], reverse=True)[:max_stops]

    route_res = optimize_cleanup_route(target_reports, depot_key=depot_key)
    return jsonify({"success": True, **route_res, "available_depots": MUNICIPAL_DEPOTS})


@app.route("/api/analytics", methods=["GET"])
def analytics_endpoint():
    return jsonify({"success": True, **get_analytics_summary()})


@app.route("/api/seed", methods=["POST"])
@require_admin
def reseed_endpoint():
    """Admin only: DESTRUCTIVE. Deletes every report and loads the demo dataset."""
    seed_database()
    return jsonify({"success": True, "message": "Database reset and reseeded with demo data"})


# ---------------------------------------------------------------- exports
@app.route("/api/export/geojson", methods=["GET"])
def export_geojson():
    features = []
    for r in fetch_reports():
        features.append({
            "type": "Feature",
            "properties": {
                "id": r["id"], "title": r["title"], "category": r["category"], "status": r["status"],
                "priority_level": r["priority_level"], "priority_score": r["priority_score"],
                "ward_name": r["ward_name"], "reported_at": r["reported_at"]
            },
            "geometry": {"type": "Point", "coordinates": [float(r["longitude"]), float(r["latitude"])]}
        })
    return Response(
        json.dumps({"type": "FeatureCollection", "features": features}, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment;filename=geo_waste_reports.geojson"}
    )


def _csv_safe(v):
    """Neutralise spreadsheet formula injection (=, +, -, @ at the start of a text cell)."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


@app.route("/api/export/csv", methods=["GET"])
def export_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Title", "Category", "Severity", "Priority Score", "Priority Level",
        "Latitude", "Longitude", "Ward Name", "Status", "Upvotes", "Reported At", "Cleared At"
    ])
    for r in fetch_reports():
        writer.writerow([_csv_safe(v) for v in [
            r.get("id"), r.get("title"), r.get("category"), r.get("severity"),
            r.get("priority_score"), r.get("priority_level"), r.get("latitude"),
            r.get("longitude"), r.get("ward_name"), r.get("status"),
            r.get("upvotes"), r.get("reported_at"), r.get("cleared_at")
        ]])
    return Response(
        output.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=geo_waste_reports.csv"}
    )


# ---------------------------------------------------------------- startup
try:
    init_db()
    if len(get_all_reports()) == 0:
        seed_database()
except Exception as _db_err:
    print(f"Database auto-init notice: {_db_err}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    if not os.environ.get("ADMIN_TOKEN"):
        # Local convenience only: a random per-run token, printed once. In production set ADMIN_TOKEN yourself.
        os.environ["ADMIN_TOKEN"] = secrets.token_urlsafe(12)
        print(f"\n  Admin token for this run (needed for the Admin tab): {os.environ['ADMIN_TOKEN']}\n")
    debug = os.environ.get("FLASK_DEBUG") == "1"
    host = "127.0.0.1" if debug else os.environ.get("HOST", "0.0.0.0")
    print(f"Starting Geo-Waste Reporter on http://{host}:{port} (debug={'on' if debug else 'off'})")
    app.run(host=host, port=port, debug=debug)
