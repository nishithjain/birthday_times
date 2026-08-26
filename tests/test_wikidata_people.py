import json
import sqlite3
from datetime import date

import pytest

from backend.database import db
from backend.importers.wikidata_people import (
    WikidataPeopleImporter,
    birthday_buckets,
    build_query,
    normalize_occupation,
    parse_people,
    select_people,
)
from backend.models.person import FamousPerson
from backend.repositories.person_repository import PersonRepository


def binding(value, datatype=None):
    result = {"value": value}
    if datatype:
        result["datatype"] = datatype
    return result


def person_row(qid, name, birth, sitelinks, datatype="http://www.w3.org/2001/XMLSchema#dateTime"):
    return {
        "person": binding(f"http://www.wikidata.org/entity/{qid}"),
        "personLabel": binding(name, "http://www.w3.org/2001/XMLSchema#string"),
        "birthDate": binding(birth, datatype),
        "article": binding(f"https://en.wikipedia.org/wiki/{qid}"),
        "occupationLabel": binding("actor"),
        "description": binding("English description"),
        "sitelinks": binding(str(sitelinks), "http://www.w3.org/2001/XMLSchema#integer"),
    }


def test_parse_people_rejects_imprecise_dates_and_deduplicates_by_qid():
    data = {"results": {"bindings": [
        person_row("Q2", "Second", "1982-05-09T00:00:00Z", 20),
        person_row("Q1", "First", "1982-05-09T00:00:00Z", 100),
        person_row("Q1", "First Updated", "1982-05-09T00:00:00Z", 100),
        person_row("Q3", "Year Only", "1982-01-01T00:00:00Z", 500, "http://www.w3.org/2001/XMLSchema#gYear"),
        person_row("not-a-qid", "Invalid", "1982-05-09T00:00:00Z", 999),
    ]}}

    people = parse_people(data, month=5, day=9)

    assert [person.wikidata_id for person in people] == ["Q1", "Q2"]
    assert people[0].name == "First Updated"
    assert people[0].birth_date == date(1982, 5, 9)


def test_birthday_buckets_include_february_29_and_reject_invalid_dates():
    buckets = birthday_buckets()
    assert len(buckets) == 366
    assert (2, 29) in buckets
    assert birthday_buckets(2, 29) == [(2, 29)]
    with pytest.raises(ValueError):
        birthday_buckets(2, 30)


def test_query_uses_exact_birthday_filter():
    query = build_query(5, 9, 10)

    assert 'CONTAINS(STR(?birthDate), "-05-09T")' in query
    assert "wikibase:timePrecision" not in query
    assert "MONTH(?birthDate)" not in query
    assert "LIMIT 10" in query


@pytest.mark.parametrize("label, expected", [
    ("film actor", ("Actor", 1)),
    ("television actor", ("Actor", 1)),
    ("cricket player", ("Cricketer", 2)),
    ("physicist", ("Scientist", 3)),
    ("inventor", ("Inventor", 4)),
    ("entrepreneur", ("Entrepreneur", 5)),
    ("singer-songwriter", ("Singer", 6)),
    ("association football player", ("Footballer", 8)),
    ("basketball player", ("Basketball Player", 9)),
    ("tennis player", ("Tennis Player", 10)),
    ("painter", ("Artist", 11)),
    ("astronaut", ("Astronaut", 12)),
    ("novelist", ("Writer", 13)),
    ("musician", ("Musician", 14)),
    ("film director", ("Director", 15)),
])
def test_occupation_normalization(label, expected):
    assert normalize_occupation([label]) == expected


def test_occupation_precedence_and_safety():
    assert normalize_occupation(["singer", "musician"]) == ("Singer", 6)
    assert normalize_occupation(["actor", "film director"]) == ("Actor", 1)
    assert normalize_occupation(["tennis player", "athlete"]) == ("Athlete", 7)
    assert normalize_occupation(["American football player"]) == (None, None)
    assert normalize_occupation(["company director"]) == (None, None)
    assert normalize_occupation(["historian"]) == (None, None)


def test_select_people_softly_rewards_occupation_diversity():
    people = [
        FamousPerson(name=f"Actor {index}", birth_date=date(1980, 5, 9), wikidata_id=f"Q{index}", occupation="Actor", sitelinks=100 - index)
        for index in range(20)
    ] + [
        FamousPerson(name="Scientist", birth_date=date(1980, 5, 9), wikidata_id="Q101", occupation="Scientist", sitelinks=90),
        FamousPerson(name="Singer", birth_date=date(1980, 5, 9), wikidata_id="Q102", occupation="Singer", sitelinks=89),
        FamousPerson(name="Writer", birth_date=date(1980, 5, 9), wikidata_id="Q103", occupation="Writer", sitelinks=88),
    ]

    selected = select_people(people, 5)

    assert {person.occupation for person in selected} >= {"Actor", "Scientist", "Singer", "Writer"}


class FakeImporter(WikidataPeopleImporter):
    def __init__(self, people, checkpoint_path):
        super().__init__(session=type("Session", (), {"headers": {}})(), checkpoint_path=checkpoint_path, delay=0)
        self.people = people
        self.fetch_calls = []

    def fetch(self, month, day, limit):
        self.fetch_calls.append((month, day, limit))
        return list(self.people)


def sample_person(qid="Q1"):
    return FamousPerson(name="Sample", birth_date=date(1982, 5, 9), wikidata_id=qid)


def test_run_dry_run_does_not_write_or_checkpoint(tmp_path, monkeypatch):
    importer = FakeImporter([sample_person()], tmp_path / "checkpoint.json")
    saved = []
    monkeypatch.setattr(PersonRepository, "save", lambda people: saved.append(people))

    summary = importer.run([(5, 9)], limit=20, commit=False)

    assert summary["buckets_completed"] == 1
    assert not saved
    assert not (tmp_path / "checkpoint.json").exists()


def test_run_commit_saves_then_resumes_from_checkpoint(tmp_path, monkeypatch):
    importer = FakeImporter([sample_person()], tmp_path / "checkpoint.json")
    saved = []
    monkeypatch.setattr(PersonRepository, "save", lambda people: saved.append(people))

    first = importer.run([(5, 9), (2, 29)], limit=20, commit=True)
    second = importer.run([(5, 9), (2, 29)], limit=20, commit=True)

    assert first["buckets_completed"] == 2
    assert second["buckets_attempted"] == 0
    assert len(saved) == 2
    assert json.loads((tmp_path / "checkpoint.json").read_text()) == {"completed": ["02-29", "05-09"]}


def test_run_records_failure_and_continues(tmp_path, monkeypatch):
    importer = FakeImporter([sample_person()], tmp_path / "checkpoint.json")
    original_fetch = importer.fetch

    def fetch_with_one_failure(month, day, limit):
        if (month, day) == (1, 2):
            raise RuntimeError("temporary timeout")
        return original_fetch(month, day, limit)

    monkeypatch.setattr(importer, "fetch", fetch_with_one_failure)
    monkeypatch.setattr(PersonRepository, "save", lambda people: len(people))

    summary = importer.run([(1, 1), (1, 2), (1, 3)], limit=1, commit=True)

    assert summary["buckets_completed"] == 2
    assert summary["failed_buckets"] == ["01-02"]
    state = json.loads((tmp_path / "checkpoint.json").read_text())
    assert state["completed"] == ["01-01", "01-03"]
    assert state["failed"] == ["01-02"]


def test_repository_save_upserts_and_birthday_query_uses_iso_date(tmp_path, monkeypatch):
    database_path = tmp_path / "people.db"
    connection = sqlite3.connect(database_path)
    connection.executescript("""
        CREATE TABLE famous_people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            birth_date TEXT NOT NULL,
            death_date TEXT,
            occupation TEXT,
            country TEXT,
            description TEXT,
            wikidata_id TEXT NOT NULL UNIQUE,
            wikipedia_url TEXT,
            image_url TEXT,
            sitelinks INTEGER DEFAULT 0,
            notability_score INTEGER DEFAULT 5,
            source TEXT NOT NULL DEFAULT 'Wikidata',
            source_url TEXT,
            created_at TEXT,
            updated_at TEXT
        );
    """)
    connection.close()
    monkeypatch.setattr(db, "DATABASE_PATH", database_path)

    PersonRepository.save([sample_person()])
    PersonRepository.save([FamousPerson(name="Updated", birth_date=date(1982, 5, 9), wikidata_id="Q1", sitelinks=50)])
    people = PersonRepository.get_by_month_day(5, 9)

    assert len(people) == 1
    assert people[0].name == "Updated"
    assert people[0].sitelinks == 50
