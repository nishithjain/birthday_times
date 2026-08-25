"""Offline tests for boundary-aware Chinese zodiac content."""

import json
from datetime import date
from pathlib import Path

import pytest

from backend.services.chinese_zodiac_service import ChineseZodiacError, ChineseZodiacService


class Illustrations:
    def resolve_by_id(self, illustration_id, style_id):
        return {"id": illustration_id, "displayPath": f"images/illustrations/variants/{style_id}/zodiac/{illustration_id[7:]}.png"}


def service():
    return ChineseZodiacService(Illustrations())


def test_boundary_before_on_and_after_chinese_new_year():
    result = service().get_chinese_zodiac(date(1982, 1, 24), "Nishith", "1980")
    assert result["animalId"] == "rooster"
    assert service().get_chinese_zodiac(date(1982, 1, 25), "Nishith", "1980")["animalId"] == "dog"
    assert service().get_chinese_zodiac(date(1982, 1, 26), "Nishith", "1980")["animalId"] == "dog"


def test_february_boundary_and_january_regression():
    assert service().get_chinese_zodiac(date(1980, 2, 15), "Nishith")["animalId"] == "goat"
    assert service().get_chinese_zodiac(date(1980, 2, 16), "Nishith")["animalId"] == "monkey"
    assert service().get_chinese_zodiac(date(1980, 2, 17), "Nishith")["animalId"] == "monkey"


def test_all_animals_have_profiles():
    payload = json.loads(Path("backend/data/chinese_zodiac.json").read_text(encoding="utf-8"))
    assert len(payload["animals"]) == 12
    for animal in payload["animals"]:
        assert animal["name"] and animal["traits"] and animal["illustrationId"].startswith("zodiac_")


def test_template_and_fortune_are_deterministic():
    first = service().get_chinese_zodiac(date(1982, 8, 26), "Nishith")
    for _ in range(100):
        result = service().get_chinese_zodiac(date(1982, 8, 26), "  NISHITH ")
        assert result["templateId"] == first["templateId"]
        assert result["fortuneMessage"] == first["fortuneMessage"]
    assert "{" not in first["headline"] + first["introText"] + first["fortuneText"]


def test_unknown_boundary_is_unavailable():
    result = service().get_chinese_zodiac(date(2100, 1, 1), "Future")
    assert result == {"available": False, "reason": "zodiac_boundary_unavailable"}
