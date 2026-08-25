"""Traditional Chinese zodiac content backed by verified local JSON data."""

import hashlib
import json
import string
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

from backend.services.famous_birthdays_service import english_list

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
ANIMAL_IDS = {"rat", "ox", "tiger", "rabbit", "dragon", "snake", "horse", "goat", "monkey", "rooster", "dog", "pig"}


class ChineseZodiacError(ValueError):
    """Invalid or unavailable zodiac configuration/data."""


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ChineseZodiacError(f"Could not load {path.name}: {exc}") from exc


def _load_boundaries() -> Dict[int, Dict[str, Any]]:
    records = _load_json(DATA_DIR / "chinese_new_years.json").get("years")
    if not isinstance(records, list) or not records:
        raise ChineseZodiacError("Chinese New Year data must contain years")
    result = {}
    previous_year = 0
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("year"), int) or record["year"] in result:
            raise ChineseZodiacError("Chinese New Year records must have unique integer years")
        if record["year"] <= previous_year:
            raise ChineseZodiacError("Chinese New Year records must be sorted")
        try:
            start = date.fromisoformat(record["startDate"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ChineseZodiacError("Chinese New Year startDate must be ISO date") from exc
        if record.get("animal") not in ANIMAL_IDS or start.year != record["year"]:
            raise ChineseZodiacError("Invalid Chinese New Year animal or date")
        result[record["year"]] = {**record, "start": start}
        previous_year = record["year"]
    return result


def _load_animals() -> Dict[str, Dict[str, Any]]:
    records = _load_json(DATA_DIR / "chinese_zodiac.json").get("animals")
    if not isinstance(records, list) or {item.get("id") for item in records} != ANIMAL_IDS:
        raise ChineseZodiacError("Chinese zodiac data must define all twelve animals")
    result = {}
    for item in records:
        if not item.get("name") or not isinstance(item.get("traits"), list) or not item.get("illustrationId"):
            raise ChineseZodiacError("Each Chinese zodiac animal needs name, traits, and illustrationId")
        result[item["id"]] = item
    return result


def _templates() -> tuple[Dict[str, str], ...]:
    payload = _load_json(DATA_DIR / "chinese_zodiac_templates.json")
    records = payload.get("templates")
    required = {"personFirstName", "personFirstNameUpper", "animal", "animalUpper", "traitList", "fortuneMessage"}
    if not isinstance(records, list) or not records:
        raise ChineseZodiacError("Chinese zodiac templates must be non-empty")
    result = []
    ids = set()
    for item in records:
        if not isinstance(item, dict) or any(not item.get(key) for key in ("id", "headlineTemplate", "introTemplate", "fortuneTemplate")) or item["id"] in ids:
            raise ChineseZodiacError("Chinese zodiac templates must have unique IDs and required fields")
        ids.add(item["id"])
        for field in ("headlineTemplate", "introTemplate", "fortuneTemplate"):
            fields = {name for _, name, _, _ in string.Formatter().parse(item[field]) if name}
            if fields - required:
                raise ChineseZodiacError(f"Unsupported Chinese zodiac placeholder(s): {fields - required}")
        result.append(item)
    if payload.get("defaultTemplateId") not in ids:
        raise ChineseZodiacError("Chinese zodiac default template is missing")
    return tuple(result)


def _fortune_messages() -> list[str]:
    messages = _load_json(DATA_DIR / "fortune_cookie_messages.json").get("messages")
    if not isinstance(messages, list) or not all(isinstance(message, str) and message.strip() for message in messages):
        raise ChineseZodiacError("Fortune-cookie messages must be non-empty strings")
    return messages


def _normalized_name(name: Optional[str]) -> str:
    return " ".join((name or "there").strip().casefold().split())


def _pick(items, seed: str):
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return items[int.from_bytes(digest[:8], "big") % len(items)]


class ChineseZodiacService:
    def __init__(self, illustration_service=None):
        if illustration_service is None:
            from backend.services.illustration_service import illustration_service as default_service
            illustration_service = default_service
        self.illustration_service = illustration_service

    def get_chinese_zodiac(self, birth_date: date, person_name: Optional[str] = None, newspaper_style_id: Optional[str] = None) -> Dict[str, Any]:
        boundaries = _load_boundaries()
        current = boundaries.get(birth_date.year)
        previous = boundaries.get(birth_date.year - 1)
        if not current or not previous:
            return {"available": False, "reason": "zodiac_boundary_unavailable"}
        zodiac_year = birth_date.year if birth_date >= current["start"] else birth_date.year - 1
        animal_id = boundaries[zodiac_year]["animal"]
        animal = _load_animals()[animal_id]
        templates = _templates()
        normalized = _normalized_name(person_name)
        birth_seed = birth_date.isoformat()
        template = _pick(templates, f"zodiac-template|{normalized}|{birth_seed}")
        fortune = _pick(_fortune_messages(), f"zodiac-fortune|{normalized}|{birth_seed}")
        first = (person_name or "there").strip().split()[0] if (person_name or "").strip() else "There"
        values = {
            "personFirstName": first, "personFirstNameUpper": first.upper(),
            "animal": animal["name"], "animalUpper": animal["name"].upper(),
            "traitList": english_list(animal["traits"]), "fortuneMessage": fortune,
        }
        result = {
            "available": True, "zodiacYear": zodiac_year, "animalId": animal_id,
            "animal": animal["name"], "animalUpper": animal["name"].upper(),
            "traits": animal["traits"], "traitList": values["traitList"],
            "templateId": template["id"], "headline": template["headlineTemplate"].format(**values),
            "introText": template["introTemplate"].format(**values), "fortuneMessage": fortune,
            "fortuneText": template["fortuneTemplate"].format(**values),
            "illustrationId": animal["illustrationId"], "accuracyType": "traditional_zodiac",
            "optionalSentences": [
                f"The {animal['name']} is one of twelve signs in the traditional zodiac cycle.",
                f"{first} shares this traditional sign with others born in the same twelve-year cycle.",
            ],
                "candidates": [
                    {
                        "id": candidate["id"],
                        "introText": candidate["introTemplate"].format(**values),
                        "fortuneText": candidate["fortuneTemplate"].format(**values),
                        "lengthClass": "compact" if len(candidate["introTemplate"]) + len(candidate["fortuneTemplate"]) < 150 else "standard",
                    }
                    for candidate in templates
                ],
        }
        if self.illustration_service:
            result["illustration"] = self.illustration_service.resolve_by_id(result["illustrationId"], newspaper_style_id)
        return result

    def get_animal_for_date(self, birth_date: date) -> Optional[str]:
        boundaries = _load_boundaries()
        current = boundaries.get(birth_date.year)
        previous = boundaries.get(birth_date.year - 1)
        if not current or not previous:
            return None
        zodiac_year = birth_date.year if birth_date >= current["start"] else birth_date.year - 1
        return _load_animals()[boundaries[zodiac_year]["animal"]]["name"]


chinese_zodiac_service = ChineseZodiacService()
