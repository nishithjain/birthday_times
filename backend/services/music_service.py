"""Offline year-level music chart presentation service."""

import hashlib
import json
import string
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

from backend.repositories.music_repository import MusicRepository
from backend.services.illustration_service import illustration_service

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SUPPORTED_PLACEHOLDERS = {"year", "yearShort", "songList", "personFirstName", "topSong", "topArtist"}


def english_list(values):
    values = [value for value in values if value]
    if len(values) < 2:
        return values[0] if values else ""
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def quote_title(title: str) -> str:
    return f'"{title}"'


class MusicService:
    def __init__(self, repository=MusicRepository, templates_path: Optional[Path] = None, illustration_service_=illustration_service):
        self.repository = repository
        self.templates_path = templates_path or DATA_DIR / "music_templates.json"
        self.illustration_service = illustration_service_

    def _templates(self):
        payload = json.loads(self.templates_path.read_text(encoding="utf-8"))
        templates = payload.get("templates", [])
        if not templates:
            raise ValueError("music templates must not be empty")
        ids = set()
        for template in templates:
            if template.get("id") in ids or any(not template.get(field) for field in ("id", "headlineTemplate", "subheadlineTemplate", "bodyTemplate")):
                raise ValueError("music templates require unique IDs and required fields")
            ids.add(template["id"])
            for field in ("headlineTemplate", "subheadlineTemplate", "bodyTemplate"):
                fields = {name for _, name, _, _ in string.Formatter().parse(template[field]) if name}
                if fields - SUPPORTED_PLACEHOLDERS:
                    raise ValueError(f"unsupported music placeholder(s): {fields - SUPPORTED_PLACEHOLDERS}")
        if payload.get("defaultTemplateId") not in ids:
            raise ValueError("music default template is missing")
        return templates

    def _select_template(self, person_name: Optional[str], birth_date: Optional[date], year: int):
        templates = self._templates()
        name = " ".join((person_name or "").strip().casefold().split())
        birth_value = birth_date.isoformat() if birth_date else f"{year:04d}-01-01"
        seed = f"music-template|{name}|{birth_value}"
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        return templates[int.from_bytes(digest[:8], "big") % len(templates)]

    def get_music_for_year(self, year: int, person_name: Optional[str] = None, birth_date: Optional[date] = None, newspaper_style_id: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
        tracks = self.repository.get_top_tracks(year, limit=limit)
        if not tracks:
            return {"available": False, "year": int(year), "reason": "music_data_unavailable"}
        year = int(year)
        track_payload = [{"rank": item["rank"], "title": item["title"], "artist": item["artist"]} for item in tracks]
        song_list = english_list([quote_title(item["title"]) for item in track_payload])
        template = self._select_template(person_name, birth_date, year)
        first_name = (person_name or "").strip().split()[0] if (person_name or "").strip() else "there"
        values = {"year": year, "yearShort": f"{year % 100:02d}", "songList": song_list, "personFirstName": first_name, "topSong": track_payload[0]["title"], "topArtist": track_payload[0]["artist"]}
        illustration = self.illustration_service.get_for_category("music", year) if self.illustration_service else None
        resolved = self.illustration_service.resolve_by_id(illustration["id"], newspaper_style_id) if illustration and self.illustration_service else None
        body_candidates = []
        for mention_limit in (5, 4, 3):
            candidate_values = dict(values, songList=english_list([quote_title(item["title"]) for item in track_payload[:mention_limit]]))
            body_candidates.append({"mentionLimit": mention_limit, "bodyText": template["bodyTemplate"].format(**candidate_values)})
        return {"available": True, "year": year, "yearShort": values["yearShort"], "templateId": template["id"], "headline": template["headlineTemplate"].format(**values), "subheadline": template["subheadlineTemplate"].format(**values), "tracks": track_payload, "songList": song_list, "bodyText": body_candidates[0]["bodyText"], "bodyCandidates": body_candidates, "illustrationId": illustration["id"] if illustration else None, "illustration": resolved, "accuracyType": "year"}


music_service = MusicService()
