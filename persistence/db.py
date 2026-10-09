import json
import logging
import os
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MAX_CONVERSATIONS = 15
# A cursor before every conversation, so the first page needs no separate query.
_FIRST_PAGE = (2**62, "")
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


def _is_legacy_id(conv_id: str) -> bool:
    """Pre-#69 ids were Date.now(): 13 digits. Since then a conversation gets a UUID."""
    return len(conv_id) == 13 and conv_id.isdigit()


def _dedupe_conversations(conn: Any) -> None:
    """Remove pre-#69 duplicate conversations: snapshots of one growing thread.

    Before #69 every save got a new id (#151), so one conversation was stored
    once per save, also when nothing had changed. A row is such a snapshot only
    when it has a legacy id and its messages, role and content, are the start of
    (or equal to) another row of the same user and title (case-insensitive).
    Anything less is no proof: a UUID row is never a snapshot, so two separate
    conversations with the same content both stay (#198); neither do two that
    open with the same question but got another answer (#178, #184), nor a row
    whose messages cannot be read. The richest row wins, tie-break on the newest
    timestamp.

    Databases that ran this migration before #184 used a looser rule (same user
    questions only); the schema_migrations marker keeps it from running again.
    """
    rows = [
        dict(r)
        for r in _execute(
            conn,
            "SELECT id, username, title, timestamp, messages FROM conversations",
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
            if _is_legacy_id(str(r["id"])) and any(k[: len(thread)] == thread for k in kept):
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

        cursor.execute("SELECT 1 FROM conversations WHERE timestamp > 1000000000000 LIMIT 1")
        if cursor.fetchone():
            cursor.execute(
                "UPDATE conversations SET timestamp = CAST(timestamp / 1000 AS INTEGER) WHERE timestamp > 1000000000000"
            )
            conn.commit()
        cursor.close()
    else:
        cursor = conn.execute("PRAGMA table_info(workbooks)")
        columns = {row[1] for row in cursor.fetchall()}
        if "dashboard_spec" not in columns:
            conn.execute("ALTER TABLE workbooks ADD COLUMN dashboard_spec TEXT")
            conn.commit()

        has_ms = conn.execute("SELECT 1 FROM conversations WHERE timestamp > 1000000000000 LIMIT 1").fetchone()
        if has_ms:
            conn.execute(
                "UPDATE conversations SET timestamp = CAST(timestamp / 1000 AS INTEGER) WHERE timestamp > 1000000000000"
            )
            conn.commit()

    _run_once(conn, "160_dedupe_legacy_conversations", _dedupe_conversations)


# Eén rij per inzending; answers is JSON {vraag-id: antwoord} (zie core/feedback.py).
_FEEDBACK_TABLE = """
    CREATE TABLE IF NOT EXISTS feedback (
        id           TEXT PRIMARY KEY,
        username     TEXT NOT NULL,
        workbook_id  TEXT NOT NULL,
        report_type  TEXT NOT NULL,
        report_title TEXT NOT NULL DEFAULT '',
        answers      TEXT NOT NULL,
        created_at   TEXT NOT NULL
    )
"""


# Eén oordeel per antwoord; een nieuw oordeel vervangt het oude (#248). trace is
# JSON uit het opgeslagen gesprek (core/answer_feedback.py), zodat de melding
# reproduceerbaar blijft als het gesprek later verandert of verdwijnt.
_ANSWER_FEEDBACK_TABLE = """
    CREATE TABLE IF NOT EXISTS answer_feedback (
        username        TEXT    NOT NULL,
        conversation_id TEXT    NOT NULL,
        message_index   INTEGER NOT NULL,
        oordeel         TEXT    NOT NULL,
        toelichting     TEXT    NOT NULL DEFAULT '',
        trace           TEXT    NOT NULL,
        created_at      TEXT    NOT NULL,
        PRIMARY KEY (username, conversation_id, message_index)
    )
"""


# Hoe een data-key van een gesprek ontstond, zodat hij een herstart overleeft (#472).
# recipe is JSON: {laad: [tool, args]} of {afgeleid_van, tool, args, stap}; nooit een script.
_DATA_RECIPES_TABLE = """
    CREATE TABLE IF NOT EXISTS data_recipes (
        username   TEXT NOT NULL,
        conv_id    TEXT NOT NULL,
        data_key   TEXT NOT NULL,
        recipe     TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (username, conv_id, data_key)
    )
"""
_DATA_RECIPES_INDEX = "CREATE INDEX IF NOT EXISTS idx_recipes_key ON data_recipes(username, data_key, created_at DESC)"


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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(username, timestamp DESC)")
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
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wb_user ON workbooks(username, created_at DESC)")
        cursor.execute(_FEEDBACK_TABLE)
        cursor.execute(_ANSWER_FEEDBACK_TABLE)
        cursor.execute(_DATA_RECIPES_TABLE)
        cursor.execute(_DATA_RECIPES_INDEX)
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
        conn.execute(_FEEDBACK_TABLE)
        conn.execute(_ANSWER_FEEDBACK_TABLE)
        conn.execute(_DATA_RECIPES_TABLE)
        conn.execute(_DATA_RECIPES_INDEX)

    _migrate(conn)
    conn.close()


def list_conversations(
    username: str, before: tuple[int, str] | None = None, limit: int = _MAX_CONVERSATIONS
) -> list[dict]:
    """Newest first, one page at a time (#123).

    The next page starts after `before`, the (timestamp, id) of the last
    conversation on the previous one; id breaks ties between equal timestamps.
    """
    ts, conv_id = before or _FIRST_PAGE
    conn = _connect()
    rows = _execute(
        conn,
        "SELECT id, title, timestamp, messages FROM conversations "
        "WHERE username = ? AND (timestamp < ? OR (timestamp = ? AND id < ?)) "
        "ORDER BY timestamp DESC, id DESC LIMIT ?",
        (username, ts, ts, conv_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_conversations(username: str, query: str, limit: int = _MAX_CONVERSATIONS) -> list[dict]:
    """Conversations whose title or message text contains `query`, newest first (#124).

    Matched in Python on the parsed messages, not with LIKE on the stored JSON:
    that JSON escapes non-ASCII ("é" is stored as "\\u00e9") and would
    match its own keys ("role", "content").
    """
    needle = query.casefold()
    conn = _connect()
    rows = _execute(
        conn,
        "SELECT id, title, timestamp, messages FROM conversations WHERE username = ? ORDER BY timestamp DESC, id DESC",
        (username,),
    ).fetchall()
    conn.close()
    hits = [dict(r) for r in rows if _contains(dict(r), needle)]
    return hits[:limit]


def _contains(row: dict, needle: str) -> bool:
    if needle in (row.get("title") or "").casefold():
        return True
    try:
        messages = json.loads(row.get("messages") or "[]")
    except ValueError:
        return False
    return any(
        isinstance(m, dict) and isinstance(m.get("content"), str) and needle in m["content"].casefold()
        for m in messages
    )


def _normalize_ts(timestamp: float) -> int:
    """Normalize millisecond timestamps to seconds."""
    if timestamp > 1e12:
        return int(timestamp) // 1000
    return int(timestamp)


def upsert_conversation(username: str, conv_id: str, title: str, timestamp: int, messages: list[dict]) -> None:
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
    _execute(conn, "DELETE FROM data_recipes WHERE conv_id = ? AND username = ?", (conv_id, username))
    conn.commit()
    conn.close()


def save_recipes(username: str, conv_id: str, recipes: dict[str, dict]) -> None:
    """Bewaar per data-key van een gesprek zijn recept; een bestaand recept wordt bijgewerkt (#472)."""
    if not recipes:
        return
    now = datetime.now(UTC).isoformat(timespec="seconds")
    conn = _connect()
    for key, recipe in recipes.items():
        _execute(
            conn,
            "INSERT INTO data_recipes (username, conv_id, data_key, recipe, created_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (username, conv_id, data_key) DO UPDATE SET recipe=excluded.recipe",
            (username, conv_id, key, json.dumps(recipe, ensure_ascii=False, default=str), now),
        )
    conn.commit()
    conn.close()


def recipes_for(username: str, conv_id: str) -> dict[str, dict]:
    """De recepten van een eigen gesprek, per data-key."""
    conn = _connect()
    rows = _execute(
        conn,
        "SELECT data_key, recipe FROM data_recipes WHERE username = ? AND conv_id = ?",
        (username, conv_id),
    ).fetchall()
    conn.close()
    return {r["data_key"]: json.loads(r["recipe"]) for r in rows}


def recipe_for_key(username: str, key: str) -> dict | None:
    """Het nieuwste recept van deze gebruiker voor `key`, over al zijn gesprekken; nooit dat van een ander."""
    conn = _connect()
    row = _execute(
        conn,
        "SELECT recipe FROM data_recipes WHERE username = ? AND data_key = ? ORDER BY created_at DESC LIMIT 1",
        (username, key),
    ).fetchone()
    conn.close()
    return json.loads(row["recipe"]) if row else None


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
            wb_id,
            username,
            title,
            description,
            json.dumps(messages) if messages is not None else None,
            json.dumps(figures) if figures is not None else None,
            instelling,
            html_content,
            json.dumps(dashboard_spec) if dashboard_spec is not None else None,
            created_at,
        ),
    )
    conn.commit()
    conn.close()


def workbook_belongs_to(username: str, wb_id: str) -> bool:
    conn = _connect()
    row = _execute(
        conn,
        "SELECT 1 FROM workbooks WHERE id = ? AND username = ?",
        (wb_id, username),
    ).fetchone()
    conn.close()
    return row is not None


def delete_workbook(username: str, wb_id: str) -> None:
    conn = _connect()
    _execute(
        conn,
        "DELETE FROM workbooks WHERE id = ? AND username = ?",
        (wb_id, username),
    )
    conn.commit()
    conn.close()


def add_feedback(
    username: str,
    workbook_id: str,
    report_type: str,
    report_title: str,
    answers: dict[str, str],
) -> None:
    conn = _connect()
    _execute(
        conn,
        "INSERT INTO feedback (id, username, workbook_id, report_type, report_title, answers, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            str(uuid.uuid4()),
            username,
            workbook_id,
            report_type,
            report_title,
            json.dumps(answers),
            datetime.now(UTC).isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    conn.close()


def list_feedback_workbooks(username: str) -> list[str]:
    conn = _connect()
    rows = _execute(
        conn,
        "SELECT DISTINCT workbook_id FROM feedback WHERE username = ? ORDER BY workbook_id",
        (username,),
    ).fetchall()
    conn.close()
    return [r["workbook_id"] for r in rows]


def conversation_messages(username: str, conv_id: str) -> list[dict] | None:
    """De berichten van een eigen gesprek; None als deze gebruiker het niet heeft."""
    conn = _connect()
    row = _execute(
        conn,
        "SELECT messages FROM conversations WHERE id = ? AND username = ?",
        (conv_id, username),
    ).fetchone()
    conn.close()
    return json.loads(row["messages"]) if row else None


def upsert_answer_feedback(
    username: str, conv_id: str, message_index: int, oordeel: str, toelichting: str, trace: dict
) -> None:
    conn = _connect()
    _execute(
        conn,
        "INSERT INTO answer_feedback "
        "(username, conversation_id, message_index, oordeel, toelichting, trace, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (username, conversation_id, message_index) DO UPDATE SET "
        "oordeel=excluded.oordeel, toelichting=excluded.toelichting, trace=excluded.trace, "
        "created_at=excluded.created_at",
        (
            username,
            conv_id,
            message_index,
            oordeel,
            toelichting,
            json.dumps(trace, ensure_ascii=False),
            datetime.now(UTC).isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    conn.close()


def answer_feedback_for(username: str, conv_id: str) -> dict[int, str]:
    """Het oordeel per antwoord in een eigen gesprek, om de knoppen na heropenen te tonen."""
    conn = _connect()
    rows = _execute(
        conn,
        "SELECT message_index, oordeel FROM answer_feedback WHERE username = ? AND conversation_id = ?",
        (username, conv_id),
    ).fetchall()
    conn.close()
    return {r["message_index"]: r["oordeel"] for r in rows}


def all_answer_feedback() -> list[dict]:
    """Alle meldingen, nieuwste eerst: de lijst voor het team."""
    conn = _connect()
    rows = _execute(conn, "SELECT * FROM answer_feedback ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]
