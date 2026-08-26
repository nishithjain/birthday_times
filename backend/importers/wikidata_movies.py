"""Import normalized movie metadata from Wikidata into SQLite."""

import argparse
import json
import logging
import time
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

from backend.config import config
from backend.database import initialize_database
from backend.models.movie import Movie
from backend.repositories.movie_repository import MovieRepository

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = PROJECT_ROOT / "backend" / "data" / "cache" / "wikidata_movies"


def build_query(year: int) -> str:
    """Fetch films with one earliest usable release date and compact metadata."""
    return f'''PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <http://schema.org/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX bd: <http://www.bigdata.com/rdf#>
SELECT ?film ?filmLabel ?description (MIN(?release) AS ?releaseDate)
       (SAMPLE(?directorLabel) AS ?director) (SAMPLE(?actorLabel) AS ?actor)
       (SAMPLE(?genreLabel) AS ?genre) (SAMPLE(?countryLabel) AS ?country)
       (SAMPLE(?imdb) AS ?imdbId) (SAMPLE(?article) AS ?articleUrl)
       (COUNT(DISTINCT ?article) AS ?sitelinks)
WHERE {{
  ?film wdt:P31/wdt:P279* wd:Q11424; wdt:P577 ?release.
    FILTER(YEAR(?release) = {int(year)} && ?release <= NOW())
    ?film rdfs:label ?filmLabel.
    FILTER(LANG(?filmLabel) = "en")
  OPTIONAL {{ ?film schema:description ?description FILTER(LANG(?description) = "en") }}
  OPTIONAL {{ ?film wdt:P57 ?director. ?director rdfs:label ?directorLabel FILTER(LANG(?directorLabel) = "en") }}
  OPTIONAL {{ ?film wdt:P161 ?actor. ?actor rdfs:label ?actorLabel FILTER(LANG(?actorLabel) = "en") }}
  OPTIONAL {{ ?film wdt:P136 ?genreEntity. ?genreEntity rdfs:label ?genreLabel FILTER(LANG(?genreLabel) = "en") }}
  OPTIONAL {{ ?film wdt:P495 ?countryEntity. ?countryEntity rdfs:label ?countryLabel FILTER(LANG(?countryLabel) = "en") }}
  OPTIONAL {{ ?film wdt:P345 ?imdb }}
  OPTIONAL {{ ?article schema:about ?film; schema:isPartOf <https://en.wikipedia.org/> }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
GROUP BY ?film ?filmLabel ?description
LIMIT 500'''


def _value(binding: Dict[str, Any], name: str) -> Optional[str]:
    value = binding.get(name, {}).get("value")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _qid(uri: Optional[str]) -> Optional[str]:
    return uri.rsplit("/", 1)[-1] if uri else None


def normalize_results(payload: Dict[str, Any], year: int, movies_per_month: int = 2) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for binding in payload.get("results", {}).get("bindings", []):
        source_id = _qid(_value(binding, "film"))
        title = _value(binding, "filmLabel")
        raw_date = _value(binding, "releaseDate")
        if not source_id or not title or title == source_id or not raw_date:
            continue
        try:
            release = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).date()
        except ValueError:
            continue
        if release.year != year:
            continue
        item = {
            "year": year, "release_month": release.month, "release_date": release.isoformat(),
            "title": title, "director": _value(binding, "director"), "lead_actor": _value(binding, "actor"),
            "description": _value(binding, "description"), "genre": _value(binding, "genre"),
            "country": _value(binding, "country"), "source": "wikidata", "source_id": source_id,
            "source_url": f"https://www.wikidata.org/wiki/{source_id}",
            "notabilityScore": int(_value(binding, "sitelinks") or 0) * 2 + bool(_value(binding, "imdbId")) * 5 + bool(_value(binding, "director")) * 3 + bool(_value(binding, "actor")) * 2 + bool(_value(binding, "genre")) + bool(_value(binding, "country")),
        }
        grouped.setdefault(source_id, []).append(item)
    unique = [sorted(items, key=lambda item: (item["release_date"], item["title"], item["source_id"]))[0] for items in grouped.values()]
    selected = []
    for month in range(1, 13):
        month_items = sorted((item for item in unique if item["release_month"] == month), key=lambda item: (-item["notabilityScore"], item["release_date"], item["title"], item["source_id"]))
        selected.extend(month_items[:max(0, movies_per_month)])
    selected.sort(key=lambda item: (item["release_month"], -item["notabilityScore"], item["release_date"], item["title"], item["source_id"]))
    for rank, item in enumerate(selected, 1):
        item["rank"] = rank
        item.pop("notabilityScore", None)
    return selected


def fetch_year(session: requests.Session, year: int, cache_dir: Path, retries: int = 3, delay: float = 1.0, force: bool = False) -> Dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{year:04d}.json"
    if cache_path.exists() and not force:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    for attempt in range(1, retries + 1):
        try:
            response = session.get(config.wikidata_endpoint, params={"query": build_query(year), "format": "json"}, timeout=config.wikidata_timeout)
            if response.status_code == 200:
                payload = response.json()
                cache_path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
                if delay:
                    time.sleep(delay)
                return payload
            if response.status_code not in {429, 502, 503, 504} or attempt == retries:
                response.raise_for_status()
        except requests.RequestException:
            if attempt == retries:
                raise
        time.sleep(delay * (2 ** (attempt - 1)))
    return {"results": {"bindings": []}}


def import_movies(rows: Iterable[Dict[str, Any]], dry_run: bool = False) -> Dict[str, int]:
    """Upsert normalized Wikidata rows into the movies table."""
    inserted = updated = 0
    for row in rows:
        movie = Movie(
            title=row["title"],
            release_date=date.fromisoformat(row["release_date"]),
            country=row.get("country"),
            genres=row.get("genre"),
            overview=row.get("description"),
            imdb_id=row.get("imdb_id"),
            source_id=row.get("source_id"),
            director=row.get("director"),
            lead_actor=row.get("lead_actor"),
            source=row.get("source") or "wikidata",
            source_url=row.get("source_url"),
        )
        if dry_run:
            inserted += 1
            continue
        result = MovieRepository.upsert(movie)
        inserted += result == "inserted"
        updated += result == "updated"
    return {"inserted": inserted, "updated": updated}


def main() -> None:
    parser = argparse.ArgumentParser(description="Import movie metadata from Wikidata into SQLite")
    parser.add_argument("--year", type=int)
    parser.add_argument("--from-year", type=int)
    parser.add_argument("--to-year", type=int)
    parser.add_argument("--movies-per-month", type=int, default=2)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--request-delay", type=float, default=1.0)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    if args.status:
        initialize_database()
        counts = {year: MovieRepository.count_for_year(year) for year in range(1950, 2027)}
        counts = {year: count for year, count in counts.items() if count}
        print("WIKIDATA MOVIE DATABASE STATUS")
        print(f"Total movies: {sum(counts.values())}")
        print("Coverage:", counts)
        return
    start = args.year or args.from_year
    end = args.year or args.to_year or start
    if start is None or end is None or start > end:
        parser.error("specify --year or --from-year/--to-year")
    initialize_database()
    session = requests.Session()
    session.headers.update({"User-Agent": config.wikidata_user_agent, "Accept": "application/sparql-results+json"})
    rows = []
    for year in range(start, end + 1):
        payload = fetch_year(session, year, args.cache_dir, args.max_retries, args.request_delay, args.force)
        selected = normalize_results(payload, year, args.movies_per_month)
        rows.extend(selected)
        print(f"{year}: selected {len(selected)} ({Counter(item['release_month'] for item in selected)})")
    result = import_movies(rows, args.dry_run)
    action = "would be imported" if args.dry_run else "imported"
    print(f"Rows {action}: {len(rows)} (inserted: {result['inserted']}, updated: {result['updated']})")


if __name__ == "__main__":
    main()
