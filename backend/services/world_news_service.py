"""Offline loader for generated yearly world-news datasets."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class WorldNewsService:
    """Load and cache generated world-news JSON files."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = data_dir or Path(__file__).resolve().parents[1] / "data" / "world_news"
        self._cache: Dict[int, Optional[Dict[str, Any]]] = {}

    def get_world_news(self, year: int, limit: Optional[int] = 5) -> Optional[Dict[str, Any]]:
        """Return stored headlines for ``year``, or None when unavailable/invalid."""
        try:
            year = int(year)
            if not 1 <= year <= 9999:
                return None
            limit = None if limit is None else max(0, int(limit))
        except (TypeError, ValueError):
            return None
        if year not in self._cache:
            path = self.data_dir / f"{year:04d}.json"
            try:
                with path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                if not isinstance(payload, dict) or not isinstance(payload.get("headlines"), list):
                    raise ValueError("world-news payload must contain a headlines list")
                self._cache[year] = payload
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                logger.debug("Could not load world news for %s: %s", year, exc)
                self._cache[year] = None
        payload = self._cache[year]
        if payload is None:
            return None
        result = dict(payload)
        result["headlines"] = list(payload["headlines"] if limit is None else payload["headlines"][:limit])
        result["candidates"] = list(payload["headlines"])
        return result


world_news_service = WorldNewsService()