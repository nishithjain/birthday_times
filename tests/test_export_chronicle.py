"""Unit tests for the Chronicle browser export workflow."""

from datetime import date
from pathlib import Path

import pytest
from PIL import Image

from backend.tools.export_chronicle import (
    A4_HEIGHT_MM,
    A4_WIDTH_MM,
    CANONICAL_HEIGHT,
    CANONICAL_WIDTH,
    _validate_date,
    build_parser,
    _create_a4_png,
    export_url,
    fit_on_a4,
    output_paths,
    rendered_dimensions,
)
from backend.web.app import app


EXPORT_SOURCE = __import__(
    "backend.tools.export_chronicle", fromlist=["__file__"]
).__file__


def test_rendered_dimensions_follow_chromium_device_scale():
    assert rendered_dimensions(1) == (1000, 1596)
    assert rendered_dimensions(2) == (2000, 3192)
    assert rendered_dimensions(3) == (3000, 4788)


@pytest.mark.parametrize("scale", (0, 4))
def test_rendered_dimensions_reject_unsupported_scale(scale):
    with pytest.raises(ValueError, match="scale must be 1, 2, or 3"):
        rendered_dimensions(scale)


def test_a4_fit_at_zero_margin_preserves_aspect_ratio_and_centers():
    placement = fit_on_a4(0)

    assert placement.height_mm == pytest.approx(A4_HEIGHT_MM)
    assert placement.width_mm == pytest.approx(186.0902256)
    assert placement.x_mm == pytest.approx(11.9548872)
    assert placement.y_mm == pytest.approx(0)
    assert placement.width_mm / placement.height_mm == pytest.approx(
        CANONICAL_WIDTH / CANONICAL_HEIGHT
    )


def test_a4_fit_with_default_safety_margin_is_proportional_and_centered():
    placement = fit_on_a4(5)

    assert placement.height_mm == pytest.approx(287)
    assert placement.width_mm == pytest.approx(179.8245614)
    assert placement.x_mm == pytest.approx((A4_WIDTH_MM - placement.width_mm) / 2)
    assert placement.y_mm == pytest.approx(5)
    assert placement.width_mm / placement.height_mm == pytest.approx(
        CANONICAL_WIDTH / CANONICAL_HEIGHT
    )


@pytest.mark.parametrize("margin", (-1, 106))
def test_a4_fit_rejects_invalid_margins(margin):
    with pytest.raises(ValueError):
        fit_on_a4(margin)


def test_output_paths_are_deterministic_and_include_dimensions(tmp_path):
    paths = output_paths(date(1982, 8, 26), tmp_path, 3)

    assert paths["native_png"].name == "birthday_chronicle_1982-08-26_1000x1596.png"
    assert paths["scaled_png"].name == "birthday_chronicle_1982-08-26_3000x4788.png"
    assert paths["a4_png"].name == "birthday_chronicle_1982-08-26_A4_300dpi.png"
    assert paths["a4_pdf"].name == "birthday_chronicle_1982-08-26_A4.pdf"


def test_export_url_uses_the_dedicated_production_equivalent_route():
    url = export_url("http://127.0.0.1:5000/", date(1982, 8, 26), "Alex Smith", "India", "Mumbai")

    assert url.startswith("http://127.0.0.1:5000/chronicle/export?")
    assert "date=1982-08-26" in url
    assert "name=Alex+Smith" in url
    assert "city=Mumbai" in url


def test_cli_rejects_invalid_dates():
    with pytest.raises(SystemExit, match="2"):
        build_parser().parse_args(["--date", "1949-12-31"])

    with pytest.raises(Exception, match="YYYY-MM-DD"):
        _validate_date("26-08-1982")


def test_export_route_renders_the_existing_master_template():
    response = app.test_client().get("/chronicle/export?date=1982-08-26")

    assert response.status_code == 200
    assert b'<main class="chronicle-page"' in response.data
    assert b"chronicle_master.css" in response.data


def test_export_waits_for_the_chronicle_css_background_before_capture():
    source = open(EXPORT_SOURCE, encoding="utf-8").read()

    assert "getComputedStyle(root).backgroundImage" in source
    assert "backgroundReady" in source
    assert "image.naturalWidth > 0" in source


def test_a4_png_preserves_rgb_source_pixels(tmp_path):
    source = tmp_path / "chronicle.png"
    destination = tmp_path / "a4.png"
    Image.new("RGB", (CANONICAL_WIDTH, CANONICAL_HEIGHT), (188, 151, 89)).save(source)

    _create_a4_png(source, destination, fit_on_a4())

    with Image.open(destination) as image:
        assert image.mode == "RGB"
        assert image.getpixel((image.width // 2, image.height // 2))[0] != image.getpixel(
            (image.width // 2, image.height // 2)
        )[1]


@pytest.mark.parametrize("value", ("1949-12-31", "not-a-date"))
def test_export_route_rejects_invalid_dates(value):
    response = app.test_client().get(f"/chronicle/export?date={value}")

    assert response.status_code == 400
