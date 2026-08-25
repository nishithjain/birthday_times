"""Tests for the dedicated president newspaper-photo processor."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from backend.services.newspaper_style_service import NewspaperStyleService
from backend.tools.president_photo_processor import (
    PhotoPrintParams,
    normalize_photo_print_style,
    process_president_photo,
)


@pytest.fixture
def style_service():
    return NewspaperStyleService()


def _print_style(style_service, era):
    return next(s for s in style_service.styles if s["id"] == era)["printStyle"]


def _make_source(path: Path, size=(600, 750), mode="RGB") -> None:
    """Write a colourful gradient portrait so effects are measurable."""
    width, height = size
    xs = np.linspace(0, 255, width, dtype=np.float32)
    ys = np.linspace(0, 255, height, dtype=np.float32)
    grid_x, grid_y = np.meshgrid(xs, ys)
    red = grid_x
    green = grid_y
    blue = np.full((height, width), 128.0, dtype=np.float32)
    rgb = np.dstack([red, green, blue]).astype(np.uint8)
    if mode == "RGBA":
        alpha = np.full((height, width), 255, dtype=np.uint8)
        alpha[: height // 4, : width // 4] = 0  # a transparent corner
        arr = np.dstack([rgb, alpha])
        Image.fromarray(arr, mode="RGBA").save(path)
    else:
        Image.fromarray(rgb, mode="RGB").save(path)


def _load(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0


class TestNormalizePhotoPrintStyle:
    def test_normalizes_real_style(self, style_service):
        params = normalize_photo_print_style(_print_style(style_service, "1950"), "1950")
        assert isinstance(params, PhotoPrintParams)
        assert params.color_mode == "black_and_white"
        assert params.color_strength == 0.0
        # Optional keys are derived, not required.
        assert 0.0 <= params.softness <= 0.35
        assert 0.0 <= params.ink_density <= 0.6

    def test_black_and_white_forces_zero_color(self, style_service):
        params = normalize_photo_print_style(_print_style(style_service, "1960"), "1960")
        assert params.color_strength == 0.0

    def test_missing_keys_raise(self):
        with pytest.raises(ValueError):
            normalize_photo_print_style({"colorMode": "full_color"}, "bad")

    def test_bad_color_mode_raises(self):
        style = {
            "colorMode": "sepia",
            "colorStrength": 0.5,
            "halftoneStrength": 0.2,
            "grainStrength": 0.1,
            "contrast": 1.0,
            "brightness": 1.0,
        }
        with pytest.raises(ValueError):
            normalize_photo_print_style(style, "bad")

    def test_optional_overrides_are_used(self):
        style = {
            "colorMode": "full_color",
            "colorStrength": 1.0,
            "halftoneStrength": 0.2,
            "grainStrength": 0.1,
            "contrast": 1.0,
            "brightness": 1.0,
            "softness": 0.25,
            "inkDensity": 0.4,
        }
        params = normalize_photo_print_style(style, "custom")
        assert params.softness == pytest.approx(0.25)
        assert params.ink_density == pytest.approx(0.4)


class TestProcessPresidentPhoto:
    def test_output_size_matches_slot(self, tmp_path, style_service):
        source = tmp_path / "src.png"
        _make_source(source)
        out = tmp_path / "1950.png"
        process_president_photo(source, out, _print_style(style_service, "1950"), seed=1)
        assert Image.open(out).size == (600, 750)

    def test_custom_output_size(self, tmp_path, style_service):
        source = tmp_path / "src.png"
        _make_source(source, size=(800, 1000))
        out = tmp_path / "1950.png"
        process_president_photo(
            source,
            out,
            _print_style(style_service, "1950"),
            seed=1,
            output_size=(300, 375),
        )
        assert Image.open(out).size == (300, 375)

    def test_preserves_transparency(self, tmp_path, style_service):
        source = tmp_path / "src.png"
        _make_source(source, mode="RGBA")
        out = tmp_path / "1950.png"
        process_president_photo(source, out, _print_style(style_service, "1950"), seed=1)
        result = Image.open(out)
        assert result.mode == "RGBA"
        alpha = np.asarray(result)[..., 3]
        assert alpha.min() == 0  # transparent corner survives
        assert alpha.max() == 255

    def test_rectangular_photo_stays_opaque(self, tmp_path, style_service):
        source = tmp_path / "src.png"
        _make_source(source, mode="RGB")
        out = tmp_path / "1950.png"
        process_president_photo(source, out, _print_style(style_service, "1950"), seed=1)
        assert Image.open(out).mode == "RGB"

    def test_1950_uses_warm_newsprint_tone(self, tmp_path, style_service):
        source = tmp_path / "src.png"
        _make_source(source)
        out = tmp_path / "1950.png"
        process_president_photo(source, out, _print_style(style_service, "1950"), seed=1)
        arr = _load(out)
        channel_spread = np.abs(arr[..., 0] - arr[..., 2]).mean()
        assert channel_spread > 0.02
        assert arr[..., 0].mean() > arr[..., 2].mean()

    def test_2015_keeps_color(self, tmp_path, style_service):
        source = tmp_path / "src.png"
        _make_source(source)
        out = tmp_path / "2015.png"
        process_president_photo(source, out, _print_style(style_service, "2015"), seed=1)
        arr = _load(out)
        channel_spread = np.abs(arr[..., 0] - arr[..., 2]).mean()
        assert channel_spread > 0.05  # colour is retained

    def test_1950_differs_more_from_original_than_2015(self, tmp_path, style_service):
        source = tmp_path / "src.png"
        _make_source(source)
        original = _load(source)

        out_1950 = tmp_path / "1950.png"
        out_2015 = tmp_path / "2015.png"
        process_president_photo(source, out_1950, _print_style(style_service, "1950"), seed=1)
        process_president_photo(source, out_2015, _print_style(style_service, "2015"), seed=1)

        diff_1950 = np.abs(_load(out_1950) - original).mean()
        diff_2015 = np.abs(_load(out_2015) - original).mean()
        assert diff_1950 > diff_2015

    def test_different_eras_produce_different_outputs(self, tmp_path, style_service):
        source = tmp_path / "src.png"
        _make_source(source)
        out_1950 = tmp_path / "1950.png"
        out_1980 = tmp_path / "1980.png"
        process_president_photo(source, out_1950, _print_style(style_service, "1950"), seed=1)
        process_president_photo(source, out_1980, _print_style(style_service, "1980"), seed=1)
        assert np.abs(_load(out_1950) - _load(out_1980)).mean() > 0.02

    def test_deterministic_with_same_seed(self, tmp_path, style_service):
        source = tmp_path / "src.png"
        _make_source(source)
        out_a = tmp_path / "a.png"
        out_b = tmp_path / "b.png"
        style = _print_style(style_service, "1960")
        process_president_photo(source, out_a, style, seed=7)
        process_president_photo(source, out_b, style, seed=7)
        assert out_a.read_bytes() == out_b.read_bytes()

    def test_missing_source_raises(self, tmp_path, style_service):
        with pytest.raises(FileNotFoundError):
            process_president_photo(
                tmp_path / "nope.png",
                tmp_path / "out.png",
                _print_style(style_service, "1950"),
                seed=1,
            )

    def test_does_not_modify_source(self, tmp_path, style_service):
        source = tmp_path / "src.png"
        _make_source(source)
        before = source.read_bytes()
        process_president_photo(
            source, tmp_path / "out.png", _print_style(style_service, "1950"), seed=1
        )
        assert source.read_bytes() == before
