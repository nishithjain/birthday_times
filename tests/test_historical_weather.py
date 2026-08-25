"""Offline tests for the historical weather importer and repository."""

from datetime import date

from backend.database import initialize_database
from backend.importers.historical_weather import parse_daily_response
from backend.repositories.weather_repository import WeatherRepository


def test_parse_daily_response():
    rows = list(parse_daily_response({"daily": {
        "time": ["1982-05-09"],
        "temperature_2m_max": [31.2], "temperature_2m_min": [20.1], "temperature_2m_mean": [25.4],
        "precipitation_sum": [0], "wind_speed_10m_max": [11.8], "weather_code": [0],
    }}, 12.9716, 77.5946, "Bengaluru", "India"))
    assert rows[0]["weather_date"] == "1982-05-09"
    assert rows[0]["temperature_mean_c"] == 25.4
    assert rows[0]["data_quality"] == "reanalysis"


def test_repository_upsert_does_not_duplicate(tmp_path, monkeypatch):
    database = tmp_path / "weather.db"
    monkeypatch.setattr("backend.config.config.database_path", database)
    monkeypatch.setattr("backend.database.db.DATABASE_PATH", database)
    initialize_database()
    row = {
        "weather_date": "1982-05-09", "latitude": 12.9716, "longitude": 77.5946,
        "city": "Bengaluru", "country": "India", "source": "open-meteo",
        "temperature_mean_c": 25.4, "weather_code": 0, "fetched_at": "2026-08-24T00:00:00+00:00",
    }
    WeatherRepository.upsert_daily_weather(row)
    row["temperature_mean_c"] = 26.0
    WeatherRepository.upsert_daily_weather(row)
    result = WeatherRepository.get_daily_weather(date(1982, 5, 9), 12.9716, 77.5946)
    assert result["temperature_mean_c"] == 26.0
    assert WeatherRepository.status()["total"] == 1
