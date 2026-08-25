"""Historical accuracy level constants for Chronicle sections."""

EXACT_DATE = "exact_date"
NEAR_DATE = "near_date"
YEAR = "year"

VALID_ACCURACY_TYPES = {
    EXACT_DATE,
    NEAR_DATE,
    YEAR,
}


def is_valid_accuracy_type(value: str) -> bool:
    """Return True if value is a supported historical accuracy type."""
    return value in VALID_ACCURACY_TYPES
