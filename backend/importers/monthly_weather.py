"""Import approximate monthly climate profiles for supported cities."""

import argparse
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.providers.weather.nasa_power import NASA_POWER_CLIMATOLOGY_URL, NasaPowerClimatologyProvider, NasaPowerError, format_error
from backend.repositories.weather_location_repository import WeatherLocationRepository
from backend.repositories.weather_repository import WeatherRepository
from backend.services.climate_condition_classifier import classify_monthly_climate

REQUEST_DELAY_SECONDS = 1.5


def monthly_profiles(rows: List[Dict[str, Any]], location_id: int) -> List[Dict[str, Any]]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[date.fromisoformat(row["weather_date"]).month].append(row)
    profiles = []
    for month, values in sorted(grouped.items()):
        rain_values = [row.get("precipitation_mm") for row in values if row.get("precipitation_mm") is not None]
        rainy_days = sum(1 for row in values if (row.get("precipitation_mm") or 0) >= 1)
        means = lambda key: mean([row[key] for row in values if row.get(key) is not None]) if any(row.get(key) is not None for row in values) else None
        profiles.append({
            "location_id": location_id, "month": month,
            "avg_min_temp_c": means("temperature_min_c"), "avg_max_temp_c": means("temperature_max_c"), "avg_mean_temp_c": means("temperature_mean_c"),
            "avg_precipitation_mm": sum(rain_values) / 30.0 if rain_values else None,
            "avg_rainy_days": rainy_days / max(1, len(values) / 30.0) if values else None,
            "avg_wind_kmh": means("wind_speed_max_kmh"),
            "source": "open-meteo", "source_dataset": "open-meteo-archive", "reference_period": "2011-2020", "fetched_at": None,
        })
        profiles[-1]["climate_condition"] = classify_monthly_climate(profiles[-1])[0]
    return profiles


def nasa_profiles(rows: List[Dict[str, Any]], location_id: int) -> List[Dict[str, Any]]:
    """Attach the local city ID and import timestamp to normalized NASA rows."""
    months = {row.get("month") for row in rows}
    if any(month not in range(1, 13) for month in months) or len(months) != len(rows):
        raise NasaPowerError("NASA POWER returned duplicate or invalid months")
    fetched_at = datetime.now(timezone.utc).isoformat()
    profiles = []
    for row in rows:
        profile = dict(row, location_id=location_id, fetched_at=fetched_at)
        profile["climate_condition"] = classify_monthly_climate(profile)[0]
        profiles.append(profile)
    return profiles


def main() -> None:
    parser = argparse.ArgumentParser(description="Import city/month climate profiles.")
    parser.add_argument("--location")
    parser.add_argument("--country")
    parser.add_argument("--priority", type=int)
    parser.add_argument("--max-priority", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--estimate", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--major-cities", type=int)
    parser.add_argument("--request-delay", type=float, default=REQUEST_DELAY_SECONDS)
    parser.add_argument("--max-retries", type=int, default=4)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--provider-test", action="store_true")
    args = parser.parse_args()
    if args.status:
        locations = WeatherLocationRepository.get_enabled_locations(major_limit=1000)
        complete = sum(WeatherRepository.count_months(item["id"]) == 12 for item in locations)
        partial = sum(0 < WeatherRepository.count_months(item["id"]) < 12 for item in locations)
        rows = sum(WeatherRepository.count_months(item["id"]) for item in locations)
        print("MONTHLY WEATHER DATABASE")
        print("Major cities target: 1000")
        print(f"Major cities available: {len(locations)}")
        print(f"Supported cities: {len(locations)}")
        print(f"Cities with all 12 months: {complete}")
        print(f"Partial cities: {partial}")
        print(f"No climate data: {len(locations) - complete - partial}")
        print(f"Monthly weather rows: {rows}")
        print(f"Expected monthly rows: {len(locations) * 12}")
        print(f"Coverage: {(rows / (len(locations) * 12) * 100) if locations else 0:.2f}%")
        return
    if args.location:
        locations = [WeatherLocationRepository.get_by_location_key(args.location) or WeatherLocationRepository.find_city(args.location)]
        locations = [item for item in locations if item]
    else:
        max_priority = args.max_priority or args.priority
        major_limit = args.major_cities
        if max_priority == 1:
            major_limit = 1000
        locations = WeatherLocationRepository.get_enabled_locations(max_priority, args.country, major_limit=major_limit)
    if args.provider_test:
        if len(locations) != 1:
            parser.error("--provider-test requires exactly one --location")
        location = locations[0]
        print(f"NASA POWER provider test: {location['city']}, {location['country']}")
        print(f"Endpoint: {NASA_POWER_CLIMATOLOGY_URL}")
        print("Community: AG")
        print("Parameters: T2M,T2M_MIN,T2M_MAX,PRECTOTCORR,WS10M")
        print(f"Latitude: {location['latitude']}")
        print(f"Longitude: {location['longitude']}")
        try:
            rows = NasaPowerClimatologyProvider(max_retries=args.max_retries).fetch_climatology(location["latitude"], location["longitude"])
            print(f"Parameters available: {', '.join(sorted({field for row in rows for field in row if field.startswith('avg_')}))}")
            print(f"Months returned: {len(rows)}")
            print("SQLite writes: none")
        except NasaPowerError as exc:
            print(format_error(exc) if args.debug else str(exc))
        return
    if args.limit:
        locations = locations[:args.limit]
    if args.estimate or args.dry_run:
        if args.estimate:
            print("MONTHLY WEATHER IMPORT ESTIMATE")
        print(f"Cities selected: {len(locations)}")
        print("Months per city: 12")
        print(f"Maximum weather rows: {len(locations) * 12}")
        complete = sum(WeatherRepository.count_months(item["id"]) == 12 for item in locations)
        partial = sum(0 < WeatherRepository.count_months(item["id"]) < 12 for item in locations)
        existing_rows = sum(WeatherRepository.count_months(item["id"]) for item in locations)
        print(f"Cities already complete: {complete}")
        print(f"Cities partial: {partial}")
        print(f"Cities missing: {len(locations) - complete - partial}")
        print(f"Rows currently stored: {existing_rows}")
        print(f"Rows potentially added: {len(locations) * 12 - existing_rows}")
        return
    provider = NasaPowerClimatologyProvider(max_retries=args.max_retries)
    completed = skipped = failed = 0
    failures = []
    for index, location in enumerate(locations, 1):
        print(f"[{index}/{len(locations)}] {location['city']}, {location['country']}")
        if not args.force and WeatherRepository.count_months(location["id"]) == 12:
            skipped += 1
            print("12/12 already cached\nSKIPPED")
            continue
        try:
            print("Fetching NASA POWER monthly climatology...")
            profiles = nasa_profiles(provider.fetch_climatology(location["latitude"], location["longitude"]), location["id"])
            WeatherRepository.bulk_upsert_monthly_weather(profiles)
            completed += 1
            print(f"{len(profiles)} monthly records")
            if len(profiles) == 12:
                print("COMPLETE")
            else:
                print("PARTIAL")
        except NasaPowerError as exc:
            failed += 1
            failures.append(f"{location['city']}, {location['country']}: {exc}")
            print(format_error(exc) if args.debug else f"FAILED: {exc}")
        if index < len(locations) and args.request_delay > 0:
            import time
            time.sleep(args.request_delay)
    print(f"\nCities requested: {len(locations)}\nCompleted: {completed}\nSkipped: {skipped}\nFailed: {failed}")
    if failures:
        print("Failed cities:")
        for failure in failures:
            print(f"- {failure}")


if __name__ == "__main__":
    main()
