"""Structural checks for contained weather artwork."""

from pathlib import Path


TEMPLATE = Path("backend/web/templates/chronicles/sections/weather.html")
STYLESHEET = Path("backend/web/static/css/chronicles/sections/weather.css")


def test_weather_image_has_dedicated_class_and_no_inline_size():
    html = TEMPLATE.read_text(encoding="utf-8")
    assert "newspaper-illustration" in html
    assert "weather-illustration" in html
    assert "style=\"width:36px" not in html


def test_weather_art_is_fixed_and_contained_inside_box():
    css = STYLESHEET.read_text(encoding="utf-8")
    assert ".chronicle-weather" in css
    assert "overflow: hidden" in css
    assert ".weather-art" in css
    assert "width: 44px" in css
    assert "height: 40px" in css
    assert "object-fit: contain" in css