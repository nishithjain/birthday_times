"""Import supported cities from a GeoNames cities-style tab-separated file."""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.repositories.weather_location_repository import WeatherLocationRepository

MIN_CITY_POPULATION = 15000
CAPITAL_FEATURE_CODES = {"PPLC", "PPLA", "PPLA1", "PPLA2", "PPLA3", "PPLA4"}


def valid_coordinates(city: Dict) -> bool:
    latitude = city.get("latitude")
    longitude = city.get("longitude")
    return latitude is not None and longitude is not None and -90 <= latitude <= 90 and -180 <= longitude <= 180


def select_major_cities(cities, limit: int = 1000):
    """Select a stable top-N set without a hand-maintained city list."""
    unique = {}
    for city in cities:
        if not valid_coordinates(city):
            continue
        external_id = city.get("geoname_id") or city.get("location_key")
        if external_id not in unique or city.get("population", 0) > unique[external_id].get("population", 0):
            unique[external_id] = city
    ranked = sorted(
        unique.values(),
        key=lambda city: (
            0 if city.get("feature_code") in {"PPLC", "PPLA1"} else 1,
            -int(city.get("population") or 0),
            str(city.get("country_code") or "").upper(),
            str(city.get("ascii_name") or city.get("city") or "").casefold(),
            int(city.get("geoname_id") or 0),
        ),
    )
    return [dict(city, priority=1, major_city_rank=index) for index, city in enumerate(ranked[:limit], 1)]


def location_key(city: str, state: Optional[str], country_code: str, geoname_id: Optional[int] = None) -> str:
    if geoname_id:
        return f"geonames_{geoname_id}"
    text = "_".join(part for part in (country_code, state, city) if part)
    return re.sub(r"[^a-z0-9]+", "_", text.casefold()).strip("_")


def priority(population: int, feature_code: str) -> int:
    if population >= 1_000_000 or feature_code == "PPLC":
        return 1
    if population >= 100_000:
        return 2
    return 3


def parse_geonames_line(line: str, min_population: int = MIN_CITY_POPULATION) -> Optional[Dict]:
    fields = line.rstrip("\n").split("\t")
    if len(fields) < 19:
        return None
    geoname_id, name, ascii_name = fields[0], fields[1], fields[2]
    latitude, longitude, feature_class, feature_code = fields[4], fields[5], fields[6], fields[7]
    country_code, state_code = fields[8], fields[10]
    population = fields[14]
    if feature_class != "P" or not name or not country_code:
        return None
    try:
        geoname_id_int, population_int = int(geoname_id), int(population or 0)
        latitude_float, longitude_float = float(latitude), float(longitude)
    except ValueError:
        return None
    if population_int < min_population and feature_code not in CAPITAL_FEATURE_CODES:
        return None
    return {
        "location_key": location_key(name, state_code, country_code, geoname_id_int),
        "geoname_id": geoname_id_int, "city": name, "ascii_name": ascii_name,
        "state_region": state_code or None, "state_code": state_code or None,
        "country": country_code, "country_code": country_code, "latitude": latitude_float,
        "longitude": longitude_float, "population": population_int, "feature_code": feature_code,
        "priority": priority(population_int, feature_code), "enabled": 1, "source": "geonames",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import supported cities from GeoNames.")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--country")
    parser.add_argument("--min-population", type=int, default=MIN_CITY_POPULATION)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--major-status", action="store_true")
    parser.add_argument("--major-cities", type=int)
    args = parser.parse_args()
    if args.status or args.major_status:
        locations = WeatherLocationRepository.get_enabled_locations()
        major = [item for item in locations if item.get("major_city_rank") is not None and item["major_city_rank"] <= 1000]
        print("WEATHER LOCATIONS")
        print(f"Total cities: {len(locations)}")
        print(f"Major cities target: 1000")
        print(f"Major cities present: {len(major)}")
        print(f"Priority 1: {sum(item.get('priority') == 1 for item in locations)}")
        print(f"Countries represented: {len({item['country_code'] for item in major})}")
        print(f"Missing coordinates: {sum(not valid_coordinates(item) for item in major)}")
        ranks = {item["major_city_rank"] for item in major}
        print(f"Duplicate major ranks: {len(ranks) != len(major)}")
        print(f"Ranks missing in 1-1000: {len(set(range(1, 1001)) - ranks)}")
        if args.major_status:
            for item in sorted(major, key=lambda value: value["major_city_rank"])[:20]:
                print(f"{item['major_city_rank']}: {item['city']}, {item['country']} ({item.get('population') or 0})")
        return
    if not args.file:
        parser.error("--file is required unless using --status")
    count = 0
    with args.file.open(encoding="utf-8") as source:
        for line in source:
            if line.startswith("#"):
                continue
            location = parse_geonames_line(line, args.min_population)
            if location and (not args.country or location["country_code"].upper() == args.country.upper()):
                count += 1
                if args.major_cities:
                    # Selection is finalized after reading the complete catalog.
                    continue
                if not args.dry_run:
                    WeatherLocationRepository.upsert_location(location)
    if args.major_cities:
        with args.file.open(encoding="utf-8") as source:
            cities = [parse_geonames_line(line, args.min_population) for line in source if not line.startswith("#")]
        cities = [city for city in cities if city and (not args.country or city["country_code"].upper() == args.country.upper())]
        selected = select_major_cities(cities, args.major_cities)
        count = len(selected)
        if not args.dry_run:
            for city in selected:
                WeatherLocationRepository.upsert_location(city)
        print(f"Selected major cities: {count}")
    print(f"Imported {count} supported cities.")


if __name__ == "__main__":
    main()
