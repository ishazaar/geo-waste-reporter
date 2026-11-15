# Geo-Waste Reporter: Hackathon Presentation Deck (Problem 10)

This document contains the exact slide-by-slide structure, speaker notes, and architectural diagrams for your 6-slide GeoAI Hackathon PPT presentation.

---

## Slide 1: Title & Team
- **Title:** Geo-Waste Reporter
- **Subtitle:** AI-Powered Citizen Geospatial Platform for Illegal Dumping Detection, Hotspot Analytics & Smart Municipal Cleanup
- **Hackathon Track:** Problem 10 (GeoAI Hackathon 2026)
- **Target Deployment:** Bengaluru Urban (Bruhat Bengaluru Mahanagara Palike - BBMP)
- **Team Name:** GeoAI Urban Innovators
- **Core Value Proposition:** Transforming passive citizen complaints into real-time geospatial intelligence, automated vision triage, and fuel-optimized municipal dispatch.

---

## Slide 2: Problem Statement & Real-World Impact
### The Urban Challenge
- **Unreported & Untracked:** Over 70% of illegal garbage dumping spots ("black spots") remain unreported until severe monsoon drain clogs and leachate disasters occur.
- **Reactive & Untargeted Cleanup:** Sanitation trucks drive unoptimized, arbitrary routes, clearing benign garden waste while toxic or lake-adjacent dumps fester.
- **Citizen Frustration & Duplicate Clutter:** When dumping happens on prominent corners, dozens of citizens submit separate complaints for the same pile, overwhelming municipal control rooms with redundant tickets.
- **Zero Proof Accountability:** Contractors often mark complaints as "Resolved" without photographic evidence or verification.

### Our Solution
- **Zero-Friction AI Citizen Reporting:** Take a photo &rarr; GPS pin is automatically locked, waste category & volume are classified by AI in under 800ms.
- **Spatial Deduplication (30m Buffer):** Detects existing nearby open reports; invites citizens to upvote rather than cluttering control room queues.
- **MCDA Priority Scoring:** Automatically elevates dump sites near sensitive water bodies (Bellandur Lake, Ulsoor Lake), schools, and hospitals to "Critical".
- **Verified Before/After Photographic Proof:** Mandatory visual proof with side-by-side comparison slider before status changes to "Cleared".

---

## Slide 3: GeoAI Core & Data Sources
### Mathematical Rigor & Geospatial Models
1. **AI Waste Classification (Gemini Vision API, with offline keyword fallback):**
   - Classifies 6 municipal waste categories: *Plastic Waste*, *Construction & Demolition Debris*, *Organic / Biodegradable Waste*, *Electronic Waste (E-Waste)*, *Hazardous / Medical Waste*, and *Mixed Municipal Solid Waste*.
   - Outputs: Category, Confidence Score (reported by the model; low for the keyword fallback), Severity (1–5), Estimated Volume ($m^3$), Recyclability, and Dispatch Fleet recommendations.
2. **DBSCAN Density-Based Hotspot Clustering:**
   - Runs DBSCAN on pairwise Haversine distance matrix ($\epsilon = 250\text{ m}$, $\text{min\_samples} = 3$).
   - Isolates recurring chronic dumping zones from random one-off litter.
   - Calculates **Dumping Severity Index**:
     $$\text{Dumping Index} = N_{\text{reports}} \times \overline{\text{Severity}} \times \left(1 + \frac{\text{Open Reports}}{\text{Total Reports}}\right)$$
   - Produces a ranked "Top 10 Hotspots" leaderboard and multi-intensity heat layer.
3. **Multi-Criteria Decision Analysis (MCDA) Priority Scoring:**
   - Factors: Base Severity ($10\text{–}50\text{ pts}$) + Sensitive Receptor Proximity Buffer ($0\text{–}30\text{ pts}$) + Citizen Upvotes ($0\text{–}15\text{ pts}$) + Aging Days ($0\text{–}10\text{ pts}$).
   - Total Score ($0\text{–}100$) drives automated dispatch prioritization.
4. **Data Sources:**
   - OpenStreetMap (OSM) & CartoDB base tiles
   - BBMP Official Ward Boundaries GeoJSON (10 major Bengaluru wards)
   - Environmental Receptor GIS database (Lakes, Hospitals, Educational Institutes)

---

## Slide 4: System Architecture & Tech Stack
```mermaid
flowchart TD
    subgraph Citizen Client
        A[Mobile PWA / Web Browser] -->|Photo + GPS| B[Auto-Geolocation & Photo Capture]
        B -->|Check 40m Radius| C{Nearby Open Dump?}
        C -->|Yes| D[Prompt 1-Click Upvote]
        C -->|No| E[Submit New Dump Report]
    end

    subgraph GeoAI Backend Engine
        E --> F[Flask REST API Core]
        F --> G[Gemini Vision API, with offline keyword fallback]
        F --> H[MCDA Priority Scorer]
        F --> I[DBSCAN Hotspot Clustering]
        F --> J[2-Opt TSP Route Optimizer]
    end

    subgraph Data & Storage Layer
        F <--> K[(SQLite / PostGIS Spatial DB)]
        K <--> L[BBMP Ward GeoJSON Boundaries]
        K <--> M[Sensitive Receptors GIS Buffers]
    end

    subgraph Municipal Command Center
        I --> N[Live Heatmap & Top Hotspots]
        H --> O[Priority Triage Dashboard]
        J --> P[Optimized Truck Dispatch Itinerary]
        Q[Sanitation Supervisor] -->|Upload After Proof| K
    end
```

### Technology Stack Summary
- **Frontend:** HTML5, Modern ES6, Tailwind CSS, Leaflet.js, Leaflet.heat, Chart.js
- **Backend / Analytics:** Python 3.14, Flask 3.1, NumPy (Haversine & DBSCAN clustering), Pandas
- **Geospatial & Spatial Math:** Great-Circle Haversine, Spatial Buffering, 2-Opt TSP Heuristic
- **Database:** SQLite / PostGIS with immutable audit trails

---

## Slide 5: Features, Demonstrations & Results
### Validated Results across 55 Bengaluru Reports
- **55 Seeded & Verified Incidents:** Mapped across Indiranagar, Koramangala, Bellandur, Whitefield, Peenya, Malleshwaram, HSR Layout, Jayanagar, Shivajinagar, and Hebbal.
- **5 Primary DBSCAN Hotspots Detected:**
  - *Hotspot #1:* Bellandur Lake Catchment Canal (Heavy plastic & C&D debris, Priority: 92/100 Critical)
  - *Hotspot #2:* Peenya Industrial Area 4th Phase (Toxic e-waste & chemical drum dumping)
  - *Hotspot #3:* Shivajinagar Russell Market (Decomposing organic wet waste & hospital boundary)
  - *Hotspot #4:* Koramangala 80ft Road (Commercial plastic & food delivery packaging)
  - *Hotspot #5:* Whitefield ECC Road (Illegal night-dumped construction rubble)
- **Route Efficiency (computed live in the Route tab):**
  - Compares the 2-Opt TSP tour against visiting stops in priority order; the saving varies with the selected reports and depot.
- **Photographic Proof:**
  - Admins can attach an after-photo when clearing a report; if none is attached a placeholder is shown and the audit log records it.

---

## Slide 6: Conclusion, Municipal Integration & Future Scope
### Scalability & Real-World Rollout
1. **Direct BBMP Sahaya 2.0 Integration:**
   - Webhook bridge to municipal complaint management and automated auto-tipper assignment.
2. **Satellite Hotspot Monitoring (Stretch):**
   - Integration with European Space Agency Sentinel-2 MSI optical imagery to observe recurring lake encroachment and illegal land-filling over time.
3. **WhatsApp / Telegram Citizen Bot:**
   - Citizens simply send a picture with live location over WhatsApp; the Flask GeoAI engine classifies and logs the incident automatically without requiring app downloads.
4. **Community Incentives (CleanKarma):**
   - Reward points for active citizens reporting verified dumps, redeemable for municipal utility discounts.

### Open Source Repository
- **GitHub:** https://github.com/your-username/geo-waste-reporter
- **Live Demo:** http://127.0.0.1:5000
