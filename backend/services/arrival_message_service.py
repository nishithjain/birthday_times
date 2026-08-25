"""Era-specific, deterministic wording for the NEWS OF ARRIVAL article."""

import json
import re
import string
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "arrival_templates.json"
SUPPORTED_PLACEHOLDERS = {
    "personName", "personNameUpper", "personFirstName", "personFirstNameUpper",
    "weekday", "monthName", "monthNameUpper", "day", "dayOrdinal", "year",
    "country", "zodiac", "birthstone", "generation", "presidentName",
    "presidentNameUpper", "presidentLastName", "presidentLastNameUpper",
}
HEADLINE_FALLBACKS = {
    "1950": "WASHINGTON HAILS ARRIVAL OF {personNameUpper}.",
    "1960": "WASHINGTON NOTES BIRTH OF {personNameUpper}.",
    "1970": "WHITE HOUSE WELCOMES NEWS OF {personNameUpper}'S ARRIVAL.",
    "1980": "WASHINGTON GREETS NEW ARRIVAL {personNameUpper}.",
    "1990": "WASHINGTON TAKES NOTE: {personNameUpper} HAS ARRIVED!",
    "1995": "WASHINGTON WELCOMES BIRTH OF {personNameUpper}.",
    "2000": "WASHINGTON HEARS THE NEWS: {personNameUpper} IS HERE!",
    "2005": "WASHINGTON MARKS ARRIVAL OF {personNameUpper}.",
    "2010": "WASHINGTON WELCOMES {personNameUpper} TO THE WORLD.",
    "2015": "WASHINGTON NOTES A NEW ARRIVAL: {personNameUpper}.",
}
PRESIDENT_CONTEXT_ESTIMATED_CAPACITY: Optional[int] = None
PRESIDENT_CONTEXT_SAFETY_RATIO = 0.90


def president_context_safe_capacity(capacity: Optional[int]) -> Optional[int]:
    """Return the conservative 90% preselection capacity, when measured."""
    return int(capacity * PRESIDENT_CONTEXT_SAFETY_RATIO) if capacity is not None else None


def normalize_president_context_templates(raw_candidates: Any) -> tuple[list[Dict[str, str]], list[str]]:
    """Validate the global, era-independent president-context candidate pool."""
    if not isinstance(raw_candidates, list):
        return [], ["presidentContextTemplates must be a list"]
    normalized: list[Dict[str, str]] = []
    ids = set()
    diagnostics = []
    for candidate in raw_candidates:
        if not isinstance(candidate, dict):
            diagnostics.append("candidate must be an object")
            continue
        candidate_id = candidate.get("id")
        template = candidate.get("template")
        if not all(isinstance(value, str) and value.strip() for value in (candidate_id, template)):
            diagnostics.append("candidate requires non-empty id and template")
            continue
        if candidate_id in ids:
            diagnostics.append(f"duplicate candidate id: {candidate_id}")
            continue
        ids.add(candidate_id)
        normalized.append({"id": candidate_id, "template": template})
    return normalized, diagnostics


def ordinal(day: int) -> str:
    suffix = "th" if 10 < day % 100 < 14 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


class ArrivalMessageService:
    """Select an era template before deterministically selecting its wording."""

    # These are intentionally content measurements rather than CSS values. They
    # provide a stable ranking when several era candidates are available.
    ARTICLE_WIDTH = 490
    ARTICLE_PADDING = 10
    PORTRAIT_COLUMN = 145
    COLUMN_GAP = 10
    NARROW_CHARS_PER_LINE = 38
    FULL_CHARS_PER_LINE = 58
    NARROW_AVAILABLE_LINES = 8
    BODY_LINE_HEIGHT = 17.64
    HEADLINE_LINE_HEIGHT = 25.2
    KICKER_HEIGHT = 17
    ARTICLE_TEXT_HEIGHT = 250

    def __init__(self, data_file: Optional[Path] = None):
        self.data_file = data_file or DATA_FILE

    def _load_payload(self) -> Dict[str, Any]:
        try:
            return json.loads(self.data_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not load arrival templates: {exc}") from exc

    def _load_global_president_context_templates(self) -> list[Dict[str, str]]:
        """Load the single, era-independent president-context candidate pool."""
        payload = self._load_payload()
        normalized, _diagnostics = normalize_president_context_templates(payload.get("presidentContextTemplates"))
        return normalized

    def _load_templates(self) -> list[Dict[str, str]]:
        try:
            payload = json.loads(self.data_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not load arrival templates: {exc}") from exc
        templates = payload.get("templates")
        if not isinstance(templates, list) or not templates:
            raise ValueError("arrival templates must be a non-empty list")
        seen = set()
        for template in templates:
            if any(not template.get(key) for key in ("id", "era", "headlineTemplate", "bodyTemplate")) or template["id"] in seen:
                raise ValueError("arrival templates require unique IDs, era, headlineTemplate, and bodyTemplate")
            seen.add(template["id"])
            for field in ("headlineTemplate", "bodyTemplate"):
                fields = {name for _, name, _, _ in string.Formatter().parse(template[field]) if name}
                if fields - SUPPORTED_PLACEHOLDERS:
                    raise ValueError(f"Unsupported arrival placeholder(s): {fields - SUPPORTED_PLACEHOLDERS}")
        return templates

    @staticmethod
    def _expand_president_context_candidate(candidate: Dict[str, str], values: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        template = candidate.get("template", "")
        try:
            fields = {name for _, name, _, _ in string.Formatter().parse(template) if name}
        except ValueError:
            return None
        unsupported = fields - SUPPORTED_PLACEHOLDERS
        if unsupported or not fields.issubset(values):
            return None
        expanded = re.sub(r"\s+", " ", template.format(**values)).strip()
        return {
            "id": candidate.get("id", ""),
            "text": expanded,
            "characterCount": len(expanded),
        }

    @staticmethod
    def _expand_president_context_candidates(global_candidates: Any, values: Dict[str, Any]) -> Dict[str, Any]:
        normalized, diagnostics = normalize_president_context_templates(global_candidates)
        expanded = []
        for candidate in normalized:
            result = ArrivalMessageService._expand_president_context_candidate(candidate, values)
            if result:
                expanded.append(result)
            else:
                diagnostics.append(f"malformed template: {candidate['id']}")
        # Longest candidate first; final DOM fit still governs the browser's actual pick.
        expanded.sort(key=lambda item: item["characterCount"], reverse=True)
        capacity = PRESIDENT_CONTEXT_ESTIMATED_CAPACITY
        safe_capacity = president_context_safe_capacity(capacity)
        if safe_capacity is None:
            selected = expanded[0] if expanded else None
        else:
            selected = next((item for item in expanded if item["characterCount"] <= safe_capacity), None)
            if selected is None and expanded:
                selected = min(expanded, key=lambda item: item["characterCount"])
        return {
            "available": bool(expanded),
            "diagnostics": diagnostics,
            "estimatedCapacity": capacity,
            "safeEstimatedCapacity": safe_capacity,
            "estimatedSelectedId": selected["id"] if selected else None,
            "estimatedSelectedCharacterCount": selected["characterCount"] if selected else None,
            "estimatedSelectedText": selected["text"] if selected else None,
            "candidates": expanded,
        }

    @staticmethod
    def _compact_templates(template: Dict[str, str]) -> list[Dict[str, str]]:
        """Create era-preserving fallbacks when the data has one standard copy."""
        if template.get("lengthClass") in {"ultra_compact", "compact"}:
            return []
        compact = dict(template)
        compact.update({
            "id": f'{template["era"]}_compact_01',
            "lengthClass": "compact",
            "presidentWishTemplate": "WASHINGTON (SPECIAL) -- President {presidentName} welcomed news of {personFirstName}'s arrival, marking the day for celebration.",
            "bodyTemplate": "{personFirstNameUpper} was born on {weekday}, {monthName} {day}, {year}, in {country}. A {zodiac} with {birthstone}, this {generation} arrival joins the world.",
        })
        medium = dict(template)
        medium.update({
            "id": f'{template["era"]}_medium_01',
            "lengthClass": "medium",
            "presidentWishTemplate": (
                "WASHINGTON (SPECIAL) -- President {presidentName} welcomed word of {personFirstName}'s arrival, and the White House marked the occasion for celebration."
                + " The bulletin brought smiles to Washington and gave the day's formal news a happy turn."
                + " Family welcomed the happy news."
                if template["era"] == "1950" else
                "WASHINGTON (SPECIAL) -- President {presidentName} welcomed word of {personFirstName}'s arrival, and the White House marked the occasion for celebration. The bulletin brightened Washington. Family welcomed the happy news. The nation noted the cheerful announcement."
                if template["era"] == "1960" else
                "WASHINGTON (SPECIAL) -- President {presidentName} welcomed word of {personFirstName}'s arrival, and the White House marked the occasion for celebration. The cheerful bulletin brightened Washington that morning, giving the day's news a distinctly happy note."
                + " Family welcomed the happy news."
            ),
            "bodyTemplate": "{personFirstNameUpper} was born on {weekday}, {monthName} {day}, {year}, in {country}. A {zodiac} with {birthstone}, {personFirstName} joins the {generation} generation in a memorable new beginning.",
        })
        expanded = dict(template)
        expanded.update({
            "id": f'{template["era"]}_expanded_01',
            "lengthClass": "expanded",
            "presidentWishTemplate": "WASHINGTON (SPECIAL) -- President {presidentName} welcomed word of {personFirstName}'s arrival, with the White House marking the occasion as one well worth celebrating. Officials in this special edition agreed that ordinary business could wait while the newest headline-maker received a proper greeting.",
            "bodyTemplate": "{personFirstNameUpper} was born on {weekday}, {monthName} {day}, {year}, in {country}. A {zodiac} with {birthstone} as the traditional birthstone, {personFirstName} joins the {generation} generation at the beginning of a remarkable new story. For family and friends, the day's biggest news had already arrived.",
        })
        ultra = dict(template)
        ultra.update({
            "id": f'{template["era"]}_ultra_compact_01',
            "lengthClass": "ultra_compact",
            "presidentWishTemplate": "WASHINGTON (SPECIAL) -- President {presidentName} welcomed {personFirstName}'s arrival.",
            "bodyTemplate": "{personFirstNameUpper} was born {monthName} {day}, {year}, in {country}: a {zodiac} with {birthstone}, joining the {generation} generation.",
        })
        return [compact, medium, expanded, ultra]

    def _templates_with_fallbacks(self, templates: list[Dict[str, str]]) -> list[Dict[str, str]]:
        expanded = []
        for template in templates:
            standard = dict(template)
            standard.setdefault("lengthClass", "standard")
            expanded.extend([standard, *self._compact_templates(standard)])
        return expanded

    def _templates_for_era(self, era: str) -> tuple[list[Dict[str, str]], bool]:
        templates = self._load_templates()
        matches = [template for template in templates if template["era"] == era]
        if matches:
            return matches, False
        default_era = "1950"
        fallback = [template for template in templates if template["era"] == default_era]
        if not fallback:
            raise ValueError(f"No arrival templates configured for era {era}")
        return fallback, True

    @staticmethod
    def _line_count(text: str, chars_per_line: int) -> int:
        lines = 0
        for paragraph in text.splitlines():
            current = 0
            for word in paragraph.split():
                if current and current + len(word) + 1 > chars_per_line:
                    lines += 1
                    current = 0
                current += len(word) + (1 if current else 0)
            lines += max(1, bool(current))
        return max(1, lines)

    def _layout_estimate(self, headline: str, president_wish: str, body: str) -> Dict[str, Any]:
        headline_lines = self._line_count(headline, self.FULL_CHARS_PER_LINE)
        narrow_lines = self._line_count(president_wish, self.NARROW_CHARS_PER_LINE)
        remaining_narrow = max(0, self.NARROW_AVAILABLE_LINES - narrow_lines)
        body_narrow_lines = min(self._line_count(body, self.NARROW_CHARS_PER_LINE), remaining_narrow)
        body_full_lines = max(0, self._line_count(body, self.FULL_CHARS_PER_LINE) - body_narrow_lines)
        body_lines = narrow_lines + body_narrow_lines + body_full_lines
        used_height = (
            headline_lines * self.HEADLINE_LINE_HEIGHT
            + self.KICKER_HEIGHT
            + body_lines * self.BODY_LINE_HEIGHT
        )
        return {
            "headlineLines": headline_lines,
            "bodyLines": body_lines,
            "estimatedHeight": round(used_height, 2),
            "fits": used_height <= self.ARTICLE_TEXT_HEIGHT,
        }

    def _render_candidate(
        self,
        template: Dict[str, str],
        values: Dict[str, Any],
        president_name: str,
        era: str,
        fallback_used: bool,
    ) -> Dict[str, Any]:
        has_president = bool(president_name)
        headline = (
            template["headlineTemplate"] if has_president
            else HEADLINE_FALLBACKS.get(era, "WASHINGTON HAILS ARRIVAL OF {personNameUpper}.")
        ).format(**values)
        president_wish = (
            template.get("presidentWishTemplate", "").format(**values)
            if has_president
            else "WASHINGTON (SPECIAL) -- News of " + values["personNameUpper"]
            + "'s arrival has reached the nation's capital, where the occasion has been declared worthy of celebration in this special BirthdayChronicles edition."
        )
        body = template["bodyTemplate"].format(**values)
        layout = self._layout_estimate(headline, president_wish, body)
        length_rank = {"extended": 0, "expanded": 1, "standard": 2, "medium": 3, "compact": 4, "ultra_compact": 5}.get(template.get("lengthClass"), 2)
        return {
            "available": True,
            "era": era,
            "templateId": template["id"],
            "headline": headline,
            "kicker": "NEWS OF ARRIVAL REACHES WHITE HOUSE",
            "presidentWishText": president_wish,
            "isNoveltyCopy": True,
            "bodyText": body,
            "facts": values,
            "fallbackUsed": fallback_used,
            "lengthClass": template.get("lengthClass", "standard"),
            "_layoutScore": (not layout["fits"], length_rank),
            "_layoutEstimate": layout,
        }

    def get_arrival(self, birth_date: date, name: Optional[str], country: str, calendar_data: Dict[str, Any], era: str, president_name: Optional[str] = None, city: Optional[str] = None) -> Dict[str, Any]:
        templates, fallback_used = self._templates_for_era(era)
        templates = self._templates_with_fallbacks(templates)
        normalized_name = " ".join((name or "A New Arrival").strip().split())
        first_name = normalized_name.split()[0] if normalized_name else "A New Arrival"
        president_name = (president_name or "").strip()
        president_last_name = president_name.split()[-1] if president_name else ""
        values = {
            "personName": normalized_name,
            "personNameUpper": normalized_name.upper(),
            "personFirstName": first_name,
            "personFirstNameUpper": first_name.upper(),
            "weekday": calendar_data["day_of_week"],
            "monthName": birth_date.strftime("%B"),
            "monthNameUpper": birth_date.strftime("%B").upper(),
            "day": birth_date.day,
            "dayOrdinal": ordinal(birth_date.day),
            "year": birth_date.year,
            "country": country or "the world",
            "zodiac": calendar_data["western_zodiac"],
            "birthstone": calendar_data["birthstone"],
            "generation": calendar_data["generation"],
            "presidentName": president_name,
            "presidentNameUpper": president_name.upper(),
            "presidentLastName": president_last_name,
            "presidentLastNameUpper": president_last_name.upper(),
        }
        global_context_templates = self._load_global_president_context_templates()
        president_context = (
            self._expand_president_context_candidates(global_context_templates, values)
            if president_name
            else {
                "available": False,
                "diagnostics": ["president data unavailable"],
                "estimatedCapacity": PRESIDENT_CONTEXT_ESTIMATED_CAPACITY,
                "safeEstimatedCapacity": president_context_safe_capacity(PRESIDENT_CONTEXT_ESTIMATED_CAPACITY),
                "estimatedSelectedId": None,
                "estimatedSelectedCharacterCount": None,
                "estimatedSelectedText": None,
                "candidates": [],
            }
        )
        candidates = [
            self._render_candidate(template, values, president_name, era, fallback_used)
            for template in templates
        ]
        candidates.sort(key=lambda candidate: (candidate["_layoutScore"], candidate["templateId"]))
        selected = candidates[0]
        selected_id = selected["templateId"]
        length_rank = {"extended": 0, "expanded": 1, "standard": 2, "medium": 3, "compact": 4, "ultra_compact": 5}
        selected_rank = length_rank.get(selected["lengthClass"], 1)
        ordered = [selected, *sorted(
            [candidate for candidate in candidates if candidate["templateId"] != selected_id and length_rank.get(candidate["lengthClass"], 1) >= selected_rank],
            key=lambda candidate: (length_rank.get(candidate["lengthClass"], 1), candidate["templateId"]),
        ), *sorted(
            [candidate for candidate in candidates if length_rank.get(candidate["lengthClass"], 1) < selected_rank],
            key=lambda candidate: (length_rank.get(candidate["lengthClass"], 1), candidate["templateId"]),
        )]
        for candidate in ordered:
            candidate.pop("_layoutScore")
            candidate["estimatedSize"] = candidate.pop("_layoutEstimate")
        selected = dict(selected)
        selected["candidates"] = [
            {
                "id": candidate["templateId"],
                "lengthClass": candidate["lengthClass"],
                "headline": candidate["headline"],
                "presidentWishText": candidate["presidentWishText"],
                "bodyText": candidate["bodyText"],
                "estimatedSize": candidate["estimatedSize"],
            }
            for candidate in ordered
        ]
        location = " ".join((city or "").strip().split())
        location_lead = f"{location} - " if location else ""
        selected["birthStoryHeadline"] = "A New Arrival Makes Headlines"
        selected["birthStoryParagraphs"] = [
            f"{location_lead}On this memorable {values['weekday']}, a new arrival entered the world on {values['monthName']} {values['day']}, {values['year']}.",
            f"The beginning of {values['personName']}'s story brought a fresh personal headline to {location or values['country']}. Around it, the world was already alive with news, culture and change.",
            f"For family and friends, this was the day's most meaningful bulletin: a new chapter had begun in {location or values['country']}.",
            "While headlines elsewhere recorded the events of the year, one story mattered most close to home.",
        ]
        selected["dispatchCity"] = location or None
        selected["dispatchCountry"] = country or None
        selected["presidentContextText"] = (
            f"{president_name} was serving as President of the United States when this new arrival entered the world."
            if president_name else "The President of the United States was serving during this new arrival's beginning."
        )
        selected["presidentContext"] = president_context
        return selected


arrival_message_service = ArrivalMessageService()
