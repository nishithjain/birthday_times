"""Tests for ChronicleService president integration."""

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from backend.services.accuracy import EXACT_DATE, YEAR
from backend.services.chronicle_service import ChronicleService
from backend.services.president_service import PresidentService
from backend.models.event import HistoricalEvent


REPOSITORY_PATCHES = (
    "backend.services.chronicle_service.MovieRepository.get_by_year",
    "backend.services.chronicle_service.PersonRepository.get_by_birthday",
    "backend.services.chronicle_service.EventRepository.get_by_date",
)


def _patch_repositories(mock_get_events, mock_get_people, mock_get_movies):
    mock_get_events.return_value = []
    mock_get_people.return_value = []
    mock_get_movies.return_value = []


class TestChronicleServicePresident:
    """Test president integration in ChronicleService."""

    @pytest.mark.parametrize(
        ("birth_date", "expected_id", "expected_name"),
        [
            (date(1950, 5, 9), "harry_s_truman", "Harry S. Truman"),
            (date(1958, 5, 9), "dwight_eisenhower", "Dwight D. Eisenhower"),
            (date(1960, 5, 9), "dwight_eisenhower", "Dwight D. Eisenhower"),
            (date(1962, 5, 9), "john_f_kennedy", "John F. Kennedy"),
            (date(1975, 5, 9), "gerald_ford", "Gerald Ford"),
            (date(1985, 5, 9), "ronald_reagan", "Ronald Reagan"),
            (date(1997, 5, 9), "bill_clinton", "Bill Clinton"),
            (date(2007, 5, 9), "george_w_bush", "George W. Bush"),
            (date(2012, 5, 9), "barack_obama", "Barack Obama"),
            (date(2018, 5, 9), "donald_trump", "Donald Trump"),
            (date(2023, 5, 9), "joe_biden", "Joe Biden"),
            (date(2026, 5, 9), "donald_trump", "Donald Trump"),
        ],
    )
    @patch(REPOSITORY_PATCHES[0])
    @patch(REPOSITORY_PATCHES[1])
    @patch(REPOSITORY_PATCHES[2])
    def test_president_lookup_by_birth_date(
        self,
        mock_get_events,
        mock_get_people,
        mock_get_movies,
        birth_date,
        expected_id,
        expected_name,
    ):
        _patch_repositories(mock_get_events, mock_get_people, mock_get_movies)
        chronicle = ChronicleService.generate_chronicle(birth_date=birth_date)

        assert chronicle["president"]["id"] == expected_id
        assert chronicle["president"]["name"] == expected_name
        assert chronicle["has_president"] is True
        assert chronicle["accuracy"]["president"] == EXACT_DATE

    @pytest.mark.parametrize(
        ("birth_date", "expected_id"),
        [
            (date(1953, 1, 19), "harry_s_truman"),
            (date(1953, 1, 20), "dwight_eisenhower"),
            (date(1961, 1, 19), "dwight_eisenhower"),
            (date(1961, 1, 20), "john_f_kennedy"),
            (date(1963, 11, 21), "john_f_kennedy"),
            (date(1963, 11, 22), "lyndon_b_johnson"),
            (date(1974, 8, 8), "richard_nixon"),
            (date(1974, 8, 9), "gerald_ford"),
            (date(2021, 1, 19), "donald_trump"),
            (date(2021, 1, 20), "joe_biden"),
            (date(2025, 1, 19), "joe_biden"),
            (date(2025, 1, 20), "donald_trump"),
        ],
    )
    @patch(REPOSITORY_PATCHES[0])
    @patch(REPOSITORY_PATCHES[1])
    @patch(REPOSITORY_PATCHES[2])
    def test_president_transition_dates(
        self,
        mock_get_events,
        mock_get_people,
        mock_get_movies,
        birth_date,
        expected_id,
    ):
        _patch_repositories(mock_get_events, mock_get_people, mock_get_movies)
        chronicle = ChronicleService.generate_chronicle(birth_date=birth_date)

        assert chronicle["president"]["id"] == expected_id

    @patch(REPOSITORY_PATCHES[0])
    @patch(REPOSITORY_PATCHES[1])
    @patch(REPOSITORY_PATCHES[2])
    def test_1958_uses_style_1950_variant(
        self,
        mock_get_events,
        mock_get_people,
        mock_get_movies,
    ):
        _patch_repositories(mock_get_events, mock_get_people, mock_get_movies)
        chronicle = ChronicleService.generate_chronicle(birth_date=date(1958, 5, 9))

        assert chronicle["newspaper_style"]["id"] == "1950"
        assert chronicle["president"]["id"] == "dwight_eisenhower"
        assert "variants/1950/dwight_eisenhower.png" in chronicle["president"]["variantImage"]

    @patch(REPOSITORY_PATCHES[0])
    @patch(REPOSITORY_PATCHES[1])
    @patch(REPOSITORY_PATCHES[2])
    def test_1960_uses_style_1960_variant(
        self,
        mock_get_events,
        mock_get_people,
        mock_get_movies,
    ):
        _patch_repositories(mock_get_events, mock_get_people, mock_get_movies)
        chronicle = ChronicleService.generate_chronicle(birth_date=date(1960, 5, 9))

        assert chronicle["newspaper_style"]["id"] == "1960"
        assert chronicle["president"]["id"] == "dwight_eisenhower"
        assert "variants/1960/dwight_eisenhower.png" in chronicle["president"]["variantImage"]

    @patch(REPOSITORY_PATCHES[0])
    @patch(REPOSITORY_PATCHES[1])
    @patch(REPOSITORY_PATCHES[2])
    def test_variant_preferred_when_present(
        self,
        mock_get_events,
        mock_get_people,
        mock_get_movies,
        tmp_path,
    ):
        _patch_repositories(mock_get_events, mock_get_people, mock_get_movies)
        service = PresidentService()
        service.static_root = tmp_path

        president = service.presidents_by_id["dwight_eisenhower"]
        original_path = tmp_path / president["originalImage"]
        variant_path = tmp_path / service.get_variant_image_path(
            "dwight_eisenhower",
            "1950",
        )
        original_path.parent.mkdir(parents=True, exist_ok=True)
        variant_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (600, 750), color=(100, 100, 100)).save(original_path)
        Image.new("RGB", (600, 750), color=(20, 20, 20)).save(variant_path)

        with patch(
            "backend.services.chronicle_service.president_service",
            service,
        ):
            chronicle = ChronicleService.generate_chronicle(birth_date=date(1958, 5, 9))

        assert chronicle["president"]["displayImage"] == chronicle["president"]["variantImage"]

    @patch(REPOSITORY_PATCHES[0])
    @patch(REPOSITORY_PATCHES[1])
    @patch(REPOSITORY_PATCHES[2])
    def test_president_payload_exposes_display_path(
        self,
        mock_get_events,
        mock_get_people,
        mock_get_movies,
        tmp_path,
    ):
        _patch_repositories(mock_get_events, mock_get_people, mock_get_movies)
        service = PresidentService()
        service.static_root = tmp_path

        president = service.presidents_by_id["dwight_eisenhower"]
        original_path = tmp_path / president["originalImage"]
        variant_path = tmp_path / service.get_variant_image_path(
            "dwight_eisenhower",
            "1950",
        )
        original_path.parent.mkdir(parents=True, exist_ok=True)
        variant_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (600, 750), color=(100, 100, 100)).save(original_path)
        Image.new("RGB", (600, 750), color=(20, 20, 20)).save(variant_path)

        with patch(
            "backend.services.chronicle_service.president_service",
            service,
        ):
            chronicle = ChronicleService.generate_chronicle(birth_date=date(1958, 5, 9))

        payload = chronicle["president"]
        assert payload["displayName"] == "Dwight D. Eisenhower"
        assert payload["usingVariant"] is True
        assert payload["displayPath"] == payload["variantPath"]
        assert "variants/1950/dwight_eisenhower.png" in payload["displayPath"]

    @patch(REPOSITORY_PATCHES[0])
    @patch(REPOSITORY_PATCHES[1])
    @patch(REPOSITORY_PATCHES[2])
    def test_original_fallback_when_variant_missing(
        self,
        mock_get_events,
        mock_get_people,
        mock_get_movies,
        tmp_path,
    ):
        _patch_repositories(mock_get_events, mock_get_people, mock_get_movies)
        service = PresidentService()
        service.static_root = tmp_path

        president = service.presidents_by_id["barack_obama"]
        original_path = tmp_path / president["originalImage"]
        original_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (600, 750), color=(120, 120, 120)).save(original_path)

        with patch(
            "backend.services.chronicle_service.president_service",
            service,
        ):
            chronicle = ChronicleService.generate_chronicle(birth_date=date(2012, 5, 9))

        assert chronicle["president"]["displayImage"] == chronicle["president"]["originalImage"]

    @patch(REPOSITORY_PATCHES[0])
    @patch(REPOSITORY_PATCHES[1])
    @patch(REPOSITORY_PATCHES[2])
    def test_no_display_image_when_both_missing(
        self,
        mock_get_events,
        mock_get_people,
        mock_get_movies,
        tmp_path,
    ):
        _patch_repositories(mock_get_events, mock_get_people, mock_get_movies)
        service = PresidentService()
        service.static_root = tmp_path

        with patch(
            "backend.services.chronicle_service.president_service",
            service,
        ):
            chronicle = ChronicleService.generate_chronicle(birth_date=date(2012, 5, 9))

        assert chronicle["president"]["displayImage"] is None


class TestChronicleServiceAccuracy:
    """Test ChronicleService accuracy metadata without database data."""

    @patch(REPOSITORY_PATCHES[0])
    @patch(REPOSITORY_PATCHES[1])
    @patch(REPOSITORY_PATCHES[2])
    def test_accuracy_metadata_without_data(
        self,
        mock_get_events,
        mock_get_people,
        mock_get_movies,
    ):
        birth_date = date(1982, 5, 9)
        chronicle = ChronicleService.generate_chronicle(birth_date=birth_date, name="Alex")

        accuracy = chronicle["accuracy"]
        assert accuracy["person"] == EXACT_DATE
        assert accuracy["calendar"] == EXACT_DATE
        assert accuracy["famous_birthdays"] == EXACT_DATE
        assert accuracy["historical_events"] == EXACT_DATE
        assert accuracy["movies"] == YEAR
        assert accuracy["newspaper_style"] == YEAR
        assert accuracy["what_things_cost"] == YEAR
        assert accuracy["president"] == EXACT_DATE
        assert "fun_facts" not in accuracy
        assert "illustrations" not in accuracy

    @patch("backend.services.chronicle_service.arrival_message_service.get_arrival")
    @patch(REPOSITORY_PATCHES[0])
    @patch(REPOSITORY_PATCHES[1])
    @patch(REPOSITORY_PATCHES[2])
    def test_arrival_payload_uses_newspaper_era(
        self,
        mock_get_events,
        mock_get_people,
        mock_get_movies,
        mock_get_arrival,
    ):
        _patch_repositories(mock_get_events, mock_get_people, mock_get_movies)
        mock_get_arrival.return_value = {"available": True, "era": "1980", "templateId": "1980_classic_01", "bodyText": "Era-specific arrival."}
        chronicle = ChronicleService.generate_chronicle(date(1982, 5, 9), name="Nishith")
        assert chronicle["arrival"]["era"] == "1980"
        assert chronicle["arrival"]["templateId"].startswith("1980_")
        assert chronicle["arrival"]["bodyText"] == "Era-specific arrival."

    @patch("backend.services.chronicle_service.world_news_service.get_world_news")
    @patch(REPOSITORY_PATCHES[0])
    @patch(REPOSITORY_PATCHES[1])
    @patch(REPOSITORY_PATCHES[2])
    def test_world_news_is_year_level_and_keeps_candidates(
        self,
        mock_get_events,
        mock_get_people,
        mock_get_movies,
        mock_get_world_news,
    ):
        _patch_repositories(mock_get_events, mock_get_people, mock_get_movies)
        mock_get_world_news.return_value = {
            "year": 1982,
            "headlineTitle": "Making Headlines In 1982",
            "headlines": [{"displayText": f"Story {index}"} for index in range(8)],
        }

        chronicle = ChronicleService.generate_chronicle(birth_date=date(1982, 5, 9))

        assert chronicle["world_news"]["year"] == 1982
        assert len(chronicle["world_news"]["headlines"]) == 8
        assert chronicle["accuracy"]["world_news"] == YEAR
        assert chronicle["has_world_news"] is True

    @patch(REPOSITORY_PATCHES[0])
    @patch(REPOSITORY_PATCHES[1])
    @patch(REPOSITORY_PATCHES[2])
    def test_birthday_lead_story_is_personalized(
        self,
        mock_get_events,
        mock_get_people,
        mock_get_movies,
    ):
        chronicle = ChronicleService.generate_chronicle(
            birth_date=date(1982, 5, 9),
            name="Alex",
        )

        assert chronicle["lead_story"]["type"] == "birthday"
        assert chronicle["lead_story"]["accuracyType"] == "personalized"

    @patch(REPOSITORY_PATCHES[0])
    @patch(REPOSITORY_PATCHES[1])
    @patch(REPOSITORY_PATCHES[2])
    def test_historical_lead_story_is_exact_date(
        self,
        mock_get_events,
        mock_get_people,
        mock_get_movies,
    ):
        mock_get_events.return_value = [
            HistoricalEvent(
                event_date=date(1982, 5, 9),
                title="Major Event",
                description="Something important happened.",
                category="politics",
                country="India",
                wikidata_id="Q123",
                source="Wikidata",
                importance_score=8,
            )
        ]

        chronicle = ChronicleService.generate_chronicle(birth_date=date(1982, 5, 9))

        assert chronicle["lead_story"]["type"] == "historical"
        assert chronicle["lead_story"]["accuracyType"] == EXACT_DATE

    @patch(REPOSITORY_PATCHES[0])
    @patch(REPOSITORY_PATCHES[1])
    @patch(REPOSITORY_PATCHES[2])
    def test_future_section_placeholders(
        self,
        mock_get_events,
        mock_get_people,
        mock_get_movies,
    ):
        chronicle = ChronicleService.generate_chronicle(birth_date=date(2015, 3, 15))

        assert chronicle["near_events"] == []
        assert chronicle["year_news"] == []
        assert chronicle["music"] == []
        assert chronicle["sports"] == []
        assert chronicle["prices"] == []
        assert chronicle["has_near_events"] is False
        assert chronicle["has_music"] is False
        assert chronicle["has_sports"] is False
        assert chronicle["has_prices"] is False


class TestChronicleServiceIllustrations:
    """Test ChronicleService illustration payload."""

    @patch(REPOSITORY_PATCHES[0])
    @patch(REPOSITORY_PATCHES[1])
    @patch(REPOSITORY_PATCHES[2])
    def test_1955_classic_illustrations(
        self,
        mock_get_events,
        mock_get_people,
        mock_get_movies,
    ):
        chronicle = ChronicleService.generate_chronicle(birth_date=date(1955, 6, 15))
        illustrations = chronicle["illustrations"]

        assert illustrations["masthead"]["id"] == "eagle"
        assert illustrations["world"]["id"] == "globe"
        assert illustrations["music"]["id"] == "jukebox"
        masthead = illustrations["masthead"]
        assert masthead["originalPath"] == "images/illustrations/originals/masthead/eagle.png"
        assert masthead["displayPath"].startswith("images/illustrations/")
        assert masthead["displayPath"].endswith("masthead/eagle.png")
        assert masthead["path"] == masthead["displayPath"]
        assert "\\" not in masthead["displayPath"]
        assert "illustrations" not in chronicle["accuracy"]

    @patch(REPOSITORY_PATCHES[0])
    @patch(REPOSITORY_PATCHES[1])
    @patch(REPOSITORY_PATCHES[2])
    def test_1985_music_is_boombox(
        self,
        mock_get_events,
        mock_get_people,
        mock_get_movies,
    ):
        chronicle = ChronicleService.generate_chronicle(birth_date=date(1985, 5, 9))
        assert chronicle["illustrations"]["music"]["id"] == "boombox"

    @patch(REPOSITORY_PATCHES[0])
    @patch(REPOSITORY_PATCHES[1])
    @patch(REPOSITORY_PATCHES[2])
    def test_2005_generic_technology_is_eligible(
        self,
        mock_get_events,
        mock_get_people,
        mock_get_movies,
    ):
        chronicle = ChronicleService.generate_chronicle(birth_date=date(2005, 8, 20))
        technology = chronicle["illustrations"]["technology"]
        assert technology is not None
        assert technology["id"] in {"computer", "mobile-phone", "mp3-player"}

    @patch(REPOSITORY_PATCHES[0])
    @patch(REPOSITORY_PATCHES[1])
    @patch(REPOSITORY_PATCHES[2])
    def test_tiger_year_uses_calendar_zodiac(
        self,
        mock_get_events,
        mock_get_people,
        mock_get_movies,
    ):
        birth_date = date(1950, 5, 9)
        chronicle = ChronicleService.generate_chronicle(birth_date=birth_date)

        from backend.services.calendar_service import CalendarService

        assert CalendarService.chinese_zodiac(birth_date) == "Tiger"
        assert chronicle["calendar"]["chinese_zodiac"] == "Tiger"
        assert chronicle["illustrations"]["zodiac"]["id"] == "tiger"
        assert chronicle["illustrations"]["zodiac"]["path"].endswith("zodiac/tiger.png")

    @patch(REPOSITORY_PATCHES[0])
    @patch(REPOSITORY_PATCHES[1])
    @patch(REPOSITORY_PATCHES[2])
    def test_2018_masthead_is_absent(
        self,
        mock_get_events,
        mock_get_people,
        mock_get_movies,
    ):
        chronicle = ChronicleService.generate_chronicle(birth_date=date(2018, 11, 2))
        assert chronicle["illustrations"]["masthead"] is None


    @patch(REPOSITORY_PATCHES[0])
    @patch(REPOSITORY_PATCHES[1])
    @patch(REPOSITORY_PATCHES[2])
    def test_existing_keys_remain_compatible(
        self,
        mock_get_events,
        mock_get_people,
        mock_get_movies,
    ):
        chronicle = ChronicleService.generate_chronicle(birth_date=date(1982, 5, 9))

        for key in (
            "person",
            "calendar",
            "fun_facts",
            "historical_events",
            "famous_birthdays",
            "movies",
            "lead_story",
            "newspaper_style",
            "president",
            "illustrations",
            "has_historical_events",
            "has_famous_birthdays",
            "has_movies",
            "has_president",
        ):
            assert key in chronicle
