"""
Geo-Analytics Engine for Geo-Waste Reporter
- Spatial Haversine Distance
- DBSCAN Density-Based Hotspot Clustering
- Multi-Criteria Decision Analysis (MCDA) Priority Scoring
- Sensitive Receptor Proximity Buffering (Lakes, Schools, Hospitals)
- Duplicate Detection
- 2-Opt Traveling Salesperson Problem (TSP) Route Optimization
"""

from datetime import datetime, timedelta, timezone
import math
import json
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np

# Earth radius in meters
EARTH_RADIUS_M = 6371000.0

# Critical Environmental & Social Receptors in Bengaluru (Lat, Lon, Name, Type)
SENSITIVE_RECEPTORS = [
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


def find_closest_receptor(lat: float, lon: float):
    """Finds the nearest environmental or social sensitive receptor and distance in meters."""
    closest = None
    min_dist = float("inf")
    for r in SENSITIVE_RECEPTORS:
        d = haversine_distance(lat, lon, r["lat"], r["lon"])
        if d < min_dist:
            min_dist = d
            closest = {**r, "distance_m": round(d, 1)}
    return closest


# ---------------------------------------------------------------------------------------------
# Live sensitive-place lookup (OpenStreetMap / Overpass). Finds EVERY school, hospital/clinic and named
# water body around a pin, anywhere in Bengaluru. Falls back to the built-in list if Overpass is down.
# ---------------------------------------------------------------------------------------------
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]
LOOKUP_RADIUS_M = 700          # receptors further than this add no priority points
_QUERY_RADIUS_M = 900          # cached query is a little wider than the lookup radius
_OSM_TTL_S = 6 * 3600
_OSM_FAIL_TTL_S = 30
_OSM_CACHE = {}                # (rounded lat, rounded lon) -> (timestamp, elements or None)
_UA = "geo-waste-reporter/1.0 (student project)"

PEOPLE_TYPES = ("school", "hospital")   # places where people are most vulnerable -> urgent clean-up
TYPE_LABEL = {"school": "School", "hospital": "Hospital / clinic", "water_body": "Water body"}


def _classify_osm(tags: dict):
    amenity = tags.get("amenity")
    if amenity in ("school", "kindergarten", "college", "university"):
        return "school"
    if amenity in ("hospital", "clinic") or tags.get("healthcare") in ("hospital", "clinic"):
        return "hospital"
    if tags.get("natural") == "water" and tags.get("name"):
        return "water_body"
    return None


def _overpass_query(lat: float, lon: float) -> str:
    r = _QUERY_RADIUS_M
    return (
        "[out:json][timeout:8];("
        f'nwr["amenity"~"^(school|kindergarten|college|university|hospital|clinic)$"](around:{r},{lat},{lon});'
        f'nwr["healthcare"~"^(hospital|clinic)$"](around:{r},{lat},{lon});'
        f'nwr["natural"="water"]["name"](around:{r},{lat},{lon});'
        ");out center tags 80;"
    )


def _query_mirror(url: str, query: str, timeout: float, diag: dict = None):
    t0 = time.time()
    try:
        data = urllib.parse.urlencode({"data": query}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            els = json.loads(resp.read().decode("utf-8")).get("elements", [])
        if diag is not None:
            diag[url] = f"ok: {len(els)} places in {round((time.time() - t0) * 1000)} ms"
        return els
    except Exception as e:
        if diag is not None:
            diag[url] = f"FAILED after {round((time.time() - t0) * 1000)} ms: {type(e).__name__}: {str(e)[:100]}"
        raise


def _nominatim_amenities(lat: float, lon: float, diag: dict = None, timeout: float = 4.0):
    """
    Backup source (separate servers from Overpass): asks Nominatim for schools / hospitals / clinics /
    colleges in a ~1 km box around the pin. Returns Overpass-style elements, or raises if every call failed.
    """
    dlat, dlon = 0.009, 0.0095
    viewbox = f"{lon - dlon},{lat + dlat},{lon + dlon},{lat - dlat}"

    def one(term):
        qs = urllib.parse.urlencode({"q": term, "format": "jsonv2", "limit": 30, "bounded": 1,
                                     "viewbox": viewbox, "countrycodes": "in"})
        req = urllib.request.Request("https://nominatim.openstreetmap.org/search?" + qs,
                                     headers={"User-Agent": _UA, "Accept-Language": "en"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return term, json.loads(resp.read().decode("utf-8"))

    elements, ok = [], 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = [pool.submit(one, t) for t in ("school", "hospital", "clinic", "college")]
        for f in futs:
            try:
                term, items = f.result(timeout=timeout + 1)
                ok += 1
                for it in items:
                    elements.append({"lat": float(it["lat"]), "lon": float(it["lon"]),
                                     "tags": {"amenity": it.get("type") or term,
                                              "name": it.get("name") or (it.get("display_name", "").split(",")[0])}})
            except Exception as e:
                if diag is not None:
                    diag["nominatim:" + str(f)[-12:]] = f"FAILED: {type(e).__name__}: {str(e)[:80]}"
    if diag is not None:
        diag["nominatim (backup)"] = f"{ok}/4 queries ok, {len(elements)} places in {round((time.time() - t0) * 1000)} ms"
    if ok == 0:
        raise RuntimeError("Nominatim backup failed")
    return elements


def fetch_osm_elements(lat: float, lon: float, overall_timeout: float = 5.0):
    """
    Races all Overpass mirrors; if none answers in time, uses the Nominatim backup. Returns a list of
    Overpass-style elements, or None when every source failed. Results are cached.
    """
    key = (round(lat, 3), round(lon, 3))
    now = time.time()
    hit = _OSM_CACHE.get(key)
    if hit:
        ttl = _OSM_TTL_S if hit[1] is not None else _OSM_FAIL_TTL_S
        if now - hit[0] < ttl:
            return hit[1]

    query = _overpass_query(key[0], key[1])
    elements = None
    pool = ThreadPoolExecutor(max_workers=len(OVERPASS_MIRRORS) + 1)
    try:
        futures = [pool.submit(_query_mirror, m, query, overall_timeout + 1) for m in OVERPASS_MIRRORS]
        backup = pool.submit(_nominatim_amenities, key[0], key[1])
        try:
            for fut in as_completed(futures, timeout=overall_timeout):
                try:
                    elements = fut.result()
                    break
                except Exception:
                    continue
        except Exception:
            pass
        if elements is None:   # Overpass gave nothing in time -> use the backup source
            try:
                elements = backup.result(timeout=4.5)
            except Exception:
                elements = None
    finally:
        pool.shutdown(wait=False)
    _OSM_CACHE[key] = (now, elements)
    return elements


def diagnose_osm(lat: float, lon: float) -> dict:
    """Setup check: tries every source once and reports what happened (used by /api/osm-test)."""
    diag = {}
    query = _overpass_query(round(lat, 3), round(lon, 3))
    with ThreadPoolExecutor(max_workers=len(OVERPASS_MIRRORS)) as pool:
        futs = [pool.submit(_query_mirror, m, query, 9.0, diag) for m in OVERPASS_MIRRORS]
        for f in futs:
            try:
                f.result(timeout=10)
            except Exception:
                pass
    try:
        _nominatim_amenities(lat, lon, diag)
    except Exception:
        pass
    return diag


def nearby_receptors(lat: float, lon: float, radius_m: float = LOOKUP_RADIUS_M):
    """
    Returns (receptors, source). Each receptor: name, type, lat, lon, distance_m. Sorted nearest first.
    source is "openstreetmap" when the live lookup worked, otherwise "builtin" (small hard-coded list).
    """
    found, seen = [], set()
    elements = fetch_osm_elements(lat, lon)
    source = "openstreetmap" if elements is not None else "builtin"

    for el in elements or []:
        tags = el.get("tags") or {}
        rtype = _classify_osm(tags)
        if not rtype:
            continue
        rlat = el.get("lat", (el.get("center") or {}).get("lat"))
        rlon = el.get("lon", (el.get("center") or {}).get("lon"))
        if rlat is None or rlon is None:
            continue
        d = haversine_distance(lat, lon, rlat, rlon)
        if d > radius_m:
            continue
        name = tags.get("name") or f"{TYPE_LABEL[rtype]} (unnamed)"
        uid = (name.lower(), rtype, round(rlat, 4), round(rlon, 4))
        if uid in seen:
            continue
        seen.add(uid)
        found.append({"name": name, "type": rtype, "lat": rlat, "lon": rlon, "distance_m": round(d, 1)})

    # Always merge the built-in list too (covers famous lakes whose OSM outline is huge / far-centred)
    names = {f["name"].lower() for f in found}
    for r in SENSITIVE_RECEPTORS:
        d = haversine_distance(lat, lon, r["lat"], r["lon"])
        if d <= radius_m and r["name"].lower() not in names:
            found.append({**r, "distance_m": round(d, 1)})

    found.sort(key=lambda x: x["distance_m"])
    return found, source


def sanitize_client_receptors(raw, lat: float, lon: float, max_items: int = 40, max_dist_m: float = 1200.0):
    """
    Validates a place list sent by the browser (the browser looks up OpenStreetMap itself when the server
    cannot). Types are whitelisted, text is trimmed, and distances are recomputed here from the coordinates.
    Returns a clean list, or None if the input is not a list.
    """
    if not isinstance(raw, list):
        return None
    clean = []
    for it in raw[:max_items]:
        try:
            rtype = it.get("type")
            if rtype not in TYPE_LABEL:
                continue
            rlat, rlon = float(it["lat"]), float(it["lon"])
            d = haversine_distance(lat, lon, rlat, rlon)
            if d > max_dist_m:
                continue
            name = str(it.get("name") or f"{TYPE_LABEL[rtype]} (unnamed)")[:120]
            clean.append({"name": name, "type": rtype, "lat": rlat, "lon": rlon, "distance_m": round(d, 1)})
        except Exception:
            continue
    clean.sort(key=lambda x: x["distance_m"])
    return clean


def merge_with_builtin(receptors: list, lat: float, lon: float, radius_m: float = LOOKUP_RADIUS_M) -> list:
    """Adds the built-in famous places (lakes etc.) to a list, skipping ones already present by name."""
    out = [r for r in receptors if r["distance_m"] <= radius_m]
    names = {r["name"].lower() for r in out}
    for r in SENSITIVE_RECEPTORS:
        d = haversine_distance(lat, lon, r["lat"], r["lon"])
        if d <= radius_m and r["name"].lower() not in names:
            out.append({**r, "distance_m": round(d, 1)})
    out.sort(key=lambda x: x["distance_m"])
    return out


def _proximity_points(dist: float) -> int:
    return 30 if dist < 150 else 20 if dist < 350 else 10 if dist < 700 else 0


def pick_best_receptor(receptors):
    """Most important receptor = most proximity points, then schools/hospitals over water, then nearest."""
    if not receptors:
        return None
    return max(receptors, key=lambda r: (_proximity_points(r["distance_m"]),
                                         1 if r["type"] in PEOPLE_TYPES else 0,
                                         -r["distance_m"]))


def receptor_from_report(report: dict):
    """Rebuilds the receptor saved with a report (so re-scoring never needs a network call)."""
    report = dict(report)  # also accepts sqlite3.Row
    name, dist, rtype = (report.get("closest_receptor_name"), report.get("closest_receptor_dist"),
                         report.get("closest_receptor_type"))
    if name and dist is not None and rtype:
        return {"name": name, "type": rtype, "distance_m": float(dist)}
    return None


def calculate_priority_score(severity: int, lat: float, lon: float, upvotes: int = 0, days_open: float = 0.0,
                             receptors=None, receptor=None, category: str = None) -> dict:
    """
    Location-driven priority score (0 - 100).
      1. Waste severity (1-5): 10 to 50 pts
      2. Proximity to schools / hospitals / water bodies: up to 30 pts (<150 m 30, <350 m 20, <700 m 10)
      3. Citizen upvotes: up to 15 pts   4. Age: up to 10 pts
    URGENT RULE: a dump within 150 m of a school or hospital is always at least CRITICAL; within 350 m at
    least HIGH, no matter how small the dump looks.
    `receptors` = list from nearby_receptors(); `receptor` = one stored receptor; neither = built-in list.
    `category` is accepted (and currently unused) so callers that pass it, e.g. seed_data.py, keep working.
    """
    severity = max(1, min(5, int(severity or 3)))
    base_score = severity * 10

    if receptor is None:
        if receptors is None:
            receptors = [{**r, "distance_m": haversine_distance(lat, lon, r["lat"], r["lon"])}
                         for r in SENSITIVE_RECEPTORS]
        receptor = pick_best_receptor(receptors)
    dist = receptor["distance_m"] if receptor else 999999
    rtype = receptor["type"] if receptor else None
    label = TYPE_LABEL.get(rtype, "place")

    proximity_score = _proximity_points(dist)
    if receptor and proximity_score:
        proximity_note = f"{round(dist)} m from {receptor['name']} ({label.lower()})"
    else:
        proximity_note = "No school, hospital or water body within 700 m"

    upvote_score = min(15, upvotes * 3)
    age_score = min(10, int(days_open * 2))
    total = max(5, min(100, base_score + proximity_score + upvote_score + age_score))

    escalated = False
    if rtype in PEOPLE_TYPES:
        floor = 75 if dist < 150 else 50 if dist < 350 else 0
        if floor and total < floor:
            total, escalated = floor, True
            proximity_note += " - escalated"

    if total >= 75:
        level, badge_color = "Critical", "#ef4444"
    elif total >= 50:
        level, badge_color = "High", "#f97316"
    elif total >= 30:
        level, badge_color = "Medium", "#eab308"
    else:
        level, badge_color = "Low", "#22c55e"

    return {
        "score": total, "level": level, "badge_color": badge_color, "escalated": escalated,
        "breakdown": {"base_severity": base_score, "proximity_score": proximity_score,
                      "upvote_score": upvote_score, "age_score": age_score},
        "closest_receptor": ({**receptor, "distance_m": round(dist, 1)} if receptor else None),
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



# ---------------------------------------------------------------------------------------------
# Repeat-dump ("gets dirty again") analysis
# ---------------------------------------------------------------------------------------------
def _parse_dt(value):
    try:
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def find_repeat_dump_sites(reports: list, radius_m: float = 50.0, now=None) -> dict:
    """
    Finds places that were cleaned and then got dumped on again.
      1. Reports within `radius_m` of each other are treated as the SAME spot.
      2. A "relapse" = a report filed AFTER an earlier report at that spot had been cleared.
      3. Each repeat spot gets a risk score and a prediction of when it will be dirty again,
         based on its own average clean-to-re-dump gap.
    """
    now = now or datetime.now(timezone.utc)
    pts = [r for r in reports if r.get("latitude") is not None and r.get("longitude") is not None
           and _parse_dt(r.get("reported_at"))]
    n = len(pts)

    # union-find grouping of reports into spots
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if haversine_distance(pts[i]["latitude"], pts[i]["longitude"],
                                  pts[j]["latitude"], pts[j]["longitude"]) <= radius_m:
                parent[find(i)] = find(j)

    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(pts[i])

    sites = []
    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort(key=lambda r: _parse_dt(r["reported_at"]))
        gaps = []          # days between a clean-up and the next dump at the same spot
        last_cleared = None
        relapse_dates = []
        for r in members:
            rep_dt = _parse_dt(r["reported_at"])
            if last_cleared is not None and rep_dt > last_cleared:
                gaps.append((rep_dt - last_cleared).total_seconds() / 86400.0)
                relapse_dates.append(rep_dt)
            clr = _parse_dt(r.get("cleared_at")) if r.get("status") == "Cleared" else None
            if clr and (last_cleared is None or clr > last_cleared):
                last_cleared = clr
        if not gaps:
            continue   # never re-dumped after a clean-up, so not a repeat spot

        cleanups = sum(1 for r in members if r.get("status") == "Cleared")
        open_now = [r for r in members if r.get("status") != "Cleared"]
        avg_gap = sum(gaps) / len(gaps)
        days_since_relapse = (now - relapse_dates[-1]).total_seconds() / 86400.0

        score = min(60, len(gaps) * 20)
        score += 15 if days_since_relapse <= 30 else 0
        score += 10 if open_now else 0
        score += 15 if avg_gap <= 14 else 8 if avg_gap <= 30 else 0
        score = min(100, score)
        level = "Chronic" if score >= 70 else "Recurring" if score >= 45 else "Watch"

        clat = sum(r["latitude"] for r in members) / len(members)
        clon = sum(r["longitude"] for r in members) / len(members)
        latest = members[-1]
        cats = {}
        for r in members:
            cats[r.get("category")] = cats.get(r.get("category"), 0) + 1

        if open_now:
            predicted_iso, days_until = None, None
            prediction = f"Dirty again right now (re-dumped {round(days_since_relapse)} day{"s" if round(days_since_relapse) != 1 else ""} ago, after the last clean-up)."
        else:
            due = last_cleared + timedelta(days=avg_gap)
            days_until = round((due - now).total_seconds() / 86400.0)
            predicted_iso = due.isoformat()
            if days_until > 0:
                prediction = f"Expected to be dirty again in about {days_until} day{'s' if days_until != 1 else ''} (usual gap: {round(avg_gap)} days)."
            else:
                prediction = f"Overdue: it usually gets dirty again about {round(avg_gap)} days after clean-up. Check it now."

        sites.append({
            "site_id": f"RS-{len(sites) + 1}",
            "latitude": round(clat, 6), "longitude": round(clon, 6),
            "name": (members[0].get("title") or members[0].get("address") or "Repeat dump spot"),
            "ward_name": latest.get("ward_name"),
            "primary_category": max(cats, key=cats.get),
            "total_reports": len(members), "cleanups": cleanups, "relapses": len(gaps),
            "avg_days_until_dirty_again": round(avg_gap, 1),
            "currently_dirty": bool(open_now),
            "last_cleared_at": last_cleared.isoformat() if last_cleared else None,
            "predicted_next_dump": predicted_iso, "days_until_next": days_until,
            "prediction": prediction,
            "risk_score": score, "level": level,
            "recommendation": ("Permanent fix needed: fencing/CCTV, a bin or collection point, and fines for dumping. "
                               "Repeated clean-ups alone are not working here.") if level == "Chronic" else
                              "Schedule regular patrols and a bin or signage here.",
            "report_ids": [r["id"] for r in members],
        })

    sites.sort(key=lambda x: (-x["risk_score"], -x["relapses"]))
    for i, st in enumerate(sites, 1):
        st["site_id"] = f"RS-{i}"
    return {"sites": sites, "summary": {"count": len(sites), "total_relapses": sum(x["relapses"] for x in sites),
                                        "dirty_now": sum(1 for x in sites if x["currently_dirty"])}}
