"""Offline tests for deterministic major-city selection."""

from backend.importers.weather_locations import select_major_cities


def city(identifier, population, feature="PPL", latitude=1.0, longitude=1.0):
    return {
        "geoname_id": identifier, "city": f"City {identifier}", "ascii_name": f"City {identifier}",
        "country_code": "XX", "population": population, "feature_code": feature,
        "latitude": latitude, "longitude": longitude,
    }


def test_selects_exact_limit_deterministically_and_ranks():
    cities = [city(index, 1000 + index) for index in range(1005)]
    selected = select_major_cities(cities, limit=1000)
    assert len(selected) == 1000
    assert [item["major_city_rank"] for item in selected] == list(range(1, 1001))
    assert all(item["priority"] == 1 for item in selected)
    assert selected == select_major_cities(list(reversed(cities)), limit=1000)


def test_capital_is_preferred_and_invalid_coordinates_excluded():
    cities = [city(1, 1000000), city(2, 100, "PPLC"), city(3, 999999, latitude=999)]
    selected = select_major_cities(cities, limit=2)
    assert [item["geoname_id"] for item in selected] == [2, 1]
    assert 3 not in [item["geoname_id"] for item in selected]
