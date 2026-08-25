"""Offline tests for era-specific NEWS OF ARRIVAL wording."""

from datetime import date

from backend.services.arrival_message_service import ArrivalMessageService
from backend.services.arrival_message_service import normalize_president_context_templates, president_context_safe_capacity


CALENDAR = {
    "day_of_week": "Sunday",
    "western_zodiac": "Taurus",
    "birthstone": "Emerald",
    "generation": "Millennials",
}


def test_supported_eras_use_era_templates(tmp_path):
    service = ArrivalMessageService()
    expected = {
        1950: "1950", 1968: "1960", 1976: "1970", 1982: "1980", 1992: "1990",
        1998: "1995", 2002: "2000", 2008: "2005", 2012: "2010", 2018: "2015",
    }
    for year, era in expected.items():
        result = service.get_arrival(date(year, 5, 9), "Nishith Jain M R", "India", CALENDAR, era)
        assert result["era"] == era
        assert result["templateId"].startswith(f"{era}_")
        assert "{" not in result["bodyText"]


def test_body_wording_differs_by_era():
    service = ArrivalMessageService()
    bodies = [
        service.get_arrival(date(1950, 5, 9), "Nishith Jain M R", "India", CALENDAR, "1950")["bodyText"],
        service.get_arrival(date(1982, 5, 9), "Nishith Jain M R", "India", CALENDAR, "1980")["bodyText"],
        service.get_arrival(date(2018, 5, 9), "Nishith Jain M R", "India", CALENDAR, "2015")["bodyText"],
    ]
    assert len(set(bodies)) == 3


def test_same_person_date_era_is_deterministic():
    service = ArrivalMessageService()
    results = [service.get_arrival(date(1982, 5, 9), "  NISHITH   JAIN M R ", "India", CALENDAR, "1980") for _ in range(100)]
    assert len({result["templateId"] for result in results}) == 1
    assert len({result["bodyText"] for result in results}) == 1


def test_fallback_is_reported_for_unknown_era():
    result = ArrivalMessageService().get_arrival(date(1982, 5, 9), "Nishith", "India", CALENDAR, "2080")
    assert result["fallbackUsed"] is True
    assert result["templateId"].startswith("1950_")


def test_selects_rendered_candidate_that_fits_article_space(tmp_path):
    data_file = tmp_path / "arrival.json"
    data_file.write_text(
        '{"templates": ['
        '{"id":"1960_long","era":"1960","headlineTemplate":"LONG {personNameUpper}",'
        '"bodyTemplate":"' + ("Very long body text. " * 70) + '",'
        '"presidentWishTemplate":"' + ("Very long wish text. " * 70) + '"},'
        '{"id":"1960_short","era":"1960","headlineTemplate":"SHORT {personNameUpper}",'
        '"bodyTemplate":"A concise arrival note for {personNameUpper}.",'
        '"presidentWishTemplate":"Washington welcomes {personNameUpper}."}],'
        '"schemaVersion":1}',
        encoding="utf-8",
    )
    result = ArrivalMessageService(data_file).get_arrival(
        date(1965, 5, 9), "Nishith", "India", CALENDAR, "1960", "President Johnson"
    )
    assert result["templateId"] == "1960_short"
    assert result["headline"] == "SHORT NISHITH"
    assert result["presidentWishText"] == "Washington welcomes NISHITH."
    assert result["bodyText"] == "A concise arrival note for NISHITH."


def test_president_context_candidates_come_from_wish_pool_in_random_order():
    result = ArrivalMessageService().get_arrival(
        date(1982, 5, 9),
        "Ava Lee",
        "India",
        CALENDAR,
        "1980",
        "Jimmy Carter",
    )
    context = result["presidentContext"]
    # One candidate per era's legacy presidentWishTemplate, plus one compact
    # era-independent fallback candidate, pooled together.
    assert len(context["candidates"]) == 11
    assert context["estimatedCapacity"] is None
    assert context["safeEstimatedCapacity"] is None
    # The server's estimated pick is always the first entry of the (randomized) list.
    assert context["estimatedSelectedId"] == context["candidates"][0]["id"]
    assert context["estimatedSelectedCharacterCount"] == context["candidates"][0]["characterCount"]
    for candidate in context["candidates"]:
        assert "Jimmy Carter" in candidate["text"]
        assert "ava lee" in candidate["text"].lower()


def test_president_context_pool_is_independent_of_era():
    service = ArrivalMessageService()
    by_era = {
        era: service.get_arrival(date(1982, 5, 9), "Ava Lee", "India", CALENDAR, era, "Jimmy Carter")["presidentContext"]
        for era in ("1950", "1980", "2015")
    }
    # Era must not filter which wish templates are available, only randomness may vary the pick.
    id_sets = {frozenset(candidate["id"] for candidate in context["candidates"]) for context in by_era.values()}
    assert len(id_sets) == 1


def test_president_context_counts_change_for_long_names():
    service = ArrivalMessageService()
    short = service.get_arrival(date(1978, 5, 9), "Ava Lee", "India", {**CALENDAR, "day_of_week": "Friday"}, "1970", "Jimmy Carter")["presidentContext"]["candidates"]
    long = service.get_arrival(date(1959, 9, 30), "Christopher Alexander Montgomery", "India", {**CALENDAR, "day_of_week": "Wednesday"}, "1950", "Dwight D. Eisenhower")["presidentContext"]["candidates"]
    # Candidate order is randomized per call, so compare aggregate length rather than positionally.
    assert sum(item["characterCount"] for item in long) > sum(item["characterCount"] for item in short)


def test_president_context_safe_capacity_uses_ninety_percent():
    assert president_context_safe_capacity(170) == 153
    assert president_context_safe_capacity(None) is None


def test_missing_president_wish_templates_still_get_compact_candidate(tmp_path):
    data_file = tmp_path / "arrival.json"
    data_file.write_text('{"templates": [{"id":"1980","era":"1980","headlineTemplate":"H","bodyTemplate":"B"}]}', encoding="utf-8")
    result = ArrivalMessageService(data_file).get_arrival(date(1982, 5, 9), "Ava Lee", "India", CALENDAR, "1980", "Jimmy Carter")
    # No era presidentWishTemplate exists, but the guaranteed compact candidate remains.
    assert [candidate["id"] for candidate in result["presidentContext"]["candidates"]] == ["president_wish_compact"]
    assert result["presidentContext"]["estimatedSelectedId"] == "president_wish_compact"


def test_missing_president_does_not_expand_empty_name_context():
    result = ArrivalMessageService().get_arrival(date(1982, 5, 9), "Ava Lee", "India", CALENDAR, "1980", None)
    assert result["presidentContext"]["candidates"] == []


def test_malformed_wish_template_placeholder_is_skipped():
    values = {"presidentName": "Jimmy Carter", "personNameUpper": "AVA LEE"}
    candidate = {"id": "bad", "template": "{presedentName} entered."}
    assert ArrivalMessageService._expand_president_context_candidate(candidate, values) is None


def test_context_normalization_accepts_global_pool_and_rejects_invalid_shapes():
    short = {"id": "short", "template": "{presidentName} served when {personName} arrived."}
    long = {"id": "long", "template": "{presidentName} served when {personName} arrived on {weekday}."}
    normalized, diagnostics = normalize_president_context_templates([long, short])
    assert {item["id"] for item in normalized} == {"short", "long"}
    assert diagnostics == []
    for invalid in (None, "invalid", [{"id": "missing-template"}]):
        normalized, diagnostics = normalize_president_context_templates(invalid)
        assert normalized == []
        assert diagnostics
    normalized, diagnostics = normalize_president_context_templates([])
    assert normalized == []
    assert diagnostics == []
    normalized, diagnostics = normalize_president_context_templates([short, {**short, "id": "short"}])
    assert [item["id"] for item in normalized] == ["short"]
    assert any("duplicate candidate id" in item for item in diagnostics)


def test_president_context_sourced_from_president_wish_template(tmp_path):
    data_file = tmp_path / "arrival.json"
    data_file.write_text(
        '{"templates": [{"id":"1980","era":"1980","headlineTemplate":"H","bodyTemplate":"B",'
        '"presidentWishTemplate":"{presidentName} welcomed {personNameUpper}."}]}',
        encoding="utf-8",
    )
    result = ArrivalMessageService(data_file).get_arrival(date(1982, 5, 9), "Ava Lee", "India", CALENDAR, "1980", "Jimmy Carter")
    assert result["presidentContext"]["available"] is True
    texts = {candidate["id"]: candidate["text"] for candidate in result["presidentContext"]["candidates"]}
    assert texts["president_wish_1980"] == "Jimmy Carter welcomed AVA LEE."
    assert texts["president_wish_compact"] == "Jimmy Carter was President when Ava Lee entered the world."
