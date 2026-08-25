"""Offline tests for the generated world-news loader."""

import json

from backend.services.world_news_service import WorldNewsService


def payload():
    return {
        "schemaVersion": 1,
        "year": 1982,
        "sectionTitle": "NEWS AROUND THE WORLD",
        "headlineTitle": "Making Headlines In 1982",
        "headlines": [{"displayText": f"Story {index}"} for index in range(8)],
    }


def test_loads_stored_order_and_applies_limit(tmp_path):
    (tmp_path / "1982.json").write_text(json.dumps(payload()), encoding="utf-8")
    service = WorldNewsService(tmp_path)
    result = service.get_world_news("1982", limit=5)
    assert result["year"] == 1982
    assert [item["displayText"] for item in result["headlines"]] == [f"Story {i}" for i in range(5)]


def test_explicit_unlimited_load_preserves_all_candidates(tmp_path):
    (tmp_path / "1982.json").write_text(json.dumps(payload()), encoding="utf-8")
    result = WorldNewsService(tmp_path).get_world_news(1982, limit=None)
    assert len(result["headlines"]) == 8
    assert len(result["candidates"]) == 8


def test_missing_malformed_and_empty_files_are_safe(tmp_path):
    service = WorldNewsService(tmp_path)
    assert service.get_world_news(1981) is None
    (tmp_path / "1982.json").write_text("not json", encoding="utf-8")
    assert service.get_world_news(1982) is None
    (tmp_path / "1983.json").write_text(json.dumps({"headlines": []}), encoding="utf-8")
    assert service.get_world_news(1983, limit=5)["headlines"] == []


def test_cache_returns_snapshot(tmp_path):
    (tmp_path / "1982.json").write_text(json.dumps(payload()), encoding="utf-8")
    service = WorldNewsService(tmp_path)
    first = service.get_world_news(1982)
    first["headlines"].clear()
    assert len(service.get_world_news(1982)["headlines"]) == 5
