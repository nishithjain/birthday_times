"""Offline tests for the static What Things Cost service."""

import json
from datetime import date

from backend.services.what_things_cost_service import WhatThingsCostService


def dataset(years):
    return {
        "schemaVersion": 1,
        "title": "What Things Cost",
        "yearFrom": 1950,
        "yearTo": 2026,
        "years": years,
    }


def test_formatting_and_car_deduplication(tmp_path):
    path = tmp_path / "costs.json"
    path.write_text(json.dumps(dataset([{
        "year": 1982,
        "gasoline": {"valueUsd": 1.22},
        "movieTicket": {"valueUsd": 2.94},
        "gold": {"valueUsd": 447},
        "popularCar": {"manufacturer": "Ford", "model": "Ford Mustang", "priceUsd": 7500},
        "salary": {"valueUsd": 15000},
    }])), encoding="utf-8")
    result = WhatThingsCostService(path).get_costs_for_year(1982)
    assert result["headline"] == "WHAT THINGS COST IN 1982"
    assert result["hasAnyData"] is True
    values = {item["key"]: item for item in result["items"]}
    assert values["gasoline"]["displayValue"] == "$1.22 per gallon"
    assert values["movieTicket"]["displayValue"] == "$2.94"
    assert values["gold"]["displayValue"] == "$447 per ounce"
    assert values["popularCar"]["detail"] == "Ford Mustang"
    assert values["popularCar"]["displayValue"] == "$7,500"
    assert values["salary"]["displayValue"] == "$15,000 per year"


def test_partial_and_empty_values(tmp_path):
    path = tmp_path / "costs.json"
    path.write_text(json.dumps(dataset([{"year": 1960, "gasoline": {"valueUsd": 0.31}, "popularCar": {"model": "Test Car"}}])), encoding="utf-8")
    result = WhatThingsCostService(path).get_costs_for_year(1960)
    items = {item["key"]: item for item in result["items"]}
    assert result["hasAnyData"] is True
    assert items["gasoline"]["displayValue"] == "$0.31 per gallon"
    assert items["popularCar"]["detail"] == "Test Car"
    assert items["popularCar"]["displayValue"] is None
    assert items["gold"]["displayValue"] is None
    assert WhatThingsCostService(path).get_costs_for_year(1949)["reason"] == "cost_data_unavailable"


def test_all_null_year_has_no_data(tmp_path):
    path = tmp_path / "costs.json"
    path.write_text(json.dumps(dataset([{"year": 1960}])), encoding="utf-8")
    result = WhatThingsCostService(path).get_costs_for_year(1960)
    assert result["available"] is True
    assert result["hasAnyData"] is False


def test_car_model_without_price_counts_as_data(tmp_path):
    path = tmp_path / "costs.json"
    path.write_text(json.dumps(dataset([{"year": 1960, "popularCar": {"model": "Example Sedan", "priceUsd": None}}])), encoding="utf-8")
    result = WhatThingsCostService(path).get_costs_for_year(1960)
    assert result["hasAnyData"] is True
    car = next(item for item in result["items"] if item["key"] == "popularCar")
    assert car["available"] is True
    assert car["detail"] == "Example Sedan"


def test_production_dataset_has_expected_years():
    service = WhatThingsCostService()
    records = service._load()
    assert len(records) == 77
    assert set(records) == set(range(1950, 2027))
