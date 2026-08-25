from datetime import date

from backend.models.event import HistoricalEvent
from backend.services.around_this_time_service import AroundThisTimeService


class Repository:
    events = []

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


def make_event(day, title, importance=5, description="A factual event description.", date_type="exact_date", qid=None):
    return HistoricalEvent(date(1982, 5, day), title, description, "politics", wikidata_id=qid or title, importance_score=importance, date_property_type=date_type)


def service():
    return AroundThisTimeService(Repository, Illustrations)


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
    assert result["windowDays"] == 30
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
