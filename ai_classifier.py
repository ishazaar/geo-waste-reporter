"""
Waste Classifier
Two modes:
1. Google Gemini vision (real image analysis) - used only when the GEMINI_API_KEY environment
   variable is set on the SERVER. Model is configurable with GEMINI_MODEL (otherwise current Gemini models are tried automatically).
2. Keyword heuristic fallback (offline demo). It reads the filename + description text ONLY and does
   NOT look at image pixels. It reports low confidence and is flagged with is_demo_heuristic=True so the
   UI never presents it as computer vision.
"""

import os
import json
import base64
import re
from typing import Dict, Any, Optional

CATEGORIES = [
    "Plastic Waste",
    "Construction & Demolition Debris",
    "Organic / Biodegradable Waste",
    "Electronic Waste (E-Waste)",
    "Hazardous / Medical Waste",
    "Mixed Municipal Solid Waste"
]

TYPICAL_SIZE = {  # (volume range m3 string, typical weight kg) -- category averages, NOT measured from the photo
    "Plastic Waste": ("0.5 - 1.5 m³", 60),
    "Construction & Demolition Debris": ("2.0 - 5.0 m³", 2500),
    "Organic / Biodegradable Waste": ("1.0 - 2.5 m³", 700),
    "Electronic Waste (E-Waste)": ("0.3 - 1.0 m³", 120),
    "Hazardous / Medical Waste": ("0.2 - 1.0 m³", 150),
    "Mixed Municipal Solid Waste": ("1.0 - 3.0 m³", 500),
}

CATEGORY_KNOWLEDGE = {
    "Plastic Waste": {
        "severity": 3,
        "recyclability": "High (PET / HDPE / Film)",
        "truck_type": "Light Tipper / Mechanical Grabber",
        "materials": ["PET Bottles", "Polythene Carry Bags", "Packaging Film", "Single-Use Cups"],
        "risks": ["Clogging storm drains & urban floods", "Microplastic breakdown", "Stray animal ingestion"],
        "recommended_action": "Route to dry waste collection center (DWCC) for baling and shredding."
    },
    "Construction & Demolition Debris": {
        "severity": 4,
        "recyclability": "Moderate (Crushed Aggregates / Sub-base)",
        "truck_type": "Heavy Dumper Truck (10 Ton) + JCB",
        "materials": ["Concrete Chunks", "Red Brick Rubble", "Plaster Mortar", "Excavated Soil"],
        "risks": ["Pedestrian right-of-way obstruction", "Dust and PM2.5 air pollution", "Drain siltation"],
        "recommended_action": "Dispatch C&D recycling fleet; transport to municipal processing plant."
    },
    "Organic / Biodegradable Waste": {
        "severity": 3,
        "recyclability": "Compostable / Bio-methanation",
        "truck_type": "Wet Waste Compactor",
        "materials": ["Vegetable & Fruit Scraps", "Rotting Market Produce", "Foliage & Tree Branches", "Food Scraps"],
        "risks": ["Foul odor & hydrogen sulfide emission", "Fly, rodent & mosquito breeding", "Acidic leachate run-off"],
        "recommended_action": "Daily clearance required; route directly to decentralized bio-gas or composting unit."
    },
    "Electronic Waste (E-Waste)": {
        "severity": 5,
        "recyclability": "Specialized Precious Metal Extraction",
        "truck_type": "Enclosed Hazmat / E-Waste Van",
        "materials": ["Circuit Boards (PCBs)", "Cathode / LCD Screens", "PVC Coated Wiring", "Alkaline / Li-ion Cells"],
        "risks": ["Lead, mercury & cadmium soil poisoning", "Toxic fume release upon open burning", "Water table contamination"],
        "recommended_action": "Immediate cordoning; handover strictly to KSPCB authorized e-waste dismantler."
    },
    "Hazardous / Medical Waste": {
        "severity": 5,
        "recyclability": "Strict Incineration / Secure Landfill",
        "truck_type": "Bio-Medical / Hazmat Sealed Vehicle",
        "materials": ["Discarded Syringes & Vials", "Chemical Solvents / Drums", "Oil / Paint Residue", "Contaminated Cotton"],
        "risks": ["Infectious disease transmission (Hepatitis, HIV)", "Chemical fire hazard", "Extreme aquatic toxicity"],
        "recommended_action": "CRITICAL HAZARD: Notify Karnataka State Pollution Control Board & bio-medical incinerator."
    },
    "Mixed Municipal Solid Waste": {
        "severity": 4,
        "recyclability": "Low (Requires MRF Mechanical Sorting)",
        "truck_type": "Automated Hydraulic Compactor",
        "materials": ["Unsegregated Household Bags", "Food Stained Paper", "Textiles", "Packaging", "Composite Debris"],
        "risks": ["Methane gas generation", "Uncontrolled burning risk", "Sanitation worker puncture injury"],
        "recommended_action": "Deploy frontline clearing crew; issue ward source-segregation advisory."
    }
}


def sniff_mime(image_bytes: bytes) -> Optional[str]:
    """Detects the real image type from magic bytes (never trust the filename or client header)."""
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    if image_bytes[:4] == b"GIF8":
        return "image/gif"
    return None


def classify_waste_image(
    image_bytes: Optional[bytes] = None,
    filename: str = "",
    description: str = ""
) -> Dict[str, Any]:
    """
    Classifies a waste report. Uses Gemini if GEMINI_API_KEY is configured on the server and an image is
    supplied; otherwise (or on any Gemini error) falls back to the clearly-labelled keyword heuristic.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    reason = None
    if api_key and image_bytes:
        mime = sniff_mime(image_bytes)
        if mime:
            try:
                return _call_gemini_vision(image_bytes, mime, api_key)
            except Exception as e:  # never log the key / URL
                reason = f"{type(e).__name__}: {str(e)[:140]}"
                print(f"[Classifier] Gemini call failed, using keyword fallback: {reason}")
        else:
            reason = "unsupported image type"

    return _local_keyword_inference(filename, description, reason)


def _build_result(category: str, confidence: float, severity: int, volume: str, weight: int,
                  materials, risks, action: str, recyclable: str, model: str, demo: bool, note: str = "") -> Dict[str, Any]:
    meta = CATEGORY_KNOWLEDGE[category]
    severity = max(1, min(5, int(severity)))
    confidence = max(0.0, min(1.0, float(confidence)))
    return {
        "category": category,
        "confidence": round(confidence, 3),
        "confidence_percentage": round(confidence * 100, 1),
        "severity": severity,
        "recyclability": recyclable or meta["recyclability"],
        "estimated_volume_m3": volume,
        "estimated_weight_kg": weight,
        "truck_dispatch_type": meta["truck_type"],
        "detected_materials": materials or meta["materials"],
        "environmental_risks": risks or meta["risks"],
        "recommended_action": action or meta["recommended_action"],
        "ai_model": model,
        "is_demo_heuristic": demo,
        "note": note,
        "leachate_risk": "High" if severity >= 4 else "Moderate" if severity == 3 else "Low",
    }


# Tried in order if GEMINI_MODEL is unset or its name has been retired (Google answers HTTP 404).
GEMINI_MODEL_FALLBACKS = ("gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-flash-latest", "gemini-3.6-flash")
_WORKING_MODEL: Dict[str, str] = {}
PER_TRY_TIMEOUT_S = 12      # seconds to wait for one model before trying the next one
TOTAL_BUDGET_S = 30         # give up on Gemini after this long overall (keeps the app responsive)


def _call_gemini_vision(image_bytes: bytes, mime: str, api_key: str) -> Dict[str, Any]:
    """Calls the Gemini vision API. The key is sent in a header (not the URL) so it never ends up in logs."""
    import urllib.request

    prompt = (
        "Analyze this urban waste dumping photo. Return ONLY JSON with these exact keys:\n"
        '{"category": one of ' + json.dumps(CATEGORIES) + ', '
        '"confidence": float 0-1 (your honest confidence; use a low value if the photo is unclear or not waste), '
        '"severity": int 1-5, "estimated_volume_m3": string like "1.5 - 2.5 m³", "estimated_weight_kg": int, '
        '"detected_materials": [strings], "environmental_risks": [strings], '
        '"recommended_action": string, "recyclable": string}'
    )
    payload = {
        "contents": [{"parts": [
            {"text": prompt},
            {"inlineData": {"mimeType": mime, "data": base64.b64encode(image_bytes).decode("utf-8")}}
        ]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}
    }
    import urllib.error
    import time

    def _post(model_name: str) -> Dict[str, Any]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key}, method="POST"
        )
        for attempt in range(2):  # one retry for transient 429/5xx
            try:
                with urllib.request.urlopen(req, timeout=PER_TRY_TIMEOUT_S) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = ""
                try:
                    body = e.read().decode("utf-8")[:300]
                except Exception:
                    pass
                print(f"[Classifier] Gemini HTTP {e.code} for model {model_name}: {body}")
                if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                    time.sleep(1.5)
                    continue
                raise

    # Google retires model names over time (HTTP 404). Try the configured model first, then current ones,
    # and remember whichever works so later requests go straight to it.
    candidates = []
    for m in (_WORKING_MODEL.get("name"), os.environ.get("GEMINI_MODEL"), *GEMINI_MODEL_FALLBACKS):
        if m and m not in candidates:
            candidates.append(m)
    res_data, model, last_err = None, None, None
    started = time.time()
    for m in candidates:
        if time.time() - started > TOTAL_BUDGET_S:
            break
        try:
            res_data, model = _post(m), m
            _WORKING_MODEL["name"] = m
            break
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (404, 400):   # unknown / retired model name -> try the next one
                continue
            raise
        except (TimeoutError, OSError) as e:   # slow or unreachable model -> try the next one
            last_err = e
            print(f"[Classifier] {m} timed out / unreachable ({type(e).__name__}); trying next model")
            _WORKING_MODEL.pop("name", None)
            continue
    if res_data is None:
        raise last_err or TimeoutError("Gemini did not answer in time")
    parts = res_data["candidates"][0]["content"]["parts"]
    text = next((p_["text"] for p_ in parts if p_.get("text") and not p_.get("thought")), None)
    if text is None:
        raise ValueError("Gemini returned no text")
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    raw = json.loads(text)
    if isinstance(raw, list) and raw:
        raw = raw[0]

    category = raw.get("category")
    if category not in CATEGORIES:
        raise ValueError(f"Model returned unknown category: {category!r}")
    default_vol, default_wt = TYPICAL_SIZE[category]

    def _list(v):
        return [str(x)[:80] for x in v][:8] if isinstance(v, list) else None

    try:
        weight = int(raw.get("estimated_weight_kg", default_wt))
    except (TypeError, ValueError):
        weight = default_wt
    try:
        confidence = float(raw.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    try:
        severity = int(raw.get("severity", CATEGORY_KNOWLEDGE[category]["severity"]))
    except (TypeError, ValueError):
        severity = CATEGORY_KNOWLEDGE[category]["severity"]

    return _build_result(
        category, confidence, severity,
        str(raw.get("estimated_volume_m3") or default_vol)[:40], weight,
        _list(raw.get("detected_materials")), _list(raw.get("environmental_risks")),
        str(raw.get("recommended_action") or "")[:300], str(raw.get("recyclable") or "")[:100],
        model=f"Google {model} (vision)", demo=False
    )


KEYWORDS = {
    "Plastic Waste": ["plastic", "bottle", "pet", "bag", "polythene", "wrapper", "cup", "pouch", "packaging", "thermocol", "styrofoam", "sachet"],
    "Construction & Demolition Debris": ["debris", "construction", "concrete", "brick", "rubble", "demolition", "cement", "sand", "c&d", "tiles", "excavation", "building material"],
    "Organic / Biodegradable Waste": ["organic", "food", "vegetable", "fruit", "market", "leaf", "leaves", "rotting", "wet waste", "kitchen", "coconut", "banana", "flower", "garden waste"],
    "Electronic Waste (E-Waste)": ["ewaste", "e-waste", "e waste", "circuit", "computer", "battery", "batteries", "phone", "wire", "wiring", "screen", "electronic",
                                    "printer", "monitor", "laptop", "keyboard", "cpu", "tv", "television", "fridge", "refrigerator", "appliance", "ac unit", "scrap electronics", "cable", "charger", "inverter"],
    "Hazardous / Medical Waste": ["chemical", "medical", "hospital", "syringe", "needle", "hazard", "hazardous", "toxic", "oil", "drum", "pharma", "biomedical", "bio-medical", "bandage", "blood", "asbestos", "paint", "acid"],
    "Mixed Municipal Solid Waste": ["dump", "heap", "overflow", "garbage", "bin", "roadside", "mixed", "black bag", "smelly", "trash", "rubbish", "litter"],
}


def _count_hits(text: str, keywords) -> int:
    """Whole-word matching (allows a plural 's'), so 'pet' doesn't match 'carpet' or 'bin' match 'binding'."""
    n = 0
    for k in keywords:
        if re.search(r"(?<![a-z0-9])" + re.escape(k) + r"s?(?![a-z0-9])", text):
            n += 1
    return n


def _local_keyword_inference(filename: str, description: str, reason: Optional[str] = None) -> Dict[str, Any]:
    """
    OFFLINE DEMO FALLBACK. Counts keyword hits in filename + description. It does not analyse the image,
    so confidence is deliberately low and the result is flagged is_demo_heuristic=True.
    If nothing matches, needs_manual_category=True is set so the UI can ask the person to pick a category.
    """
    text = re.sub(r"[_\-.]+", " ", f"{filename} {description}".lower())
    text = f" {text} "
    hits = {cat: _count_hits(text, kws) for cat, kws in KEYWORDS.items()}
    best, n = max(hits.items(), key=lambda kv: kv[1])
    needs_manual = False

    why = (f"The AI photo analysis failed ({reason})" if reason
           else "AI photo analysis is not enabled on the server (no GEMINI_API_KEY)")
    if n == 0:
        best, confidence = "Mixed Municipal Solid Waste", 0.30
        needs_manual = True
        note = f"{why}, so this photo was not analysed and no keywords were found. Please choose the waste category yourself."
    else:
        confidence = min(0.70, 0.45 + 0.08 * n)
        note = f"{why}. Guessed from the words in your description/filename, not from the photo."

    meta = CATEGORY_KNOWLEDGE[best]
    vol, wt = TYPICAL_SIZE[best]
    result = _build_result(
        best, confidence, meta["severity"], f"{vol} (typical)", wt,
        None, None, "", "",
        model="Keyword heuristic (demo fallback, no image analysis)", demo=True, note=note
    )
    result["needs_manual_category"] = needs_manual
    return result
