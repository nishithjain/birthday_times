"""Tests for image variant generation orchestration."""

from pathlib import Path

import pytest
from PIL import Image

from backend.services.newspaper_style_service import NewspaperStyleService
from backend.services.president_service import PresidentService
from backend.tools.generate_image_variants import (
    build_president_jobs,
    collect_president_status,
    main,
    required_eras_for_president,
    run_jobs,
)


@pytest.fixture
def president_service():
    return PresidentService()


@pytest.fixture
def style_service():
    return NewspaperStyleService()


class TestGenerateImageVariants:
    def test_eisenhower_required_eras(self, president_service, style_service):
        eras = required_eras_for_president(
            "dwight_eisenhower",
            president_service.terms,
            style_service.styles,
        )

        assert eras == ["1950", "1960"]

    def test_eisenhower_does_not_require_1970(self, president_service, style_service):
        eras = required_eras_for_president(
            "dwight_eisenhower",
            president_service.terms,
            style_service.styles,
        )

        assert "1970" not in eras

    def test_existing_variant_is_skipped_without_force(
        self, tmp_path, president_service, style_service
    ):
        president_service.static_root = tmp_path
        original_relative = "images/people/presidents/originals/test_president.png"
        variant_relative = "images/people/presidents/variants/1950/test_president.png"
        original_path = tmp_path / original_relative
        variant_path = tmp_path / variant_relative
        original_path.parent.mkdir(parents=True, exist_ok=True)
        variant_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (600, 750), color=(80, 80, 80)).save(original_path)
        Image.new("RGB", (600, 750), color=(10, 10, 10)).save(variant_path)
        original_bytes = variant_path.read_bytes()

        president_service.presidents_by_id = {
            "test_president": {
                "id": "test_president",
                "name": "Test President",
                "presidentNumbers": [99],
                "originalImage": original_relative,
            }
        }
        president_service.terms = [
            {
                "presidentId": "test_president",
                "dateFrom": "1953-01-20",
                "dateTo": "1961-01-19",
            }
        ]

        jobs, _warnings = build_president_jobs(
            president_service,
            style_service,
            subject_ids=["test_president"],
            era_filter="1950",
        )
        summary = run_jobs(jobs, output_size=(600, 750), force=False)

        assert summary.already_existed == 1
        assert summary.generated == 0
        assert variant_path.read_bytes() == original_bytes

    def test_force_replaces_existing_variant(
        self, tmp_path, president_service, style_service
    ):
        president_service.static_root = tmp_path
        original_relative = "images/people/presidents/originals/test_president.png"
        variant_relative = "images/people/presidents/variants/1950/test_president.png"
        original_path = tmp_path / original_relative
        variant_path = tmp_path / variant_relative
        original_path.parent.mkdir(parents=True, exist_ok=True)
        variant_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (600, 750), color=(180, 120, 90)).save(original_path)
        Image.new("RGB", (600, 750), color=(10, 10, 10)).save(variant_path)

        president_service.presidents_by_id = {
            "test_president": {
                "id": "test_president",
                "name": "Test President",
                "presidentNumbers": [99],
                "originalImage": original_relative,
            }
        }
        president_service.terms = [
            {
                "presidentId": "test_president",
                "dateFrom": "1953-01-20",
                "dateTo": "1961-01-19",
            }
        ]

        jobs, _warnings = build_president_jobs(
            president_service,
            style_service,
            subject_ids=["test_president"],
            era_filter="1950",
        )
        summary = run_jobs(jobs, output_size=(600, 750), force=True)

        assert summary.generated == 1
        assert variant_path.read_bytes() != b""

    def test_missing_original_is_handled_without_crashing_batch(
        self, president_service, style_service
    ):
        president_service.presidents_by_id = {
            "missing_president": {
                "id": "missing_president",
                "name": "Missing President",
                "presidentNumbers": [98],
                "originalImage": "images/people/presidents/originals/missing_president.png",
            }
        }
        president_service.terms = [
            {
                "presidentId": "missing_president",
                "dateFrom": "1969-01-20",
                "dateTo": "1974-08-08",
            }
        ]

        jobs, warnings = build_president_jobs(
            president_service,
            style_service,
            subject_ids=["missing_president"],
        )

        assert jobs == []
        assert warnings == ["[MISSING ORIGINAL] missing_president"]

    def test_status_reports_coverage(self, president_service, style_service):
        report = collect_president_status(president_service, style_service)

        assert report["category"] == "presidents"
        assert report["presidents_found"] == 14
        assert isinstance(report["required_variants"], list)
        assert isinstance(report["existing_variants"], list)
        assert isinstance(report["missing_variants"], list)

    def test_dry_run_does_not_write_files(
        self, tmp_path, president_service, style_service
    ):
        president_service.static_root = tmp_path
        original_relative = "images/people/presidents/originals/test_president.png"
        variant_relative = "images/people/presidents/variants/1970/test_president.png"
        original_path = tmp_path / original_relative
        variant_path = tmp_path / variant_relative
        original_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (600, 750), color=(120, 100, 80)).save(original_path)

        president_service.presidents_by_id = {
            "test_president": {
                "id": "test_president",
                "name": "Test President",
                "presidentNumbers": [99],
                "originalImage": original_relative,
            }
        }
        president_service.terms = [
            {
                "presidentId": "test_president",
                "dateFrom": "1969-01-20",
                "dateTo": "1974-08-08",
            }
        ]

        jobs, _warnings = build_president_jobs(
            president_service,
            style_service,
            subject_ids=["test_president"],
            era_filter="1970",
        )
        summary = run_jobs(jobs, output_size=(600, 750), dry_run=True)

        assert variant_path.exists() is False
        assert any("WOULD GENERATE" in message for message in summary.messages)

    def test_main_status_command(self, capsys):
        exit_code = main(["--category", "presidents", "--status"])
        captured = capsys.readouterr().out

        assert exit_code == 0
        assert "Presidents found: 14" in captured
        assert "Required variants:" in captured
