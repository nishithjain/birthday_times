"""Application-derived classifications for monthly climate rows."""

from typing import Any, Dict, Optional, Tuple

# NASA POWER PRECTOTCORR is climatological daily precipitation in mm/day.
RAIN_PRECIPITATION_MM_PER_DAY = 10.0
SHOWERS_PRECIPITATION_MM_PER_DAY = 3.0
WINDY_KMH = 25.0

TEMPERATURE_LABELS = {
    "very_cold": "COLD",
    "cold": "COLD",
    "cool": "COOL",
    "mild": "MILD",
    "warm": "WARM",
    "hot": "HOT",
}

DISPLAY_CONDITIONS = {
    "sunny", "partly_cloudy", "cloudy", "showers", "rain", "thunderstorm",
    "snow", "fog", "windy", "generic",
}


def temperature_character(mean_c: Optional[float]) -> str:
    """Classify monthly mean temperature independently of precipitation."""
    if mean_c is None:
        return "mild"
    if mean_c < 0:
        return "very_cold"
    if mean_c < 10:
        return "cold"
    if mean_c < 18:
        return "cool"
    if mean_c < 25:
        return "mild"
    if mean_c < 32:
        return "warm"
    return "hot"


def classify_monthly_climate(row: Dict[str, Any]) -> Tuple[str, str, str]:
    """Return condition, temperature character, and the classification reason.

    Monthly NASA rows have no cloud, snowfall, precipitation-phase, or weather-code
    signal, so this classifier uses precipitation and wind conservatively. Snow,
    fog, cloud, and thunderstorm are never inferred from these fields alone.
    """
    mean_c = row.get("avg_mean_temp_c")
    character = temperature_character(mean_c)
    precipitation = row.get("avg_precipitation_mm")
    rainy_days = row.get("avg_rainy_days")
    wind = row.get("avg_wind_kmh")
    wet_days = rainy_days is not None and rainy_days > 0

    if precipitation is None and not wet_days:
        return "generic", character, "no precipitation signal"
    if precipitation is None and wet_days:
        if rainy_days >= 12:
            return "rain", character, f"rainy days {rainy_days:g} >= 12"
        return "showers", character, "rainy days present"
    if precipitation is not None and precipitation >= RAIN_PRECIPITATION_MM_PER_DAY:
        return "rain", character, f"precipitation {precipitation:g} mm/day >= {RAIN_PRECIPITATION_MM_PER_DAY:g}"
    if precipitation is not None and (precipitation >= SHOWERS_PRECIPITATION_MM_PER_DAY or wet_days):
        return "showers", character, f"precipitation {precipitation:g} mm/day >= {SHOWERS_PRECIPITATION_MM_PER_DAY:g} or rainy days present"
    if wind is not None and wind >= WINDY_KMH:
        return "windy", character, f"wind {wind:g} km/h >= {WINDY_KMH:g} with low/moderate precipitation"
    if character in {"mild", "warm", "hot"}:
        return "sunny", character, f"dry precipitation and {character} temperature"
    return "generic", character, f"dry precipitation with {character} temperature; sky condition unavailable"


def condition_label(row: Dict[str, Any], condition: str, character: Optional[str] = None) -> Tuple[str, str]:
    """Return a reader-facing label and matching copy key for a condition."""
    character = character or temperature_character(row.get("avg_mean_temp_c"))
    condition = condition if condition in DISPLAY_CONDITIONS else "generic"
    if condition != "generic":
        return condition.replace("_", " ").upper(), condition

    temperature = TEMPERATURE_LABELS.get(character)
    precipitation = row.get("avg_precipitation_mm")
    rainy_days = row.get("avg_rainy_days")
    wind = row.get("avg_wind_kmh")
    wet = (precipitation is not None and precipitation >= SHOWERS_PRECIPITATION_MM_PER_DAY) or (rainy_days is not None and rainy_days > 0)
    dry = precipitation is not None and precipitation < SHOWERS_PRECIPITATION_MM_PER_DAY and not (rainy_days and rainy_days > 0)
    breezy = wind is not None and wind >= WINDY_KMH

    if temperature and wet:
        return f"{temperature} & WET", "generic_wet"
    if temperature and dry and character in {"mild", "warm", "hot"}:
        return f"{temperature} & DRY", f"generic_{character}_dry"
    if temperature and breezy:
        return f"{temperature} & BREEZY", f"generic_{character}_breezy"
    if temperature:
        return f"{temperature} CONDITIONS", f"generic_{character}_conditions"
    return "SEASONAL CONDITIONS", "generic_seasonal"
