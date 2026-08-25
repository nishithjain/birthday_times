# backend/models/person.py
"""Famous person model."""

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class FamousPerson:
    """Famous person data model."""
    
    name: str
    birth_date: date
    death_date: Optional[date] = None
    occupation: Optional[str] = None
    country: Optional[str] = None
    description: Optional[str] = None
    wikidata_id: Optional[str] = None
    wikipedia_url: Optional[str] = None
    image_url: Optional[str] = None
    sitelinks: int = 0
    notability_score: int = 5
    source: str = "Wikidata"
    source_url: Optional[str] = None
    
    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> "FamousPerson":
        """Create from database row."""
        return cls(
            name=row["name"],
            birth_date=date.fromisoformat(row["birth_date"]),
            death_date=date.fromisoformat(row["death_date"]) if row["death_date"] else None,
            occupation=row["occupation"],
            country=row["country"],
            description=row["description"],
            wikidata_id=row["wikidata_id"],
            wikipedia_url=row["wikipedia_url"],
            image_url=row["image_url"],
            sitelinks=row["sitelinks"] or 0,
            notability_score=row["notability_score"] or 5,
            source=row["source"],
            source_url=row["source_url"],
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "birth_date": self.birth_date.isoformat(),
            "death_date": self.death_date.isoformat() if self.death_date else None,
            "occupation": self.occupation,
            "country": self.country,
            "description": self.description,
            "wikidata_id": self.wikidata_id,
            "wikipedia_url": self.wikipedia_url,
            "image_url": self.image_url,
            "notability_score": self.notability_score,
        }