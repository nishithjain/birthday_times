"""Tests for the read-only illustration master report."""

from pathlib import Path

from PIL import Image

from backend.tools.report_illustrations import (
    WARNING_LOW_RESOLUTION,
    WARNING_OPAQUE_BACKGROUND,
    WARNING_POSSIBLE_BAKED_BACKGROUND,
    WARNING_SUSPICIOUS_DIMENSIONS,
    WARNING_VERY_LARGE,
    WARNING_ZODIAC_SIZE_OUTLIER,
    category_dimension_warnings,
    classify_orientation,
    discover_png_files,
    has_actual_transparency,
    has_alpha_channel,
    inspect_png,
    is_zodiac_size_outlier,
    main,
    possible_baked_background,
    scan_illustrations,
    size_warnings,
    write_reports,
    zodiac_consistency,
)


def _save_png(path: Path, image: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")


def _rgb(path: Path, size: tuple[int, int], color: tuple[int, int, int] = (10, 20, 30)) -> Path:
    _save_png(path, Image.new("RGB", size, color=color))
    return path


def _rgba(
    path: Path,
    size: tuple[int, int],
    color: tuple[int, int, int, int] = (10, 20, 30, 255),
) -> Path:
    _save_png(path, Image.new("RGBA", size, color=color))
    return path


def _library(tmp_path: Path) -> Path:
    return tmp_path / "illustrations" / "originals"


class TestDiscoverPngFiles:
    def test_scans_pngs_and_ignores_hidden_and_non_png(self, tmp_path):
        root = _library(tmp_path)
        _rgb(root / "world" / "globe.png", (400, 400))
        _rgb(root / "world" / "notes.jpg", (400, 400))
        _rgb(root / "world" / ".hidden.png", (400, 400))
        (root / "world" / "readme.txt").parent.mkdir(parents=True, exist_ok=True)
        (root / "world" / "readme.txt").write_text("skip", encoding="utf-8")
        nested_dir = root / "world" / "subdir"
        nested_dir.mkdir(parents=True, exist_ok=True)

        found = discover_png_files(root)

        assert [path.name for path in found] == ["globe.png"]


class TestOrientation:
    def test_square_detection(self):
        ratio, orientation = classify_orientation(600, 600)
        assert ratio == 1.0
        assert orientation == "square"

    def test_near_square_uses_tolerance(self):
        _, orientation = classify_orientation(100, 104)
        assert orientation == "square"

    def test_landscape_detection(self):
        ratio, orientation = classify_orientation(1200, 400)
        assert ratio == 3.0
        assert orientation == "landscape"

    def test_portrait_detection(self):
        ratio, orientation = classify_orientation(400, 800)
        assert ratio == 0.5
        assert orientation == "portrait"


class TestTransparency:
    def test_rgba_with_actual_transparency(self, tmp_path):
        path = _rgba(tmp_path / "transparent.png", (40, 40), (12, 34, 56, 0))
        with Image.open(path) as image:
            assert has_alpha_channel(image) is True
            assert has_actual_transparency(image) is True

    def test_rgba_without_transparency(self, tmp_path):
        path = _rgba(tmp_path / "opaque-alpha.png", (40, 40), (12, 34, 56, 255))
        with Image.open(path) as image:
            assert has_alpha_channel(image) is True
            assert has_actual_transparency(image) is False

    def test_rgb_opaque_image(self, tmp_path):
        path = _rgb(tmp_path / "opaque.png", (40, 40))
        with Image.open(path) as image:
            assert has_alpha_channel(image) is False
            assert has_actual_transparency(image) is False


class TestSizeAndCategoryWarnings:
    def test_low_resolution_warning(self):
        assert WARNING_LOW_RESOLUTION in size_warnings(299, 400, 1000)
        assert WARNING_LOW_RESOLUTION not in size_warnings(300, 300, 1000)

    def test_very_large_dimension_warning(self):
        assert WARNING_VERY_LARGE in size_warnings(4001, 200, 1000)

    def test_very_large_file_size_warning(self):
        assert WARNING_VERY_LARGE in size_warnings(400, 400, 5 * 1024 * 1024 + 1)

    def test_masthead_portrait_is_suspicious(self):
        warnings = category_dimension_warnings("masthead", "eagle.png", "portrait", 0.5)
        assert WARNING_SUSPICIOUS_DIMENSIONS in warnings

    def test_globe_non_square_is_suspicious(self):
        warnings = category_dimension_warnings("world", "globe.png", "landscape", 1.8)
        assert WARNING_SUSPICIOUS_DIMENSIONS in warnings

    def test_microphone_portrait_is_not_flagged(self):
        warnings = category_dimension_warnings("music", "microphone.png", "portrait", 0.4)
        assert warnings == []

    def test_inspect_flags_opaque_and_low_resolution(self, tmp_path):
        root = _library(tmp_path)
        path = _rgb(root / "sports" / "cricket.png", (80, 80), (0, 0, 0))
        record = inspect_png(path, root)
        assert WARNING_LOW_RESOLUTION in record["warnings"]
        assert WARNING_OPAQUE_BACKGROUND in record["warnings"]
        assert record["hasTransparency"] is False
        assert record["status"] == "WARNINGS"


class TestBakedBackground:
    def test_cream_border_on_opaque_image(self, tmp_path):
        image = Image.new("RGB", (40, 40), color=(12, 12, 12))
        for x in range(40):
            for y in range(3):
                image.putpixel((x, y), (245, 240, 220))
                image.putpixel((x, 39 - y), (245, 240, 220))
        for y in range(40):
            for x in range(3):
                image.putpixel((x, y), (245, 240, 220))
                image.putpixel((39 - x, y), (245, 240, 220))

        assert possible_baked_background(image, transparent=False) is True
        assert possible_baked_background(image, transparent=True) is False


class TestZodiacConsistency:
    def test_outlier_detection_and_image_warning(self):
        images = [
            {
                "category": "zodiac",
                "filename": "rat.png",
                "relativePath": "images/illustrations/originals/zodiac/rat.png",
                "width": 400,
                "height": 400,
                "warnings": [],
                "status": "OK",
            },
            {
                "category": "zodiac",
                "filename": "ox.png",
                "relativePath": "images/illustrations/originals/zodiac/ox.png",
                "width": 400,
                "height": 400,
                "warnings": [],
                "status": "OK",
            },
            {
                "category": "zodiac",
                "filename": "tiger.png",
                "relativePath": "images/illustrations/originals/zodiac/tiger.png",
                "width": 400,
                "height": 400,
                "warnings": [],
                "status": "OK",
            },
            {
                "category": "zodiac",
                "filename": "dragon.png",
                "relativePath": "images/illustrations/originals/zodiac/dragon.png",
                "width": 100,
                "height": 100,
                "warnings": [],
                "status": "OK",
            },
        ]

        result = zodiac_consistency(images)

        assert result["medianWidth"] == 400
        assert result["outliers"][0]["filename"] == "dragon.png"
        assert WARNING_ZODIAC_SIZE_OUTLIER in images[3]["warnings"]
        assert is_zodiac_size_outlier(100, 400) is True
        assert is_zodiac_size_outlier(400, 400) is False


class TestReportOutputs:
    def test_json_and_text_reports_are_created(self, tmp_path):
        root = _library(tmp_path)
        _rgba(root / "world" / "globe.png", (400, 400), (20, 40, 80, 0))
        _rgb(root / "masthead" / "eagle.png", (80, 200), (0, 0, 0))
        _rgba(root / "zodiac" / "rat.png", (400, 400), (1, 2, 3, 0))
        _rgba(root / "zodiac" / "ox.png", (400, 400), (1, 2, 3, 0))
        _rgba(root / "zodiac" / "tiger.png", (400, 400), (1, 2, 3, 0))
        _rgba(root / "zodiac" / "dragon.png", (100, 100), (1, 2, 3, 0))

        text_output = tmp_path / "out" / "illustrations_report.txt"
        json_output = tmp_path / "out" / "illustrations_report.json"

        exit_code = main(
            [
                "--root",
                str(root),
                "--text-output",
                str(text_output),
                "--json-output",
                str(json_output),
            ]
        )

        assert exit_code == 0
        assert text_output.is_file()
        assert json_output.is_file()

        text = text_output.read_text(encoding="utf-8")
        assert "BIRTHDAY CHRONICLES — ILLUSTRATION MASTER REPORT" in text
        assert "[world]" in text
        assert "globe.png" in text
        assert "ZODIAC CONSISTENCY" in text

        report = scan_illustrations(root)
        write_reports(report, text_output, json_output)
        globe = next(image for image in report["images"] if image["filename"] == "globe.png")
        eagle = next(image for image in report["images"] if image["filename"] == "eagle.png")
        assert globe["hasTransparency"] is True
        assert globe["orientation"] == "square"
        assert WARNING_SUSPICIOUS_DIMENSIONS in eagle["warnings"]
        assert WARNING_LOW_RESOLUTION in eagle["warnings"]
        assert report["summary"]["total"] == 6
        assert report["zodiacConsistency"]["outliers"]
        assert WARNING_POSSIBLE_BAKED_BACKGROUND not in globe["warnings"]
