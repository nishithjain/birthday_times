"""Derive and optionally populate monthly NASA climate conditions."""

import argparse

from backend.database import fetch_all
from backend.repositories.weather_repository import WeatherRepository
from backend.services.climate_condition_classifier import classify_monthly_climate


QUERY = """
SELECT m.id, l.city, m.month, m.avg_min_temp_c, m.avg_mean_temp_c,
       m.avg_max_temp_c, m.avg_precipitation_mm, m.avg_rainy_days,
       m.avg_wind_kmh, m.climate_condition, m.source
FROM monthly_weather m
JOIN weather_locations l ON l.id = m.location_id
WHERE m.source = 'nasa_power'
ORDER BY l.city, m.month
"""


def build_updates(rows):
    updates = []
    for row in rows:
        condition, character, reason = classify_monthly_climate(dict(row))
        updates.append({
            **dict(row),
            "old_climate_condition": row["climate_condition"],
            "climate_condition": condition,
            "temperature_character": character,
            "reason": reason,
        })
    return updates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="show planned classifications without updating SQLite")
    args = parser.parse_args()
    updates = build_updates(fetch_all(QUERY))
    changed = [row for row in updates if row["old_climate_condition"] != row["climate_condition"]]
    # Keep the report useful without printing thousands of rows.
    for row in updates:
        if row["city"] in {"Dubai", "Helsinki"} and row["month"] in {1, 7, 12}:
            print(f"{row['city']} {row['month']}: old={row['old_climate_condition'] or 'NULL'} new={row['climate_condition']} temperature_character={row['temperature_character']} reason={row['reason']}")
    print(f"NASA rows scanned: {len(updates)}")
    print(f"Rows classified: {len(changed)}")
    print(f"Dry run: {'yes' if args.dry_run else 'no'}")
    if not args.dry_run:
        print(f"Rows updated: {WeatherRepository.update_climate_conditions(updates)}")


if __name__ == "__main__":
    main()