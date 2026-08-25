"""Tests for condition-driven weather illustration selection."""

import json
from datetime import date
from pathlib import Path

from backend.models.person import FamousPerson
from backend.services.weather_service import WeatherService, illustration_id_for_condition


class Locations:
    @staticmethod
    def find_city(*args):
        return {"id": 7, "location_key": "bengaluru", "city": "Bengaluru", "state_region": "Karnataka", "country": "India", "country_code": "IN", "latitude": 12.97, "longitude": 77.59}


class Repository:
    @staticmethod
    def get_monthly_weather(location_id, month):
        return {"climate_condition": "showers", "avg_mean_temp_c": 25, "avg_precipitation_mm": 110, "avg_wind_kmh": 9, "source": "nasa_power"}


class Illustrations:
    def get_by_id(self, illustration_id):
        return {"id": illustration_id, "path": f"images/illustrations/originals/weather/{illustration_id.removeprefix('weather_')}.png"}

    def resolve_by_id(self, illustration_id, style_id):
        return {"id": illustration_id, "displayPath": f"images/illustrations/variants/{style_id}/weather/{illustration_id.removeprefix('weather_')}.png"}


def test_mapping_aliases_and_fallback():
    assert illustration_id_for_condition("sunny") == "weather_sunny"
    assert illustration_id_for_condition("clear") == "weather_sunny"
    assert illustration_id_for_condition("showers") == "weather_showers"
    assert illustration_id_for_condition("rainy") == "weather_rain"
    assert illustration_id_for_condition("something_unknown") == "weather_generic"


def test_monthly_weather_resolves_condition_specific_era_art():
    service = WeatherService(repository=Repository, location_repository=Locations, illustration_service=Illustrations())
    result = service.get_weather(date(1982, 5, 9), city="Bengaluru", newspaper_style_id="1980")
    assert result["condition"] == "showers"
    assert result["illustrationId"] == "weather_showers"
    assert result["illustration"]["displayPath"].endswith("variants/1980/weather/showers.png")
    assert result["weatherAccuracy"] == "monthly_climate"


def test_rain_keeps_rain_art_even_with_strong_wind():
    class RainRepository(Repository):
        @staticmethod
        def get_monthly_weather(location_id, month):
            return {"climate_condition": "rain", "avg_mean_temp_c": 15, "avg_precipitation_mm": 250, "avg_wind_kmh": 50, "source": "nasa_power"}

    service = WeatherService(repository=RainRepository, location_repository=Locations, illustration_service=Illustrations())
    assert service.get_weather(date(1982, 5, 9), city="Bengaluru")["illustrationId"] == "weather_rain"


def test_registry_has_ten_condition_assets_and_paths_exist():
    payload = json.loads(Path("backend/data/illustrations.json").read_text(encoding="utf-8"))
    weather = [item for item in payload["illustrations"] if item["id"].startswith("weather_")]
    assert {item["id"] for item in weather} == {
        "weather_generic", "weather_sunny", "weather_partly_cloudy", "weather_cloudy", "weather_showers",
        "weather_rain", "weather_thunderstorm", "weather_snow", "weather_fog", "weather_windy",
    }
    assert all(Path("backend/web/static").joinpath(item["path"]).is_file() for item in weather)
