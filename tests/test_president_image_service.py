"""Tests for the president image resolver (displayPath / usingVariant schema)."""

from datetime import date
from pathlib import Path

import pytest

from backend.services.president_service import PresidentService


@pytest.fixture
def service():
    return PresidentService()


def _write(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"png")


class TestNewSchemaFields:
    def test_prefers_variant_when_present(self, service, tmp_path):
        service.static_root = tmp_path
        _write(
            tmp_path / "images/people/presidents/originals/dwight_eisenhower.png"
        )
        _write(
            tmp_path
            / "images/people/presidents/variants/1950/dwight_eisenhower.png"
        )
        result = service.resolve_president_image("dwight_eisenhower", "1950")

        assert result["displayName"] == "Dwight D. Eisenhower"
        assert result["originalPath"] == (
            "images/people/presidents/originals/dwight_eisenhower.png"
        )
        assert result["variantPath"] == (
            "images/people/presidents/variants/1950/dwight_eisenhower.png"
        )
        assert result["displayPath"] == result["variantPath"]
        assert result["usingVariant"] is True

    def test_falls_back_to_original_when_variant_missing(self, service, tmp_path):
        service.static_root = tmp_path
        _write(
            tmp_path / "images/people/presidents/originals/dwight_eisenhower.png"
        )
        result = service.resolve_president_image("dwight_eisenhower", "1950")

        assert result["displayPath"] == result["originalPath"]
        assert result["variantPath"] is None
        assert result["usingVariant"] is False

    def test_display_path_none_when_both_missing(self, service, tmp_path):
        service.static_root = tmp_path
        result = service.resolve_president_image("dwight_eisenhower", "1950")

        assert result["displayPath"] is None
        assert result["usingVariant"] is False

    def test_legacy_fields_still_present(self, service, tmp_path):
        service.static_root = tmp_path
        _write(
            tmp_path / "images/people/presidents/originals/dwight_eisenhower.png"
        )
        result = service.resolve_president_image("dwight_eisenhower", "1950")

        assert result["originalImage"] == result["originalPath"]
        assert result["displayImage"] == result["displayPath"]
        assert result["variantImage"] == (
            "images/people/presidents/variants/1950/dwight_eisenhower.png"
        )

    def test_resolve_for_date_carries_new_fields(self, service, tmp_path):
        service.static_root = tmp_path
        _write(
            tmp_path / "images/people/presidents/originals/dwight_eisenhower.png"
        )
        president = service.resolve_president_for_date(date(1958, 5, 9), "1950")

        assert president["id"] == "dwight_eisenhower"
        assert president["displayPath"] == president["originalPath"]
        assert president["usingVariant"] is False
