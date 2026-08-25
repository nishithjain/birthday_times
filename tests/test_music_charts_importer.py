"""Offline tests for music chart CSV ingestion."""

from pathlib import Path

from backend.importers.music_charts import normalize_row, read_rows


def test_normalize_valid_and_invalid_rows():
    row = normalize_row({"year": "1968", "rank": "1", "title": "Hey Jude", "artist": "The Beatles", "chart_name": "Year End", "chart_country": "US", "source": "fixture"})
    assert row["year"] == 1968
    assert row["rank"] == 1
    assert row["source"] == "fixture"
    assert normalize_row({"year": "bad", "rank": "1", "title": "Song", "artist": "Artist"}) is None
    assert normalize_row({"year": "1968", "rank": "0", "title": "Song", "artist": "Artist"}) is None
    assert normalize_row({"year": "1968", "rank": "1", "title": "", "artist": "Artist"}) is None


def test_csv_reader(tmp_path):
    path = tmp_path / "charts.csv"
    path.write_text("year,rank,title,artist\n1968,1,Hey Jude,The Beatles\n", encoding="utf-8")
    rows = list(read_rows(path))
    assert rows[0]["title"] == "Hey Jude"
