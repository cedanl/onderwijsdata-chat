import json
import logging
import os
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MAX_CONVERSATIONS = 15
_USE_POSTGRES = bool(os.getenv("POSTGRES_URI"))


def _db_path() -> Path:
    configured = os.getenv("DATABASE_PATH")
    if configured:
        return Path(configured)
    azure_home = Path("/home")
    if azure_home.exists() and os.access(str(azure_home), os.W_OK):
        return azure_home / "onderwijsdata.db"
    return Path(__file__).parent.parent / "onderwijsdata.db"


def _connect() -> Any:
    if _USE_POSTGRES:
        try:
            import psycopg2
            import psycopg2.extras
            conn = psycopg2.connect(os.getenv("POSTGRES_URI"))
            conn.autocommit = False
            return conn
        except ImportError:
            raise RuntimeError("psycopg2 required for PostgreSQL but not installed") from None
    else:
        conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn


def _execute(conn: Any, sql: str, params: tuple = ()) -> Any:
    """Run a query with SQLite '?' placeholders, on either driver.

    sqlite3.Connection has a convenience .execute(); psycopg2 connections
    don't — they need an explicit cursor, and Postgres uses '%s' placeholders
    instead of '?'. RealDictCursor keeps rows dict-convertible like
    sqlite3.Row, so callers can use dict(row) either way.
    """
    if _USE_POSTGRES:
        import psycopg2.extras
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(sql.replace("?", "%s"), params)
        return cursor
    return conn.execute(sql, params)


def _thread(messages_json: str) -> list[tuple] | None:
    """A stored thread as comparable (role, content) pairs; None when unreadable."""
    try:
        messages = json.loads(messages_json)
    except (TypeError, ValueError):
        return None
    if not isinstance(messages, list) or not all(isinstance(m, dict) for m in messages):
        return None
    return [(m.get("role"), json.dumps(m.get("content"), sort_keys=True)) for m in messages]


def _dedupe_conversations(conn: Any) -> None:
    """Remove pre-#69 duplicate conversations: snapshots of one growing thread.

    Before #69 every save got a new id (#151), so one conversation was stored
    once per save. A row is such a snapshot only when its messages, role and
    content, are the start of another row of the same user and title
    (case-insensitive). Anything less is no proof: two conversations that open
    with the same question but got another answer both stay (#178, #184), and
    so does a row whose messages cannot be read. The richest row wins, tie-break
    on the newest timestamp.

    Databases that ran this migration before #184 used a looser rule (same user
    questions only); the schema_migrations marker keeps it from running again.
    """
    rows = [
        dict(r) for r in _execute(
            conn, "SELECT id, username, title, timestamp, messages FROM conversations",
        ).fetchall()
    ]
    groups: dict = {}
    for r in rows:
        r["thread"] = _thread(r["messages"])
        if r["thread"] is not None:
            groups.setdefault((r["username"].lower(), r["title"].lower()), []).append(r)

    doomed: list[tuple[str, str]] = []
    for group in groups.values():
        group.sort(key=lambda r: (len(r["thread"]), r["timestamp"]), reverse=True)
        kept: list[list[tuple]] = []
        for r in group:
            thread = r["thread"]
            if any(k[: len(thread)] == thread for k in kept):
                doomed.append((r["id"], r["username"]))
            else:
                kept.append(thread)

    for conv_id, username in doomed:
        _execute(conn, "DELETE FROM conversations WHERE id = ? AND username = ?", (conv_id, username))
    logger.info("dedupe: %d legacy duplicate conversations removed", len(doomed))


def _run_once(conn: Any, name: str, migration: Callable[[Any], None]) -> None:
    """Run a data migration exactly once per database, recorded in schema_migrations.

    Data migrations may delete rows, so unlike the idempotent schema checks in
    _migrate they must not re-run on every start-up against newer data (#178).
    Replicas starting together may both run it; the migration must therefore be
    idempotent, and the second marker insert is a no-op.
    """
    if _execute(conn, "SELECT 1 FROM schema_migrations WHERE name = ?", (name,)).fetchone():
        return
    migration(conn)
    _execute(conn, "INSERT INTO schema_migrations (name) VALUES (?) ON CONFLICT (name) DO NOTHING", (name,))
    conn.commit()


def _migrate(conn: Any) -> None:
    if _USE_POSTGRES:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='workbooks' AND column_name='dashboard_spec'
        """)
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE workbooks ADD COLUMN dashboard_spec TEXT")
            conn.commit()

        cursor.execute(
            "SELECT 1 FROM conversations WHERE timestamp > 1000000000000 LIMIT 1"
        )
        if cursor.fetchone():
            cursor.execute(
                "UPDATE conversations SET timestamp = CAST(timestamp / 1000 AS INTEGER) "
                "WHERE timestamp > 1000000000000"
            )
            conn.commit()
        cursor.close()
    else:
        cursor = conn.execute("PRAGMA table_info(workbooks)")
        columns = {row[1] for row in cursor.fetchall()}
        if "dashboard_spec" not in columns:
            conn.execute("ALTER TABLE workbooks ADD COLUMN dashboard_spec TEXT")
            conn.commit()

        has_ms = conn.execute(
            "SELECT 1 FROM conversations WHERE timestamp > 1000000000000 LIMIT 1"
        ).fetchone()
        if has_ms:
            conn.execute(
                "UPDATE conversations SET timestamp = CAST(timestamp / 1000 AS INTEGER) "
                "WHERE timestamp > 1000000000000"
            )
            conn.commit()

    _run_once(conn, "160_dedupe_legacy_conversations", _dedupe_conversations)


def init_db() -> None:
    conn = _connect()
    cursor = conn.cursor()

    if _USE_POSTGRES:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id        TEXT    NOT NULL,
                username  TEXT    NOT NULL,
                title     TEXT    NOT NULL,
                timestamp INTEGER NOT NULL,
                messages  TEXT    NOT NULL,
                PRIMARY KEY (id, username)
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(username, timestamp DESC)"
        )
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workbooks (
                id             TEXT NOT NULL,
                username       TEXT NOT NULL,
                title          TEXT NOT NULL,
                description    TEXT NOT NULL DEFAULT '',
                messages       TEXT,
                figures        TEXT,
                instelling     TEXT,
                html_content   TEXT,
                dashboard_spec TEXT,
                created_at     TEXT NOT NULL,
                PRIMARY KEY (id, username)
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_wb_user ON workbooks(username, created_at DESC)"
        )
        cursor.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY)")
        conn.commit()
        cursor.close()
    else:
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
                id             TEXT NOT NULL,
                username       TEXT NOT NULL,
                title          TEXT NOT NULL,
                description    TEXT NOT NULL DEFAULT '',
                messages       TEXT,
                figures        TEXT,
                instelling     TEXT,
                html_content   TEXT,
                dashboard_spec TEXT,
                created_at     TEXT NOT NULL,
                PRIMARY KEY (id, username)
            );
            CREATE INDEX IF NOT EXISTS idx_wb_user ON workbooks(username, created_at DESC);

            CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY);
        """)

    _migrate(conn)
    conn.close()


def list_conversations(username: str) -> list[dict]:
    conn = _connect()
    rows = _execute(
        conn,
        "SELECT id, title, timestamp, messages FROM conversations "
        "WHERE username = ? ORDER BY timestamp DESC LIMIT ?",
        (username, _MAX_CONVERSATIONS),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _normalize_ts(timestamp: float) -> int:
    """Normalize millisecond timestamps to seconds."""
    if timestamp > 1e12:
        return int(timestamp) // 1000
    return int(timestamp)


def upsert_conversation(
    username: str, conv_id: str, title: str, timestamp: int, messages: list[dict]
) -> None:
    conn = _connect()
    _execute(
        conn,
        "INSERT INTO conversations (id, username, title, timestamp, messages) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT (id, username) DO UPDATE SET title=excluded.title, "
        "timestamp=excluded.timestamp, messages=excluded.messages",
        (conv_id, username, title, _normalize_ts(timestamp), json.dumps(messages)),
    )
    conn.commit()
    conn.close()


def rename_conversation(username: str, conv_id: str, title: str) -> bool:
    """Update only the title. Returns False when the user has no such conversation."""
    conn = _connect()
    cursor = _execute(
        conn,
        "UPDATE conversations SET title = ? WHERE id = ? AND username = ?",
        (title, conv_id, username),
    )
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def delete_conversation(username: str, conv_id: str) -> None:
    conn = _connect()
    _execute(
        conn,
        "DELETE FROM conversations WHERE id = ? AND username = ?",
        (conv_id, username),
    )
    conn.commit()
    conn.close()


def list_workbooks(username: str) -> list[dict]:
    conn = _connect()
    rows = _execute(
        conn,
        "SELECT id, title, description, messages, figures, instelling, "
        "html_content, dashboard_spec, created_at FROM workbooks "
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
    dashboard_spec: dict | None = None,
    created_at: str = "",
) -> None:
    conn = _connect()
    _execute(
        conn,
        "INSERT INTO workbooks (id, username, title, description, messages, figures, "
        "instelling, html_content, dashboard_spec, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (id, username) DO UPDATE SET title=excluded.title, "
        "description=excluded.description, messages=excluded.messages, "
        "figures=excluded.figures, instelling=excluded.instelling, "
        "html_content=excluded.html_content, dashboard_spec=excluded.dashboard_spec, "
        "created_at=excluded.created_at",
        (
            wb_id, username, title, description,
            json.dumps(messages) if messages is not None else None,
            json.dumps(figures) if figures is not None else None,
            instelling, html_content,
            json.dumps(dashboard_spec) if dashboard_spec is not None else None,
            created_at,
        ),
    )
    conn.commit()
    conn.close()


def delete_workbook(username: str, wb_id: str) -> None:
    conn = _connect()
    _execute(
        conn,
        "DELETE FROM workbooks WHERE id = ? AND username = ?",
        (wb_id, username),
    )
    conn.commit()
    conn.close()
