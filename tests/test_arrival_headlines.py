"""Tests for dynamic president-based arrival headlines."""

from datetime import date

from backend.services.arrival_message_service import ArrivalMessageService
from backend.services.president_service import PresidentService

CALENDAR = {"day_of_week": "Sunday", "western_zodiac": "Taurus", "birthstone": "Emerald", "generation": "Millennials"}


def test_lbj_and_reagan_headlines_use_president_service_name():
    service = ArrivalMessageService()
    president_service = PresidentService()
    lbj_date = date(1965, 5, 9)
    reagan_date = date(1982, 5, 9)
    lbj = president_service.get_president_for_date(lbj_date)
    reagan = president_service.get_president_for_date(reagan_date)
    lbj_arrival = service.get_arrival(lbj_date, "Nishith Jain M R", "India", CALENDAR, "1960", lbj["name"])
    reagan_arrival = service.get_arrival(reagan_date, "Nishith Jain M R", "India", CALENDAR, "1980", reagan["name"])
    assert lbj_arrival["headline"] == "PRESIDENT JOHNSON NOTES BIRTH OF NISHITH JAIN M R."
    assert reagan_arrival["headline"] == "PRESIDENT REAGAN GREETS NEW ARRIVAL NISHITH JAIN M R."
    assert "President Lyndon B. Johnson" in lbj_arrival["presidentWishText"]
    assert "President Ronald Reagan" in reagan_arrival["presidentWishText"]


def test_transition_date_changes_president_surname():
    service = ArrivalMessageService()
    president_service = PresidentService()
    before = date(1961, 1, 19)
    after = date(1961, 1, 20)
    before_president = president_service.get_president_for_date(before)["name"]
    after_president = president_service.get_president_for_date(after)["name"]
    before_result = service.get_arrival(before, "Alex", "India", CALENDAR, "1960", before_president)
    after_result = service.get_arrival(after, "Alex", "India", CALENDAR, "1960", after_president)
    assert "EISENHOWER" in before_result["headline"]
    assert "KENNEDY" in after_result["headline"]


def test_missing_president_gets_generic_headline():
    result = ArrivalMessageService().get_arrival(date(1982, 5, 9), "Nishith", "India", CALENDAR, "1980", None)
    assert result["headline"] == "WASHINGTON GREETS NEW ARRIVAL NISHITH."
    assert "President None" not in result["presidentWishText"]
