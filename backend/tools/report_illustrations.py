"""Read-only report for illustration master PNG files.

This module never writes, resizes, converts, or otherwise mutates image files.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from PIL import Image

SQUARE_RATIO_MIN = 0.95
SQUARE_RATIO_MAX = 1.05
NEAR_SQUARE_RATIO_MIN = 0.85
NEAR_SQUARE_RATIO_MAX = 1.15
STRONG_PORTRAIT_RATIO_MAX = 0.80
MASTHEAD_RATIO_MIN = 2.5
MASTHEAD_RATIO_MAX = 4.0
LOW_RESOLUTION_PX = 300
VERY_LARGE_PX = 4000
VERY_LARGE_BYTES = 5 * 1024 * 1024
BAKED_BACKGROUND_THRESHOLD = 0.65
BORDER_SAMPLE_DEPTH = 3
ZODIAC_SIZE_TOLERANCE = 0.50

STATIC_RELATIVE_PREFIX = "images/illustrations/originals"
DEFAULT_TEXT_NAME = "illustrations_report.txt"
DEFAULT_JSON_NAME = "illustrations_report.json"

OPAQUE_FLAG_CATEGORIES = {
    "masthead",
    "world",
    "government",
    "movies",
    "music",
    "sports",
    "technology",
    "science",
    "zodiac",
}

ZODIAC_ANIMALS = {
    "rat",
    "ox",
    "tiger",
    "rabbit",
    "dragon",
    "snake",
    "horse",
    "goat",
    "monkey",
    "rooster",
    "dog",
    "pig",
}

WARNING_LOW_RESOLUTION = "LOW_RESOLUTION"
WARNING_VERY_LARGE = "VERY_LARGE"
WARNING_OPAQUE_BACKGROUND = "OPAQUE_BACKGROUND"
WARNING_POSSIBLE_BAKED_BACKGROUND = "POSSIBLE_BAKED_BACKGROUND"
WARNING_SUSPICIOUS_DIMENSIONS = "SUSPICIOUS_DIMENSIONS"
WARNING_ZODIAC_SIZE_OUTLIER = "ZODIAC_SIZE_OUTLIER"
WARNING_UNREADABLE = "UNREADABLE"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_illustrations_root() -> Path:
    return project_root() / "backend" / "web" / "static" / "images" / "illustrations" / "originals"


def default_reports_dir() -> Path:
    return project_root() / "backend" / "reports"


def discover_png_files(root: Path) -> List[Path]:
    """Return sorted PNG files under root, skipping hidden files and directories."""
    if not root.exists():
        return []

    found: List[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() != ".png":
            continue
        relative_parts = path.relative_to(root).parts
        if any(part.startswith(".") for part in relative_parts):
            continue
        found.append(path)
    return found


def category_of(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    if len(relative.parts) >= 2:
        return relative.parts[0]
    return "uncategorized"


def static_relative_path(path: Path, root: Path) -> str:
    relative = path.relative_to(root).as_posix()
    return f"{STATIC_RELATIVE_PREFIX}/{relative}"


def classify_orientation(width: int, height: int) -> Tuple[float, str]:
    if height == 0:
        return 0.0, "portrait"
    ratio = round(width / height, 3)
    if SQUARE_RATIO_MIN <= ratio <= SQUARE_RATIO_MAX:
        return ratio, "square"
    if width > height:
        return ratio, "landscape"
    return ratio, "portrait"


def has_alpha_channel(image: Image.Image) -> bool:
    if "A" in image.getbands():
        return True
    if image.mode == "P" and "transparency" in image.info:
        return True
    return False


def has_actual_transparency(image: Image.Image) -> bool:
    """True only when at least one pixel has alpha below 255.

    Uses an in-memory conversion when needed. Never writes a file.
    """
    working = image
    if "A" not in working.getbands():
        if working.mode == "P" and "transparency" in working.info:
            working = working.convert("RGBA")
        else:
            return False
    extrema = working.getchannel("A").getextrema()
    return extrema[0] < 255


def is_paper_like_rgb(red: int, green: int, blue: int) -> bool:
    """Heuristic for white / cream / yellow / beige paper tones."""
    if red >= 220 and green >= 220 and blue >= 210:
        return True
    if red >= 210 and green >= 190 and blue >= 140 and (red - blue) <= 90 and (green - blue) <= 80:
        return True
    if red >= 190 and green >= 170 and blue >= 120 and abs(red - green) <= 45 and red >= blue:
        return True
    return False


def possible_baked_background(image: Image.Image, transparent: bool) -> bool:
    """Sample corners and borders for paper-colored pixels.

    Only applied to fully opaque images. Conservative; may be wrong.
    """
    if transparent:
        return False

    rgb = image if image.mode == "RGB" else image.convert("RGB")
    width, height = rgb.size
    if width < 2 or height < 2:
        return False

    depth = min(BORDER_SAMPLE_DEPTH, width, height)
    pixels = rgb.load()
    samples: List[Tuple[int, int, int]] = []

    for y in range(height):
        for x in range(width):
            on_border = x < depth or y < depth or x >= width - depth or y >= height - depth
            if not on_border:
                continue
            samples.append(pixels[x, y][:3])

    if len(samples) < 16:
        return False

    paper_count = sum(1 for color in samples if is_paper_like_rgb(*color))
    return (paper_count / len(samples)) >= BAKED_BACKGROUND_THRESHOLD


def size_warnings(width: int, height: int, file_size_bytes: int) -> List[str]:
    warnings: List[str] = []
    if width < LOW_RESOLUTION_PX or height < LOW_RESOLUTION_PX:
        warnings.append(WARNING_LOW_RESOLUTION)
    if width > VERY_LARGE_PX or height > VERY_LARGE_PX or file_size_bytes > VERY_LARGE_BYTES:
        warnings.append(WARNING_VERY_LARGE)
    return warnings


def category_dimension_warnings(
    category: str,
    filename: str,
    orientation: str,
    aspect_ratio: float,
) -> List[str]:
    """Guideline-based dimension checks. Warnings only; never fail the scan."""
    stem = Path(filename).stem.lower()
    flags: List[str] = []

    def flag() -> None:
        if WARNING_SUSPICIOUS_DIMENSIONS not in flags:
            flags.append(WARNING_SUSPICIOUS_DIMENSIONS)

    if category == "masthead":
        if orientation in {"portrait", "square"}:
            flag()
        if aspect_ratio < MASTHEAD_RATIO_MIN or aspect_ratio > MASTHEAD_RATIO_MAX:
            flag()

    elif category == "world":
        if stem == "globe" and orientation != "square":
            flag()
        if stem == "weather" and not (
            NEAR_SQUARE_RATIO_MIN <= aspect_ratio <= NEAR_SQUARE_RATIO_MAX
        ):
            flag()

    elif category == "government":
        if aspect_ratio <= STRONG_PORTRAIT_RATIO_MAX:
            flag()

    elif category == "movies":
        if stem == "film-strip" and orientation != "landscape":
            flag()
        if stem == "movie-camera" and orientation == "portrait":
            flag()

    elif category == "music":
        if stem != "microphone" and aspect_ratio <= STRONG_PORTRAIT_RATIO_MAX:
            flag()

    elif category == "sports":
        if stem in {"baseball", "football"} and aspect_ratio <= STRONG_PORTRAIT_RATIO_MAX:
            flag()

    elif category == "technology":
        if stem not in {"mobile-phone", "smartphone"} and aspect_ratio <= STRONG_PORTRAIT_RATIO_MAX:
            flag()

    elif category == "science":
        if stem == "rocket" and orientation != "portrait":
            flag()
        if stem == "atom" and orientation != "square":
            flag()
        if stem == "airplane" and orientation != "landscape":
            flag()
        if stem == "satellite" and aspect_ratio <= STRONG_PORTRAIT_RATIO_MAX:
            flag()

    elif category == "zodiac":
        if stem == "chinese-zodiac" and aspect_ratio <= STRONG_PORTRAIT_RATIO_MAX:
            flag()

    return flags


def inspect_png(path: Path, root: Path) -> Dict[str, Any]:
    """Inspect a PNG without modifying it."""
    file_size_bytes = path.stat().st_size
    record: Dict[str, Any] = {
        "category": category_of(path, root),
        "filename": path.name,
        "relativePath": static_relative_path(path, root),
        "width": 0,
        "height": 0,
        "aspectRatio": 0.0,
        "orientation": "unknown",
        "mode": "",
        "hasAlpha": False,
        "hasTransparency": False,
        "fileSizeBytes": file_size_bytes,
        "fileSizeKB": round(file_size_bytes / 1024, 1),
        "fileSizeMB": round(file_size_bytes / (1024 * 1024), 3),
        "warnings": [],
        "status": "OK",
    }

    try:
        with Image.open(path) as image:
            image.load()
            width, height = image.size
            aspect_ratio, orientation = classify_orientation(width, height)
            alpha = has_alpha_channel(image)
            transparent = has_actual_transparency(image)
            baked = possible_baked_background(image, transparent)
            mode = image.mode
    except OSError as exc:
        record["warnings"] = [WARNING_UNREADABLE]
        record["status"] = "WARNINGS"
        record["error"] = str(exc)
        return record

    warnings: List[str] = []
    warnings.extend(size_warnings(width, height, file_size_bytes))
    if not transparent and record["category"] in OPAQUE_FLAG_CATEGORIES:
        warnings.append(WARNING_OPAQUE_BACKGROUND)
    if baked:
        warnings.append(WARNING_POSSIBLE_BAKED_BACKGROUND)
    warnings.extend(
        category_dimension_warnings(
            record["category"],
            record["filename"],
            orientation,
            aspect_ratio,
        )
    )

    record.update(
        {
            "width": width,
            "height": height,
            "aspectRatio": aspect_ratio,
            "orientation": orientation,
            "mode": mode,
            "hasAlpha": alpha,
            "hasTransparency": transparent,
            "warnings": warnings,
            "status": "OK" if not warnings else "WARNINGS",
        }
    )
    return record


def _median(values: Sequence[int]) -> float:
    if not values:
        return 0.0
    return float(statistics.median(values))


def is_zodiac_size_outlier(value: int, median_value: float) -> bool:
    if median_value <= 0:
        return False
    return value < median_value * (1 - ZODIAC_SIZE_TOLERANCE) or value > median_value * (
        1 + ZODIAC_SIZE_TOLERANCE
    )


def zodiac_consistency(images: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    animals = [
        image
        for image in images
        if image.get("category") == "zodiac"
        and Path(image["filename"]).stem.lower() in ZODIAC_ANIMALS
        and image.get("width")
        and image.get("height")
    ]

    widths = [image["width"] for image in animals]
    heights = [image["height"] for image in animals]
    median_width = _median(widths)
    median_height = _median(heights)

    outliers: List[Dict[str, Any]] = []
    for image in animals:
        reasons: List[str] = []
        if is_zodiac_size_outlier(image["width"], median_width):
            reasons.append("width")
        if is_zodiac_size_outlier(image["height"], median_height):
            reasons.append("height")
        if reasons:
            outliers.append(
                {
                    "filename": image["filename"],
                    "relativePath": image["relativePath"],
                    "width": image["width"],
                    "height": image["height"],
                    "differs": reasons,
                }
            )
            if WARNING_ZODIAC_SIZE_OUTLIER not in image["warnings"]:
                image["warnings"].append(WARNING_ZODIAC_SIZE_OUTLIER)
                image["status"] = "WARNINGS"

    return {
        "count": len(animals),
        "minWidth": min(widths) if widths else 0,
        "maxWidth": max(widths) if widths else 0,
        "minHeight": min(heights) if heights else 0,
        "maxHeight": max(heights) if heights else 0,
        "medianWidth": median_width,
        "medianHeight": median_height,
        "outliers": outliers,
        "note": (
            "Individual animal images are flagged when width or height differs "
            "from the median by more than 50%. Exact matching dimensions are not required."
        ),
    }


def build_summary(images: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "total": len(images),
        "ok": sum(1 for image in images if image["status"] == "OK"),
        "warnings": sum(1 for image in images if image["status"] != "OK"),
        "transparent": sum(1 for image in images if image.get("hasTransparency")),
        "opaque": sum(1 for image in images if not image.get("hasTransparency")),
        "lowResolution": sum(
            1 for image in images if WARNING_LOW_RESOLUTION in image.get("warnings", [])
        ),
        "veryLarge": sum(1 for image in images if WARNING_VERY_LARGE in image.get("warnings", [])),
        "opaqueBackground": sum(
            1 for image in images if WARNING_OPAQUE_BACKGROUND in image.get("warnings", [])
        ),
        "possibleBakedBackground": sum(
            1
            for image in images
            if WARNING_POSSIBLE_BAKED_BACKGROUND in image.get("warnings", [])
        ),
        "suspiciousDimensions": sum(
            1
            for image in images
            if WARNING_SUSPICIOUS_DIMENSIONS in image.get("warnings", [])
        ),
    }


def scan_illustrations(root: Path) -> Dict[str, Any]:
    png_files = discover_png_files(root)
    images = [inspect_png(path, root) for path in png_files]
    consistency = zodiac_consistency(images)
    summary = build_summary(images)
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "root": str(root).replace("\\", "/"),
        "summary": summary,
        "images": images,
        "zodiacConsistency": consistency,
        "notes": [
            "This report is read-only. No illustration files were modified.",
            "POSSIBLE_BAKED_BACKGROUND uses a simple corner/border color heuristic "
            "(white/cream/beige) and can be wrong.",
            "Category dimension checks are guidelines, not hard failures.",
        ],
    }


def _format_file_size(image: Dict[str, Any]) -> str:
    if image["fileSizeBytes"] >= 1024 * 1024:
        return f"{image['fileSizeMB']:.2f} MB"
    return f"{image['fileSizeKB']:.1f} KB"


def _yes_no(value: bool) -> str:
    return "YES" if value else "NO"


def render_text_report(report: Dict[str, Any]) -> str:
    summary = report["summary"]
    lines: List[str] = [
        "BIRTHDAY CHRONICLES — ILLUSTRATION MASTER REPORT",
        "================================================",
        "",
        f"Root:",
        report["root"],
        "",
        f"Generated at: {report['generatedAt']}",
        f"Total PNG files: {summary['total']}",
        "",
        "SUMMARY",
        "-------",
        f"OK: {summary['ok']}",
        f"Warnings: {summary['warnings']}",
        f"Transparent: {summary['transparent']}",
        f"Opaque: {summary['opaque']}",
        f"Low resolution: {summary['lowResolution']}",
        f"Very large: {summary['veryLarge']}",
        "",
        "NOTES",
        "-----",
    ]
    for note in report.get("notes", []):
        lines.append(f"- {note}")

    lines.extend(["", "BY CATEGORY", "-----------", ""])

    by_category: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for image in report["images"]:
        by_category[image["category"]].append(image)

    for category in sorted(by_category):
        lines.append(f"[{category}]")
        lines.append("")
        for image in by_category[category]:
            lines.extend(
                [
                    image["filename"],
                    f"  Size: {image['width']} x {image['height']}",
                    f"  Ratio: {image['aspectRatio']:.3f}",
                    f"  Orientation: {image['orientation']}",
                    f"  Mode: {image['mode'] or 'n/a'}",
                    f"  Alpha channel: {_yes_no(image['hasAlpha'])}",
                    f"  Actual transparency: {_yes_no(image['hasTransparency'])}",
                    f"  File size: {_format_file_size(image)}",
                    f"  Status: {image['status']}",
                ]
            )
            if image["warnings"]:
                lines.append(f"  Warnings: {', '.join(image['warnings'])}")
            lines.append("")
        lines.append("")

    grouped: Dict[str, List[str]] = defaultdict(list)
    for image in report["images"]:
        display = f"{image['category']}/{image['filename']}"
        for warning in image["warnings"]:
            grouped[warning].append(display)

    lines.extend(["WARNINGS", "--------", ""])
    if not grouped:
        lines.append("None.")
        lines.append("")
    else:
        for warning in sorted(grouped):
            lines.append(warning)
            for item in grouped[warning]:
                lines.append(f"- {item}")
            lines.append("")

    consistency = report["zodiacConsistency"]
    lines.extend(
        [
            "ZODIAC CONSISTENCY",
            "------------------",
            f"Individual animal images: {consistency['count']}",
            f"Width range: {consistency['minWidth']} – {consistency['maxWidth']}",
            f"Height range: {consistency['minHeight']} – {consistency['maxHeight']}",
            f"Median width: {consistency['medianWidth']}",
            f"Median height: {consistency['medianHeight']}",
            consistency["note"],
            "",
        ]
    )
    if consistency["outliers"]:
        lines.append("Outliers (>50% from median):")
        for outlier in consistency["outliers"]:
            lines.append(
                f"- {outlier['filename']} ({outlier['width']} x {outlier['height']}; "
                f"{', '.join(outlier['differs'])})"
            )
    else:
        lines.append("No animal image differs from the median by more than 50%.")
    lines.append("")
    return "\n".join(lines)


def write_reports(
    report: Dict[str, Any],
    text_output: Path,
    json_output: Path,
) -> None:
    text_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    text_output.write_text(render_text_report(report), encoding="utf-8")
    json_output.write_text(json.dumps(report, indent=2), encoding="utf-8")


def print_console_summary(
    report: Dict[str, Any],
    text_output: Path,
    json_output: Path,
    verbose: bool = False,
) -> None:
    summary = report["summary"]
    print("Illustration scan complete.")
    print()
    print(f"Images scanned: {summary['total']}")
    print(f"Transparent: {summary['transparent']}")
    print(f"Opaque: {summary['opaque']}")
    print(f"Warnings: {summary['warnings']}")
    print()
    print("Text report:")
    print(text_output)
    print()
    print("JSON report:")
    print(json_output)
    if verbose:
        print()
        for image in report["images"]:
            print(
                f"{image['relativePath']}: {image['width']}x{image['height']} "
                f"{image['orientation']} {image['status']}"
            )
            if image["warnings"]:
                print(f"  {', '.join(image['warnings'])}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only report for illustration master PNG files.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Illustration originals root (default: backend/web/static/images/illustrations/originals).",
    )
    parser.add_argument(
        "--text-output",
        type=Path,
        default=None,
        help="Path for the text report.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="Path for the JSON report.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print every image record to the console.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    root = (args.root or default_illustrations_root()).resolve()
    reports_dir = default_reports_dir()
    text_output = (args.text_output or reports_dir / DEFAULT_TEXT_NAME).resolve()
    json_output = (args.json_output or reports_dir / DEFAULT_JSON_NAME).resolve()

    report = scan_illustrations(root)
    write_reports(report, text_output, json_output)
    print_console_summary(report, text_output, json_output, verbose=args.verbose)
    return 0


if __name__ == "__main__":
    sys.exit(main())
