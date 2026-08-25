"""Generate era-specific newspaper illustration variants from clean masters.

Required eras for each illustration are derived automatically from the overlap
between the illustration's yearFrom/yearTo (illustrations.json) and each
newspaper style's yearFrom/yearTo (newspaper_styles.json). No illustration-to-era
mapping is hardcoded, and no variant paths are stored in illustrations.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from PIL import Image

from backend.services.illustration_service import variant_path_for
from backend.services.newspaper_style_service import NewspaperStyleService
from backend.tools.generate_image_variants import ranges_overlap, style_date_range
from backend.tools.illustration_processor import (
    derive_illustration_seed,
    process_newspaper_illustration,
)

GENERATOR_VERSION = 1


@dataclass
class IllustrationJob:
    """One illustration/era variant generation job."""

    illustration_id: str
    category: str
    era: str
    original_path: Path
    variant_path: Path
    variant_relative: str
    print_style: Dict[str, Any]
    seed: int


@dataclass
class GenerationSummary:
    """Aggregate results for a generation run."""

    required: int = 0
    generated: int = 0
    already_existed: int = 0
    missing_originals: int = 0
    failed: int = 0
    messages: List[str] = field(default_factory=list)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def static_root() -> Path:
    return project_root() / "backend" / "web" / "static"


def illustrations_data_file() -> Path:
    return project_root() / "backend" / "data" / "illustrations.json"


def load_illustrations(data_file: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load raw illustration metadata (id, category, path, yearFrom, yearTo)."""
    path = data_file or illustrations_data_file()
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or "illustrations" not in data:
        raise ValueError(f"Invalid illustrations file: {path}.")
    return list(data["illustrations"])


def illustration_date_range(
    illustration: Dict[str, Any],
    styles: Sequence[Dict[str, Any]],
) -> Tuple[date, date]:
    """Return the inclusive date range covered by an illustration's metadata."""
    min_year = min(style["yearFrom"] for style in styles)
    max_year = max(style["yearTo"] for style in styles)
    year_from = illustration.get("yearFrom")
    year_to = illustration.get("yearTo")
    start = date(year_from if year_from is not None else min_year, 1, 1)
    end = date(year_to if year_to is not None else max_year, 12, 31)
    return start, end


def required_eras_for_illustration(
    illustration: Dict[str, Any],
    styles: Sequence[Dict[str, Any]],
) -> List[str]:
    """Return style ids whose date ranges overlap the illustration's range."""
    start, end = illustration_date_range(illustration, styles)
    eras: List[str] = []
    for style in styles:
        style_start, style_end = style_date_range(style)
        if ranges_overlap(start, end, style_start, style_end):
            eras.append(style["id"])
    return sorted(eras, key=int)


def resolve_static_path(relative_path: str, root: Optional[Path] = None) -> Path:
    base = root if root is not None else static_root()
    return base / Path(relative_path)


def build_jobs(
    illustrations: Sequence[Dict[str, Any]],
    styles: Sequence[Dict[str, Any]],
    *,
    root: Path,
    subject_ids: Optional[Iterable[str]] = None,
    era_filter: Optional[str] = None,
) -> Tuple[List[IllustrationJob], List[str]]:
    """Build generation jobs and collect warnings (missing originals, etc.)."""
    warnings: List[str] = []
    jobs: List[IllustrationJob] = []
    styles_by_id = {style["id"]: style for style in styles}

    wanted = set(subject_ids) if subject_ids is not None else None

    for illustration in illustrations:
        illustration_id = illustration["id"]
        if wanted is not None and illustration_id not in wanted:
            continue

        original_relative = illustration["path"]
        original_path = resolve_static_path(original_relative, root)
        if not original_path.is_file():
            warnings.append(f"[MISSING ORIGINAL] {illustration_id}")
            continue

        required_eras = required_eras_for_illustration(illustration, styles)
        if era_filter is not None:
            if era_filter not in required_eras:
                warnings.append(f"[UNNECESSARY ERA] {illustration_id} / {era_filter}")
                continue
            required_eras = [era_filter]

        for era in required_eras:
            style = styles_by_id[era]
            variant_relative = variant_path_for(original_relative, era)
            jobs.append(
                IllustrationJob(
                    illustration_id=illustration_id,
                    category=illustration["category"],
                    era=era,
                    original_path=original_path,
                    variant_path=resolve_static_path(variant_relative, root),
                    variant_relative=variant_relative,
                    print_style=style["illustrationPrintStyle"],
                    seed=derive_illustration_seed(illustration_id, era),
                )
            )

    return jobs, warnings


def collect_status(
    illustrations: Sequence[Dict[str, Any]],
    styles: Sequence[Dict[str, Any]],
    *,
    root: Path,
) -> Dict[str, Any]:
    """Return a status report for illustration variants (no generation)."""
    originals_missing: List[str] = []
    required_variants: List[Dict[str, str]] = []
    existing_variants: List[Dict[str, str]] = []
    missing_variants: List[Dict[str, str]] = []

    for illustration in illustrations:
        illustration_id = illustration["id"]
        original_path = resolve_static_path(illustration["path"], root)
        if not original_path.is_file():
            originals_missing.append(illustration_id)

        for era in required_eras_for_illustration(illustration, styles):
            variant_relative = variant_path_for(illustration["path"], era)
            entry = {
                "id": illustration_id,
                "era": era,
                "path": variant_relative,
            }
            required_variants.append(entry)
            if resolve_static_path(variant_relative, root).is_file():
                existing_variants.append(entry)
            else:
                missing_variants.append(entry)

    return {
        "illustrations": len(illustrations),
        "originals_missing": originals_missing,
        "required_variants": required_variants,
        "existing_variants": existing_variants,
        "missing_variants": missing_variants,
    }


def validate_generated_variant(
    variant_path: Path,
    original_path: Path,
) -> Optional[str]:
    """Validate a generated variant. Return an error string, or None if valid."""
    if not variant_path.is_file():
        return "output file not created"
    if variant_path.stat().st_size == 0:
        return "zero-byte file"

    with Image.open(original_path) as original:
        original_size = original.size

    with Image.open(variant_path) as variant:
        variant.load()
        if variant.size != original_size:
            return f"dimensions changed {variant.size} != {original_size}"
        rgba = variant.convert("RGBA")

    alpha = rgba.getchannel("A")
    low, _high = alpha.getextrema()
    if low >= 255:
        return "no transparency (opaque background)"
    return None


def run_jobs(
    jobs: Sequence[IllustrationJob],
    *,
    dry_run: bool = False,
    force: bool = False,
) -> GenerationSummary:
    """Execute or simulate illustration variant generation jobs."""
    summary = GenerationSummary(required=len(jobs))

    for job in jobs:
        label = f"{job.illustration_id} / {job.era}"

        if job.variant_path.is_file() and not force:
            summary.already_existed += 1
            summary.messages.append(f"[SKIP EXISTING] {label}")
            continue

        if not job.original_path.is_file():
            summary.missing_originals += 1
            summary.messages.append(f"[MISSING ORIGINAL] {job.illustration_id}")
            continue

        if dry_run:
            if job.variant_path.is_file():
                summary.messages.append(f"[WOULD REPLACE] {label}")
            else:
                summary.messages.append(f"[WOULD GENERATE] {label}")
            continue

        try:
            process_newspaper_illustration(
                source_path=job.original_path,
                output_path=job.variant_path,
                print_style=job.print_style,
                seed=job.seed,
                style_id=job.era,
            )
            error = validate_generated_variant(job.variant_path, job.original_path)
            if error is not None:
                summary.failed += 1
                summary.messages.append(f"[FAILED] {label}: {error}")
                continue
            summary.generated += 1
            summary.messages.append(f"[GENERATED] {label}")
        except Exception as exc:  # pragma: no cover - defensive
            summary.failed += 1
            summary.messages.append(f"[FAILED] {label}: {exc}")

    return summary


def print_summary(summary: GenerationSummary) -> None:
    for message in summary.messages:
        print(message)
    print("")
    print(f"Required: {summary.required}")
    print(f"Generated: {summary.generated}")
    print(f"Existing/skipped: {summary.already_existed}")
    print(f"Missing originals: {summary.missing_originals}")
    print(f"Failed: {summary.failed}")


def print_status_report(report: Dict[str, Any]) -> None:
    print(f"Illustrations: {report['illustrations']}")
    print(f"Required variants: {len(report['required_variants'])}")
    print(f"Existing variants: {len(report['existing_variants'])}")
    print(f"Missing variants: {len(report['missing_variants'])}")
    print(f"Missing originals: {len(report['originals_missing'])}")
    print("")

    if report["originals_missing"]:
        print("Missing originals:")
        for illustration_id in report["originals_missing"]:
            print(f"  - {illustration_id}")
        print("")

    if report["missing_variants"]:
        print("[REQUIRED]")
        for entry in report["missing_variants"]:
            print(f"{entry['id']} / {entry['era']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate era-specific newspaper illustration variants.",
    )
    parser.add_argument("--id", dest="subject_id", help="Specific illustration id.")
    parser.add_argument("--era", help="Specific newspaper era/style id.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all illustrations.",
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

    style_service = NewspaperStyleService()
    styles = style_service.styles
    illustrations = load_illustrations()
    root = static_root()

    if args.status:
        report = collect_status(illustrations, styles, root=root)
        print_status_report(report)
        return 0

    if not args.all and not args.subject_id:
        parser.error("Specify --all or --id.")

    subject_ids = None if args.all else [args.subject_id]
    jobs, warnings = build_jobs(
        illustrations,
        styles,
        root=root,
        subject_ids=subject_ids,
        era_filter=args.era,
    )

    for warning in warnings:
        print(warning)

    summary = run_jobs(jobs, dry_run=args.dry_run, force=args.force)
    print_summary(summary)
    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
