"""Offline tests for NASA POWER climatology requests and parsing."""

from datetime import date
from unittest.mock import patch

import pytest

from backend.providers.weather.nasa_power import (
    NASA_POWER_CLIMATOLOGY_URL,
    NASA_POWER_PARAMETERS,
    NASA_POWER_TEMPERATURE_UNIT,
    NasaPowerClimatologyProvider,
    NasaPowerError,
    parse_climatology,
)


def payload():
    months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    return {"properties": {"parameter": {
        "T2M": {month: 25.0 for month in months + ["ANN"]},
        "T2M_MIN": {month: 20.0 for month in months + ["ANN"]},
        "T2M_MAX": {month: 30.0 for month in months + ["ANN"]},
        "PRECTOTCORR": {month: 10.0 for month in months + ["ANN"]},
        "WS10M": {month: 3.0 for month in months + ["ANN"]},
    }, "period": "POWER climatology"}}


def test_parse_maps_months_and_ignores_ann():
    rows = parse_climatology(payload())
    assert len(rows) == 12
    assert [row["month"] for row in rows] == list(range(1, 13))
    assert all(row["avg_rainy_days"] is None for row in rows)
    assert rows[0]["reference_period"] == "POWER climatology"
    assert NASA_POWER_TEMPERATURE_UNIT == "C"


def test_provider_uses_climatology_endpoint_and_parameters():
    response = type("Response", (), {"status_code": 200, "headers": {}, "json": lambda self: payload()})()
    with patch("backend.providers.weather.nasa_power.requests.get", return_value=response) as request:
        rows = NasaPowerClimatologyProvider(sleep=lambda _: None).fetch_climatology(12.97, 77.59)
    params = request.call_args.kwargs["params"]
    assert request.call_args.args[0] == NASA_POWER_CLIMATOLOGY_URL
    assert params["format"] == "JSON"
    assert params["community"] == "AG"
    assert params["parameters"] == ",".join(NASA_POWER_PARAMETERS)
    assert "start" not in params and "end" not in params
    assert len(rows) == 12


def test_429_then_success_and_bounded_failure():
    response_429 = type("Response", (), {"status_code": 429, "headers": {}, "json": lambda self: {}})()
    response_ok = type("Response", (), {"status_code": 200, "headers": {}, "json": lambda self: payload()})()
    delays = []
    with patch("backend.providers.weather.nasa_power.requests.get", side_effect=[response_429, response_ok]):
        assert len(NasaPowerClimatologyProvider(sleep=delays.append).fetch_climatology(1, 2)) == 12
    assert delays == [5]
    with patch("backend.providers.weather.nasa_power.requests.get", return_value=response_429):
        with pytest.raises(NasaPowerError):
            NasaPowerClimatologyProvider(sleep=lambda _: None).fetch_climatology(1, 2)
