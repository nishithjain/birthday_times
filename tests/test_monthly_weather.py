"""Offline tests for monthly climate aggregation and city-based runtime."""

from datetime import date

from backend.importers.monthly_weather import monthly_profiles, nasa_profiles
from backend.services.weather_service import WeatherService


class LocationRepository:
    @staticmethod
    def find_city(city, state_region=None, country_code=None):
        return {"id": 7, "location_key": "india_karnataka_bengaluru", "city": "Bengaluru", "state_region": "Karnataka", "country": "India", "country_code": "IN", "latitude": 12.9716, "longitude": 77.5946}

    @staticmethod
    def get_by_id(location_id):
        return LocationRepository.find_city("Bengaluru")


class WeatherRepository:
    @staticmethod
    def get_monthly_weather(location_id, month):
        return {"location_id": location_id, "month": month, "avg_min_temp_c": 21, "avg_max_temp_c": 30, "avg_mean_temp_c": 25, "avg_precipitation_mm": 110, "avg_rainy_days": 8, "avg_wind_kmh": 9, "source": "open-meteo", "source_dataset": "archive", "reference_period": "1991-2020"}


def test_monthly_profiles_aggregate_one_month():
    rows = [{"weather_date": "2020-05-09", "temperature_min_c": 20, "temperature_max_c": 30, "temperature_mean_c": 25, "precipitation_mm": 3, "wind_speed_max_kmh": 9}]
    result = monthly_profiles(rows, 7)
    assert len(result) == 1
    assert result[0]["month"] == 5
    assert result[0]["avg_mean_temp_c"] == 25
    assert result[0]["reference_period"] == "2011-2020"


def test_nasa_profiles_populates_derived_climate_condition():
    rows = [{
        "month": 1,
        "avg_min_temp_c": 13.02,
        "avg_mean_temp_c": 20.07,
        "avg_max_temp_c": 27.93,
        "avg_precipitation_mm": 0.55,
        "avg_rainy_days": None,
        "avg_wind_kmh": 14.364,
        "source": "nasa_power",
    }]
    result = nasa_profiles(rows, 1)
    assert result[0]["climate_condition"] == "sunny"


def test_weather_uses_city_month_not_birth_year():
    service = WeatherService(repository=WeatherRepository, location_repository=LocationRepository)
    may_1955 = service.get_weather(date(1955, 5, 9), city="Bengaluru")
    may_1982 = service.get_weather(date(1982, 5, 9), city="Bengaluru")
    assert may_1955["available"] is True
    assert may_1955["conditionText"] == may_1982["conditionText"]
    assert may_1955["weatherAccuracy"] == "monthly_climate"
    assert may_1955["dateText"] != may_1982["dateText"]
