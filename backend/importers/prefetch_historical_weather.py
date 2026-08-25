"""Explicit, resumable city weather prefetch coordinator."""

import argparse
import sys
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.importers.historical_weather import OpenMeteoHistoricalProvider, parse_daily_response
from backend.repositories.weather_location_repository import WeatherLocationRepository
from backend.repositories.weather_repository import WeatherRepository
from backend.database import database_connection, fetch_all, fetch_one

PROVIDER = "open-meteo"
STATUS_PENDING = "pending"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_PARTIAL = "partial"
STATUS_FAILED = "failed"
CHUNK_DAYS = 365 * 5


def chunks(start: date, end: date):
    current = start
    while current <= end:
        chunk_end = min(current + timedelta(days=CHUNK_DAYS - 1), end)
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


def select_locations(args) -> List[Dict[str, Any]]:
    if args.location:
        item = WeatherLocationRepository.get_by_location_key(args.location) or WeatherLocationRepository.find_city(args.location)
        if not item and args.location.isdigit():
            item = WeatherLocationRepository.get_by_id(int(args.location))
        return [item] if item else []
    return WeatherLocationRepository.get_enabled_locations(args.max_priority, args.country, args.min_population)


def status_report() -> None:
    locations = fetch_one("SELECT COUNT(*) AS count FROM weather_locations WHERE enabled = 1")["count"]
    statuses = fetch_all("SELECT status, COUNT(*) AS count FROM weather_import_status GROUP BY status ORDER BY status")
    rows = fetch_one("SELECT COUNT(*) AS count FROM historical_weather")["count"]
    print("Historical Weather Prefetch Status")
    print(f"Supported cities: {locations}")
    for item in statuses:
        print(f"{item['status']}: {item['count']}")
    print(f"Weather rows: {rows}")


def set_status(location_id: int, start: date, end: date, status: str, rows: int = 0, error: str = None) -> None:
    with database_connection() as connection:
        connection.execute("""INSERT INTO weather_import_status (location_id, from_date, through_date, status, rows_imported, last_attempt_at, completed_at, error_message, provider)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(location_id, from_date, provider) DO UPDATE SET through_date=excluded.through_date, status=excluded.status, rows_imported=excluded.rows_imported, last_attempt_at=excluded.last_attempt_at, completed_at=excluded.completed_at, error_message=excluded.error_message""",
            (location_id, start.isoformat(), end.isoformat(), status, rows, datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat() if status == STATUS_COMPLETED else None, error, PROVIDER))


def main() -> None:
    parser = argparse.ArgumentParser(description="Prefetch historical weather for supported cities.")
    parser.add_argument("--location")
    parser.add_argument("--country")
    parser.add_argument("--priority", type=int)
    parser.add_argument("--max-priority", type=int)
    parser.add_argument("--min-population", type=int)
    parser.add_argument("--from-date", default="1950-01-01")
    parser.add_argument("--to-date", default=date.today().isoformat())
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--estimate", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if args.status:
        status_report(); return
    if args.priority is not None:
        args.max_priority = args.priority
    if not any((args.location, args.country, args.max_priority is not None, args.min_population is not None, args.all)):
        parser.error("select a location/filter or explicitly provide --all")
    locations = select_locations(args)
    start, end = date.fromisoformat(args.from_date), date.fromisoformat(args.to_date)
    days = (end - start).days + 1
    total_chunks = sum(1 for _ in chunks(start, end))
    if args.estimate or args.dry_run:
        print(f"Locations selected: {len(locations)}")
        print(f"Days per city: {days}")
        print(f"Estimated rows: {len(locations) * days}")
        print(f"Provider chunks per city: {total_chunks}")
        return
    provider = OpenMeteoHistoricalProvider()
    for location in locations:
        for chunk_start, chunk_end in chunks(start, end):
            try:
                if not args.force:
                    existing = fetch_one("SELECT status FROM weather_import_status WHERE location_id = ? AND from_date = ? AND provider = ?", (location["id"], chunk_start.isoformat(), PROVIDER))
                    if existing and existing["status"] == STATUS_COMPLETED:
                        continue
                set_status(location["id"], chunk_start, chunk_end, STATUS_IN_PROGRESS)
                payload = provider.fetch(chunk_start, chunk_end, location["latitude"], location["longitude"])
                rows = []
                for row in parse_daily_response(payload, location["latitude"], location["longitude"], location["city"], location["country"]):
                    row.update({"location_id": location["id"], "source_dataset": "open-meteo-archive", "source_latitude": location["latitude"], "source_longitude": location["longitude"]})
                    rows.append(row)
                WeatherRepository.bulk_upsert_daily_weather(rows)
                set_status(location["id"], chunk_start, chunk_end, STATUS_COMPLETED, len(rows))
                print(f"{location['location_key']} {chunk_start}..{chunk_end}: {len(rows)} rows")
            except Exception as exc:
                set_status(location["id"], chunk_start, chunk_end, STATUS_FAILED, error=str(exc))
                print(f"{location['location_key']} {chunk_start}..{chunk_end}: FAILED {exc}")
                break


if __name__ == "__main__":
    main()
