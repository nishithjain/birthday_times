"""Offline tests for FamousBirthdaysService."""

import json
from datetime import date

from backend.models.person import FamousPerson
from backend.services.famous_birthdays_service import FamousBirthdaysService, english_list, ordinal


def person(name, birth, score, occupation, qid):
    return FamousPerson(name=name, birth_date=date.fromisoformat(birth), notability_score=score, occupation=occupation, wikidata_id=qid)


def service(tmp_path, people, overrides=None):
    templates = tmp_path / "templates.json"
    templates.write_text(json.dumps({"defaultTemplateId": "classic", "templates": [{
        "id": "classic",
        "headlineTemplate": "CELEBRITIES SHARE {monthNameShortUpper} {dayOrdinalUpper} BIRTHDAY",
        "introTemplate": "{monthName} {dayOrdinal}: {celebrityNames}.",
        "daysAliveTemplate": "As of {asOfDateLong}, {personFirstName} has been alive for {daysAliveFormatted} days!",
    }]}), encoding="utf-8")
    override_path = tmp_path / "overrides.json"
    override_path.write_text(json.dumps({"dates": overrides or {}}), encoding="utf-8")
    class Repository:
        @staticmethod
        def get_by_month_day(month, day):
            return people
    return FamousBirthdaysService(Repository, templates, override_path)


def test_format_helpers():
    assert ordinal(1) == "1st"
    assert ordinal(11) == "11th"
    assert ordinal(22) == "22nd"
    assert english_list(["A"]) == "A"
    assert english_list(["A", "B"]) == "A and B"
    assert english_list(["A", "B", "C"]) == "A, B, and C"


def test_month_day_ranking_diversity_and_days_alive(tmp_path):
    people = [
        person("Actor One", "1948-10-16", 10, "actor", "Q1"),
        person("Writer Two", "1900-10-16", 8, "writer", "Q2"),
        person("Scientist Three", "1950-10-16", 7, "scientist", "Q3"),
        person("Actor Four", "1960-10-16", 6, "actor", "Q4"),
        person("Artist Five", "1970-10-16", 5, "artist", "Q5"),
    ]
    result = service(tmp_path, people).get_famous_birthdays(date(1948, 10, 16), "Michael Borgmann", date(2013, 10, 16))
    assert result["headline"] == "CELEBRITIES SHARE OCT 16TH BIRTHDAY"
    assert len(result["people"]) == 5
    assert result["daysAlive"] == (date(2013, 10, 16) - date(1948, 10, 16)).days
    assert result["daysAliveFormatted"] == f"{result['daysAlive']:,}"
    assert result["asOfDateLong"] == "Wednesday, Oct. 16, 2013"
    assert "Michael has been alive" in result["daysAliveText"]


def test_override_missing_and_duplicate_ids_fill_automatically(tmp_path):
    people = [person("First", "1982-05-09", 5, "writer", "Q1"), person("Second", "1980-05-09", 4, "actor", "Q2")]
    result = service(tmp_path, people, {"05-09": {"featured": ["Q2", "Q2", "MISSING"]}}).get_famous_birthdays(date(1982, 5, 9), "Nishith", date(2026, 8, 24))
    assert [person["id"] for person in result["people"]] == ["Q2", "Q1"]


def test_february_29_and_future_safety(tmp_path):
    leap_person = person("Leap Person", "2000-02-29", 5, "writer", "Q29")
    result = service(tmp_path, [leap_person]).get_famous_birthdays(date(2024, 2, 29), "Nishith", date(2000, 1, 1))
    assert result["monthDay"] == "02-29"
    assert result["daysAlive"] is None
    assert result["daysAliveText"] == ""


def test_selection_prefers_occupied_people_and_preserves_fallback_order(tmp_path):
    people = [
        person("No Occupation", "1980-05-09", 10, None, "Q1"),
        person("Actor", "1981-05-09", 8, "actor", "Q2"),
        person("Historian", "1982-05-09", 7, "Historian", "Q3"),
        person("Blank", "1983-05-09", 6, "  ", "Q4"),
        person("Singer", "1984-05-09", 5, "singer", "Q5"),
    ]
    result = service(tmp_path, people).get_famous_birthdays(date(1982, 5, 9), limit=3)
    assert [value["name"] for value in result["people"]] == ["Actor", "Singer", "Historian"]


def test_selection_fills_from_missing_occupation_candidates(tmp_path):
    people = [
        person("Actor", "1981-05-09", 8, "actor", "Q1"),
        person("Writer", "1982-05-09", 7, "writer", "Q2"),
        person("Fallback One", "1983-05-09", 9, None, "Q3"),
        person("Fallback Two", "1984-05-09", 6, "", "Q4"),
    ]
    result = service(tmp_path, people).get_famous_birthdays(date(1982, 5, 9), limit=3)
    assert [value["name"] for value in result["people"]] == ["Actor", "Writer", "Fallback One"]


def test_selection_treats_placeholders_as_missing_and_keeps_non_priority_occupation(tmp_path):
    people = [
        person("Placeholder", "1980-05-09", 10, "Unknown", "Q1"),
        person("Historian", "1981-05-09", 5, "Historian", "Q2"),
        person("Whitespace", "1982-05-09", 9, "   ", "Q3"),
    ]
    result = service(tmp_path, people).get_famous_birthdays(date(1982, 5, 9), limit=2)
    assert [value["name"] for value in result["people"]] == ["Historian", "Placeholder"]
