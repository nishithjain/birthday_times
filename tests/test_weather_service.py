"""Offline tests for historical weather formatting."""

from datetime import date

from backend.services.weather_service import (
    WeatherService,
    derive_climate_condition,
    temperature_character,
    temperature_text,
    wind_text,
    weather_service,
)
from backend.services.climate_condition_classifier import condition_label


class Repository:
    row = None

    @staticmethod
    def get_daily_weather(*args, **kwargs):
        return Repository.row


def service():
    return WeatherService(repository=Repository)


def test_condition_temperature_wind_and_date_text():
    Repository.row = {
        "weather_code": 0,
        "temperature_min_c": 8.0,
        "temperature_max_c": 18.0,
        "temperature_mean_c": 13.0,
        "wind_speed_max_kmh": 3.0,
        "precipitation_mm": 0,
        "source": "open-meteo",
        "data_quality": "reanalysis",
    }
    result = service().get_weather(date(1948, 10, 16), 51.5, -0.1, "London", "United Kingdom")
    assert result["available"] is True
    assert result["conditionText"] == "Clear and Chilly"
    assert result["windText"] == "Calm Winds"
    assert result["dateText"] == "SATURDAY, OCTOBER 16"
    assert result["weatherAccuracy"] == "exact_date_location"


def test_classification_boundaries():
    assert temperature_text(-1) == "Very Cold"
    assert temperature_text(10) == "Chilly"
    assert temperature_text(18) == "Mild"
    assert temperature_text(25) == "Warm"
    assert temperature_text(32) == "Hot"
    assert wind_text(4.9) == "Calm Winds"
    assert wind_text(15) == "Breezy"
    assert wind_text(25) == "Windy"
    assert wind_text(40) == "Strong Winds"
    assert [temperature_character(value) for value in (-1, 0, 10, 18, 25, 32)] == [
        "very_cold", "cold", "cool", "mild", "warm", "hot"
    ]


def test_monthly_condition_does_not_turn_cold_dry_data_into_sunny():
    row = {"avg_mean_temp_c": -2.92, "avg_precipitation_mm": 1.82, "avg_rainy_days": None, "avg_wind_kmh": 20.7}
    character = temperature_character(row["avg_mean_temp_c"])
    assert derive_climate_condition(row, character) == "generic"


def test_generic_condition_gets_meaningful_label_and_matching_copy_key():
    row = {"avg_mean_temp_c": 35, "avg_precipitation_mm": 0.03, "avg_wind_kmh": 13}
    assert condition_label(row, "generic") == ("HOT & DRY", "generic_hot_dry")
    row["avg_mean_temp_c"] = -2.92
    assert condition_label(row, "generic") == ("COLD CONDITIONS", "generic_very_cold_conditions")
    row["avg_mean_temp_c"] = 13
    row["avg_wind_kmh"] = 25
    assert condition_label(row, "generic") == ("COOL & BREEZY", "generic_cool_breezy")
    assert condition_label(row, "unknown") == ("COOL & BREEZY", "generic_cool_breezy")


def test_monthly_service_uses_stored_condition_as_source_of_truth():
    class MonthlyLocations:
        @staticmethod
        def find_city(*args):
            return {
                "id": 1, "location_key": "bengaluru", "city": "Bengaluru", "state_region": None,
                "country": "India", "country_code": "IN", "latitude": 12.97, "longitude": 77.59,
            }

    class MonthlyRepository:
        @staticmethod
        def get_monthly_weather(location_id, month):
            return {
                "avg_mean_temp_c": 35,
                "avg_min_temp_c": 27,
                "avg_max_temp_c": 45,
                "avg_precipitation_mm": 0.1,
                "avg_wind_kmh": 10,
                "climate_condition": "generic",
                "source": "nasa_power",
            }

    service = WeatherService(repository=MonthlyRepository, location_repository=MonthlyLocations, illustration_service=None)
    result = service.get_weather(date(1982, 7, 9), city="Bengaluru")
    assert result["condition"] == "generic"


def test_monthly_condition_uses_wetness_and_wind_without_fabricating_snow():
    assert derive_climate_condition({"avg_mean_temp_c": 27, "avg_precipitation_mm": 26.9, "avg_rainy_days": None, "avg_wind_kmh": 19}, "warm") == "rain"
    assert derive_climate_condition({"avg_mean_temp_c": 8, "avg_precipitation_mm": 1, "avg_rainy_days": None, "avg_wind_kmh": 25}, "cool") == "windy"
    assert derive_climate_condition({"avg_mean_temp_c": -2, "avg_precipitation_mm": 4, "avg_rainy_days": None, "avg_wind_kmh": 10}, "very_cold") == "showers"
    assert derive_climate_condition({"avg_mean_temp_c": -2, "avg_precipitation_mm": 0, "avg_rainy_days": None, "avg_wind_kmh": 10}, "very_cold") != "snow"


def test_missing_location_and_weather_are_safe():
    Repository.row = None
    missing_location = service().get_weather(date(1982, 5, 9))
    assert missing_location["available"] is False
    assert missing_location["reason"] == "missing_location"
    missing_weather = service().get_weather(date(1982, 5, 9), 12.9, 77.6)
    assert missing_weather["available"] is False
    assert missing_weather["reason"] == "weather_unavailable"


def test_real_monthly_weather_for_bengaluru():
    result = weather_service.get_weather(date(1982, 5, 9), city="Bengaluru")
    assert result["available"] is True
    assert result["month"] == 5
    assert result["weatherAccuracy"] == "monthly_climate"
    assert result["conditionText"] != "Weather unavailable"


def test_february_29_date_text():
    Repository.row = None
    result = service().get_weather(date(2000, 2, 29))
    assert result["dateText"] == "TUESDAY, FEBRUARY 29"
