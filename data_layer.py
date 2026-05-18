import os

import chainlit as cl
from chainlit.data import get_data_layer
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./chat_history.db"

# Schema compatible with both SQLite and PostgreSQL.
# Covers all fields in Chainlit's StepDict as of 2.11.x.
# When Chainlit adds columns to StepDict, add them here AND to _STEPS_MIGRATIONS.
_DDL = """
CREATE TABLE IF NOT EXISTS users (
    "id"         TEXT PRIMARY KEY,
    "identifier" TEXT NOT NULL UNIQUE,
    "metadata"   TEXT NOT NULL DEFAULT '{}',
    "createdAt"  TEXT
);

CREATE TABLE IF NOT EXISTS threads (
    "id"             TEXT PRIMARY KEY,
    "createdAt"      TEXT,
    "name"           TEXT,
    "userId"         TEXT,
    "userIdentifier" TEXT,
    "tags"           TEXT,
    "metadata"       TEXT,
    FOREIGN KEY ("userId") REFERENCES users("id") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS steps (
    "id"            TEXT    PRIMARY KEY,
    "name"          TEXT    NOT NULL,
    "type"          TEXT    NOT NULL,
    "threadId"      TEXT    NOT NULL,
    "parentId"      TEXT,
    "streaming"     INTEGER NOT NULL DEFAULT 0,
    "waitForAnswer" INTEGER,
    "isError"       INTEGER,
    "metadata"      TEXT,
    "tags"          TEXT,
    "input"         TEXT,
    "output"        TEXT,
    "createdAt"     TEXT,
    "command"       TEXT,
    "start"         TEXT,
    "end"           TEXT,
    "generation"    TEXT,
    "showInput"     TEXT,
    "language"      TEXT,
    "indent"        INTEGER,
    "defaultOpen"   INTEGER,
    "autoCollapse"  INTEGER,
    "modes"         TEXT,
    "icon"          TEXT,
    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS elements (
    "id"          TEXT PRIMARY KEY,
    "threadId"    TEXT,
    "type"        TEXT,
    "url"         TEXT,
    "chainlitKey" TEXT,
    "name"        TEXT NOT NULL,
    "display"     TEXT,
    "objectKey"   TEXT,
    "size"        TEXT,
    "page"        INTEGER,
    "language"    TEXT,
    "forId"       TEXT,
    "mime"        TEXT,
    "props"       TEXT,
    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS feedbacks (
    "id"       TEXT    PRIMARY KEY,
    "forId"    TEXT    NOT NULL,
    "threadId" TEXT    NOT NULL,
    "value"    INTEGER NOT NULL,
    "comment"  TEXT,
    FOREIGN KEY ("threadId") REFERENCES threads("id") ON DELETE CASCADE
);
"""

# Columns absent from the original shipped schema, applied to existing databases.
# New columns must be added both to _DDL above (for fresh installs) and here (for upgrades).
_STEPS_MIGRATIONS: list[tuple[str, str]] = [
    ("autoCollapse", "INTEGER"),
    ("icon", "TEXT"),
]


def build_conninfo(database_url: str) -> str:
    """Add the correct async driver prefix to a database URL if missing."""
    if database_url.startswith("sqlite://") and "+aiosqlite" not in database_url:
        return database_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    if database_url.startswith("postgres://") and "+asyncpg" not in database_url:
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgresql://") and "+asyncpg" not in database_url:
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


def setup() -> None:
    """Register the Chainlit data layer. Call once at app startup."""

    @cl.data_layer
    def get_data_layer_instance() -> SQLAlchemyDataLayer:
        url = build_conninfo(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
        return SQLAlchemyDataLayer(conninfo=url)

    @cl.on_app_startup
    async def on_app_startup() -> None:
        layer = get_data_layer()
        if not isinstance(layer, SQLAlchemyDataLayer):
            return

        async with layer.engine.begin() as conn:
            for stmt in _DDL.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    await conn.execute(text(stmt))

            for col, col_type in _STEPS_MIGRATIONS:
                try:
                    await conn.execute(
                        text(f'ALTER TABLE steps ADD COLUMN "{col}" {col_type}')
                    )
                except OperationalError:
                    pass  # column already exists — safe to skip
