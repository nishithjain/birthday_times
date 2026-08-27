"""Load illustration metadata and select assets by year, category, and context."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ("id", "category", "path", "priority")
PATH_PREFIX = "images/illustrations/originals/"
ORIGINALS_SEGMENT = "/originals/"
VARIANTS_SEGMENT = "/variants/{era}/"
SPORT_CONTEXTS = frozenset({"baseball", "football", "cricket", "olympics"})
GENERIC_ZODIAC_ID = "chinese-zodiac"
DEFAULT_SPORTS_CONTEXT = "baseball"
FAMOUS_PEOPLE_ICON_FILES = {
    "Activist": "activist.png", "Actor": "actor.png", "Administrator": "governor.png",
    "Agriculturalist": "scientist.png", "Apostle": "religious-leader.png", "Architect": "architect.png",
    "Artisan": "artisan.png", "Artist": "artist.png", "Astronaut": "astronaut.png",
    "Astronomer": "scientist.png", "Athlete": "athlete.png", "Author": "writer.png",
    "Banker": "banker.png", "Basketball Player": "basketball_player.png", "Biologist": "biologist.png",
    "Caliph": "ruler.png", "Chemist": "chemist.png", "Composer": "composer.png",
    "Cook": "cook.png", "Cricketer": "cricketer.png", "Criminal": "pirate.png",
    "Dancer": "dancer.png", "Diplomat": "diplomat.png", "Director": "director.png",
    "Doge": "ruler.png", "Duchess": "princess.png", "Duke": "prince.png",
    "Economist": "economist.png", "Educator": "scholar.png", "Emperor": "emperor.png",
    "Empress": "queen.png", "Engineer": "engineer.png", "Entrepreneur": "entrepreneur.png",
    "Evangelist": "religious-leader.png", "Explorer": "explorer.png", "Footballer": "footballer.png",
    "General": "military_commander.png", "Governor": "governor.png", "Historian": "historian.png",
    "Inventor": "inventor.png", "Judge": "judge.png", "King": "king.png",
    "Lawyer": "lawyer.png", "Librarian": "librarian.png", "Mathematician": "mathematician.png",
    "Merchant": "banker.png", "Military Commander": "military_commander.png", "Monarch": "monarch.png",
    "Musician": "musician.png", "Noble": "prince.png", "Nurse": "nurse.png",
    "Painter": "painter.png", "Philosopher": "philosopher.png", "Physician": "nurse.png",
    "Physicist": "physicist.png", "Pirate": "pirate.png", "Playwright": "writer.png",
    "Poet": "poet.png", "Politician": "politician.png", "Pope": "pope.png",
    "Prince": "prince.png", "Princess": "princess.png", "Printer": "librarian.png",
    "Prophet": "prophet.png", "Publisher": "librarian.png", "Queen": "queen.png",
    "Religious Leader": "religious-leader.png", "Ruler": "ruler.png", "Saint": "religious-leader.png",
    "Scholar": "scholar.png", "Scientist": "scientist.png", "Shogun": "military_commander.png",
    "Singer": "singer.png", "Soldier": "soldier.png", "Statesman": "politician.png",
    "Sultan": "sultan.png", "Tennis Player": "tennis_player.png", "Theologian": "religious-leader.png",
    "Tsar": "emperor.png", "Writer": "writer.png",
}

MASTHEAD_LOGO_ERAS = (
    (1950, 1969, "eagle", "eagle.png"),
    (1970, 1989, "eagle-globe", "eagle_globe.png"),
    (1990, 2004, "newspaper-globe", "newspaper_globe.png"),
    (2005, 2014, "chronicle-seal", "circular_chronicle_seal.png"),
    (2015, None, "bc-logo", "bc_logo.png"),
)


def variant_path_for(original_path: str, era: str) -> Optional[str]:
    """Derive the era variant static path from an original illustration path.

    images/illustrations/originals/<cat>/<file>.png
        -> images/illustrations/variants/<era>/<cat>/<file>.png

    Returns None when the input is not an originals path.
    """
    if not original_path or ORIGINALS_SEGMENT not in original_path:
        return None
    return original_path.replace(
        ORIGINALS_SEGMENT,
        VARIANTS_SEGMENT.format(era=era),
        1,
    )


def normalize_context(value: Optional[str]) -> str:
    """Normalize context tokens for case-insensitive matching."""
    if value is None:
        return ""
    normalized = str(value).strip().lower()
    normalized = normalized.replace("-", "_").replace(" ", "_")
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_")


def is_year_eligible(illustration: Dict[str, Any], year: Optional[int]) -> bool:
    """Return True when year falls within the illustration's JSON range."""
    if year is None:
        return True
    year_from = illustration.get("yearFrom")
    year_to = illustration.get("yearTo")
    if year_from is not None and year < year_from:
        return False
    if year_to is not None and year > year_to:
        return False
    return True


def validate_illustration_entry(entry: Any, seen_ids: set, seen_paths: set) -> Dict[str, Any]:
    """Validate one illustrations.json object. Raises ValueError on data errors."""
    if not isinstance(entry, dict):
        raise ValueError("Each illustration must be an object.")

    missing = [field for field in REQUIRED_FIELDS if field not in entry]
    if missing:
        raise ValueError(f"Illustration is missing required fields: {missing}.")

    illustration_id = entry["id"]
    if not isinstance(illustration_id, str) or not illustration_id.strip():
        raise ValueError("Illustration id must be a non-empty string.")
    if illustration_id in seen_ids:
        raise ValueError(f"Duplicate illustration id: {illustration_id}")

    category = entry["category"]
    if not isinstance(category, str) or not category.strip():
        raise ValueError(f"Illustration {illustration_id}: category must be a non-empty string.")

    path = entry["path"]
    if not isinstance(path, str) or not path.startswith(PATH_PREFIX):
        raise ValueError(
            f"Illustration {illustration_id}: path must start with '{PATH_PREFIX}'."
        )
    if path in seen_paths:
        raise ValueError(f"Duplicate illustration path: {path}")

    priority = entry["priority"]
    if not isinstance(priority, int) or isinstance(priority, bool):
        raise ValueError(f"Illustration {illustration_id}: priority must be an integer.")

    year_from = entry.get("yearFrom")
    year_to = entry.get("yearTo")
    if year_from is not None and not isinstance(year_from, int):
        raise ValueError(f"Illustration {illustration_id}: yearFrom must be an integer or null.")
    if year_to is not None and not isinstance(year_to, int):
        raise ValueError(f"Illustration {illustration_id}: yearTo must be an integer or null.")
    if year_from is not None and year_to is not None and year_from > year_to:
        raise ValueError(
            f"Illustration {illustration_id}: yearFrom must be <= yearTo."
        )

    contexts = entry.get("contexts", [])
    if contexts is None:
        contexts = []
    if not isinstance(contexts, list) or not all(isinstance(item, str) for item in contexts):
        raise ValueError(f"Illustration {illustration_id}: contexts must be a list of strings.")

    evergreen = entry.get("evergreen", False)
    if not isinstance(evergreen, bool):
        raise ValueError(f"Illustration {illustration_id}: evergreen must be a boolean.")

    seen_ids.add(illustration_id)
    seen_paths.add(path)

    return {
        "id": illustration_id,
        "category": category,
        "path": path.replace("\\", "/"),
        "yearFrom": year_from,
        "yearTo": year_to,
        "contexts": contexts,
        "priority": priority,
        "evergreen": evergreen,
    }


class IllustrationService:
    """Load illustrations.json once and select presentation assets."""

    def __init__(
        self,
        data_file: Optional[Path] = None,
        static_root: Optional[Path] = None,
    ) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.data_file = data_file or (
            project_root / "backend" / "data" / "illustrations.json"
        )
        self.static_root = static_root or (
            project_root / "backend" / "web" / "static"
        )
        self.illustrations: List[Dict[str, Any]] = []
        self.illustrations_by_id: Dict[str, Dict[str, Any]] = {}
        self.missing_paths: List[str] = []
        self._load()

    def _load(self) -> None:
        with self.data_file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        if not isinstance(data, dict) or "illustrations" not in data:
            raise ValueError(
                f"Invalid illustrations file: {self.data_file}. "
                "Expected an object with an 'illustrations' array."
            )

        seen_ids: set = set()
        seen_paths: set = set()
        loaded: List[Dict[str, Any]] = []
        for raw in data["illustrations"]:
            entry = validate_illustration_entry(raw, seen_ids, seen_paths)
            if not self._static_file_exists(entry["path"]):
                logger.warning(
                    "Illustration file missing for id=%s path=%s; skipping.",
                    entry["id"],
                    entry["path"],
                )
                self.missing_paths.append(entry["path"])
                continue
            loaded.append(entry)

        self.illustrations = loaded
        self.illustrations_by_id = {item["id"]: item for item in loaded}

    def _static_file_exists(self, static_relative_path: str) -> bool:
        return (self.static_root / Path(static_relative_path)).is_file()

    def _copy(self, illustration: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if illustration is None:
            return None
        return dict(illustration)

    def _matches_context(self, illustration: Dict[str, Any], context: str) -> bool:
        wanted = normalize_context(context)
        if not wanted:
            return True
        return any(normalize_context(item) == wanted for item in illustration.get("contexts", []))

    def _sort_key(self, illustration: Dict[str, Any]) -> tuple:
        return (-illustration["priority"], illustration["id"])

    def _best(self, candidates: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        ranked = sorted(candidates, key=self._sort_key)
        if not ranked:
            return None
        return self._copy(ranked[0])

    def get_by_id(self, illustration_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not illustration_id:
            return None
        return self._copy(self.illustrations_by_id.get(illustration_id))

    def resolve_by_id(
        self,
        illustration_id: Optional[str],
        style_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Resolve an illustration ID to its original or era-variant payload."""
        return self._payload(self.get_by_id(illustration_id), style_id)

    def resolve_masthead_logo(self, year: int, style_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Resolve the canonical masthead logo for a Chronicle birth year."""
        selected = next(
            (item for item in MASTHEAD_LOGO_ERAS if year >= item[0] and (item[1] is None or year <= item[1])),
            MASTHEAD_LOGO_ERAS[0],
        )
        _, _, logo_type, filename = selected
        original_path = f"images/illustrations/originals/masthead/{filename}"
        if not self._static_file_exists(original_path):
            original_path = "images/illustrations/originals/masthead/eagle.png"
            logo_type = "eagle"
        payload = self._payload({
            "id": f"masthead-{logo_type}",
            "category": "masthead",
            "path": original_path,
            "priority": 10,
        }, style_id)
        if payload:
            payload.update({"logoType": logo_type, "logoEra": f"{selected[0]}-{selected[1] or 'present'}"})
        return payload
    def get_for_category(
        self,
        category: Optional[str],
        year: Optional[int] = None,
        context: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if not category:
            return None
        wanted_category = normalize_context(category)
        candidates = [
            item
            for item in self.illustrations
            if normalize_context(item["category"]) == wanted_category
            and is_year_eligible(item, year)
        ]
        if context:
            matched = [item for item in candidates if self._matches_context(item, context)]
            return self._best(matched)
        return self._best(candidates)

    def get_for_context(
        self,
        context: Optional[str],
        year: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        if not normalize_context(context):
            return None
        candidates = [
            item
            for item in self.illustrations
            if is_year_eligible(item, year) and self._matches_context(item, context)
        ]
        return self._best(candidates)

    def get_zodiac_animal(self, animal_name: Optional[str]) -> Optional[Dict[str, Any]]:
        """Resolve a CalendarService Chinese zodiac animal to an illustration."""
        normalized = normalize_context(animal_name)
        if not normalized:
            return self.get_by_id(GENERIC_ZODIAC_ID)

        direct = self.get_by_id(normalized)
        if direct and direct["category"] == "zodiac" and direct["id"] != GENERIC_ZODIAC_ID:
            return direct

        by_context = self.get_for_category("zodiac", context=normalized)
        if by_context and by_context["id"] != GENERIC_ZODIAC_ID:
            # Preserve the legacy animal ID returned by this compatibility API.
            result = dict(by_context)
            result["id"] = normalized
            return result

        return self.get_by_id(GENERIC_ZODIAC_ID)

    def get_famous_people_occupation_icons(self, style_id: Optional[str] = None) -> Dict[str, Dict[str, Optional[str]]]:
        """Return template-ready occupation icon payloads for existing assets."""
        result = {}
        for occupation, filename in FAMOUS_PEOPLE_ICON_FILES.items():
            result[occupation] = self._payload({
                "id": f"famous-people-{occupation.casefold().replace(' ', '-')}",
                "category": "famous_people",
                "path": f"images/illustrations/originals/famous_people/{filename}",
                "priority": 1,
            }, style_id)
        return {occupation: payload for occupation, payload in result.items() if payload and payload.get("displayPath")}

    def _sports_context(self, sports_records: Optional[Sequence[Any]]) -> str:
        """Use a normalized sport field when present; otherwise default to baseball.

        Olympic-year detection is not implemented. Only explicit sport/category
        values of baseball, football, cricket, or olympics are used.
        """
        if not sports_records:
            return DEFAULT_SPORTS_CONTEXT

        for record in sports_records:
            values: List[Any] = []
            if isinstance(record, dict):
                values = [record.get(key) for key in ("sport", "category", "name", "title")]
            else:
                for key in ("sport", "category", "name", "title"):
                    values.append(getattr(record, key, None))
            for value in values:
                token = normalize_context(value)
                if token in SPORT_CONTEXTS:
                    return token
        return DEFAULT_SPORTS_CONTEXT

    def _payload(
        self,
        illustration: Optional[Dict[str, Any]],
        style_id: Optional[str] = None,
    ) -> Optional[Dict[str, Optional[str]]]:
        """Build a template-ready payload with variant/original fallback.

        displayPath prefers the processed era variant, falls back to the
        original, and is None only when neither file exists.
        """
        if illustration is None:
            return None

        original_path = illustration["path"]
        original_exists = self._static_file_exists(original_path)

        variant_path = variant_path_for(original_path, style_id) if style_id else None
        variant_exists = bool(variant_path) and self._static_file_exists(variant_path)

        if variant_exists:
            display_path: Optional[str] = variant_path
        elif original_exists:
            display_path = original_path
        else:
            display_path = None

        return {
            "id": illustration["id"],
            "category": illustration["category"],
            "originalPath": original_path,
            "variantPath": variant_path if variant_exists else None,
            "displayPath": display_path,
            "path": display_path,
        }

    def select_for_chronicle(
        self,
        year: int,
        style_id: Optional[str] = None,
        chinese_zodiac: Optional[str] = None,
        sports_records: Optional[Sequence[Any]] = None,
    ) -> Dict[str, Optional[Dict[str, Optional[str]]]]:
        """Return template-ready illustration slots for a Chronicle birth year.

        style_id is the selected NewspaperStyleService style id (e.g. "1950")
        and drives variant path resolution. When omitted, only originals are
        used.
        """
        sports_context = self._sports_context(sports_records)
        return {
            "masthead": self._payload(self.get_for_category("masthead", year), style_id),
            "weather": self._payload(self.get_for_context("weather", year), style_id),
            "world": self._payload(self.get_for_category("world", year, context="world"), style_id),
            "government": self._payload(
                self.get_for_category("government", year, context="congress"), style_id
            ),
            "movies": self._payload(self.get_for_category("movies", year), style_id),
            "music": self._payload(self.get_for_category("music", year), style_id),
            "sports": self._payload(
                self.get_for_category("sports", year, context=sports_context), style_id
            ),
            "technology": self._payload(self.get_for_category("technology", year), style_id),
            "science": self._payload(self.get_for_category("science", year), style_id),
            "zodiac": self._payload(self.get_zodiac_animal(chinese_zodiac), style_id),
            "famousPeopleOccupationIcons": self.get_famous_people_occupation_icons(style_id),
        }


illustration_service = IllustrationService()
