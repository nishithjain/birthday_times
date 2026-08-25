"""Tests for the generic newspaper illustration (ink) processor."""

import numpy as np
import pytest
from PIL import Image

from backend.services.newspaper_style_service import NewspaperStyleService
from backend.tools.illustration_processor import (
    normalize_illustration_print_style,
    process_newspaper_illustration,
)


@pytest.fixture(scope="module")
def styles_by_id():
    service = NewspaperStyleService()
    return {style["id"]: style for style in service.styles}


def _ink_style(styles_by_id, era):
    return styles_by_id[era]["illustrationPrintStyle"]


def _colored_artwork(path, size=(80, 80)):
    """A transparent PNG with strongly colored artwork in the center."""
    width, height = size
    arr = np.zeros((height, width, 4), dtype=np.uint8)
    third = width // 3
    arr[:, :third] = (220, 20, 20, 255)          # red
    arr[:, third : 2 * third] = (20, 120, 220, 255)  # blue
    arr[:, 2 * third :] = (240, 200, 20, 255)    # yellow
    # transparent border
    arr[:8, :, 3] = 0
    arr[-8:, :, 3] = 0
    Image.fromarray(arr, mode="RGBA").save(path)
    return path


def _load_rgba(path):
    with Image.open(path) as image:
        image.load()
        return np.asarray(image.convert("RGBA"), dtype=np.float32) / 255.0


def _visible_saturation(rgb, visible):
    channel_max = rgb.max(axis=-1)
    channel_min = rgb.min(axis=-1)
    sat = channel_max - channel_min
    return float(sat[visible].mean())


class TestValidation:
    def test_missing_key_raises(self):
        with pytest.raises(ValueError):
            normalize_illustration_print_style({"colorMode": "monochrome"}, "bad")

    def test_invalid_color_mode_raises(self):
        style = {
            "colorMode": "neon",
            "colorStrength": 0.0,
            "inkStrength": 1.0,
            "inkSpread": 0.0,
            "roughness": 0.0,
            "detailRetention": 1.0,
            "grainStrength": 0.0,
            "softness": 0.0,
        }
        with pytest.raises(ValueError):
            normalize_illustration_print_style(style, "bad")


class TestDimensionsAndAlpha:
    @pytest.mark.parametrize("era", ["1950", "1970", "2015"])
    def test_dimensions_and_alpha_preserved(self, tmp_path, styles_by_id, era):
        source = _colored_artwork(tmp_path / "src.png", size=(90, 70))
        output = tmp_path / f"out_{era}.png"

        process_newspaper_illustration(
            source, output, _ink_style(styles_by_id, era), seed=1, style_id=era
        )

        original = _load_rgba(source)
        variant = _load_rgba(output)
        assert variant.shape == original.shape  # same dimensions

        original_alpha = original[..., 3]
        variant_alpha = variant[..., 3]
        transparent = original_alpha == 0.0
        # transparent stays transparent
        assert np.all(variant_alpha[transparent] == 0.0)
        # visible stays visible
        assert np.all(variant_alpha[original_alpha > 0.0] > 0.0)

    def test_no_opaque_background(self, tmp_path, styles_by_id):
        source = _colored_artwork(tmp_path / "src.png")
        output = tmp_path / "out.png"
        process_newspaper_illustration(
            source, output, _ink_style(styles_by_id, "1950"), seed=1, style_id="1950"
        )
        variant = _load_rgba(output)
        assert variant[..., 3].min() == 0.0  # some fully transparent pixels remain


class TestColorReduction:
    @pytest.mark.parametrize("era", ["1950", "1960", "1970"])
    def test_monochrome_eras_are_neutral(self, tmp_path, styles_by_id, era):
        source = _colored_artwork(tmp_path / "src.png")
        output = tmp_path / f"out_{era}.png"
        process_newspaper_illustration(
            source, output, _ink_style(styles_by_id, era), seed=3, style_id=era
        )
        variant = _load_rgba(output)
        visible = variant[..., 3] > 0.0
        rgb = variant[..., :3]
        saturation = _visible_saturation(rgb, visible)
        assert saturation < 0.02  # effectively monochrome

    def test_1980_low_saturation_but_present(self, tmp_path, styles_by_id):
        source = _colored_artwork(tmp_path / "src.png")
        out_1980 = tmp_path / "out_1980.png"
        out_2015 = tmp_path / "out_2015.png"
        process_newspaper_illustration(
            source, out_1980, _ink_style(styles_by_id, "1980"), seed=3, style_id="1980"
        )
        process_newspaper_illustration(
            source, out_2015, _ink_style(styles_by_id, "2015"), seed=3, style_id="2015"
        )
        v1980 = _load_rgba(out_1980)
        v2015 = _load_rgba(out_2015)
        vis = v1980[..., 3] > 0.0
        sat_1980 = _visible_saturation(v1980[..., :3], vis)
        sat_2015 = _visible_saturation(v2015[..., :3], v2015[..., 3] > 0.0)
        assert sat_1980 < sat_2015  # modern retains more color


class TestProgression:
    def _mean_diff_from_original(self, source, output):
        original = _load_rgba(source)
        variant = _load_rgba(output)
        visible = original[..., 3] > 0.0
        diff = np.abs(original[..., :3] - variant[..., :3])
        return float(diff[visible].mean())

    def test_1950_differs_more_than_2015(self, tmp_path, styles_by_id):
        source = _colored_artwork(tmp_path / "src.png")
        out_1950 = tmp_path / "out_1950.png"
        out_2015 = tmp_path / "out_2015.png"
        process_newspaper_illustration(
            source, out_1950, _ink_style(styles_by_id, "1950"), seed=5, style_id="1950"
        )
        process_newspaper_illustration(
            source, out_2015, _ink_style(styles_by_id, "2015"), seed=5, style_id="2015"
        )
        assert self._mean_diff_from_original(source, out_1950) > self._mean_diff_from_original(
            source, out_2015
        )

    def test_1950_and_1970_are_measurably_different(self, tmp_path, styles_by_id):
        source = _colored_artwork(tmp_path / "src.png")
        out_1950 = tmp_path / "out_1950.png"
        out_1970 = tmp_path / "out_1970.png"
        process_newspaper_illustration(
            source, out_1950, _ink_style(styles_by_id, "1950"), seed=7, style_id="1950"
        )
        process_newspaper_illustration(
            source, out_1970, _ink_style(styles_by_id, "1970"), seed=7, style_id="1970"
        )
        a = _load_rgba(out_1950)[..., :3]
        b = _load_rgba(out_1970)[..., :3]
        assert float(np.abs(a - b).mean()) > 0.005


class TestDeterminism:
    def test_same_seed_same_output(self, tmp_path, styles_by_id):
        source = _colored_artwork(tmp_path / "src.png")
        out_a = tmp_path / "a.png"
        out_b = tmp_path / "b.png"
        style = _ink_style(styles_by_id, "1950")
        process_newspaper_illustration(source, out_a, style, seed=42, style_id="1950")
        process_newspaper_illustration(source, out_b, style, seed=42, style_id="1950")
        assert out_a.read_bytes() == out_b.read_bytes()
