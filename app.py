"""
Geo-Waste Reporter - Main Flask Application
Provides RESTful APIs for Citizen Reporting, GeoAI Analytics, DBSCAN Clustering,
AI Waste Vision Classification, and Municipal Admin Dashboard.
"""

import os
import io
import csv
import json
import uuid
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory, Response

from database import (
    init_db, get_all_reports, get_report_by_id, create_report,
    update_report_status, upvote_report, get_analytics_summary,
    get_ward_stats, reset_db
)
from geo_analytics import (
    haversine_distance, calculate_priority_score, check_for_duplicate,
    run_dbscan_clustering, optimize_cleanup_route, SENSITIVE_RECEPTORS,
    MUNICIPAL_DEPOTS, lookup_ward_and_address
)
from ai_classifier import classify_waste_image
from seed_data import seed_database

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    return response


# --- Static Frontend Serving ---
@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


# --- Reports Endpoints ---
@app.route("/api/reports", methods=["GET"])
def list_reports():
    status = request.args.get("status")
    category = request.args.get("category")
    ward = request.args.get("ward")
    priority = request.args.get("priority")
    search = request.args.get("search")

    reports = get_all_reports(
        status=status,
        category=category,
        ward=ward,
        priority=priority,
        search=search
    )
    return jsonify({"success": True, "count": len(reports), "reports": reports})


@app.route("/api/reports/<report_id>", methods=["GET"])
def get_single_report(report_id):
    report = get_report_by_id(report_id)
    if not report:
        return jsonify({"success": False, "error": "Report not found"}), 404
    return jsonify({"success": True, "report": report})


@app.route("/api/check-duplicate", methods=["POST"])
def duplicate_check_endpoint():
    data = request.get_json() or {}
    lat = data.get("latitude")
    lon = data.get("longitude")
    threshold_m = float(data.get("threshold_m", 40.0))

    if lat is None or lon is None:
        return jsonify({"success": False, "error": "Coordinates required"}), 400

    active_reports = get_all_reports()
    result = check_for_duplicate(float(lat), float(lon), active_reports, threshold_m=threshold_m)
    return jsonify({"success": True, **result})


@app.route("/api/reverse-geocode", methods=["GET", "POST"])
def reverse_geocode_endpoint():
    """
    Accepts latitude and longitude and returns authentic ward and address information.
    """
    if request.method == "POST":
        data = request.get_json() or {}
        lat = data.get("latitude")
        lon = data.get("longitude")
    else:
        lat = request.args.get("lat") or request.args.get("latitude")
        lon = request.args.get("lon") or request.args.get("longitude")

    if lat is None or lon is None:
        return jsonify({"success": False, "error": "Latitude and longitude required"}), 400

    geojson_path = os.path.join(STATIC_DIR, "data", "bangalore_wards.geojson")
    geo_info = lookup_ward_and_address(float(lat), float(lon), wards_geojson_path=geojson_path)
    return jsonify({"success": True, **geo_info})


@app.route("/api/ai-classify", methods=["POST"])
def ai_classify_endpoint():
    """
    Accepts uploaded image file or base64 string and runs waste classification.
    """
    image_bytes = None
    filename = ""
    description = request.form.get("description", "")
    api_key = request.form.get("gemini_api_key")

    if "photo" in request.files:
        f = request.files["photo"]
        filename = f.filename or ""
        image_bytes = f.read()
    elif request.is_json:
        data = request.get_json()
        description = data.get("description", "")
        filename = data.get("filename", "")
        b64 = data.get("image_base64")
        if b64:
            if "," in b64:
                b64 = b64.split(",", 1)[1]
            try:
                import base64
                image_bytes = base64.b64decode(b64)
            except Exception:
                pass

    analysis = classify_waste_image(
        image_bytes=image_bytes,
        filename=filename,
        description=description,
        gemini_api_key=api_key
    )
    return jsonify({"success": True, "analysis": analysis})


@app.route("/api/reports", methods=["POST"])
def submit_report():
    """
    Creates a new waste report:
    - Auto-classifies image if uploaded
    - Computes GeoAI priority score (MCDA)
    - Checks for duplicates unless force_submit=True
    """
    is_multipart = request.content_type and "multipart/form-data" in request.content_type
    
    if is_multipart:
        data = request.form.to_dict()
        photo_file = request.files.get("photo")
    else:
        data = request.get_json() or {}
        photo_file = None

    lat = data.get("latitude")
    lon = data.get("longitude")
    if not lat or not lon:
        return jsonify({"success": False, "error": "Latitude and Longitude are required"}), 400

    lat = float(lat)
    lon = float(lon)
    force_submit = str(data.get("force_submit", "false")).lower() in ["true", "1", "yes"]

    # Duplicate check
    if not force_submit:
        active_reports = get_all_reports()
        dup_check = check_for_duplicate(lat, lon, active_reports, threshold_m=40.0)
        if dup_check.get("is_duplicate"):
            return jsonify({
                "success": False,
                "is_duplicate": True,
                "message": "Potential duplicate dump detected nearby",
                "duplicate_info": dup_check
            }), 409

    # Handle Photo upload and AI Classification
    image_url = data.get("image_url")
    ai_classification = None

    if photo_file:
        file_ext = os.path.splitext(photo_file.filename)[1] or ".jpg"
        unique_filename = f"report_{uuid.uuid4().hex[:10]}{file_ext}"
        save_path = os.path.join(UPLOAD_DIR, unique_filename)
        photo_bytes = photo_file.read()
        
        with open(save_path, "wb") as f_out:
            f_out.write(photo_bytes)
        image_url = f"/static/uploads/{unique_filename}"

        # Run AI classification on the uploaded photo
        ai_classification = classify_waste_image(
            image_bytes=photo_bytes,
            filename=photo_file.filename,
            description=data.get("description", "")
        )
    elif not image_url:
        image_url = "/static/images/placeholder_dump.jpg"

    # Category and Severity
    category = data.get("category")
    severity = int(data.get("severity") or 3)
    ai_materials = []
    ai_confidence = 0.92
    est_vol = data.get("estimated_volume", "1.5 - 2.5 m³")

    if ai_classification:
        if not category or category == "Auto-Detect (AI)":
            category = ai_classification["category"]
            severity = ai_classification["severity"]
        ai_materials = ai_classification.get("detected_materials", [])
        ai_confidence = ai_classification.get("confidence", 0.92)
        est_vol = ai_classification.get("estimated_volume_m3", est_vol)

    if not category:
        category = "Mixed Municipal Solid Waste"

    # Compute MCDA Priority Score
    priority_res = calculate_priority_score(
        severity=severity,
        lat=lat,
        lon=lon,
        upvotes=0,
        days_open=0.0
    )

    report_payload = {
        "title": data.get("title") or f"{category} on Roadside",
        "description": data.get("description", ""),
        "category": category,
        "severity": severity,
        "priority_score": priority_res["score"],
        "priority_level": priority_res["level"],
        "latitude": lat,
        "longitude": lon,
        "address": data.get("address", "Bengaluru Urban"),
        "ward_id": data.get("ward_id", "WARD-112"),
        "ward_name": data.get("ward_name", "Bengaluru Urban"),
        "status": "Reported",
        "image_url": image_url,
        "after_image_url": None,
        "upvotes": 0,
        "ai_confidence": ai_confidence,
        "ai_materials": ai_materials,
        "estimated_volume": est_vol,
        "closest_receptor_name": priority_res["closest_receptor"]["name"] if priority_res.get("closest_receptor") else None,
        "closest_receptor_dist": priority_res["closest_receptor"]["distance_m"] if priority_res.get("closest_receptor") else None,
        "notes": f"Initial report logged. Proximity: {priority_res.get('proximity_note', '')}"
    }

    created = create_report(report_payload)
    return jsonify({
        "success": True,
        "message": "Report submitted successfully",
        "report": created,
        "ai_analysis": ai_classification
    }), 201


@app.route("/api/reports/<report_id>/status", methods=["POST"])
def update_status(report_id):
    """
    Admin updates report status (Reported -> In Progress -> Cleared).
    Supports uploading an 'after_image' proof when marking as Cleared.
    """
    is_multipart = request.content_type and "multipart/form-data" in request.content_type
    if is_multipart:
        data = request.form.to_dict()
        after_file = request.files.get("after_photo")
    else:
        data = request.get_json() or {}
        after_file = None

    status = data.get("status")
    if not status or status not in ["Reported", "In Progress", "Cleared"]:
        return jsonify({"success": False, "error": "Invalid status value"}), 400

    after_image_url = data.get("after_image_url")
    if after_file:
        file_ext = os.path.splitext(after_file.filename)[1] or ".jpg"
        fname = f"cleared_{uuid.uuid4().hex[:10]}{file_ext}"
        fpath = os.path.join(UPLOAD_DIR, fname)
        after_file.save(fpath)
        after_image_url = f"/static/uploads/{fname}"

    actor = data.get("actor", "Municipal SWM Supervisor")
    notes = data.get("notes", "")

    updated = update_report_status(
        report_id=report_id,
        status=status,
        after_image_url=after_image_url,
        notes=notes,
        actor=actor
    )

    if not updated:
        return jsonify({"success": False, "error": "Report not found"}), 404

    return jsonify({"success": True, "message": "Status updated successfully", "report": updated})


@app.route("/api/reports/<report_id>/upvote", methods=["POST"])
def upvote(report_id):
    data = request.get_json() or {}
    user_token = data.get("user_token") or request.remote_addr or "anon_user"
    res = upvote_report(report_id, user_token=user_token)
    return jsonify(res)


# --- GeoAI Analytics Endpoints ---
@app.route("/api/hotspots", methods=["GET"])
def hotspots_endpoint():
    """
    Runs DBSCAN spatial clustering and returns ranked hotspots & heat points.
    """
    eps = float(request.args.get("eps_meters", 250.0))
    min_pts = int(request.args.get("min_samples", 3))

    all_reports = get_all_reports()
    clustering_res = run_dbscan_clustering(all_reports, eps_meters=eps, min_samples=min_pts)

    # Prepare heatmap coordinates: [lat, lon, intensity]
    heatmap_points = []
    for r in all_reports:
        # Intensity scaled by severity (1 to 5) and status
        status_mult = 1.0 if r.get("status") == "Reported" else 0.7 if r.get("status") == "In Progress" else 0.2
        intensity = round((r.get("severity", 3) / 5.0) * status_mult, 2)
        heatmap_points.append([float(r["latitude"]), float(r["longitude"]), intensity])

    return jsonify({
        "success": True,
        **clustering_res,
        "heatmap_points": heatmap_points
    })


@app.route("/api/wards", methods=["GET"])
def wards_endpoint():
    """
    Returns GeoJSON ward boundaries enriched with live statistics and cleanliness indices.
    """
    geojson_path = os.path.join(STATIC_DIR, "data", "bangalore_wards.geojson")
    if not os.path.exists(geojson_path):
        return jsonify({"success": False, "error": "Ward GeoJSON not found"}), 404

    with open(geojson_path, "r", encoding="utf-8") as f:
        wards_geojson = json.load(f)

    ward_stats = {w["ward_id"]: w for w in get_ward_stats()}

    # Merge stats into GeoJSON properties
    for feature in wards_geojson.get("features", []):
        wid = feature.get("properties", {}).get("ward_id")
        if wid in ward_stats:
            feature["properties"].update(ward_stats[wid])
        else:
            feature["properties"].update({
                "total_reports": 0,
                "open_reports": 0,
                "cleared_reports": 0,
                "clearance_rate": 100.0,
                "cleanliness_index": 95,
                "grade": "A (Clean)"
            })

    return jsonify({
        "success": True,
        "geojson": wards_geojson,
        "ward_leaderboard": sorted(list(ward_stats.values()), key=lambda x: x["cleanliness_index"], reverse=True),
        "worst_wards": sorted(list(ward_stats.values()), key=lambda x: x["open_reports"], reverse=True)
    })


@app.route("/api/route-optimizer", methods=["GET", "POST"])
def route_optimizer_endpoint():
    """
    Computes optimal pickup route for municipal waste trucks across open reports.
    """
    depot_key = request.args.get("depot", "central")
    cluster_id = request.args.get("cluster_id")
    max_stops = int(request.args.get("max_stops", 10))

    all_reports = get_all_reports(status="Reported")

    # If cluster specified, filter reports in that cluster
    target_reports = []
    if cluster_id is not None and cluster_id != "":
        clustering_res = run_dbscan_clustering(get_all_reports())
        matched = [c for c in clustering_res["clusters"] if str(c["cluster_id"]) == str(cluster_id)]
        if matched:
            rep_ids = set(matched[0]["report_ids"])
            target_reports = [r for r in all_reports if r["id"] in rep_ids]
    
    if not target_reports:
        # Pick top highest priority open reports
        sorted_reports = sorted(all_reports, key=lambda x: x["priority_score"], reverse=True)
        target_reports = sorted_reports[:max_stops]

    route_res = optimize_cleanup_route(target_reports, depot_key=depot_key)
    return jsonify({"success": True, **route_res, "available_depots": MUNICIPAL_DEPOTS})


@app.route("/api/analytics", methods=["GET"])
def analytics_endpoint():
    summary = get_analytics_summary()
    return jsonify({"success": True, **summary})


@app.route("/api/seed", methods=["POST"])
def reseed_endpoint():
    seed_database()
    return jsonify({"success": True, "message": "Database reseeded successfully with 55 dummy reports!"})


# --- Export Endpoints ---
@app.route("/api/export/geojson", methods=["GET"])
def export_geojson():
    reports = get_all_reports()
    features = []
    for r in reports:
        features.append({
            "type": "Feature",
            "properties": {
                "id": r["id"],
                "title": r["title"],
                "category": r["category"],
                "status": r["status"],
                "priority_level": r["priority_level"],
                "priority_score": r["priority_score"],
                "ward_name": r["ward_name"],
                "reported_at": r["reported_at"]
            },
            "geometry": {
                "type": "Point",
                "coordinates": [float(r["longitude"]), float(r["latitude"])]
            }
        })
    collection = {"type": "FeatureCollection", "features": features}
    return Response(
        json.dumps(collection, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment;filename=geo_waste_reports.geojson"}
    )


@app.route("/api/export/csv", methods=["GET"])
def export_csv():
    reports = get_all_reports()
    output = io.StringIO()
    writer = csv.writer(output)
    
    headers = [
        "ID", "Title", "Category", "Severity", "Priority Score", "Priority Level",
        "Latitude", "Longitude", "Ward Name", "Status", "Upvotes", "Reported At", "Cleared At"
    ]
    writer.writerow(headers)
    for r in reports:
        writer.writerow([
            r.get("id"), r.get("title"), r.get("category"), r.get("severity"),
            r.get("priority_score"), r.get("priority_level"), r.get("latitude"),
            r.get("longitude"), r.get("ward_name"), r.get("status"),
            r.get("upvotes"), r.get("reported_at"), r.get("cleared_at")
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=geo_waste_reports.csv"}
    )


# Ensure database exists and is seeded with realistic demonstration incidents
try:
    init_db()
    if len(get_all_reports()) == 0:
        seed_database()
except Exception as _db_err:
    print(f"Database auto-init notice: {_db_err}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Geo-Waste Reporter server on http://127.0.0.1:{port} ...")
    app.run(host="0.0.0.0", port=port, debug=True)
