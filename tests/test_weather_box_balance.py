"""Checks for the weather box's scoped visual composition rules."""

from pathlib import Path


CSS = Path("backend/web/static/css/chronicles/chronicle_common.css")


def test_weather_box_dimensions_and_containment_are_preserved():
    text = CSS.read_text(encoding="utf-8")
    assert "width: 170px" not in text
    assert "height: 100px" not in text
    assert ".newspaper-page .weather-box" in text
    assert "overflow: hidden" in text
    assert "gap: 3px" in text


def test_weather_box_uses_larger_balanced_content():
    text = CSS.read_text(encoding="utf-8")
    assert "width: 46px" in text
    assert "height: 46px" in text
    assert "max-width: 46px" in text
    assert "max-height: 46px" in text
    assert "font-size: 11px" in text
    assert "font-size: 10.5px" in text
    assert "font-size: 10px" in text
    assert "object-fit: contain" in text
    assert "overflow-wrap: anywhere" in text