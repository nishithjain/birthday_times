"""Import normalized movie metadata from a local CSV file."""

import argparse
import csv
from datetime import date
from pathlib import Path

from backend.models.movie import Movie
from backend.repositories.movie_repository import MovieRepository
from backend.database import initialize_database


FIELDS = ("year", "release_month", "release_date", "rank", "title", "director", "lead_actor", "description", "genre", "country", "source", "source_id", "source_url", "tmdb_id", "imdb_id", "popularity", "vote_average", "vote_count", "overview", "genres")


def read_movies(path: Path, start_year=None, end_year=None):
    rows = inserted = updated = invalid = 0
    years = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            rows += 1
            try:
                year = int((raw.get("year") or "").strip())
                title = (raw.get("title") or "").strip()
                release_date = date.fromisoformat((raw.get("release_date") or f"{year:04d}-01-01").strip())
                if not title or year < 1888 or (start_year is not None and year < start_year) or (end_year is not None and year > end_year):
                    raise ValueError
                movie = Movie(title=title, release_date=release_date, country=raw.get("country") or None, genres=raw.get("genre") or raw.get("genres") or None, overview=raw.get("description") or raw.get("overview") or None, tmdb_id=int(raw["tmdb_id"]) if raw.get("tmdb_id") else None, imdb_id=raw.get("imdb_id") or None, source_id=raw.get("source_id") or None, director=raw.get("director") or None, lead_actor=raw.get("lead_actor") or None, popularity=float(raw["popularity"]) if raw.get("popularity") else None, vote_average=float(raw["vote_average"]) if raw.get("vote_average") else None, vote_count=int(raw["vote_count"]) if raw.get("vote_count") else None, source=raw.get("source") or "curated_csv", source_url=raw.get("source_url") or None)
            except (TypeError, ValueError):
                invalid += 1
                continue
            years.add(year)
            result = MovieRepository.upsert(movie)
            inserted += result == "inserted"
            updated += result == "updated"
    return {"rowsRead": rows, "validRows": rows - invalid, "invalidRows": invalid, "inserted": inserted, "updated": updated, "years": sorted(years)}


def main():
    parser = argparse.ArgumentParser(description="Import local normalized movie metadata")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--year", type=int)
    parser.add_argument("--from-year", type=int)
    parser.add_argument("--to-year", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    initialize_database()
    if args.status:
        print("Movie rows:", sum(MovieRepository.count_for_year(year) for year in range(1950, 2027)))
        return
    if not args.file:
        parser.error("--file is required unless --status is used")
    if args.dry_run:
        original = MovieRepository.upsert
        MovieRepository.upsert = lambda movie: "inserted"
        try:
            print(read_movies(args.file, args.year or args.from_year, args.year or args.to_year))
        finally:
            MovieRepository.upsert = original
    else:
        print(read_movies(args.file, args.year or args.from_year, args.year or args.to_year))


if __name__ == "__main__":
    main()