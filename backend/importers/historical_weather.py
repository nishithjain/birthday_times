"""Explicit Open-Meteo archive importer for selected dates and locations."""

import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import requests
import time

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.repositories.weather_repository import WeatherRepository

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY_FIELDS = ",".join((
    "temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
    "precipitation_sum", "wind_speed_10m_max", "weather_code",
))

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
RETRY_DELAYS_SECONDS = (5, 15, 30, 60)


class WeatherProviderError(RuntimeError):
    """A bounded provider failure that a batch importer can record and skip."""


class OpenMeteoHistoricalProvider:
    """Provider-specific HTTP code kept outside runtime services."""

    def fetch(self, start_date: date, end_date: date, latitude: float, longitude: float, max_retries: int = 4, sleep=time.sleep) -> Dict[str, Any]:
        response = None
        for attempt in range(max(0, max_retries) + 1):
            try:
                response = requests.get(ARCHIVE_URL, params={
                    "latitude": latitude, "longitude": longitude,
                    "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
                    "daily": DAILY_FIELDS, "timezone": "UTC",
                }, timeout=60)
            except (requests.Timeout, requests.ConnectionError) as exc:
                if attempt >= max_retries:
                    raise WeatherProviderError(f"network error after {attempt} retries: {exc}") from exc
                delay = RETRY_DELAYS_SECONDS[min(attempt, len(RETRY_DELAYS_SECONDS) - 1)]
                sleep(delay)
                continue
            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError as exc:
                    raise WeatherProviderError("provider returned malformed JSON") from exc
            if response.status_code not in RETRYABLE_STATUS_CODES:
                raise WeatherProviderError(f"HTTP {response.status_code}")
            if attempt >= max_retries:
                raise WeatherProviderError(f"HTTP {response.status_code} after {attempt} retries")
            retry_after = response.headers.get("Retry-After")
            try:
                delay = max(0, float(retry_after)) if retry_after else RETRY_DELAYS_SECONDS[min(attempt, len(RETRY_DELAYS_SECONDS) - 1)]
            except ValueError:
                delay = RETRY_DELAYS_SECONDS[min(attempt, len(RETRY_DELAYS_SECONDS) - 1)]
            sleep(delay)
        raise WeatherProviderError("provider request failed")


def parse_daily_response(payload: Dict[str, Any], latitude: float, longitude: float, city: Optional[str], country: Optional[str]) -> Iterable[Dict[str, Any]]:
    daily = payload.get("daily") or {}
    dates = daily.get("time") or []
    for index, value in enumerate(dates):
        def item(key: str):
            values = daily.get(key) or []
            return values[index] if index < len(values) else None
        yield {
            "weather_date": value, "latitude": latitude, "longitude": longitude,
            "city": city, "country": country, "source": "open-meteo",
            "source_location_id": f"{latitude:.4f},{longitude:.4f}",
            "temperature_max_c": item("temperature_2m_max"), "temperature_min_c": item("temperature_2m_min"),
            "temperature_mean_c": item("temperature_2m_mean"), "apparent_temperature_max_c": item("apparent_temperature_max"),
            "apparent_temperature_min_c": item("apparent_temperature_min"), "precipitation_mm": item("precipitation_sum"),
            "rain_mm": item("rain_sum"), "snowfall_cm": item("snowfall_sum"), "wind_speed_max_kmh": item("wind_speed_10m_max"),
            "wind_gust_max_kmh": item("wind_gusts_10m_max"), "wind_direction_dominant_deg": item("wind_direction_10m_dominant"),
            "weather_code": item("weather_code"), "sunrise": item("sunrise"), "sunset": item("sunset"),
            "data_quality": "reanalysis", "fetched_at": datetime.now(timezone.utc).isoformat(),
        }


def _date(value: str) -> date:
    return date.fromisoformat(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import selected historical weather into SQLite.")
    parser.add_argument("--date")
    parser.add_argument("--from-date")
    parser.add_argument("--to-date")
    parser.add_argument("--latitude", type=float)
    parser.add_argument("--longitude", type=float)
    parser.add_argument("--city")
    parser.add_argument("--country")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if args.status:
        status = WeatherRepository.status()
        print("Historical Weather Database")
        print(f"Total rows: {status['total']}")
        print(f"Locations: {status['locations']}")
        print("Sources:")
        for source in status["sources"]:
            print(f"{source['source']}: {source['count']}")
        return
    if args.latitude is None or args.longitude is None:
        parser.error("--latitude and --longitude are required")
    start = _date(args.date) if args.date else _date(args.from_date) if args.from_date else None
    end = _date(args.date) if args.date else _date(args.to_date) if args.to_date else None
    if start is None or end is None or start > end:
        parser.error("provide --date or both --from-date and --to-date")
    payload = OpenMeteoHistoricalProvider().fetch(start, end, args.latitude, args.longitude)
    count = 0
    for row in parse_daily_response(payload, args.latitude, args.longitude, args.city, args.country):
        WeatherRepository.upsert_daily_weather(row)
        count += 1
    print(f"Imported {count} weather records for {args.city or 'selected location'}.")


if __name__ == "__main__":
    main()
