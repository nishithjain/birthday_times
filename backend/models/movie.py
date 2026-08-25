# backend/models/movie.py
"""Movie model."""

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Movie:
    """Movie data model."""
    
    title: str
    release_date: Optional[date] = None
    country: Optional[str] = None
    genres: Optional[str] = None
    overview: Optional[str] = None
    poster_url: Optional[str] = None
    tmdb_id: Optional[int] = None
    imdb_id: Optional[str] = None
    popularity: Optional[float] = None
    vote_average: Optional[float] = None
    vote_count: Optional[int] = None
    source: str = "TMDB"
    source_url: Optional[str] = None
    id: Optional[int] = None
    source_id: Optional[str] = None
    director: Optional[str] = None
    lead_actor: Optional[str] = None
    
    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> "Movie":
        """Create from database row."""
        return cls(
            title=row["title"],
            release_date=date.fromisoformat(row["release_date"]) if row["release_date"] else None,
            country=row["country"],
            genres=row["genres"],
            overview=row["overview"],
            poster_url=row["poster_url"],
            tmdb_id=row["tmdb_id"],
            imdb_id=row["imdb_id"],
            popularity=row["popularity"],
            vote_average=row["vote_average"],
            vote_count=row["vote_count"],
            source=row["source"],
            source_url=row["source_url"],
            id=row["id"] if "id" in row.keys() else None,
            source_id=row["source_id"] if "source_id" in row.keys() else None,
            director=row["director"] if "director" in row.keys() else None,
            lead_actor=row["lead_actor"] if "lead_actor" in row.keys() else None,
        )