"""Offline tests for the supported city catalog."""

from backend.importers.weather_locations import parse_geonames_line, priority


def line(geoname_id="123", name="Bengaluru", population="14000000", feature="PPLA2"):
    fields = [geoname_id, name, name, "", "12.9716", "77.5946", "P", feature, "IN", "", "KA", "", "", "", population, "", "", "", ""]
    return "\t".join(fields)


def test_city_parser_and_priority():
    result = parse_geonames_line(line())
    assert result["location_key"] == "geonames_123"
    assert result["city"] == "Bengaluru"
    assert result["country_code"] == "IN"
    assert result["priority"] == 1
    assert priority(15000, "P") == 3


def test_small_non_capital_place_is_excluded():
    assert parse_geonames_line(line(population="14999", feature="PPL")) is None


def test_capital_feature_is_kept_below_population_threshold():
    result = parse_geonames_line(line(population="100", feature="PPLC"))
    assert result is not None
