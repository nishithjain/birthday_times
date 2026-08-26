from datetime import date

import pytest

from backend.config import config
from backend.database import db as database_module
from backend.database import initialize_database
from backend.importers.wikidata_around_this_time import (
    DAY_PRECISION,
    AroundThisTimeImporter,
    build_month_query,
    convert_results,
    merge_property_results,
    normalize_events,
    rejection_reason,
    sentence_case,
)
from backend.models.around_this_time_event import AroundThisTimeEvent
from backend.repositories.around_this_time_repository import AroundThisTimeRepository


def binding(value, value_type="literal"):
    return {"value": value, "type": value_type}


def row(qid, title, event_date, precision=DAY_PRECISION, description="A major treaty changed international relations.", type_label="treaty", sitelinks="100", article=True, type_id=None):
    result = {
        "event": binding(f"http://www.wikidata.org/entity/{qid}", "uri"),
        "eventLabel": binding(title),
        "eventDescription": binding(description) if description is not None else {},
        "eventDate": binding(event_date),
        "datePrecision": binding(str(precision)),
        "typeLabel": binding(type_label),
        "sitelinks": binding(sitelinks),
    }
    if type_id:
        result["type"] = binding(f"http://www.wikidata.org/entity/{type_id}", "uri")
    if article:
        result["article"] = binding(f"https://en.wikipedia.org/wiki/{qid}")
    return result


def data(*rows):
    return {"results": {"bindings": list(rows)}}


def test_precision_and_real_january_first_are_distinguished():
    records = convert_results(data(
        row("Q1", "Real New Year treaty", "2020-01-01T00:00:00Z", 11),
        row("Q2", "Year only", "1982-01-01T00:00:00Z", 9),
        row("Q3", "Month only", "1982-05-01T00:00:00Z", 10),
    ), "P585")

    assert [record["external_id"] for record in records] == ["Q1"]
    assert records[0]["event_date"] == "2020-01-01"


def test_month_query_is_bounded_to_one_calendar_month():
    query = build_month_query(2010, 5, "P585", limit=100)

    assert '"2010-05-01T00:00:00Z"' in query
    assert '"2010-06-01T00:00:00Z"' in query
    assert "LIMIT 100" in query


def test_quality_filters_and_categories_are_deterministic():
    raw = convert_results(data(
        row("Q1", "List of events in 2020", "1982-05-09T00:00:00Z"),
        row("Q2", "1980s", "1982-05-10T00:00:00Z"),
        row("Q3", "Routine film release", "1982-05-11T00:00:00Z", type_label="film", description="A film was released."),
        row("Q4", "Ordinary match", "1982-05-12T00:00:00Z", type_label="football match", description="A football match took place.", sitelinks="5"),
        row("Q5", "Constitutional treaty", "1982-05-13T00:00:00Z"),
    ), "P585")

    accepted, rejected = normalize_events(raw)

    assert [event.external_id for event in accepted] == ["Q5"]
    assert {item["filter_reason"] for item in rejected} == {
        "metadata or navigation entity", "generic year or decade title",
        "ordinary entertainment", "routine sports event",
    }
    assert accepted[0].category == "politics"


def test_rejection_reason_filters_generic_and_tagged_records():
    assert rejection_reason(
        {"title": "Natural disaster", "description": "A natural disaster.", "sitelink_count": 100},
        "other",
    ) == "generic or tagged title"


def test_rejection_reason_filters_calendar_vague_and_short_records():
    assert rejection_reason({"title": "Monday in 2020", "description": "A meaningful description here.", "sitelink_count": 100}, "politics") == "generic calendar title"
    assert rejection_reason({"title": "Workshop", "description": "A meaningful description here.", "sitelink_count": 100}, "culture") == "weak description"
    assert rejection_reason({"title": "Useful event", "description": "Only a few words.", "sitelink_count": 100}, "politics") == "description too short"


def test_rejection_reason_filters_geographic_locations_and_p31_types():
    assert rejection_reason(
        {"title": "Linnaleirinaukio", "description": "Square in Helsinki, Finland", "sitelink_count": 100},
        "other",
    ) == "geographic location or structure"
    assert rejection_reason(
        {"title": "Historic place", "description": "A site with a long useful description.", "type_ids": ["Q174782"], "sitelink_count": 100},
        "other",
    ) == "geographic location or structure"


def test_convert_results_retains_p31_ids():
    records = convert_results(data(row("Q1", "Historic place", "1982-05-09T00:00:00Z", type_id="Q515")), "P585")
    assert records[0]["type_ids"] == ["Q515"]


def test_sentence_case_preserves_proper_nouns():
    assert sentence_case("nASA and McDonald launch Wikidata") == "NASA and McDonald launch Wikidata"
    assert rejection_reason(
        {"title": "Presentation at #vbib20", "description": "A presentation at #vbib20.", "sitelink_count": 100},
        "other",
    ) == "generic or tagged title"


def test_property_priority_and_same_entity_different_dates():
    p580 = convert_results(data(row("Q1", "Mission begins", "1982-05-09T00:00:00Z", type_label="space mission")), "P580")
    p585 = convert_results(data(row("Q1", "Mission begins", "1982-05-09T00:00:00Z", type_label="space mission")), "P585")
    p571 = convert_results(data(row("Q1", "Mission founded", "1982-05-10T00:00:00Z", type_label="space mission")), "P571")

    merged = merge_property_results((("P580", p580), ("P571", p571), ("P585", p585)))
    accepted, _ = normalize_events(merged)

    assert {(event.external_id, event.event_date.isoformat()) for event in accepted} == {
        ("Q1", "1982-05-09"), ("Q1", "1982-05-10")
    }
    assert next(event for event in accepted if event.event_date == date(1982, 5, 9)).date_source == "P585"
    assert next(event for event in accepted if event.event_date == date(1982, 5, 10)).date_source == "P571"


class FakeResponse:
    status_code = 200
    headers = {}

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        raise AssertionError("unexpected HTTP failure")


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.headers = {}
        self.queries = []

    def get(self, endpoint, params, timeout):
        self.queries.append((params, timeout))
        property_id = next(item for item in ("P585", "P580", "P571") if f"wdt:{item}" in params["query"])
        return FakeResponse(self.responses[property_id])


@pytest.fixture
def temporary_database(tmp_path, monkeypatch):
    path = tmp_path / "importer.db"
    monkeypatch.setattr(config, "database_path", path)
    monkeypatch.setattr(database_module, "DATABASE_PATH", path)
    initialize_database()
    return path


def mocked_responses():
    return {
        "P585": data(row("Q1", "Treaty signed", "1982-05-09T00:00:00Z")),
        "P580": data(row("Q2", "Space mission begins", "1982-05-16T00:00:00Z", type_label="space mission")),
        "P571": data(row("Q3", "Important institute founded", "1982-06-01T00:00:00Z", type_label="institution", sitelinks="100")),
    }


def test_dry_run_does_not_write_and_commit_is_idempotent(temporary_database, tmp_path):
    checkpoint = tmp_path / "state.json"
    importer = AroundThisTimeImporter(session=FakeSession(mocked_responses()), delay=0, retries=1, timeout=1, checkpoint_path=checkpoint)

    dry_summary = importer.run([1982], commit=False)
    assert dry_summary["accepted"] == 3
    assert AroundThisTimeRepository.count() == 0
    assert not checkpoint.exists()

    commit_summary = importer.run([1982], commit=True)
    assert commit_summary["years_completed"] == 1
    assert AroundThisTimeRepository.count() == 3
    assert checkpoint.exists()

    second_summary = importer.run([1982], commit=True)
    assert second_summary["years_attempted"] == 0
    assert AroundThisTimeRepository.count() == 3


def test_checkpoint_marks_only_successful_years(tmp_path, monkeypatch):
    importer = AroundThisTimeImporter(session=FakeSession(mocked_responses()), delay=0, retries=1, checkpoint_path=tmp_path / "state.json")
    successful = ([AroundThisTimeEvent(date(1950, 1, 1), "Valid event", "Useful historical context.", external_id="Q1")], [], {"raw_fetched": 1, "day_precision_valid": 1, "P585": 1, "P580": 0, "P571": 0})
    calls = []

    def fetch_year(year):
        calls.append(year)
        if year == 1951:
            raise RuntimeError("mock failure")
        return successful

    monkeypatch.setattr(importer, "fetch_year", fetch_year)
    monkeypatch.setattr(AroundThisTimeRepository, "save", lambda events: {"inserted": 1, "updated": 0, "skipped": 0})
    summary = importer.run([1950, 1951], commit=True)

    assert calls == [1950, 1951]
    assert summary["years_failed"] == [1951]
    assert importer.load_checkpoint() == {1950}
