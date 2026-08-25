"""Generate era-specific newspaper image variants from original photographs."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from backend.services.newspaper_style_service import NewspaperStyleService
from backend.services.president_service import PresidentService
from backend.tools.image_processor import derive_processing_seed, process_newspaper_photo

GENERATOR_VERSION = 1


@dataclass
class VariantJob:
    """One president/category variant generation job."""

    category: str
    subject_id: str
    era: str
    original_path: Path
    variant_path: Path
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


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def static_root() -> Path:
    return project_root() / "backend" / "web" / "static"


def ranges_overlap(
    first_start: date,
    first_end: date,
    second_start: date,
    second_end: date,
) -> bool:
    """Return True when two inclusive date ranges overlap."""
    return first_start <= second_end and first_end >= second_start


def style_date_range(style: Dict[str, Any]) -> Tuple[date, date]:
    """Return the inclusive date range covered by a newspaper style."""
    return date(style["yearFrom"], 1, 1), date(style["yearTo"], 12, 31)


def term_date_range(
    term: Dict[str, Any],
    open_era_end: date,
) -> Tuple[date, date]:
    """Return the inclusive date range covered by a presidential term."""
    term_start = date.fromisoformat(term["dateFrom"])
    term_end = (
        date.fromisoformat(term["dateTo"])
        if term.get("dateTo")
        else open_era_end
    )
    return term_start, term_end


def required_eras_for_term(
    term: Dict[str, Any],
    styles: Sequence[Dict[str, Any]],
    open_era_end: date,
) -> List[str]:
    """Return style ids whose date ranges overlap a presidential term."""
    term_start, term_end = term_date_range(term, open_era_end)
    eras: List[str] = []

    for style in styles:
        style_start, style_end = style_date_range(style)
        if ranges_overlap(term_start, term_end, style_start, style_end):
            eras.append(style["id"])

    return eras


def required_eras_for_president(
    president_id: str,
    terms: Sequence[Dict[str, Any]],
    styles: Sequence[Dict[str, Any]],
) -> List[str]:
    """Return sorted required era ids for one president based on term overlap."""
    open_era_end = date(max(style["yearTo"] for style in styles), 12, 31)
    president_terms = [term for term in terms if term["presidentId"] == president_id]
    eras = set()

    for term in president_terms:
        eras.update(required_eras_for_term(term, styles, open_era_end))

    return sorted(eras, key=int)


def resolve_static_path(relative_path: str, root: Optional[Path] = None) -> Path:
    base = root if root is not None else static_root()
    return base / Path(relative_path)


def build_president_jobs(
    president_service: PresidentService,
    style_service: NewspaperStyleService,
    subject_ids: Optional[Iterable[str]] = None,
    era_filter: Optional[str] = None,
) -> Tuple[List[VariantJob], List[str]]:
    """Build generation jobs for presidents and collect missing-original warnings."""
    warnings: List[str] = []
    jobs: List[VariantJob] = []
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
                warnings.append(
                    f"[UNNECESSARY ERA] {president_id} / {era_filter}"
                )
                continue
            required_eras = [era_filter]

        for era in required_eras:
            style = next(style for style in styles if style["id"] == era)
            variant_relative = president_service.get_variant_image_path(
                president_id,
                era,
            )
            jobs.append(
                VariantJob(
                    category="presidents",
                    subject_id=president_id,
                    era=era,
                    original_path=original_path,
                    variant_path=resolve_static_path(variant_relative, static),
                    print_style=style["printStyle"],
                    seed=derive_processing_seed("presidents", president_id, era),
                )
            )

    return jobs, warnings


def collect_president_status(
    president_service: PresidentService,
    style_service: NewspaperStyleService,
) -> Dict[str, Any]:
    """Return a status report for president image variants."""
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
            entry = {
                "subjectId": president_id,
                "era": era,
                "path": variant_relative,
            }
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
    }


def output_size_from_policy(image_policy: Dict[str, Any]) -> Tuple[int, int]:
    return (
        int(image_policy.get("sourceWidth", 600)),
        int(image_policy.get("sourceHeight", 750)),
    )


def run_jobs(
    jobs: Sequence[VariantJob],
    *,
    output_size: Tuple[int, int],
    dry_run: bool = False,
    force: bool = False,
) -> GenerationSummary:
    """Execute or simulate variant generation jobs."""
    summary = GenerationSummary(required_variants=len(jobs))

    for job in jobs:
        label = f"{job.subject_id} / {job.era}"
        if job.variant_path.is_file() and not force:
            summary.already_existed += 1
            summary.messages.append(f"[EXISTS] {label}")
            continue

        if not job.original_path.is_file():
            summary.missing_originals += 1
            summary.messages.append(f"[MISSING ORIGINAL] {job.subject_id}")
            continue

        if dry_run:
            if job.variant_path.is_file():
                summary.messages.append(f"[WOULD REPLACE] {label}")
            else:
                summary.messages.append(f"[WOULD GENERATE] {label}")
            continue

        try:
            process_newspaper_photo(
                source_path=job.original_path,
                output_path=job.variant_path,
                print_style=job.print_style,
                output_size=output_size,
                seed=job.seed,
            )
            summary.generated += 1
            summary.messages.append(f"[GENERATED] {label}")
        except Exception as exc:  # pragma: no cover - exercised via tests with mocks
            summary.failed += 1
            summary.messages.append(f"[FAILED] {label}: {exc}")

    return summary


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
    print(f"Category: {report['category']}")
    print(f"Presidents found: {report['presidents_found']}")
    print(f"Originals found: {len(report['originals_found'])}")
    print(f"Originals missing: {len(report['originals_missing'])}")
    print(f"Required variants: {len(report['required_variants'])}")
    print(f"Variants already existing: {len(report['existing_variants'])}")
    print(f"Missing required variants: {len(report['missing_variants'])}")
    print("")

    if report["originals_missing"]:
        print("Missing originals:")
        for president_id in report["originals_missing"]:
            print(f"  - {president_id}")
        print("")

    if report["existing_variants"]:
        print("Existing variants:")
        for entry in report["existing_variants"]:
            print(f"  - {entry['subjectId']} / {entry['era']}")
        print("")

    if report["missing_variants"]:
        print("Missing required variants:")
        for entry in report["missing_variants"]:
            print(f"  - {entry['subjectId']} / {entry['era']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate era-specific newspaper image variants.",
    )
    parser.add_argument(
        "--category",
        choices=["presidents"],
        help="Image subject category to process.",
    )
    parser.add_argument("--id", dest="subject_id", help="Specific subject id.")
    parser.add_argument("--era", help="Specific newspaper era/style id.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all subjects in the category.",
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

    if args.category is None:
        parser.error("--category is required")

    president_service = PresidentService()
    style_service = NewspaperStyleService()
    output_size = output_size_from_policy(president_service.image_policy)

    if args.status:
        if args.category != "presidents":
            parser.error("Status is currently supported only for presidents.")
        report = collect_president_status(president_service, style_service)
        print_status_report(report)
        return 0

    if not args.all and not args.subject_id:
        parser.error("Specify --all or --id.")

    subject_ids = None if args.all else [args.subject_id]
    jobs, warnings = build_president_jobs(
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
