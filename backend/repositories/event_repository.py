# backend/repositories/event_repository.py
"""Event repository for database operations."""

from datetime import date
from typing import List, Optional, Dict, Any
import sqlite3

from backend.database import fetch_all, fetch_one, execute, database_connection
from backend.models.event import HistoricalEvent


class EventRepository:
    """Repository for historical events."""
    
    @staticmethod
    def get_by_date(target_date: date, limit: Optional[int] = None) -> List[HistoricalEvent]:
        """Get events for a specific date, ordered by importance."""
        query = """
            SELECT *
            FROM historical_events
            WHERE event_date = ?
            ORDER BY importance_score DESC, title ASC
        """
        params = [target_date.isoformat()]
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        rows = fetch_all(query, params)
        return [HistoricalEvent.from_db_row(row) for row in rows]

    @staticmethod
    def get_by_year(year: int) -> List[HistoricalEvent]:
        """Get all historical events for a year in stable database order."""
        rows = fetch_all(
            """
            SELECT *
            FROM historical_events
            WHERE event_date >= ? AND event_date < ?
            ORDER BY event_date ASC, importance_score DESC, title ASC,
                     wikidata_id ASC
            """,
            (f"{year:04d}-01-01", f"{year + 1:04d}-01-01"),
        )
        return [HistoricalEvent.from_db_row(row) for row in rows]

    @staticmethod
    def get_events_near_date(
        target_date: date,
        days_before: int = 30,
        days_after: int = 30,
        limit: Optional[int] = None,
    ) -> List[HistoricalEvent]:
        """Return dated events in an inclusive calendar window."""
        start = target_date.fromordinal(target_date.toordinal() - max(0, days_before))
        end = target_date.fromordinal(target_date.toordinal() + max(0, days_after))
        query = """
            SELECT * FROM historical_events
            WHERE event_date BETWEEN ? AND ?
            ORDER BY event_date ASC, importance_score DESC, title ASC, wikidata_id ASC
        """
        params: List[Any] = [start.isoformat(), end.isoformat()]
        if limit is not None:
            query += " LIMIT ?"
            params.append(max(0, int(limit)))
        return [HistoricalEvent.from_db_row(row) for row in fetch_all(query, params)]
    
    @staticmethod
    def get_by_wikidata_id(wikidata_id: str) -> Optional[HistoricalEvent]:
        """Get event by Wikidata ID."""
        row = fetch_one(
            "SELECT * FROM historical_events WHERE wikidata_id = ?",
            (wikidata_id,)
        )
        return HistoricalEvent.from_db_row(row) if row else None
    
    @staticmethod
    def save(events: List[HistoricalEvent]) -> int:
        """Save events to database. Returns number saved."""
        if not events:
            return 0
        
        sql = """
            INSERT INTO historical_events
            (
                event_date, title, description, category, country,
                wikidata_id, source, source_url, wikipedia_url,
                importance_score, date_property, date_property_type
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_date, wikidata_id)
            DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                category = excluded.category,
                country = excluded.country,
                source = excluded.source,
                source_url = excluded.source_url,
                wikipedia_url = excluded.wikipedia_url,
                importance_score = excluded.importance_score,
                date_property = excluded.date_property,
                date_property_type = excluded.date_property_type
        """
        
        with database_connection() as conn:
            for event in events:
                conn.execute(sql, (
                    event.event_date.isoformat(),
                    event.title,
                    event.description,
                    event.category,
                    event.country,
                    event.wikidata_id,
                    event.source,
                    event.source_url,
                    event.wikipedia_url,
                    event.importance_score,
                    event.date_property,
                    event.date_property_type,
                ))
        
        return len(events)
    
    @staticmethod
    def delete_by_date(target_date: date) -> int:
        """Delete all events for a specific date."""
        return execute(
            "DELETE FROM historical_events WHERE event_date = ?",
            (target_date.isoformat(),)
        )
    
    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        """Get database statistics."""
        total = fetch_one("SELECT COUNT(*) AS total FROM historical_events")["total"]
        dates = fetch_one("SELECT COUNT(DISTINCT event_date) AS total FROM historical_events")["total"]
        earliest = fetch_one("SELECT MIN(event_date) AS value FROM historical_events")["value"]
        latest = fetch_one("SELECT MAX(event_date) AS value FROM historical_events")["value"]
        
        return {
            "total_events": total,
            "dates_covered": dates,
            "earliest_date": earliest,
            "latest_date": latest,
        }