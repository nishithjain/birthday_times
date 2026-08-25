"""Tests for president photo variant generation orchestration."""

import numpy as np
import pytest
from PIL import Image

from backend.services.newspaper_style_service import NewspaperStyleService
from backend.services.president_service import PresidentService
from backend.tools.generate_president_variants import (
    build_jobs,
    collect_status,
    main,
    required_era_map,
    run_jobs,
)
from backend.tools.generate_image_variants import required_eras_for_president
from backend.tools.president_photo_processor import derive_president_seed


@pytest.fixture
def president_service():
    return PresidentService()


@pytest.fixture
def style_service():
    return NewspaperStyleService()


def _make_president(service, president_id, date_from, date_to):
    original_relative = f"images/people/presidents/originals/{president_id}.png"
    service.presidents_by_id = {
        president_id: {
            "id": president_id,
            "name": president_id.replace("_", " ").title(),
            "presidentNumbers": [99],
            "originalImage": original_relative,
        }
    }
    service.terms = [
        {"presidentId": president_id, "dateFrom": date_from, "dateTo": date_to}
    ]
    return original_relative


def _write_portrait(path, color=(120, 90, 70)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (600, 750), color=color).save(path)


class TestRequiredEras:
    def test_eisenhower(self, president_service, style_service):
        eras = required_eras_for_president(
            "dwight_eisenhower", president_service.terms, style_service.styles
        )
        assert eras == ["1950", "1960"]

    def test_reagan(self, president_service, style_service):
        eras = required_eras_for_president(
            "ronald_reagan", president_service.terms, style_service.styles
        )
        assert eras == ["1980"]

    def test_obama(self, president_service, style_service):
        eras = required_eras_for_president(
            "barack_obama", president_service.terms, style_service.styles
        )
        assert eras == ["2005", "2010", "2015"]

    def test_required_era_map_has_names(self, president_service, style_service):
        mapping = required_era_map(president_service, style_service)
        assert mapping["ronald_reagan"]["name"] == "Ronald Reagan"
        assert mapping["ronald_reagan"]["eras"] == ["1980"]


class TestBuildJobs:
    def test_missing_original_warns_and_skips(self, president_service, style_service):
        _make_president(president_service, "ghost_prez", "1969-01-20", "1974-08-08")
        jobs, warnings = build_jobs(
            president_service, style_service, subject_ids=["ghost_prez"]
        )
        assert jobs == []
        assert warnings == ["[MISSING ORIGINAL] ghost_prez"]

    def test_unknown_president_warns(self, president_service, style_service):
        jobs, warnings = build_jobs(
            president_service, style_service, subject_ids=["does_not_exist"]
        )
        assert jobs == []
        assert warnings == ["[UNKNOWN PRESIDENT] does_not_exist"]

    def test_era_filter_outside_range_warns(
        self, tmp_path, president_service, style_service
    ):
        president_service.static_root = tmp_path
        original_relative = _make_president(
            president_service, "test_prez", "1981-01-20", "1989-01-19"
        )
        _write_portrait(tmp_path / original_relative)
        jobs, warnings = build_jobs(
            president_service,
            style_service,
            subject_ids=["test_prez"],
            era_filter="1950",
        )
        assert jobs == []
        assert warnings == ["[UNNECESSARY ERA] test_prez / 1950"]

    def test_builds_expected_jobs(self, tmp_path, president_service, style_service):
        president_service.static_root = tmp_path
        original_relative = _make_president(
            president_service, "test_prez", "1953-01-20", "1961-01-19"
        )
        _write_portrait(tmp_path / original_relative)
        jobs, warnings = build_jobs(
            president_service, style_service, subject_ids=["test_prez"]
        )
        assert warnings == []
        assert sorted(job.era for job in jobs) == ["1950", "1960"]
        assert jobs[0].seed == derive_president_seed("test_prez", jobs[0].era)


class TestRunJobs:
    def _setup(self, tmp_path, service, era, date_from="1953-01-20", date_to="1961-01-19"):
        service.static_root = tmp_path
        original_relative = _make_president(service, "test_prez", date_from, date_to)
        _write_portrait(tmp_path / original_relative)
        return original_relative

    def test_generates_variant(self, tmp_path, president_service, style_service):
        self._setup(tmp_path, president_service, "1950")
        jobs, _ = build_jobs(
            president_service, style_service, subject_ids=["test_prez"], era_filter="1950"
        )
        summary = run_jobs(jobs, output_size=(600, 750))
        assert summary.generated == 1
        variant = tmp_path / "images/people/presidents/variants/1950/test_prez.png"
        assert variant.is_file()
        assert Image.open(variant).size == (600, 750)

    def test_skips_existing_without_force(
        self, tmp_path, president_service, style_service
    ):
        self._setup(tmp_path, president_service, "1950")
        variant = tmp_path / "images/people/presidents/variants/1950/test_prez.png"
        _write_portrait(variant, color=(5, 5, 5))
        sentinel = variant.read_bytes()
        jobs, _ = build_jobs(
            president_service, style_service, subject_ids=["test_prez"], era_filter="1950"
        )
        summary = run_jobs(jobs, output_size=(600, 750), force=False)
        assert summary.already_existed == 1
        assert summary.generated == 0
        assert variant.read_bytes() == sentinel

    def test_force_regenerates(self, tmp_path, president_service, style_service):
        self._setup(tmp_path, president_service, "1950")
        variant = tmp_path / "images/people/presidents/variants/1950/test_prez.png"
        _write_portrait(variant, color=(5, 5, 5))
        sentinel = variant.read_bytes()
        jobs, _ = build_jobs(
            president_service, style_service, subject_ids=["test_prez"], era_filter="1950"
        )
        summary = run_jobs(jobs, output_size=(600, 750), force=True)
        assert summary.generated == 1
        assert variant.read_bytes() != sentinel

    def test_dry_run_writes_nothing(self, tmp_path, president_service, style_service):
        self._setup(tmp_path, president_service, "1960")
        jobs, _ = build_jobs(
            president_service, style_service, subject_ids=["test_prez"], era_filter="1960"
        )
        summary = run_jobs(jobs, output_size=(600, 750), dry_run=True)
        variant = tmp_path / "images/people/presidents/variants/1960/test_prez.png"
        assert not variant.exists()
        assert any("WOULD GENERATE" in message for message in summary.messages)

    def test_different_eras_produce_different_variants(
        self, tmp_path, president_service, style_service
    ):
        self._setup(tmp_path, president_service, "both")
        jobs, _ = build_jobs(
            president_service, style_service, subject_ids=["test_prez"]
        )
        run_jobs(jobs, output_size=(600, 750))
        v1950 = tmp_path / "images/people/presidents/variants/1950/test_prez.png"
        v1960 = tmp_path / "images/people/presidents/variants/1960/test_prez.png"
        a = np.asarray(Image.open(v1950).convert("RGB"), dtype=np.float32)
        b = np.asarray(Image.open(v1960).convert("RGB"), dtype=np.float32)
        assert np.abs(a - b).mean() > 1.0


class TestStatus:
    def test_collect_status_shape(self, president_service, style_service):
        report = collect_status(president_service, style_service)
        assert report["category"] == "presidents"
        assert report["presidents_found"] == 14
        assert isinstance(report["required_variants"], list)
        assert "ronald_reagan" in report["required_era_map"]

    def test_main_status_command(self, capsys):
        exit_code = main(["--status"])
        captured = capsys.readouterr().out
        assert exit_code == 0
        assert "Total presidents: 14" in captured
        assert "Ronald Reagan -> 1980" in captured
