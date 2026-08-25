"""Newspaper style selection based on birth year."""

import json
from pathlib import Path
from typing import Any, Dict, List

# printStyle color modes are visual design presets for Birthday Chronicles.
# They represent the gradual adoption of color newspaper printing and
# improvements in reproduction quality. They must NOT be interpreted as a
# strict historical statement that all newspapers changed printing technology
# on January 1 of the style year.

VALID_COLOR_MODES = {
    "black_and_white",
    "limited_color",
    "muted_color",
    "color",
    "full_color",
}

VALID_PHOTO_TREATMENTS = {
    "coarse_halftone",
    "medium_halftone",
    "fine_halftone",
    "muted_color_halftone",
    "newspaper_color",
    "clean_newspaper_color",
    "modern_newspaper_color",
    "modern_editorial",
}

REQUIRED_PRINT_STYLE_KEYS = (
    "colorMode",
    "photoTreatment",
    "colorStrength",
    "halftoneStrength",
    "grainStrength",
    "contrast",
    "brightness",
)

NORMALIZED_STRENGTH_KEYS = (
    "colorStrength",
    "halftoneStrength",
    "grainStrength",
)


def validate_print_style(print_style: Dict[str, Any], style_id: str) -> None:
    """Validate a newspaper printStyle object from newspaper_styles.json."""
    if not isinstance(print_style, dict):
        raise ValueError(
            f"Invalid printStyle for style {style_id}: expected an object."
        )

    missing_keys = [
        key for key in REQUIRED_PRINT_STYLE_KEYS if key not in print_style
    ]
    if missing_keys:
        raise ValueError(
            f"Invalid printStyle for style {style_id}: "
            f"missing keys {missing_keys}."
        )

    color_mode = print_style["colorMode"]
    if color_mode not in VALID_COLOR_MODES:
        raise ValueError(
            f"Invalid printStyle for style {style_id}: "
            f"unsupported colorMode '{color_mode}'."
        )

    photo_treatment = print_style["photoTreatment"]
    if photo_treatment not in VALID_PHOTO_TREATMENTS:
        raise ValueError(
            f"Invalid printStyle for style {style_id}: "
            f"unsupported photoTreatment '{photo_treatment}'."
        )

    for key in NORMALIZED_STRENGTH_KEYS:
        value = print_style[key]
        if not isinstance(value, (int, float)):
            raise ValueError(
                f"Invalid printStyle for style {style_id}: "
                f"{key} must be numeric."
            )
        if not 0 <= value <= 1:
            raise ValueError(
                f"Invalid printStyle for style {style_id}: "
                f"{key} must be between 0 and 1."
            )

    contrast = print_style["contrast"]
    if not isinstance(contrast, (int, float)) or contrast <= 0:
        raise ValueError(
            f"Invalid printStyle for style {style_id}: contrast must be > 0."
        )

    brightness = print_style["brightness"]
    if not isinstance(brightness, (int, float)) or brightness <= 0:
        raise ValueError(
            f"Invalid printStyle for style {style_id}: brightness must be > 0."
        )


class NewspaperStyleService:
    """Load newspaper styles and select the matching style for a birth year."""

    def __init__(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        styles_file = project_root / "backend" / "data" / "newspaper_styles.json"

        with styles_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if "styles" not in data or not data["styles"]:
            raise ValueError(
                f"Invalid newspaper styles file: {styles_file}. "
                "Expected a non-empty 'styles' array."
            )

        self.styles: List[Dict[str, Any]] = data["styles"]
        for style in self.styles:
            if "printStyle" not in style:
                raise ValueError(
                    f"Invalid newspaper style {style.get('id', '<unknown>')}: "
                    "missing printStyle."
                )
            validate_print_style(style["printStyle"], style["id"])

    def get_style_for_year(self, year: int) -> Dict[str, Any]:
        """Return the complete style object for the given birth year."""
        for style in self.styles:
            if style["yearFrom"] <= year <= style["yearTo"]:
                return style

        return self.styles[-1]

    def get_print_style_for_year(self, year: int) -> Dict[str, Any]:
        """Return the printStyle object for the given birth year."""
        return self.get_style_for_year(year)["printStyle"]


newspaper_style_service = NewspaperStyleService()
