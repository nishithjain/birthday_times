"""Quality and date-precision policy for historical event presentation."""

import re
from datetime import date

from backend.services.accuracy import EXACT_DATE, NEAR_DATE

EXACT_DAY = "exact_day"
DAY_LEVEL_MILESTONE = "day_level_milestone"
YEAR_LEVEL = "year_level"
UNKNOWN_PRECISION = "unknown"

_GENERIC_TITLE_RE = re.compile(r"^(?:\d{4}|\d{4}s)$", re.IGNORECASE)
_HASHTAG_RE = re.compile(r"(?:^|\s)#\w+\b")
_CALENDAR_TITLE_RE = re.compile(
    r"^(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+in\s+",
    re.IGNORECASE,
)
_GEOGRAPHIC_LOCATION_RE = re.compile(
    r"\b(?:square|street|avenue|park|plaza|road|building|station|city|town|municipality)\s+(?:in|of)\b",
    re.IGNORECASE,
)
_GENERIC_PLACE_DESCRIPTION_RE = re.compile(
    r"^(?:the\s+|a\s+|an\s+)?(?:public\s+)?(?:square|street|avenue|park|plaza|road|building|station|city|town|municipality)\s+(?:in|of)\s+.+$",
    re.IGNORECASE,
)
_EVENT_PHRASE_RE = re.compile(
    r"\b(?:was|were|is|are|became|began|ended|occurred|took place|founded|opened|closed|"
    r"launched|signed|declared|approved|elected|won|lost|died|born|created|introduced|"
    r"discovered|invented|released|premiered|joined|left|captured|invaded|exploded|"
    r"collapsed|established|inaugurated|hosted|held|celebrated|recorded|changed|happened|started|"
    r"battle|championship|conflict|coup|disaster|election|festival|invasion|massacre|"
    r"rebellion|revolution|treaty|tournament|war|world cup|coronation|discovery|mission)\b",
    re.IGNORECASE,
)
_METADATA_PREFIXES = (
    "list of ", "category:", "portal:", "outline of ", "index of ", "timeline of ",
)
_WEAK_DESCRIPTIONS = {
    "article", "calendar year", "decade", "event", "historical event", "natural disaster",
    "period", "television series", "year",
}
_VAGUE_TERMS = {"natural disaster", "workshop", "training program"}
_CONTEXT_WORDS = {
    "battle", "championship", "conflict", "coup", "disaster", "election",
    "festival", "founded", "inaugurated", "invasion", "launched", "massacre",
    "opened", "prize", "rebellion", "revolution", "treaty", "tournament",
    "war", "world cup", "agreement", "coronation", "discovery", "mission", "political",
}
_ENTERTAINMENT_TERMS = {
    "album", "film", "movie", "song", "television", "tv series", "video game",
}
_TITLE_FAMILY_SUFFIXES = (
    "badminton championships", "nba game", "nba games", "nba match", "nba matches",
)


def _property_type(event) -> str:
    value = (getattr(event, "date_property_type", None) or "").casefold()
    property_id = (getattr(event, "date_property", None) or "").casefold()
    if value in {"point_in_time", "p585"} or property_id == "p585":
        return "p585"
    if value in {"start_time", "p580"} or property_id == "p580":
        return "p580"
    if value in {"inception", "p571"} or property_id == "p571":
        return "p571"
    if value in {"year", "year_only", "year_level"}:
        return "year"
    return "unknown"


def classify_event_date_precision(event) -> str:
    """Classify stored date precision without trusting its shape alone."""
    event_date = getattr(event, "event_date", None)
    if not isinstance(event_date, date):
        return UNKNOWN_PRECISION
    property_type = _property_type(event)
    if property_type == "p585":
        return EXACT_DAY
    if property_type in {"p580", "p571"}:
        return DAY_LEVEL_MILESTONE
    if property_type == "year" or (event_date.month == 1 and event_date.day == 1):
        return YEAR_LEVEL
    return UNKNOWN_PRECISION


def is_usable_around_this_time_event(event, allow_sparse=False) -> bool:
    """Return whether an event has enough context for the nearby-events article.

    Extended-window candidates may use the relaxed context policy because sparse
    dates should not lose meaningful events solely for lacking a taxonomy word.
    Basic metadata and weak-description checks remain strict in both modes.
    """
    title = " ".join(str(getattr(event, "title", "") or "").split())
    normalized_title = title.casefold()
    if not title or _GENERIC_TITLE_RE.fullmatch(title):
        return False
    if normalized_title in _WEAK_DESCRIPTIONS or _HASHTAG_RE.search(title):
        return False
    if _CALENDAR_TITLE_RE.match(title) or _GEOGRAPHIC_LOCATION_RE.search(title):
        return False
    if normalized_title.startswith(_METADATA_PREFIXES):
        return False

    description = " ".join(str(getattr(event, "description", "") or "").split())
    normalized_description = description.casefold().strip(" .;:")
    if not normalized_description or normalized_description == normalized_title:
        return False
    if normalized_description in _WEAK_DESCRIPTIONS or _HASHTAG_RE.search(description):
        return False
    display_text = " ".join(str(getattr(event, "displayText", "") or "").split())
    if not display_text:
        display_text = max((title, description), key=len)
    normalized_display_text = display_text.casefold().strip(" .;:")
    if _GEOGRAPHIC_LOCATION_RE.search(description) or _GENERIC_PLACE_DESCRIPTION_RE.fullmatch(normalized_description):
        return False
    if _GENERIC_PLACE_DESCRIPTION_RE.fullmatch(normalized_display_text):
        return False
    if any(
        term in f"{normalized_title} {normalized_description}" for term in _VAGUE_TERMS
    ):
        return False
    if len(re.sub(r"[^a-z0-9]+", "", normalized_description)) < 20:
        return False
    if not _EVENT_PHRASE_RE.search(description) and not _EVENT_PHRASE_RE.search(display_text):
        return False
    if not allow_sparse and getattr(event, "category", None) == "entertainment":
        return False
    if any(term in normalized_description for term in {"wikimedia list", "category page", "disambiguation page"}):
        return False
    if not allow_sparse and not any(term in normalized_title or term in normalized_description for term in _CONTEXT_WORDS):
        return False
    if not allow_sparse and any(term in normalized_title or term in normalized_description for term in _ENTERTAINMENT_TERMS):
        return False
    return True


def _title_family_key(title: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()
    for suffix in _TITLE_FAMILY_SUFFIXES:
        if normalized.endswith(suffix):
            return suffix
    return normalized


def deduplicate_events(events):
    """Keep the highest-importance event from each repeated title family."""
    selected = {}
    for event in events:
        key = _title_family_key(str(getattr(event, "title", "") or ""))
        current = selected.get(key)
        if current is None or (
            int(getattr(event, "importance_score", 0) or 0),
            str(getattr(event, "title", "") or "").casefold(),
        ) > (
            int(getattr(current, "importance_score", 0) or 0),
            str(getattr(current, "title", "") or "").casefold(),
        ):
            selected[key] = event
    return list(selected.values())


def accuracy_for_event(event, birthday) -> str:
    """Return exact accuracy only for a matching, trusted P585 date."""
    if event.event_date == birthday and classify_event_date_precision(event) == EXACT_DAY:
        return EXACT_DATE
    return NEAR_DATE


def quality_score(event) -> int:
    """Provide a stable ranking signal after the hard quality filter."""
    score = int(getattr(event, "importance_score", 0) or 0) * 4
    precision = classify_event_date_precision(event)
    score += {EXACT_DAY: 5, DAY_LEVEL_MILESTONE: 2, UNKNOWN_PRECISION: 0}.get(precision, -8)
    if getattr(event, "description", None):
        score += 3
    if getattr(event, "category", None) == "sports":
        score -= 2
    return score