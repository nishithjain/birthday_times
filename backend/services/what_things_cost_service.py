"""Static yearly What Things Cost data for the newspaper."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from backend.services.accuracy import YEAR

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "what_things_cost_1950_2026.json"
ITEM_LABELS = {
    "gasoline": "Petrol",
    "movieTicket": "Movie Ticket",
    "gold": "Gold",
    "popularCar": "Popular Car",
    "salary": "Salary",
}


def format_money(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    if amount.is_integer():
        return f"${int(amount):,}"
    return f"${amount:,.2f}"


def _car_detail(record: Dict[str, Any]) -> Optional[str]:
    manufacturer = (record.get("manufacturer") or "").strip()
    model = (record.get("model") or "").strip()
    if not model:
        return manufacturer or None
    if manufacturer and model.casefold().startswith(manufacturer.casefold() + " "):
        return model
    return f"{manufacturer} {model}".strip()


class WhatThingsCostService:
    def __init__(self, data_file: Optional[Path] = None):
        self.data_file = data_file or DATA_FILE
        self._years: Optional[Dict[int, Dict[str, Any]]] = None

    def _load(self) -> Dict[int, Dict[str, Any]]:
        if self._years is not None:
            return self._years
        try:
            payload = json.loads(self.data_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not load costs data: {exc}") from exc
        if payload.get("schemaVersion") != 1 or not isinstance(payload.get("years"), list):
            raise ValueError("Invalid What Things Cost dataset")
        years = {}
        for record in payload["years"]:
            year = record.get("year")
            if not isinstance(year, int) or year in years:
                raise ValueError("Cost records require unique integer years")
            years[year] = record
        self._years = years
        return years

    def get_costs_for_year(self, year: int) -> Dict[str, Any]:
        year = int(year)
        record = self._load().get(year)
        if record is None:
            return {"available": False, "year": year, "reason": "cost_data_unavailable"}
        items = []
        for key in ("gasoline", "movieTicket", "gold", "popularCar", "salary"):
            source = record.get(key) or {}
            if key == "popularCar":
                display_value = format_money(source.get("priceUsd"))
                detail = _car_detail(source)
            else:
                display_value = format_money(source.get("valueUsd"))
                detail = None
                if display_value and key == "gasoline":
                    display_value += " per gallon"
                elif display_value and key == "salary":
                    display_value += " per year"
                elif display_value and key == "gold":
                    display_value += " per ounce"
            items.append({
                "key": key,
                "label": ITEM_LABELS[key],
                "available": display_value is not None or detail is not None,
                "detail": detail,
                "displayValue": display_value,
            })
        has_any_data = any(item["available"] for item in items)
        return {
            "available": True,
            "hasAnyData": has_any_data,
            "year": year,
            "headline": f"WHAT THINGS COST IN {year}",
            "items": items,
            "accuracyType": YEAR,
        }


what_things_cost_service = WhatThingsCostService()
