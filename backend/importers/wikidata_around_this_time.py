#!/usr/bin/env python
"""Import day-level, historically meaningful events for Around This Time."""

import argparse
import json
import logging
import re
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

import requests

from backend.config import config
from backend.database import initialize_database
from backend.models.around_this_time_event import AroundThisTimeEvent
from backend.repositories.around_this_time_repository import AroundThisTimeRepository

logger = logging.getLogger(__name__)

MIN_YEAR = 1950
MAX_YEAR = 2026
DAY_PRECISION = 11
DATE_PROPERTIES = ("P585", "P580", "P571")
DATE_PROPERTY_TYPES = {
    "P585": "point_in_time",
    "P580": "start_time",
    "P571": "inception",
}
PROPERTY_PRIORITY = {property_id: index for index, property_id in enumerate(DATE_PROPERTIES)}
DEFAULT_CHECKPOINT = Path("backend/data/import-state/wikidata_around_this_time.json")
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
GENERIC_TITLE_RE = re.compile(r"^(?:\d{4}|\d{4}s)$", re.IGNORECASE)
CALENDAR_TITLE_RE = re.compile(r"^(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+in\s+", re.IGNORECASE)
META_PREFIXES = ("list of ", "category:", "portal:", "outline of ", "index of ", "timeline of ")
WEAK_DESCRIPTIONS = {"event", "year", "calendar year", "decade", "period", "article", "historical event", "natural disaster"}
HASHTAG_RE = re.compile(r"(?:^|\s)#\w+\b")
VAGUE_TERMS = {"natural disaster", "workshop", "training program"}
GEOGRAPHIC_LOCATION_RE = re.compile(
    r"\b(?:square|street|avenue|park|plaza|road|building|station|city|town|municipality)\s+in\b",
    re.IGNORECASE,
)
GEOGRAPHIC_P31_IDS = {"Q174782", "Q79007", "Q515", "Q484170"}
ENTERTAINMENT_TERMS = (
    "film", "movie", "album", "song", "television series", "tv series",
    "television episode", "video game", "single (music)",
)
CATEGORY_TERMS = {
    "politics": ("election", "referendum", "treaty", "government", "independence", "inauguration", "coronation", "assassination"),
    "conflict": ("battle", "war", "conflict", "invasion", "siege", "coup", "rebellion", "revolution", "bombing", "massacre"),
    "science": ("scientific", "experiment", "discovery", "research"),
    "technology": ("technology", "invention", "computer", "internet", "software"),
    "space": ("space", "mission", "launch", "satellite", "astronaut", "rocket", "lunar", "planetary"),
    "disaster": ("earthquake", "tsunami", "hurricane", "flood", "wildfire", "explosion", "accident", "disaster", "crash"),
    "economy": ("economic", "economy", "currency", "market", "bank"),
    "social": ("civil rights", "protest", "demonstration", "reform", "strike", "social movement"),
    "culture": ("festival", "exhibition", "ceremony", "world's fair", "award", "prize", "cultural"),
    "sports": ("olympic", "world cup", "championship", "tournament", "final", "football match", "cricket match"),
}


def _build_date_range_query(start_date: date, end_date: date, property_id: str, limit: int = 1000) -> str:
    """Build one bounded property query with raw Wikibase precision."""
    if property_id not in DATE_PROPERTIES:
        raise ValueError(f"Unsupported date property: {property_id}")
    start = f"{start_date.isoformat()}T00:00:00Z"
    end = f"{end_date.isoformat()}T00:00:00Z"
    return f"""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX bd: <http://www.bigdata.com/rdf#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX schema: <http://schema.org/>
SELECT DISTINCT ?event ?eventLabel ?eventDescription ?eventDate ?datePrecision
    ?countryLabel ?type ?typeLabel ?article ?sitelinks
WHERE {{
    {{
        SELECT DISTINCT ?event ?eventDate ?datePrecision WHERE {{
            ?event wdt:{property_id} ?eventDate .
            ?event p:{property_id} ?statement .
            ?statement psv:{property_id} ?valueNode .
            ?valueNode wikibase:timePrecision ?datePrecision .
            FILTER (?datePrecision = {DAY_PRECISION})
            FILTER (?eventDate >= "{start}"^^xsd:dateTime && ?eventDate < "{end}"^^xsd:dateTime)
        }}
        LIMIT {int(limit)}
    }}
    OPTIONAL {{ ?event schema:description ?eventDescription . FILTER (LANG(?eventDescription) = "en") }}
    OPTIONAL {{ ?event wdt:P31 ?type . }}
    OPTIONAL {{ ?event wikibase:sitelinks ?sitelinks . }}
    OPTIONAL {{ ?article schema:about ?event ; schema:isPartOf <https://en.wikipedia.org/> . }}
    SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""


def build_year_query(year: int, property_id: str, limit: int = 1000) -> str:
    """Build one manageable year/property query with raw Wikibase precision."""
    return _build_date_range_query(date(year, 1, 1), date(year + 1, 1, 1), property_id, limit)


def build_month_query(year: int, month: int, property_id: str, limit: int = 1000) -> str:
    """Build a targeted month/property query for repairing sparse coverage."""
    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")
    start_date = date(year, month, 1)
    end_date = date(year + (month == 12), month % 12 + 1, 1)
    return _build_date_range_query(start_date, end_date, property_id, limit)


def _value(row: Mapping[str, Any], field: str) -> Optional[str]:
    value = row.get(field) or {}
    return value.get("value") if isinstance(value, Mapping) else None


def _qid(value: Optional[str]) -> Optional[str]:
    return value.rsplit("/", 1)[-1] if value else None


def _text(value: Optional[str]) -> str:
    return " ".join((value or "").split())


def sentence_case(value: Optional[str]) -> str:
    """Capitalize the first letter while preserving proper-noun casing."""
    text = _text(value)
    if not text:
        return ""
    match = re.search(r"[A-Za-z]", text)
    if not match:
        return text
    index = match.start()
    return text[:index] + text[index].upper() + text[index + 1:]


def parse_precision(value: Optional[str]) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def convert_results(data: Mapping[str, Any], property_id: str) -> List[Dict[str, Any]]:
    """Convert bindings while retaining only genuine Wikibase day precision."""
    records: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in data.get("results", {}).get("bindings", []):
        external_id = _qid(_value(row, "event"))
        title = _text(_value(row, "eventLabel"))
        raw_date = _value(row, "eventDate") or ""
        precision = parse_precision(_value(row, "datePrecision"))
        if not external_id or not title or title == external_id or precision != DAY_PRECISION:
            continue
        try:
            event_date = date.fromisoformat(raw_date[:10])
        except ValueError:
            continue
        key = (external_id, event_date.isoformat())
        record = records.setdefault(key, {
            "external_id": external_id,
            "event_date": event_date.isoformat(),
            "title": title,
            "description": _text(_value(row, "eventDescription")),
            "country": _text(_value(row, "countryLabel")) or None,
            "wikipedia_url": _value(row, "article"),
            "date_source": property_id,
            "date_precision": precision,
            "date_property_type": DATE_PROPERTY_TYPES[property_id],
            "sitelink_count": parse_precision(_value(row, "sitelinks")) or 0,
            "types": [],
            "type_ids": [],
        })
        type_id = _qid(_value(row, "type"))
        if type_id and type_id not in record["type_ids"]:
            record["type_ids"].append(type_id)
        type_label = _text(_value(row, "typeLabel"))
        if type_label and type_label not in record["types"]:
            record["types"].append(type_label)
    return list(records.values())


def normalize_category(event: Mapping[str, Any]) -> str:
    """Map title, description, and Wikidata type labels deterministically."""
    searchable = " ".join([event.get("title", ""), event.get("description", ""), *event.get("types", [])]).casefold()
    for category, terms in CATEGORY_TERMS.items():
        if any(term in searchable for term in terms):
            return category
    return "other"


def rejection_reason(event: Mapping[str, Any], category: str) -> Optional[str]:
    title = _text(event.get("title"))
    description = _text(event.get("description"))
    title_lower = title.casefold()
    description_lower = description.casefold().strip(" .;:")
    types = " ".join(event.get("types", [])).casefold()
    type_ids = {str(value).casefold() for value in event.get("type_ids", []) if value}
    if not title or GENERIC_TITLE_RE.fullmatch(title):
        return "generic year or decade title"
    if CALENDAR_TITLE_RE.match(title):
        return "generic calendar title"
    if GEOGRAPHIC_LOCATION_RE.search(title) or GEOGRAPHIC_LOCATION_RE.search(description):
        return "geographic location or structure"
    if type_ids & {value.casefold() for value in GEOGRAPHIC_P31_IDS}:
        return "geographic location or structure"
    if title_lower in WEAK_DESCRIPTIONS or HASHTAG_RE.search(title):
        return "generic or tagged title"
    if title_lower.startswith(META_PREFIXES) or any(prefix in title_lower for prefix in META_PREFIXES[1:]):
        return "metadata or navigation entity"
    searchable = f"{title_lower} {description_lower}"
    if description_lower in WEAK_DESCRIPTIONS or any(term in searchable for term in VAGUE_TERMS) or HASHTAG_RE.search(description):
        return "weak description"
    if not description or description_lower == title_lower:
        return "missing useful description"
    if len(description) < 20:
        return "description too short"
    entertainment = any(term in f"{title_lower} {description_lower} {types}" for term in ENTERTAINMENT_TERMS)
    if entertainment and category != "culture":
        return "ordinary entertainment"
    if category == "sports" and not any(term in f"{title_lower} {types}" for term in ("olympic", "world cup", "championship", "tournament")):
        return "routine sports event"
    if category == "other" and int(event.get("sitelink_count", 0) or 0) < 15:
        return "low-notability uncategorized event"
    if event.get("date_source") == "P571" and int(event.get("sitelink_count", 0) or 0) < 20:
        return "low-notability inception"
    return None


def calculate_importance(event: Mapping[str, Any], category: str) -> int:
    """Calculate a transparent 1-10 ranking signal; sitelinks are not history."""
    score = {"politics": 5, "conflict": 5, "science": 5, "space": 5, "disaster": 5, "economy": 4, "social": 4, "culture": 4, "sports": 4, "technology": 4, "other": 3}.get(category, 3)
    sitelinks = int(event.get("sitelink_count", 0) or 0)
    score += 3 if sitelinks >= 150 else 2 if sitelinks >= 75 else 1 if sitelinks >= 25 else 0
    if event.get("wikipedia_url"):
        score += 1
    if event.get("date_source") == "P585":
        score += 1
    return max(1, min(10, score))


def normalize_events(raw_events: Iterable[Dict[str, Any]]) -> Tuple[List[AroundThisTimeEvent], List[Dict[str, Any]]]:
    """Filter, classify, and deduplicate candidates by external ID plus date."""
    accepted: Dict[Tuple[str, str], AroundThisTimeEvent] = {}
    rejected: List[Dict[str, Any]] = []
    for event in raw_events:
        category = normalize_category(event)
        reason = rejection_reason(event, category)
        if reason:
            event["filter_reason"] = reason
            rejected.append(event)
            continue
        candidate = AroundThisTimeEvent(
            event_date=date.fromisoformat(event["event_date"]), title=sentence_case(event["title"]),
            description=sentence_case(event.get("description") or event["title"]), category=category,
            external_id=event["external_id"], source_name="Wikidata",
            source_url=f"https://www.wikidata.org/wiki/{event['external_id']}",
            wikipedia_url=event.get("wikipedia_url"), date_source=event.get("date_source"),
            date_precision=event["date_precision"], date_property_type=event.get("date_property_type"),
            sitelink_count=int(event.get("sitelink_count", 0) or 0),
            importance_score=calculate_importance(event, category),
        )
        key = (candidate.external_id, candidate.event_date.isoformat())
        current = accepted.get(key)
        if current is None or PROPERTY_PRIORITY.get(candidate.date_source, 99) < PROPERTY_PRIORITY.get(current.date_source, 99):
            accepted[key] = candidate
    return sorted(accepted.values(), key=lambda item: (item.event_date, -item.importance_score, item.external_id)), rejected


def merge_property_results(results: Iterable[Tuple[str, Sequence[Dict[str, Any]]]]) -> List[Dict[str, Any]]:
    """Merge the three property responses and prefer P585, then P580, then P571."""
    merged: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for property_id, records in results:
        for record in records:
            key = (record["external_id"], record["event_date"])
            current = merged.get(key)
            if current is None or PROPERTY_PRIORITY[property_id] < PROPERTY_PRIORITY.get(current["date_source"], 99):
                replacement = dict(record)
                replacement["types"] = sorted(set(current.get("types", [])) | set(record.get("types", []))) if current else list(record.get("types", []))
                replacement["type_ids"] = sorted(set(current.get("type_ids", [])) | set(record.get("type_ids", []))) if current else list(record.get("type_ids", []))
                merged[key] = replacement
            elif current:
                current["types"] = sorted(set(current.get("types", [])) | set(record.get("types", [])))
                current["type_ids"] = sorted(set(current.get("type_ids", [])) | set(record.get("type_ids", [])))
                if not current.get("description") and record.get("description"):
                    current["description"] = record["description"]
                current["sitelink_count"] = max(current.get("sitelink_count", 0), record.get("sitelink_count", 0))
    return list(merged.values())


def month_counts(events: Sequence[AroundThisTimeEvent]) -> Dict[int, int]:
    return {month: sum(event.event_date.month == month for event in events) for month in range(1, 13)}


def maximum_date_gap(events: Sequence[AroundThisTimeEvent]) -> int:
    dates = sorted({event.event_date for event in events})
    return max((right - left).days for left, right in zip(dates, dates[1:])) if len(dates) > 1 else 0


def coverage(events: Sequence[AroundThisTimeEvent], target: date) -> Dict[str, int]:
    distances = [abs((event.event_date - target).days) for event in events]
    return {f"plus_minus_{days}": sum(distance <= days for distance in distances) for days in (0, 7, 15, 30)}


class AroundThisTimeImporter:
    def __init__(self, session: Optional[requests.Session] = None, delay: float = config.wikidata_rate_limit, retries: int = 3, timeout: Optional[float] = None, limit: int = 1000, checkpoint_path: Path = DEFAULT_CHECKPOINT):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": config.wikidata_user_agent, "Accept": "application/sparql-results+json"})
        self.delay = max(0.0, float(delay))
        self.retries = max(1, int(retries))
        self.timeout = max(1.0, float(timeout if timeout is not None else config.wikidata_timeout))
        self.limit = max(1, int(limit))
        self.checkpoint_path = Path(checkpoint_path)

    def request(self, query: str) -> Mapping[str, Any]:
        last_error: Optional[BaseException] = None
        for attempt in range(1, self.retries + 1):
            response = None
            try:
                response = self.session.get(config.wikidata_endpoint, params={"query": query, "format": "json"}, timeout=(5, self.timeout))
                if response.status_code == 200:
                    return response.json()
                if response.status_code not in RETRYABLE_STATUS_CODES:
                    response.raise_for_status()
                last_error = requests.HTTPError(f"Wikidata returned HTTP {response.status_code}")
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if response is not None and response.status_code not in RETRYABLE_STATUS_CODES:
                    raise RuntimeError(f"Wikidata request failed: {exc}") from exc
            if attempt < self.retries:
                retry_after = response.headers.get("Retry-After") if response is not None else None
                try:
                    wait = float(retry_after) if retry_after else 2 ** (attempt - 1)
                except ValueError:
                    wait = 2 ** (attempt - 1)
                wait = min(60.0, max(0.0, wait))
                logger.warning("Wikidata request failed; retrying in %.1fs", wait)
                time.sleep(wait)
        raise RuntimeError(f"Wikidata request failed after {self.retries} attempts: {last_error}") from last_error

    def fetch_year(self, year: int) -> Tuple[List[AroundThisTimeEvent], List[Dict[str, Any]], Dict[str, int]]:
        if not MIN_YEAR <= year <= MAX_YEAR:
            raise ValueError(f"year must be between {MIN_YEAR} and {MAX_YEAR}")
        property_results = []
        raw_counts = {"raw_fetched": 0, "day_precision_valid": 0}
        for index, property_id in enumerate(DATE_PROPERTIES):
            response = self.request(build_year_query(year, property_id, self.limit))
            raw_counts["raw_fetched"] += len(response.get("results", {}).get("bindings", []))
            records = convert_results(response, property_id)
            property_results.append((property_id, records))
            raw_counts[property_id] = len(records)
            raw_counts["day_precision_valid"] += len(records)
            if index < len(DATE_PROPERTIES) - 1 and self.delay:
                time.sleep(self.delay)
        accepted, rejected = normalize_events(merge_property_results(property_results))
        return accepted, rejected, raw_counts

    def fetch_month(self, year: int, month: int) -> Tuple[List[AroundThisTimeEvent], List[Dict[str, Any]], Dict[str, int]]:
        if not MIN_YEAR <= year <= MAX_YEAR:
            raise ValueError(f"year must be between {MIN_YEAR} and {MAX_YEAR}")
        if not 1 <= month <= 12:
            raise ValueError("month must be between 1 and 12")
        property_results = []
        raw_counts = {"raw_fetched": 0, "day_precision_valid": 0}
        for index, property_id in enumerate(DATE_PROPERTIES):
            response = self.request(build_month_query(year, month, property_id, self.limit))
            raw_counts["raw_fetched"] += len(response.get("results", {}).get("bindings", []))
            records = convert_results(response, property_id)
            property_results.append((property_id, records))
            raw_counts[property_id] = len(records)
            raw_counts["day_precision_valid"] += len(records)
            if index < len(DATE_PROPERTIES) - 1 and self.delay:
                time.sleep(self.delay)
        accepted, rejected = normalize_events(merge_property_results(property_results))
        return accepted, rejected, raw_counts

    def load_checkpoint(self) -> Set[int]:
        try:
            payload = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
            return {int(value) for value in payload.get("completed_years", [])}
        except (OSError, ValueError, TypeError):
            return set()

    def save_checkpoint(self, completed_years: Set[int]) -> None:
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.checkpoint_path.with_suffix(self.checkpoint_path.suffix + ".tmp")
        temporary.write_text(json.dumps({"completed_years": sorted(completed_years)}, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.checkpoint_path)

    def run(self, years: Iterable[int], commit: bool = False, resume: bool = True) -> Dict[str, Any]:
        completed = self.load_checkpoint() if commit and resume else set()
        summary: Dict[str, Any] = {"years_attempted": 0, "years_completed": 0, "years_failed": [], "fetched": 0, "accepted": 0, "rejected": 0, "inserted": 0, "updated": 0, "by_property": Counter(), "by_month": Counter(), "reports": {}}
        for year in years:
            if year in completed:
                continue
            summary["years_attempted"] += 1
            try:
                accepted, rejected, property_counts = self.fetch_year(year)
                summary["fetched"] += property_counts["raw_fetched"]
                summary["accepted"] += len(accepted)
                summary["rejected"] += len(rejected)
                summary["by_property"].update(property_counts)
                summary["by_month"].update(month_counts(accepted))
                report = {"year": year, "fetched": property_counts["raw_fetched"], "day_precision_valid": property_counts["day_precision_valid"], "accepted": len(accepted), "rejected": len(rejected), "P585": property_counts.get("P585", 0), "P580": property_counts.get("P580", 0), "P571": property_counts.get("P571", 0), "unique_dates": len({event.event_date for event in accepted}), "monthly_counts": month_counts(accepted), "maximum_date_gap": maximum_date_gap(accepted), "coverage_may_9": coverage(accepted, date(year, 5, 9))}
                summary["reports"][year] = report
                if commit:
                    persistence = AroundThisTimeRepository.save(accepted)
                    summary["inserted"] += persistence["inserted"]
                    summary["updated"] += persistence["updated"]
                    completed.add(year)
                    self.save_checkpoint(completed)
                summary["years_completed"] += 1
                print(f"[{year}] fetched={report['fetched']} accepted={report['accepted']} rejected={report['rejected']} unique_dates={report['unique_dates']} max_gap={report['maximum_date_gap']} {'saved' if commit else 'dry-run'}")
                print("  monthly=" + ", ".join(f"{month:02d}:{count}" for month, count in report["monthly_counts"].items()))
            except Exception as exc:
                summary["years_failed"].append(year)
                logger.error("[%s] failed: %s", year, exc)
        return summary


def _year_arguments(parser: argparse.ArgumentParser, args: argparse.Namespace) -> Tuple[int, int]:
    if args.year is not None and (args.year_from is not None or args.year_to is not None):
        parser.error("--year cannot be combined with --year-from/--year-to")
    if args.year is not None:
        start = end = args.year
    else:
        start = args.year_from if args.year_from is not None else MIN_YEAR
        end = args.year_to if args.year_to is not None else (start if args.year_from is not None else MAX_YEAR)
    if not MIN_YEAR <= start <= end <= MAX_YEAR:
        parser.error(f"years must be between {MIN_YEAR} and {MAX_YEAR}")
    return start, end


def main() -> None:
    parser = argparse.ArgumentParser(description="Import day-level Around This Time events from Wikidata.")
    parser.add_argument("--repair-coverage", action="store_true", help="Fetch one month for targeted sparse-coverage repair")
    parser.add_argument("--year", type=int, help="Import one year")
    parser.add_argument("--month", type=int, help="Month for --repair-coverage")
    parser.add_argument("--year-from", type=int, help="First year in a future import range")
    parser.add_argument("--year-to", type=int, help="Last year in a future import range")
    parser.add_argument("--limit", type=int, default=100, help="Maximum records per date property")
    parser.add_argument("--delay", type=float, default=config.wikidata_rate_limit, help="Delay between property requests")
    parser.add_argument("--timeout", type=float, default=None, help="Per-request read timeout")
    parser.add_argument("--retries", type=int, default=3, help="Maximum attempts per request")
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT, help="Year checkpoint JSON path")
    parser.add_argument("--no-resume", action="store_true", help="Ignore completed years")
    parser.add_argument("--commit", action="store_true", help="Persist accepted records; default is dry-run")
    parser.add_argument("--dry-run", action="store_true", help="Explicitly request no database writes")
    parser.add_argument("--clear-db", action="store_true", help="Delete all existing Around This Time records before importing")
    args = parser.parse_args()
    if args.commit and args.dry_run:
        parser.error("--commit and --dry-run are mutually exclusive")
    if args.repair_coverage:
        if args.year is None or args.month is None or args.year_from is not None or args.year_to is not None:
            parser.error("--repair-coverage requires --year and --month only")
        if not MIN_YEAR <= args.year <= MAX_YEAR or not 1 <= args.month <= 12:
            parser.error(f"repair year must be between {MIN_YEAR} and {MAX_YEAR}, and month must be 1-12")
        initialize_database()
        if args.clear_db:
            print(f"Cleared records: {AroundThisTimeRepository.clear()}")
        importer = AroundThisTimeImporter(delay=args.delay, retries=args.retries, timeout=args.timeout, limit=args.limit, checkpoint_path=args.checkpoint)
        accepted, rejected, property_counts = importer.fetch_month(args.year, args.month)
        print(f"Repair dry-run={not args.commit}: year={args.year} month={args.month} fetched={property_counts['raw_fetched']} accepted={len(accepted)} rejected={len(rejected)}")
        for event in accepted:
            print(f"  {event.event_date.isoformat()} | {event.external_id} | {event.date_source} | {event.category} | {event.title}")
        if args.commit:
            print("Persistence:", AroundThisTimeRepository.save(accepted))
        return
    if args.month is not None:
        parser.error("--month can only be used with --repair-coverage")
    start, end = _year_arguments(parser, args)
    initialize_database()
    if args.clear_db:
        print(f"Cleared records: {AroundThisTimeRepository.clear()}")
    importer = AroundThisTimeImporter(delay=args.delay, retries=args.retries, timeout=args.timeout, limit=args.limit, checkpoint_path=args.checkpoint)
    summary = importer.run(range(start, end + 1), commit=args.commit, resume=not args.no_resume and not args.clear_db)
    print("Summary:", "; ".join(f"{key}={value}" for key, value in summary.items() if key not in {"reports", "by_property", "by_month"}))
    print("Property counts:", dict(summary["by_property"]))
    if summary["years_failed"]:
        print("Failed years:", ", ".join(map(str, summary["years_failed"])))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    main()
