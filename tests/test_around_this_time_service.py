from datetime import date

from backend.models.event import HistoricalEvent
from backend.repositories.around_this_time_repository import AroundThisTimeRepository
from backend.services.accuracy import EXACT_DATE, NEAR_DATE
from backend.services.around_this_time_service import AroundThisTimeService
from backend.services.historical_event_quality import (
    accuracy_for_event,
    classify_event_date_precision,
    is_usable_around_this_time_event,
)


class Repository:
    events = []

    @staticmethod
    def get_between_dates(start_date, end_date, limit=None, exclude_external_ids=None):
        events = [event for event in Repository.events if start_date <= event.event_date <= end_date]
        return events[:limit] if limit is not None else events

    @staticmethod
    def get_events_near_date(target_date, days_before, days_after, limit=None):
        return [event for event in Repository.events if abs((event.event_date - target_date).days) <= max(days_before, days_after)]


class Illustrations:
    @staticmethod
    def get_for_context(context, year=None):
        return {"id": "globe"}

    @staticmethod
    def resolve_by_id(illustration_id, style_id=None):
        return {"id": illustration_id, "displayPath": "images/illustrations/originals/world/globe.png"}


def make_event(day, title, importance=5, description="A political event occurred.", date_type="exact_date", qid=None):
    return HistoricalEvent(date(1982, 5, day), title, description, "politics", wikidata_id=qid or title, importance_score=importance, date_property_type=date_type)


def service():
    return AroundThisTimeService(Repository, Illustrations)


def test_default_service_uses_dedicated_repository():
    assert AroundThisTimeService().repository is AroundThisTimeRepository


def test_exact_date_and_importance_are_ranked():
    Repository.events = [make_event(9, "Minor Birthday Event", 2, qid="minor"), make_event(10, "Major Nearby Event", 10, qid="major")]
    result = service().get_around_this_time(date(1982, 5, 9))
    assert result["featuredEvent"]["id"] == "major"
    assert result["secondaryEvents"][0]["id"] == "minor"


def test_window_expands_until_enough_events():
    Repository.events = [
        make_event(25, "Wider Window Event One", qid="wide-1"),
        make_event(26, "Wider Window Event Two", qid="wide-2"),
        make_event(27, "Wider Window Event Three", qid="wide-3"),
    ]
    result = service().get_around_this_time(date(1982, 5, 9))
    assert result["windowDays"] == 180
    assert result["available"] is True


def test_year_only_events_are_excluded():
    Repository.events = [make_event(9, "Year Only", date_type="year", qid="year")]
    result = service().get_around_this_time(date(1982, 5, 9))
    assert result["available"] is False
    assert result["reason"] == "nearby_events_unavailable"


def test_world_news_ids_are_excluded():
    Repository.events = [make_event(9, "Duplicate", qid="duplicate"), make_event(10, "Alternative", qid="alternative")]
    result = service().get_around_this_time(date(1982, 5, 9), excluded_event_ids={"duplicate"})
    assert result["featuredEvent"]["id"] == "alternative"


def test_quality_rejects_generic_and_metadata_titles():
    for title in ("1982", "1980s", "List of events", "Category:Events", "Portal:History", "Timeline of events"):
        assert is_usable_around_this_time_event(make_event(9, title)) is False


def test_quality_rejects_weak_descriptions():
    assert is_usable_around_this_time_event(make_event(9, "A real event", description=None)) is False
    assert is_usable_around_this_time_event(make_event(9, "A real event", description="year")) is False
    assert is_usable_around_this_time_event(make_event(9, "A real event", description="A real event")) is False


def test_quality_rejects_generic_and_tagged_records():
    assert is_usable_around_this_time_event(make_event(9, "Natural disaster")) is False
    assert is_usable_around_this_time_event(
        make_event(9, "Presentation at #vbib20", description="A presentation at #vbib20.")
    ) is False


def test_quality_rejects_geographic_location_descriptions():
    assert is_usable_around_this_time_event(
        make_event(9, "Linnaleirinaukio", description="Square in Helsinki, Finland")
    ) is False


def test_quality_rejects_generic_display_text_and_static_descriptions():
    place = make_event(9, "Linnaleirinaukio", description="A notable historical location in Helsinki, Finland.")
    place.displayText = "City in Minnesota"
    assert is_usable_around_this_time_event(place) is False
    assert is_usable_around_this_time_event(
        make_event(9, "Notable development", description="A significant historical development in the region.")
    ) is False


def test_ordinary_entertainment_is_rejected():
    assert is_usable_around_this_time_event(make_event(9, "A television series", description="A television series premiered.")) is False


def test_sports_events_remain_eligible_for_significant_milestones():
    event = make_event(9, "World Cup championship", description="A major world cup championship final.")
    event.category = "sports"
    assert is_usable_around_this_time_event(event) is True


def test_date_provenance_controls_precision_and_accuracy():
    exact = make_event(9, "Confirmed event", date_type="point_in_time")
    start = make_event(9, "War begins", date_type="start_time")
    inception = make_event(9, "Institution founded", date_type="inception")
    assert classify_event_date_precision(exact) == "exact_day"
    assert classify_event_date_precision(start) == "day_level_milestone"
    assert classify_event_date_precision(inception) == "day_level_milestone"
    assert accuracy_for_event(start, date(1982, 5, 9)) == NEAR_DATE
    assert accuracy_for_event(inception, date(1982, 5, 9)) == NEAR_DATE


def test_p585_matching_date_is_exact_date():
    Repository.events = [make_event(9, "Confirmed event", date_type="point_in_time")]
    result = service().get_around_this_time(date(1982, 5, 9))
    assert result["featuredEvent"]["accuracyType"] == EXACT_DATE


def test_january_one_unknown_provenance_is_not_exact():
    event = HistoricalEvent(date(1982, 1, 1), "A political event", "A political event occurred.", "politics", wikidata_id="unknown")
    assert classify_event_date_precision(event) == "year_level"
    assert is_usable_around_this_time_event(event) is True


def test_confirmed_p585_january_one_can_be_exact():
    Repository.events = [
        HistoricalEvent(date(1982, 1, 1), "New year treaty", "A political event occurred.", "politics", wikidata_id="new-year", date_property_type="point_in_time")
    ]
    result = service().get_around_this_time(date(1982, 1, 1))
    assert result["featuredEvent"]["accuracyType"] == EXACT_DATE


def test_year_wide_fallback_recovers_event_outside_window():
    Repository.events = [
        HistoricalEvent(date(1982, 11, 15), "Distant political event", "A political event occurred.", "politics", wikidata_id="distant")
    ]
    result = service().get_around_this_time(date(1982, 5, 9))
    assert result["available"] is True
    assert result["featuredEvent"]["id"] == "distant"
    assert result["featuredEvent"]["selectionWindow"] == 180


def test_extended_window_fills_sparse_candidate_pool():
    Repository.events = [
        make_event(25, "Thirty day event", qid="near"),
        HistoricalEvent(date(1982, 6, 28), "Distant historic milestone", "A significant milestone happened in the region.", "politics", wikidata_id="extended"),
    ]

    result = service().get_around_this_time(date(1982, 5, 9), limit=2)

    assert result["available"] is True
    assert result["windowDays"] == 180
    assert {item["id"] for item in result["candidates"]} == {"near", "extended"}
    assert next(item for item in result["candidates"] if item["id"] == "extended")["selectionWindow"] == 60


def test_search_reaches_one_hundred_eighty_days_when_one_hundred_fifty_is_still_sparse():
    Repository.events = [
        HistoricalEvent(
            date(1982, 10, 1), "Nasa mission milestone", "A milestone was recorded during the mission.",
            "science", wikidata_id="one-eighty-day",
        )
    ]

    result = service().get_around_this_time(date(1982, 5, 9))

    assert result["available"] is True
    assert result["windowDays"] == 180
    assert result["candidates"][0]["selectionWindow"] == 150


def test_payload_uses_sentence_case_and_title_fallback_for_generic_description(monkeypatch):
    monkeypatch.setattr(
        "backend.services.around_this_time_service.is_usable_around_this_time_event",
        lambda event, allow_sparse=False: True,
    )
    Repository.events = [
        HistoricalEvent(
            date(1982, 5, 9), "nASA and McDonald announce launch", "Event", "politics", wikidata_id="formatted",
        )
    ]

    result = service().get_around_this_time(date(1982, 5, 9))
    payload = result["featuredEvent"]

    assert payload["title"] == "NASA and McDonald announce launch"
    assert payload["description"] == "Event"
    assert payload["displayText"] == "NASA and McDonald announce launch"


def test_sparse_quality_policy_keeps_descriptive_extended_event():
    event = make_event(9, "Major documentary release", description="A documentary premiered after years of production.")

    assert is_usable_around_this_time_event(event) is False
    assert is_usable_around_this_time_event(event, allow_sparse=True) is True


def test_year_level_event_is_not_a_near_date_fallback():
    Repository.events = [make_event(9, "Annual political event", date_type="year", qid="year-level")]
    result = service().get_around_this_time(date(1982, 5, 9))
    assert result["available"] is False


def test_same_year_boundary_is_enforced():
    Repository.events = [
        HistoricalEvent(date(1981, 12, 31), "Previous year event", "A political event occurred.", "politics", wikidata_id="previous"),
        HistoricalEvent(date(1982, 1, 1), "Current year event", "A political event occurred.", "politics", wikidata_id="current", date_property_type="point_in_time"),
    ]
    result = service().get_around_this_time(date(1982, 1, 1))
    assert [item["id"] for item in result["candidates"]] == ["current"]


def test_december_boundary_excludes_next_year():
    Repository.events = [
        HistoricalEvent(date(1983, 1, 1), "Next year event", "A political event occurred.", "politics", wikidata_id="next"),
        HistoricalEvent(date(1982, 12, 31), "Current year event", "A political event occurred.", "politics", wikidata_id="current", date_property_type="point_in_time"),
    ]
    result = service().get_around_this_time(date(1982, 12, 31))
    assert [item["id"] for item in result["candidates"]] == ["current"]


def test_missing_source_ids_use_normalized_title_deduplication():
    Repository.events = [
        HistoricalEvent(date(1982, 5, 9), "Historic Treaty", "A political treaty was signed.", "politics"),
        HistoricalEvent(date(1982, 5, 10), " historic  treaty ", "A political treaty was signed.", "politics"),
    ]
    result = service().get_around_this_time(date(1982, 5, 9))
    assert len(result["candidates"]) == 1


def test_default_pool_is_richer_than_display_count():
    Repository.events = [make_event(day, f"Political event {day}", qid=f"event-{day}") for day in range(9, 18)]
    result = service().get_around_this_time(date(1982, 5, 9))
    assert len(result["candidates"]) == 6


def test_default_pool_stays_at_six_when_a_description_is_long():
    Repository.events = [
        make_event(day, f"Political event {day}", description=("A political event occurred. " if day < 15 else "A political event occurred with a very long description that should keep the optional seventh item out of the compact card layout."), qid=f"event-{day}")
        for day in range(9, 18)
    ]

    result = service().get_around_this_time(date(1982, 5, 9))

    assert len(result["candidates"]) == 6


def test_candidates_sort_by_importance_then_display_length():
    Repository.events = [
        make_event(9, "Short title", importance=7, description="A brief historical event occurred."),
        make_event(10, "Longer title", importance=7, description="A much longer historical event description occurred here."),
        make_event(11, "Highest importance", importance=9, description="A major event occurred here."),
    ]

    result = service().get_around_this_time(date(1982, 5, 9), limit=3)

    assert [item["title"] for item in result["candidates"]] == [
        "Highest importance", "Longer title", "Short title",
    ]


def test_repeated_title_families_keep_highest_importance_event():
    Repository.events = [
        make_event(9, "Surrey Badminton Championships", importance=4, qid="surrey"),
        make_event(10, "West Hants Badminton Championships", importance=8, qid="west-hants"),
    ]

    result = service().get_around_this_time(date(1982, 5, 9), limit=3)

    assert [item["id"] for item in result["candidates"]] == ["west-hants"]


def test_limit_can_reduce_candidate_pool():
    Repository.events = [make_event(day, f"Political event {day}", qid=f"event-{day}") for day in range(9, 18)]
    result = service().get_around_this_time(date(1982, 5, 9), limit=4)
    assert len(result["candidates"]) == 5


def test_search_scans_all_configured_windows_before_ranking():
    class TrackingRepository(Repository):
        calls = []

        @staticmethod
        def get_events_near_date(target_date, days_before, days_after, limit=None):
            TrackingRepository.calls.append(days_before)
            return Repository.get_events_near_date(target_date, days_before, days_after, limit)

    TrackingRepository.events = [make_event(day, f"Political event {day}", qid=f"event-{day}") for day in range(9, 15)]
    AroundThisTimeService(TrackingRepository, Illustrations).get_around_this_time(date(1982, 5, 9))
    assert TrackingRepository.calls == [0, 30, 60, 90, 120, 150, 180]
