"""Import a bounded, resumable set of notable birthdays from Wikidata."""

from __future__ import annotations

import argparse
import calendar
import json
import logging
import os
import sys
import time
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import config
from backend.models.person import FamousPerson
from backend.repositories.person_repository import PersonRepository

logger = logging.getLogger(__name__)
DEFAULT_CHECKPOINT = PROJECT_ROOT / "backend" / "data" / "import-state" / "wikidata_people.json"
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
OCCUPATION_PRIORITY = {
    "Actor": 1,
    "Cricketer": 2,
    "Scientist": 3,
    "Inventor": 4,
    "Entrepreneur": 5,
    "Singer": 6,
    "Athlete": 7,
    "Footballer": 8,
    "Basketball Player": 9,
    "Tennis Player": 10,
    "Artist": 11,
    "Astronaut": 12,
    "Writer": 13,
    "Musician": 14,
    "Director": 15,
}
OCCUPATION_PATTERNS = (
    ("Actor", ("actor", "actress")),
    ("Cricketer", ("cricketer", "cricket player")),
    ("Scientist", ("scientist", "physicist", "chemist", "biologist", "mathematician", "astronomer")),
    ("Inventor", ("inventor",)),
    ("Entrepreneur", ("entrepreneur", "businessperson", "business executive", "company founder")),
    ("Singer", ("singer-songwriter", "singer")),
    ("Athlete", ("athlete",)),
    ("Footballer", ("association football player", "footballer")),
    ("Basketball Player", ("basketball player",)),
    ("Tennis Player", ("tennis player",)),
    ("Artist", ("visual artist", "painter", "sculptor", "artist")),
    ("Astronaut", ("astronaut", "cosmonaut")),
    ("Writer", ("writer", "author", "novelist", "poet", "playwright")),
    ("Musician", ("musician", "instrumentalist", "composer")),
    ("Director", ("film director", "television director", "theatre director")),
)


def _retry_after_seconds(response: requests.Response) -> Optional[float]:
    """Read a server-directed retry delay, when supplied."""
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            return max(0.0, (retry_at - datetime.now(retry_at.tzinfo)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def birthday_buckets(month: Optional[int] = None, day: Optional[int] = None) -> List[Tuple[int, int]]:
    """Return valid calendar month/day pairs, including February 29."""
    if month is not None:
        if not 1 <= month <= 12:
            raise ValueError("month must be between 1 and 12")
        if day is not None:
            if not 1 <= day <= 31:
                raise ValueError("day must be between 1 and 31")
            try:
                date(2000, month, day)
            except ValueError as exc:
                raise ValueError("month/day is not a valid calendar date") from exc
            return [(month, day)]
        return [(month, value) for value in range(1, calendar.monthrange(2000, month)[1] + 1)]
    if day is not None:
        raise ValueError("day requires month")
    return [
        (current_month, current_day)
        for current_month in range(1, 13)
        for current_day in range(1, calendar.monthrange(2000, current_month)[1] + 1)
    ]


def build_query(month: int, day: int, limit: int = 100) -> str:
    """Build a bounded exact-birthday query for humans with day precision."""
    return f"""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX schema: <http://schema.org/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT DISTINCT ?person ?personLabel ?birthDate ?article ?sitelinks ?occupationLabel
WHERE {{
    ?person wdt:P31 wd:Q5 ;
        wdt:P569 ?birthDate .
    FILTER(YEAR(?birthDate) >= 1 && CONTAINS(STR(?birthDate), "-{month:02d}-{day:02d}T"))
    ?person rdfs:label ?personLabel .
    FILTER(LANG(?personLabel) = "en")
    OPTIONAL {{
        ?person wdt:P106 ?occupation .
        ?occupation rdfs:label ?occupationLabel .
        FILTER(LANG(?occupationLabel) = "en")
    }}
    ?article schema:about ?person ;
             schema:isPartOf <https://en.wikipedia.org/> .
    OPTIONAL {{ ?person wikibase:sitelinks ?sitelinks . }}
}}
LIMIT {int(limit)}
"""


def _value(row: Dict[str, Any], key: str) -> Optional[str]:
    value = row.get(key)
    return value.get("value") if isinstance(value, dict) else None


def _qid(uri: Optional[str]) -> Optional[str]:
    value = uri.rsplit("/", 1)[-1] if uri else ""
    return value if value.startswith("Q") and value[1:].isdigit() else None


def _parse_exact_date(binding: Optional[Dict[str, Any]]) -> Optional[date]:
    if not binding:
        return None
    datatype = binding.get("datatype", "")
    if not (datatype.endswith("#date") or datatype.endswith("#dateTime")):
        return None
    value = binding.get("value")
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return None


def _first_label(values: Iterable[Optional[str]], maximum: int = 2) -> Optional[str]:
    labels = []
    for value in values:
        if value and value not in labels:
            labels.append(value)
        if len(labels) >= maximum:
            break
    return ", ".join(labels) if labels else None


def normalize_occupation(labels: Iterable[Optional[str]] | Optional[str]) -> Tuple[Optional[str], Optional[int]]:
    """Return the highest-priority conservative occupation match."""
    if isinstance(labels, str) or labels is None:
        labels = [labels]
    matches = []
    for label in labels:
        text = " ".join((label or "").casefold().split())
        if "american football" in text:
            continue
        for normalized, patterns in OCCUPATION_PATTERNS:
            if any(pattern in text for pattern in patterns):
                matches.append((OCCUPATION_PRIORITY[normalized], normalized))
                break
    if not matches:
        return None, None
    priority, normalized = min(matches)
    return normalized, priority


def ranking_key(person: FamousPerson, selected: Sequence[FamousPerson] = ()) -> Tuple[float, int, int, str, str]:
    """Balance preferred occupation, fame, and soft repeated-category penalty."""
    priority = OCCUPATION_PRIORITY.get(person.occupation or "", 99)
    repeat_count = sum(candidate.occupation == person.occupation for candidate in selected) if person.occupation else 0
    occupation_bonus = max(0, 16 - priority) * 2
    diversity_penalty = min(repeat_count, 4) * 1.5
    return (-(person.sitelinks + occupation_bonus - diversity_penalty), priority, -person.notability_score, person.name.casefold(), person.wikidata_id or "")


def select_people(people: Sequence[FamousPerson], limit: int) -> List[FamousPerson]:
    """Select a deterministic, occupation-diverse prefix without hard quotas."""
    remaining = sorted(people, key=lambda person: ranking_key(person))
    selected: List[FamousPerson] = []
    selected_categories: Set[str] = set()
    for candidate in remaining:
        category = candidate.occupation or "Other"
        if category not in selected_categories:
            selected.append(candidate)
            selected_categories.add(category)
            if len(selected) >= limit:
                return selected
    remaining = [candidate for candidate in remaining if candidate not in selected]
    while remaining and len(selected) < limit:
        candidate = min(remaining, key=lambda person: ranking_key(person, selected))
        selected.append(candidate)
        remaining.remove(candidate)
    return selected


def calculate_notability(
    sitelinks: int,
    occupation: Optional[str],
    description: Optional[str],
    article: Optional[str],
) -> int:
    score = 2
    for threshold, points in ((150, 5), (100, 4), (50, 3), (20, 2), (5, 1)):
        if sitelinks >= threshold:
            score += points
            break
    if occupation:
        score += 1
    if description:
        score += 1
    if article:
        score += 1
    return max(1, min(score, 10))


def parse_people(
    data: Dict[str, Any],
    month: Optional[int] = None,
    day: Optional[int] = None,
) -> List[FamousPerson]:
    """Map valid Wikidata bindings to the existing FamousPerson model."""
    rows_by_qid: Dict[str, Dict[str, Any]] = {}
    for row in data.get("results", {}).get("bindings", []):
        qid = _qid(_value(row, "person"))
        name = _value(row, "personLabel")
        birth_date = _parse_exact_date(row.get("birthDate"))
        if (
            not qid
            or not name
            or not birth_date
            or (month and birth_date.month != month)
            or (day and birth_date.day != day)
        ):
            continue
        current = rows_by_qid.setdefault(qid, {"row": row, "occupations": []})
        current["row"] = row
        occupation_label = _value(row, "occupationLabel")
        if occupation_label and occupation_label not in current["occupations"]:
            current["occupations"].append(occupation_label)
    people: Dict[str, FamousPerson] = {}
    for qid, grouped in rows_by_qid.items():
        row = grouped["row"]
        birth_date = _parse_exact_date(row.get("birthDate"))
        if not birth_date or (month and birth_date.month != month) or (day and birth_date.day != day):
            continue
        name = _value(row, "personLabel")
        occupation, _ = normalize_occupation(grouped["occupations"])
        try:
            sitelinks = max(0, int(_value(row, "sitelinks") or 0))
        except ValueError:
            sitelinks = 0
        description = _value(row, "description")
        article = _value(row, "article")
        people[qid] = FamousPerson(
            name=name,
            birth_date=birth_date,
            occupation=occupation,
            country=_value(row, "countryLabel"),
            description=description,
            wikidata_id=qid,
            wikipedia_url=article,
            image_url=_value(row, "image"),
            sitelinks=sitelinks,
            notability_score=calculate_notability(sitelinks, occupation, description, article),
            source="Wikidata",
            source_url=f"https://www.wikidata.org/wiki/{qid}",
        )
    return sorted(
        people.values(),
        key=lambda person: (-person.sitelinks, -person.notability_score, person.name.casefold(), person.wikidata_id or ""),
    )


class WikidataPeopleImporter:
    """Fetch and persist people one birthday bucket at a time."""

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        checkpoint_path: Path = DEFAULT_CHECKPOINT,
        delay: float = 1.0,
        retries: Optional[int] = None,
        timeout: Optional[float] = None,
        fetch_limit: int = 100,
    ):
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": config.wikidata_user_agent,
                "Accept": "application/sparql-results+json",
            }
        )
        self.checkpoint_path = Path(checkpoint_path)
        self.delay = max(0.0, delay)
        self.retries = max(1, retries if retries is not None else 1)
        self.timeout = max(1.0, timeout if timeout is not None else min(config.wikidata_timeout, 20))
        self.fetch_limit = max(1, min(500, fetch_limit))
        self.lock_path = self.checkpoint_path.with_suffix(".lock")

    def fetch(self, month: int, day: int, limit: Optional[int] = None) -> List[FamousPerson]:
        query = build_query(month, day, limit or self.fetch_limit)
        for attempt in range(1, self.retries + 1):
            response = None
            try:
                response = self.session.get(
                    config.wikidata_endpoint,
                    params={"query": query, "format": "json"},
                    timeout=(5, self.timeout),
                )
                if response.status_code == 200:
                    return parse_people(response.json(), month, day)
                if response.status_code not in RETRY_STATUS_CODES:
                    response.raise_for_status()
                error = requests.HTTPError(
                    f"Wikidata returned HTTP {response.status_code}"
                )
            except requests.RequestException as exc:
                error = exc
                if response is not None and response.status_code not in RETRY_STATUS_CODES:
                    raise RuntimeError(
                        f"Unable to query Wikidata for {month:02d}-{day:02d}: {error}"
                    ) from error
            if attempt == self.retries:
                raise RuntimeError(
                    f"Unable to query Wikidata for {month:02d}-{day:02d}: {error}"
                ) from error
            server_wait = _retry_after_seconds(response) if response is not None else None
            wait = min(300.0, server_wait if server_wait is not None else 2 ** (attempt - 1))
            logger.warning(
                "Wikidata request failed for %02d-%02d (HTTP %s); retrying in %.1fs",
                month,
                day,
                response.status_code if response is not None else "network error",
                wait,
            )
            time.sleep(wait)
        return []

    def load_checkpoint(self) -> Set[str]:
        try:
            payload = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
            return set(payload.get("completed", []))
        except (OSError, json.JSONDecodeError):
            return set()

    def mark_completed(self, bucket: str, completed: Set[str]) -> None:
        completed.add(bucket)
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            failed = json.loads(self.checkpoint_path.read_text(encoding="utf-8")).get("failed", [])
        except (OSError, json.JSONDecodeError):
            failed = []
        failed = [value for value in failed if value != bucket]
        temporary = self.checkpoint_path.with_name(f"{self.checkpoint_path.name}.{os.getpid()}.tmp")
        state = {"completed": sorted(completed)}
        if failed:
            state["failed"] = failed
        temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.checkpoint_path)

    def mark_failed(self, bucket: str, failed: Set[str]) -> None:
        """Persist a failed bucket without marking it complete."""
        failed.add(bucket)
        state = {"completed": sorted(self.load_checkpoint()), "failed": sorted(failed)}
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.checkpoint_path.with_name(f"{self.checkpoint_path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.checkpoint_path)

    def run(
        self,
        buckets: Sequence[Tuple[int, int]],
        limit: int,
        commit: bool = False,
        resume: bool = True,
    ) -> Dict[str, int]:
        if not commit:
            return self._run(buckets, limit, commit=False, resume=resume)
        try:
            descriptor = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(descriptor, "w", encoding="ascii") as handle:
                handle.write(str(os.getpid()))
        except FileExistsError as exc:
            raise RuntimeError(
                f"Another importer is already running ({self.lock_path}). "
                "Stop it before starting another commit."
            ) from exc
        try:
            return self._run(buckets, limit, commit=True, resume=resume)
        finally:
            try:
                self.lock_path.unlink()
            except FileNotFoundError:
                pass

    def _run(
        self,
        buckets: Sequence[Tuple[int, int]],
        limit: int,
        commit: bool = False,
        resume: bool = True,
    ) -> Dict[str, int]:
        completed = self.load_checkpoint() if resume and commit else set()
        failed: Set[str] = set()
        if resume and commit:
            try:
                failed = set(json.loads(self.checkpoint_path.read_text(encoding="utf-8")).get("failed", []))
            except (OSError, json.JSONDecodeError):
                failed = set()
        summary = {
            "buckets_attempted": 0,
            "buckets_completed": 0,
            "fetched": 0,
            "validated": 0,
            "inserted": 0,
            "updated": 0,
            "duplicates": 0,
            "errors": 0,
            "failed_buckets": [],
        }
        for index, (month, day) in enumerate(buckets, 1):
            bucket = f"{month:02d}-{day:02d}"
            if bucket in completed:
                continue
            summary["buckets_attempted"] += 1
            try:
                candidates = self.fetch(month, day, self.fetch_limit)
                people = select_people(candidates, limit)
                summary["fetched"] += len(candidates)
                summary["validated"] += len(candidates)
                if commit:
                    existing_ids = {
                        person.wikidata_id
                        for person in people
                        if person.wikidata_id and PersonRepository.get_by_wikidata_id(person.wikidata_id)
                    }
                    PersonRepository.save(people)
                    self.mark_completed(bucket, completed)
                    summary["updated"] += len(existing_ids)
                    summary["duplicates"] += len(existing_ids)
                    summary["inserted"] += len(people) - len(existing_ids)
                summary["buckets_completed"] += 1
                mode = "saved" if commit else "would-insert"
                print(f"[{index:03d}/{len(buckets)}] {bucket} fetched={self.fetch_limit} valid={len(candidates)} selected={len(people)} {mode}")
                if self.delay and index < len(buckets):
                    time.sleep(self.delay)
            except Exception:
                summary["errors"] += 1
                summary["failed_buckets"].append(bucket)
                if commit:
                    self.mark_failed(bucket, failed)
                logger.error("Birthday bucket %s failed; continuing with remaining buckets", bucket)
        return summary


def print_preview(people: Sequence[FamousPerson], month: int, day: int, limit: int) -> None:
    print(f"Birthday: {month:02d}-{day:02d}")
    print(f"Retrieved: {len(people)}")
    print(f"Valid exact dates: {len(people)}")
    print(f"English Wikipedia: {sum(bool(person.wikipedia_url) for person in people)}")
    print(f"Would insert: {min(limit, len(people))}")
    print("\nTop candidates:")
    for index, person in enumerate(people[:limit], 1):
        print(
            f"{index}. {person.name} - born {person.birth_date.year} - "
            f"{person.occupation or 'occupation unavailable'} - sitelinks {person.sitelinks}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import notable Wikidata people by exact birthday.")
    parser.add_argument("--month", type=int, help="Birthday month")
    parser.add_argument("--day", type=int, help="Birthday day; requires --month")
    parser.add_argument("--month-day", help="Compatibility form for an exact birthday, such as 05-09")
    parser.add_argument("--all", action="store_true", help="Process all 366 valid birthday buckets")
    parser.add_argument("--status", action="store_true", help="Show current famous_people coverage")
    parser.add_argument("--limit-per-birthday", "--limit", type=int, default=25)
    parser.add_argument("--fetch-limit-per-birthday", type=int, default=100)
    parser.add_argument("--delay", type=float, default=config.wikidata_rate_limit)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--commit", action="store_true", help="Write to famous_people; default is dry-run")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to SQLite (default)")
    parser.add_argument("--no-resume", action="store_true", help="Ignore completed checkpoint buckets")
    args = parser.parse_args()
    if args.limit_per_birthday < 1:
        parser.error("--limit-per-birthday must be positive")
    if args.fetch_limit_per_birthday < args.limit_per_birthday:
        parser.error("--fetch-limit-per-birthday must be at least --limit-per-birthday")
    if args.dry_run and args.commit:
        parser.error("--dry-run and --commit are mutually exclusive")
    if args.status:
        from backend.database import fetch_all, fetch_one

        total = fetch_one("SELECT COUNT(*) AS count FROM famous_people")["count"]
        dates = fetch_all("SELECT strftime('%m-%d', birth_date) AS birthday, COUNT(*) AS count FROM famous_people GROUP BY birthday")
        print(f"Total people in SQLite: {total}")
        print(f"Birthdays covered: {len(dates)}")
        print(f"Birthdays without candidates: {366 - len(dates)}")
        return
    if args.month_day and (args.month is not None or args.day is not None):
        parser.error("--month-day cannot be combined with --month or --day")
    if args.month_day:
        try:
            args.month, args.day = (int(value) for value in args.month_day.split("-", 1))
        except (TypeError, ValueError):
            parser.error("--month-day must use MM-DD")
    if not args.all and args.month is None:
        parser.error("provide --month, --month-day, or --all")
    try:
        buckets = birthday_buckets(args.month, args.day)
    except ValueError as exc:
        parser.error(str(exc))
    importer = WikidataPeopleImporter(
        checkpoint_path=args.checkpoint,
        delay=args.delay,
        fetch_limit=args.fetch_limit_per_birthday,
    )
    if len(buckets) == 1:
        candidates = importer.fetch(*buckets[0])
        people = select_people(candidates, args.limit_per_birthday)
        print_preview(people, *buckets[0], args.limit_per_birthday)
        if args.commit:
            completed = importer.load_checkpoint() if not args.no_resume else set()
            PersonRepository.save(people)
            importer.mark_completed(f"{buckets[0][0]:02d}-{buckets[0][1]:02d}", completed)
        return
    summary = importer.run(
        buckets,
        args.limit_per_birthday,
        commit=args.commit,
        resume=not args.no_resume,
    )
    print("Summary:", "; ".join(f"{key}={value}" for key, value in summary.items() if key != "failed_buckets"))
    print("Failed birthdays:", ", ".join(summary["failed_buckets"]) or "none")


if __name__ == "__main__":
    main()
