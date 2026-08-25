"""Dedicated newspaper-PHOTOGRAPH processor for president portraits.

This turns an original president photo into an era-appropriate *printed
newspaper photograph*. It is deliberately separate from the illustration
(line-art / ink) processor:

- photographs keep continuous tone; they are never reduced to flat ink
- the era look comes from tonal treatment + a gentle print screen + fine
  grain, NOT from hard posterization or an aggressive dot pattern
- dimensions are normalized to the president display slot (policy size) with a
  centered cover-crop so faces are never stretched
- transparency is preserved when the source is a cut-out PNG; a rectangular
  photo stays a rectangle. The paper background is never baked into the file.

The processor reads the photo-oriented ``printStyle`` object from
``newspaper_styles.json``. Optional ``softness`` / ``inkDensity`` keys are
supported but not required; when absent they are derived from the existing
values so no newspaper style data has to change.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from backend.tools.image_processor import (
    PHOTO_TREATMENT_CELL_SIZE,
    _luminance,
    _ordered_halftone_luminance,
    apply_grain,
    cover_crop_to_aspect,
    derive_processing_seed,
)

PathLike = Union[str, Path]

VALID_PHOTO_COLOR_MODES = {
    "black_and_white",
    "limited_color",
    "muted_color",
    "color",
    "full_color",
}

REQUIRED_PHOTO_KEYS = (
    "colorMode",
    "colorStrength",
    "halftoneStrength",
    "grainStrength",
    "contrast",
    "brightness",
)


@dataclass(frozen=True)
class PhotoPrintParams:
    """Normalized, validated newspaper-photo print parameters."""

    color_mode: str
    color_strength: float
    contrast: float
    brightness: float
    halftone_strength: float
    grain_strength: float
    softness: float
    ink_density: float
    photo_treatment: str
    photo_tone: Optional[Tuple[Tuple[int, int, int], Tuple[int, int, int]]]


def _coerce_number(value: Any, key: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"printStyle: {key} must be numeric.")
    return float(value)


def normalize_photo_print_style(
    print_style: Dict[str, Any],
    style_id: str = "<unknown>",
) -> PhotoPrintParams:
    """Validate and normalize a photo ``printStyle`` object.

    ``softness`` and ``inkDensity`` are optional; when missing they are derived
    from the mandatory values so that older eras read softer / inkier and newer
    eras stay clean, without requiring changes to newspaper_styles.json.
    """
    if not isinstance(print_style, dict):
        raise ValueError(f"Invalid printStyle for {style_id}: expected an object.")

    missing = [key for key in REQUIRED_PHOTO_KEYS if key not in print_style]
    if missing:
        raise ValueError(
            f"Invalid printStyle for {style_id}: missing keys {missing}."
        )

    color_mode = print_style["colorMode"]
    if color_mode not in VALID_PHOTO_COLOR_MODES:
        raise ValueError(
            f"Invalid printStyle for {style_id}: unsupported colorMode '{color_mode}'."
        )

    def unit(key: str) -> float:
        return float(np.clip(_coerce_number(print_style[key], key), 0.0, 1.0))

    color_strength = 0.0 if color_mode == "black_and_white" else unit("colorStrength")
    halftone_strength = unit("halftoneStrength")
    grain_strength = unit("grainStrength")
    contrast = float(np.clip(_coerce_number(print_style["contrast"], "contrast"), 0.5, 2.0))
    brightness = float(
        np.clip(_coerce_number(print_style["brightness"], "brightness"), 0.5, 1.5)
    )

    if "softness" in print_style:
        softness = unit("softness")
    else:
        # Older eras (heavier screen) read a touch softer.
        softness = float(np.clip(halftone_strength * 0.35, 0.0, 0.35))

    if "inkDensity" in print_style:
        ink_density = unit("inkDensity")
    else:
        # Stronger contrast + heavier screen implies deeper ink gain.
        ink_density = float(
            np.clip((contrast - 1.0) * 0.6 + halftone_strength * 0.2, 0.0, 0.6)
        )

    photo_treatment = print_style.get("photoTreatment", "fine_halftone")

    photo_tone = None
    tone = print_style.get("photoTone")
    if tone is not None:
        if not isinstance(tone, dict) or not all(isinstance(tone.get(key), str) for key in ("dark", "light")):
            raise ValueError(f"Invalid photoTone for {style_id}: expected dark/light hex colors.")

        def parse_hex(value: str) -> Tuple[int, int, int]:
            token = value.lstrip("#")
            if len(token) != 6:
                raise ValueError(f"Invalid photoTone color for {style_id}: {value}")
            try:
                return tuple(int(token[index:index + 2], 16) for index in (0, 2, 4))
            except ValueError as exc:
                raise ValueError(f"Invalid photoTone color for {style_id}: {value}") from exc

        photo_tone = (parse_hex(tone["dark"]), parse_hex(tone["light"]))

    return PhotoPrintParams(
        color_mode=color_mode,
        color_strength=color_strength,
        contrast=contrast,
        brightness=brightness,
        halftone_strength=halftone_strength,
        grain_strength=grain_strength,
        softness=softness,
        ink_density=ink_density,
        photo_treatment=photo_treatment,
        photo_tone=photo_tone,
    )


def _normalize_rgba(
    image: Image.Image,
    output_size: Tuple[int, int],
) -> Tuple[Image.Image, bool]:
    """Cover-crop to the slot aspect ratio then resize, preserving alpha."""
    target_width, target_height = output_size
    rgba = image.convert("RGBA")
    cropped, was_cropped = cover_crop_to_aspect(rgba, target_width / target_height)
    resized = cropped.resize(output_size, Image.Resampling.LANCZOS)
    return resized, was_cropped


def _apply_tone(rgb: np.ndarray, brightness: float, contrast: float) -> np.ndarray:
    """Gentle brightness then mid-pivot contrast (no posterization)."""
    out = np.clip(rgb * brightness, 0.0, 1.0)
    out = 0.5 + (out - 0.5) * contrast
    return np.clip(out, 0.0, 1.0)


def _apply_color_treatment(rgb: np.ndarray, color_strength: float) -> np.ndarray:
    """Blend between grayscale (0.0) and original color (1.0)."""
    if color_strength >= 1.0:
        return rgb
    gray = _luminance(rgb)[..., None]
    return gray * (1.0 - color_strength) + rgb * color_strength


def _apply_photo_tone(
    rgb: np.ndarray,
    tone: Optional[Tuple[Tuple[int, int, int], Tuple[int, int, int]]],
) -> np.ndarray:
    """Map grayscale ink into an era's paper-compatible dark/light tones."""
    if tone is None:
        return rgb
    gray = _luminance(rgb)
    dark, light = (np.asarray(color, dtype=np.float32) / 255.0 for color in tone)
    return dark + gray[..., None] * (light - dark)


def _apply_ink_density(rgb: np.ndarray, ink_density: float) -> np.ndarray:
    """Subtle ink gain: a mild gamma that deepens mid/shadow tones."""
    if ink_density <= 1e-6:
        return rgb
    gamma = 1.0 + ink_density * 0.3
    return np.clip(rgb, 0.0, 1.0) ** gamma


def _apply_softness(rgb: np.ndarray, softness: float) -> np.ndarray:
    """Small Gaussian blur to emulate soft newsprint reproduction."""
    if softness <= 1e-6:
        return rgb
    radius = softness * 1.6
    image = Image.fromarray((np.clip(rgb, 0.0, 1.0) * 255.0).astype(np.uint8), mode="RGB")
    blurred = image.filter(ImageFilter.GaussianBlur(radius=radius))
    return np.asarray(blurred, dtype=np.float32) / 255.0


def _apply_print_screen(
    rgb: np.ndarray,
    halftone_strength: float,
    treatment: str,
) -> np.ndarray:
    """Blend in a gentle halftone screen as print texture.

    The blend amount is capped well below 1.0 so the photograph keeps
    continuous tone instead of collapsing into harsh dots.
    """
    amount = min(halftone_strength * 0.55, 0.5)
    if amount <= 1e-6:
        return rgb
    cell_size = PHOTO_TREATMENT_CELL_SIZE.get(treatment, 5)
    luminance = _luminance(rgb)
    screened_luminance = _ordered_halftone_luminance(luminance, cell_size)
    scale = screened_luminance / np.clip(luminance, 1e-4, None)
    screened = np.clip(rgb * scale[..., None], 0.0, 1.0)
    return rgb * (1.0 - amount) + screened * amount


def process_president_photo(
    source_path: PathLike,
    output_path: PathLike,
    print_style: Dict[str, Any],
    seed: Optional[int] = None,
    output_size: Tuple[int, int] = (600, 750),
    style_id: str = "<unknown>",
) -> Dict[str, Any]:
    """Transform a president photo into an era-specific newspaper print variant.

    Normalizes to the display slot size (centered cover-crop, no face stretch),
    applies a continuous-tone newspaper-photo treatment, preserves transparency
    when present, and never bakes in a paper background. Returns metadata and
    never modifies the source file.
    """
    params = normalize_photo_print_style(print_style, style_id)

    source = Path(source_path)
    output = Path(output_path)
    if not source.is_file():
        raise FileNotFoundError(f"President original photo not found: {source}")

    with Image.open(source) as opened:
        opened.load()
        has_alpha = opened.mode in ("RGBA", "LA") or (
            opened.mode == "P" and "transparency" in opened.info
        )
        normalized, was_cropped = _normalize_rgba(opened, output_size)

    arr = np.asarray(normalized, dtype=np.float32) / 255.0
    rgb = arr[..., :3].copy()
    alpha = arr[..., 3].copy()

    rgb = _apply_tone(rgb, params.brightness, params.contrast)
    rgb = _apply_color_treatment(rgb, params.color_strength)
    rgb = _apply_photo_tone(rgb, params.photo_tone)
    rgb = _apply_ink_density(rgb, params.ink_density)
    rgb = _apply_softness(rgb, params.softness)
    rgb = _apply_print_screen(rgb, params.halftone_strength, params.photo_treatment)

    processing_seed = 0 if seed is None else seed
    rgb = apply_grain(rgb, params.grain_strength, processing_seed)
    rgb = np.clip(rgb, 0.0, 1.0)

    output.parent.mkdir(parents=True, exist_ok=True)
    if has_alpha:
        out = np.dstack([rgb, alpha])
        out_image = Image.fromarray((out * 255.0).astype(np.uint8), mode="RGBA")
    else:
        out_image = Image.fromarray((rgb * 255.0).astype(np.uint8), mode="RGB")
    out_image.save(output, format="PNG")

    return {
        "source_path": str(source),
        "output_path": str(output),
        "output_size": output_size,
        "was_cropped": was_cropped,
        "used_alpha": bool(has_alpha),
        "color_mode": params.color_mode,
        "seed": processing_seed,
    }


def derive_president_seed(president_id: str, era: str) -> int:
    """Deterministic seed derived from president id and era."""
    return derive_processing_seed("president", president_id, era)
