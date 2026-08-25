"""Tests for newspaper style selection."""

from datetime import date

import pytest

from backend.services.newspaper_style_service import (
    NewspaperStyleService,
    validate_print_style,
)


class TestNewspaperStyleService:
    """Test NewspaperStyleService year-to-style mapping."""

    @pytest.fixture
    def service(self):
        return NewspaperStyleService()

    @pytest.mark.parametrize(
        ("year", "expected_id", "expected_template", "expected_stylesheet", "expected_bg"),
        [
            (1955, "1950", "chronicles/chronicle_1950.html", "css/chronicles/chronicle_1950.css", "1950"),
            (1965, "1960", "chronicles/chronicle_1950.html", "css/chronicles/chronicle_1950.css", "1960"),
            (1975, "1970", "chronicles/chronicle_1970.html", "css/chronicles/chronicle_1970.css", "1970"),
            (1982, "1980", "chronicles/chronicle_1970.html", "css/chronicles/chronicle_1970.css", "1980"),
            (1992, "1990", "chronicles/chronicle_1990.html", "css/chronicles/chronicle_1990.css", "1990"),
            (1997, "1995", "chronicles/chronicle_1990.html", "css/chronicles/chronicle_1990.css", "1995"),
            (2003, "2000", "chronicles/chronicle_1990.html", "css/chronicles/chronicle_1990.css", "2000"),
            (2007, "2005", "chronicles/chronicle_2005.html", "css/chronicles/chronicle_2005.css", "2005"),
            (2012, "2010", "chronicles/chronicle_2005.html", "css/chronicles/chronicle_2005.css", "2010"),
            (2018, "2015", "chronicles/chronicle_2015.html", "css/chronicles/chronicle_2015.css", "2015"),
        ],
    )
    def test_get_style_for_year(
        self,
        service,
        year,
        expected_id,
        expected_template,
        expected_stylesheet,
        expected_bg,
    ):
        style = service.get_style_for_year(year)

        assert style["id"] == expected_id
        assert style["yearFrom"] <= year <= style["yearTo"]
        assert style["backgroundImage"] == f"images/newspaper/{expected_bg}.png"
        assert style["template"] == expected_template
        assert style["stylesheet"] == expected_stylesheet
        assert "mastheadFont" in style
        assert "headlineFont" in style
        assert "bodyFont" in style
        assert "theme" in style
        assert "printStyle" in style

    @pytest.mark.parametrize(
        ("year", "expected_id", "expected_color_mode", "expected_photo_treatment"),
        [
            (1955, "1950", "black_and_white", "coarse_halftone"),
            (1965, "1960", "black_and_white", "medium_halftone"),
            (1975, "1970", "black_and_white", "fine_halftone"),
            (1985, "1980", "limited_color", "muted_color_halftone"),
            (1992, "1990", "muted_color", "newspaper_color"),
            (1997, "1995", "color", "newspaper_color"),
            (2003, "2000", "full_color", "clean_newspaper_color"),
            (2007, "2005", "full_color", "clean_newspaper_color"),
            (2012, "2010", "full_color", "modern_newspaper_color"),
            (2018, "2015", "full_color", "modern_editorial"),
        ],
    )
    def test_get_print_style_for_year(
        self,
        service,
        year,
        expected_id,
        expected_color_mode,
        expected_photo_treatment,
    ):
        style = service.get_style_for_year(year)
        print_style = service.get_print_style_for_year(year)

        assert style["id"] == expected_id
        assert print_style["colorMode"] == expected_color_mode
        assert print_style["photoTreatment"] == expected_photo_treatment
        assert print_style is style["printStyle"]

    @pytest.mark.parametrize(
        ("year", "expected_id"),
        [
            (1959, "1950"),
            (1960, "1960"),
            (1979, "1970"),
            (1980, "1980"),
            (1989, "1980"),
            (1990, "1990"),
            (1994, "1990"),
            (1995, "1995"),
            (1999, "1995"),
            (2000, "2000"),
        ],
    )
    def test_style_boundary_years(self, service, year, expected_id):
        style = service.get_style_for_year(year)

        assert style["id"] == expected_id

    def test_may_9_1982_selects_1980_style(self, service):
        birth_date = date(1982, 5, 9)
        style = service.get_style_for_year(birth_date.year)

        assert style["id"] == "1980"
        assert style["backgroundImage"] == "images/newspaper/1980.png"
        assert style["template"] == "chronicles/chronicle_1970.html"
        assert style["stylesheet"] == "css/chronicles/chronicle_1970.css"
        assert style["printStyle"]["colorMode"] == "limited_color"

    def test_returns_complete_style_object(self, service):
        style = service.get_style_for_year(1982)

        assert style["id"] == "1980"
        assert style["backgroundImage"] == "images/newspaper/1980.png"
        assert style["template"] == "chronicles/chronicle_1970.html"
        assert style["stylesheet"] == "css/chronicles/chronicle_1970.css"
        assert isinstance(style["mastheadFont"], str)
        assert isinstance(style["headlineFont"], str)
        assert isinstance(style["bodyFont"], str)
        assert isinstance(style["theme"], str)
        assert isinstance(style["printStyle"], dict)

    def test_modern_styles_reduce_halftone_and_grain(self, service):
        style_1950 = service.get_print_style_for_year(1955)
        style_2015 = service.get_print_style_for_year(2018)

        assert style_1950["halftoneStrength"] > style_2015["halftoneStrength"]
        assert style_1950["grainStrength"] > style_2015["grainStrength"]

    def test_validate_print_style_rejects_invalid_color_mode(self):
        with pytest.raises(ValueError, match="unsupported colorMode"):
            validate_print_style(
                {
                    "colorMode": "sepia",
                    "photoTreatment": "coarse_halftone",
                    "colorStrength": 0.0,
                    "halftoneStrength": 0.5,
                    "grainStrength": 0.5,
                    "contrast": 1.0,
                    "brightness": 1.0,
                },
                "1950",
            )

    def test_validate_print_style_rejects_out_of_range_strength(self):
        with pytest.raises(ValueError, match="colorStrength must be between 0 and 1"):
            validate_print_style(
                {
                    "colorMode": "black_and_white",
                    "photoTreatment": "coarse_halftone",
                    "colorStrength": 1.5,
                    "halftoneStrength": 0.5,
                    "grainStrength": 0.5,
                    "contrast": 1.0,
                    "brightness": 1.0,
                },
                "1950",
            )
