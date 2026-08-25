"""Tests for U.S. president lookup and image path resolution."""

from datetime import date
from pathlib import Path

import pytest

from backend.services.president_service import PresidentService


class TestPresidentService:
    """Test PresidentService date lookup and image paths."""

    @pytest.fixture
    def service(self):
        return PresidentService()

    @pytest.mark.parametrize(
        ("target_date", "expected_id", "expected_name"),
        [
            (date(1953, 1, 19), "harry_s_truman", "Harry S. Truman"),
            (date(1953, 1, 20), "dwight_eisenhower", "Dwight D. Eisenhower"),
            (date(1961, 1, 19), "dwight_eisenhower", "Dwight D. Eisenhower"),
            (date(1961, 1, 20), "john_f_kennedy", "John F. Kennedy"),
            (date(1963, 11, 21), "john_f_kennedy", "John F. Kennedy"),
            (date(1963, 11, 22), "lyndon_b_johnson", "Lyndon B. Johnson"),
            (date(1974, 8, 8), "richard_nixon", "Richard Nixon"),
            (date(1974, 8, 9), "gerald_ford", "Gerald Ford"),
            (date(1981, 1, 19), "jimmy_carter", "Jimmy Carter"),
            (date(1981, 1, 20), "ronald_reagan", "Ronald Reagan"),
            (date(2009, 1, 19), "george_w_bush", "George W. Bush"),
            (date(2009, 1, 20), "barack_obama", "Barack Obama"),
            (date(2017, 1, 19), "barack_obama", "Barack Obama"),
            (date(2017, 1, 20), "donald_trump", "Donald Trump"),
            (date(2021, 1, 19), "donald_trump", "Donald Trump"),
            (date(2021, 1, 20), "joe_biden", "Joe Biden"),
            (date(2025, 1, 19), "joe_biden", "Joe Biden"),
            (date(2025, 1, 20), "donald_trump", "Donald Trump"),
        ],
    )
    def test_get_president_for_date_transitions(
        self,
        service,
        target_date,
        expected_id,
        expected_name,
    ):
        president = service.get_president_for_date(target_date)

        assert president["id"] == expected_id
        assert president["name"] == expected_name

    def test_donald_trump_has_one_record_and_two_terms(self, service):
        trump_records = [
            president
            for president in service.presidents_by_id.values()
            if president["id"] == "donald_trump"
        ]
        trump_terms = [
            term for term in service.terms if term["presidentId"] == "donald_trump"
        ]

        assert len(trump_records) == 1
        assert trump_records[0]["presidentNumbers"] == [45, 47]
        assert len(trump_terms) == 2

    def test_get_variant_image_path(self, service):
        assert service.get_variant_image_path("dwight_eisenhower", "1950") == (
            "images/people/presidents/variants/1950/dwight_eisenhower.png"
        )
        assert service.get_variant_image_path("dwight_eisenhower", "1960") == (
            "images/people/presidents/variants/1960/dwight_eisenhower.png"
        )

    def test_resolve_president_image_falls_back_to_original(self, service, tmp_path):
        service.static_root = tmp_path
        original_path = tmp_path / "images/people/presidents/originals/dwight_eisenhower.png"
        original_path.parent.mkdir(parents=True, exist_ok=True)
        original_path.write_bytes(b"png")
        result = service.resolve_president_image("dwight_eisenhower", "1950")

        assert result["originalImage"] == (
            "images/people/presidents/originals/dwight_eisenhower.png"
        )
        assert result["variantImage"] == (
            "images/people/presidents/variants/1950/dwight_eisenhower.png"
        )
        assert result["displayImage"] == result["originalImage"]

    def test_resolve_president_image_uses_variant_when_present(self, service, tmp_path):
        service.static_root = tmp_path
        variant_path = Path("images/people/presidents/variants/1960/dwight_eisenhower.png")
        full_variant = tmp_path / variant_path
        full_variant.parent.mkdir(parents=True, exist_ok=True)
        full_variant.write_bytes(b"png")

        result = service.resolve_president_image("dwight_eisenhower", "1960")

        assert result["displayImage"] == str(variant_path).replace("\\", "/")

    def test_example_1958_05_09(self, service, tmp_path):
        service.static_root = tmp_path
        original_path = tmp_path / "images/people/presidents/originals/dwight_eisenhower.png"
        original_path.parent.mkdir(parents=True, exist_ok=True)
        original_path.write_bytes(b"png")
        president = service.resolve_president_for_date(date(1958, 5, 9), "1950")

        assert president["id"] == "dwight_eisenhower"
        assert president["name"] == "Dwight D. Eisenhower"
        assert president["variantImage"] == (
            "images/people/presidents/variants/1950/dwight_eisenhower.png"
        )
        assert president["displayImage"] == president["originalImage"]

    def test_example_1960_05_09(self, service, tmp_path):
        service.static_root = tmp_path
        original_path = tmp_path / "images/people/presidents/originals/dwight_eisenhower.png"
        original_path.parent.mkdir(parents=True, exist_ok=True)
        original_path.write_bytes(b"png")
        president = service.resolve_president_for_date(date(1960, 5, 9), "1960")

        assert president["id"] == "dwight_eisenhower"
        assert president["name"] == "Dwight D. Eisenhower"
        assert president["variantImage"] == (
            "images/people/presidents/variants/1960/dwight_eisenhower.png"
        )
        assert president["displayImage"] == president["originalImage"]

    def test_display_image_none_when_both_missing(self, service, tmp_path):
        service.static_root = tmp_path
        result = service.resolve_president_image("dwight_eisenhower", "1950")

        assert result["displayImage"] is None
