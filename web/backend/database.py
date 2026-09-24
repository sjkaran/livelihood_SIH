"""
database.py — SQLite session logging for the Livelihood Mapping Voice Assistant
Uses plain sqlite3 (kept simple on purpose, matches SwagatAI's lightweight DB style).
"""
import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sessions.db")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            language TEXT,
            qa_json TEXT,          -- raw question/answer transcript pairs
            profile_json TEXT,     -- extracted structured profile
            recommendations_json TEXT  -- top-3 trades with scores
        )
    """)
    conn.commit()
    conn.close()


def log_session(language, qa_pairs, profile, recommendations):
    conn = get_conn()
    conn.execute(
        "INSERT INTO sessions (timestamp, language, qa_json, profile_json, recommendations_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            datetime.utcnow().isoformat(timespec="seconds") + "Z",
            language,
            json.dumps(qa_pairs, ensure_ascii=False),
            json.dumps(profile, ensure_ascii=False),
            json.dumps(recommendations, ensure_ascii=False),
        ),
    )
    conn.commit()
    session_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    conn.close()
    return session_id


def get_all_sessions():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM sessions ORDER BY id DESC").fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "timestamp": r["timestamp"],
            "language": r["language"],
            "qa": json.loads(r["qa_json"]) if r["qa_json"] else [],
            "profile": json.loads(r["profile_json"]) if r["profile_json"] else {},
            "recommendations": json.loads(r["recommendations_json"]) if r["recommendations_json"] else [],
        })
    return result


def get_trade_recommendation_counts():
    """Aggregate how often each trade was recommended (rank #1) — used for the dashboard bar chart."""
    sessions = get_all_sessions()
    counts = {}
    for s in sessions:
        recs = s["recommendations"]
        if recs:
            top_trade = recs[0]["trade_name"]
            counts[top_trade] = counts.get(top_trade, 0) + 1
    return counts
