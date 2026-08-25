"""Offline tests for yearly world-news generation."""

import json
from datetime import date
from unittest.mock import patch

from backend.models.event import HistoricalEvent
from backend.tools.generate_world_news import WorldNewsBuilder


def event(title, day, category, importance, qid):
    return HistoricalEvent(
        event_date=date(1982, 1, day),
        title=title,
        description=f"Description of {title}",
        category=category,
        country="Argentina, United Kingdom",
        wikidata_id=qid,
        source_url=f"https://www.wikidata.org/wiki/{qid}",
        importance_score=importance,
    )


class TestWorldNewsBuilder:
    def test_rank_dedupe_balance_and_candidate_limit(self, tmp_path):
        records = [
            event("Apollo 11 Moon Landing", 1, "science_space", 10, "Q1"),
            event("Apollo 11 Moon Landing", 2, "science_space", 9, "Q2"),
            event("Treaty Signed", 3, "politics", 8, "Q3"),
            event("Great Earthquake", 4, "disaster", 7, "Q4"),
            event("Cultural Festival", 5, "culture", 6, "Q5"),
            event("New Achievement", 6, "achievement", 5, "Q6"),
        ]
        builder = WorldNewsBuilder(tmp_path)
        with patch("backend.tools.generate_world_news.EventRepository.get_by_year", return_value=records):
            result = builder.generate_year(1982)
        payload = result["payload"]
        assert payload["displayLimit"] == 5
        assert len(payload["headlines"]) == 5
        assert payload["headlines"][0]["sourceTitle"] == "Apollo 11 Moon Landing"
        assert payload["duplicatesRemoved"] == 1
        assert payload["headlines"][0]["country"] == ["Argentina", "United Kingdom"]
        assert (tmp_path / "1982.json").exists()

    def test_dry_run_and_approved_protection_and_force(self, tmp_path):
        records = [event("A Significant Event", 1, "politics", 8, "Q1")]
        builder = WorldNewsBuilder(tmp_path)
        with patch("backend.tools.generate_world_news.EventRepository.get_by_year", return_value=records):
            result = builder.generate_year(1982, dry_run=True)
            assert result["status"] == "would write"
            assert not (tmp_path / "1982.json").exists()
            (tmp_path / "1982.json").write_text(json.dumps({"reviewStatus": "approved"}))
            skipped = builder.generate_year(1982)
            assert skipped["status"] == "skipped approved"
            forced = builder.generate_year(1982, force=True)
        assert forced["payload"]["insufficientData"] is True
        assert json.loads((tmp_path / "1982.json").read_text())["reviewStatus"] == "generated"

    def test_partial_year_is_calculated_from_today(self, tmp_path):
        class FixedDate(date):
            @classmethod
            def today(cls):
                return cls(2026, 8, 24)

        builder = WorldNewsBuilder(tmp_path)
        with patch("backend.tools.generate_world_news.date", FixedDate):
            payload = builder.build_payload(2026, [])
        assert payload["isPartialYear"] is True
        assert payload["throughDate"] == "2026-08-24"
        assert payload["insufficientData"] is True
