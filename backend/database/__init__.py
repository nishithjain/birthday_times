# backend/database/__init__.py
"""Database package for Birthday Chronicles."""

from .db import (
    get_connection,
    database_connection,
    initialize_database,
    execute,
    fetch_one,
    fetch_all,
)

__all__ = [
    "get_connection",
    "database_connection",
    "initialize_database",
    "execute",
    "fetch_one",
    "fetch_all",
]