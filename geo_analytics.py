"""
Geo-Analytics Engine for Geo-Waste Reporter
- Spatial Haversine Distance
- DBSCAN Density-Based Hotspot Clustering
- Multi-Criteria Decision Analysis (MCDA) Priority Scoring
- Sensitive Receptor Proximity Buffering (Lakes, Schools, Hospitals)
- Duplicate Detection
- 2-Opt Traveling Salesperson Problem (TSP) Route Optimization
"""

import json
import math
import os
import numpy as np

# Earth radius in meters
EARTH_RADIUS_M = 6371000.0

# Built-in sample of critical environmental & social receptors in Bengaluru (Lat, Lon, Name, Type)
SENSITIVE_RECEPTORS = []  # filled by _load_receptors() below
_BUILTIN_RECEPTORS = [
    # Water Bodies (Critical contamination risk)
    {"name": "Bellandur Lake", "type": "water_body", "lat": 12.9360, "lon": 77.6740},
    {"name": "Ulsoor Lake", "type": "water_body", "lat": 12.9832, "lon": 77.6200},
    {"name": "Sankey Tank", "type": "water_body", "lat": 13.0075, "lon": 77.5755},
    {"name": "Varthur Lake", "type": "water_body", "lat": 12.9550, "lon": 77.7470},
    {"name": "Hebbal Lake", "type": "water_body", "lat": 13.0450, "lon": 77.5900},
    {"name": "Madiwala Lake", "type": "water_body", "lat": 12.9150, "lon": 77.6200},

    # Healthcare / Hospitals (Disease & Biohazard vulnerability)
    {"name": "Manipal Hospital HAL", "type": "hospital", "lat": 12.9582, "lon": 77.6492},
    {"name": "Victoria Hospital KR Market", "type": "hospital", "lat": 12.9635, "lon": 77.5752},
    {"name": "Bowring & Lady Curzon Hospital", "type": "hospital", "lat": 12.9838, "lon": 77.6042},
    {"name": "Narayana Multispeciality Hospital HSR", "type": "hospital", "lat": 12.9125, "lon": 77.6391},
    {"name": "Columbia Asia Hospital Hebbal", "type": "hospital", "lat": 13.0400, "lon": 77.5920},

    # Educational Institutions (Children health risk)
    {"name": "Bishop Cotton Boys' School", "type": "school", "lat": 12.9720, "lon": 77.6025},
    {"name": "Mount Carmel College", "type": "school", "lat": 12.9935, "lon": 77.5912},
    {"name": "Christ University Koramangala", "type": "school", "lat": 12.9345, "lon": 77.6060},
    {"name": "IISc Bangalore Mathikere", "type": "school", "lat": 13.0210, "lon": 77.5670},
    {"name": "National Public School Indiranagar", "type": "school", "lat": 12.9785, "lon": 77.6420}
]

# Municipal SWM Hubs / Dispatch Depots
MUNICIPAL_DEPOTS = {
    "central": {"name": "BBMP SWM Central Hub (Corporation Circle)", "lat": 12.9716, "lon": 77.5946},
    "east": {"name": "BBMP East Division Hub (Indiranagar)", "lat": 12.9780, "lon": 77.6400},
    "south": {"name": "BBMP South Transfer Station (Koramangala)", "lat": 12.9350, "lon": 77.6250},
    "north": {"name": "BBMP North Zone SWM Hub (Hebbal)", "lat": 13.0350, "lon": 77.5950}
}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two GPS coordinates in meters."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_M * c


# --------------------------------------------------------------------------------------------------
# Receptor dataset: built-in sample list + optional full OpenStreetMap export (static/data/receptors.json).
# Generate the full file once with:  python fetch_receptors.py   (needs internet). Without it, the built-in
# list above is used, so nothing breaks.
# --------------------------------------------------------------------------------------------------
RECEPTORS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "data", "receptors.json")
_VALID_TYPES = ("water_body", "hospital", "school")
_REC_INDEX = {"list": [], "lat": None, "lon": None, "radius": None}


def _load_receptors():
    """Merges the built-in receptors with receptors.json (if present) and builds numpy arrays for fast search."""
    merged = [dict(r, radius_m=float(r.get("radius_m", 0))) for r in _BUILTIN_RECEPTORS]
    extra_count = 0
    if os.path.exists(RECEPTORS_FILE):
        try:
            with open(RECEPTORS_FILE, "r", encoding="utf-8") as fh:
                extra = json.load(fh)
            for r in extra:
                if r.get("type") in _VALID_TYPES and "lat" in r and "lon" in r:
                    merged.append({
                        "name": str(r.get("name") or r["type"].replace("_", " ").title())[:120],
                        "type": r["type"], "lat": float(r["lat"]), "lon": float(r["lon"]),
                        "radius_m": float(r.get("radius_m", 0) or 0),
                    })
                    extra_count += 1
        except Exception as exc:  # a broken file must never take the app down
            print(f"[GeoAI] Could not read {RECEPTORS_FILE}: {exc}. Using built-in receptors only.")
    _REC_INDEX["list"] = merged
    _REC_INDEX["lat"] = np.radians(np.array([r["lat"] for r in merged], dtype=float))
    _REC_INDEX["lon"] = np.radians(np.array([r["lon"] for r in merged], dtype=float))
    _REC_INDEX["radius"] = np.array([r["radius_m"] for r in merged], dtype=float)
    # Public name kept for backwards compatibility
    global SENSITIVE_RECEPTORS
    SENSITIVE_RECEPTORS = merged
    print(f"[GeoAI] Sensitive receptors loaded: {len(merged)} ({len(_BUILTIN_RECEPTORS)} built-in + {extra_count} from receptors.json)")


def _receptor_distances(lat: float, lon: float):
    """Vectorised haversine distance (metres) from a point to every receptor. Water bodies use the edge, not the centre."""
    phi1 = math.radians(lat)
    lam1 = math.radians(lon)
    dphi = _REC_INDEX["lat"] - phi1
    dlam = _REC_INDEX["lon"] - lam1
    a = np.sin(dphi / 2.0) ** 2 + math.cos(phi1) * np.cos(_REC_INDEX["lat"]) * np.sin(dlam / 2.0) ** 2
    d = 2.0 * EARTH_RADIUS_M * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
    return np.maximum(0.0, d - _REC_INDEX["radius"])


def find_closest_receptor(lat: float, lon: float):
    """Finds the nearest environmental or social sensitive receptor and distance in meters."""
    if not _REC_INDEX["list"]:
        return None
    d = _receptor_distances(lat, lon)
    i = int(np.argmin(d))
    return {**_REC_INDEX["list"][i], "distance_m": round(float(d[i]), 1)}


def receptors_within(lat: float, lon: float, radius_m: float = 700.0):
    """All receptors within radius_m, nearest first."""
    if not _REC_INDEX["list"]:
        return []
    d = _receptor_distances(lat, lon)
    idx = np.where(d <= radius_m)[0]
    idx = idx[np.argsort(d[idx])]
    return [{**_REC_INDEX["list"][int(i)], "distance_m": round(float(d[i]), 1)} for i in idx]


# Urgency boost (points) when a given kind of waste sits within 350 m of a given kind of receptor.
# Rationale: hazardous/medical waste endangers children and patients; organic waste and plastics foul water
# bodies; e-waste leaches toxins into water; construction debris is routinely dumped into lakes.
URGENCY_BOOST = {
    "Hazardous / Medical Waste":        {"hospital": 10, "school": 10, "water_body": 8},
    "Organic / Biodegradable Waste":    {"water_body": 10, "hospital": 5, "school": 5},
    "Electronic Waste (E-Waste)":       {"water_body": 8, "school": 5, "hospital": 3},
    "Plastic Waste":                    {"water_body": 8, "school": 3, "hospital": 3},
    "Construction & Demolition Debris": {"water_body": 8, "school": 5, "hospital": 3},
    "Mixed Municipal Solid Waste":      {"water_body": 5, "school": 5, "hospital": 5},
}
URGENCY_RADIUS_M = 350.0


_load_receptors()


def calculate_priority_score(severity: int, lat: float, lon: float, upvotes: int = 0, days_open: float = 0.0,
                             category: str = None) -> dict:
    """
    Computes GeoAI Multi-Criteria Decision Analysis (MCDA) Priority Score (0 - 100).
    Components:
    1. Base AI Waste Severity (1 to 5): 10 to 50 pts
    2. Proximity to the nearest Sensitive Receptor (Lakes, Hospitals, Schools): up to 30 pts
    3. Urgency boost: up to 10 pts when this KIND of waste is within 350 m of this KIND of receptor
       (e.g. hazardous/medical waste near a school or hospital, organic waste next to a lake)
    4. Vulnerable-area bonus: +5 pts when 2+ receptors lie within 700 m
    5. Citizen Upvotes: up to 15 pts (3 pts per upvote)
    6. Aging Factor (Days Open): up to 10 pts (2 pts per day)
    The total is capped at 100. Hazardous/medical waste within 150 m of a school or hospital is escalated to Critical.
    """
    severity = max(1, min(5, int(severity or 3)))
    base_score = severity * 10  # 10 to 50

    nearby = receptors_within(lat, lon, 700.0)
    receptor = nearby[0] if nearby else find_closest_receptor(lat, lon)
    dist = receptor["distance_m"] if receptor else 999999

    # Proximity points
    if dist < 150:
        proximity_score = 30
        proximity_note = f"Within 150m of {receptor['name']} ({receptor['type'].replace('_', ' ')})"
    elif dist < 350:
        proximity_score = 20
        proximity_note = f"Within 350m of {receptor['name']} ({receptor['type'].replace('_', ' ')})"
    elif dist < 700:
        proximity_score = 10
        proximity_note = f"Within 700m of {receptor['name']} ({receptor['type'].replace('_', ' ')})"
    else:
        proximity_score = 0
        far = f"{round(dist/1000, 1)} km to {receptor['name']}" if receptor else "none loaded"
        proximity_note = f"> 700m from sensitive receptors ({far})"

    # Urgency boost: best category-vs-receptor match inside 350 m
    urgency_score = 0
    urgency_note = ""
    matrix = URGENCY_BOOST.get(category or "", {})
    for r in nearby:
        if r["distance_m"] > URGENCY_RADIUS_M:
            break  # list is sorted nearest-first
        pts = matrix.get(r["type"], 0)
        if pts > urgency_score:
            urgency_score = pts
            urgency_note = f"{category} within {int(r['distance_m'])}m of {r['name']} ({r['type'].replace('_', ' ')}): +{pts} urgency"

    # Several vulnerable places close together
    density_score = 5 if len(nearby) >= 2 else 0

    upvote_score = min(15, upvotes * 3)
    age_score = min(10, int(days_open * 2))

    total = base_score + proximity_score + urgency_score + density_score + upvote_score + age_score
    total = max(5, min(100, total))

    # Public-health escalation: hazardous/medical waste right next to a school or hospital is always Critical
    escalated = False
    if category == "Hazardous / Medical Waste":
        for r in nearby:
            if r["distance_m"] >= 150:
                break
            if r["type"] in ("school", "hospital"):
                if total < 75:
                    total = 75
                    escalated = True
                urgency_note = (urgency_note + " | " if urgency_note else "") + (
                    f"ESCALATED to Critical: hazardous waste within {int(r['distance_m'])}m of {r['name']}" if escalated else "")
                break

    if total >= 75:
        level = "Critical"
        badge_color = "#ef4444" # red-500
    elif total >= 50:
        level = "High"
        badge_color = "#f97316" # orange-500
    elif total >= 30:
        level = "Medium"
        badge_color = "#eab308" # yellow-500
    else:
        level = "Low"
        badge_color = "#22c55e" # green-500

    return {
        "score": total,
        "level": level,
        "badge_color": badge_color,
        "breakdown": {
            "base_severity": base_score,
            "proximity_score": proximity_score,
            "urgency_boost": urgency_score,
            "vulnerable_area_bonus": density_score,
            "upvote_score": upvote_score,
            "age_score": age_score
        },
        "closest_receptor": receptor,
        "receptors_within_700m": len(nearby),
        "urgency_note": urgency_note,
        "proximity_note": proximity_note
    }


def check_for_duplicate(lat: float, lon: float, active_reports: list, threshold_m: float = 40.0) -> dict:
    """
    Checks if a new submission is within threshold meters of an existing open report.
    Returns details of duplicate candidate if found.
    """
    for r in active_reports:
        # Ignore already cleared reports for duplicate blocking
        if r.get("status") == "Cleared":
            continue
        r_lat = r.get("latitude")
        r_lon = r.get("longitude")
        if r_lat is None or r_lon is None:
            continue
        dist = haversine_distance(lat, lon, float(r_lat), float(r_lon))
        if dist <= threshold_m:
            return {
                "is_duplicate": True,
                "distance_m": round(dist, 1),
                "matched_report": {
                    "id": r.get("id"),
                    "title": r.get("title"),
                    "category": r.get("category"),
                    "status": r.get("status"),
                    "upvotes": r.get("upvotes", 0),
                    "reported_at": r.get("reported_at"),
                    "image_url": r.get("image_url")
                }
            }
    return {"is_duplicate": False}


def run_dbscan_clustering(reports: list, eps_meters: float = 250.0, min_samples: int = 3) -> dict:
    """
    Pure NumPy Density-Based Spatial Clustering (DBSCAN) on coordinates.
    Finds recurring waste dump hotspots.
    
    Returns:
    - clusters: list of hotspot clusters with centroid, size, report_ids, category breakdown, severity
    - ranked_hotspots: Top 10 sorted by recurring severity index
    - noise_reports: individual reports not part of a cluster
    """
    valid_reports = [r for r in reports if r.get("latitude") is not None and r.get("longitude") is not None]
    n = len(valid_reports)
    if n == 0:
        return {"clusters": [], "ranked_hotspots": [], "total_clusters": 0}

    # Extract coordinates
    coords = np.array([[float(r["latitude"]), float(r["longitude"])] for r in valid_reports])

    # Compute pairwise distance matrix in meters
    lat1 = np.radians(coords[:, 0:1])
    lon1 = np.radians(coords[:, 1:2])
    lat2 = np.radians(coords[:, 0:1].T)
    lon2 = np.radians(coords[:, 1:2].T)

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0)**2
    # Numerical safety
    a = np.clip(a, 0.0, 1.0)
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    dist_matrix = EARTH_RADIUS_M * c

    # DBSCAN implementation
    labels = np.full(n, -1, dtype=int)  # -1 is noise
    cluster_id = 0
    visited = np.zeros(n, dtype=bool)

    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True
        neighbors = np.where(dist_matrix[i] <= eps_meters)[0]

        if len(neighbors) < min_samples:
            labels[i] = -1
        else:
            labels[i] = cluster_id
            queue = list(neighbors[neighbors != i])

            while queue:
                current_p = queue.pop(0)
                if not visited[current_p]:
                    visited[current_p] = True
                    current_neighbors = np.where(dist_matrix[current_p] <= eps_meters)[0]
                    if len(current_neighbors) >= min_samples:
                        for neighbor in current_neighbors:
                            if neighbor not in queue and not visited[neighbor]:
                                queue.append(neighbor)
                if labels[current_p] == -1:
                    labels[current_p] = cluster_id

            cluster_id += 1

    # Aggregate cluster statistics
    clusters = []
    unique_labels = set(labels)
    if -1 in unique_labels:
        unique_labels.remove(-1)

    for cid in unique_labels:
        idx = np.where(labels == cid)[0]
        cluster_reports = [valid_reports[i] for i in idx]
        cluster_coords = coords[idx]

        center_lat = float(np.mean(cluster_coords[:, 0]))
        center_lon = float(np.mean(cluster_coords[:, 1]))

        # Calculate bounding box / radius
        distances_from_center = [haversine_distance(center_lat, center_lon, float(c[0]), float(c[1])) for c in cluster_coords]
        radius_m = max(50.0, float(max(distances_from_center)))

        # Category and status distribution
        categories = {}
        statuses = {"Reported": 0, "In Progress": 0, "Cleared": 0}
        severities = []
        priority_scores = []
        wards = {}

        for r in cluster_reports:
            cat = r.get("category", "General")
            categories[cat] = categories.get(cat, 0) + 1
            st = r.get("status", "Reported")
            statuses[st] = statuses.get(st, 0) + 1
            severities.append(float(r.get("severity", 3)))
            priority_scores.append(float(r.get("priority_score", 50)))
            w = r.get("ward_name", "Unknown Ward")
            wards[w] = wards.get(w, 0) + 1

        primary_category = max(categories.items(), key=lambda x: x[1])[0]
        primary_ward = max(wards.items(), key=lambda x: x[1])[0]
        avg_severity = round(float(np.mean(severities)), 1)
        avg_priority = round(float(np.mean(priority_scores)), 1)

        # Recurring dumping index = count * avg_severity * (1 + open_reports / total)
        open_count = statuses["Reported"] + statuses["In Progress"]
        dumping_index = round(len(cluster_reports) * avg_severity * (1.0 + (open_count / max(1, len(cluster_reports)))), 1)

        clusters.append({
            "cluster_id": int(cid),
            "name": f"Hotspot #{cid + 1} - {primary_ward}",
            "center": {"lat": round(center_lat, 5), "lon": round(center_lon, 5)},
            "radius_m": round(radius_m, 1),
            "total_reports": len(cluster_reports),
            "open_reports": open_count,
            "cleared_reports": statuses["Cleared"],
            "primary_category": primary_category,
            "primary_ward": primary_ward,
            "avg_severity": avg_severity,
            "avg_priority": avg_priority,
            "dumping_index": dumping_index,
            "categories": categories,
            "report_ids": [r.get("id") for r in cluster_reports]
        })

    # Sort hotspots by dumping index descending
    ranked_hotspots = sorted(clusters, key=lambda c: c["dumping_index"], reverse=True)

    return {
        "clusters": clusters,
        "ranked_hotspots": ranked_hotspots[:10],
        "total_clusters": len(clusters),
        "total_clustered_reports": sum(c["total_reports"] for c in clusters),
        "eps_meters": eps_meters,
        "min_samples": min_samples
    }


def optimize_cleanup_route(target_reports: list, depot_key: str = "central") -> dict:
    """
    2-Opt Traveling Salesperson Problem (TSP) solver for municipal waste cleanup trucks.
    Starts at depot, visits all selected report points, and returns to depot.
    NOTE: `baseline_distance_km` is the distance if trucks visited the stops in the order given
    (callers pass them sorted by priority), i.e. "priority-order dispatch" - not the DB row order.
    Computes total distance, optimized order, and carbon emissions saved.
    """
    depot = MUNICIPAL_DEPOTS.get(depot_key, MUNICIPAL_DEPOTS["central"])
    if not target_reports:
        return {"waypoints": [], "total_distance_km": 0.0, "estimated_hours": 0.0}

    # Build points list: 0 is depot, 1..N are reports
    points = [{"name": depot["name"], "lat": depot["lat"], "lon": depot["lon"], "is_depot": True, "id": "DEPOT"}]
    for r in target_reports:
        points.append({
            "name": r.get("title", f"Report #{r.get('id')}"),
            "id": r.get("id"),
            "lat": float(r["latitude"]),
            "lon": float(r["longitude"]),
            "category": r.get("category"),
            "severity": r.get("severity", 3),
            "is_depot": False
        })

    num_points = len(points)
    if num_points <= 1:
        return {"waypoints": points, "total_distance_km": 0.0, "estimated_hours": 0.0}

    # Calculate distance matrix
    dist_mat = np.zeros((num_points, num_points))
    for i in range(num_points):
        for j in range(num_points):
            if i != j:
                dist_mat[i][j] = haversine_distance(points[i]["lat"], points[i]["lon"], points[j]["lat"], points[j]["lon"])

    # Baseline = visit stops in the order supplied by the caller (priority order): 0 -> 1 -> ... -> N -> 0
    baseline_dist = sum(dist_mat[i][(i + 1) % num_points] for i in range(num_points))

    # Nearest Neighbor Initial Route
    unvisited = set(range(1, num_points))
    current = 0
    route = [0]
    while unvisited:
        next_point = min(unvisited, key=lambda x: dist_mat[current][x])
        route.append(next_point)
        unvisited.remove(next_point)
        current = next_point
    route.append(0)  # return to depot

    # 2-Opt Optimization
    improved = True
    iterations = 0
    while improved and iterations < 50:
        improved = False
        iterations += 1
        for i in range(1, len(route) - 2):
            for j in range(i + 1, len(route) - 1):
                # Check if reversing route[i:j+1] gives shorter distance
                a, b = route[i - 1], route[i]
                c, d = route[j], route[j + 1]
                current_cost = dist_mat[a][b] + dist_mat[c][d]
                new_cost = dist_mat[a][c] + dist_mat[b][d]
                if new_cost < current_cost - 1e-4:
                    route[i:j + 1] = reversed(route[i:j + 1])
                    improved = True
                    break
            if improved:
                break

    # Calculate final route distance
    optimized_dist_m = sum(dist_mat[route[k]][route[k + 1]] for k in range(len(route) - 1))
    dist_saved_m = max(0.0, baseline_dist - optimized_dist_m)
    percent_saved = round((dist_saved_m / max(1.0, baseline_dist)) * 100.0, 1) if baseline_dist > 0 else 0

    # Diesel truck emissions: approx 0.85 kg CO2 per km for heavy municipal truck
    co2_saved_kg = round((dist_saved_m / 1000.0) * 0.85, 2)

    # Time estimate: 22 km/h average city transit speed + 20 mins per cleanup stop
    driving_hours = (optimized_dist_m / 1000.0) / 22.0
    cleanup_stops_hours = (len(target_reports) * 20.0) / 60.0
    total_hours = round(driving_hours + cleanup_stops_hours, 1)

    ordered_waypoints = []
    for step_num, p_idx in enumerate(route):
        point_data = dict(points[p_idx])
        point_data["step_number"] = step_num + 1
        ordered_waypoints.append(point_data)

    return {
        "depot": depot,
        "total_stops": len(target_reports),
        "total_distance_km": round(optimized_dist_m / 1000.0, 2),
        "baseline_distance_km": round(baseline_dist / 1000.0, 2),
        "distance_saved_km": round(dist_saved_m / 1000.0, 2),
        "efficiency_gain_percent": percent_saved,
        "co2_saved_kg": co2_saved_kg,
        "estimated_duration_hours": total_hours,
        "waypoints": ordered_waypoints,
        "polyline_coords": [[p["lat"], p["lon"]] for p in ordered_waypoints]
    }


def point_in_polygon(lon: float, lat: float, poly: list) -> bool:
    """Ray-casting algorithm to test if (lon, lat) is inside a polygon."""
    n = len(poly)
    inside = False
    p1x, p1y = poly[0]
    for i in range(1, n + 1):
        p2x, p2y = poly[i % n]
        if lat > min(p1y, p2y):
            if lat <= max(p1y, p2y):
                if lon <= max(p1x, p2x):
                    xints = (lat - p1y) * (p2x - p1x) / (p2y - p1y) + p1x if p1y != p2y else p1x
                    if p1x == p2x or lon <= xints:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def lookup_ward_and_address(lat: float, lon: float, wards_geojson_path: str = None) -> dict:
    """
    Reverse geocodes coordinates to a BBMP Ward and authentic street address / landmark.
    Uses point-in-polygon against Bengaluru wards GeoJSON + proximity to known landmarks.
    """
    import os, json

    matched_ward = None
    if wards_geojson_path and os.path.exists(wards_geojson_path):
        try:
            with open(wards_geojson_path, "r", encoding="utf-8") as f:
                geo = json.load(f)
            for feat in geo.get("features", []):
                coords = feat.get("geometry", {}).get("coordinates", [])
                if coords:
                    ring = coords[0]
                    if point_in_polygon(lon, lat, ring):
                        matched_ward = feat.get("properties", {})
                        break
        except Exception:
            pass

    # Closest landmark / sensitive receptor
    closest_rec = find_closest_receptor(lat, lon)

    # Ward fallback if outside precise polygons
    if not matched_ward:
        # Ward centroid estimates
        ward_centroids = [
            {"ward_id": "WARD-112", "ward_name": "Domlur & Indiranagar", "lat": 12.973, "lon": 77.644},
            {"ward_id": "WARD-151", "ward_name": "Koramangala", "lat": 12.933, "lon": 77.625},
            {"ward_id": "WARD-150", "ward_name": "Bellandur (Catchment)", "lat": 12.935, "lon": 77.675},
            {"ward_id": "WARD-85", "ward_name": "Whitefield & Kadugodi", "lat": 12.975, "lon": 77.746},
            {"ward_id": "WARD-174", "ward_name": "HSR Layout", "lat": 12.913, "lon": 77.643},
            {"ward_id": "WARD-45", "ward_name": "Malleshwaram", "lat": 13.008, "lon": 77.571},
            {"ward_id": "WARD-84", "ward_name": "Peenya Industrial Area", "lat": 13.029, "lon": 77.523},
            {"ward_id": "WARD-93", "ward_name": "Shivajinagar & Commercial St", "lat": 12.985, "lon": 77.605},
            {"ward_id": "WARD-168", "ward_name": "Jayanagar", "lat": 12.928, "lon": 77.585},
            {"ward_id": "WARD-20", "ward_name": "Hebbal & Kempapura", "lat": 13.045, "lon": 77.595}
        ]
        best_w = min(ward_centroids, key=lambda w: haversine_distance(lat, lon, w["lat"], w["lon"]))
        matched_ward = best_w

    ward_name = matched_ward.get("ward_name", "Bengaluru Urban")
    ward_id = matched_ward.get("ward_id", "WARD-00")

    # Authentic landmark address synthesis
    rec_name = closest_rec["name"] if closest_rec else "Main Road"
    rec_dist = closest_rec["distance_m"] if closest_rec else 500

    if rec_dist < 200:
        address = f"Adjacent to {rec_name}, {ward_name}, Bengaluru"
    elif rec_dist < 600:
        address = f"Near {rec_name} ({round(rec_dist)}m), {ward_name}, Bengaluru"
    else:
        address = f"Service Road, {ward_name}, Bengaluru"

    return {
        "ward_id": ward_id,
        "ward_name": ward_name,
        "address": address,
        "closest_receptor": closest_rec,
        "latitude": round(lat, 6),
        "longitude": round(lon, 6)
    }

