"""SQLite repository for imported historical daily weather."""

from datetime import date
from typing import Any, Dict, Optional

from backend.database import database_connection, fetch_all, fetch_one


class WeatherRepository:
    @staticmethod
    def get_monthly_weather(location_id: int, month: int) -> Optional[Dict[str, Any]]:
        if not 1 <= int(month) <= 12:
            return None
        row = fetch_one("SELECT * FROM monthly_weather WHERE location_id = ? AND month = ?", (location_id, month))
        return dict(row) if row else None

    @staticmethod
    def get_all_months(location_id: int):
        return [dict(row) for row in fetch_all("SELECT * FROM monthly_weather WHERE location_id = ? ORDER BY month", (location_id,))]

    @staticmethod
    def count_months(location_id: int) -> int:
        return fetch_one("SELECT COUNT(*) AS count FROM monthly_weather WHERE location_id = ?", (location_id,))["count"]

    @staticmethod
    def update_climate_conditions(rows) -> int:
        rows = list(rows)
        if not rows:
            return 0
        with database_connection() as connection:
            for row in rows:
                connection.execute(
                    "UPDATE monthly_weather SET climate_condition = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (row["climate_condition"], row["id"]),
                )
        return len(rows)

    @staticmethod
    def upsert_monthly_weather(weather: Dict[str, Any]) -> None:
        month = int(weather["month"])
        if not 1 <= month <= 12:
            raise ValueError("month must be between 1 and 12")
        fields = ["location_id", "month", "avg_min_temp_c", "avg_max_temp_c", "avg_mean_temp_c", "avg_precipitation_mm", "avg_rainy_days", "avg_wind_kmh", "climate_condition", "source", "source_dataset", "reference_period", "fetched_at"]
        values = [weather.get(field) for field in fields]
        updates = ", ".join(f"{field} = excluded.{field}" for field in fields[2:])
        with database_connection() as connection:
            connection.execute(f"INSERT INTO monthly_weather ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)}) ON CONFLICT(location_id, month) DO UPDATE SET {updates}", values)

    @staticmethod
    def bulk_upsert_monthly_weather(rows) -> None:
        rows = list(rows)
        if not rows:
            return
        with database_connection() as connection:
            for row in rows:
                month = int(row["month"])
                if not 1 <= month <= 12:
                    raise ValueError("month must be between 1 and 12")
                fields = ["location_id", "month", "avg_min_temp_c", "avg_max_temp_c", "avg_mean_temp_c", "avg_precipitation_mm", "avg_rainy_days", "avg_wind_kmh", "climate_condition", "source", "source_dataset", "reference_period", "fetched_at"]
                values = [row.get(field) for field in fields]
                updates = ", ".join(f"{field} = excluded.{field}" for field in fields[2:])
                connection.execute(f"INSERT INTO monthly_weather ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)}) ON CONFLICT(location_id, month) DO UPDATE SET {updates}", values)

    @staticmethod
    def get_daily_weather_by_location(location_id: int, weather_date: date) -> Optional[Dict[str, Any]]:
        row = fetch_one("SELECT * FROM historical_weather WHERE location_id = ? AND weather_date = ? ORDER BY id DESC LIMIT 1", (location_id, weather_date.isoformat()))
        return dict(row) if row else None

    @staticmethod
    def get_weather_range(location_id: int, start_date: date, end_date: date):
        return [dict(row) for row in fetch_all("SELECT * FROM historical_weather WHERE location_id = ? AND weather_date BETWEEN ? AND ? ORDER BY weather_date", (location_id, start_date.isoformat(), end_date.isoformat()))]

    @staticmethod
    def has_weather(location_id: int, weather_date: date) -> bool:
        return WeatherRepository.get_daily_weather_by_location(location_id, weather_date) is not None

    @staticmethod
    def bulk_upsert_daily_weather(rows):
        rows = list(rows)
        if not rows:
            return
        with database_connection() as connection:
            for row in rows:
                WeatherRepository._upsert_daily_weather(connection, row)

    @staticmethod
    def get_daily_weather(weather_date: date, latitude: float, longitude: float, tolerance: Optional[float] = None) -> Optional[Dict[str, Any]]:
        if tolerance is None:
            row = fetch_one(
                "SELECT * FROM historical_weather WHERE weather_date = ? AND latitude = ? AND longitude = ? ORDER BY id DESC LIMIT 1",
                (weather_date.isoformat(), latitude, longitude),
            )
        else:
            row = fetch_one(
                """SELECT * FROM historical_weather WHERE weather_date = ?
                   AND ABS(latitude - ?) <= ? AND ABS(longitude - ?) <= ?
                   ORDER BY ((latitude - ?) * (latitude - ?) + (longitude - ?) * (longitude - ?)), id DESC LIMIT 1""",
                (weather_date.isoformat(), latitude, tolerance, longitude, tolerance, latitude, latitude, longitude, longitude),
            )
        return dict(row) if row else None

    @staticmethod
    def upsert_daily_weather(weather: Dict[str, Any]) -> None:
        with database_connection() as connection:
            WeatherRepository._upsert_daily_weather(connection, weather)

    @staticmethod
    def _upsert_daily_weather(connection, weather: Dict[str, Any]) -> None:
        if weather.get("location_id"):
            fields = ["location_id", "weather_date", "temperature_max_c", "temperature_min_c", "temperature_mean_c", "apparent_temperature_max_c", "apparent_temperature_min_c", "precipitation_mm", "rain_mm", "snowfall_cm", "wind_speed_max_kmh", "wind_gust_max_kmh", "wind_direction_dominant_deg", "weather_code", "sunrise", "sunset", "source", "source_dataset", "source_latitude", "source_longitude", "data_quality", "fetched_at"]
            values = [weather.get(field) for field in fields]
            updates = ", ".join(f"{field} = excluded.{field}" for field in fields[2:])
            connection.execute(f"INSERT INTO historical_weather ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)}) ON CONFLICT(location_id, weather_date, source) DO UPDATE SET {updates}", values)
            return
        fields = [
            "weather_date", "latitude", "longitude", "city", "region", "country", "source", "source_location_id",
            "temperature_max_c", "temperature_min_c", "temperature_mean_c", "apparent_temperature_max_c",
            "apparent_temperature_min_c", "precipitation_mm", "rain_mm", "snowfall_cm", "wind_speed_max_kmh",
            "wind_gust_max_kmh", "wind_direction_dominant_deg", "weather_code", "sunrise", "sunset", "data_quality", "fetched_at",
        ]
        values = [weather.get(field) for field in fields]
        placeholders = ", ".join("?" for _ in fields)
        updates = ", ".join(f"{field} = excluded.{field}" for field in fields[3:])
        connection.execute(
            f"INSERT INTO historical_weather ({', '.join(fields)}) VALUES ({placeholders}) ON CONFLICT(weather_date, latitude, longitude, source) DO UPDATE SET {updates}",
            values,
        )

    @staticmethod
    def status() -> Dict[str, Any]:
        total = fetch_one("SELECT COUNT(*) AS count FROM historical_weather")["count"]
        locations = fetch_one("SELECT COUNT(DISTINCT latitude || ':' || longitude) AS count FROM historical_weather")["count"]
        sources = fetch_all("SELECT source, COUNT(*) AS count FROM historical_weather GROUP BY source ORDER BY source")
        return {"total": total, "locations": locations, "sources": [dict(row) for row in sources]}