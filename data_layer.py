import os

import chainlit as cl
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./chat_history.db"


def build_conninfo(database_url: str) -> str:
    """Add the correct async driver prefix to a database URL if missing."""
    if database_url.startswith("sqlite://") and "+aiosqlite" not in database_url:
        return database_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    if database_url.startswith("postgres://") and "+asyncpg" not in database_url:
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgresql://") and "+asyncpg" not in database_url:
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


@cl.data_layer
def get_data_layer() -> SQLAlchemyDataLayer:
    url = build_conninfo(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
    return SQLAlchemyDataLayer(conninfo=url)
