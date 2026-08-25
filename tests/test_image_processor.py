"""Tests for generic newspaper image processing."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from backend.services.newspaper_style_service import NewspaperStyleService
from backend.tools.image_processor import (
    apply_brightness_contrast,
    apply_color_treatment,
    apply_grain,
    apply_halftone,
    cover_crop_to_aspect,
    effective_color_strength,
    normalize_portrait,
    process_newspaper_photo,
)


def _solid_image(path: Path, color: tuple[int, int, int], size: tuple[int, int]) -> None:
    Image.new("RGB", size, color=color).save(path)


def _gradient_image(path: Path, size: tuple[int, int]) -> None:
    width, height = size
    pixels = np.zeros((height, width, 3), dtype=np.uint8)
    for x in range(width):
        value = int(255 * x / max(width - 1, 1))
        pixels[:, x] = (value, value // 2, 255 - value)
    Image.fromarray(pixels, mode="RGB").save(path)


class TestImageProcessor:
  @pytest.fixture
  def style_service(self):
    return NewspaperStyleService()

  def test_output_size_and_aspect_ratio(self, tmp_path, style_service):
    source = tmp_path / "source.png"
    output = tmp_path / "output.png"
    _gradient_image(source, (900, 700))

    result = process_newspaper_photo(
      source,
      output,
      style_service.get_print_style_for_year(1955),
      output_size=(600, 750),
      seed=123,
    )

    with Image.open(output) as image:
      assert image.size == (600, 750)
    assert result["was_cropped"] is True

  def test_cover_crop_preserves_aspect_when_already_correct(self):
    image = Image.new("RGB", (400, 500), color=(120, 120, 120))
    cropped, was_cropped = cover_crop_to_aspect(image, 400 / 500)
    assert cropped.size == (400, 500)
    assert was_cropped is False

  def test_black_and_white_style_produces_grayscale_pixels(
    self, tmp_path, style_service
  ):
    source = tmp_path / "source.png"
    output = tmp_path / "output.png"
    _gradient_image(source, (500, 625))

    process_newspaper_photo(
      source,
      output,
      style_service.get_print_style_for_year(1955),
      seed=42,
    )

    array = np.asarray(Image.open(output).convert("RGB"), dtype=np.float32)
    channel_delta = np.abs(array[..., 0] - array[..., 1]).mean()
    assert channel_delta < 8.0

  def test_color_strength_zero_removes_color(self, tmp_path):
    source = tmp_path / "source.png"
    _gradient_image(source, (200, 250))
    array = np.asarray(Image.open(source).convert("RGB"), dtype=np.float32) / 255.0
    print_style = {
      "colorMode": "muted_color",
      "photoTreatment": "newspaper_color",
      "colorStrength": 0.0,
      "halftoneStrength": 0.0,
      "grainStrength": 0.0,
      "contrast": 1.0,
      "brightness": 1.0,
    }

    result = apply_color_treatment(array, print_style)
    assert np.abs(result[..., 0] - result[..., 1]).mean() < 1e-6
    assert np.abs(result[..., 1] - result[..., 2]).mean() < 1e-6

  def test_color_strength_one_preserves_color(self, tmp_path):
    source = tmp_path / "source.png"
    _gradient_image(source, (200, 250))
    array = np.asarray(Image.open(source).convert("RGB"), dtype=np.float32) / 255.0
    print_style = {
      "colorMode": "full_color",
      "photoTreatment": "modern_editorial",
      "colorStrength": 1.0,
      "halftoneStrength": 0.0,
      "grainStrength": 0.0,
      "contrast": 1.0,
      "brightness": 1.0,
    }

    result = apply_color_treatment(array, print_style)
    assert np.allclose(result, array)

  def test_brightness_is_applied(self):
    array = np.full((20, 20, 3), 0.5, dtype=np.float32)
    brighter = apply_brightness_contrast(array, brightness=1.2, contrast=1.0)
    darker = apply_brightness_contrast(array, brightness=0.8, contrast=1.0)
    assert brighter.mean() > array.mean()
    assert darker.mean() < array.mean()

  def test_contrast_is_applied(self):
    array = np.linspace(0.2, 0.8, 400, dtype=np.float32).reshape(20, 20, 1)
    array = np.repeat(array, 3, axis=2)
    high_contrast = apply_brightness_contrast(array, brightness=1.0, contrast=1.5)
    assert high_contrast.std() > array.std()

  def test_halftone_changes_image(self, style_service):
    array = np.linspace(0.1, 0.9, 6000, dtype=np.float32).reshape(75, 80, 1)
    array = np.repeat(array, 3, axis=2)
    print_style = style_service.get_print_style_for_year(1955)
    result = apply_halftone(array, print_style)
    assert not np.allclose(result, array)

  def test_grain_changes_image(self):
    array = np.full((40, 40, 3), 0.5, dtype=np.float32)
    result = apply_grain(array, grain_strength=0.5, seed=99)
    assert not np.allclose(result, array)

  def test_deterministic_processing(self, tmp_path, style_service):
    source = tmp_path / "source.png"
    output_a = tmp_path / "a.png"
    output_b = tmp_path / "b.png"
    _gradient_image(source, (480, 600))
    print_style = style_service.get_print_style_for_year(1975)

    process_newspaper_photo(source, output_a, print_style, seed=555)
    process_newspaper_photo(source, output_b, print_style, seed=555)

    assert output_a.read_bytes() == output_b.read_bytes()

  def test_different_era_settings_produce_different_outputs(
    self, tmp_path, style_service
  ):
    source = tmp_path / "source.png"
    output_1950 = tmp_path / "1950.png"
    output_1980 = tmp_path / "1980.png"
    _gradient_image(source, (480, 600))

    process_newspaper_photo(
      source,
      output_1950,
      style_service.get_print_style_for_year(1955),
      seed=1,
    )
    process_newspaper_photo(
      source,
      output_1980,
      style_service.get_print_style_for_year(1985),
      seed=1,
    )

    assert output_1950.read_bytes() != output_1980.read_bytes()

  def test_effective_color_strength_for_black_and_white(self, style_service):
    print_style = style_service.get_print_style_for_year(1955)
    assert effective_color_strength(print_style) == 0.0

  def test_normalize_portrait_output_size(self):
    image = Image.new("RGB", (800, 800), color=(100, 120, 140))
    normalized, was_cropped = normalize_portrait(image, output_size=(600, 750))
    assert normalized.size == (600, 750)
    assert was_cropped is True
