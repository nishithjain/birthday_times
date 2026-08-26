from datetime import date

import pytest

from backend.config import config
from backend.database import initialize_database
from backend.database import db as database_module
from backend.models.around_this_time_event import AroundThisTimeEvent
from backend.repositories.around_this_time_repository import AroundThisTimeRepository


@pytest.fixture
def repository_database(tmp_path, monkeypatch):
    database_path = tmp_path / "around-this-time.db"
    monkeypatch.setattr(config, "database_path", database_path)
    monkeypatch.setattr(database_module, "DATABASE_PATH", database_path)
    initialize_database()
    return AroundThisTimeRepository


def event(event_date, title, external_id, importance=5):
    return AroundThisTimeEvent(
        event_date=event_date,
        title=title,
        description="A significant event with useful context.",
        external_id=external_id,
        date_source="P585",
        date_precision=11,
        importance_score=importance,
    )


def test_near_date_query_is_deterministic_without_implicit_year_clamping(repository_database):
    repository_database.save([
        event(date(1982, 1, 1), "Boundary", "Q1", 5),
        event(date(1982, 1, 2), "Second", "Q2", 5),
        event(date(1982, 1, 2), "First", "Q3", 5),
        event(date(1981, 12, 31), "Previous year", "Q4", 9),
    ])

    results = repository_database.get_events_near_date(date(1982, 1, 1), 30, 30)

    assert [item.external_id for item in results] == ["Q4", "Q1", "Q2", "Q3"]


def test_range_query_is_inclusive_and_supports_same_id_on_different_dates(repository_database):
    repository_database.save([
        event(date(1982, 5, 1), "Outside", "Q1"),
        event(date(1982, 5, 5), "Inside one", "Q2"),
        event(date(1982, 5, 9), "Inside two", "Q123"),
        event(date(1982, 5, 10), "Same ID later", "Q123"),
        event(date(1982, 5, 15), "Inside three", "Q3"),
        event(date(1982, 5, 25), "Outside", "Q4"),
    ])

    results = repository_database.get_between_dates(date(1982, 5, 2), date(1982, 5, 16))

    assert [item.external_id for item in results] == ["Q2", "Q123", "Q123", "Q3"]


def test_exclusion_and_optional_source_fields_are_supported(repository_database):
    optional = event(date(1990, 1, 1), "Optional fields", "Q9")
    optional.category = None
    optional.date_source = None
    optional.source_url = None
    repository_database.save([optional])

    results = repository_database.get_between_dates(
        date(1990, 1, 1), date(1990, 1, 1), exclude_external_ids=["Q-no-match"]
    )

    assert len(results) == 1
    assert results[0].category == "historical_event"


def test_queries_support_exact_windows_exclusions_and_limit(repository_database):
    repository_database.save([
        event(date(2000, 5, 9), "Exact", "Q1"),
        event(date(2000, 5, 16), "Plus seven", "Q2"),
        event(date(2000, 5, 25), "Plus sixteen", "Q3"),
    ])

    exact = repository_database.get_by_date(date(2000, 5, 9))
    nearby = repository_database.get_events_near_date(
        date(2000, 5, 9), 7, 7, limit=1, excluded_ids={"Q1"}
    )

    assert [item.external_id for item in exact] == ["Q1"]
    assert [item.external_id for item in nearby] == ["Q2"]


def test_upsert_preserves_identity_and_merges_richer_values(repository_database):
    repository_database.save([event(date(2020, 1, 1), "Short", "Q1", 4)])
    richer = event(date(2020, 1, 1), "A richer title", "Q1", 8)
    richer.description = "A much longer description with additional historical context."
    result = repository_database.save([richer])

    assert result["inserted"] == 0
    assert repository_database.count() == 1
    stored = repository_database.get_by_date(date(2020, 1, 1))[0]
    assert stored.title == "A richer title"
    assert stored.importance_score == 8


def test_clear_deletes_all_dedicated_events(repository_database):
    repository_database.save([event(date(2020, 1, 1), "First", "Q1"), event(date(2020, 1, 2), "Second", "Q2")])

    assert repository_database.clear() == 2
    assert repository_database.count() == 0
