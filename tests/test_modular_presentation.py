from pathlib import Path

from backend.web.app import app


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "backend" / "web" / "templates" / "chronicles"
CSS = ROOT / "backend" / "web" / "static" / "css" / "chronicles"


def test_modular_presentation_files_exist():
    sections = ["masthead", "weather", "arrival_president", "world_news", "famous_birthdays", "around_this_time", "movies", "music", "chinese_zodiac", "what_things_cost", "sports", "footer"]
    for section in sections:
        assert (TEMPLATES / "sections" / f"{section}.html").exists()
        assert (CSS / "sections" / ("arrival.css" if section == "arrival_president" else "zodiac.css" if section == "chinese_zodiac" else f"{section}.css")).exists()
    for page in ["weather", "arrival", "world_news", "famous_birthdays", "around_this_time", "movies", "music", "zodiac", "what_things_cost", "sports"]:
        assert list((TEMPLATES / "test_pages").glob(f"test_{page}*.html"))
    assert (TEMPLATES / "sections" / "eagle_logo.html").exists()
    assert (CSS / "sections" / "eagle_logo.css").exists()
    assert (TEMPLATES / "test_pages" / "test_eagle_logo.html").exists()
    assert (TEMPLATES / "test_pages" / "eagle_logo_review_runner.html").exists()
    assert (TEMPLATES / "sections" / "extra.html").exists()
    assert (CSS / "sections" / "extra.css").exists()
    assert (TEMPLATES / "test_pages" / "test_extra.html").exists()
    assert (TEMPLATES / "test_pages" / "extra_review_runner.html").exists()
    assert (TEMPLATES / "master" / "chronicle_master.html").exists()
    assert (CSS / "chronicle_master.css").exists()
    assert (TEMPLATES / "test_pages" / "weather_review_runner.html").exists()
    assert (TEMPLATES / "test_pages" / "test_masthead.html").exists()
    assert (TEMPLATES / "test_pages" / "masthead_review_runner.html").exists()
    assert (TEMPLATES / "test_pages" / "test_arrival.html").exists()
    assert (TEMPLATES / "test_pages" / "arrival_review_runner.html").exists()


def test_modular_development_routes_render():
    client = app.test_client()
    routes = ["chronicle-master", "sections/masthead", "sections/masthead-review", "sections/weather", "sections/weather-review", "sections/eagle-logo", "sections/eagle-logo-review", "sections/extra", "sections/extra-review", "sections/arrival", "sections/arrival-review", "sections/world-news", "sections/famous-birthdays", "sections/around-this-time", "sections/movies", "sections/music", "sections/zodiac", "sections/what-things-cost", "sections/sports"]
    for route in routes:
        response = client.get(f"/dev/{route}?date=1982-05-09&name=Nishith&city=Bengaluru")
        assert response.status_code == 200, route

    assert client.get("/dev/sections/extra?date=2000-02-29").status_code == 200


def test_chronicle_master_review_supplies_weather_city():
    response = app.test_client().get("/dev/chronicle-master-review")

    assert response.status_code == 200
    assert b"&city=Bengaluru" in response.data


def test_extra_ornaments_follow_newspaper_style_ids():
    client = app.test_client()
    expected = {
        1950: "★", 1960: "★", 1970: "✶", 1980: "✶", 1990: "◆",
        1995: "◆", 2000: "◆", 2005: "❖", 2010: "❖", 2015: "•", 2026: "•",
    }
    for year, ornament in expected.items():
        response = client.get(f"/dev/sections/extra?date={year}-05-09")
        assert response.status_code == 200
        assert response.data.count(ornament.encode("utf-8")) == 2


def test_extra_has_newspaper_callout_structure():
    response = app.test_client().get("/dev/sections/extra?date=1982-05-09")
    assert response.status_code == 200
    assert b'data-extra-style="1980"' in response.data
    assert b"extra-headline-rule" in response.data
    assert b"extra-divider" in response.data
    assert b"extra-special-line" in response.data
    assert b"extra-edition-line" in response.data
    assert b"extra-date" in response.data


def test_eagle_logo_era_boundaries_render_expected_assets():
    client = app.test_client()
    expected = {
        1969: "eagle.png", 1970: "eagle_globe.png", 1989: "eagle_globe.png",
        1990: "newspaper_globe.png", 2004: "newspaper_globe.png",
        2005: "circular_chronicle_seal.png", 2014: "circular_chronicle_seal.png",
        2015: "bc_logo.png", 2026: "bc_logo.png",
    }
    for year, filename in expected.items():
        response = client.get(f"/dev/sections/eagle-logo?date={year}-05-09")
        assert response.status_code == 200
        assert filename.encode() in response.data


def test_masthead_review_includes_all_date_cases_and_style_metadata():
    response = app.test_client().get("/dev/sections/masthead-review")
    assert response.status_code == 200
    assert b'"date": "1950-01-01"' in response.data
    assert b'"date": "2026-12-31"' in response.data
    assert b'"styleId": "1950"' in response.data
    assert b'"styleId": "2015"' in response.data
    assert b'"mastheadTitle": "The Birthday Times"' in response.data


def test_arrival_review_includes_dispatch_presentation_cases():
    response = app.test_client().get("/dev/sections/arrival-review")
    assert response.status_code == 200
    for label, artwork in (("Telegram", "telegram_1950.png"), ("Wire Service", "wire_globe_1960.png"),
                           ("News Press", "mimeograph_1970.png"), ("News Flash", "typewriter_1980.png"),
                           ("Computer Bulletin", "computer_1990.png"), ("News Alert", "pager_2000.png"),
                           ("Digital Dispatch", "ipad_2010.png"), ("News Update", "dispatch_badge_2015.png")):
        assert label.encode() in response.data
        assert artwork.encode() in response.data


def test_dispatch_artwork_uses_contain_without_legacy_blending():
    css = (CSS / "sections" / "arrival.css").read_text(encoding="utf-8")
    assert "max-width: 124px" in css
    assert "max-height: 80px" in css
    assert "object-fit: contain" in css
    assert "mix-blend-mode: multiply" not in css
    assert "width: 124px" in css
    assert "height: 80px" in css


def test_masthead_titles_follow_style_id_mapping():
    expected = {
        1950: "The Birthday Gazette", 1960: "The Birthday Gazette",
        1970: "The Birthday Chronicle", 1980: "The Birthday Chronicle",
        1990: "The Birthday Herald", 1995: "The Birthday Herald", 2000: "The Birthday Herald",
        2005: "The Birthday Edition", 2010: "The Birthday Edition", 2015: "The Birthday Times",
    }
    client = app.test_client()
    for year, title in expected.items():
        response = client.get(f"/dev/sections/masthead?date={year}-05-09")
        assert title.encode() in response.data


def test_masthead_title_preserves_requested_case():
    response = app.test_client().get("/dev/sections/masthead?date=1982-05-09")
    assert b"The Birthday Chronicle" in response.data
