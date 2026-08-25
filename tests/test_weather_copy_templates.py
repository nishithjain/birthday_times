import json
from pathlib import Path


EXPECTED = {
    "sunny", "partly_cloudy", "cloudy", "showers", "rain",
    "thunderstorm", "snow", "fog", "windy", "generic",
}


def test_weather_copy_has_three_monthly_climate_variants_per_condition():
    path = Path(__file__).parents[1] / "backend" / "data" / "weather_copy_templates.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    conditions = {key: value for key, value in payload.items() if key not in {"combinations", "fallbacks"}}
    assert set(conditions) == EXPECTED
    assert set(payload["combinations"]["sunny"]) == {
        "very_cold", "cold", "cool", "mild", "warm", "hot",
    }
    for variants in conditions.values():
        assert set(variants) == {"compact", "standard", "long"}
        assert all(text.strip() for text in variants.values())
        assert all(" on May " not in text and " on January " not in text for text in variants.values())
        assert all(not text.endswith("...") for text in variants.values())
    for variants in payload["combinations"]["sunny"].values():
        assert set(variants) == {"compact", "standard", "long"}
        assert all(text.strip() for text in variants.values())


def test_weather_template_displays_explicit_celsius_units():
    template = Path(__file__).parents[1] / "backend" / "web" / "templates" / "chronicles" / "sections" / "weather.html"
    text = template.read_text(encoding="utf-8")
    assert "minC|round(0)|int }}°C" in text
    assert "maxC|round(0)|int }}°C" in text
    assert "meanC|round(0)|int }}°C" in text
    assert "|int }}°</span>" not in text
