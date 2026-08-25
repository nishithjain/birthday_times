"""Tests for illustration variant generation orchestration."""

import numpy as np
import pytest
from PIL import Image

from backend.services.newspaper_style_service import NewspaperStyleService
from backend.tools.generate_illustration_variants import (
    build_jobs,
    collect_status,
    required_eras_for_illustration,
    run_jobs,
    validate_generated_variant,
)


@pytest.fixture(scope="module")
def styles():
    return NewspaperStyleService().styles


def _illustration(illustration_id, category, year_from, year_to):
    return {
        "id": illustration_id,
        "category": category,
        "path": f"images/illustrations/originals/{category}/{illustration_id}.png",
        "yearFrom": year_from,
        "yearTo": year_to,
    }


def _make_original(root, relative, size=(60, 48)):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = size
    arr = np.zeros((height, width, 4), dtype=np.uint8)
    arr[:, : width // 2] = (200, 40, 40, 255)
    arr[:, width // 2 :] = (40, 80, 200, 255)
    arr[:6, :, 3] = 0  # transparent strip
    Image.fromarray(arr, mode="RGBA").save(path)
    return path


class TestRequiredEras:
    @pytest.mark.parametrize(
        ("illustration", "expected"),
        [
            (_illustration("jukebox", "music", 1950, 1969), ["1950", "1960"]),
            (_illustration("boombox", "music", 1980, 1994), ["1980", "1990"]),
            (_illustration("smartphone", "technology", 2010, None), ["2010", "2015"]),
            (_illustration("eagle", "masthead", 1950, 1969), ["1950", "1960"]),
            (
                _illustration("rocket", "science", 1957, 1989),
                ["1950", "1960", "1970", "1980"],
            ),
        ],
    )
    def test_required_eras(self, styles, illustration, expected):
        assert required_eras_for_illustration(illustration, styles) == expected


class TestBuildJobs:
    def test_missing_original_warns_and_skips(self, tmp_path, styles):
        illustration = _illustration("ghost", "world", 1950, None)
        jobs, warnings = build_jobs([illustration], styles, root=tmp_path)
        assert jobs == []
        assert any("MISSING ORIGINAL" in w for w in warnings)

    def test_era_filter_limits_jobs(self, tmp_path, styles):
        illustration = _illustration("jukebox", "music", 1950, 1969)
        _make_original(tmp_path, illustration["path"])
        jobs, warnings = build_jobs(
            [illustration], styles, root=tmp_path, era_filter="1950"
        )
        assert [job.era for job in jobs] == ["1950"]

    def test_unnecessary_era_is_warned(self, tmp_path, styles):
        illustration = _illustration("jukebox", "music", 1950, 1969)
        _make_original(tmp_path, illustration["path"])
        jobs, warnings = build_jobs(
            [illustration], styles, root=tmp_path, era_filter="1980"
        )
        assert jobs == []
        assert any("UNNECESSARY ERA" in w for w in warnings)


class TestRunJobs:
    def _jobs(self, tmp_path, styles, era_filter="1950"):
        illustration = _illustration("jukebox", "music", 1950, 1969)
        _make_original(tmp_path, illustration["path"])
        return build_jobs(
            [illustration], styles, root=tmp_path, era_filter=era_filter
        )[0]

    def test_generation_creates_valid_variant(self, tmp_path, styles):
        jobs = self._jobs(tmp_path, styles)
        summary = run_jobs(jobs)
        assert summary.generated == 1
        assert summary.failed == 0
        variant = jobs[0].variant_path
        assert variant.is_file()
        assert validate_generated_variant(variant, jobs[0].original_path) is None

    def test_existing_is_skipped_without_force(self, tmp_path, styles):
        jobs = self._jobs(tmp_path, styles)
        run_jobs(jobs)
        original_bytes = jobs[0].variant_path.read_bytes()
        summary = run_jobs(jobs)
        assert summary.generated == 0
        assert summary.already_existed == 1
        assert jobs[0].variant_path.read_bytes() == original_bytes

    def test_force_regenerates(self, tmp_path, styles):
        jobs = self._jobs(tmp_path, styles)
        run_jobs(jobs)
        jobs[0].variant_path.write_bytes(b"stale")
        summary = run_jobs(jobs, force=True)
        assert summary.generated == 1
        assert jobs[0].variant_path.read_bytes() != b"stale"

    def test_dry_run_creates_nothing(self, tmp_path, styles):
        jobs = self._jobs(tmp_path, styles)
        summary = run_jobs(jobs, dry_run=True)
        assert summary.generated == 0
        assert not jobs[0].variant_path.exists()


class TestStatus:
    def test_status_counts_without_writing(self, tmp_path, styles):
        illustration = _illustration("jukebox", "music", 1950, 1969)
        _make_original(tmp_path, illustration["path"])
        report = collect_status([illustration], styles, root=tmp_path)

        assert report["illustrations"] == 1
        assert len(report["required_variants"]) == 2  # 1950 + 1960
        assert len(report["existing_variants"]) == 0
        assert len(report["missing_variants"]) == 2
        assert report["originals_missing"] == []
        # status must not create files
        variants_dir = tmp_path / "images" / "illustrations" / "variants"
        assert not variants_dir.exists()
