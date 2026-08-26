"""Dedicated Around This Time event model."""

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class AroundThisTimeEvent:
    event_date: date
    title: str
    description: str
    category: str = "historical_event"
    external_id: str = ""
    source_name: str = "Wikidata"
    source_url: Optional[str] = None
    wikipedia_url: Optional[str] = None
    date_source: str = "P585"
    date_precision: int = 11
    date_property_type: Optional[str] = None
    sitelink_count: int = 0
    importance_score: int = 5

    @property
    def wikidata_id(self) -> str:
        return self.external_id

    @property
    def source(self) -> str:
        return self.source_name

    @property
    def date_property(self) -> Optional[str]:
        return self.date_source

    @classmethod
    def from_db_row(cls, row: sqlite3.Row) -> "AroundThisTimeEvent":
        return cls(
            event_date=date.fromisoformat(row["event_date"]),
            title=row["title"],
            description=row["description"],
            category=row["category"] or "historical_event",
            external_id=row["external_id"],
            source_name=row["source_name"] or "Wikidata",
            source_url=row["source_url"],
            wikipedia_url=row["wikipedia_url"],
            date_source=row["date_source"],
            date_precision=row["date_precision"],
            date_property_type=row["date_property_type"],
            sitelink_count=row["sitelink_count"] or 0,
            importance_score=row["importance_score"] or 5,
        )