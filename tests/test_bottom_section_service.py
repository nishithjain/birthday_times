"""Tests for database-backed Bottom section data."""

from backend.services import bottom_section_service as module
from backend.services.bottom_section_service import BottomSectionService


def test_bottom_data_selects_one_annual_value_and_five_facts(monkeypatch):
    def fetch_all(query, params=()):
        if "economic_indicators" in query:
            return [
                {"indicator": "Gold", "value": 34.72, "unit": "USD per troy ounce"},
                {"indicator": "Gold", "value": 34.72, "unit": "USD per troy ounce"},
                {"indicator": "Crude Oil (WTI)", "value": 2.57, "unit": "USD per barrel"},
                {"indicator": "Bread (White, Pan)", "value": 0.143, "unit": "USD per pound"},
            ]
        return [{"fact": f"Fact {index}"} for index in range(1, 6)]

    monkeypatch.setattr(module, "fetch_all", fetch_all)
    result = BottomSectionService().get_bottom_data(1950)

    assert [item["value"] for item in result["costs"]] == ["$ 34.72", "$ 2.57", "$ 0.143"]
    assert result["facts"] == [f"Fact {index}" for index in range(1, 6)]


def test_bottom_data_formats_missing_values(monkeypatch):
    monkeypatch.setattr(module, "fetch_all", lambda query, params=(): [])
    result = BottomSectionService().get_bottom_data(2026)

    assert [item["value"] for item in result["costs"]] == ["-", "-", "-"]
    assert result["facts"] == []


def test_bottom_data_uses_side_specific_florals():
    result = BottomSectionService().get_bottom_data(2015)

    assert result["floralArtworkLeft"].endswith("floral_2015_left.png")
    assert result["floralArtworkRight"].endswith("floral_2015_right.png")
    assert result["floralArtwork"] == result["floralArtworkLeft"]


def test_floral_artwork_uses_2015_assets_for_later_years():
    assert BottomSectionService.get_era_artwork(2026, "left").endswith("floral_2015_left.png")
    assert BottomSectionService.get_era_artwork(2026, "right").endswith("floral_2015_right.png")
