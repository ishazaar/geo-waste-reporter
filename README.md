# 🌿 Geo-Waste Reporter (Problem 10)
### *AI-Powered Citizen Geospatial Platform for Illegal Dumping Detection, Hotspot Analytics & Smart Municipal Cleanup*

[![GeoAI Hackathon 2026](https://img.shields.io/badge/GeoAI-Hackathon_2026-10b981.svg)](https://github.com)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Backend-Flask_3.1-black.svg)](https://flask.palletsprojects.com/)
[![Leaflet](https://img.shields.io/badge/Maps-Leaflet_1.9-green.svg)](https://leafletjs.com/)
[![TailwindCSS](https://img.shields.io/badge/Styling-Tailwind_CSS-38bdf8.svg)](https://tailwindcss.com/)

---

## 📌 Executive Summary

Illegal municipal solid waste and demolition debris dumping ("black spots") pose grave threats to public health, urban flood mitigation, and water body ecosystems in cities across India. Traditional municipal grievance systems suffer from:
1. Low citizen reporting due to tedious manual form-filling.
2. Cluttered duplicate tickets for the same dump site.
3. Lack of spatial intelligence to prioritize hazards near lakes, hospitals, and schools.
4. Unoptimized, arbitrary truck dispatching that wastes fuel.
5. Zero photographic proof or accountability when tickets are closed.

**Geo-Waste Reporter** solves this through an end-to-end GeoAI platform:
- **Zero-Friction Citizen AI:** Citizens upload a photo; the classifier suggests the waste category (Plastic, C&D Debris, Organic, E-Waste, Hazardous, Mixed MSW), estimates severity and volume, and locks the GPS location.
- **Spatial Deduplication (30m–50m buffer):** Prevents duplicate clutter by identifying nearby active reports and prompting 1-click upvotes.
- **MCDA Priority Triage:** Calculates a 0–100 Multi-Criteria Decision Analysis priority score weighted by proximity to sensitive water bodies and healthcare facilities.
- **DBSCAN Spatial Hotspot Detection:** Density-based spatial clustering on pairwise Haversine coordinates reveals chronic recurring dumping zones with ranked Top 10 Hotspots.
- **Municipal 2-Opt TSP Route Optimizer:** Computes the optimal pickup tour for cleanup trucks, reporting the distance and CO₂ saved versus visiting stops in priority order (computed live).
- **Before/After Verification:** Mandatory photographic proof with an interactive comparison slider before complaints can be marked as "Cleared".
- **Interactive Pitch Deck:** An integrated 6-slide presentation deck built directly into the app for hackathon judges!

---

## 🚀 Key Features

| Feature | Description | GeoAI Angle |
|---|---|---|
| **📸 AI Waste Vision Classification** | Auto-detects waste category, confidence %, recyclable flag, estimated volume ($m^3$) and weight (kg) from uploaded photos | Computer Vision / Multi-feature inference |
| **📍 Auto GPS & Pinpoint Picker** | Captures browser geolocation with fallback to an interactive Leaflet pinpoint map picker | Spatial Geolocation & Geofencing |
| **⚠️ Duplicate Detection** | Proximity check within 40m of existing open dumps; prompts citizen to upvote existing report | Spatial Buffer & Haversine Distance |
| **🔥 Hotspot Heatmap & DBSCAN** | Density-based clustering on coordinates ($\epsilon=250\text{m}$, $\text{minPts}=3$); ranks Top 10 hotspots | Unsupervised Machine Learning & Spatial Density |
| **🚨 MCDA Priority Scoring** | Scores reports 0–100 combining AI severity, citizen upvotes, days open, and proximity to lakes & hospitals | Multi-Criteria Decision Analysis & Spatial Buffering |
| **🏛️ BBMP Ward Analytics** | GeoJSON ward boundaries with live Cleanliness Index (0–100), clearance rate %, and letter grades (A to D) | Choropleth Mapping & Spatial Aggregation |
| **🚛 2-Opt TSP Route Optimizer** | Solves Traveling Salesperson pickup tours from municipal depots to high-priority dumps | Combinatorial Optimization & Graph Routing |
| **🔄 Before / After Proof Slider** | Interactive comparison slider comparing dump photo with cleanup crew's after photo | Photographic Audit & Verification |
| **📶 Offline PWA Sync** | Saves reports to LocalStorage queue when offline and auto-syncs upon reconnection | Resilient Citizen Offline Support |
| **🎙️ Hackathon Pitch Deck** | Built-in 6-slide presentation deck matching hackathon criteria | Pitch & Demonstration Ready |

---

## 🛠️ System Architecture

```
[ Citizen Smartphone / Web App ]
         │
         ├── 1. Photo Capture + Auto GPS Location
         ├── 2. Spatial Deduplication Check (40m Buffer)
         ▼
[ Flask GeoAI Backend Engine ]
         ├── AI Waste Vision Inference (Gemini Vision API with offline keyword fallback)
         ├── MCDA Priority Scorer (Proximity to Lakes & Hospitals)
         ├── DBSCAN Hotspot Clustering Engine (NumPy Haversine Matrix)
         └── 2-Opt TSP Route Optimizer (Municipal Fleet Logistics)
         ▼
[ SQLite / PostGIS Spatial Database ]
         ├── Reports Table (55 Seeded Bengaluru Incidents)
         ├── Upvotes Table (One-Vote Guard)
         └── Immutable Audit Trail Table
         ▼
[ Municipal Command Center & Live Map ]
         ├── Leaflet.js Base Map (CartoDB Positron / OSM)
         ├── Dynamic Heatmap Layer (Leaflet.heat)
         ├── BBMP GeoJSON Ward Choropleth Layer
         ├── Before/After Photo Verification Slider
         └── Turn-by-Turn Truck Itinerary with Animated Paths
```

---

## 💻 Tech Stack

- **Frontend:** HTML5, Modern ES6 Modules, Tailwind CSS, Leaflet 1.9, Leaflet.heat, Chart.js
- **Backend:** Python 3.10+, Flask 3.1, Jinja2
- **Data & Geospatial Math:** NumPy (Pairwise distance matrix & DBSCAN algorithm), SQLite3
- **Spatial Boundaries:** BBMP (Bruhat Bengaluru Mahanagara Palike) Ward Boundaries GeoJSON
- **Pre-seeded Dataset:** 55 realistic, richly detailed dumping incidents across 10 Bengaluru wards

---

## 🌐 Cloud Deployment Guide (Stage 2 Phase 1)

This project is pre-configured with `Procfile`, `render.yaml`, and `Dockerfile` for seamless 1-click cloud deployment.

### Option A: Deploy on Render (Recommended - Free & Fast)
1. Fork or push this repository to your GitHub account (`https://github.com/<your-username>/geo-waste-reporter`).
2. Log in to [Render](https://render.com) and click **New +** &rarr; **Web Service**.
3. Select your `geo-waste-reporter` repository.
4. Render will automatically detect the settings:
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
5. Click **Create Web Service**. Your live public application will be available at:
   `https://<your-service-name>.onrender.com`

### Option B: Deploy on Railway
1. Go to [Railway](https://railway.app) and click **New Project** &rarr; **Deploy from GitHub repo**.
2. Select `geo-waste-reporter`. Railway detects the `Dockerfile` or `Procfile` and deploys automatically.
3. In **Settings** &rarr; **Networking**, click **Generate Domain** to get a public HTTPS link.

### Option C: Instant Local Tunnel (For Immediate Evaluation)
If running locally and you need an instant public URL:
```bash
# Terminal 1: Start application
python app.py

# Terminal 2: Expose via localtunnel or cloudflared
npx localtunnel --port 5000
```

---

## ⚡ Quickstart Guide

### 1. Requirements
- Python 3.10 or higher
- Standard web browser (Chrome, Edge, Firefox, Safari)

### 2. Run the Application (Windows)
Double-click `run.bat` or run in PowerShell:
```powershell
cd geo-waste-reporter
python app.py   # prints a one-off admin token for the Admin tab
```

### 3. Run the Application (Linux / macOS)
```bash
cd geo-waste-reporter
python3 app.py
```

### 4. Access the Web Application
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 📡 REST API Documentation

### Reports
- `GET /api/reports`: List all reports with query filters (`status`, `category`, `ward`, `priority`, `search`).
- `GET /api/reports/<id>`: Get single report details with complete audit trail.
- `POST /api/reports`: Create a new report (multipart form or JSON). Automatically runs AI classification, checks duplicates, and calculates priority score.
- `POST /api/reports/<id>/status`: Update report status (`Reported` &rarr; `In Progress` &rarr; `Cleared`) with optional `after_photo` proof upload.
- `POST /api/reports/<id>/upvote`: Upvote a report (recalculates priority score and verifies citizen engagement).

### GeoAI Intelligence
- `POST /api/check-duplicate`: Checks whether coordinates `(lat, lon)` fall within 40m of an open dump.
- `POST /api/ai-classify`: Direct image classification endpoint returning category, confidence, volume, materials, and risks.
- `GET /api/hotspots`: Runs DBSCAN spatial clustering; returns ranked Top 10 hotspots, cluster centroids, radii, and heatmap coordinate array.
- `GET /api/wards`: Returns Bengaluru GeoJSON ward boundaries enriched with real-time cleanliness indices, clearance rates, and letter grades.
- `GET /api/route-optimizer`: Computes optimal 2-Opt TSP pickup route starting from municipal depot across open reports.
- `GET /api/analytics`: Aggregated metrics for Chart.js dashboards (14-day trendline, category doughnut, priority breakdown).

### Data Management & Export
- `POST /api/seed`: Reset and reseed SQLite database with 55 realistic Bengaluru dumping reports.
- `GET /api/export/geojson`: Export all reports as a standard GeoJSON FeatureCollection.
- `GET /api/export/csv`: Export all reports as a CSV audit table.

---

## 🧮 Mathematical Formulations

### 1. Pairwise Haversine Distance
$$d = 2 R \arcsin \sqrt{ \sin^2\left(\frac{\Delta\phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta\lambda}{2}\right) }$$
Where $R = 6,371,000\text{ m}$.

### 2. Multi-Criteria Priority Score (MCDA)
$$\text{Priority Score} = \min\left(100, \, S_{\text{base}} + P_{\text{receptor}} + U_{\text{citizen}} + A_{\text{aging}}\right)$$
- $S_{\text{base}} = \text{Severity} \times 10 \quad [10\text{--}50]$
- $P_{\text{receptor}} = \begin{cases} 30 & d < 150\text{ m} \\ 20 & d < 350\text{ m} \\ 10 & d < 700\text{ m} \\ 0 & \text{otherwise} \end{cases}$
- $U_{\text{citizen}} = \min(15, \, \text{Upvotes} \times 3)$
- $A_{\text{aging}} = \min(10, \, \text{Days Open} \times 2)$

### 3. DBSCAN Hotspot Severity Index
$$\text{Dumping Index} = N_{\text{cluster}} \times \overline{\text{Severity}} \times \left(1 + \frac{\text{Open Reports}}{\max(1, N_{\text{cluster}})}\right)$$

---

## 🏙️ Seeded Bengaluru Wards & Hotspots

1. **Ward 150: Bellandur Lake Catchment** &mdash; 8 reports (Hotspot #1: Plastic & C&D debris blocking feeder canal; 92/100 Critical)
2. **Ward 84: Peenya Industrial Area** &mdash; 6 reports (Hotspot #2: E-waste & chemical drum discarding)
3. **Ward 93: Shivajinagar & Russell Market** &mdash; 6 reports (Hotspot #3: Decomposing market organic produce)
4. **Ward 151: Koramangala (80ft Road)** &mdash; 6 reports (Hotspot #4: Commercial food containers & plastic refuse)
5. **Ward 85: Whitefield (ITPL / ECC Road)** &mdash; 6 reports (Hotspot #5: Concrete slabs & construction demolition rubble)
6. **Ward 112: Domlur & Indiranagar** &mdash; 5 reports
7. **Ward 174: HSR Layout** &mdash; 5 reports
8. **Ward 45: Malleshwaram** &mdash; 4 reports
9. **Ward 168: Jayanagar** &mdash; 5 reports
10. **Ward 20: Hebbal & Kempapura** &mdash; 4 reports

---

## 🎙️ Presentation Ready

To present to hackathon judges:
1. Start the app via `python app.py`.
2. Open `http://127.0.0.1:5000` in your browser.
3. Click the **"🎙️ Pitch Deck"** tab in the top navigation bar.
4. Use the `Next →` and `← Prev` buttons or keyboard arrow keys to navigate the 6 slides.
5. Jump to the **"Live Map & Hotspots"** or **"Route Optimizer"** tab anytime for interactive live demonstrations!


---

## 🔐 Configuration, Security & Known Limits

| Environment variable | Purpose |
| --- | --- |
| `ADMIN_TOKEN` | **Required in production.** Secret for admin actions (changing report status, reseeding). Without it those endpoints return 503. `python app.py` generates a random one and prints it. |
| `GEMINI_API_KEY` | Optional. Enables real image classification, read **server-side only**. `GEMINI_MODEL` overrides the default model. |
| `FLASK_DEBUG` | `1` enables debug mode. Local development only. |
| `TRUST_PROXY` | `1` when behind a proxy such as Render, so voter IPs are read correctly (set automatically on Vercel). |
| `DATA_DIR` | Optional folder for the SQLite DB and uploaded photos. Defaults to the project folder, or `/tmp` on Vercel. |
| `CORS_ORIGINS` | Optional allow-list of cross-origin callers (default: same-origin only). |

**About the "AI":** with a Gemini key the photo is analysed by the model. Without one, the app uses a
*keyword heuristic* over the description/filename. It does **not** look at the image, reports low confidence and is
labelled as a demo fallback in the UI. Volume/weight in fallback mode are per-category averages, not measurements.
The 55 seeded reports are illustrative demo data.

**Other limits:** ward polygons are 10 simplified demo rectangles (not official boundaries); upvotes are limited per
IP + browser, which is a deterrent rather than strong identity; SQLite and uploaded photos live on local disk, which is
**ephemeral on Render's free plan** (use Postgres + object storage for real deployments); offline-queued reports sync
automatically when back online but cannot include photos.

**Deploying on Vercel:** the project folder is read-only and `/tmp` is wiped on every cold start, so the SQLite database
and uploaded photos are **temporary** there: the 55 demo reports are re-created on each cold start and new reports/photos
can disappear, or differ between server instances. That is fine for a demo; for real use switch to a hosted database
(e.g. Neon/Supabase Postgres or Turso) and object storage. Set `ADMIN_TOKEN` in Project Settings -> Environment Variables.

## Sensitive-receptor data (schools, hospitals, lakes)

Priority scoring rewards waste near lakes, hospitals and schools, and adds an *urgency boost* when the kind of
waste matches the kind of place (e.g. hazardous/medical waste near a school; organic waste beside a lake).
Hazardous/medical waste within 150 m of a school or hospital is escalated to **Critical**.

The app ships with a small built-in sample (16 places). For full coverage run once, with internet:

    python fetch_receptors.py

This downloads real schools/colleges, hospitals and named lakes for Bengaluru from OpenStreetMap into
`static/data/receptors.json`, which the app loads automatically at startup (commit the file to deploy it).
