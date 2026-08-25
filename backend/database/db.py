# backend/database/db.py (Updated)
"""
Database helper for Birthday Chronicles.

Provides connection management, query execution, and database initialization.
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, Any, Dict, List, Tuple, Union

from backend.config import config


# ============================================================
# Paths
# ============================================================

DATABASE_PATH = config.database_path
SCHEMA_PATH = config.schema_path


# ============================================================
# Database Connection
# ============================================================

def get_connection() -> sqlite3.Connection:
    """
    Create and return an SQLite connection.
    
    Rows can be accessed by column name:
        row["title"]
        row["event_date"]
    """
    config.ensure_database_dir()
    
    connection = sqlite3.connect(str(DATABASE_PATH))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    
    return connection


@contextmanager
def database_connection() -> sqlite3.Connection:
    """Safely open and close a database connection with transaction management."""
    connection = get_connection()
    
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


# ============================================================
# Initialize Database
# ============================================================

def initialize_database() -> None:
    """Create all tables, indexes, triggers, and views from schema.sql."""
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"schema.sql not found at: {SCHEMA_PATH}")
    
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    
    with database_connection() as connection:
        existing_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'historical_weather'"
        ).fetchone()
        if existing_table:
            existing_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(historical_weather)")
            }
            additive_columns = {
                "location_id": "INTEGER",
                "source_dataset": "TEXT",
                "source_latitude": "REAL",
                "source_longitude": "REAL",
            }
            for column, definition in additive_columns.items():
                if column not in existing_columns:
                    connection.execute(f"ALTER TABLE historical_weather ADD COLUMN {column} {definition}")
        location_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'weather_locations'"
        ).fetchone()
        if location_table:
            location_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(weather_locations)")
            }
            if "major_city_rank" not in location_columns:
                connection.execute("ALTER TABLE weather_locations ADD COLUMN major_city_rank INTEGER")
        movie_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'movies'"
        ).fetchone()
        if movie_table:
            movie_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(movies)")
            }
            for column in ("source_id", "director", "lead_actor"):
                if column not in movie_columns:
                    connection.execute(f"ALTER TABLE movies ADD COLUMN {column} TEXT")
        connection.executescript(schema_sql)


# ============================================================
# Generic Query Helpers
# ============================================================

def execute(query: str, params: Union[Tuple, Dict, List] = ()) -> int:
    """Execute INSERT, UPDATE, or DELETE. Returns number of affected rows."""
    with database_connection() as connection:
        cursor = connection.execute(query, params)
        return cursor.rowcount


def fetch_one(query: str, params: Union[Tuple, Dict, List] = ()) -> Optional[sqlite3.Row]:
    """Execute SELECT and return one row."""
    with database_connection() as connection:
        cursor = connection.execute(query, params)
        return cursor.fetchone()


def fetch_all(query: str, params: Union[Tuple, Dict, List] = ()) -> List[sqlite3.Row]:
    """Execute SELECT and return all rows."""
    with database_connection() as connection:
        cursor = connection.execute(query, params)
        return cursor.fetchall()