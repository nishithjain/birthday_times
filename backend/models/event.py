# backend/models/event.py
"""Historical event model."""

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Optional, List, Dict, Any


@dataclass
class HistoricalEvent:
    """Historical event data model."""
    
    event_date: date
    title: str
    description: Optional[str] = None
    category: str = "historical_event"
    country: Optional[str] = None
    wikidata_id: Optional[str] = None
    source: str = "Wikidata"
    source_url: Optional[str] = None
    wikipedia_url: Optional[str] = None
    importance_score: int = 5
    date_property: Optional[str] = None
    date_property_type: Optional[str] = None
    
    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> "HistoricalEvent":
        """Create from database row."""
        return cls(
            event_date=date.fromisoformat(row["event_date"]),
            title=row["title"],
            description=row["description"],
            category=row["category"],
            country=row["country"],
            wikidata_id=row["wikidata_id"],
            source=row["source"],
            source_url=row["source_url"],
            wikipedia_url=row["wikipedia_url"],
            importance_score=row["importance_score"],
            date_property=row["date_property"],
            date_property_type=row["date_property_type"],
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "event_date": self.event_date.isoformat(),
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "country": self.country,
            "wikidata_id": self.wikidata_id,
            "source": self.source,
            "source_url": self.source_url,
            "wikipedia_url": self.wikipedia_url,
            "importance_score": self.importance_score,
            "date_property_type": self.date_property_type,
        }