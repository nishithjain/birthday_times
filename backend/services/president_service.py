"""U.S. president lookup and image path resolution."""

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional


class PresidentService:
    """Load president metadata and resolve portrait image paths."""

    def __init__(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        data_file = project_root / "backend" / "data" / "us_presidents.json"
        static_root = project_root / "backend" / "web" / "static"

        with data_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if "presidents" not in data or not data["presidents"]:
            raise ValueError(
                f"Invalid presidents file: {data_file}. "
                "Expected a non-empty 'presidents' array."
            )
        if "terms" not in data or not data["terms"]:
            raise ValueError(
                f"Invalid presidents file: {data_file}. "
                "Expected a non-empty 'terms' array."
            )

        self.image_policy: Dict[str, Any] = data.get("imagePolicy", {})
        self.presidents_by_id: Dict[str, Dict[str, Any]] = {
            president["id"]: president for president in data["presidents"]
        }
        self.terms = data["terms"]
        self.static_root = static_root
        self._variant_pattern = self.image_policy.get(
            "variantPathPattern",
            "images/people/presidents/variants/{era}/{presidentId}.png",
        )

    def get_president_for_date(self, target_date: date) -> Dict[str, Any]:
        """Return president metadata for the given calendar date."""
        term = self._find_term_for_date(target_date)
        president = self.presidents_by_id[term["presidentId"]]
        return dict(president)

    def get_variant_image_path(self, president_id: str, era: str) -> str:
        """Return the static-relative variant image path for an era."""
        return self._variant_pattern.format(era=era, presidentId=president_id)

    def resolve_president_image(
        self,
        president_id: str,
        era: str,
    ) -> Dict[str, Any]:
        """Return original, variant, and display image paths for a president.

        The ORIGINAL photo is the source of truth. The auto-generated era
        variant is preferred when present; otherwise we fall back to the
        original. ``usingVariant`` records which one is being displayed.

        Both the legacy image field names (``originalImage`` / ``variantImage``
        / ``displayImage``) and the newer path field names (``originalPath`` /
        ``variantPath`` / ``displayPath``) are returned so callers and tests can
        use either without breaking.
        """
        president = self.presidents_by_id[president_id]
        original_image = president["originalImage"]
        variant_image = self.get_variant_image_path(president_id, era)

        variant_exists = self._static_file_exists(variant_image)
        original_exists = self._static_file_exists(original_image)

        if variant_exists:
            display_image: Optional[str] = variant_image
        elif original_exists:
            display_image = original_image
        else:
            display_image = None

        using_variant = variant_exists and display_image == variant_image

        return {
            "id": president["id"],
            "name": president["name"],
            "displayName": president["name"],
            "presidentNumbers": president["presidentNumbers"],
            "originalImage": original_image,
            "variantImage": variant_image,
            "displayImage": display_image,
            "originalPath": original_image,
            "variantPath": variant_image if variant_exists else None,
            "displayPath": display_image,
            "usingVariant": using_variant,
        }

    def resolve_president_for_date(
        self,
        target_date: date,
        era: str,
    ) -> Dict[str, Any]:
        """Return president metadata and resolved image paths for a date and era."""
        president = self.get_president_for_date(target_date)
        image_paths = self.resolve_president_image(president["id"], era)
        return {
            **president,
            **image_paths,
        }

    def _find_term_for_date(self, target_date: date) -> Dict[str, Any]:
        for term in self.terms:
            date_from = date.fromisoformat(term["dateFrom"])
            date_to = (
                date.fromisoformat(term["dateTo"])
                if term.get("dateTo")
                else None
            )

            if target_date < date_from:
                continue
            if date_to is not None and target_date > date_to:
                continue
            return term

        raise ValueError(f"No presidential term found for {target_date.isoformat()}")

    def _static_file_exists(self, static_relative_path: str) -> bool:
        file_path = self.static_root / Path(static_relative_path)
        return file_path.is_file()


president_service = PresidentService()
