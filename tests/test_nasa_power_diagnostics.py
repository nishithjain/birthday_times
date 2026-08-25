"""Diagnostics and validation tests for NASA POWER."""

from unittest.mock import patch

import pytest

from backend.providers.weather.nasa_power import NasaPowerClimatologyProvider, NasaPowerError, format_error, parse_climatology
from tests.test_nasa_power_provider import payload


def response(status, body, url="https://power.test/request"):
    return type("Response", (), {
        "status_code": status,
        "headers": {},
        "url": url,
        "text": str(body),
        "json": lambda self: body,
    })()


def test_informational_messages_are_success():
    body = payload()
    body["messages"] = ["The requested parameters are retrieved from a pre-computed climatological period"]
    assert len(parse_climatology(body)) == 12


@pytest.mark.parametrize("status, body", [
    (400, {"errors": ["Invalid parameter"]}),
    (422, {"messages": ["Invalid community"], "detail": "community is not supported"}),
])
def test_http_errors_include_actual_nasa_details(status, body):
    with patch("backend.providers.weather.nasa_power.requests.get", return_value=response(status, body)):
        with pytest.raises(NasaPowerError) as raised:
            NasaPowerClimatologyProvider().fetch_climatology(12.9, 77.6)
    error = raised.value
    formatted = format_error(error)
    assert f"HTTP status: {status}" in formatted
    assert "Request URL:" in formatted
    assert "Parameters:" in formatted
    assert "Latitude: 12.9" in formatted
    assert "community is not supported" in formatted or "Invalid parameter" in formatted


def test_http_200_error_payload_is_reported():
    with patch("backend.providers.weather.nasa_power.requests.get", return_value=response(200, {"errors": ["Bad parameter"]})):
        with pytest.raises(NasaPowerError) as raised:
            NasaPowerClimatologyProvider().fetch_climatology(1, 2)
    assert "Bad parameter" in format_error(raised.value)


def test_malformed_json_is_reported():
    bad = type("Response", (), {"status_code": 200, "headers": {}, "url": "https://power.test", "json": lambda self: (_ for _ in ()).throw(ValueError("bad json"))})()
    with patch("backend.providers.weather.nasa_power.requests.get", return_value=bad):
        with pytest.raises(NasaPowerError, match="malformed JSON"):
            NasaPowerClimatologyProvider().fetch_climatology(1, 2)


def test_wind_units_are_converted_from_meters_per_second():
    body = payload()
    body["parameters"] = {"WS10M": {"units": "m/s"}}
    rows = parse_climatology(body)
    assert rows[0]["avg_wind_kmh"] == pytest.approx(10.8)
