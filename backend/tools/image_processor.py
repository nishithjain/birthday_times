"""Generic newspaper photograph processing."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
from PIL import Image, ImageEnhance

PathLike = Union[str, Path]

PHOTO_TREATMENT_CELL_SIZE: Dict[str, int] = {
    "coarse_halftone": 10,
    "medium_halftone": 7,
    "fine_halftone": 5,
    "muted_color_halftone": 6,
    "newspaper_color": 4,
    "clean_newspaper_color": 3,
    "modern_newspaper_color": 2,
    "modern_editorial": 2,
}

BAYER_8X8 = np.array(
    [
        [0, 48, 12, 60, 3, 51, 15, 63],
        [32, 16, 44, 28, 35, 19, 47, 31],
        [8, 56, 4, 52, 11, 59, 7, 55],
        [40, 24, 36, 20, 43, 27, 39, 23],
        [2, 50, 14, 62, 1, 49, 13, 61],
        [34, 18, 46, 30, 33, 17, 45, 29],
        [10, 58, 6, 54, 9, 57, 5, 53],
        [42, 26, 38, 22, 41, 25, 37, 21],
    ],
    dtype=np.float32,
) / 64.0


def derive_processing_seed(*parts: str) -> int:
    """Return a deterministic seed derived from stable string parts."""
    key = ":".join(parts)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def cover_crop_to_aspect(image: Image.Image, target_aspect: float) -> Tuple[Image.Image, bool]:
    """Center-crop an image to the target width/height aspect ratio."""
    width, height = image.size
    current_aspect = width / height

    if abs(current_aspect - target_aspect) < 1e-6:
        return image, False

    if current_aspect > target_aspect:
        new_width = int(round(height * target_aspect))
        left = (width - new_width) // 2
        return image.crop((left, 0, left + new_width, height)), True

    new_height = int(round(width / target_aspect))
    top = (height - new_height) // 2
    return image.crop((0, top, width, top + new_height)), True


def normalize_portrait(
    image: Image.Image,
    output_size: Tuple[int, int] = (600, 750),
) -> Tuple[Image.Image, bool]:
    """Resize a portrait to the target size using centered cover crop."""
    target_width, target_height = output_size
    target_aspect = target_width / target_height
    cropped, was_cropped = cover_crop_to_aspect(image, target_aspect)
    resized = cropped.resize(output_size, Image.Resampling.LANCZOS)
    return resized, was_cropped


def _to_float_array(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0


def _to_image(array: np.ndarray) -> Image.Image:
    clipped = np.clip(array, 0.0, 1.0)
    return Image.fromarray((clipped * 255.0).astype(np.uint8), mode="RGB")


def _luminance(array: np.ndarray) -> np.ndarray:
    return (
        0.2126 * array[..., 0]
        + 0.7152 * array[..., 1]
        + 0.0722 * array[..., 2]
    )


def apply_brightness_contrast(
    array: np.ndarray,
    brightness: float,
    contrast: float,
) -> np.ndarray:
    """Apply brightness and contrast adjustments."""
    adjusted = np.clip(array * brightness, 0.0, 1.0)
    mean = adjusted.mean()
    return np.clip((adjusted - mean) * contrast + mean, 0.0, 1.0)


def effective_color_strength(print_style: Dict[str, Any]) -> float:
    """Return the effective color retention strength for a print style."""
    if print_style.get("colorMode") == "black_and_white":
        return 0.0
    return float(print_style.get("colorStrength", 0.0))


def apply_color_treatment(
    array: np.ndarray,
    print_style: Dict[str, Any],
) -> np.ndarray:
    """Blend between grayscale and original color according to printStyle."""
    strength = effective_color_strength(print_style)
    luminance = _luminance(array)[..., np.newaxis]
    grayscale = np.repeat(luminance, 3, axis=2)
    return grayscale * (1.0 - strength) + array * strength


def _ordered_halftone_luminance(luminance: np.ndarray, cell_size: int) -> np.ndarray:
    """Simulate newspaper dot-screen halftone on luminance."""
    height, width = luminance.shape
    cell_y = np.arange(height) // cell_size
    cell_x = np.arange(width) // cell_size
    cell_means = np.zeros((cell_y.max() + 1, cell_x.max() + 1), dtype=np.float32)

    for row_index in range(cell_means.shape[0]):
        for col_index in range(cell_means.shape[1]):
            block = luminance[
                row_index * cell_size : (row_index + 1) * cell_size,
                col_index * cell_size : (col_index + 1) * cell_size,
            ]
            if block.size:
                cell_means[row_index, col_index] = block.mean()

    mean_map = cell_means[cell_y[:, None], cell_x[None, :]]

    local_y = (np.arange(height) % cell_size).astype(np.float32) + 0.5
    local_x = (np.arange(width) % cell_size).astype(np.float32) + 0.5
    yy, xx = np.meshgrid(local_y, local_x, indexing="ij")
    center = cell_size / 2.0
    distance = np.sqrt((yy - center) ** 2 + (xx - center) ** 2)
    max_radius = cell_size * 0.48
    radius = max_radius * np.power(1.0 - mean_map, 0.85)
    dot_mask = (distance <= radius).astype(np.float32)

    halftoned = mean_map * (1.0 - dot_mask) + dot_mask * (mean_map * 0.25)

    bayer_y = (yy.astype(int) * 8 // max(cell_size, 1)) % 8
    bayer_x = (xx.astype(int) * 8 // max(cell_size, 1)) % 8
    threshold = BAYER_8X8[bayer_y, bayer_x]
    ordered = (mean_map > threshold).astype(np.float32) * mean_map + (
        1.0 - (mean_map > threshold).astype(np.float32)
    ) * (mean_map * 0.65)

    return np.clip((halftoned * 0.75) + (ordered * 0.25), 0.0, 1.0)


def apply_halftone(array: np.ndarray, print_style: Dict[str, Any]) -> np.ndarray:
    """Blend a halftone screen into the processed photograph."""
    strength = float(print_style.get("halftoneStrength", 0.0))
    if strength <= 0:
        return array

    treatment = print_style.get("photoTreatment", "fine_halftone")
    cell_size = PHOTO_TREATMENT_CELL_SIZE.get(treatment, 5)

    luminance = _luminance(array)
    halftoned_luminance = _ordered_halftone_luminance(luminance, cell_size)
    scale = halftoned_luminance / np.clip(luminance, 1e-4, None)
    halftoned = np.clip(array * scale[..., np.newaxis], 0.0, 1.0)
    return array * (1.0 - strength) + halftoned * strength


def apply_grain(
    array: np.ndarray,
    grain_strength: float,
    seed: int,
) -> np.ndarray:
    """Apply subtle deterministic monochrome grain."""
    if grain_strength <= 0:
        return array

    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, grain_strength * 0.035, array.shape[:2])
    luminance = _luminance(array)
    adjusted_luminance = np.clip(luminance + noise, 0.0, 1.0)
    scale = adjusted_luminance / np.clip(luminance, 1e-4, None)
    return np.clip(array * scale[..., np.newaxis], 0.0, 1.0)


def apply_print_degradation(
    array: np.ndarray,
    print_style: Dict[str, Any],
    seed: int,
) -> np.ndarray:
    """Apply very subtle ink-density variation without paper artifacts."""
    amount = (
        float(print_style.get("halftoneStrength", 0.0))
        + float(print_style.get("grainStrength", 0.0))
    ) * 0.02
    if amount <= 0:
        return array

    height, width = array.shape[:2]
    rng = np.random.default_rng(seed + 17)
    coarse = rng.normal(0.0, 1.0, (max(1, height // 12), max(1, width // 12)))
    coarse_image = Image.fromarray(coarse.astype(np.float32), mode="F")
    coarse_image = coarse_image.resize((width, height), Image.Resampling.BILINEAR)
    variation = np.asarray(coarse_image, dtype=np.float32)
    variation = (variation - variation.mean()) * amount

    luminance = _luminance(array)
    adjusted_luminance = np.clip(luminance + variation, 0.0, 1.0)
    scale = adjusted_luminance / np.clip(luminance, 1e-4, None)
    softened = np.clip(array * scale[..., np.newaxis], 0.0, 1.0)

    soften_amount = min(0.35, amount * 4.0)
    if soften_amount > 0:
        softened_image = _to_image(softened)
        blur = softened_image.resize(
            (max(1, width // 4), max(1, height // 4)),
            Image.Resampling.BILINEAR,
        ).resize((width, height), Image.Resampling.BILINEAR)
        blur_array = _to_float_array(blur)
        softened = softened * (1.0 - soften_amount) + blur_array * soften_amount

    return softened


def process_newspaper_photo(
    source_path: PathLike,
    output_path: PathLike,
    print_style: Dict[str, Any],
    output_size: Tuple[int, int] = (600, 750),
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Transform a source photograph into an era-specific newspaper variant."""
    source = Path(source_path)
    output = Path(output_path)
    image = Image.open(source).convert("RGB")
    normalized, was_cropped = normalize_portrait(image, output_size=output_size)

    working = _to_float_array(normalized)
    working = apply_brightness_contrast(
        working,
        float(print_style.get("brightness", 1.0)),
        float(print_style.get("contrast", 1.0)),
    )
    working = apply_color_treatment(working, print_style)
    working = apply_halftone(working, print_style)

    processing_seed = 0 if seed is None else seed
    working = apply_grain(
        working,
        float(print_style.get("grainStrength", 0.0)),
        processing_seed,
    )
    working = apply_print_degradation(working, print_style, processing_seed)

    result = _to_image(working)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.save(output, format="PNG")

    return {
        "source_path": str(source),
        "output_path": str(output),
        "output_size": output_size,
        "was_cropped": was_cropped,
        "seed": processing_seed,
    }
