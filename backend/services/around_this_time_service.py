"""Offline nearby historical-event selection for the Around This Time article."""

import re
from datetime import date
from typing import Any, Dict, Iterable, Optional

from backend.repositories.event_repository import EventRepository
from backend.services.accuracy import EXACT_DATE, NEAR_DATE
from backend.services.illustration_service import illustration_service

WINDOWS = (14, 30, 45)
TARGET_FILL = 0.89


def _short_description(value: Optional[str]) -> Optional[str]:
    text = " ".join((value or "").split())
    if not text:
        return None
    sentences = re.split(r"(?<=[.!?])\s+", text)
    selected = " ".join(sentences[:2]).strip()
    return selected or text


def _title_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


class AroundThisTimeService:
    """Build a Chronicle-ready nearby-event payload from SQLite."""

    def __init__(self, repository=EventRepository, illustrations=illustration_service):
        self.repository = repository
        self.illustrations = illustrations

    @staticmethod
    def _score(event, target: date) -> float:
        distance = abs((event.event_date - target).days)
        proximity = max(0, 20 - distance * 0.5)
        description = 3 if event.description else 0
        precision = 4 if event.date_property_type not in {"year", "year_only"} else -8
        category = 1 if event.category and event.category != "unknown" else 0
        return int(event.importance_score or 0) * 4 + proximity + description + precision + category

    @staticmethod
    def _illustration_context(category: Optional[str]) -> str:
        category = (category or "").casefold()
        if category in {"politics", "government"}:
            return "politics"
        if category in {"science_space", "science", "technology"}:
            return "science"
        if category in {"sports", "achievement"}:
            return "sports"
        if category in {"culture", "entertainment"}:
            return "culture"
        if category in {"war_conflict", "disaster", "society"}:
            return "world"
        return "landmark"

    def get_around_this_time(
        self,
        birth_date: date,
        newspaper_style_id: Optional[str] = None,
        excluded_event_ids: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        excluded = {str(item) for item in (excluded_event_ids or [])}
        seen_titles = set()
        candidates = []
        for window in WINDOWS:
            raw_events = self.repository.get_events_near_date(birth_date, window, window)
            for event in raw_events:
                if event.date_property_type in {"year", "year_only"}:
                    continue
                if event.wikidata_id and event.wikidata_id in excluded:
                    continue
                title_key = _title_key(event.title)
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)
                candidates.append(event)
            if len(candidates) >= 3 or window == WINDOWS[-1]:
                break
        if not candidates:
            return {
                "available": False,
                "year": birth_date.year,
                "targetDate": birth_date.isoformat(),
                "windowDays": window,
                "featuredEvent": None,
                "secondaryEvents": [],
                "illustrationId": None,
                "illustration": None,
                "accuracyType": NEAR_DATE,
                "reason": "nearby_events_unavailable",
            }
        ranked = sorted(
            candidates,
            key=lambda event: (-self._score(event, birth_date), abs((event.event_date - birth_date).days), event.title.casefold(), event.wikidata_id or ""),
        )
        featured = ranked[0]
        featured_payload = {
            "id": featured.wikidata_id,
            "title": featured.title,
            "date": featured.event_date.isoformat(),
            "dateDisplay": featured.event_date.strftime("%b %-d, %Y") if not __import__("os").name == "nt" else featured.event_date.strftime("%b %#d, %Y"),
            "daysFromBirthday": (featured.event_date - birth_date).days,
            "description": _short_description(featured.description),
            "category": featured.category,
            "importance": featured.importance_score,
            "accuracyType": EXACT_DATE if featured.event_date == birth_date else NEAR_DATE,
        }
        secondary = []
        for event in ranked[1:]:
            secondary.append({
                "id": event.wikidata_id,
                "title": event.title,
                "date": event.event_date.isoformat(),
                "dateDisplay": event.event_date.strftime("%b %-d") if not __import__("os").name == "nt" else event.event_date.strftime("%b %#d"),
                "daysFromBirthday": (event.event_date - birth_date).days,
                "description": _short_description(event.description),
                "category": event.category,
                "importance": event.importance_score,
                "accuracyType": EXACT_DATE if event.event_date == birth_date else NEAR_DATE,
            })
        context = self._illustration_context(featured.category)
        illustration = self.illustrations.get_for_context(context, birth_date.year) or self.illustrations.get_for_context("world", birth_date.year)
        illustration_id = illustration.get("id") if illustration else None
        illustration_payload = self.illustrations.resolve_by_id(illustration_id, newspaper_style_id) if illustration_id else None
        return {
            "available": True,
            "year": birth_date.year,
            "targetDate": birth_date.isoformat(),
            "windowDays": window,
            "featuredEvent": featured_payload,
            "secondaryEvents": secondary,
            "illustrationId": illustration_id,
            "illustration": illustration_payload,
            "accuracyType": NEAR_DATE,
            "candidates": [featured_payload, *secondary],
            "targetFill": TARGET_FILL,
        }


around_this_time_service = AroundThisTimeService()
