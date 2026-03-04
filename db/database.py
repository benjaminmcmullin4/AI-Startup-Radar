import sqlite3
import json
from pathlib import Path
from typing import Optional
from config.settings import DB_PATH
from models.company import Company


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    schema_path = Path(__file__).parent / "schema.sql"
    conn.executescript(schema_path.read_text())
    conn.commit()
    conn.close()


# --- Company CRUD ---

def insert_company(company: Company) -> int:
    conn = get_connection()
    d = company.to_dict()
    d.pop("id", None)
    cols = ", ".join(d.keys())
    placeholders = ", ".join(["?"] * len(d))
    cur = conn.execute(f"INSERT INTO companies ({cols}) VALUES ({placeholders})", list(d.values()))
    conn.commit()
    cid = cur.lastrowid
    conn.close()
    log_activity(cid, "imported", f"Added {company.name}")
    return cid


def get_company(company_id: int) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_companies() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM companies ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_company(company_id: int, updates: dict):
    conn = get_connection()
    sets = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [company_id]
    conn.execute(f"UPDATE companies SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", vals)
    conn.commit()
    conn.close()


def update_pipeline_stage(company_id: int, stage: str):
    update_company(company_id, {"pipeline_stage": stage})
    log_activity(company_id, "stage_changed", f"Moved to {stage}")


def get_company_count() -> int:
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    conn.close()
    return count


def delete_companies_by_source(source: str) -> int:
    """Delete all companies (and their scores, notes, tags, news, activity) with a given source."""
    conn = get_connection()
    company_ids = [r[0] for r in conn.execute(
        "SELECT id FROM companies WHERE source = ?", (source,)
    ).fetchall()]
    if company_ids:
        placeholders = ",".join("?" * len(company_ids))
        conn.execute(f"DELETE FROM scores WHERE company_id IN ({placeholders})", company_ids)
        conn.execute(f"DELETE FROM notes WHERE company_id IN ({placeholders})", company_ids)
        conn.execute(f"DELETE FROM company_tags WHERE company_id IN ({placeholders})", company_ids)
        conn.execute(f"DELETE FROM news_items WHERE company_id IN ({placeholders})", company_ids)
        conn.execute(f"DELETE FROM activity_log WHERE company_id IN ({placeholders})", company_ids)
        conn.execute(f"DELETE FROM companies WHERE source = ?", (source,))
    conn.commit()
    conn.close()
    return len(company_ids)


# --- Scores CRUD ---

def upsert_score(score_data: dict):
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM scores WHERE company_id = ? AND thesis_id = ?",
        (score_data["company_id"], score_data.get("thesis_id")),
    ).fetchone()
    if existing:
        sid = existing[0]
        sets = ", ".join(f"{k} = ?" for k in score_data if k != "id")
        vals = [v for k, v in score_data.items() if k != "id"] + [sid]
        conn.execute(f"UPDATE scores SET {sets}, scored_at = CURRENT_TIMESTAMP WHERE id = ?", vals)
    else:
        cols = ", ".join(score_data.keys())
        placeholders = ", ".join(["?"] * len(score_data))
        conn.execute(f"INSERT INTO scores ({cols}) VALUES ({placeholders})", list(score_data.values()))
    conn.commit()
    conn.close()
    log_activity(score_data["company_id"], "scored", f"Composite: {score_data.get('composite_score', 0):.1f}")


def get_score(company_id: int, thesis_id: Optional[int] = None) -> Optional[dict]:
    conn = get_connection()
    if thesis_id:
        row = conn.execute(
            "SELECT * FROM scores WHERE company_id = ? AND thesis_id = ? ORDER BY scored_at DESC LIMIT 1",
            (company_id, thesis_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM scores WHERE company_id = ? ORDER BY scored_at DESC LIMIT 1",
            (company_id,),
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_scores() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT s.*, c.name as company_name
        FROM scores s JOIN companies c ON s.company_id = c.id
        ORDER BY s.composite_score DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Theses CRUD ---

def insert_thesis(thesis_data: dict) -> int:
    conn = get_connection()
    cols = ", ".join(thesis_data.keys())
    placeholders = ", ".join(["?"] * len(thesis_data))
    cur = conn.execute(f"INSERT INTO theses ({cols}) VALUES ({placeholders})", list(thesis_data.values()))
    conn.commit()
    tid = cur.lastrowid
    conn.close()
    return tid


def get_thesis(thesis_id: int) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM theses WHERE id = ?", (thesis_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_theses() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM theses ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_thesis(thesis_id: int, updates: dict):
    conn = get_connection()
    sets = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [thesis_id]
    conn.execute(f"UPDATE theses SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", vals)
    conn.commit()
    conn.close()


def get_default_thesis() -> Optional[dict]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM theses ORDER BY id LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


# --- Notes ---

def add_note(company_id: int, content: str, author: str = "analyst"):
    conn = get_connection()
    conn.execute("INSERT INTO notes (company_id, content, author) VALUES (?, ?, ?)", (company_id, content, author))
    conn.commit()
    conn.close()
    log_activity(company_id, "note_added", content[:100])


def get_notes(company_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM notes WHERE company_id = ? ORDER BY created_at DESC", (company_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Tags ---

def add_tag(company_id: int, tag: str):
    conn = get_connection()
    try:
        conn.execute("INSERT INTO company_tags (company_id, tag) VALUES (?, ?)", (company_id, tag))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()


def remove_tag(company_id: int, tag: str):
    conn = get_connection()
    conn.execute("DELETE FROM company_tags WHERE company_id = ? AND tag = ?", (company_id, tag))
    conn.commit()
    conn.close()


def get_tags(company_id: int) -> list[str]:
    conn = get_connection()
    rows = conn.execute("SELECT tag FROM company_tags WHERE company_id = ?", (company_id,)).fetchall()
    conn.close()
    return [r["tag"] for r in rows]


# --- News ---

def insert_news(news_data: dict) -> int:
    conn = get_connection()
    cols = ", ".join(news_data.keys())
    placeholders = ", ".join(["?"] * len(news_data))
    cur = conn.execute(f"INSERT INTO news_items ({cols}) VALUES ({placeholders})", list(news_data.values()))
    conn.commit()
    nid = cur.lastrowid
    conn.close()
    return nid


def get_news(company_id: Optional[int] = None, limit: int = 50) -> list[dict]:
    conn = get_connection()
    if company_id:
        rows = conn.execute(
            "SELECT * FROM news_items WHERE company_id = ? ORDER BY published_date DESC LIMIT ?",
            (company_id, limit),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM news_items ORDER BY published_date DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Activity Log ---

def log_activity(company_id: Optional[int], action: str, details: str = ""):
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO activity_log (company_id, action, details) VALUES (?, ?, ?)",
            (company_id, action, details),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_activity_log(limit: int = 50) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT a.*, c.name as company_name
        FROM activity_log a LEFT JOIN companies c ON a.company_id = c.id
        ORDER BY a.created_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Companies with scores join ---

def get_companies_with_scores() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT c.*, s.composite_score, s.tier, s.team_score, s.financial_score,
               s.market_score, s.product_score, s.momentum_score, s.score_breakdown_json
        FROM companies c
        LEFT JOIN scores s ON c.id = s.company_id
        ORDER BY COALESCE(s.composite_score, 0) DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]
