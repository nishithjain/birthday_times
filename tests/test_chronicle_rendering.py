"""Tests for era Chronicle template rendering."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.web.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


REPOSITORY_PATCHES = (
    "backend.services.chronicle_service.MovieRepository.get_by_year",
    "backend.services.chronicle_service.PersonRepository.get_by_birthday",
    "backend.services.chronicle_service.EventRepository.get_by_date",
)


def _patch_repositories(mock_get_events, mock_get_people, mock_get_movies):
    mock_get_events.return_value = []
    mock_get_people.return_value = []
    mock_get_movies.return_value = []


@pytest.mark.parametrize(
    ("birth_date", "expected_era", "expected_bg"),
    [
        ("1955-06-15", "1950", "1950.png"),
        ("1965-06-15", "1960", "1960.png"),
        ("1982-05-09", "1980", "1980.png"),
        ("1997-03-15", "1995", "1995.png"),
        ("2007-08-20", "2005", "2005.png"),
        ("2018-11-02", "2015", "2015.png"),
    ],
)
@patch(REPOSITORY_PATCHES[0])
@patch(REPOSITORY_PATCHES[1])
@patch(REPOSITORY_PATCHES[2])
def test_chronicle_renders_era_template(
    mock_get_events,
    mock_get_people,
    mock_get_movies,
    client,
    birth_date,
    expected_era,
    expected_bg,
):
    _patch_repositories(mock_get_events, mock_get_people, mock_get_movies)

    response = client.post(
        "/chronicle",
        data={"birth_date": birth_date, "country": "India", "name": "Alex"},
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "chronicle_master.css" in html
    assert f'<main class="chronicle-page" data-era="{expected_era}"' in html
    assert f"/static/images/newspaper/{expected_bg}" in html
    assert "chronicle_common.css" in html
    assert "WHAT THE WORLD WAS LIKE WHEN YOU WERE BORN" in html


@pytest.mark.parametrize(
    ("birth_date", "expected_president_name"),
    [
        ("1958-05-09", "DWIGHT D. EISENHOWER"),
        ("1960-05-09", "DWIGHT D. EISENHOWER"),
        ("1985-05-09", "RONALD REAGAN"),
        ("1997-05-09", "BILL CLINTON"),
        ("2007-05-09", "GEORGE W. BUSH"),
        ("2018-05-09", "DONALD TRUMP"),
    ],
)
@patch(REPOSITORY_PATCHES[0])
@patch(REPOSITORY_PATCHES[1])
@patch(REPOSITORY_PATCHES[2])
def test_chronicle_renders_president(
    mock_get_events,
    mock_get_people,
    mock_get_movies,
    client,
    birth_date,
    expected_president_name,
):
    _patch_repositories(mock_get_events, mock_get_people, mock_get_movies)

    response = client.post(
        "/chronicle",
        data={"birth_date": birth_date, "country": "India", "name": "Alex"},
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert expected_president_name.title() in html
    assert "From The White House" in html
    assert "/static/images/people/presidents/" in html


def test_templates_do_not_hardcode_illustration_paths():
    templates_root = Path("backend/web/templates")
    for template in templates_root.rglob("*.html"):
        text = template.read_text(encoding="utf-8")
        assert "images/illustrations/originals/" not in text, template


@pytest.mark.parametrize(
    ("birth_date", "expected_fragment"),
    [
        ("1955-06-15", "music/jukebox.png"),
        ("1965-06-15", "music/jukebox.png"),
        ("1985-05-09", "music/boombox.png"),
        ("1997-03-15", "world/globe.png"),
        ("2007-08-20", "world/globe.png"),
        ("2018-11-02", "world/globe.png"),
    ],
)
@patch(REPOSITORY_PATCHES[0])
@patch(REPOSITORY_PATCHES[1])
@patch(REPOSITORY_PATCHES[2])
def test_chronicle_renders_illustrations(
    mock_get_events,
    mock_get_people,
    mock_get_movies,
    client,
    birth_date,
    expected_fragment,
):
    _patch_repositories(mock_get_events, mock_get_people, mock_get_movies)

    response = client.post(
        "/chronicle",
        data={"birth_date": birth_date, "country": "India", "name": "Alex"},
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert expected_fragment in html
    assert "newspaper-illustration" in html
    if birth_date.startswith("2018"):
        assert "/static/images/illustrations/originals/masthead/eagle.png" not in html



@pytest.mark.parametrize(
    "birth_date",
    [
        "1955-06-15",
        "1965-06-15",
        "1985-05-09",
        "1997-03-15",
        "2007-08-20",
        "2018-11-02",
    ],
)
@patch(REPOSITORY_PATCHES[0])
@patch(REPOSITORY_PATCHES[1])
@patch(REPOSITORY_PATCHES[2])
def test_chronicle_illustration_paths_are_dynamic(
    mock_get_events,
    mock_get_people,
    mock_get_movies,
    client,
    birth_date,
):
    _patch_repositories(mock_get_events, mock_get_people, mock_get_movies)

    response = client.post(
        "/chronicle",
        data={"birth_date": birth_date, "country": "India", "name": "Alex"},
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "/static/images/illustrations/" in html
    assert "newspaper-illustration" in html
    assert "images/illustrations/originals/music/jukebox.png" not in open(
        "backend/web/templates/chronicles/_newspaper_main.html",
        encoding="utf-8",
    ).read()


@pytest.mark.parametrize(
    ("birth_date", "expected_era"),
    [
        ("1955-06-15", "1950"),
        ("1965-06-15", "1960"),
        ("1975-06-15", "1970"),
        ("1982-05-09", "1980"),
        ("1992-05-09", "1990"),
        ("1997-03-15", "1995"),
        ("2002-08-20", "2000"),
        ("2007-08-20", "2005"),
        ("2012-08-20", "2010"),
        ("2018-11-02", "2015"),
    ],
)
@patch(REPOSITORY_PATCHES[0])
@patch(REPOSITORY_PATCHES[1])
@patch(REPOSITORY_PATCHES[2])
def test_newspaper_page_exposes_selected_era(
    mock_get_events,
    mock_get_people,
    mock_get_movies,
    client,
    birth_date,
    expected_era,
):
    _patch_repositories(mock_get_events, mock_get_people, mock_get_movies)

    response = client.post(
        "/chronicle",
        data={"birth_date": birth_date, "country": "India", "name": "Alex"},
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "chronicle-page" in html
    assert f'data-era="{expected_era}"' in html


def test_submitted_chronicle_includes_print_control_but_export_does_not():
    client = app.test_client()
    submitted = client.post(
        "/chronicle",
        data={"birth_date": "1982-08-26", "country": "India", "name": "Alex"},
    )
    exported = client.get("/chronicle/export?date=1982-08-26")

    assert submitted.status_code == 200
    assert b"Print / Save PDF" in submitted.data
    assert exported.status_code == 200
    assert b"Print / Save PDF" not in exported.data


def test_illustration_filter_defined_for_every_style():
    styles = json.loads(
        Path("backend/data/newspaper_styles.json").read_text(encoding="utf-8")
    )
    css = Path(
        "backend/web/static/css/chronicles/chronicle_common.css"
    ).read_text(encoding="utf-8")

    for style in styles["styles"]:
        selector = f'[data-era="{style["id"]}"]'
        assert selector in css, selector

    assert "mix-blend-mode: multiply" in css
    assert "filter: var(--chronicle-illustration-filter)" in css
    assert "opacity: var(--chronicle-illustration-opacity)" in css
    assert ".chronicle-era-illustration" in css


def test_modular_decorative_art_uses_shared_era_class_and_president_is_a_photo():
    sections_root = Path("backend/web/templates/chronicles/sections")
    decorative_templates = (
        "weather.html",
        "eagle_logo.html",
        "arrival_president.html",
        "music.html",
        "chinese_zodiac.html",
        "bottom.html",
    )

    for template_name in decorative_templates:
        text = (sections_root / template_name).read_text(encoding="utf-8")
        assert "chronicle-era-illustration" in text

    arrival = (sections_root / "arrival_president.html").read_text(encoding="utf-8")
    president_index = arrival.index("arrival-president-photo")
    president_markup = arrival[max(0, president_index - 240):president_index + 240]
    assert "chronicle-era-photo" in president_markup
    assert "chronicle-era-illustration" not in president_markup


def test_famous_birthdays_fit_reserves_space_for_occupation_icons():
    app_source = Path("backend/web/static/js/app.js").read_text(encoding="utf-8")

    assert "hasIconForSelection" in app_source
    assert "iconReserve" in app_source
    assert "result.scrollHeight + iconReserve" in app_source
    assert "selectedPersonIndices" in app_source


def test_famous_birthdays_content_starts_40px_lower():
    css = Path(
        "backend/web/static/css/chronicles/sections/famous_birthdays.css"
    ).read_text(encoding="utf-8")

    assert "padding: 48px 10px 0" in css


def test_world_famous_divider_moves_with_famous_birthdays_content():
    css = Path("backend/web/static/css/chronicles/chronicle_master.css").read_text(
        encoding="utf-8"
    )

    assert ".master-world-famous .master-divider" in css
    assert "margin-top: 40px" in css

