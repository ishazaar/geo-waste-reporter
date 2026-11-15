"""
Seed Dataset Generator for Geo-Waste Reporter
Generates 55 realistic dumping reports across Bengaluru with:
- Exact coordinates mapped to 10 prominent BBMP wards
- Specific clustering to demonstrate DBSCAN hotspot detection
- Varied waste categories and severity levels
- Proximity calculations to lakes and hospitals
- Before & After proof imagery
- Authentic timestamps spanning the past 14 days
"""

import os
import json
import random
from datetime import datetime, timedelta, timezone
from database import init_db, reset_db, create_report, get_connection
from geo_analytics import calculate_priority_score, find_closest_receptor

# High-quality SVG visual illustrations for waste categories & clean proof
SVG_TEMPLATES = {
    "Plastic Waste": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='260' viewBox='0 0 400 260'><rect width='400' height='260' fill='%23e0f2fe'/><rect y='180' width='400' height='80' fill='%2364748b'/><circle cx='120' cy='160' r='35' fill='%230284c7' opacity='0.8'/><rect x='150' y='140' width='30' height='60' rx='5' fill='%2338bdf8'/><path d='M80 180 Q100 130 130 170 T180 190' stroke='%230369a1' stroke-width='8' fill='none'/><rect x='220' y='150' width='45' height='50' rx='4' fill='%23bae6fd'/><circle cx='290' cy='175' r='25' fill='%230ea5e9' opacity='0.7'/><text x='20' y='40' font-family='sans-serif' font-weight='bold' font-size='18' fill='%230369a1'>ILLEGAL PLASTIC DUMP</text><text x='20' y='65' font-family='sans-serif' font-size='13' fill='%230284c7'>AI: 95% PET &amp; LDPE Polymers</text></svg>",
    
    "Construction & Demolition Debris": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='260' viewBox='0 0 400 260'><rect width='400' height='260' fill='%23fef3c7'/><rect y='170' width='400' height='90' fill='%2378716c'/><polygon points='70,200 130,120 190,200' fill='%23b45309'/><polygon points='160,210 220,135 280,210' fill='%239a3412'/><polygon points='250,200 290,150 330,200' fill='%2378350f'/><rect x='110' y='170' width='40' height='25' fill='%23ea580c'/><text x='20' y='40' font-family='sans-serif' font-weight='bold' font-size='18' fill='%239a3412'>C&amp;D DEBRIS ACCUMULATION</text><text x='20' y='65' font-family='sans-serif' font-size='13' fill='%23b45309'>AI: Concrete, Bricks &amp; Mortar Rubble</text></svg>",
    
    "Organic / Biodegradable Waste": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='260' viewBox='0 0 400 260'><rect width='400' height='260' fill='%23ecfdf5'/><rect y='180' width='400' height='80' fill='%23475569'/><path d='M60 210 Q120 120 180 210' fill='%2315803d'/><path d='M150 210 Q210 140 270 210' fill='%23166534'/><circle cx='140' cy='180' r='18' fill='%23eab308'/><circle cx='200' cy='185' r='15' fill='%23ef4444'/><text x='20' y='40' font-family='sans-serif' font-weight='bold' font-size='18' fill='%23166534'>ROTTING ORGANIC &amp; MARKET WASTE</text><text x='20' y='65' font-family='sans-serif' font-size='13' fill='%2315803d'>AI: Food &amp; Wet Waste / Leachate Risk</text></svg>",
    
    "Electronic Waste (E-Waste)": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='260' viewBox='0 0 400 260'><rect width='400' height='260' fill='%23f1f5f9'/><rect y='180' width='400' height='80' fill='%23334155'/><rect x='80' y='120' width='70' height='60' rx='4' fill='%230f172a'/><rect x='85' y='125' width='60' height='45' fill='%2338bdf8' opacity='0.3'/><rect x='180' y='140' width='65' height='45' fill='%23047857'/><circle cx='210' cy='160' r='10' fill='%23fbbf24'/><line x1='120' y1='180' x2='200' y2='200' stroke='%23dc2626' stroke-width='4'/><text x='20' y='40' font-family='sans-serif' font-weight='bold' font-size='18' fill='%230f172a'>HAZARDOUS E-WASTE DISCARD</text><text x='20' y='65' font-family='sans-serif' font-size='13' fill='%23475569'>AI: High Heavy Metal Toxicity (Lead/Cadmium)</text></svg>",
    
    "Hazardous / Medical Waste": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='260' viewBox='0 0 400 260'><rect width='400' height='260' fill='%23fee2e2'/><rect y='180' width='400' height='80' fill='%231f2937'/><rect x='100' y='130' width='40' height='60' rx='6' fill='%23dc2626'/><polygon points='120,105 130,125 110,125' fill='%23facc15'/><line x1='180' y1='140' x2='220' y2='190' stroke='%23ef4444' stroke-width='6'/><circle cx='250' cy='165' r='16' fill='%23b91c1c'/><text x='20' y='40' font-family='sans-serif' font-weight='bold' font-size='18' fill='%23991b1b'>BIO-HAZARD / CHEMICAL DRUMS</text><text x='20' y='65' font-family='sans-serif' font-size='13' fill='%23dc2626'>AI: CRITICAL PRIORITY - Contamination Risk</text></svg>",
    
    "Mixed Municipal Solid Waste": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='260' viewBox='0 0 400 260'><rect width='400' height='260' fill='%23ffedd5'/><rect y='180' width='400' height='80' fill='%2357534e'/><path d='M70 200 Q140 100 210 200' fill='%2378350f'/><path d='M160 205 Q220 120 300 205' fill='%23a16207'/><circle cx='110' cy='180' r='14' fill='%2338bdf8'/><polygon points='230,170 250,150 260,180' fill='%23ea580c'/><text x='20' y='40' font-family='sans-serif' font-weight='bold' font-size='18' fill='%2378350f'>OVERFLOWING MUNICIPAL PILE</text><text x='20' y='65' font-family='sans-serif' font-size='13' fill='%23c2410c'>AI: Unsegregated Mixed Refuse</text></svg>",

    "CLEARED_PROOF": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='260' viewBox='0 0 400 260'><rect width='400' height='260' fill='%23f0fdf4'/><rect y='180' width='400' height='80' fill='%23475569'/><line x1='0' y1='180' x2='400' y2='180' stroke='%2322c55e' stroke-width='6'/><circle cx='200' cy='110' r='45' fill='%2322c55e' opacity='0.2'/><path d='M180 110 L195 125 L225 95' stroke='%2316a34a' stroke-width='8' stroke-linecap='round' stroke-linejoin='round' fill='none'/><text x='20' y='40' font-family='sans-serif' font-weight='bold' font-size='18' fill='%23166534'>CLEANED &amp; VERIFIED SITE</text><text x='20' y='65' font-family='sans-serif' font-size='13' fill='%2315803d'>BBMP SWM Crew: 100% Debris Cleared &amp; Disinfected</text></svg>"
}

RAW_SEED_CONFIGS = [
    # --- CLUSTER 1: Bellandur Lake Buffer Road (Major Hotspot: 8 reports) ---
    {"ward_id": "WARD-150", "ward_name": "Bellandur (Catchment)", "lat": 12.9355, "lon": 77.6710, "cat": "Plastic Waste", "sev": 4, "title": "Heavy Plastic Dumping near Lake Feeder Canal", "status": "Reported", "upvotes": 14, "days_ago": 3},
    {"ward_id": "WARD-150", "ward_name": "Bellandur (Catchment)", "lat": 12.9362, "lon": 77.6718, "cat": "Mixed Municipal Solid Waste", "sev": 4, "title": "Overflowing Commercial Trash by Lake Road", "status": "Reported", "upvotes": 9, "days_ago": 4},
    {"ward_id": "WARD-150", "ward_name": "Bellandur (Catchment)", "lat": 12.9348, "lon": 77.6725, "cat": "Plastic Waste", "sev": 3, "title": "Styrofoam & Packaging Bundles in Open Plot", "status": "In Progress", "upvotes": 6, "days_ago": 5},
    {"ward_id": "WARD-150", "ward_name": "Bellandur (Catchment)", "lat": 12.9370, "lon": 77.6732, "cat": "Construction & Demolition Debris", "sev": 5, "title": "Night Demolition Debris Blocking Storm Culvert", "status": "Reported", "upvotes": 19, "days_ago": 2},
    {"ward_id": "WARD-150", "ward_name": "Bellandur (Catchment)", "lat": 12.9358, "lon": 77.6705, "cat": "Plastic Waste", "sev": 4, "title": "Repeated Single-Use Plastic Bags Dump", "status": "Reported", "upvotes": 11, "days_ago": 1},
    {"ward_id": "WARD-150", "ward_name": "Bellandur (Catchment)", "lat": 12.9365, "lon": 77.6722, "cat": "Hazardous / Medical Waste", "sev": 5, "title": "Suspicious Chemical Container Discard", "status": "In Progress", "upvotes": 24, "days_ago": 2},
    {"ward_id": "WARD-150", "ward_name": "Bellandur (Catchment)", "lat": 12.9351, "lon": 77.6715, "cat": "Organic / Biodegradable Waste", "sev": 3, "title": "Vegetable Crate Sweepings Decomposing", "status": "Cleared", "upvotes": 8, "days_ago": 7},
    {"ward_id": "WARD-150", "ward_name": "Bellandur (Catchment)", "lat": 12.9372, "lon": 77.6712, "cat": "Plastic Waste", "sev": 3, "title": "PET Bottles Strewn on Lake Bund", "status": "Cleared", "upvotes": 5, "days_ago": 9},

    # --- CLUSTER 2: Peenya Industrial Area 4th Phase (Industrial / E-Waste Hotspot: 6 reports) ---
    {"ward_id": "WARD-84", "ward_name": "Peenya Industrial Area", "lat": 13.0280, "lon": 13.0280 and 77.5210, "cat": "Electronic Waste (E-Waste)", "sev": 5, "title": "Burned Circuit Boards & Wire Scrap along Storm Drain", "status": "Reported", "upvotes": 16, "days_ago": 2},
    {"ward_id": "WARD-84", "ward_name": "Peenya Industrial Area", "lat": 13.0288, "lon": 77.5218, "cat": "Hazardous / Medical Waste", "sev": 5, "title": "Industrial Solvent Drums Dumped Behind Warehouse", "status": "Reported", "upvotes": 22, "days_ago": 1},
    {"ward_id": "WARD-84", "ward_name": "Peenya Industrial Area", "lat": 13.0275, "lon": 77.5205, "cat": "Electronic Waste (E-Waste)", "sev": 5, "title": "Smashed Monitors & Battery Shells on Roadside", "status": "In Progress", "upvotes": 13, "days_ago": 4},
    {"ward_id": "WARD-84", "ward_name": "Peenya Industrial Area", "lat": 13.0292, "lon": 77.5222, "cat": "Mixed Municipal Solid Waste", "sev": 4, "title": "Factory Canteen Waste Overflowing onto Pavement", "status": "Reported", "upvotes": 7, "days_ago": 3},
    {"ward_id": "WARD-84", "ward_name": "Peenya Industrial Area", "lat": 13.0279, "lon": 77.5228, "cat": "Construction & Demolition Debris", "sev": 4, "title": "Concrete Slabs & Silt Dumped in Open Drain", "status": "Cleared", "upvotes": 10, "days_ago": 8},
    {"ward_id": "WARD-84", "ward_name": "Peenya Industrial Area", "lat": 13.0285, "lon": 77.5201, "cat": "Hazardous / Medical Waste", "sev": 5, "title": "Oil Sludge Drums Leaking onto Ground", "status": "In Progress", "upvotes": 18, "days_ago": 3},

    # --- CLUSTER 3: Shivajinagar Russell Market Area (Organic / Market Waste Hotspot: 6 reports) ---
    {"ward_id": "WARD-93", "ward_name": "Shivajinagar & Commercial St", "lat": 12.9840, "lon": 77.6050, "cat": "Organic / Biodegradable Waste", "sev": 4, "title": "Rotting Market Produce Piles behind Mutton Market", "status": "Reported", "upvotes": 15, "days_ago": 1},
    {"ward_id": "WARD-93", "ward_name": "Shivajinagar & Commercial St", "lat": 12.9846, "lon": 77.6058, "cat": "Organic / Biodegradable Waste", "sev": 4, "title": "Vegetable Crates & Rotten Leaves Spilling onto Road", "status": "Reported", "upvotes": 11, "days_ago": 2},
    {"ward_id": "WARD-93", "ward_name": "Shivajinagar & Commercial St", "lat": 12.9835, "lon": 77.6045, "cat": "Mixed Municipal Solid Waste", "sev": 4, "title": "Black Trash Bags Dumped near Bowring Hospital Wall", "status": "Reported", "upvotes": 21, "days_ago": 1},
    {"ward_id": "WARD-93", "ward_name": "Shivajinagar & Commercial St", "lat": 12.9852, "lon": 77.6062, "cat": "Plastic Waste", "sev": 3, "title": "Plastic Packaging Wrappers around Fruit Stalls", "status": "In Progress", "upvotes": 8, "days_ago": 4},
    {"ward_id": "WARD-93", "ward_name": "Shivajinagar & Commercial St", "lat": 12.9838, "lon": 77.6052, "cat": "Organic / Biodegradable Waste", "sev": 3, "title": "Foul Odor Vegetable Heap Blockading Footpath", "status": "Cleared", "upvotes": 14, "days_ago": 6},
    {"ward_id": "WARD-93", "ward_name": "Shivajinagar & Commercial St", "lat": 12.9848, "lon": 77.6040, "cat": "Mixed Municipal Solid Waste", "sev": 3, "title": "Street Corner Rubbish Bin Overflow", "status": "Cleared", "upvotes": 9, "days_ago": 10},

    # --- CLUSTER 4: Koramangala 80 Feet Road (Commercial & Food Waste Hotspot: 6 reports) ---
    {"ward_id": "WARD-151", "ward_name": "Koramangala", "lat": 12.9340, "lon": 77.6250, "cat": "Mixed Municipal Solid Waste", "sev": 4, "title": "Restaurant Wet Waste Bags Piled on Corner Plot", "status": "Reported", "upvotes": 17, "days_ago": 2},
    {"ward_id": "WARD-151", "ward_name": "Koramangala", "lat": 12.9348, "lon": 77.6258, "cat": "Plastic Waste", "sev": 3, "title": "Swiggy/Zomato Takeaway Containers in Storm Water Drain", "status": "Reported", "upvotes": 12, "days_ago": 3},
    {"ward_id": "WARD-151", "ward_name": "Koramangala", "lat": 12.9335, "lon": 77.6242, "cat": "Organic / Biodegradable Waste", "sev": 3, "title": "Juice Stall Pulp & Coconut Shells Heaped on Footpath", "status": "In Progress", "upvotes": 7, "days_ago": 4},
    {"ward_id": "WARD-151", "ward_name": "Koramangala", "lat": 12.9352, "lon": 77.6265, "cat": "Plastic Waste", "sev": 3, "title": "Plastic Packaging from Retail Stores", "status": "Reported", "upvotes": 5, "days_ago": 1},
    {"ward_id": "WARD-151", "ward_name": "Koramangala", "lat": 12.9338, "lon": 77.6255, "cat": "Mixed Municipal Solid Waste", "sev": 3, "title": "Unsegregated Apartment Waste on Empty Site", "status": "Cleared", "upvotes": 13, "days_ago": 5},
    {"ward_id": "WARD-151", "ward_name": "Koramangala", "lat": 12.9345, "lon": 77.6248, "cat": "Construction & Demolition Debris", "sev": 4, "title": "Remodeling Floor Tiles & Plaster Sacks", "status": "Cleared", "upvotes": 8, "days_ago": 11},

    # --- CLUSTER 5: Whitefield ITPL / ECC Road (Construction Debris Hotspot: 6 reports) ---
    {"ward_id": "WARD-85", "ward_name": "Whitefield & Kadugodi", "lat": 12.9750, "lon": 77.7450, "cat": "Construction & Demolition Debris", "sev": 5, "title": "Massive Truckloads of Excavated Soil & Rocks Dumped", "status": "Reported", "upvotes": 18, "days_ago": 3},
    {"ward_id": "WARD-85", "ward_name": "Whitefield & Kadugodi", "lat": 12.9758, "lon": 77.7458, "cat": "Construction & Demolition Debris", "sev": 4, "title": "Broken Cement Blocks Encroaching Tar Road", "status": "Reported", "upvotes": 14, "days_ago": 4},
    {"ward_id": "WARD-85", "ward_name": "Whitefield & Kadugodi", "lat": 12.9742, "lon": 77.7442, "cat": "Plastic Waste", "sev": 3, "title": "Tarpaulin & Plastic Packing Straps", "status": "In Progress", "upvotes": 6, "days_ago": 5},
    {"ward_id": "WARD-85", "ward_name": "Whitefield & Kadugodi", "lat": 12.9765, "lon": 77.7465, "cat": "Construction & Demolition Debris", "sev": 4, "title": "Red Bricks & Plaster Waste on Vacant Layout", "status": "Reported", "upvotes": 11, "days_ago": 2},
    {"ward_id": "WARD-85", "ward_name": "Whitefield & Kadugodi", "lat": 12.9748, "lon": 77.7455, "cat": "Mixed Municipal Solid Waste", "sev": 3, "title": "Labor Shed Refuse and Packaging Dump", "status": "Cleared", "upvotes": 7, "days_ago": 8},
    {"ward_id": "WARD-85", "ward_name": "Whitefield & Kadugodi", "lat": 12.9755, "lon": 77.7448, "cat": "Construction & Demolition Debris", "sev": 4, "title": "Demolition Rubble Cleared from Metro Line Side", "status": "Cleared", "upvotes": 16, "days_ago": 7},

    # --- INDIRANAGAR (Ward 112: 5 reports) ---
    {"ward_id": "WARD-112", "ward_name": "Domlur & Indiranagar", "lat": 12.9710, "lon": 77.6410, "cat": "Mixed Municipal Solid Waste", "sev": 3, "title": "12th Main Road Black Spot Dump", "status": "Reported", "upvotes": 10, "days_ago": 2},
    {"ward_id": "WARD-112", "ward_name": "Domlur & Indiranagar", "lat": 12.9782, "lon": 77.6435, "cat": "Plastic Waste", "sev": 3, "title": "Discarded Delivery Boxes & Bubble Wrap", "status": "Reported", "upvotes": 8, "days_ago": 3},
    {"ward_id": "WARD-112", "ward_name": "Domlur & Indiranagar", "lat": 12.9660, "lon": 77.6390, "cat": "Organic / Biodegradable Waste", "sev": 3, "title": "Garden Clippings & Fallen Branches Blocking Lane", "status": "In Progress", "upvotes": 4, "days_ago": 4},
    {"ward_id": "WARD-112", "ward_name": "Domlur & Indiranagar", "lat": 12.9735, "lon": 77.6450, "cat": "Electronic Waste (E-Waste)", "sev": 4, "title": "Broken Computer Cabinets near Park", "status": "Reported", "upvotes": 12, "days_ago": 1},
    {"ward_id": "WARD-112", "ward_name": "Domlur & Indiranagar", "lat": 12.9690, "lon": 77.6420, "cat": "Mixed Municipal Solid Waste", "sev": 2, "title": "Cleared Corner near 100ft Flyover", "status": "Cleared", "upvotes": 15, "days_ago": 12},

    # --- HSR LAYOUT (Ward 174: 5 reports) ---
    {"ward_id": "WARD-174", "ward_name": "HSR Layout", "lat": 12.9120, "lon": 77.6420, "cat": "Mixed Municipal Solid Waste", "sev": 4, "title": "Sector 2 Park Boundary Garbage Mound", "status": "Reported", "upvotes": 13, "days_ago": 2},
    {"ward_id": "WARD-174", "ward_name": "HSR Layout", "lat": 12.9150, "lon": 77.6380, "cat": "Construction & Demolition Debris", "sev": 4, "title": "Tiles and Cement Bags Dumped by Builder", "status": "In Progress", "upvotes": 9, "days_ago": 4},
    {"ward_id": "WARD-174", "ward_name": "HSR Layout", "lat": 12.9080, "lon": 77.6450, "cat": "Organic / Biodegradable Waste", "sev": 3, "title": "Decaying Leaves and Coconut Shells in Drain", "status": "Reported", "upvotes": 6, "days_ago": 3},
    {"ward_id": "WARD-174", "ward_name": "HSR Layout", "lat": 12.9190, "lon": 77.6350, "cat": "Plastic Waste", "sev": 3, "title": "Plastic Beverage Cups along Ring Road", "status": "Reported", "upvotes": 5, "days_ago": 1},
    {"ward_id": "WARD-174", "ward_name": "HSR Layout", "lat": 12.9140, "lon": 77.6400, "cat": "Mixed Municipal Solid Waste", "sev": 3, "title": "Sector 1 Cleared Spot with Plant Pots Placed", "status": "Cleared", "upvotes": 19, "days_ago": 9},

    # --- MALLESHWARAM (Ward 45: 4 reports) ---
    {"ward_id": "WARD-45", "ward_name": "Malleshwaram", "lat": 13.0040, "lon": 77.5710, "cat": "Organic / Biodegradable Waste", "sev": 3, "title": "Flower & Pooja Waste along 8th Cross", "status": "Reported", "upvotes": 11, "days_ago": 2},
    {"ward_id": "WARD-45", "ward_name": "Malleshwaram", "lat": 13.0110, "lon": 77.5740, "cat": "Plastic Waste", "sev": 3, "title": "Single-use Plastic Cups near Sankey Tank Entry", "status": "Reported", "upvotes": 14, "days_ago": 1},
    {"ward_id": "WARD-45", "ward_name": "Malleshwaram", "lat": 13.0070, "lon": 77.5680, "cat": "Mixed Municipal Solid Waste", "sev": 3, "title": "Commercial Waste dumped beside Post Office", "status": "In Progress", "upvotes": 7, "days_ago": 3},
    {"ward_id": "WARD-45", "ward_name": "Malleshwaram", "lat": 13.0020, "lon": 77.5720, "cat": "Mixed Municipal Solid Waste", "sev": 2, "title": "Cleaned Street Corner in 15th Cross", "status": "Cleared", "upvotes": 12, "days_ago": 8},

    # --- JAYANAGAR (Ward 168: 5 reports) ---
    {"ward_id": "WARD-168", "ward_name": "Jayanagar", "lat": 12.9280, "lon": 77.5840, "cat": "Mixed Municipal Solid Waste", "sev": 3, "title": "4th Block Complex Backyard Waste Accumulation", "status": "Reported", "upvotes": 12, "days_ago": 2},
    {"ward_id": "WARD-168", "ward_name": "Jayanagar", "lat": 12.9320, "lon": 77.5890, "cat": "Plastic Waste", "sev": 3, "title": "Plastic Packaging dumped on Road Median", "status": "Reported", "upvotes": 6, "days_ago": 3},
    {"ward_id": "WARD-168", "ward_name": "Jayanagar", "lat": 12.9240, "lon": 77.5810, "cat": "Construction & Demolition Debris", "sev": 4, "title": "Bathroom Renovation Rubble on Pavement", "status": "Reported", "upvotes": 8, "days_ago": 1},
    {"ward_id": "WARD-168", "ward_name": "Jayanagar", "lat": 12.9350, "lon": 77.5860, "cat": "Organic / Biodegradable Waste", "sev": 3, "title": "Fallen Tree Trunks & Dry Leaf Heap", "status": "In Progress", "upvotes": 5, "days_ago": 4},
    {"ward_id": "WARD-168", "ward_name": "Jayanagar", "lat": 12.9300, "lon": 77.5830, "cat": "Mixed Municipal Solid Waste", "sev": 3, "title": "Cleared Corner with Anti-Dumping Rangoli Art", "status": "Cleared", "upvotes": 22, "days_ago": 10},

    # --- HEBBAL (Ward 20: 4 reports) ---
    {"ward_id": "WARD-20", "ward_name": "Hebbal & Kempapura", "lat": 13.0420, "lon": 77.5920, "cat": "Mixed Municipal Solid Waste", "sev": 4, "title": "Flyover Pillar #44 Garbage Accumulation", "status": "Reported", "upvotes": 16, "days_ago": 2},
    {"ward_id": "WARD-20", "ward_name": "Hebbal & Kempapura", "lat": 13.0460, "lon": 77.5880, "cat": "Plastic Waste", "sev": 4, "title": "Plastic Bottled Waste Floating near Lake Edge", "status": "Reported", "upvotes": 20, "days_ago": 1},
    {"ward_id": "WARD-20", "ward_name": "Hebbal & Kempapura", "lat": 13.0380, "lon": 77.5950, "cat": "Construction & Demolition Debris", "sev": 4, "title": "Debris Dumping along Kempapura Main Road", "status": "In Progress", "upvotes": 8, "days_ago": 3},
    {"ward_id": "WARD-20", "ward_name": "Hebbal & Kempapura", "lat": 13.0440, "lon": 77.5910, "cat": "Mixed Municipal Solid Waste", "sev": 3, "title": "Lake Pathway Debris Cleared by Marshals", "status": "Cleared", "upvotes": 17, "days_ago": 7},
    # --- REPEAT-DUMP SITES: cleaned, then dumped on again and again (powers the 'gets dirty again' analysis) ---
    {"ward_id": "WARD-151", "ward_name": "Koramangala", "lat": 12.93514, "lon": 77.614, "cat": "Mixed Municipal Solid Waste", "sev": 3, "title": "Koramangala 5th Block Bus Stop Corner", "status": "Cleared", "upvotes": 2, "days_ago": 84},
    {"ward_id": "WARD-151", "ward_name": "Koramangala", "lat": 12.9352, "lon": 77.61406, "cat": "Mixed Municipal Solid Waste", "sev": 3, "title": "Koramangala 5th Block Bus Stop Corner (again)", "status": "Cleared", "upvotes": 3, "days_ago": 61},
    {"ward_id": "WARD-151", "ward_name": "Koramangala", "lat": 12.93526, "lon": 77.61394, "cat": "Mixed Municipal Solid Waste", "sev": 3, "title": "Koramangala 5th Block Bus Stop Corner (again)", "status": "Cleared", "upvotes": 4, "days_ago": 38},
    {"ward_id": "WARD-151", "ward_name": "Koramangala", "lat": 12.93514, "lon": 77.614, "cat": "Mixed Municipal Solid Waste", "sev": 3, "title": "Koramangala 5th Block Bus Stop Corner (again)", "status": "Cleared", "upvotes": 5, "days_ago": 15},
    {"ward_id": "WARD-151", "ward_name": "Koramangala", "lat": 12.9352, "lon": 77.61406, "cat": "Mixed Municipal Solid Waste", "sev": 3, "title": "Koramangala 5th Block Bus Stop Corner (again)", "status": "Reported", "upvotes": 6, "days_ago": 3},
    {"ward_id": "WARD-168", "ward_name": "Jayanagar", "lat": 12.92544, "lon": 77.5835, "cat": "Organic / Biodegradable Waste", "sev": 3, "title": "Jayanagar 4th T Block Market Back Lane", "status": "Cleared", "upvotes": 2, "days_ago": 70},
    {"ward_id": "WARD-168", "ward_name": "Jayanagar", "lat": 12.9255, "lon": 77.58356, "cat": "Organic / Biodegradable Waste", "sev": 3, "title": "Jayanagar 4th T Block Market Back Lane (again)", "status": "Cleared", "upvotes": 3, "days_ago": 49},
    {"ward_id": "WARD-168", "ward_name": "Jayanagar", "lat": 12.92556, "lon": 77.58344, "cat": "Organic / Biodegradable Waste", "sev": 3, "title": "Jayanagar 4th T Block Market Back Lane (again)", "status": "Cleared", "upvotes": 4, "days_ago": 27},
    {"ward_id": "WARD-168", "ward_name": "Jayanagar", "lat": 12.92544, "lon": 77.5835, "cat": "Organic / Biodegradable Waste", "sev": 3, "title": "Jayanagar 4th T Block Market Back Lane (again)", "status": "In Progress", "upvotes": 5, "days_ago": 8},
    {"ward_id": "WARD-112", "ward_name": "Domlur & Indiranagar", "lat": 12.96994, "lon": 77.6405, "cat": "Plastic Waste", "sev": 3, "title": "Indiranagar 12th Main Bus Shelter", "status": "Cleared", "upvotes": 2, "days_ago": 60},
    {"ward_id": "WARD-112", "ward_name": "Domlur & Indiranagar", "lat": 12.97, "lon": 77.64056, "cat": "Plastic Waste", "sev": 3, "title": "Indiranagar 12th Main Bus Shelter (again)", "status": "Cleared", "upvotes": 3, "days_ago": 41},
    {"ward_id": "WARD-112", "ward_name": "Domlur & Indiranagar", "lat": 12.97006, "lon": 77.64044, "cat": "Plastic Waste", "sev": 3, "title": "Indiranagar 12th Main Bus Shelter (again)", "status": "Cleared", "upvotes": 4, "days_ago": 20},
    {"ward_id": "WARD-20", "ward_name": "Hebbal & Kempapura", "lat": 13.04994, "lon": 77.595, "cat": "Construction & Demolition Debris", "sev": 4, "title": "Hebbal Service Road Vacant Plot", "status": "Cleared", "upvotes": 2, "days_ago": 45},
    {"ward_id": "WARD-20", "ward_name": "Hebbal & Kempapura", "lat": 13.05, "lon": 77.59506, "cat": "Construction & Demolition Debris", "sev": 4, "title": "Hebbal Service Road Vacant Plot (again)", "status": "Cleared", "upvotes": 3, "days_ago": 30},
    {"ward_id": "WARD-20", "ward_name": "Hebbal & Kempapura", "lat": 13.05006, "lon": 77.59494, "cat": "Construction & Demolition Debris", "sev": 4, "title": "Hebbal Service Road Vacant Plot (again)", "status": "Cleared", "upvotes": 4, "days_ago": 14},
    {"ward_id": "WARD-174", "ward_name": "HSR Layout", "lat": 12.90994, "lon": 77.648, "cat": "Mixed Municipal Solid Waste", "sev": 3, "title": "HSR Sector 7 Park Gate", "status": "Cleared", "upvotes": 2, "days_ago": 52},
    {"ward_id": "WARD-174", "ward_name": "HSR Layout", "lat": 12.91, "lon": 77.64806, "cat": "Mixed Municipal Solid Waste", "sev": 3, "title": "HSR Sector 7 Park Gate (again)", "status": "Cleared", "upvotes": 3, "days_ago": 33},
]


def seed_database():
    """Initializes and seeds 55 rich reports into SQLite."""
    reset_db()
    now = datetime.now(timezone.utc)

    for idx, cfg in enumerate(RAW_SEED_CONFIGS, start=1):
        report_id = f"GWR-BLR-{idx:04d}"
        days_ago = cfg["days_ago"]
        rep_date = now - timedelta(days=days_ago, hours=random.randint(1, 14), minutes=random.randint(5, 50))
        rep_iso = rep_date.isoformat()

        # Cleared date if status is Cleared
        cleared_iso = None
        after_img = None
        notes = ""
        if cfg["status"] == "Cleared":
            clr_date = rep_date + timedelta(hours=random.randint(8, 36))
            cleared_iso = clr_date.isoformat()
            after_img = SVG_TEMPLATES["CLEARED_PROOF"]
            notes = "BBMP Auto-Tipper deployed. 1.8 tons of waste cleared, area swept, sanitized with bleaching powder."
        elif cfg["status"] == "In Progress":
            notes = "Work order dispatched to Ward Sanitation Supervisor. Tipper en route."

        # Compute priority score
        p_calc = calculate_priority_score(
            severity=cfg["sev"],
            lat=cfg["lat"],
            lon=cfg["lon"],
            upvotes=cfg["upvotes"],
            days_open=days_ago if cfg["status"] != "Cleared" else 0
        )

        img_url = SVG_TEMPLATES.get(cfg["cat"], SVG_TEMPLATES["Mixed Municipal Solid Waste"])

        # Determine materials based on category
        materials = {
            "Plastic Waste": ["PET Bottles", "LDPE Wrappers", "Single-Use Plastic Cups"],
            "Construction & Demolition Debris": ["Concrete Slabs", "Red Brick Rubble", "Plaster Mortar"],
            "Organic / Biodegradable Waste": ["Rotting Food", "Vegetable Market Sweepings", "Foliage"],
            "Electronic Waste (E-Waste)": ["Burned Circuit Boards", "Smashed LCD Screens", "PVC Wiring"],
            "Hazardous / Medical Waste": ["Chemical Drum Residue", "Solvent Containers", "Industrial Sludge"],
            "Mixed Municipal Solid Waste": ["Unsegregated Household Trash", "Polythene Bags", "Food Scraps"]
        }.get(cfg["cat"], ["Mixed Refuse"])

        vol_estimate = f"{round(random.uniform(1.2, 3.8), 1)} - {round(random.uniform(4.0, 6.5), 1)} m³"

        report_data = {
            "id": report_id,
            "title": cfg["title"],
            "description": f"Citizen report logged via Geo-Waste Reporter. Observed illegal waste dumping along {cfg['ward_name']}. Potential hazard to urban drainage and neighborhood hygiene.",
            "category": cfg["cat"],
            "severity": cfg["sev"],
            "priority_score": p_calc["score"],
            "priority_level": p_calc["level"],
            "latitude": cfg["lat"],
            "longitude": cfg["lon"],
            "address": f"{cfg['title']}, {cfg['ward_name']}, Bengaluru",
            "ward_id": cfg["ward_id"],
            "ward_name": cfg["ward_name"],
            "status": cfg["status"],
            "image_url": img_url,
            "after_image_url": after_img,
            "upvotes": cfg["upvotes"],
            "ai_confidence": round(random.uniform(0.91, 0.98), 2),
            "ai_materials": materials,
            "estimated_volume": vol_estimate,
            "closest_receptor_name": p_calc["closest_receptor"]["name"] if p_calc.get("closest_receptor") else None,
            "closest_receptor_dist": p_calc["closest_receptor"]["distance_m"] if p_calc.get("closest_receptor") else None,
            "closest_receptor_type": p_calc["closest_receptor"]["type"] if p_calc.get("closest_receptor") else None,
            "reported_at": rep_iso,
            "cleared_at": cleared_iso,
            "notes": notes
        }

        create_report(report_data)

    print(f"Successfully seeded {len(RAW_SEED_CONFIGS)} realistic dumping reports into SQLite!")


if __name__ == "__main__":
    seed_database()
