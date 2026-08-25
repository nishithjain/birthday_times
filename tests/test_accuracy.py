"""Tests for historical accuracy constants."""

from backend.services.accuracy import (
    EXACT_DATE,
    NEAR_DATE,
    YEAR,
    VALID_ACCURACY_TYPES,
    is_valid_accuracy_type,
)


class TestAccuracyConstants:
    """Test accuracy level constants and validation."""

    def test_accuracy_constants(self):
        assert EXACT_DATE == "exact_date"
        assert NEAR_DATE == "near_date"
        assert YEAR == "year"

    def test_valid_accuracy_types(self):
        assert VALID_ACCURACY_TYPES == {
            "exact_date",
            "near_date",
            "year",
        }

    def test_is_valid_accuracy_type(self):
        assert is_valid_accuracy_type(EXACT_DATE) is True
        assert is_valid_accuracy_type(NEAR_DATE) is True
        assert is_valid_accuracy_type(YEAR) is True
        assert is_valid_accuracy_type("personalized") is False
        assert is_valid_accuracy_type("invalid") is False
