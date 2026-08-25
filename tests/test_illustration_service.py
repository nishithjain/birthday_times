"""Tests for IllustrationService selection and validation."""

import json

import pytest
from PIL import Image

from backend.services.illustration_service import (
    IllustrationService,
    illustration_service,
    normalize_context,
    variant_path_for,
)


ANIMALS = [
    "Rat",
    "Ox",
    "Tiger",
    "Rabbit",
    "Dragon",
    "Snake",
    "Horse",
    "Goat",
    "Monkey",
    "Rooster",
    "Dog",
    "Pig",
]


class TestIllustrationCatalog:
    def test_all_current_assets_are_loaded(self):
        assert len(illustration_service.illustrations) == 42
        assert illustration_service.get_by_id("globe")["id"] == "globe"
        assert illustration_service.get_by_id("globe")["path"].endswith("world/globe.png")

    def test_unknown_id_returns_none(self):
        assert illustration_service.get_by_id("not-an-illustration") is None

    def test_unknown_category_returns_none(self):
        assert illustration_service.get_for_category("nope", 1955) is None


class TestYearAndPrioritySelection:
    @pytest.mark.parametrize(
        ("year", "expected_id"),
        [
            (1955, "jukebox"),
            (1965, "jukebox"),
            (1975, "cassette"),
            (1985, "boombox"),
        ],
    )
    def test_music_by_year(self, year, expected_id):
        result = illustration_service.get_for_category("music", year)
        assert result["id"] == expected_id

    def test_space_context_selects_rocket(self):
        result = illustration_service.get_for_context("space", 1968)
        assert result["id"] == "rocket"

    def test_digital_music_selects_mp3_player(self):
        result = illustration_service.get_for_context("digital_music", 2005)
        assert result["id"] == "mp3-player"

    def test_2018_technology_selects_smartphone(self):
        result = illustration_service.get_for_category("technology", 2018)
        assert result["id"] == "smartphone"

    def test_1955_world_selects_globe(self):
        result = illustration_service.get_for_category("world", 1955)
        assert result["id"] == "globe"

    def test_1955_congress_selects_capitol(self):
        result = illustration_service.get_for_context("congress", 1955)
        assert result["id"] == "capitol"

    def test_2018_masthead_is_none(self):
        assert illustration_service.get_for_category("masthead", 2018) is None

    def test_1955_masthead_is_eagle(self):
        result = illustration_service.get_for_category("masthead", 1955)
        assert result["id"] == "eagle"


class TestContextNormalization:
    @pytest.mark.parametrize("context", ["world news", "world_news", "WORLD-NEWS"])
    def test_world_news_variants(self, context):
        assert normalize_context(context) == "world_news"
        result = illustration_service.get_for_context(context, 1955)
        assert result["id"] == "globe"

    @pytest.mark.parametrize("context", ["Digital Music", "digital_music", "digital-music"])
    def test_digital_music_variants(self, context):
        result = illustration_service.get_for_context(context, 2005)
        assert result["id"] == "mp3-player"


class TestZodiacLookup:
    @pytest.mark.parametrize("animal", ANIMALS)
    def test_all_animals(self, animal):
        result = illustration_service.get_zodiac_animal(animal)
        assert result["id"] == animal.lower()
        assert result["path"].endswith(f"zodiac/{animal.lower()}.png")

    def test_case_insensitive(self):
        assert illustration_service.get_zodiac_animal("TIGER")["id"] == "tiger"
        assert illustration_service.get_zodiac_animal("tiger")["id"] == "tiger"

    def test_unknown_does_not_crash(self):
        result = illustration_service.get_zodiac_animal("Lizard")
        assert result is None or result["id"] == "chinese-zodiac"


class TestVariantPathDerivation:
    def test_derives_variant_path(self):
        assert (
            variant_path_for(
                "images/illustrations/originals/music/jukebox.png", "1950"
            )
            == "images/illustrations/variants/1950/music/jukebox.png"
        )

    def test_non_originals_path_returns_none(self):
        assert variant_path_for("images/newspaper/1950.png", "1950") is None


def _catalog_with_globe():
    return {
        "schemaVersion": 1,
        "illustrations": [
            {
                "id": "globe",
                "category": "world",
                "path": "images/illustrations/originals/world/globe.png",
                "yearFrom": 1950,
                "yearTo": None,
                "contexts": ["world"],
                "priority": 10,
            }
        ],
    }


def _write_transparent_png(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (12, 12), (10, 20, 30, 0)).save(path)


class TestDisplayPathFallback:
    def _service(self, tmp_path):
        data_file = tmp_path / "illustrations.json"
        data_file.write_text(json.dumps(_catalog_with_globe()), encoding="utf-8")
        original = tmp_path / "images/illustrations/originals/world/globe.png"
        _write_transparent_png(original)
        return IllustrationService(data_file=data_file, static_root=tmp_path), tmp_path

    def test_falls_back_to_original_when_variant_missing(self, tmp_path):
        service, _ = self._service(tmp_path)
        slots = service.select_for_chronicle(year=1955, style_id="1950")
        world = slots["world"]
        assert world["displayPath"] == "images/illustrations/originals/world/globe.png"
        assert world["variantPath"] is None
        assert world["originalPath"] == "images/illustrations/originals/world/globe.png"

    def test_prefers_variant_when_present(self, tmp_path):
        service, root = self._service(tmp_path)
        variant = root / "images/illustrations/variants/1950/world/globe.png"
        _write_transparent_png(variant)
        slots = service.select_for_chronicle(year=1955, style_id="1950")
        world = slots["world"]
        assert world["displayPath"] == "images/illustrations/variants/1950/world/globe.png"
        assert world["variantPath"] == "images/illustrations/variants/1950/world/globe.png"

    def test_display_path_none_when_original_removed(self, tmp_path):
        service, root = self._service(tmp_path)
        (root / "images/illustrations/originals/world/globe.png").unlink()
        slots = service.select_for_chronicle(year=1955, style_id="1950")
        world = slots["world"]
        assert world["displayPath"] is None
        assert world["variantPath"] is None


class TestMissingFileIsSkipped:
    def test_missing_static_file_is_skipped(self, tmp_path):
        catalog = {
            "schemaVersion": 1,
            "illustrations": [
                {
                    "id": "present",
                    "category": "world",
                    "path": "images/illustrations/originals/world/globe.png",
                    "yearFrom": 1950,
                    "yearTo": None,
                    "contexts": ["world"],
                    "priority": 10,
                },
                {
                    "id": "missing",
                    "category": "world",
                    "path": "images/illustrations/originals/world/missing.png",
                    "yearFrom": 1950,
                    "yearTo": None,
                    "contexts": ["world"],
                    "priority": 20,
                },
            ],
        }
        data_file = tmp_path / "illustrations.json"
        data_file.write_text(json.dumps(catalog), encoding="utf-8")
        globe = tmp_path / "images/illustrations/originals/world/globe.png"
        globe.parent.mkdir(parents=True)
        Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(globe)

        service = IllustrationService(data_file=data_file, static_root=tmp_path)
        assert service.get_by_id("missing") is None
        assert service.get_by_id("present")["id"] == "present"
        assert service.missing_paths == [
            "images/illustrations/originals/world/missing.png"
        ]
