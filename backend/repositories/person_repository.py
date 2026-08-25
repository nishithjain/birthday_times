# backend/repositories/person_repository.py
"""Person repository for famous people."""

from datetime import date
from typing import List, Optional, Dict, Any

from backend.database import fetch_all, fetch_one, execute, database_connection
from backend.models.person import FamousPerson


class PersonRepository:
    """Repository for famous people."""
    
    @staticmethod
    def get_by_birthday(month: int, day: int, limit: int = 10) -> List[FamousPerson]:
        """Get famous people born on a specific month/day."""
        query = """
            SELECT *
            FROM famous_people
            WHERE strftime('%m', birth_date) = ? AND strftime('%d', birth_date) = ?
            ORDER BY notability_score DESC, name ASC
            LIMIT ?
        """
        rows = fetch_all(query, (f"{month:02d}", f"{day:02d}", limit))
        return [FamousPerson.from_db_row(row) for row in rows]

    @staticmethod
    def get_by_month_day(month: int, day: int, limit: Optional[int] = None) -> List[FamousPerson]:
        """Get all people matching an exact calendar month and day."""
        if not 1 <= month <= 12 or not 1 <= day <= 31:
            return []
        # Keep the established method as the compatibility seam for callers/tests.
        if limit is not None:
            return PersonRepository.get_by_birthday(month, day, limit=limit)
        rows = fetch_all(
            """
            SELECT *
            FROM famous_people
            WHERE strftime('%m', birth_date) = ? AND strftime('%d', birth_date) = ?
            ORDER BY notability_score DESC, birth_date ASC, name ASC, wikidata_id ASC
            """,
            (f"{month:02d}", f"{day:02d}"),
        )
        return [FamousPerson.from_db_row(row) for row in rows]
    
    @staticmethod
    def get_by_wikidata_id(wikidata_id: str) -> Optional[FamousPerson]:
        """Get person by Wikidata ID."""
        row = fetch_one(
            "SELECT * FROM famous_people WHERE wikidata_id = ?",
            (wikidata_id,)
        )
        return FamousPerson.from_db_row(row) if row else None
    
    @staticmethod
    def save(people: List[FamousPerson]) -> int:
        """Save people to database."""
        if not people:
            return 0
        
        sql = """
            INSERT INTO famous_people
            (
                name, birth_date, death_date, occupation, country,
                description, wikidata_id, wikipedia_url, image_url,
                sitelinks, notability_score, source, source_url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(wikidata_id)
            DO UPDATE SET
                name = excluded.name,
                birth_date = excluded.birth_date,
                death_date = excluded.death_date,
                occupation = excluded.occupation,
                country = excluded.country,
                description = excluded.description,
                wikipedia_url = excluded.wikipedia_url,
                image_url = excluded.image_url,
                sitelinks = excluded.sitelinks,
                notability_score = excluded.notability_score
        """
        
        with database_connection() as conn:
            for person in people:
                conn.execute(sql, (
                    person.name,
                    person.birth_date.isoformat(),
                    person.death_date.isoformat() if person.death_date else None,
                    person.occupation,
                    person.country,
                    person.description,
                    person.wikidata_id,
                    person.wikipedia_url,
                    person.image_url,
                    person.sitelinks,
                    person.notability_score,
                    person.source,
                    person.source_url,
                ))
        
        return len(people)