import json
import os
import sqlite3
from pathlib import Path

_MAX_CONVERSATIONS = 15


def _db_path() -> Path:
    configured = os.getenv("DATABASE_PATH")
    if configured:
        return Path(configured)
    azure_home = Path("/home")
    if azure_home.exists() and os.access(str(azure_home), os.W_OK):
        return azure_home / "onderwijsdata.db"
    return Path(__file__).parent.parent / "onderwijsdata.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id        TEXT    NOT NULL,
            username  TEXT    NOT NULL,
            title     TEXT    NOT NULL,
            timestamp INTEGER NOT NULL,
            messages  TEXT    NOT NULL,
            PRIMARY KEY (id, username)
        );
        CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(username, timestamp DESC);

        CREATE TABLE IF NOT EXISTS workbooks (
            id           TEXT NOT NULL,
            username     TEXT NOT NULL,
            title        TEXT NOT NULL,
            description  TEXT NOT NULL DEFAULT '',
            messages     TEXT,
            figures      TEXT,
            instelling   TEXT,
            html_content TEXT,
            created_at   TEXT NOT NULL,
            PRIMARY KEY (id, username)
        );
        CREATE INDEX IF NOT EXISTS idx_wb_user ON workbooks(username, created_at DESC);
    """)
    conn.close()


def list_conversations(username: str) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT id, title, timestamp, messages FROM conversations "
        "WHERE username = ? ORDER BY timestamp DESC LIMIT ?",
        (username, _MAX_CONVERSATIONS),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_conversation(
    username: str, conv_id: str, title: str, timestamp: int, messages: list[dict]
) -> None:
    conn = _connect()
    conn.execute(
        "INSERT INTO conversations (id, username, title, timestamp, messages) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT (id, username) DO UPDATE SET title=excluded.title, "
        "timestamp=excluded.timestamp, messages=excluded.messages",
        (conv_id, username, title, timestamp, json.dumps(messages)),
    )
    conn.commit()
    conn.close()


def delete_conversation(username: str, conv_id: str) -> None:
    conn = _connect()
    conn.execute(
        "DELETE FROM conversations WHERE id = ? AND username = ?",
        (conv_id, username),
    )
    conn.commit()
    conn.close()


def list_workbooks(username: str) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT id, title, description, messages, figures, instelling, "
        "html_content, created_at FROM workbooks "
        "WHERE username = ? ORDER BY created_at DESC",
        (username,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_workbook(
    username: str,
    wb_id: str,
    title: str,
    description: str,
    messages: list[dict] | None = None,
    figures: list | None = None,
    instelling: str | None = None,
    html_content: str | None = None,
    created_at: str = "",
) -> None:
    conn = _connect()
    conn.execute(
        "INSERT INTO workbooks (id, username, title, description, messages, figures, "
        "instelling, html_content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (id, username) DO UPDATE SET title=excluded.title, "
        "description=excluded.description, messages=excluded.messages, "
        "figures=excluded.figures, instelling=excluded.instelling, "
        "html_content=excluded.html_content, created_at=excluded.created_at",
        (
            wb_id, username, title, description,
            json.dumps(messages) if messages is not None else None,
            json.dumps(figures) if figures is not None else None,
            instelling, html_content, created_at,
        ),
    )
    conn.commit()
    conn.close()


def delete_workbook(username: str, wb_id: str) -> None:
    conn = _connect()
    conn.execute(
        "DELETE FROM workbooks WHERE id = ? AND username = ?",
        (wb_id, username),
    )
    conn.commit()
    conn.close()
