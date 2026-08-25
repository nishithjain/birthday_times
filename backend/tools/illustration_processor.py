"""Generic newspaper illustration (line-art / ink) print processor.

This transforms clean master illustrations into period-appropriate PRINTED INK
illustrations. It is intentionally different from the photograph processor:

- no photographic halftone dot conversion
- ink density / spread / roughness / grain instead of screen dots
- transparency is always preserved (the PNG stays transparent so the real
  newspaper paper texture shows through)
- original canvas dimensions are always preserved (no crop, no resize-to-fixed)

Never bake paper color, texture, stains, or a background into the output.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union

import numpy as np
from PIL import Image, ImageFilter

from backend.tools.image_processor import derive_processing_seed

PathLike = Union[str, Path]

VALID_ILLUSTRATION_COLOR_MODES = {
    "monochrome",
    "limited_color",
    "muted_color",
    "color",
    "full_color",
}

REQUIRED_ILLUSTRATION_KEYS = (
    "colorMode",
    "colorStrength",
    "inkStrength",
    "inkSpread",
    "roughness",
    "detailRetention",
    "grainStrength",
    "softness",
)


@dataclass(frozen=True)
class IllustrationPrintParams:
    """Normalized, validated illustration print parameters."""

    color_mode: str
    color_strength: float
    ink_strength: float
    ink_spread: float
    roughness: float
    detail_retention: float
    grain_strength: float
    softness: float


def _coerce_unit(value: Any, key: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"illustrationPrintStyle: {key} must be numeric.")
    return float(value)


def normalize_illustration_print_style(
    print_style: Dict[str, Any],
    style_id: str = "<unknown>",
) -> IllustrationPrintParams:
    """Validate and normalize an illustrationPrintStyle object."""
    if not isinstance(print_style, dict):
        raise ValueError(
            f"Invalid illustrationPrintStyle for {style_id}: expected an object."
        )

    missing = [key for key in REQUIRED_ILLUSTRATION_KEYS if key not in print_style]
    if missing:
        raise ValueError(
            f"Invalid illustrationPrintStyle for {style_id}: missing keys {missing}."
        )

    color_mode = print_style["colorMode"]
    if color_mode not in VALID_ILLUSTRATION_COLOR_MODES:
        raise ValueError(
            f"Invalid illustrationPrintStyle for {style_id}: "
            f"unsupported colorMode '{color_mode}'."
        )

    def unit(key: str) -> float:
        return float(np.clip(_coerce_unit(print_style[key], key), 0.0, 1.0))

    ink_strength = float(_coerce_unit(print_style["inkStrength"], "inkStrength"))
    ink_strength = float(np.clip(ink_strength, 0.0, 1.0))

    return IllustrationPrintParams(
        color_mode=color_mode,
        color_strength=unit("colorStrength"),
        ink_strength=ink_strength,
        ink_spread=unit("inkSpread"),
        roughness=unit("roughness"),
        detail_retention=float(np.clip(_coerce_unit(print_style["detailRetention"], "detailRetention"), 0.0, 1.0)),
        grain_strength=unit("grainStrength"),
        softness=unit("softness"),
    )


def _luminance(rgb: np.ndarray) -> np.ndarray:
    return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]


def _apply_color_reduction(rgb: np.ndarray, color_strength: float) -> np.ndarray:
    """Blend between grayscale (0.0) and original color (1.0)."""
    if color_strength >= 1.0:
        return rgb
    gray = _luminance(rgb)[..., None]
    return gray * (1.0 - color_strength) + rgb * color_strength


def _apply_ink_strength(rgb: np.ndarray, ink_strength: float) -> np.ndarray:
    """Gently adjust ink density/contrast while preserving internal shading.

    inkStrength == 1.0 is identity. Lower values slightly reduce contrast
    (weaker press); this never flattens artwork into a solid silhouette.
    """
    # Center a very mild contrast curve on mid-gray so shading is preserved.
    factor = 1.0 + 0.3 * (ink_strength - 0.9)
    factor = float(np.clip(factor, 0.7, 1.15))
    if abs(factor - 1.0) < 1e-6:
        return rgb
    return 0.5 + (rgb - 0.5) * factor


def _apply_detail_retention(
    rgb: np.ndarray,
    detail_retention: float,
    size: tuple,
) -> np.ndarray:
    """Simulate print-resolution detail loss via a small down/up resample.

    This is a resolution reduction, not a motion blur.
    """
    if detail_retention >= 0.999:
        return rgb
    width, height = size
    scale = 0.5 + 0.5 * detail_retention  # 0.78 -> 0.89 of each dimension
    small_w = max(1, int(round(width * scale)))
    small_h = max(1, int(round(height * scale)))
    if small_w >= width and small_h >= height:
        return rgb

    image = Image.fromarray((np.clip(rgb, 0.0, 1.0) * 255.0).astype(np.uint8), mode="RGB")
    reduced = image.resize((small_w, small_h), Image.Resampling.BILINEAR)
    restored = reduced.resize((width, height), Image.Resampling.BILINEAR)
    reduced_arr = np.asarray(restored, dtype=np.float32) / 255.0

    blend = 1.0 - detail_retention
    return rgb * (1.0 - blend) + reduced_arr * blend


def _apply_softness(rgb: np.ndarray, softness: float) -> np.ndarray:
    """Apply a very small Gaussian blur controlled by softness."""
    if softness <= 1e-6:
        return rgb
    radius = softness * 2.0  # conservative; 0.14 -> 0.28px
    image = Image.fromarray((np.clip(rgb, 0.0, 1.0) * 255.0).astype(np.uint8), mode="RGB")
    blurred = image.filter(ImageFilter.GaussianBlur(radius=radius))
    return np.asarray(blurred, dtype=np.float32) / 255.0


def _apply_ink_spread(rgb: np.ndarray, ink_spread: float) -> np.ndarray:
    """Thicken/expand dark ink using a MinFilter, blended by ink_spread."""
    if ink_spread <= 1e-6:
        return rgb
    image = Image.fromarray((np.clip(rgb, 0.0, 1.0) * 255.0).astype(np.uint8), mode="RGB")
    spread = image.filter(ImageFilter.MinFilter(3))
    spread_arr = np.asarray(spread, dtype=np.float32) / 255.0
    amount = float(np.clip(ink_spread, 0.0, 1.0))
    return rgb * (1.0 - amount) + spread_arr * amount


def _apply_roughness(
    rgb: np.ndarray,
    roughness: float,
    visible: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Add subtle edge/ink irregularity near artwork edges (not damage)."""
    if roughness <= 1e-6:
        return rgb
    luminance = _luminance(rgb)
    grad_y, grad_x = np.gradient(luminance)
    edge = np.sqrt(grad_x ** 2 + grad_y ** 2)
    max_edge = float(edge.max())
    if max_edge <= 1e-6:
        return rgb
    edge = edge / max_edge
    noise = rng.standard_normal(luminance.shape).astype(np.float32)
    modulation = (noise * edge * visible * (roughness * 0.20))[..., None]
    return rgb + modulation


def _apply_grain(
    rgb: np.ndarray,
    grain_strength: float,
    visible: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Add subtle deterministic print grain to visible artwork only."""
    if grain_strength <= 1e-6:
        return rgb
    noise = rng.standard_normal(rgb.shape[:2]).astype(np.float32)
    # Bias grain toward inked (darker) regions so paper-facing areas stay clean.
    ink_mask = np.clip(1.0 - _luminance(rgb), 0.0, 1.0)
    modulation = (noise * visible * (0.15 + 0.85 * ink_mask) * (grain_strength * 0.22))[..., None]
    return rgb + modulation


def process_newspaper_illustration(
    source_path: PathLike,
    output_path: PathLike,
    print_style: Dict[str, Any],
    seed: Optional[int] = None,
    style_id: str = "<unknown>",
) -> Dict[str, Any]:
    """Transform a clean master illustration into an era-specific printed variant.

    Preserves the source dimensions and transparency. Returns a small metadata
    dict describing the output. Never modifies the source file.
    """
    params = normalize_illustration_print_style(print_style, style_id)

    source = Path(source_path)
    output = Path(output_path)

    with Image.open(source) as opened:
        opened.load()
        rgba = opened.convert("RGBA")

    width, height = rgba.size
    arr = np.asarray(rgba, dtype=np.float32) / 255.0
    rgb = arr[..., :3].copy()
    alpha = arr[..., 3].copy()
    visible = alpha > 0.0

    # Neutralize fully transparent pixels to white so ink-spread / blur do not
    # pull dark halos from the invisible background. Alpha stays 0 there.
    rgb[~visible] = 1.0

    if seed is None:
        seed = 0
    rng = np.random.default_rng(seed)

    rgb = _apply_color_reduction(rgb, params.color_strength)
    rgb = _apply_ink_strength(rgb, params.ink_strength)
    rgb = _apply_detail_retention(rgb, params.detail_retention, (width, height))
    rgb = _apply_softness(rgb, params.softness)
    rgb = _apply_ink_spread(rgb, params.ink_spread)
    rgb = _apply_roughness(rgb, params.roughness, visible, rng)
    rgb = _apply_grain(rgb, params.grain_strength, visible, rng)

    rgb = np.clip(rgb, 0.0, 1.0)

    # Keep transparent pixels fully transparent; zero their RGB for clean output.
    rgb[~visible] = 0.0
    out = np.dstack([rgb, alpha])
    out_image = Image.fromarray((out * 255.0).astype(np.uint8), mode="RGBA")

    output.parent.mkdir(parents=True, exist_ok=True)
    out_image.save(output, format="PNG")

    return {
        "output_path": str(output),
        "size": (width, height),
        "color_mode": params.color_mode,
        "seed": seed,
    }


def derive_illustration_seed(illustration_id: str, era: str) -> int:
    """Deterministic seed derived from illustration id and era."""
    return derive_processing_seed("illustration", illustration_id, era)
