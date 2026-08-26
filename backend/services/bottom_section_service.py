"""Database-backed data for the standalone newspaper bottom section."""

from pathlib import Path
from typing import Any, Dict, List

from backend.database import fetch_all


REQUIRED_INDICATORS = (
    ("Gold", "USD per troy ounce"),
    ("Crude Oil (WTI)", "USD per barrel"),
    ("Bread (White, Pan)", "USD per pound"),
)
FLORAL_STATIC_ROOT = Path(__file__).resolve().parents[1] / "web" / "static"


class BottomSectionService:
    """Load the annual costs and year-specific facts used by the bottom section."""

    @staticmethod
    def _format_value(value: Any, decimals: int) -> str:
        if value is None:
            return "-"
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "-"
        return f"$ {number:,.{decimals}f}"

    def get_costs(self, year: int) -> List[Dict[str, str]]:
        rows = fetch_all(
            """
            SELECT indicator, value, unit
            FROM economic_indicators
            WHERE substr(CAST(year AS TEXT), 1, 4) = ?
              AND country = 'United States'
              AND indicator IN (?, ?, ?)
            ORDER BY id
            """,
            (str(int(year)), *(indicator for indicator, _ in REQUIRED_INDICATORS)),
        )
        first_by_indicator = {}
        for row in rows:
            first_by_indicator.setdefault(row["indicator"], row)
        return [
            {
                "indicator": indicator,
                "value": self._format_value(
                    first_by_indicator[indicator]["value"]
                    if indicator in first_by_indicator
                    else None,
                    3 if indicator == "Bread (White, Pan)" else 2,
                ),
                "unit": unit,
            }
            for indicator, unit in REQUIRED_INDICATORS
        ]

    def get_facts(self, year: int) -> List[str]:
        rows = fetch_all(
            """
            SELECT fact
            FROM fun_facts
            WHERE start_year = ?
            ORDER BY id
            LIMIT 5
            """,
            (int(year),),
        )
        return [row["fact"] for row in rows]

    @staticmethod
    def get_era_artwork(year: int) -> str:
        """Return the available floral artwork for the newspaper era."""
        year = int(year)
        era = min(max((year // 10) * 10, 1950), 2020)
        base = "images/illustrations/originals/florals"
        era_path = f"{base}/{era}.png"
        if (FLORAL_STATIC_ROOT / era_path).is_file():
            return era_path
        return f"{base}/generic.png"

    def get_bottom_data(self, year: int) -> Dict[str, Any]:
        year = int(year)
        return {
            "year": year,
            "costs": self.get_costs(year),
            "facts": self.get_facts(year),
            "floralArtwork": self.get_era_artwork(year),
        }


bottom_section_service = BottomSectionService()
