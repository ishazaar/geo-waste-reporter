"""
Downloads REAL sensitive receptors (schools/colleges, hospitals, named lakes/ponds/tanks) for Bengaluru from
OpenStreetMap via the Overpass API and writes static/data/receptors.json.

Run once on a machine WITH internet access, then commit the generated file:

    python fetch_receptors.py
    git add static/data/receptors.json && git commit -m "Add OSM receptors" && git push

The app loads this file automatically at startup (see geo_analytics.py). If the file is missing the app
falls back to its small built-in sample list, so this step is optional but makes the scoring far more complete.
Data (c) OpenStreetMap contributors, ODbL.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

# Bengaluru metropolitan bounding box: south, west, north, east
BBOX = (12.83, 77.45, 13.14, 77.78)
OUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "data", "receptors.json")
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


def build_query(bbox=BBOX) -> str:
    b = ",".join(str(x) for x in bbox)
    return f"""
[out:json][timeout:180];
(
  nwr["amenity"~"^(school|college|university)$"]["name"]({b});
  nwr["amenity"="hospital"]["name"]({b});
  nwr["natural"="water"]["name"]({b});
  nwr["water"~"^(lake|pond|reservoir)$"]["name"]({b});
);
out tags bb;
""".strip()


def _center_and_radius(el):
    """Returns (lat, lon, radius_m). Nodes have lat/lon; ways/relations come with a bounding box."""
    if "lat" in el and "lon" in el:
        return float(el["lat"]), float(el["lon"]), 0.0
    bb = el.get("bounds")
    if not bb:
        return None
    lat = (bb["minlat"] + bb["maxlat"]) / 2.0
    lon = (bb["minlon"] + bb["maxlon"]) / 2.0
    # half the longer side of the bounding box, in metres (111,320 m per degree of latitude; scale longitude)
    import math
    h = (bb["maxlat"] - bb["minlat"]) * 111320.0
    w = (bb["maxlon"] - bb["minlon"]) * 111320.0 * math.cos(math.radians(lat))
    return lat, lon, max(h, w) / 2.0


def parse_overpass(elements):
    """Converts Overpass elements into receptor records, de-duplicating by (type, name, ~100 m cell)."""
    out, seen = [], set()
    for el in elements:
        tags = el.get("tags", {})
        name = (tags.get("name:en") or tags.get("name") or "").strip()
        if not name:
            continue
        amenity = tags.get("amenity")
        if amenity in ("school", "college", "university"):
            rtype = "school"
        elif amenity == "hospital":
            rtype = "hospital"
        elif tags.get("natural") == "water" or tags.get("water") in ("lake", "pond", "reservoir"):
            rtype = "water_body"
        else:
            continue
        geo = _center_and_radius(el)
        if not geo:
            continue
        lat, lon, radius = geo
        # Only buildings/points use a tiny radius; water bodies use the edge distance
        if rtype != "water_body":
            radius = 0.0
        key = (rtype, name.lower(), round(lat, 3), round(lon, 3))
        if key in seen:
            continue
        seen.add(key)
        out.append({"name": name[:120], "type": rtype, "lat": round(lat, 6), "lon": round(lon, 6),
                    "radius_m": round(radius, 1)})
    out.sort(key=lambda r: (r["type"], r["name"]))
    return out


def fetch(query: str):
    data = urllib.parse.urlencode({"data": query}).encode()
    last = None
    for attempt in range(2):
        for url in ENDPOINTS:
            try:
                print(f"Querying {url} ...")
                req = urllib.request.Request(url, data=data, headers={"User-Agent": "geo-waste-reporter/1.0"})
                with urllib.request.urlopen(req, timeout=200) as resp:
                    return json.loads(resp.read().decode("utf-8"))["elements"]
            except Exception as exc:  # try the next mirror
                last = exc
                print(f"  failed: {exc}")
        time.sleep(5)
    raise SystemExit(f"All Overpass endpoints failed ({last}). Check your internet connection and try again.")


def main():
    elements = fetch(build_query())
    receptors = parse_overpass(elements)
    counts = {t: sum(1 for r in receptors if r["type"] == t) for t in ("school", "hospital", "water_body")}
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as fh:
        json.dump(receptors, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"Wrote {len(receptors)} receptors to {OUT_FILE}: {counts}")
    print("Restart the app (python app.py) to use them.")


if __name__ == "__main__":
    sys.exit(main())
