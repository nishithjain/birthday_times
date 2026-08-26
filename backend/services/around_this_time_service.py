"""Offline nearby historical-event selection for the Around This Time article."""

import re
from datetime import date
from typing import Any, Dict, Iterable, Optional

from backend.repositories.around_this_time_repository import AroundThisTimeRepository
from backend.services.accuracy import NEAR_DATE
from backend.services.illustration_service import illustration_service
from backend.services.historical_event_quality import (
    accuracy_for_event,
    classify_event_date_precision,
    deduplicate_events,
    is_usable_around_this_time_event,
    quality_score,
)
from backend.services.historical_event_quality import YEAR_LEVEL

WINDOWS = (0, 30, 60, 90, 120, 150, 180)
DEFAULT_CANDIDATE_LIMIT = 6
MAX_CANDIDATES = 6
TARGET_FILL = 0.89
SHORT_DESCRIPTION_MAX_CHARS = 90


def _short_description(value: Optional[str]) -> Optional[str]:
    text = " ".join((value or "").split())
    if not text:
        return None
    sentences = re.split(r"(?<=[.!?])\s+", text)
    selected = " ".join(sentences[:2]).strip()
    return selected or text


def _sentence_case(value: Optional[str]) -> Optional[str]:
    """Capitalize the first letter without changing proper-noun casing."""
    text = " ".join((value or "").split())
    if not text:
        return None
    match = re.search(r"[A-Za-z]", text)
    if not match:
        return text
    index = match.start()
    return text[:index] + text[index].upper() + text[index + 1:]


def _has_short_description(event) -> bool:
    description = _short_description(getattr(event, "description", None))
    return bool(description) and len(description) <= SHORT_DESCRIPTION_MAX_CHARS


def _title_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _display_text(event) -> str:
    title = _sentence_case(getattr(event, "title", None)) or ""
    description = _sentence_case(_short_description(getattr(event, "description", None))) or ""
    return max(title, description, key=len)


class AroundThisTimeService:
    """Build a Chronicle-ready nearby-event payload from SQLite."""

    def __init__(self, repository=AroundThisTimeRepository, illustrations=illustration_service):
        self.repository = repository
        self.illustrations = illustrations

    @staticmethod
    def _score(event, target: date) -> float:
        distance = abs((event.event_date - target).days)
        proximity = max(0, 20 - distance * 0.5)
        return quality_score(event) + proximity

    @staticmethod
    def _identity(event) -> str:
        """Prefer a stable source ID, falling back to normalized title."""
        source_id = getattr(event, "wikidata_id", None)
        if source_id:
            return f"source:{source_id}"
        return f"title:{_title_key(event.title)}"

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
        limit: int = DEFAULT_CANDIDATE_LIMIT,
    ) -> Dict[str, Any]:
        target_count = max(5, min(int(limit), MAX_CANDIDATES))
        excluded = {str(item) for item in (excluded_event_ids or [])}
        seen_ids = set()
        candidates = []
        candidate_windows = {}
        for window in WINDOWS:
            raw_events = self.repository.get_events_near_date(birth_date, window, window, limit=100)
            for event in raw_events:
                if event.event_date.year != birth_date.year:
                    continue
                if classify_event_date_precision(event) == YEAR_LEVEL:
                    continue
                if not is_usable_around_this_time_event(event, allow_sparse=window > 30):
                    continue
                if event.wikidata_id and event.wikidata_id in excluded:
                    continue
                identity = self._identity(event)
                if identity in seen_ids:
                    continue
                seen_ids.add(identity)
                candidates.append(event)
                candidate_windows.setdefault(identity, window)
        if len(deduplicate_events(candidates)) < target_count:
            year_start = date(birth_date.year, 1, 1)
            year_end = date(birth_date.year, 12, 31)
            raw_events = self.repository.get_between_dates(year_start, year_end, limit=100)
            for event in raw_events:
                if event.event_date.year != birth_date.year:
                    continue
                if classify_event_date_precision(event) == YEAR_LEVEL:
                    continue
                if not is_usable_around_this_time_event(event, allow_sparse=True):
                    continue
                if event.wikidata_id and event.wikidata_id in excluded:
                    continue
                identity = self._identity(event)
                if identity in seen_ids:
                    continue
                seen_ids.add(identity)
                candidates.append(event)
                candidate_windows.setdefault(identity, WINDOWS[-1])
        deduplicated = deduplicate_events(candidates)
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
            deduplicated,
            key=lambda event: (
                -int(getattr(event, "importance_score", 0) or 0),
                -len(_display_text(event)),
                abs((event.event_date - birth_date).days),
                event.title.casefold(),
                self._identity(event),
            ),
        )[:target_count]
        featured = ranked[0]
        def payload(event):
            identity = self._identity(event)
            distance = (event.event_date - birth_date).days
            event_accuracy = accuracy_for_event(event, birth_date)
            clean_description = _short_description(event.description)
            formatted_title = _sentence_case(event.title)
            formatted_description = _sentence_case(clean_description)
            display_text = max(
                (formatted_title, formatted_description or ""),
                key=len,
            )
            return {
            "id": event.wikidata_id,
            "wikidataId": event.wikidata_id,
            "title": formatted_title,
            "date": event.event_date.isoformat(),
            "eventDate": event.event_date.isoformat(),
            "dateDisplay": event.event_date.strftime("%b %-d, %Y") if not __import__("os").name == "nt" else event.event_date.strftime("%b %#d, %Y"),
            "daysFromBirthday": distance,
            "days_from_birthday": distance,
            "absDaysFromBirthday": abs(distance),
            "description": formatted_description,
            "displayText": display_text,
            "category": event.category,
            "importance": event.importance_score,
            "qualityScore": self._score(event, birth_date),
            "dateSource": event.date_property or event.date_property_type,
            "selectionWindow": candidate_windows[identity],
            "accuracyType": event_accuracy,
            "accuracy": event_accuracy,
            }

        featured_payload = payload(featured)
        secondary = [payload(event) for event in ranked[1:]]
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
