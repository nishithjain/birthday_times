"""Generate era-specific newspaper-print variants of president photographs.

Model:

    ORIGINAL PRESIDENT PHOTO
            |
    process_president_photo (per-era photo treatment)
            |
    variants/<era>/<presidentId>.png
            |
    PresidentService / ChronicleService / template

The ORIGINAL photo is the source of truth. A president only needs variants for
eras in which that president can actually appear, computed from the overlap
between the president's term dates and each newspaper style's year range.

CLI examples:

    python -m backend.tools.generate_president_variants --status
    python -m backend.tools.generate_president_variants --all --dry-run
    python -m backend.tools.generate_president_variants --all
    python -m backend.tools.generate_president_variants --id ronald_reagan
    python -m backend.tools.generate_president_variants --id dwight_eisenhower --era 1950
    python -m backend.tools.generate_president_variants --id ronald_reagan --era 1980 --force
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from backend.services.newspaper_style_service import NewspaperStyleService
from backend.services.president_service import PresidentService
from backend.tools.generate_image_variants import (
    output_size_from_policy,
    required_eras_for_president,
    resolve_static_path,
)
from backend.tools.president_photo_processor import (
    derive_president_seed,
    process_president_photo,
)

GENERATOR_VERSION = 1


@dataclass
class PresidentVariantJob:
    """One president/era variant generation job."""

    president_id: str
    display_name: str
    era: str
    original_path: Path
    variant_path: Path
    variant_relative: str
    print_style: Dict[str, Any]
    seed: int


@dataclass
class GenerationSummary:
    """Aggregate results for a generation run."""

    required_variants: int = 0
    already_existed: int = 0
    generated: int = 0
    missing_originals: int = 0
    failed: int = 0
    messages: List[str] = field(default_factory=list)


def required_era_map(
    president_service: PresidentService,
    style_service: NewspaperStyleService,
) -> Dict[str, Dict[str, Any]]:
    """Map each president id to its display name and required era ids."""
    mapping: Dict[str, Dict[str, Any]] = {}
    for president_id, president in president_service.presidents_by_id.items():
        eras = required_eras_for_president(
            president_id,
            president_service.terms,
            style_service.styles,
        )
        mapping[president_id] = {"name": president["name"], "eras": eras}
    return mapping


def build_jobs(
    president_service: PresidentService,
    style_service: NewspaperStyleService,
    subject_ids: Optional[Iterable[str]] = None,
    era_filter: Optional[str] = None,
) -> Tuple[List[PresidentVariantJob], List[str]]:
    """Build generation jobs and collect warnings for missing/unknown subjects."""
    warnings: List[str] = []
    jobs: List[PresidentVariantJob] = []
    styles = style_service.styles
    presidents = president_service.presidents_by_id
    static = president_service.static_root

    selected_ids = list(subject_ids) if subject_ids else list(presidents.keys())
    for president_id in selected_ids:
        president = presidents.get(president_id)
        if president is None:
            warnings.append(f"[UNKNOWN PRESIDENT] {president_id}")
            continue

        original_relative = president["originalImage"]
        original_path = resolve_static_path(original_relative, static)
        if not original_path.is_file():
            warnings.append(f"[MISSING ORIGINAL] {president_id}")
            continue

        required_eras = required_eras_for_president(
            president_id,
            president_service.terms,
            styles,
        )
        if era_filter is not None:
            if era_filter not in required_eras:
                warnings.append(f"[UNNECESSARY ERA] {president_id} / {era_filter}")
                continue
            required_eras = [era_filter]

        for era in required_eras:
            style = next(style for style in styles if style["id"] == era)
            variant_relative = president_service.get_variant_image_path(
                president_id,
                era,
            )
            jobs.append(
                PresidentVariantJob(
                    president_id=president_id,
                    display_name=president["name"],
                    era=era,
                    original_path=original_path,
                    variant_path=resolve_static_path(variant_relative, static),
                    variant_relative=variant_relative,
                    print_style=style["printStyle"],
                    seed=derive_president_seed(president_id, era),
                )
            )

    return jobs, warnings


def run_jobs(
    jobs: Sequence[PresidentVariantJob],
    *,
    output_size: Tuple[int, int],
    dry_run: bool = False,
    force: bool = False,
) -> GenerationSummary:
    """Execute or simulate president variant generation jobs."""
    summary = GenerationSummary(required_variants=len(jobs))

    for job in jobs:
        label = f"{job.president_id} / {job.era}"
        if job.variant_path.is_file() and not force:
            summary.already_existed += 1
            summary.messages.append(f"[EXISTS] {label}")
            continue

        if not job.original_path.is_file():
            summary.missing_originals += 1
            summary.messages.append(f"[MISSING ORIGINAL] {job.president_id}")
            continue

        if dry_run:
            if job.variant_path.is_file():
                summary.messages.append(f"[WOULD REPLACE] {label}")
            else:
                summary.messages.append(f"[WOULD GENERATE] {label}")
            continue

        try:
            process_president_photo(
                source_path=job.original_path,
                output_path=job.variant_path,
                print_style=job.print_style,
                seed=job.seed,
                output_size=output_size,
                style_id=job.era,
            )
            summary.generated += 1
            summary.messages.append(f"[GENERATED] {label}")
        except Exception as exc:  # pragma: no cover - exercised via tests with mocks
            summary.failed += 1
            summary.messages.append(f"[FAILED] {label}: {exc}")

    return summary


def collect_status(
    president_service: PresidentService,
    style_service: NewspaperStyleService,
) -> Dict[str, Any]:
    """Return a coverage status report for president photo variants."""
    presidents = president_service.presidents_by_id
    originals_found: List[str] = []
    originals_missing: List[str] = []
    required_variants: List[Dict[str, str]] = []
    existing_variants: List[Dict[str, str]] = []
    missing_variants: List[Dict[str, str]] = []
    static = president_service.static_root

    for president_id, president in presidents.items():
        original_path = resolve_static_path(president["originalImage"], static)
        if original_path.is_file():
            originals_found.append(president_id)
        else:
            originals_missing.append(president_id)

        for era in required_eras_for_president(
            president_id,
            president_service.terms,
            style_service.styles,
        ):
            variant_relative = president_service.get_variant_image_path(
                president_id,
                era,
            )
            variant_path = resolve_static_path(variant_relative, static)
            entry = {"presidentId": president_id, "era": era, "path": variant_relative}
            required_variants.append(entry)
            if variant_path.is_file():
                existing_variants.append(entry)
            else:
                missing_variants.append(entry)

    return {
        "category": "presidents",
        "presidents_found": len(presidents),
        "originals_found": originals_found,
        "originals_missing": originals_missing,
        "required_variants": required_variants,
        "existing_variants": existing_variants,
        "missing_variants": missing_variants,
        "required_era_map": required_era_map(president_service, style_service),
    }


def print_summary(summary: GenerationSummary) -> None:
    for message in summary.messages:
        print(message)
    print("")
    print(f"Required variants: {summary.required_variants}")
    print(f"Already existed: {summary.already_existed}")
    print(f"Generated: {summary.generated}")
    print(f"Missing originals: {summary.missing_originals}")
    print(f"Failed: {summary.failed}")


def print_status_report(report: Dict[str, Any]) -> None:
    print("President photo variant status")
    print(f"Total presidents: {report['presidents_found']}")
    print(f"Originals found: {len(report['originals_found'])}")
    print(f"Originals missing: {len(report['originals_missing'])}")
    print(f"Required variants: {len(report['required_variants'])}")
    print(f"Existing variants: {len(report['existing_variants'])}")
    print(f"Missing variants: {len(report['missing_variants'])}")
    print("")

    print("Required eras per president:")
    for entry in report["required_era_map"].values():
        eras = ", ".join(entry["eras"]) if entry["eras"] else "(none)"
        print(f"  {entry['name']} -> {eras}")
    print("")

    if report["originals_missing"]:
        print("Missing originals:")
        for president_id in report["originals_missing"]:
            print(f"  - {president_id}")
        print("")

    if report["missing_variants"]:
        print("Missing required variants:")
        for entry in report["missing_variants"]:
            print(f"  - {entry['presidentId']} / {entry['era']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate era-specific newspaper-print president photo variants.",
    )
    parser.add_argument("--id", dest="subject_id", help="Specific president id.")
    parser.add_argument("--era", help="Specific newspaper era/style id.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all presidents.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without writing files.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing variant files.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Report variant coverage without generating files.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    president_service = PresidentService()
    style_service = NewspaperStyleService()
    output_size = output_size_from_policy(president_service.image_policy)

    if args.status:
        report = collect_status(president_service, style_service)
        print_status_report(report)
        return 0

    if not args.all and not args.subject_id:
        parser.error("Specify --all or --id (or use --status).")

    subject_ids = None if args.all else [args.subject_id]
    jobs, warnings = build_jobs(
        president_service,
        style_service,
        subject_ids=subject_ids,
        era_filter=args.era,
    )

    for warning in warnings:
        print(warning)

    summary = run_jobs(
        jobs,
        output_size=output_size,
        dry_run=args.dry_run,
        force=args.force,
    )
    print_summary(summary)
    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
