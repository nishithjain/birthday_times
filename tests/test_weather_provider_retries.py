"""Offline tests for Open-Meteo retry and request shaping behavior."""

from datetime import date
from unittest.mock import patch

import pytest
import requests

from backend.importers.historical_weather import DAILY_FIELDS, OpenMeteoHistoricalProvider, WeatherProviderError


class Response:
    def __init__(self, status, payload=None, headers=None):
        self.status_code = status
        self._payload = payload or {"daily": {"time": []}}
        self.headers = headers or {}

    def json(self):
        return self._payload


def test_429_then_success_retries_with_backoff():
    responses = [Response(429), Response(200)]
    delays = []
    with patch("backend.importers.historical_weather.requests.get", side_effect=responses) as request:
        result = OpenMeteoHistoricalProvider().fetch(date(2011, 1, 1), date(2020, 12, 31), 1, 2, sleep=delays.append)
    assert result["daily"]["time"] == []
    assert delays == [5]
    assert request.call_count == 2
    assert request.call_args.kwargs["params"]["daily"] == DAILY_FIELDS


def test_retry_after_header_is_used():
    delays = []
    with patch("backend.importers.historical_weather.requests.get", side_effect=[Response(429, headers={"Retry-After": "7"}), Response(200)]) as request:
        OpenMeteoHistoricalProvider().fetch(date(2011, 1, 1), date(2020, 12, 31), 1, 2, sleep=delays.append)
    assert delays == [7.0]
    assert request.call_count == 2


def test_repeated_429_is_bounded():
    delays = []
    with patch("backend.importers.historical_weather.requests.get", side_effect=[Response(429)] * 5):
        with pytest.raises(WeatherProviderError, match="HTTP 429"):
            OpenMeteoHistoricalProvider().fetch(date(2011, 1, 1), date(2020, 12, 31), 1, 2, sleep=delays.append)
    assert delays == [5, 15, 30, 60]


def test_500_then_success_retries_and_400_does_not():
    delays = []
    with patch("backend.importers.historical_weather.requests.get", side_effect=[Response(500), Response(200)]) as request:
        OpenMeteoHistoricalProvider().fetch(date(2011, 1, 1), date(2020, 12, 31), 1, 2, sleep=delays.append)
    assert request.call_count == 2
    assert delays == [5]
    with patch("backend.importers.historical_weather.requests.get", return_value=Response(400)) as request:
        with pytest.raises(WeatherProviderError, match="HTTP 400"):
            OpenMeteoHistoricalProvider().fetch(date(2011, 1, 1), date(2020, 12, 31), 1, 2, sleep=delays.append)
    assert request.call_count == 1
