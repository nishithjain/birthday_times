# backend/services/chronicle_service.py
"""Chronicle aggregation service."""

import logging
from datetime import date
from typing import Optional, Dict, Any, List

from backend.repositories.event_repository import EventRepository
from backend.repositories.person_repository import PersonRepository
from backend.repositories.movie_repository import MovieRepository
from backend.services.accuracy import EXACT_DATE, YEAR
from backend.services.calendar_service import CalendarService
from backend.services.fun_facts_service import FunFactsService
from backend.services.illustration_service import illustration_service
from backend.services.newspaper_style_service import newspaper_style_service
from backend.services.president_service import president_service
from backend.services.world_news_service import world_news_service
from backend.services.famous_birthdays_service import famous_birthdays_service
from backend.services.weather_service import weather_service
from backend.services.chinese_zodiac_service import chinese_zodiac_service
from backend.services.music_service import music_service
from backend.services.arrival_message_service import arrival_message_service
from backend.services.what_things_cost_service import what_things_cost_service
from backend.services.movie_service import movie_service
from backend.services.around_this_time_service import around_this_time_service

logger = logging.getLogger(__name__)


class ChronicleService:
    """Service for assembling birthday chronicles."""
    
    @staticmethod
    def generate_chronicle(
        birth_date: date,
        name: Optional[str] = None,
        country: str = "India",
        birth_city: Optional[str] = None,
        birth_country: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        birth_state: Optional[str] = None,
        country_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a complete birthday chronicle."""
        
        logger.info(f"Generating chronicle for {birth_date} (country: {country})")
        
        # Calendar calculations
        calendar_data = CalendarService.all_calculations(birth_date)
        
        # Fun facts
        fun_facts = FunFactsService.fun_facts(birth_date)
        
        # Historical events
        events = EventRepository.get_by_date(birth_date, limit=10)
        
        # Newspaper style for birth year
        newspaper_style = newspaper_style_service.get_style_for_year(birth_date.year)

        chinese_zodiac = chinese_zodiac_service.get_chinese_zodiac(
            birth_date=birth_date,
            person_name=name,
            newspaper_style_id=newspaper_style["id"],
        )

        try:
            president = president_service.resolve_president_for_date(
                birth_date,
                newspaper_style["id"],
            )
        except ValueError:
            logger.warning(f"No presidential term found for {birth_date.isoformat()}")
            president = None

        arrival = arrival_message_service.get_arrival(
            birth_date=birth_date,
            name=name,
            country=country,
            calendar_data=calendar_data,
            era=newspaper_style["id"],
            president_name=president.get("displayName") if president else None,
            city=birth_city,
        )

        # Famous birthdays
        try:
            famous_birthdays = famous_birthdays_service.get_famous_birthdays(
                birth_date=birth_date,
                person_name=name,
                newspaper_style_id=newspaper_style["id"],
                limit=3,
            )
        except Exception as e:
            logger.warning(f"Could not fetch famous birthdays: {e}")
            famous_birthdays = None
        
        try:
            movies = movie_service.get_movies_for_year(
                birth_date.year,
                newspaper_style_id=newspaper_style["id"],
            )
        except Exception as e:
            logger.warning(f"Could not fetch movies: {e}")
            movies = {"available": False, "year": birth_date.year, "headline": f"MOVIES OF {birth_date.year}", "featuredMovie": None, "secondaryMovies": [], "reason": "movie_data_unavailable"}

        sports: List[Any] = []

        music_data = music_service.get_music_for_year(
            birth_date.year,
            person_name=name,
            birth_date=birth_date,
            newspaper_style_id=newspaper_style["id"],
            limit=5,
        )
        music = music_data if music_data.get("available") else []
        what_things_cost = what_things_cost_service.get_costs_for_year(birth_date.year)

        weather = weather_service.get_weather(
            birth_date=birth_date,
            city=birth_city,
            state_region=birth_state,
            country_code=country_code,
            latitude=latitude,
            longitude=longitude,
            country=birth_country or country,
            newspaper_style_id=newspaper_style["id"],
        )
        logger.debug(
            "[WEATHER DEBUG] ChronicleService birth_date=%s birth_year=%s "
            "birth_month=%s location=%r weather_available=%s reason=%s",
            birth_date.isoformat(), birth_date.year, birth_date.month, birth_city,
            weather.get("available"), weather.get("reason"),
        )

        world_news = world_news_service.get_world_news(birth_date.year, limit=None)
        if world_news:
            world_news = dict(world_news)

        world_event_ids = [
            item.get("sourceEventId") or item.get("id")
            for item in (world_news or {}).get("candidates", [])
            if item.get("sourceEventId") or item.get("id")
        ]
        around_this_time = around_this_time_service.get_around_this_time(
            birth_date=birth_date,
            newspaper_style_id=newspaper_style["id"],
            excluded_event_ids=world_event_ids,
        )
        
        # Lead story selection
        lead_story = ChronicleService._select_lead_story(events, name, birth_date)

        accuracy = {
            "person": EXACT_DATE,
            "calendar": EXACT_DATE,
            "famous_birthdays": EXACT_DATE,
            "historical_events": EXACT_DATE,
            "movies": YEAR,
            "newspaper_style": YEAR,
            "world_news": YEAR,
            "what_things_cost": YEAR,
        }
        if president is not None:
            accuracy["president"] = EXACT_DATE

        illustrations = illustration_service.select_for_chronicle(
            year=birth_date.year,
            style_id=newspaper_style["id"],
            chinese_zodiac=calendar_data.get("chinese_zodiac"),
            sports_records=sports,
        )
        dispatch_asset = illustration_service.get_for_context("news", birth_date.year)
        arrival["dispatchIllustration"] = (
            illustration_service.resolve_by_id(dispatch_asset["id"], newspaper_style["id"])
            if dispatch_asset else None
        )
        illustrations["masthead"] = illustration_service.resolve_masthead_logo(
            birth_date.year,
            style_id=newspaper_style["id"],
        )

        # Format for template
        chronicle = {
            "person": {
                "name": name,
                "birth_date": birth_date.isoformat(),
                "birth_date_display": birth_date.strftime("%B %d, %Y"),
                "country": country,
            },
            "calendar": calendar_data,
            "fun_facts": fun_facts,
            "historical_events": [e.to_dict() for e in events[:5]],
            "famous_birthdays": famous_birthdays,
            "movies": movies,
            "lead_story": lead_story,
            "arrival": arrival,
            "newspaper_style": newspaper_style,
            "world_news": world_news,
            "around_this_time": around_this_time,
            "weather": weather,
            "chinese_zodiac": chinese_zodiac,
            "music": music,
            "president": president,
            "illustrations": illustrations,
            "accuracy": accuracy,
            "near_events": [],
            "year_news": [],
            "sports": sports,
            "prices": [],
            "what_things_cost": what_things_cost,
            "has_historical_events": len(events) > 0,
            "has_world_news": bool(world_news and world_news.get("headlines")),
            "has_famous_birthdays": bool(famous_birthdays and famous_birthdays.get("people")),
            "has_movies": bool(movies.get("available")),
            "has_president": president is not None,
            "has_near_events": False,
            "has_music": bool(music_data.get("available") and music_data.get("tracks")),
            "has_sports": False,
            "has_prices": False,
        }
        
        return chronicle
    
    @staticmethod
    def _select_lead_story(events, name, birth_date):
        """Select the lead story for the newspaper."""
        
        # Find events with high importance
        high_importance = [e for e in events if e.importance_score >= 7]
        
        if high_importance:
            best = high_importance[0]
            return {
                "type": "historical",
                "headline": best.title,
                "subhead": best.description or "A significant historical event",
                "body": best.description or "",
                "source": best.wikidata_id,
                "importance": best.importance_score,
                "has_image": False,
                "accuracyType": EXACT_DATE,
            }
        
        # Fallback: Birthday headline
        display_name = name or "A New Arrival"
        day_name = CalendarService.day_of_week(birth_date)
        date_str = birth_date.strftime("%B %d, %Y")
        
        return {
            "type": "birthday",
            "headline": f"{display_name} Arrives!",
            "subhead": f"Born on {day_name}, {date_str}",
            "body": f"A new chapter begins on this {day_name} in history. "
                    f"{birth_date.strftime('%B %d')} will forever be a special day.",
            "source": None,
            "importance": 10,
            "has_image": False,
            "accuracyType": "personalized",
        }
