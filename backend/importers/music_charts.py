"""Import local CSV/JSON year-level music chart data into SQLite."""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database import fetch_all, fetch_one
from backend.repositories.music_repository import MusicRepository

REQUIRED_FIELDS = ("year", "rank", "title", "artist")
OPTIONAL_FIELDS = ("chart_name", "chart_country", "source", "source_id", "source_url")


def normalize_row(raw: Dict[str, Any], default_source: str = "local_chart") -> Optional[Dict[str, Any]]:
    try:
        year, rank = int(raw.get("year")), int(raw.get("rank"))
    except (TypeError, ValueError):
        return None
    title, artist = str(raw.get("title") or "").strip(), str(raw.get("artist") or "").strip()
    if year < 1 or rank <= 0 or not title or not artist:
        return None
    return {"year": year, "rank": rank, "title": title, "artist": artist,
            "chart_name": (raw.get("chart_name") or "").strip() or "year_end",
            "chart_country": (raw.get("chart_country") or "").strip() or None,
            "source": (raw.get("source") or default_source).strip(),
            "source_id": (raw.get("source_id") or "").strip() or None,
            "source_url": (raw.get("source_url") or "").strip() or None}


def read_rows(path: Path, format_name: Optional[str] = None) -> Iterable[Dict[str, Any]]:
    format_name = format_name or path.suffix.lower().lstrip(".")
    if format_name == "csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            yield from csv.DictReader(handle)
    elif format_name == "json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        yield from (payload if isinstance(payload, list) else payload.get("tracks", []))
    else:
        raise ValueError("format must be csv or json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import year-level music charts from local CSV or JSON.")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--format", choices=("csv", "json"))
    parser.add_argument("--year", type=int)
    parser.add_argument("--from-year", type=int)
    parser.add_argument("--to-year", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if args.status:
        rows = fetch_all("SELECT year, COUNT(*) AS count FROM music_tracks GROUP BY year ORDER BY year")
        total = fetch_one("SELECT COUNT(*) AS count FROM music_tracks")["count"]
        print("MUSIC CHART DATABASE STATUS")
        print(f"Total tracks: {total}")
        print(f"Years represented: {rows[0]['year'] if rows else '-'} -> {rows[-1]['year'] if rows else '-'}")
        print(f"Years with >= 20 songs: {sum(row['count'] >= 20 for row in rows)}")
        print(f"Years with 5-19 songs: {sum(5 <= row['count'] < 20 for row in rows)}")
        print(f"Years with 1-4 songs: {sum(1 <= row['count'] < 5 for row in rows)}")
        print(f"Years with zero songs: {0 if not rows else max(0, rows[-1]['year'] - rows[0]['year'] + 1 - len(rows))}")
        return
    if not args.file:
        parser.error("--file is required unless using --status")
    if args.from_year is not None and args.to_year is None:
        parser.error("--to-year is required with --from-year")
    valid, invalid, tracks = 0, 0, []
    for raw in read_rows(args.file, args.format):
        track = normalize_row(raw)
        if track is None or (args.year is not None and track and track["year"] != args.year) or (args.from_year is not None and track and not args.from_year <= track["year"] <= args.to_year):
            invalid += 1
            continue
        tracks.append(track)
        valid += 1
    if not args.dry_run:
        MusicRepository.bulk_upsert_tracks(tracks)
    years = sorted({track["year"] for track in tracks})
    print(f"Rows read: {valid + invalid}")
    print(f"Valid rows: {valid}")
    print(f"Invalid rows: {invalid}")
    print(f"Years found: {years}")
    print(f"Would {'insert/update' if not args.dry_run else 'insert/update'}: {valid}")


if __name__ == "__main__":
    main()
