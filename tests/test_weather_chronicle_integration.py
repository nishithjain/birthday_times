"""End-to-end offline checks for city/month weather in a Chronicle."""

from datetime import date
from unittest.mock import patch

from backend.services.chronicle_service import ChronicleService


LOCATION = {
    "id": 263,
    "location_key": "geonames_1277333",
    "city": "Bengaluru",
    "state_region": "19",
    "country": "IN",
    "country_code": "IN",
    "latitude": 12.97194,
    "longitude": 77.59369,
}


class Locations:
    @staticmethod
    def find_city(city, state_region=None, country_code=None):
        return LOCATION if city.casefold() == "bengaluru" else None

    @staticmethod
    def get_by_id(location_id):
        return LOCATION if location_id == 263 else None


class Weather:
    @staticmethod
    def get_monthly_weather(location_id, month):
        return {
            "location_id": location_id,
            "month": month,
            "avg_min_temp_c": 18.69,
            "avg_max_temp_c": 39.88,
            "avg_mean_temp_c": 26.97,
            "avg_precipitation_mm": 3.54,
            "avg_rainy_days": None,
            "avg_wind_kmh": 13.14,
            "source": "nasa_power",
        }


def test_1980_bengaluru_uses_monthly_weather(monkeypatch):
    from backend.services.weather_service import WeatherService
    service = WeatherService(repository=Weather, location_repository=Locations, illustration_service=None)
    monkeypatch.setattr("backend.services.chronicle_service.weather_service", service)
    with patch("backend.services.chronicle_service.EventRepository.get_by_date", return_value=[]), patch("backend.services.chronicle_service.PersonRepository.get_by_birthday", return_value=[]), patch("backend.services.chronicle_service.MovieRepository.get_by_year", return_value=[]):
        chronicle = ChronicleService.generate_chronicle(date(1980, 5, 9), birth_city="Bengaluru")
    assert chronicle["weather"]["available"] is True
    assert chronicle["weather"]["location"]["id"] == 263
    assert chronicle["weather"]["month"] == 5
    assert chronicle["weather"]["weatherAccuracy"] == "monthly_climate"
    assert chronicle["weather"]["conditionText"] != "Weather unavailable"
