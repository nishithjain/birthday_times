"""Structural checks for contained weather artwork."""

from pathlib import Path


TEMPLATE = Path("backend/web/templates/chronicles/_newspaper_main.html")
STYLESHEET = Path("backend/web/static/css/chronicles/chronicle_common.css")


def test_weather_image_has_dedicated_class_and_no_inline_size():
    html = TEMPLATE.read_text(encoding="utf-8")
    assert "newspaper-illustration weather-illustration" in html
    assert "style=\"width:36px" not in html
    assert "weather-icon weather-illustration" in html


def test_weather_art_is_fixed_and_contained_inside_box():
    css = STYLESHEET.read_text(encoding="utf-8")
    assert ".newspaper-page .weather-box" in css
    assert "box-sizing: border-box" in css
    assert "overflow: hidden" in css
    assert ".newspaper-page .weather-box .weather-illustration" in css
    assert "width: 46px" in css
    assert "height: 46px" in css
    assert "object-fit: contain" in css