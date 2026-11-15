"""
SQLite Database Layer for Geo-Waste Reporter
Handles persistence for reports, audit logs, and upvotes with full transactional support.
"""

import sqlite3
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from geo_analytics import calculate_priority_score, receptor_from_report

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Where the SQLite file and uploaded photos live. On Vercel / AWS Lambda the project folder is READ-ONLY and only
# /tmp is writable (and /tmp is wiped between cold starts), so use it there. Override with DATA_DIR if you
# have a persistent disk.
_SERVERLESS = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
DATA_DIR = os.environ.get("DATA_DIR") or ("/tmp/geo-waste" if _SERVERLESS else _BASE_DIR)
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except OSError as _e:  # never crash at import time
    print(f"[database] Could not create DATA_DIR {DATA_DIR}: {_e}")

DB_PATH = os.path.join(DATA_DIR, "geo_waste.db")


@contextmanager
def get_connection():
    """Yields a connection; commits on success, rolls back on error and ALWAYS closes it."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _days_open(reported_at: Optional[str]) -> float:
    try:
        dt = datetime.fromisoformat(reported_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)
    except Exception:
        return 0.0


def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass

        # Reports Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT NOT NULL,
                severity INTEGER DEFAULT 3,
                priority_score REAL DEFAULT 50.0,
                priority_level TEXT DEFAULT 'Medium',
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                address TEXT,
                ward_id TEXT,
                ward_name TEXT,
                status TEXT DEFAULT 'Reported',
                image_url TEXT,
                after_image_url TEXT,
                upvotes INTEGER DEFAULT 0,
                ai_confidence REAL DEFAULT 0.90,
                ai_materials TEXT,
                estimated_volume TEXT,
                closest_receptor_name TEXT,
                closest_receptor_dist REAL,
                closest_receptor_type TEXT,
                reported_at TEXT NOT NULL,
                cleared_at TEXT,
                notes TEXT
            )
        """)

        # Migration for databases created before closest_receptor_type existed
        try:
            cursor.execute("ALTER TABLE reports ADD COLUMN closest_receptor_type TEXT")
        except sqlite3.OperationalError:
            pass

        # Upvotes Table (Prevents double upvoting)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS upvotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id TEXT NOT NULL,
                user_token TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(report_id, user_token)
            )
        """)

        # Audit Log Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        conn.commit()


def get_all_reports(
    status: Optional[str] = None,
    category: Optional[str] = None,
    ward: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None
) -> List[Dict[str, Any]]:
    query = "SELECT * FROM reports WHERE 1=1"
    params = []

    if status and status != "All":
        query += " AND status = ?"
        params.append(status)
    if category and category != "All":
        query += " AND category = ?"
        params.append(category)
    if ward and ward != "All":
        query += " AND (ward_name = ? OR ward_id = ?)"
        params.extend([ward, ward])
    if priority and priority != "All":
        query += " AND priority_level = ?"
        params.append(priority)
    if search:
        query += " AND (title LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\' OR address LIKE ? ESCAPE '\\' OR id LIKE ? ESCAPE '\\')"
        esc_s = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        s = f"%{esc_s}%"
        params.extend([s, s, s, s])

    query += " ORDER BY reported_at DESC"

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        results = []
        for r in rows:
            d = dict(r)
            if d.get("ai_materials"):
                try:
                    d["ai_materials"] = json.loads(d["ai_materials"])
                except Exception:
                    pass
            results.append(d)
        return results


def get_report_by_id(report_id: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("ai_materials"):
            try:
                d["ai_materials"] = json.loads(d["ai_materials"])
            except Exception:
                pass
        
        # Get audit trail
        cursor.execute("SELECT * FROM audit_log WHERE report_id = ? ORDER BY timestamp DESC", (report_id,))
        d["audit_trail"] = [dict(a) for a in cursor.fetchall()]
        return d


def create_report(data: Dict[str, Any]) -> Dict[str, Any]:
    provided_id = data.get("id")
    reported_at = data.get("reported_at") or datetime.now(timezone.utc).isoformat()
    ai_materials_str = json.dumps(data.get("ai_materials", []))

    for attempt in range(5):
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                report_id = provided_id
                if not report_id:
                    # MAX-based (not COUNT-based) so deleted rows can never cause an ID collision
                    cursor.execute(
                        "SELECT COALESCE(MAX(CAST(substr(id, 9) AS INTEGER)), 0) FROM reports WHERE id LIKE 'GWR-BLR-%'"
                    )
                    report_id = f"GWR-BLR-{cursor.fetchone()[0] + 1:04d}"

                cursor.execute("""
                    INSERT INTO reports (
                        id, title, description, category, severity, priority_score, priority_level,
                        latitude, longitude, address, ward_id, ward_name, status, image_url,
                        after_image_url, upvotes, ai_confidence, ai_materials, estimated_volume,
                        closest_receptor_name, closest_receptor_dist, closest_receptor_type, reported_at, cleared_at, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    report_id,
                    data.get("title", "Illegal Dump Site"),
                    data.get("description", ""),
                    data.get("category", "Mixed Municipal Solid Waste"),
                    data.get("severity", 3),
                    data.get("priority_score", 50.0),
                    data.get("priority_level", "Medium"),
                    float(data.get("latitude")),
                    float(data.get("longitude")),
                    data.get("address", "Bengaluru Urban"),
                    data.get("ward_id", "WARD-00"),
                    data.get("ward_name", "Bengaluru Central"),
                    data.get("status", "Reported"),
                    data.get("image_url", "/static/images/placeholder_dump.svg"),
                    data.get("after_image_url"),
                    data.get("upvotes", 0),
                    data.get("ai_confidence"),
                    ai_materials_str,
                    data.get("estimated_volume"),
                    data.get("closest_receptor_name"),
                    data.get("closest_receptor_dist"),
                    data.get("closest_receptor_type"),
                    reported_at,
                    data.get("cleared_at"),
                    data.get("notes", "")
                ))

                cursor.execute("""
                    INSERT INTO audit_log (report_id, action, actor, details, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    report_id,
                    "REPORT_CREATED",
                    "Citizen Reporter",
                    f"Logged new dump report ({data.get('category')}) with initial priority {data.get('priority_score', 50.0)}",
                    reported_at
                ))
            return get_report_by_id(report_id)
        except sqlite3.IntegrityError:
            # Another request grabbed the same ID between SELECT and INSERT: retry (never for caller-supplied IDs)
            if provided_id or attempt == 4:
                raise
    raise RuntimeError("Could not allocate a report ID")


def update_report_status(
    report_id: str,
    status: str,
    after_image_url: Optional[str] = None,
    notes: Optional[str] = None,
    actor: str = "Municipal SWM Supervisor"
) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        
        now_iso = datetime.now(timezone.utc).isoformat()
        update_query = "UPDATE reports SET status = ?"
        params = [status]

        if after_image_url:
            update_query += ", after_image_url = ?"
            params.append(after_image_url)
        if notes:
            update_query += ", notes = ?"
            params.append(notes)
        if status == "Cleared":
            update_query += ", cleared_at = ?"
            params.append(now_iso)
        else:
            update_query += ", cleared_at = NULL"  # re-opened reports must not keep a stale clearance time

        update_query += " WHERE id = ?"
        params.append(report_id)

        cursor.execute(update_query, params)
        if cursor.rowcount == 0:
            return None

        # Log status change in audit log
        details = f"Status updated to '{status}'"
        if after_image_url:
            details += " with photo proof verification"
        if notes:
            details += f". Notes: {notes}"

        cursor.execute("""
            INSERT INTO audit_log (report_id, action, actor, details, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (report_id, f"STATUS_CHANGE_{status.upper().replace(' ', '_')}", actor, details, now_iso))

        conn.commit()

    return get_report_by_id(report_id)


def upvote_report(report_id: str, user_token: str = "default_user") -> Dict[str, Any]:
    """Returns a dict with `success` and, on failure, `status_code` (404 / 409) for the API layer."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT severity, latitude, longitude, status, reported_at, closest_receptor_name, closest_receptor_dist, closest_receptor_type FROM reports WHERE id = ?",
            (report_id,)
        )
        rep = cursor.fetchone()
        if not rep:
            return {"success": False, "status_code": 404, "message": "Report not found"}
        if rep["status"] == "Cleared":
            return {"success": False, "status_code": 409, "message": "This report is already cleared"}

        cursor.execute("SELECT 1 FROM upvotes WHERE report_id = ? AND user_token = ?", (report_id, user_token))
        if cursor.fetchone():
            return {"success": False, "status_code": 409, "message": "Already upvoted this report"}

        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            cursor.execute("INSERT INTO upvotes (report_id, user_token, created_at) VALUES (?, ?, ?)",
                           (report_id, user_token, now_iso))
        except sqlite3.IntegrityError:
            return {"success": False, "status_code": 409, "message": "Already upvoted this report"}

        cursor.execute("UPDATE reports SET upvotes = upvotes + 1 WHERE id = ?", (report_id,))
        cursor.execute("SELECT upvotes FROM reports WHERE id = ?", (report_id,))
        new_upvotes = cursor.fetchone()["upvotes"]

        # Recompute with the same MCDA formula used everywhere else (includes the upvote cap and report age)
        calc = calculate_priority_score(
            severity=rep["severity"], lat=rep["latitude"], lon=rep["longitude"],
            upvotes=new_upvotes, days_open=_days_open(rep["reported_at"]),
            receptor=receptor_from_report(rep)
        )
        new_priority, new_level = calc["score"], calc["level"]

        cursor.execute("UPDATE reports SET priority_score = ?, priority_level = ? WHERE id = ?",
                       (new_priority, new_level, report_id))

        cursor.execute("""
            INSERT INTO audit_log (report_id, action, actor, details, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (report_id, "UPVOTED", f"Citizen ({user_token[:8]})", f"Report verified/upvoted. Total upvotes: {new_upvotes}", now_iso))

    return {
        "success": True,
        "new_upvotes": new_upvotes,
        "new_priority_score": new_priority,
        "new_priority_level": new_level
    }


def get_analytics_summary() -> Dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Total counts
        cursor.execute("SELECT COUNT(*) FROM reports")
        total_reports = cursor.fetchone()[0]

        cursor.execute("SELECT status, COUNT(*) FROM reports GROUP BY status")
        status_counts = dict(cursor.fetchall())

        cursor.execute("SELECT category, COUNT(*) FROM reports GROUP BY category")
        category_counts = dict(cursor.fetchall())

        cursor.execute("SELECT priority_level, COUNT(*) FROM reports GROUP BY priority_level")
        priority_counts = dict(cursor.fetchall())

        # Average resolution time for cleared reports (in hours)
        cursor.execute("""
            SELECT reported_at, cleared_at FROM reports 
            WHERE status = 'Cleared' AND cleared_at IS NOT NULL
        """)
        cleared_rows = cursor.fetchall()
        
        resolution_hours = []
        for row in cleared_rows:
            try:
                rep_dt = datetime.fromisoformat(row["reported_at"])
                clr_dt = datetime.fromisoformat(row["cleared_at"])
                diff = (clr_dt - rep_dt).total_seconds() / 3600.0
                if diff > 0:
                    resolution_hours.append(diff)
            except Exception:
                pass
        
        avg_res_hours = round(sum(resolution_hours) / len(resolution_hours), 1) if resolution_hours else 0.0

        # Recent 7 days trend
        cursor.execute("""
            SELECT report_date, count FROM (
                SELECT substr(reported_at, 1, 10) AS report_date, COUNT(*) AS count
                FROM reports
                GROUP BY report_date
                ORDER BY report_date DESC
                LIMIT 14
            ) ORDER BY report_date ASC
        """)
        timeline = [{"date": r["report_date"], "count": r["count"]} for r in cursor.fetchall()]

        return {
            "total_reports": total_reports,
            "status_counts": {
                "Reported": status_counts.get("Reported", 0),
                "In Progress": status_counts.get("In Progress", 0),
                "Cleared": status_counts.get("Cleared", 0)
            },
            "category_counts": category_counts,
            "priority_counts": priority_counts,
            "average_resolution_hours": avg_res_hours,
            "clearance_rate_percent": round((status_counts.get("Cleared", 0) / max(1, total_reports)) * 100, 1),
            "timeline": timeline
        }


def get_ward_stats() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                ward_id,
                ward_name,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'Reported' THEN 1 ELSE 0 END) as reported,
                SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END) as in_progress,
                SUM(CASE WHEN status = 'Cleared' THEN 1 ELSE 0 END) as cleared,
                AVG(severity) as avg_severity,
                AVG(priority_score) as avg_priority
            FROM reports
            WHERE ward_name IS NOT NULL
            GROUP BY ward_id, ward_name
            ORDER BY total DESC
        """)
        rows = cursor.fetchall()

        wards_data = []
        for r in rows:
            tot = r["total"]
            clr = r["cleared"] or 0
            open_count = tot - clr
            rate = round((clr / max(1, tot)) * 100.0, 1)
            
            # Cleanliness index formula: higher clearance rate + lower average severity
            cleanliness_score = max(10, min(100, int(rate * 0.7 + (5.0 - (r["avg_severity"] or 3.0)) * 6.0)))
            
            if cleanliness_score >= 80:
                grade = "A (Clean)"
            elif cleanliness_score >= 65:
                grade = "B (Good)"
            elif cleanliness_score >= 50:
                grade = "C (Needs Attention)"
            else:
                grade = "D (Critical Action Required)"

            wards_data.append({
                "ward_id": r["ward_id"],
                "ward_name": r["ward_name"],
                "total_reports": tot,
                "open_reports": open_count,
                "cleared_reports": clr,
                "clearance_rate": rate,
                "avg_severity": round(r["avg_severity"] or 3.0, 1),
                "avg_priority": round(r["avg_priority"] or 50.0, 1),
                "cleanliness_index": cleanliness_score,
                "grade": grade
            })
        return wards_data


def reset_db():
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except Exception:
            pass
    init_db()
