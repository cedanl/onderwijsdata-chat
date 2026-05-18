import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from data_layer import DEFAULT_DATABASE_URL, _DDL, build_conninfo

_REQUIRED_TABLES = {"users", "threads", "steps", "elements", "feedbacks"}
_REQUIRED_STEP_COLS = {"autoCollapse", "icon", "defaultOpen", "modes", "command"}


def test_sqlite_url_gets_aiosqlite_driver():
    result = build_conninfo("sqlite:///./chat_history.db")
    assert result == "sqlite+aiosqlite:///./chat_history.db"


def test_sqlite_absolute_path():
    result = build_conninfo("sqlite:////tmp/chat.db")
    assert result == "sqlite+aiosqlite:////tmp/chat.db"


def test_sqlite_already_has_aiosqlite_unchanged():
    url = "sqlite+aiosqlite:///./chat_history.db"
    assert build_conninfo(url) == url


def test_postgresql_url_gets_asyncpg_driver():
    result = build_conninfo("postgresql://user:pass@localhost/db")
    assert result == "postgresql+asyncpg://user:pass@localhost/db"


def test_postgres_shorthand_gets_asyncpg():
    result = build_conninfo("postgres://user:pass@localhost/db")
    assert result == "postgresql+asyncpg://user:pass@localhost/db"


def test_postgresql_already_has_asyncpg_unchanged():
    url = "postgresql+asyncpg://user:pass@localhost/db"
    assert build_conninfo(url) == url


def test_default_url_is_sqlite():
    assert DEFAULT_DATABASE_URL.startswith("sqlite")


async def _apply_ddl(engine):
    async with engine.begin() as conn:
        for stmt in _DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                await conn.execute(text(stmt))


@pytest.mark.asyncio
async def test_create_tables_creates_all_required_tables():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _apply_ddl(engine)

    async with engine.connect() as conn:
        tables = await conn.run_sync(
            lambda c: set(inspect(c).get_table_names())
        )

    assert tables == _REQUIRED_TABLES
    await engine.dispose()


@pytest.mark.asyncio
async def test_steps_table_has_required_columns():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await _apply_ddl(engine)

    async with engine.connect() as conn:
        cols = await conn.run_sync(
            lambda c: {col["name"] for col in inspect(c).get_columns("steps")}
        )

    assert _REQUIRED_STEP_COLS <= cols
    await engine.dispose()
