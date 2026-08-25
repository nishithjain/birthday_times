"""NASA POWER monthly climatology provider."""

import time
from datetime import date
from typing import Any, Dict, Iterable, Optional

import requests

NASA_POWER_CLIMATOLOGY_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"
NASA_POWER_COMMUNITY = "AG"
NASA_POWER_PARAMETERS = ("T2M", "T2M_MIN", "T2M_MAX", "PRECTOTCORR", "WS10M")
NASA_POWER_TEMPERATURE_UNIT = "C"
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
RETRY_DELAYS_SECONDS = (5, 15, 30, 60)
MONTH_KEYS = {name: index for index, name in enumerate(("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}


class NasaPowerError(RuntimeError):
    """A bounded NASA POWER request or response failure."""
    
    def __init__(self, message: str, *, status_code: Optional[int] = None, url: Optional[str] = None, payload: Any = None, parameters: Optional[Iterable[str]] = None, community: Optional[str] = None, latitude: Optional[float] = None, longitude: Optional[float] = None):
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.payload = payload
        self.parameters = tuple(parameters or ())
        self.community = community
        self.latitude = latitude
        self.longitude = longitude


def _error_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return str(payload)[:500]
    values = []
    for key in ("errors", "error", "detail", "message", "messages"):
        value = payload.get(key)
        if value:
            values.append(f"{key}: {value}")
    return "; ".join(values)[:1000] or "NASA POWER returned an error payload"


def format_error(error: NasaPowerError) -> str:
    """Render actionable provider diagnostics without dumping a full response."""
    lines = ["NASA POWER request failed"]
    if error.status_code is not None:
        lines.append(f"HTTP status: {error.status_code}")
    if error.url:
        lines.append(f"Request URL: {error.url}")
    if error.parameters:
        lines.append(f"Parameters: {','.join(error.parameters)}")
    if error.community:
        lines.append(f"Community: {error.community}")
    if error.latitude is not None and error.longitude is not None:
        lines.append(f"Latitude: {error.latitude}")
        lines.append(f"Longitude: {error.longitude}")
    lines.append(f"NASA message: {error}")
    if error.payload:
        lines.append(f"Response excerpt: {str(error.payload)[:500]}")
    return "\n".join(lines)


def _parameter_values(payload: Dict[str, Any], parameter: str) -> Dict[str, Any]:
    properties = payload.get("properties")
    if not isinstance(properties, dict):
        raise NasaPowerError("NASA POWER response has no properties object")
    parameters = properties.get("parameter")
    if not isinstance(parameters, dict):
        raise NasaPowerError("NASA POWER response has no parameter object")
    values = parameters.get(parameter)
    if not isinstance(values, dict):
        raise NasaPowerError(f"NASA POWER response is missing parameter {parameter}")
    return values


def parse_climatology(payload: Dict[str, Any]) -> list[Dict[str, Any]]:
    """Normalize POWER JAN..DEC values; ANN and unknown keys are ignored."""
    if not isinstance(payload, dict):
        raise NasaPowerError("NASA POWER response was not a JSON object", payload=payload)
    if any(payload.get(key) for key in ("errors", "error", "detail")):
        raise NasaPowerError(_error_message(payload), payload=payload)
    values = {parameter: _parameter_values(payload, parameter) for parameter in NASA_POWER_PARAMETERS}
    reference_period = None
    properties = payload.get("properties", {})
    if isinstance(properties, dict):
        reference_period = properties.get("period") or properties.get("reference_period")
    header = payload.get("header")
    if not reference_period and isinstance(header, dict):
        reference_period = header.get("range")
    parameter_metadata = payload.get("parameters") if isinstance(payload.get("parameters"), dict) else {}
    rows = []
    for month_name, month in MONTH_KEYS.items():
        def value(parameter: str):
            raw = values[parameter].get(month_name)
            return None if raw in (None, -999, -999.0) else raw
        rows.append({
            "month": month,
            "avg_mean_temp_c": value("T2M"),
            "avg_min_temp_c": value("T2M_MIN"),
            "avg_max_temp_c": value("T2M_MAX"),
            "avg_precipitation_mm": value("PRECTOTCORR"),
            "avg_rainy_days": None,
            "avg_wind_kmh": (value("WS10M") * 3.6) if value("WS10M") is not None and parameter_metadata.get("WS10M", {}).get("units") == "m/s" else value("WS10M"),
            "source": "nasa_power",
            "source_dataset": "NASA POWER Climatology Point API; T2M/T2M_MIN/T2M_MAX are °C; PRECTOTCORR is mm/day; WS10M converted m/s to km/h",
            "reference_period": reference_period,
        })
    return rows


class NasaPowerClimatologyProvider:
    """Fetch one already-aggregated monthly climate profile per coordinate."""

    def __init__(self, community: str = NASA_POWER_COMMUNITY, max_retries: int = 4, timeout: int = 60, sleep=time.sleep):
        self.community = community
        self.max_retries = max_retries
        self.timeout = timeout
        self.sleep = sleep

    def fetch_climatology(self, latitude: float, longitude: float) -> list[Dict[str, Any]]:
        params = {
            "parameters": ",".join(NASA_POWER_PARAMETERS),
            "community": self.community,
            "longitude": longitude,
            "latitude": latitude,
            "format": "JSON",
        }
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.get(NASA_POWER_CLIMATOLOGY_URL, params=params, timeout=self.timeout)
            except (requests.Timeout, requests.ConnectionError) as exc:
                if attempt >= self.max_retries:
                    raise NasaPowerError(f"network error after {attempt} retries: {exc}") from exc
                self.sleep(RETRY_DELAYS_SECONDS[min(attempt, len(RETRY_DELAYS_SECONDS) - 1)])
                continue
            if response.status_code == 200:
                try:
                    payload = response.json()
                    return parse_climatology(payload)
                except (ValueError, NasaPowerError) as exc:
                    if isinstance(exc, NasaPowerError):
                        raise NasaPowerError(str(exc), status_code=response.status_code, url=getattr(response, "url", None), payload=getattr(exc, "payload", None), parameters=NASA_POWER_PARAMETERS, community=self.community, latitude=latitude, longitude=longitude) from exc
                    raise NasaPowerError("NASA POWER returned malformed JSON", status_code=response.status_code, url=getattr(response, "url", None), parameters=NASA_POWER_PARAMETERS, community=self.community, latitude=latitude, longitude=longitude) from exc
            if response.status_code not in RETRYABLE_STATUS_CODES:
                try:
                    payload = response.json()
                except ValueError:
                    payload = getattr(response, "text", "")[:1000]
                raise NasaPowerError(_error_message(payload), status_code=response.status_code, url=getattr(response, "url", None), payload=payload, parameters=NASA_POWER_PARAMETERS, community=self.community, latitude=latitude, longitude=longitude)
            if attempt >= self.max_retries:
                raise NasaPowerError(f"HTTP {response.status_code} after {self.max_retries} retries", status_code=response.status_code, url=getattr(response, "url", None), parameters=NASA_POWER_PARAMETERS, community=self.community, latitude=latitude, longitude=longitude)
            retry_after = response.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else RETRY_DELAYS_SECONDS[min(attempt, len(RETRY_DELAYS_SECONDS) - 1)]
            except ValueError:
                delay = RETRY_DELAYS_SECONDS[min(attempt, len(RETRY_DELAYS_SECONDS) - 1)]
            self.sleep(max(0, delay))
        raise NasaPowerError("NASA POWER request failed")
