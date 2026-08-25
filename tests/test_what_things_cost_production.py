"""Production data and Chronicle payload checks for What Things Cost."""

import json
from pathlib import Path
from datetime import date
from unittest.mock import patch

from backend.services.what_things_cost_service import WhatThingsCostService
from backend.services.chronicle_service import ChronicleService


DATA_FILE = Path("backend/data/what_things_cost_1950_2026.json")


def test_production_dataset_shape_and_year_index():
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    assert payload["schemaVersion"] == 1
    assert payload["yearFrom"] == 1950
    assert payload["yearTo"] == 2026
    records = payload["years"]
    assert len(records) == 77
    assert [record["year"] for record in records] == list(range(1950, 2027))
    for record in records:
        for key in ("gasoline", "movieTicket", "gold", "popularCar", "salary"):
            assert key in record


def test_1960_payload_preserves_existing_nulls():
    result = WhatThingsCostService().get_costs_for_year(1960)
    assert result["available"] is True
    assert result["hasAnyData"] is False
    assert result["year"] == 1960
    assert result["headline"] == "WHAT THINGS COST IN 1960"
    assert len(result["items"]) == 5
    assert all(item["displayValue"] is None for item in result["items"])


def test_chronicle_preserves_structured_cost_payload():
    with patch("backend.services.chronicle_service.EventRepository.get_by_date", return_value=[]), patch("backend.services.chronicle_service.PersonRepository.get_by_birthday", return_value=[]), patch("backend.services.chronicle_service.MovieRepository.get_by_year", return_value=[]):
        chronicle = ChronicleService.generate_chronicle(date(1960, 5, 9))
    assert chronicle["what_things_cost"]["available"] is True
    assert chronicle["what_things_cost"]["year"] == 1960
    assert len(chronicle["what_things_cost"]["items"]) == 5
    assert chronicle["accuracy"]["what_things_cost"] == "year"
