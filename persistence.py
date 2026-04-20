import json
import sqlite3
from datetime import datetime
from pathlib import Path

_DB = Path("data/sessions.db")


def _connect() -> sqlite3.Connection:
    _DB.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id       TEXT PRIMARY KEY,
                title    TEXT,
                saved_at TEXT NOT NULL,
                messages TEXT NOT NULL
            )
        """)


def save(session_id: str, messages: list[dict]) -> None:
    user_msgs = [m for m in messages if m["role"] == "user"]
    title = user_msgs[0]["content"][:72] if user_msgs else "Gesprek"
    serialisable = [
        m for m in messages
        if isinstance(m.get("content"), str) or m.get("content") is None
    ]
    with _connect() as conn:
        conn.execute(
            """INSERT INTO sessions(id, title, saved_at, messages) VALUES(?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET title=excluded.title,
               saved_at=excluded.saved_at, messages=excluded.messages""",
            (session_id, title, datetime.now().isoformat(),
             json.dumps(serialisable, ensure_ascii=False)),
        )


def load(session_id: str) -> list[dict] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT messages FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
    return json.loads(row["messages"]) if row else None


def recent(limit: int = 4) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, saved_at FROM sessions ORDER BY saved_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete(session_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
