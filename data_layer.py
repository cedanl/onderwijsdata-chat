"""
Minimale SQLite-gebaseerde Chainlit data layer.
Levert: sidebar met gespreksgeschiedenis + hervatten van eerdere chats.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from chainlit.data.base import BaseDataLayer
from chainlit.step import StepDict
from chainlit.types import (
    Feedback,
    PageInfo,
    PaginatedResponse,
    Pagination,
    ThreadDict,
    ThreadFilter,
)
from chainlit.user import PersistedUser, User

_DB = Path("data/sessions.db")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conn() -> sqlite3.Connection:
    _DB.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id          TEXT PRIMARY KEY,
                identifier  TEXT NOT NULL UNIQUE,
                created_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS threads (
                id          TEXT PRIMARY KEY,
                name        TEXT,
                created_at  TEXT NOT NULL,
                metadata    TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS steps (
                id          TEXT PRIMARY KEY,
                thread_id   TEXT NOT NULL,
                type        TEXT NOT NULL DEFAULT 'undefined',
                name        TEXT,
                input       TEXT,
                output      TEXT,
                created_at  TEXT NOT NULL,
                is_error    INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(thread_id) REFERENCES threads(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_steps_thread ON steps(thread_id);
        """)


def _row_to_step(row: sqlite3.Row) -> StepDict:
    return StepDict(
        id=row["id"],
        threadId=row["thread_id"],
        type=row["type"],
        name=row["name"] or "",
        input=row["input"] or "",
        output=row["output"] or "",
        createdAt=row["created_at"],
        isError=bool(row["is_error"]),
        streaming=False,
        metadata={},
    )


def _row_to_thread(row: sqlite3.Row, steps: List[StepDict] | None = None) -> ThreadDict:
    return ThreadDict(
        id=row["id"],
        createdAt=row["created_at"],
        name=row["name"],
        userId=None,
        userIdentifier=None,
        tags=None,
        metadata=json.loads(row["metadata"] or "{}"),
        steps=steps or [],
        elements=[],
    )


class SQLiteDataLayer(BaseDataLayer):

    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        with _conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE identifier=?", (identifier,)
            ).fetchone()
        if row:
            return PersistedUser(id=row["id"], identifier=row["identifier"], createdAt=row["created_at"])
        return None

    async def create_user(self, user: User) -> Optional[PersistedUser]:
        uid = user.identifier
        ts = _now()
        with _conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users(id, identifier, created_at) VALUES(?,?,?)",
                (uid, uid, ts),
            )
            row = conn.execute(
                "SELECT created_at FROM users WHERE identifier=?", (uid,)
            ).fetchone()
        return PersistedUser(id=uid, identifier=uid, createdAt=row["created_at"])

    async def delete_feedback(self, feedback_id: str) -> bool:
        return True

    async def upsert_feedback(self, feedback: Feedback) -> str:
        return ""

    async def get_thread_author(self, thread_id: str) -> str:
        return "anonymous"

    async def list_threads(
        self, pagination: Pagination, filters: ThreadFilter
    ) -> PaginatedResponse[ThreadDict]:
        limit = pagination.first or 20
        cursor_ts = pagination.cursor or "9999-99-99"

        search = f"%{filters.search}%" if filters.search else None

        with _conn() as conn:
            if search:
                rows = conn.execute(
                    """SELECT * FROM threads
                       WHERE created_at < ? AND name LIKE ?
                       ORDER BY created_at DESC LIMIT ?""",
                    (cursor_ts, search, limit + 1),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM threads
                       WHERE created_at < ?
                       ORDER BY created_at DESC LIMIT ?""",
                    (cursor_ts, limit + 1),
                ).fetchall()

        has_next = len(rows) > limit
        rows = rows[:limit]
        threads = [_row_to_thread(r) for r in rows]

        end_cursor = rows[-1]["created_at"] if rows else None
        return PaginatedResponse(
            pageInfo=PageInfo(
                hasNextPage=has_next,
                startCursor=rows[0]["created_at"] if rows else None,
                endCursor=end_cursor,
            ),
            data=threads,
        )

    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        with _conn() as conn:
            t = conn.execute(
                "SELECT * FROM threads WHERE id=?", (thread_id,)
            ).fetchone()
            if not t:
                return None
            step_rows = conn.execute(
                "SELECT * FROM steps WHERE thread_id=? ORDER BY created_at",
                (thread_id,),
            ).fetchall()

        steps = [_row_to_step(r) for r in step_rows]
        return _row_to_thread(t, steps)

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        with _conn() as conn:
            exists = conn.execute(
                "SELECT id FROM threads WHERE id=?", (thread_id,)
            ).fetchone()
            if exists:
                if name is not None:
                    conn.execute(
                        "UPDATE threads SET name=? WHERE id=?", (name, thread_id)
                    )
                if metadata is not None:
                    conn.execute(
                        "UPDATE threads SET metadata=? WHERE id=?",
                        (json.dumps(metadata, ensure_ascii=False, default=str), thread_id),
                    )
            else:
                conn.execute(
                    "INSERT INTO threads(id, name, created_at, metadata) VALUES(?,?,?,?)",
                    (
                        thread_id,
                        name,
                        _now(),
                        json.dumps(metadata or {}, ensure_ascii=False, default=str),
                    ),
                )

    async def delete_thread(self, thread_id: str) -> bool:
        with _conn() as conn:
            conn.execute("DELETE FROM threads WHERE id=?", (thread_id,))
        return True

    async def create_step(self, step_dict: StepDict) -> None:
        with _conn() as conn:
            # Ensure parent thread exists
            conn.execute(
                "INSERT OR IGNORE INTO threads(id, name, created_at) VALUES(?,?,?)",
                (step_dict.get("threadId"), None, _now()),
            )
            conn.execute(
                """INSERT OR REPLACE INTO steps
                   (id, thread_id, type, name, input, output, created_at, is_error)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (
                    step_dict.get("id"),
                    step_dict.get("threadId"),
                    step_dict.get("type", "undefined"),
                    step_dict.get("name", ""),
                    step_dict.get("input", ""),
                    step_dict.get("output", ""),
                    step_dict.get("createdAt") or _now(),
                    int(bool(step_dict.get("isError", False))),
                ),
            )

    async def update_step(self, step_dict: StepDict) -> None:
        await self.create_step(step_dict)

    async def delete_step(self, step_id: str) -> bool:
        with _conn() as conn:
            conn.execute("DELETE FROM steps WHERE id=?", (step_id,))
        return True

    async def create_element(self, element) -> None:
        pass

    async def get_element(self, thread_id: str, element_id: str):
        return None

    async def delete_element(self, element_id: str, thread_id: Optional[str] = None) -> bool:
        return True

    async def get_favorite_steps(self, thread_id: str) -> List[StepDict]:
        return []

    async def set_step_favorite(self, step_id: str, is_favorite: bool) -> None:
        pass

    async def build_debug_url(self) -> str:
        return ""

    async def close(self) -> None:
        pass
