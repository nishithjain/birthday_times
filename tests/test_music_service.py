"""Offline tests for MusicService."""

from datetime import date
import json

from backend.services.music_service import MusicService, english_list


TRACKS = [
    {"rank": 1, "title": "Hey Jude", "artist": "The Beatles"},
    {"rank": 2, "title": "Mrs. Robinson", "artist": "Simon & Garfunkel"},
    {"rank": 3, "title": "Song C", "artist": "Artist C"},
]


class Repository:
    @staticmethod
    def get_top_tracks(year, limit=5):
        return TRACKS[:limit]


class Illustrations:
    def get_for_category(self, category, year):
        return {"id": "jukebox"}

    def resolve_by_id(self, identifier, style):
        return {"id": identifier, "displayPath": f"images/illustrations/variants/{style}/music/jukebox.png"}


def test_song_lists_and_year_short():
    assert english_list(['"Song A"']) == '"Song A"'
    assert english_list(['"Song A"', '"Song B"']) == '"Song A" and "Song B"'
    assert english_list(['"Song A"', '"Song B"', '"Song C"']) == '"Song A", "Song B", and "Song C"'


def test_payload_and_deterministic_template(tmp_path):
    templates = tmp_path / "music.json"
    templates.write_text(json.dumps({"defaultTemplateId": "classic_01", "templates": [{
        "id": "classic_01", "headlineTemplate": "MUSIC, MUSIC, MUSIC", "subheadlineTemplate": "The Top Hits of '{yearShort}", "bodyTemplate": "{personFirstName}: {songList} in {year}"
    }]}), encoding="utf-8")
    service = MusicService(Repository, templates, Illustrations())
    result = service.get_music_for_year(1968, "Nishith", date(1968, 10, 16), "1960")
    assert result["available"] is True
    assert result["yearShort"] == "68"
    assert result["subheadline"] == "The Top Hits of '68"
    assert result["tracks"][0]["title"] == "Hey Jude"
    assert result["illustration"]["id"] == "jukebox"
    assert result["accuracyType"] == "year"
    assert service.get_music_for_year(1968, "Nishith", date(1968, 10, 16))["templateId"] == result["templateId"]


def test_missing_year_does_not_fabricate():
    class Empty:
        @staticmethod
        def get_top_tracks(year, limit=5):
            return []
    result = MusicService(Empty).get_music_for_year(2026)
    assert result == {"available": False, "year": 2026, "reason": "music_data_unavailable"}
