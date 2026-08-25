# backend/repositories/movie_repository.py
"""Movie repository."""

from datetime import date
from typing import List, Optional

from backend.database import fetch_all, database_connection
from backend.models.movie import Movie


class MovieRepository:
    """Repository for movies."""
    
    @staticmethod
    def get_by_year(year: int, limit: Optional[int] = 10) -> List[Movie]:
        """Get movies from a specific year."""
        query = """
            SELECT *
            FROM movies
            WHERE strftime('%Y', release_date) = ?
            ORDER BY popularity DESC NULLS LAST, vote_average DESC NULLS LAST
        """
        params = [str(year)]
        if limit is not None:
            query += " LIMIT ?"
            params.append(max(0, int(limit)))
        rows = fetch_all(query, params)
        return [Movie.from_db_row(row) for row in rows]
    
    @staticmethod
    def get_by_date(target_date: date, limit: int = 5) -> List[Movie]:
        """Get movies released around a specific date."""
        # Get movies from the same month
        query = """
            SELECT *
            FROM movies
            WHERE strftime('%m', release_date) = ?
            ORDER BY popularity DESC NULLS LAST, vote_average DESC NULLS LAST
            LIMIT ?
        """
        rows = fetch_all(query, (f"{target_date.month:02d}", limit))
        return [Movie.from_db_row(row) for row in rows]

    @staticmethod
    def get_movies_for_year(year: int, limit: Optional[int] = None) -> List[Movie]:
        """Return all available movies for a year in stable prominence order."""
        return MovieRepository.get_by_year(year, limit=limit)

    @staticmethod
    def count_for_year(year: int) -> int:
        rows = MovieRepository.get_movies_for_year(year)
        return len(rows)

    @staticmethod
    def upsert(movie: Movie) -> str:
        """Insert or update a normalized movie using its stable source ID."""
        with database_connection() as connection:
            if movie.tmdb_id is not None:
                existing = connection.execute("SELECT id FROM movies WHERE tmdb_id = ?", (movie.tmdb_id,)).fetchone()
            elif movie.source_id:
                existing = connection.execute("SELECT id FROM movies WHERE source = ? AND source_id = ?", (movie.source, movie.source_id)).fetchone()
            else:
                existing = connection.execute(
                    "SELECT id FROM movies WHERE title = ? AND release_date = ? AND source = ?",
                    (movie.title, movie.release_date.isoformat() if movie.release_date else None, movie.source),
                ).fetchone()
            fields = (movie.title, movie.release_date.isoformat() if movie.release_date else None, movie.country, movie.genres, movie.overview, movie.poster_url, movie.tmdb_id, movie.imdb_id, movie.source_id, movie.director, movie.lead_actor, movie.popularity, movie.vote_average, movie.vote_count, movie.source, movie.source_url)
            if existing:
                connection.execute("UPDATE movies SET title=?, release_date=?, country=?, genres=?, overview=?, poster_url=?, tmdb_id=?, imdb_id=?, source_id=?, director=?, lead_actor=?, popularity=?, vote_average=?, vote_count=?, source=?, source_url=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (*fields, existing["id"]))
                return "updated"
            connection.execute("INSERT INTO movies (title, release_date, country, genres, overview, poster_url, tmdb_id, imdb_id, source_id, director, lead_actor, popularity, vote_average, vote_count, source, source_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", fields)
            return "inserted"