"""Factual and personalized famous-birthday presentation service."""

import json
import hashlib
import logging
import string
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from backend.models.person import FamousPerson
from backend.repositories.person_repository import PersonRepository

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SUPPORTED_PLACEHOLDERS = {
    "personFirstName", "personFirstNameUpper", "monthName", "monthNameShortUpper",
    "dayOrdinal", "dayOrdinalUpper", "celebrityNames", "asOfDateLong", "daysAliveFormatted",
}


def ordinal(day: int) -> str:
    suffix = "th" if 10 < day % 100 < 14 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def english_list(names: Iterable[str]) -> str:
    values = [name for name in names if name]
    if len(values) < 2:
        return values[0] if values else ""
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def first_name(name: str) -> str:
    return (name or "").strip().split()[0] if (name or "").strip() else "there"


def _group(occupation: Optional[str]) -> str:
    text = (occupation or "").lower()
    for group, terms in {
        "acting": ("actor", "actress"), "music": ("musician", "singer", "composer"),
        "writing": ("writer", "author", "poet"), "science": ("scientist", "inventor"),
        "politics": ("politician", "president", "minister"), "sports": ("athlete", "footballer"),
        "film": ("director", "filmmaker"), "art": ("artist", "painter"),
    }.items():
        if any(term in text for term in terms):
            return group
    return "other"


class FamousBirthdaysService:
    def __init__(self, repository=PersonRepository, templates_path: Optional[Path] = None, overrides_path: Optional[Path] = None):
        self.repository = repository
        self.templates_path = templates_path or DATA_DIR / "famous_birthdays_templates.json"
        self.overrides_path = overrides_path or DATA_DIR / "famous_birthdays_overrides.json"

    def _load_templates(self) -> tuple[Dict[str, str], ...]:
        try:
            payload = json.loads(self.templates_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not load famous-birthday templates: {exc}") from exc
        templates = payload.get("templates")
        if not isinstance(templates, list) or not templates:
            raise ValueError("famous-birthday templates must contain a non-empty templates array")
        result = []
        ids = set()
        for template in templates:
            if not isinstance(template, dict) or any(not template.get(key) for key in ("id", "headlineTemplate", "introTemplate", "daysAliveTemplate")):
                raise ValueError("each famous-birthday template requires id and three template strings")
            if template["id"] in ids:
                raise ValueError(f"duplicate famous-birthday template id: {template['id']}")
            ids.add(template["id"])
            for field in ("headlineTemplate", "introTemplate", "daysAliveTemplate"):
                fields = {name for _, name, _, _ in string.Formatter().parse(template[field]) if name}
                unknown = fields - SUPPORTED_PLACEHOLDERS
                if unknown:
                    raise ValueError(f"unsupported famous-birthday placeholder(s): {', '.join(sorted(unknown))}")
            result.append(template)
        default_id = payload.get("defaultTemplateId")
        if default_id not in ids:
            raise ValueError(f"default famous-birthday template does not exist: {default_id}")
        selection = payload.get("selection", {"mode": "deterministic"})
        if selection.get("mode", "deterministic") != "deterministic":
            raise ValueError("supported famous-birthday template selection mode is deterministic")
        return tuple(result)

    def _select_template(self, person_name: Optional[str], birth_date: date) -> Dict[str, str]:
        templates = self._load_templates()
        normalized_name = " ".join((person_name or "").strip().casefold().split())
        seed = f"{normalized_name}|{birth_date.isoformat()}"
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        return templates[int.from_bytes(digest[:8], "big") % len(templates)]

    def _override_ids(self, month: int, day: int) -> List[str]:
        try:
            payload = json.loads(self.overrides_path.read_text(encoding="utf-8"))
            return payload.get("dates", {}).get(f"{month:02d}-{day:02d}", {}).get("featured", [])
        except (OSError, ValueError):
            return []

    def _select(self, candidates: List[FamousPerson], month: int, day: int, limit: int) -> List[FamousPerson]:
        by_id = {person.wikidata_id: person for person in candidates if person.wikidata_id}
        selected: List[FamousPerson] = []
        for person_id in self._override_ids(month, day):
            person = by_id.get(person_id)
            if person and person not in selected:
                selected.append(person)
        ranked = sorted(candidates, key=lambda person: (-person.notability_score, person.birth_date, person.name.lower(), person.wikidata_id or ""))
        used_groups = {_group(person.occupation) for person in selected}
        for person in ranked:
            if len(selected) >= limit:
                break
            if person not in selected and _group(person.occupation) not in used_groups:
                selected.append(person)
                used_groups.add(_group(person.occupation))
        for person in ranked:
            if len(selected) >= limit:
                break
            if person not in selected:
                selected.append(person)
        return selected[:limit]

    def get_famous_birthdays(self, birth_date: date, person_name: Optional[str] = None, as_of_date: Optional[date] = None, limit: int = 5, newspaper_style_id: Optional[str] = None) -> Dict[str, Any]:
        as_of_date = as_of_date or date.today()
        month_name = birth_date.strftime("%B")
        month_short = birth_date.strftime("%b")
        people = self._select(self.repository.get_by_month_day(birth_date.month, birth_date.day), birth_date.month, birth_date.day, limit)
        template = self._select_template(person_name, birth_date)
        names = english_list(person.name for person in people)
        days_alive = (as_of_date - birth_date).days
        days_alive_value = days_alive if days_alive >= 0 else None
        as_of_long = f"{as_of_date.strftime('%A')}, {as_of_date.strftime('%b')}. {as_of_date.day}, {as_of_date.year}"
        values = {
            "monthName": month_name, "monthNameShort": month_short, "monthNameShortUpper": month_short.upper(),
            "dayOrdinal": ordinal(birth_date.day), "dayOrdinalUpper": ordinal(birth_date.day).upper(), "celebrityNames": names,
            "asOfDateLong": as_of_long, "personFirstName": first_name(person_name or ""),
            "personFirstNameUpper": first_name(person_name or "").upper(),
            "daysAliveFormatted": f"{days_alive:,}" if days_alive_value is not None else "",
        }
        return {
            "month": birth_date.month, "day": birth_date.day, "monthDay": f"{birth_date.month:02d}-{birth_date.day:02d}",
            "monthName": month_name, "monthNameShort": month_short, "monthNameShortUpper": month_short.upper(),
            "dayOrdinal": ordinal(birth_date.day), "dayOrdinalUpper": ordinal(birth_date.day).upper(),
            "templateId": template["id"],
            "headline": template["headlineTemplate"].format(**values),
            "people": [{"id": person.wikidata_id, "name": person.name, "birthDate": person.birth_date.isoformat(), "occupation": person.occupation, "description": person.description, "notabilityScore": person.notability_score} for person in people],
            "celebrityNames": names,
            "introText": template["introTemplate"].format(**values) if people else "",
            "asOfDate": as_of_date.isoformat(), "asOfDateLong": as_of_long,
            "daysAlive": days_alive_value, "daysAliveFormatted": values["daysAliveFormatted"],
            "daysAliveText": template["daysAliveTemplate"].format(**values) if people and days_alive_value is not None else "",
        }


famous_birthdays_service = FamousBirthdaysService()