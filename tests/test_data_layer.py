from data_layer import build_conninfo


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
    from data_layer import DEFAULT_DATABASE_URL
    assert DEFAULT_DATABASE_URL.startswith("sqlite")
