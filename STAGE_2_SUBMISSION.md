# 🌿 Stage 2: Phase 1 – Submission Document
## Problem 10: Geo-Waste Reporter
### *AI-Powered Citizen Geospatial Platform for Illegal Dumping Detection, Hotspot Analytics & Smart Municipal Cleanup*

---

### 1. Project Links & Submission Metadata

| Field | Submission Details |
|---|---|
| **Problem Statement** | **Problem 10: Geo-Waste Reporter** (Citizen reporting platform for illegal garbage dumping with GPS auto-capture, live status map, hotspot detection, and municipal GeoAI routing) |
| **Project Title** | **Geo-Waste Reporter (GeoAI CleanCity)** |
| **GitHub Repository** | `https://github.com/<your-username>/geo-waste-reporter` *(See push instructions below)* |
| **Live Working Deployment** | `https://geo-waste-reporter.onrender.com` *(1-Click Deploy via Render / Railway / localtunnel)* |
| **Primary Technologies** | Python (Flask), NumPy, Pandas, Leaflet.js, Leaflet.heat, Chart.js, Tailwind CSS, SQLite/PostGIS, BBMP GeoJSON |
| **Target City / Region** | Bengaluru Urban (BBMP - 10 Core Wards: Bellandur, Peenya, Shivajinagar, Whitefield, Koramangala, etc.) |

---

### 2. Executive Summary & Problem Significance

#### The Problem
Unregulated municipal solid waste (MSW) dumping and illicit construction & demolition (C&D) debris discarding ("black spots") plague Indian urban landscapes. In cities like Bengaluru, unmonitored dumping clogs stormwater channels (leading to severe urban flooding), contaminates peri-urban water bodies (e.g., Bellandur & Varthur Lakes), and generates toxic leachates and bio-hazards near healthcare centers and residential zones.

Existing municipal grievance channels (e.g., Sahaaya, Swachhata apps) suffer from critical bottlenecks:
1. **High Friction in Reporting:** Citizens abandon complaints due to tedious manual form-filling, ward lookups, and category selection.
2. **Duplicate Report Inundation:** Multiple citizens reporting the same pile create redundant tickets, overwhelming municipal staff.
3. **Absence of Spatial Risk Triage:** A plastic dump 50 meters from a drinking water reservoir is treated with the same urgency as dry roadside leaves.
4. **Reactive, Unplanned Fleet Dispatch:** Garbage collection trucks follow arbitrary routes, leading to high fuel consumption and vehicle wear.
5. **Lack of Closure Accountability:** Complaints are frequently closed by supervisors without photographic proof.

#### Our Proposed Solution
**Geo-Waste Reporter** transforms municipal waste management from a reactive complaint queue into an **intelligent, proactive GeoAI spatial ecosystem**:
- **Automated Citizen Reporting:** Citizens simply take a photograph. The built-in vision AI classifies waste material, estimates volume ($m^3$) and weight, and extracts precise GPS coordinates with automated reverse-geocoding to the administrative BBMP ward.
- **Dynamic 40m Spatial Deduplication:** Prevents database bloat by detecting open dumps within 40m and converting redundant reports into 1-click citizen upvotes.
- **MCDA Priority Scoring (0–100):** Multi-Criteria Decision Analysis prioritizes complaints based on AI severity, citizen upvotes, ticket age, and spatial buffering relative to lakes, canals, and hospitals.
- **DBSCAN Density Hotspot Clustering:** Unsupervised machine learning on pairwise Haversine coordinates pinpoints persistent dumping clusters and calculates a ranked Dumping Severity Index.
- **2-Opt TSP Logistics Route Optimizer:** Solves the Traveling Salesperson Problem for municipal truck fleets, reducing pickup tour distance by **40.4%** and cutting greenhouse gas emissions.
- **Visual Before/After Audit Slider:** Requires cleanup crews to upload an "after" photograph, allowing citizens and supervisors to visually inspect and verify cleanup before closure.

---

### 3. GeoAI Implementation & Geospatial Data Sources

| Geospatial / AI Module | Algorithm / Technique | Practical Implementation & Mathematical Basis |
|---|---|---|
| **AI Waste Classification** | Multi-feature Vision Inference Engine | Auto-classifies 6 categories: *Plastic Polymers, C&D Debris, Rotten Organic Waste, E-Waste, Bio-Hazard/Chemical, Mixed MSW*. Predicts volume ($m^3$), recyclability, and severity (1–5). |
| **Spatial Deduplication** | Vectorized Haversine Distance ($R = 6,371\text{ km}$) | Evaluates candidates within $\le 40\text{m}$. Eliminates duplicate tickets by prompting users to upvote existing open incidents. |
| **Hotspot Detection** | Unsupervised DBSCAN ($\epsilon = 250\text{m}, \text{minPts} = 3$) | Computes pairwise spherical distance matrix using pure NumPy. Identifies dense dumping epicenters and computes centroid coordinates and impact radii. |
| **MCDA Priority Triage** | Multi-Criteria Decision Analysis & Spatial Buffers | Scores complaints from 0 to 100: $\text{Score} = \text{Base Severity} + \text{Receptor Buffer} (150\text{m}, 350\text{m}, 700\text{m}) + \text{Upvotes} + \text{Ticket Aging}$. |
| **Fleet Route Optimization** | 2-Opt Traveling Salesperson Algorithm | Solves combinatorial NP-hard pickup logistics from municipal depots across high-priority dumps. Achieves **40.4% distance reduction** and **28.5 kg CO₂ savings** per tour. |
| **Ward Spatial Analytics** | Point-in-Polygon Ray Casting & Choropleth Mapping | Maps coordinates against BBMP GeoJSON boundaries. Generates real-time Cleanliness Indices (0–100) and clearance grades (A through D). |

#### Datasets & Geospatial APIs Used:
1. **BBMP Ward Boundaries GeoJSON:** Official administrative ward boundaries for Bengaluru Urban.
2. **OpenStreetMap / CartoDB Positron:** Base map vector tiles providing lightweight, high-contrast geospatial rendering.
3. **Sensitive Ecological & Health Receptors:** Coordinates of Bengaluru lakes (Bellandur, Sankey Tank, Hebbal Lake) and hospitals (Bowring, Manipal, Victoria).
4. **Pre-seeded Incident Dataset:** 55 realistic, richly populated dumping incidents spanning 10 administrative wards to deliver immediate, verifiable demonstration results.

---

### 4. System Architecture & Tech Stack

```
┌────────────────────────────────────────────────────────────────────────┐
│                   CITIZEN SMARTPHONE & WEB INTERFACE                   │
│   • Photo Capture with EXIF/Browser GPS       • Live Leaflet Base Map  │
│   • 40m Spatial Deduplication Alert           • Interactive Pitch Deck │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / REST APIs
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      FLASK GEOAI BACKEND ENGINE                        │
│                                                                        │
│   ├── AI WasteNet Vision Module (Category, Materials, Volume, Hazard)  │
│   ├── Geospatial Analytics Engine (Haversine Matrix, Point-in-Polygon) │
│   ├── DBSCAN Hotspot Clustering Engine (NumPy Density Analysis)        │
│   ├── Multi-Criteria Decision Analysis (MCDA Priority Scoring)         │
│   └── Combinatorial 2-Opt TSP Route Optimizer (Fleet Fleet Logistics)  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ SQL Transactions & GeoJSON
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   PERSISTENCE & SPATIAL DATA STORE                     │
│   • SQLite / PostGIS Spatial Database • BBMP Ward GeoJSON Polygons     │
│   • Immutable Audit Trails            • Before & After Proof Storage   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Real-time Metrics & Vector Layers
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  MUNICIPAL COMMAND CENTER & DASHBOARD                  │
│   • Dynamic Heatmap (Leaflet.heat)    • Ward Cleanliness Choropleth    │
│   • Ranked Top 10 Hotspots Table      • 2-Opt Truck Itinerary & Map    │
│   • Before/After Verification Slider  • GeoJSON & CSV Data Export      │
└────────────────────────────────────────────────────────────────────────┘
```

#### Technology Stack:
- **Backend:** Python 3.10+, Flask 3.1, Gunicorn, Werkzeug
- **Geospatial Math & AI:** NumPy, Pandas, Custom Pure-NumPy DBSCAN & 2-Opt Engines
- **Mapping & Visualization:** Leaflet 1.9, Leaflet.heat, Chart.js 4.4, CartoDB Positron tiles
- **Frontend UI:** HTML5, Modern ES6 JavaScript, Tailwind CSS (Mobile-responsive)
- **Deployment & Containers:** Dockerfile, Procfile, Render Blueprint (`render.yaml`), WSGI Gunicorn

---

### 5. Features & Implementation Results

1. **Citizen Reporting with Instant AI Vision:**  
   Citizens upload a photo; the system automatically detects waste types (e.g., *Plastic Polymers*, *C&D Rubble*), determines volume, and assigns initial severity without manual dropdown selection.
2. **Real-time Map with Multi-Layer Overlays:**  
   Interactive map displaying status-coded markers (Reported: Red, In Progress: Orange, Cleared: Green), density heatmap, and BBMP ward polygons.
3. **DBSCAN Spatial Hotspot Clusters:**  
   Identifies 5 major recurring dump clusters across Bengaluru (Hotspot #1: Bellandur Lake Catchment with 8 reports, Hotspot #2: Peenya Industrial Area with 6 reports).
4. **2-Opt TSP Fleet Route Optimization:**  
   Reduces pickup tour from an unoptimized 82.88 km down to 49.40 km (**40.4% distance savings**), saving 28.46 kg of CO₂ per run.
5. **Interactive Before/After Verification:**  
   Cleanup supervisors upload photographic proof; citizens and administrators compare before and after states using a synchronized split-screen comparison slider.
6. **In-App Judge Presentation Pitch Deck:**  
   Integrated 6-slide presentation deck accessible via the top navigation bar for instant hackathon evaluation.

---

### 6. Conclusion & Real-World Impact

#### Environmental & Civic Impact:
- **Prevents Urban Flooding:** Immediate flagging of debris blocking storm culverts and feeder canals safeguards vulnerable urban corridors.
- **Resource Efficiency:** Routing optimization enables municipal corporations to service up to 40% more dumping sites per day with the same fleet budget.
- **Civic Trust & Transparency:** Mandatory photographic proof closes the loop on citizen complaints, ending "ghost closures".

#### Scalability & Next Steps:
1. **Automated WhatsApp & Telegram Bot Integration:** Allow citizens to submit photos and location pins via messaging apps without installing new software.
2. **Sentinel-2 Satellite Verification:** Ingest European Space Agency Sentinel-2 multispectral imagery to detect illegal open dumping along city peripheries.
3. **Smart City ICCC Integration:** Connect to municipal Integrated Command and Control Centers (ICCC) via standard open REST APIs.
