"""Repository for the dedicated Around This Time event table."""

from datetime import date
from typing import Any, Dict, Iterable, List, Optional

from backend.database import database_connection, fetch_all, fetch_one
from backend.models.around_this_time_event import AroundThisTimeEvent


class AroundThisTimeRepository:
    @staticmethod
    def clear() -> int:
        """Delete all dedicated Around This Time records and return the count."""
        with database_connection() as connection:
            count = connection.execute("SELECT COUNT(*) FROM around_this_time_events").fetchone()[0]
            connection.execute("DELETE FROM around_this_time_events")
        return int(count)

    @staticmethod
    def get_between_dates(
        start_date: date,
        end_date: date,
        limit: Optional[int] = None,
        exclude_external_ids: Optional[Iterable[str]] = None,
    ) -> List[AroundThisTimeEvent]:
        """Return events in an inclusive ISO-date range, in stable order."""
        query = """
            SELECT * FROM around_this_time_events
            WHERE event_date >= ? AND event_date <= ?
        """
        params: List[Any] = [start_date.isoformat(), end_date.isoformat()]
        exclusions = sorted({str(value) for value in (exclude_external_ids or []) if value})
        if exclusions:
            placeholders = ",".join("?" for _ in exclusions)
            query += f" AND external_id NOT IN ({placeholders})"
            params.extend(exclusions)
        query += " ORDER BY event_date ASC, importance_score DESC, id ASC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(max(0, int(limit)))
        return [AroundThisTimeEvent.from_db_row(row) for row in fetch_all(query, params)]

    @staticmethod
    def get_events_near_date(
        target_date: date,
        days_before: int = 30,
        days_after: int = 30,
        limit: Optional[int] = None,
        excluded_ids: Optional[Iterable[str]] = None,
    ) -> List[AroundThisTimeEvent]:
        start = date.fromordinal(target_date.toordinal() - max(0, days_before))
        end = date.fromordinal(target_date.toordinal() + max(0, days_after))
        return AroundThisTimeRepository.get_between_dates(
            start, end, limit=limit, exclude_external_ids=excluded_ids
        )

    @staticmethod
    def get_by_date(target_date: date, limit: Optional[int] = None) -> List[AroundThisTimeEvent]:
        return AroundThisTimeRepository.get_events_near_date(target_date, 0, 0, limit=limit)

    @staticmethod
    def save(events: List[AroundThisTimeEvent]) -> Dict[str, int]:
        if not events:
            return {"inserted": 0, "updated": 0, "skipped": 0}
        sql = """
            INSERT INTO around_this_time_events
            (event_date, title, description, category, external_id, source_name,
             source_url, wikipedia_url, date_source, date_precision,
             date_property_type, sitelink_count, importance_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(external_id, event_date) DO UPDATE SET
                title = CASE WHEN length(excluded.title) > length(around_this_time_events.title)
                             THEN excluded.title ELSE around_this_time_events.title END,
                description = CASE WHEN length(excluded.description) > length(around_this_time_events.description)
                                   THEN excluded.description ELSE around_this_time_events.description END,
                category = CASE WHEN excluded.category <> 'unknown' THEN excluded.category ELSE around_this_time_events.category END,
                source_url = COALESCE(excluded.source_url, around_this_time_events.source_url),
                wikipedia_url = COALESCE(excluded.wikipedia_url, around_this_time_events.wikipedia_url),
                date_source = CASE WHEN excluded.date_source = 'P585' OR around_this_time_events.date_source IS NULL
                                   THEN excluded.date_source ELSE around_this_time_events.date_source END,
                date_precision = MIN(around_this_time_events.date_precision, excluded.date_precision),
                date_property_type = COALESCE(excluded.date_property_type, around_this_time_events.date_property_type),
                sitelink_count = MAX(around_this_time_events.sitelink_count, excluded.sitelink_count),
                importance_score = MAX(around_this_time_events.importance_score, excluded.importance_score),
                updated_at = CURRENT_TIMESTAMP
        """
        with database_connection() as connection:
            before = connection.execute("SELECT COUNT(*) FROM around_this_time_events").fetchone()[0]
            for event in events:
                connection.execute(sql, (
                    event.event_date.isoformat(), event.title, event.description,
                    event.category, event.external_id, event.source_name,
                    event.source_url, event.wikipedia_url, event.date_source,
                    event.date_precision, event.date_property_type, event.sitelink_count,
                    event.importance_score,
                ))
            after = connection.execute("SELECT COUNT(*) FROM around_this_time_events").fetchone()[0]
        inserted = max(0, after - before)
        return {"inserted": inserted, "updated": len(events) - inserted, "skipped": 0}

    @staticmethod
    def count() -> int:
        row = fetch_one("SELECT COUNT(*) AS count FROM around_this_time_events")
        return int(row["count"])

    @staticmethod
    def count_unique_dates() -> int:
        row = fetch_one("SELECT COUNT(DISTINCT event_date) AS count FROM around_this_time_events")
        return int(row["count"])