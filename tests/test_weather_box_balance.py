"""Checks for the weather box's scoped visual composition rules."""

from pathlib import Path


CSS = Path("backend/web/static/css/chronicles/sections/weather.css")


def test_weather_box_dimensions_and_containment_are_preserved():
    text = CSS.read_text(encoding="utf-8")
    assert ".chronicle-weather" in text
    assert ".weather-art" in text
    assert "overflow: hidden" in text
    assert "height: 40px" in text


def test_weather_box_uses_smaller_balanced_content():
    text = CSS.read_text(encoding="utf-8")
    assert "--weather-image-size: 38px" in text
    assert "--weather-image-size: 40px" in text
    assert "--weather-image-size: 62px" not in text
    assert "--weather-image-size: 55px" not in text
    assert "object-fit: contain" in text
