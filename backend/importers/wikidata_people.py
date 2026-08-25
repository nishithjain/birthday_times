"""Import notable people with precise birthdays from Wikidata into SQLite."""

import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import config
from backend.database import fetch_all, fetch_one
from backend.models.person import FamousPerson
from backend.repositories.person_repository import PersonRepository


def build_query(month: int, day: Optional[int] = None, limit: int = 500) -> str:
    """Build a bounded Wikidata query for a month or exact month/day."""
    day_filter = f'FILTER(MONTH(?birthDate) = {month} && DAY(?birthDate) = {day})' if day else f'FILTER(MONTH(?birthDate) = {month})'
    return f"""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX bd: <http://www.bigdata.com/rdf#>
PREFIX schema: <http://schema.org/>
SELECT DISTINCT ?person ?personLabel ?birthDate ?deathDate ?occupationLabel
 ?countryLabel ?description ?article ?image ?sitelinks
WHERE {{
 ?person wdt:P569 ?birthDate .
 {day_filter}
 ?article schema:about ?person ; schema:isPartOf <https://en.wikipedia.org/> .
 OPTIONAL {{ ?person wdt:P570 ?deathDate . }}
 OPTIONAL {{ ?person wdt:P106 ?occupation . }}
 OPTIONAL {{ ?person wdt:P27 ?country . }}
 OPTIONAL {{ ?person wdt:P18 ?image . }}
 OPTIONAL {{ ?person wikibase:sitelinks ?sitelinks . }}
 SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
LIMIT {int(limit)}
"""


def _value(row: Dict[str, Any], key: str) -> Optional[str]:
    value = row.get(key)
    return value.get("value") if value else None


def _qid(uri: Optional[str]) -> Optional[str]:
    return uri.rsplit("/", 1)[-1] if uri else None


def calculate_notability(sitelinks: int, occupation: Optional[str], description: Optional[str], article: Optional[str], image: Optional[str]) -> int:
    score = 2
    if sitelinks >= 150: score += 5
    elif sitelinks >= 100: score += 4
    elif sitelinks >= 50: score += 3
    elif sitelinks >= 20: score += 2
    elif sitelinks >= 5: score += 1
    if occupation: score += 1
    if description: score += 1
    if article: score += 1
    if image: score += 1
    return max(1, min(score, 10))


def parse_people(data: Dict[str, Any]) -> List[FamousPerson]:
    people: Dict[str, FamousPerson] = {}
    for row in data.get("results", {}).get("bindings", []):
        qid = _qid(_value(row, "person"))
        birth_value = _value(row, "birthDate")
        name = _value(row, "personLabel")
        if not qid or not name or not birth_value:
            continue
        try:
            birth_date = datetime.fromisoformat(birth_value.replace("Z", "+00:00")).date()
        except ValueError:
            continue
        death_value = _value(row, "deathDate")
        death_date = None
        if death_value:
            try:
                death_date = datetime.fromisoformat(death_value.replace("Z", "+00:00")).date()
            except ValueError:
                pass
        sitelinks = int(_value(row, "sitelinks") or 0)
        occupation = _value(row, "occupationLabel")
        description = _value(row, "description")
        article = _value(row, "article")
        image = _value(row, "image")
        people[qid] = FamousPerson(
            name=name, birth_date=birth_date, death_date=death_date,
            occupation=occupation, country=_value(row, "countryLabel"),
            description=description, wikidata_id=qid, wikipedia_url=article,
            image_url=image, sitelinks=sitelinks,
            notability_score=calculate_notability(sitelinks, occupation, description, article, image),
            source="Wikidata", source_url=f"https://www.wikidata.org/wiki/{qid}",
        )
    return sorted(people.values(), key=lambda person: (-person.notability_score, person.name.lower(), person.wikidata_id or ""))


def fetch_people(month: int, day: Optional[int] = None, limit: int = 500) -> List[FamousPerson]:
    response = requests.get(config.wikidata_endpoint, params={"query": build_query(month, day, limit), "format": "json"}, headers={"User-Agent": config.wikidata_user_agent}, timeout=config.wikidata_timeout)
    response.raise_for_status()
    return parse_people(response.json())


def main() -> None:
    parser = argparse.ArgumentParser(description="Import notable Wikidata people by birthday.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--month-day", help="Exact month/day, such as 10-16")
    group.add_argument("--month", type=int)
    group.add_argument("--all", action="store_true")
    group.add_argument("--status", action="store_true")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.status:
        total = fetch_one("SELECT COUNT(*) AS count FROM famous_people")["count"]
        dates = fetch_all("SELECT strftime('%m-%d', birth_date) AS md, COUNT(*) AS count FROM famous_people GROUP BY md")
        print(f"Total people in SQLite: {total}")
        print(f"Dates with 5+ candidates: {sum(row['count'] >= 5 for row in dates)}")
        print(f"Dates with 1-4 candidates: {sum(1 <= row['count'] < 5 for row in dates)}")
        print(f"Dates with 0 candidates: {366 - len(dates)}")
        print(f"February 29 candidates: {next((row['count'] for row in dates if row['md'] == '02-29'), 0)}")
        return
    batches = [(args.month, None)] if args.month else []
    if args.month_day:
        month, day = map(int, args.month_day.split("-"))
        batches = [(month, day)]
    elif args.all:
        batches = [(month, None) for month in range(1, 13)]
    totals = [0, 0, 0]
    print("Importing notable people")
    for month, day in batches:
        people = fetch_people(month, day, args.limit)
        existing = {person.wikidata_id for person in (PersonRepository.get_by_month_day(month, day) if day else [])}
        if not args.dry_run:
            PersonRepository.save(people)
        new_count = sum(person.wikidata_id not in existing for person in people)
        totals[0] += len(people); totals[1] += new_count; totals[2] += len(people) - new_count
        label = f"{month:02d}-{day:02d}" if day else datetime(2000, month, 1).strftime("%B")
        print(f"{label} ... {len(people)} candidates / {new_count} inserted / {len(people) - new_count} existing")
    print(f"Summary: Candidates: {totals[0]}; Inserted: {totals[1]}; Existing: {totals[2]}")


if __name__ == "__main__":
    main()
