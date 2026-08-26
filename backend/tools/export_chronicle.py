"""Render a Birthday Chronicle page to native PNG and proportional A4 print files."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_WIDTH = 1000
CANONICAL_HEIGHT = 1596
ROOT_SELECTOR = ".chronicle-page"
A4_WIDTH_MM = 210.0
A4_HEIGHT_MM = 297.0
A4_PNG_DPI = 300


@dataclass(frozen=True)
class A4Placement:
    """A proportionally fitted Chronicle position within an A4 page, in millimetres."""

    width_mm: float
    height_mm: float
    x_mm: float
    y_mm: float


def rendered_dimensions(scale: int) -> tuple[int, int]:
    """Return the expected raster dimensions for a Chromium device scale."""
    if scale not in (1, 2, 3):
        raise ValueError("scale must be 1, 2, or 3")
    return CANONICAL_WIDTH * scale, CANONICAL_HEIGHT * scale


def fit_on_a4(margin_mm: float = 5.0) -> A4Placement:
    """Fit the canonical Chronicle inside an A4 page without cropping or stretching."""
    if margin_mm < 0:
        raise ValueError("A4 margin cannot be negative")
    available_width = A4_WIDTH_MM - (2 * margin_mm)
    available_height = A4_HEIGHT_MM - (2 * margin_mm)
    if available_width <= 0 or available_height <= 0:
        raise ValueError("A4 margin leaves no printable area")

    scale = min(available_width / CANONICAL_WIDTH, available_height / CANONICAL_HEIGHT)
    width_mm = CANONICAL_WIDTH * scale
    height_mm = CANONICAL_HEIGHT * scale
    return A4Placement(
        width_mm=width_mm,
        height_mm=height_mm,
        x_mm=(A4_WIDTH_MM - width_mm) / 2,
        y_mm=(A4_HEIGHT_MM - height_mm) / 2,
    )


def output_paths(birth_date: date, output_dir: Path, scale: int) -> dict[str, Path]:
    """Build deterministic output names for one Chronicle export."""
    date_text = birth_date.isoformat()
    native_width, native_height = rendered_dimensions(1)
    scaled_width, scaled_height = rendered_dimensions(scale)
    return {
        "native_png": output_dir / f"birthday_chronicle_{date_text}_{native_width}x{native_height}.png",
        "scaled_png": output_dir / f"birthday_chronicle_{date_text}_{scaled_width}x{scaled_height}.png",
        "a4_png": output_dir / f"birthday_chronicle_{date_text}_A4_300dpi.png",
        "a4_pdf": output_dir / f"birthday_chronicle_{date_text}_A4.pdf",
    }


def export_url(server_url: str, birth_date: date, name: str | None, country: str, city: str | None) -> str:
    """Return the production-equivalent export route URL."""
    query = {"date": birth_date.isoformat(), "country": country}
    if name:
        query["name"] = name
    if city:
        query["city"] = city
    return f"{server_url.rstrip('/')}/chronicle/export?{urlencode(query)}"


def _validate_date(value: str) -> date:
    try:
        birth_date = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD format") from exc
    if not date(1950, 1, 1) <= birth_date <= date.today():
        raise argparse.ArgumentTypeError("date must be between 1950-01-01 and today")
    return birth_date


def _validate_png(path: Path, scale: int) -> tuple[int, int]:
    expected = rendered_dimensions(scale)
    with Image.open(path) as image:
        dimensions = image.size
        if image.getbbox() is None:
            raise RuntimeError(f"Captured PNG is empty: {path}")
    if dimensions != expected:
        raise RuntimeError(f"Expected PNG dimensions {expected[0]}x{expected[1]}, got {dimensions[0]}x{dimensions[1]}")
    return dimensions


def _capture_png(url: str, destination: Path, scale: int) -> tuple[int, int]:
    """Capture the settled master element directly from Chromium at device scale."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is required for Chronicle export. Run: pip install -r requirements.txt; "
            "python -m playwright install chromium"
        ) from exc

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": CANONICAL_WIDTH, "height": CANONICAL_HEIGHT},
                device_scale_factor=scale,
            )
            page = context.new_page()
            try:
                page.goto(url, wait_until="networkidle", timeout=30_000)
                page.locator(ROOT_SELECTOR).wait_for(state="visible", timeout=15_000)
                page.wait_for_function(
                    """
                    () => {
                        const root = document.querySelector('.chronicle-page');
                        const pending = root?.querySelector(
                            '.arrival-fit-pending, .world-news-fit-pending, .famous-birthdays-fit-pending, '
                            + '.weather-fit-pending, .zodiac-fit-pending, .movies-fit-pending, .around-fit-pending'
                        );
                        const imagesReady = root && [...root.images].every(
                            image => image.complete && image.naturalWidth > 0
                        );
                        const background = root && getComputedStyle(root).backgroundImage;
                        const backgroundUrl = background && background.match(/url\\(["']?(.*?)["']?\\)/)?.[1];
                        const backgroundReady = !backgroundUrl || (() => {
                            const image = new Image();
                            image.src = backgroundUrl;
                            return image.complete && image.naturalWidth > 0;
                        })();
                        return Boolean(root) && document.fonts.status === 'loaded' && imagesReady
                            && backgroundReady && !pending;
                    }
                    """,
                    timeout=20_000,
                )
                page.evaluate("() => new Promise(requestAnimationFrame)")
                page.evaluate("() => new Promise(requestAnimationFrame)")
                geometry = page.locator(ROOT_SELECTOR).evaluate(
                    """
                    element => ({
                        clientWidth: element.clientWidth,
                        clientHeight: element.clientHeight,
                        scrollWidth: element.scrollWidth,
                        scrollHeight: element.scrollHeight,
                    })
                    """
                )
                if (
                    geometry["clientWidth"] != CANONICAL_WIDTH
                    or geometry["clientHeight"] != CANONICAL_HEIGHT
                    or geometry["scrollWidth"] > CANONICAL_WIDTH
                    or geometry["scrollHeight"] > CANONICAL_HEIGHT
                ):
                    raise RuntimeError(
                        "Chronicle root geometry is invalid: "
                        f"{geometry['clientWidth']}x{geometry['clientHeight']} "
                        f"(scroll {geometry['scrollWidth']}x{geometry['scrollHeight']})"
                    )
                page.locator(ROOT_SELECTOR).screenshot(path=str(destination), scale="device")
            finally:
                context.close()
                browser.close()
    except PlaywrightError as exc:
        raise RuntimeError(f"BirthdayChronicles server is not reachable or did not render at {url}: {exc}") from exc
    except (AttributeError, NotImplementedError, OSError) as exc:
        raise RuntimeError(
            "Playwright Chromium could not start in this Python runtime. "
            "Install the requirements in a supported Python environment, then run: "
            "python -m playwright install chromium"
        ) from exc
    return _validate_png(destination, scale)


def _create_a4_png(source: Path, destination: Path, placement: A4Placement) -> tuple[int, int]:
    """Place a high-resolution Chronicle PNG onto a white A4 300 DPI canvas."""
    canvas_size = (
        round(A4_WIDTH_MM / 25.4 * A4_PNG_DPI),
        round(A4_HEIGHT_MM / 25.4 * A4_PNG_DPI),
    )
    target_size = (
        round(placement.width_mm / 25.4 * A4_PNG_DPI),
        round(placement.height_mm / 25.4 * A4_PNG_DPI),
    )
    target_position = (
        round(placement.x_mm / 25.4 * A4_PNG_DPI),
        round(placement.y_mm / 25.4 * A4_PNG_DPI),
    )
    with Image.open(source) as image:
        chronicle = image.convert("RGB").resize(target_size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", canvas_size, "white")
    canvas.paste(chronicle, target_position)
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, dpi=(A4_PNG_DPI, A4_PNG_DPI))
    return canvas.size


def _create_a4_pdf(source: Path, destination: Path, placement: A4Placement) -> None:
    """Create an A4 PDF with the Chronicle image centered at its fitted size."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen.canvas import Canvas
    except ImportError as exc:
        raise RuntimeError("ReportLab is required for A4 PDF export. Run: pip install -r requirements.txt") from exc

    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas = Canvas(str(destination), pagesize=A4, pageCompression=0)
    canvas.drawImage(
        str(source),
        placement.x_mm * mm,
        placement.y_mm * mm,
        width=placement.width_mm * mm,
        height=placement.height_mm * mm,
        preserveAspectRatio=True,
        mask=None,
    )
    canvas.showPage()
    canvas.save()


def _print_status(birth_date: date, scale: int, placement: A4Placement, created: Iterable[Path]) -> None:
    width, height = rendered_dimensions(scale)
    print(f"Date: {birth_date.isoformat()}")
    print(f"Chronicle root: {CANONICAL_WIDTH}x{CANONICAL_HEIGHT}")
    print(f"Scale: {scale}")
    print(f"PNG: {width}x{height}")
    print(f"A4 placement: {placement.width_mm:.2f} x {placement.height_mm:.2f} mm")
    for path in created:
        print(f"Created: {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, type=_validate_date, help="Birth date in YYYY-MM-DD format")
    parser.add_argument("--format", choices=("png", "a4-png", "a4-pdf"), default="png")
    parser.add_argument("--all", action="store_true", help="Create native PNG, high-resolution PNG, A4 PNG, and A4 PDF")
    parser.add_argument("--scale", type=int, choices=(1, 2, 3), help="Chromium device scale; default is 1 for PNG and 3 for print outputs")
    parser.add_argument("--a4-margin-mm", type=float, default=5.0, help="A4 safety margin in millimetres (default: 5)")
    parser.add_argument("--server-url", default="http://127.0.0.1:5000", help="Running BirthdayChronicles server URL")
    parser.add_argument("--name", help="Optional Chronicle name")
    parser.add_argument("--country", default="India", help="Birth country (default: India)")
    parser.add_argument("--city", help="Optional birth city")
    parser.add_argument("--output-dir", type=Path, help="Output directory; defaults to output/chronicles/YYYY-MM-DD")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir or PROJECT_ROOT / "output" / "chronicles" / args.date.isoformat()
    placement = fit_on_a4(args.a4_margin_mm)
    url = export_url(args.server_url, args.date, args.name, args.country, args.city)
    print_scale = args.scale or 3
    png_scale = args.scale or 1
    paths = output_paths(args.date, output_dir, print_scale)
    created: list[Path] = []

    if args.all:
        native_path = output_paths(args.date, output_dir, 1)["native_png"]
        _capture_png(url, native_path, 1)
        created.append(native_path)
        source_path = paths["scaled_png"]
        _capture_png(url, source_path, print_scale)
        created.append(source_path)
        _create_a4_png(source_path, paths["a4_png"], placement)
        created.append(paths["a4_png"])
        _create_a4_pdf(source_path, paths["a4_pdf"], placement)
        created.append(paths["a4_pdf"])
    elif args.format == "png":
        source_path = output_paths(args.date, output_dir, png_scale)["scaled_png"]
        _capture_png(url, source_path, png_scale)
        created.append(source_path)
    else:
        source_path = paths["scaled_png"]
        _capture_png(url, source_path, print_scale)
        created.append(source_path)
        if args.format == "a4-png":
            _create_a4_png(source_path, paths["a4_png"], placement)
            created.append(paths["a4_png"])
        else:
            _create_a4_pdf(source_path, paths["a4_pdf"], placement)
            created.append(paths["a4_pdf"])

    _print_status(args.date, print_scale if args.format != "png" or args.all else png_scale, placement, created)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
