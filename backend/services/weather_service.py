"""Offline historical weather formatting for Birthday Chronicles."""

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

from backend.repositories.weather_repository import WeatherRepository
from backend.repositories.weather_location_repository import WeatherLocationRepository
from backend.services.calendar_service import CalendarService
from backend.services.climate_condition_classifier import DISPLAY_CONDITIONS, classify_monthly_climate, condition_label, temperature_character
from backend.services.illustration_service import illustration_service

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CONDITIONS_PATH = DATA_DIR / "weather_conditions.json"
logger = logging.getLogger(__name__)

CONDITION_NAMES = {
    0: "clear", 1: "clear", 2: "cloudy", 3: "cloudy",
    45: "fog", 48: "fog", 51: "rain", 53: "rain", 55: "rain",
    56: "rain", 57: "rain", 61: "rain", 63: "rain", 65: "rain",
    66: "rain", 67: "rain", 71: "snow", 73: "snow", 75: "snow",
    77: "snow", 80: "rain", 81: "rain", 82: "rain", 85: "snow",
    86: "snow", 95: "storm", 96: "storm", 99: "storm",
}


def temperature_text(mean_c: Optional[float]) -> Optional[str]:
    if mean_c is None:
        return None
    if mean_c < 0:
        return "Very Cold"
    if mean_c < 10:
        return "Cold"
    if mean_c < 18:
        return "Chilly"
    if mean_c < 25:
        return "Mild"
    if mean_c < 32:
        return "Warm"
    if mean_c < 38:
        return "Hot"
    return "Very Hot"


def derive_climate_condition(row: Dict[str, Any], character: str) -> str:
    """Compatibility wrapper for the centralized monthly classifier."""
    del character
    return classify_monthly_climate(row)[0]


def wind_text(speed_kmh: Optional[float]) -> Optional[str]:
    if speed_kmh is None:
        return None
    if speed_kmh < 5:
        return "Calm Winds"
    if speed_kmh < 15:
        return "Light Winds"
    if speed_kmh < 25:
        return "Breezy"
    if speed_kmh < 40:
        return "Windy"
    if speed_kmh < 60:
        return "Strong Winds"
    return "Very Strong Winds"


def rain_text(precipitation_mm: Optional[float], rainy_days: Optional[float]) -> Optional[str]:
    if precipitation_mm is None and rainy_days is None:
        return None
    rainy_days = rainy_days or 0
    precipitation_mm = precipitation_mm or 0
    if rainy_days == 0 and precipitation_mm < 10:
        return "Mostly Dry"
    if rainy_days <= 4 and precipitation_mm < 80:
        return "Occasional Showers"
    if rainy_days <= 12 and precipitation_mm < 220:
        return "Showers"
    return "Rainy"


def _condition_mapping() -> Dict[str, Any]:
    try:
        return json.loads(CONDITIONS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"fallbackIllustrationId": "weather_generic", "conditions": {}}


def illustration_id_for_condition(condition: Optional[str]) -> str:
    mapping = _condition_mapping()
    normalized = (condition or "unknown").strip().casefold().replace("-", "_").replace(" ", "_")
    entry = mapping.get("conditions", {}).get(normalized)
    return (entry or {}).get("illustrationId") or mapping.get("fallbackIllustrationId", "weather_generic")


class WeatherService:
    def __init__(self, repository=WeatherRepository, location_repository=WeatherLocationRepository, templates_path: Optional[Path] = None, illustration_service=illustration_service):
        self.repository = repository
        self.location_repository = location_repository
        self.templates_path = templates_path or DATA_DIR / "weather_templates.json"
        self.illustration_service = illustration_service

    def _template(self) -> Dict[str, str]:
        try:
            payload = json.loads(self.templates_path.read_text(encoding="utf-8"))
            for template in payload.get("templates", []):
                if template.get("id") == payload.get("defaultTemplateId"):
                    return template
        except (OSError, json.JSONDecodeError):
            pass
        return {
            "title": "TODAY'S WEATHER",
            "primaryTemplate": "{conditionText}",
            "secondaryTemplate": "{windText}",
            "dateTemplate": "{dayOfWeekUpper}, {monthNameUpper} {day}",
        }

    def get_weather(self, birth_date: date, latitude: Optional[float] = None, longitude: Optional[float] = None, city: Optional[str] = None, country: Optional[str] = None, state_region: Optional[str] = None, country_code: Optional[str] = None, location_id: Optional[int] = None, newspaper_style_id: Optional[str] = None) -> Dict[str, Any]:
        template = self._template()
        date_values = {
            "dayOfWeekUpper": CalendarService.day_of_week(birth_date).upper(),
            "monthNameUpper": birth_date.strftime("%B").upper(),
            "day": birth_date.day,
        }
        base = {
            "available": False,
            "date": birth_date.isoformat(),
            "month": birth_date.month,
            "location": {"city": city, "country": country, "latitude": latitude, "longitude": longitude},
            "weatherAccuracy": "unavailable",
            "source": None,
            "title": template.get("titleTemplate", template.get("title", "TODAY'S WEATHER")),
            "dateText": template.get("dateTemplate", "{dayOfWeekUpper}, {monthNameUpper} {day}").format(**date_values),
            "illustration": None,
        }
        location = None
        if location_id is not None:
            location = self.location_repository.get_by_id(location_id)
        elif city:
            location = self.location_repository.find_city(city, state_region, country_code)
            if not location and latitude is None and longitude is None:
                base["reason"] = "weather_location_not_found"
                logger.debug(
                    "[WEATHER DEBUG] birth_date=%s birth_month=%s raw_location=%r "
                    "normalized_location=%r resolved_location_id=None resolved_city=None "
                    "monthly_weather_found=False weather_available=False failure_reason=%s",
                    birth_date.isoformat(), birth_date.month, city, city, base["reason"],
                )
                return base
        if location:
            latitude, longitude = location["latitude"], location["longitude"]
            base["location"].update({"id": location["id"], "locationKey": location["location_key"], "city": location["city"], "stateRegion": location.get("state_region"), "country": location["country"], "countryCode": location["country_code"], "latitude": latitude, "longitude": longitude})
        elif latitude is None or longitude is None:
            base["reason"] = "missing_location"
            logger.debug(
                "[WEATHER DEBUG] birth_date=%s birth_month=%s raw_location=%r "
                "normalized_location=%r resolved_location_id=None resolved_city=None "
                "monthly_weather_found=False weather_available=False failure_reason=%s",
                birth_date.isoformat(), birth_date.month, city, city, base["reason"],
            )
            return base
        monthly_mode = bool(location and hasattr(self.repository, "get_monthly_weather"))
        if location:
            if monthly_mode:
                row = self.repository.get_monthly_weather(location["id"], birth_date.month)
            else:
                row = self.repository.get_daily_weather(birth_date, float(latitude), float(longitude), tolerance=0.1)
        else:
            # Legacy coordinate callers remain supported, but city-based runtime never uses this path.
            row = self.repository.get_daily_weather(birth_date, float(latitude), float(longitude), tolerance=0.1)
        if not row:
            base["reason"] = "monthly_weather_not_found" if monthly_mode else "weather_unavailable"
            logger.debug(
                "[WEATHER DEBUG] birth_date=%s birth_month=%s raw_location=%r "
                "normalized_location=%r resolved_location_id=%s resolved_city=%r "
                "monthly_weather_found=False weather_available=False failure_reason=%s",
                birth_date.isoformat(), birth_date.month, city, city,
                location.get("id") if location else None,
                location.get("city") if location else None, base["reason"],
            )
            return base
        if monthly_mode:
            character = temperature_character(row.get("avg_mean_temp_c"))
            condition = (row.get("climate_condition") or "generic").strip().casefold().replace("-", "_").replace(" ", "_")
            if condition not in DISPLAY_CONDITIONS:
                condition = "generic"
            display_label, copy_key = condition_label(row, condition, character)
            temperature = temperature_text(row.get("avg_mean_temp_c"))
            precipitation = rain_text(row.get("avg_precipitation_mm"), row.get("avg_rainy_days"))
            condition_text = " with ".join(part for part in (temperature, precipitation) if part) or "Typical Weather"
            wind = wind_text(row.get("avg_wind_kmh"))
            values = {"conditionText": condition_text, "windText": wind}
        else:
            condition = CONDITION_NAMES.get(row.get("weather_code"), "cloudy")
            display_label, copy_key = condition.replace("_", " ").upper(), condition
            temperature = temperature_text(row.get("temperature_mean_c"))
            condition_text = " and ".join(part for part in (condition.title(), temperature) if part)
            values = {"conditionText": condition_text, "windText": wind_text(row.get("wind_speed_max_kmh"))}
        base.update({
            "available": True,
            "condition": condition,
            "conditionLabel": display_label,
            "weatherCopyKey": copy_key,
            "conditionText": template.get("primaryTemplate", "{conditionText}").format(**values),
            "windText": template.get("secondaryTemplate", "{windText}").format(**values) if values["windText"] else None,
            "weatherAccuracy": "monthly_climate" if monthly_mode else "exact_date_location",
            "source": {"provider": row.get("source"), "dataset": row.get("source_dataset"), "referencePeriod": row.get("reference_period")},
            "weatherCode": row.get("weather_code"),
            "temperatureDescriptor": temperature,
            "temperatureCharacter": character if monthly_mode else None,
            "temperature": {"minC": row.get("avg_min_temp_c", row.get("temperature_min_c")), "maxC": row.get("avg_max_temp_c", row.get("temperature_max_c")), "meanC": row.get("avg_mean_temp_c", row.get("temperature_mean_c"))},
            "wind": {"maxKmh": row.get("avg_wind_kmh", row.get("wind_speed_max_kmh"))},
            "precipitationMm": row.get("avg_precipitation_mm", row.get("precipitation_mm")),
            "dataQuality": row.get("data_quality"),
        })
        logger.debug(
            "[WEATHER DEBUG] birth_date=%s birth_month=%s raw_location=%r "
            "normalized_location=%r resolved_location_id=%s resolved_city=%r "
            "monthly_weather_found=True weather_available=True failure_reason=None",
            birth_date.isoformat(), birth_date.month, city, city,
            location.get("id") if location else None, location.get("city") if location else None,
        )
        if self.illustration_service:
            selected_condition = condition
            if monthly_mode and selected_condition == "climate":
                selected_condition = {
                    "Mostly Dry": "sunny",
                    "Occasional Showers": "showers",
                    "Showers": "showers",
                    "Rainy": "rain",
                }.get(precipitation, "unknown")
            illustration_id = illustration_id_for_condition(selected_condition)
            base["condition"] = selected_condition
            base["illustrationId"] = illustration_id
            illustration = self.illustration_service.resolve_by_id(illustration_id, newspaper_style_id)
            if illustration is None:
                illustration_id = illustration_id_for_condition("unknown")
                base["illustrationId"] = illustration_id
                illustration = self.illustration_service.resolve_by_id(illustration_id, newspaper_style_id)
            base["illustration"] = illustration
        return base


weather_service = WeatherService()
