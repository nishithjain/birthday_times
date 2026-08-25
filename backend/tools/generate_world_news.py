"""Generate static yearly world-news datasets from SQLite historical events."""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import config
from backend.models.event import HistoricalEvent
from backend.repositories.event_repository import EventRepository

FIRST_YEAR = 1950
LAST_YEAR = 2026
CANDIDATE_LIMIT = 10

CATEGORY_MAP = {
    "war_conflict": "world",
    "politics": "politics",
    "science_space": "science",
    "technology": "technology",
    "culture": "culture",
    "entertainment": "culture",
    "disaster": "disaster",
    "achievement": "achievement",
    "sports": "achievement",
    "society": "society",
    "historical_event": "world",
    "unknown": "other",
}


def normalize_title(title: str) -> str:
    """Normalize a title for conservative duplicate detection."""
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def headline_text(title: str) -> str:
    """Return a short, deterministic headline without adding facts."""
    words = (title or "").strip().split()
    if len(words) <= 12:
        return " ".join(words)
    return " ".join(words[:12]).rstrip(" ,:;-")


def _country_value(country: Optional[str]) -> List[str]:
    if not country:
        return []
    return [part.strip() for part in re.split(r"[,;]", country) if part.strip()]


def _stable_id(event: HistoricalEvent) -> str:
    return event.wikidata_id or normalize_title(event.title).replace(" ", "_")


def _is_duplicate(event: HistoricalEvent, selected: Sequence[HistoricalEvent]) -> bool:
    event_title = normalize_title(event.title)
    event_tokens = set(event_title.split())
    for existing in selected:
        if event.wikidata_id and event.wikidata_id == existing.wikidata_id:
            return True
        if event_title == normalize_title(existing.title):
            return True
        if abs((event.event_date - existing.event_date).days) <= 3:
            existing_tokens = set(normalize_title(existing.title).split())
            if event_tokens and existing_tokens:
                overlap = len(event_tokens & existing_tokens) / max(len(event_tokens), len(existing_tokens))
                if overlap >= 0.8:
                    return True
    return False


class WorldNewsBuilder:
    """Build ranked, reviewable yearly payloads from event records."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self.output_dir = output_dir or PROJECT_ROOT / "backend" / "data" / "world_news"

    def select_events(self, events: Iterable[HistoricalEvent]) -> Tuple[List[HistoricalEvent], int]:
        candidates = sorted(
            events,
            key=lambda event: (-int(event.importance_score or 0), event.event_date, normalize_title(event.title), _stable_id(event)),
        )
        unique: List[HistoricalEvent] = []
        duplicates = 0
        for event in candidates:
            if _is_duplicate(event, unique):
                duplicates += 1
            else:
                unique.append(event)

        # Take the strongest item from each available category first, then fill by rank.
        selected: List[HistoricalEvent] = []
        remaining = list(unique)
        while remaining and len(selected) < CANDIDATE_LIMIT:
            category = next((CATEGORY_MAP.get(item.category, "other") for item in remaining if CATEGORY_MAP.get(item.category, "other") not in {CATEGORY_MAP.get(chosen.category, "other") for chosen in selected}), None)
            if category is None:
                selected.extend(remaining[: CANDIDATE_LIMIT - len(selected)])
                break
            choice_index = next(index for index, item in enumerate(remaining) if CATEGORY_MAP.get(item.category, "other") == category)
            selected.append(remaining.pop(choice_index))
        selected.sort(key=lambda event: (-int(event.importance_score or 0), event.event_date, normalize_title(event.title), _stable_id(event)))
        return selected, duplicates

    def build_payload(self, year: int, events: Iterable[HistoricalEvent]) -> Dict[str, Any]:
        selected, duplicates = self.select_events(events)
        today = date.today()
        partial = year == today.year
        headlines = []
        for event in selected:
            category = CATEGORY_MAP.get(event.category, "other")
            headlines.append({
                "id": _stable_id(event),
                "displayText": headline_text(event.title),
                "eventDate": event.event_date.isoformat(),
                "category": category,
                "sourceCategory": event.category,
                "country": _country_value(event.country),
                "importance": int(event.importance_score or 0),
                "sourceEventId": event.wikidata_id,
                "sourceTitle": event.title,
                "description": event.description,
                "source": {"name": event.source, "url": event.source_url or event.wikipedia_url},
            })
        return {
            "schemaVersion": 1,
            "year": year,
            "sectionTitle": "NEWS AROUND THE WORLD",
            "headlineTitle": f"Making Headlines In {year}",
            "reviewStatus": "generated",
            "generatedAt": datetime.now().astimezone().isoformat(),
            "isPartialYear": partial,
            "throughDate": today.isoformat() if partial else None,
            "displayLimit": 5,
            "insufficientData": len(headlines) < CANDIDATE_LIMIT,
            "duplicatesRemoved": duplicates,
            "categoryDistribution": dict(Counter(item["category"] for item in headlines)),
            "headlines": headlines,
        }

    def generate_year(self, year: int, dry_run: bool = False, force: bool = False) -> Dict[str, Any]:
        if not FIRST_YEAR <= year <= LAST_YEAR:
            raise ValueError(f"year must be between {FIRST_YEAR} and {LAST_YEAR}")
        events = EventRepository.get_by_year(year)
        payload = self.build_payload(year, events)
        path = self.output_dir / f"{year:04d}.json"
        action = "would write" if dry_run else "wrote"
        if path.exists() and not force:
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                existing = {}
            if existing.get("reviewStatus") in {"reviewed", "approved"}:
                return {"year": year, "status": f"skipped {existing['reviewStatus']}", "path": str(path), "payload": existing}
        if not dry_run:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        return {"year": year, "status": action, "path": str(path), "payload": payload}


def _years(args: argparse.Namespace) -> List[int]:
    if args.year is not None:
        return [args.year]
    if args.all or args.from_year is not None or args.to_year is not None:
        start = args.from_year if args.from_year is not None else FIRST_YEAR
        end = args.to_year if args.to_year is not None else LAST_YEAR
        if start > end:
            raise ValueError("from-year must not be greater than to-year")
        return list(range(start, end + 1))
    raise ValueError("specify --year, --from-year/--to-year, --all, or --status")


def print_status(builder: WorldNewsBuilder) -> None:
    years = list(range(FIRST_YEAR, LAST_YEAR + 1))
    files = {year: builder.output_dir / f"{year:04d}.json" for year in years}
    states = Counter()
    for path in files.values():
        if path.exists():
            try:
                states[json.loads(path.read_text(encoding="utf-8")).get("reviewStatus", "generated")] += 1
            except (OSError, json.JSONDecodeError):
                states["malformed"] += 1
    print("World news dataset status")
    print(f"Years expected: {FIRST_YEAR}-{LAST_YEAR}")
    print(f"Files found: {sum(path.exists() for path in files.values())}")
    print(f"Files missing: {sum(not path.exists() for path in files.values())}")
    print(f"Generated: {states['generated']}")
    print(f"Reviewed: {states['reviewed']}")
    print(f"Approved: {states['approved']}")
    print("\nDatabase event coverage:")
    insufficient = []
    for year in years:
        count = len(EventRepository.get_by_year(year))
        print(f"{year}: {count} events")
        if count < CANDIDATE_LIMIT:
            insufficient.append(year)
    print("\nYears with insufficient events:")
    print(", ".join(map(str, insufficient)) or "None")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate static world-news files from SQLite historical events.")
    parser.add_argument("--year", type=int)
    parser.add_argument("--from-year", type=int)
    parser.add_argument("--to-year", type=int)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    builder = WorldNewsBuilder()
    if args.status:
        print_status(builder)
        return
    try:
        years = _years(args)
        print("Generating world news")
        generated = skipped = insufficient = failed = 0
        for year in years:
            try:
                result = builder.generate_year(year, dry_run=args.dry_run, force=args.force)
                payload = result["payload"]
                if result["status"].startswith("skipped"):
                    skipped += 1
                else:
                    generated += 1
                    insufficient += int(payload.get("insufficientData", False))
                print(f"{year}: DB candidates: {len(EventRepository.get_by_year(year))}; selected: {len(payload.get('headlines', []))}; {result['status']}: {result['path']}")
            except Exception as exc:
                failed += 1
                print(f"{year}: FAILED: {exc}")
        print(f"\nSummary: Years requested: {len(years)}; Generated: {generated}; Skipped: {skipped}; Insufficient: {insufficient}; Failed: {failed}")
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
