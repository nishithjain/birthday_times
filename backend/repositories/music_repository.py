"""Repository for imported year-level music chart entries."""

from typing import Any, Dict, List, Optional

from backend.database import database_connection, fetch_all, fetch_one


class MusicRepository:
    @staticmethod
    def get_top_tracks(year: int, limit: int = 5) -> List[Dict[str, Any]]:
        rows = fetch_all("SELECT * FROM music_tracks WHERE year = ? ORDER BY rank ASC, title ASC, artist ASC LIMIT ?", (int(year), max(0, int(limit))))
        return [dict(row) for row in rows]

    @staticmethod
    def get_tracks_for_year(year: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM music_tracks WHERE year = ? ORDER BY rank ASC, title ASC, artist ASC"
        params: List[Any] = [int(year)]
        if limit is not None:
            query += " LIMIT ?"
            params.append(max(0, int(limit)))
        return [dict(row) for row in fetch_all(query, params)]

    @staticmethod
    def count_for_year(year: int) -> int:
        return fetch_one("SELECT COUNT(*) AS count FROM music_tracks WHERE year = ?", (int(year),))["count"]

    @staticmethod
    def upsert_track(track: Dict[str, Any]) -> None:
        fields = ["year", "rank", "title", "artist", "chart_name", "chart_country", "source", "source_id", "source_url"]
        values = [track.get(field) for field in fields]
        updates = ", ".join(f"{field} = excluded.{field}" for field in fields[2:])
        with database_connection() as connection:
            connection.execute(f"INSERT INTO music_tracks ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)}) ON CONFLICT(source, year, chart_name, rank) DO UPDATE SET {updates}", values)

    @staticmethod
    def bulk_upsert_tracks(tracks: List[Dict[str, Any]]) -> None:
        with database_connection() as connection:
            for track in tracks:
                fields = ["year", "rank", "title", "artist", "chart_name", "chart_country", "source", "source_id", "source_url"]
                values = [track.get(field) for field in fields]
                updates = ", ".join(f"{field} = excluded.{field}" for field in fields[2:])
                connection.execute(f"INSERT INTO music_tracks ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)}) ON CONFLICT(source, year, chart_name, rank) DO UPDATE SET {updates}", values)