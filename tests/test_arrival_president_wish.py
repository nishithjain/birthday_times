"""Tests for the fictional White House arrival reaction."""

from datetime import date

from backend.services.arrival_message_service import ArrivalMessageService


CALENDAR = {"day_of_week": "Sunday", "western_zodiac": "Taurus", "birthstone": "Emerald", "generation": "Millennials"}


def test_president_name_is_injected_without_hardcoding():
    result = ArrivalMessageService().get_arrival(
        date(1982, 5, 9), "Nishith Jain M R", "India", CALENDAR, "1980", "Ronald Reagan"
    )
    assert result["kicker"] == "NEWS OF ARRIVAL REACHES WHITE HOUSE"
    assert "President Ronald Reagan" in result["presidentWishText"]
    assert "WASHINGTON (SPECIAL)" in result["presidentWishText"]
    assert result["isNoveltyCopy"] is True
    assert "(AP)" not in result["presidentWishText"]


def test_missing_president_uses_safe_novelty_fallback():
    result = ArrivalMessageService().get_arrival(
        date(1982, 5, 9), "Nishith", "India", CALENDAR, "1980", None
    )
    assert "President None" not in result["presidentWishText"]
    assert "President Unknown" not in result["presidentWishText"]
    assert "WASHINGTON (SPECIAL)" in result["presidentWishText"]


def test_templates_do_not_hardcode_real_president_names():
    text = ArrivalMessageService().data_file.read_text(encoding="utf-8")
    for name in ("Lyndon B. Johnson", "Ronald Reagan", "Harry S. Truman"):
        assert name not in text
