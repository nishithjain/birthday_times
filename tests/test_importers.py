from datetime import date

from backend.importers.wikidata_events import (
	DAY_PRECISION,
	classify_events,
	convert_results,
)


def binding(value, value_type="literal"):
	return {"value": value, "type": value_type}


def result_row(title, value, precision=11, property_id="P585", description="A major political event occurred."):
	return {
		"event": binding("http://www.wikidata.org/entity/Q1", "uri"),
		"eventLabel": binding(title),
		"eventDescription": binding(description) if description is not None else {},
		"eventDate": binding(value, "literal"),
		"datePrecision": binding(str(precision)),
		"countryLabel": binding("Exampleland"),
		"typeLabel": binding("political event"),
		"type": binding("http://www.wikidata.org/entity/Q2", "uri"),
		"article": binding("https://en.wikipedia.org/wiki/Example"),
		"sitelinks": binding("100"),
	}


def test_convert_results_preserves_wikidata_precision_and_rejects_non_day_values():
	data = {"results": {"bindings": [
		result_row("Exact event", "1982-05-09T00:00:00Z", DAY_PRECISION),
		result_row("Year event", "1982-01-01T00:00:00Z", 9),
	]}}
	events = convert_results(data, "P585")
	assert len(events) == 2
	assert events[0]["date_precision"] == DAY_PRECISION

	accepted, rejected = classify_events(events)
	assert len(accepted) == 1
	assert rejected[0]["filter_reason"] == "Date is not day-level precision"


def test_month_only_value_is_not_accepted_as_first_day():
	event = result_row("Month event", "1982-05-01T00:00:00Z", 10)
	accepted, rejected = classify_events(convert_results({"results": {"bindings": [event]}}, "P585"))
	assert accepted == []
	assert rejected[0]["filter_reason"] == "Date is not day-level precision"


def test_p580_and_p571_day_precision_are_preserved_as_milestones():
	for property_id in ("P580", "P571"):
		events = convert_results({"results": {"bindings": [result_row("Historical milestone", "1982-05-09T00:00:00Z", 11, property_id)]}}, property_id)
		accepted, _ = classify_events(events)
		assert accepted[0].date_property == property_id
