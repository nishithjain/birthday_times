"""Tests for reusable famous-birthday text templates."""

import json
from datetime import date
from pathlib import Path

import pytest

from backend.models.person import FamousPerson
from backend.services.famous_birthdays_service import FamousBirthdaysService


PRODUCTION_TEMPLATES = Path("backend/data/famous_birthdays_templates.json")


def _service(tmp_path, payload):
    templates = tmp_path / "templates.json"
    templates.write_text(json.dumps(payload), encoding="utf-8")
    class Repository:
        @staticmethod
        def get_by_month_day(month, day):
            return [FamousPerson("Oscar Wilde", date(1854, month, day), occupation="writer", wikidata_id="Q1")]
    return FamousBirthdaysService(Repository, templates, tmp_path / "missing-overrides.json")


def test_production_file_has_ten_unique_templates():
    payload = json.loads(PRODUCTION_TEMPLATES.read_text(encoding="utf-8"))
    assert payload["defaultTemplateId"] == "classic_01"
    assert payload["selection"]["mode"] == "deterministic"
    assert [template["id"] for template in payload["templates"]] == [f"classic_{index:02d}" for index in range(1, 11)]


def test_every_production_template_renders_supported_placeholders(tmp_path):
    payload = json.loads(PRODUCTION_TEMPLATES.read_text(encoding="utf-8"))
    for template in payload["templates"]:
        service = _service(tmp_path, {**payload, "templates": [template], "defaultTemplateId": template["id"]})
        result = service.get_famous_birthdays(date(1948, 10, 16), "Michael Borgmann", date(2013, 10, 16))
        assert result["templateId"] == template["id"]
        for field in ("headline", "introText", "daysAliveText"):
            assert "{" not in result[field]
            assert "}" not in result[field]


def test_template_selection_is_stable_and_normalizes_name(tmp_path):
    payload = json.loads(PRODUCTION_TEMPLATES.read_text(encoding="utf-8"))
    service = _service(tmp_path, payload)
    first = service.get_famous_birthdays(date(1948, 10, 16), "Michael Borgmann", date(2013, 10, 16))["templateId"]
    repeated = [service.get_famous_birthdays(date(1948, 10, 16), "  MICHAEL   BORGMANN  ", date(2013, 10, 16))["templateId"] for _ in range(100)]
    assert all(template_id == first for template_id in repeated)


def test_invalid_placeholder_is_rejected(tmp_path):
    payload = {
        "defaultTemplateId": "classic_01",
        "templates": [{
            "id": "classic_01",
            "headlineTemplate": "{unknownField}",
            "introTemplate": "ok",
            "daysAliveTemplate": "ok",
        }],
    }
    with pytest.raises(ValueError, match="unsupported"):
        _service(tmp_path, payload).get_famous_birthdays(date(1982, 5, 9), "Nishith")
