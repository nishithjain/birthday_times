# tests/test_calendar_service.py
"""Tests for calendar service."""

import pytest
from datetime import date
from backend.services.calendar_service import CalendarService


class TestCalendarService:
    """Test CalendarService."""
    
    def test_day_of_week(self):
        """Test day of week calculation."""
        assert CalendarService.day_of_week(date(1982, 8, 26)) == "Thursday"
        assert CalendarService.day_of_week(date(1969, 7, 20)) == "Sunday"
        assert CalendarService.day_of_week(date(2000, 1, 1)) == "Saturday"
    
    def test_western_zodiac(self):
        """Test western zodiac calculation."""
        assert CalendarService.western_zodiac(date(1982, 8, 26)) == "Virgo"
        assert CalendarService.western_zodiac(date(1969, 7, 20)) == "Cancer"
        assert CalendarService.western_zodiac(date(2000, 1, 1)) == "Capricorn"
    
    def test_chinese_zodiac(self):
        """Test Chinese zodiac calculation."""
        assert CalendarService.chinese_zodiac(date(1982, 8, 26)) == "Dog"
        assert CalendarService.chinese_zodiac(date(1983, 1, 1)) == "Dog"
    
    def test_birthstone(self):
        """Test birthstone calculation."""
        assert CalendarService.birthstone(date(1982, 8, 26)) == "Peridot"
        assert CalendarService.birthstone(date(1969, 7, 20)) == "Ruby"
    
    def test_generation(self):
        """Test generation calculation."""
        assert CalendarService.generation(date(1982, 8, 26)) == "Millennials"
        assert CalendarService.generation(date(1969, 7, 20)) == "Generation X"
        assert CalendarService.generation(date(1950, 1, 1)) == "Baby Boomers"
    
    def test_is_leap_year(self):
        """Test leap year detection."""
        assert CalendarService.is_leap_year(date(1984, 1, 1)) is True
        assert CalendarService.is_leap_year(date(1982, 8, 26)) is False
        assert CalendarService.is_leap_year(date(2000, 1, 1)) is True
        assert CalendarService.is_leap_year(date(1900, 1, 1)) is False
    
    def test_days_remaining(self):
        """Test days remaining calculation."""
        assert CalendarService.days_remaining(date(1982, 8, 26)) == 127
        assert CalendarService.days_remaining(date(2000, 1, 1)) == 365  # Leap year
        assert CalendarService.days_remaining(date(2001, 1, 1)) == 364
    
    def test_age(self):
        """Test age calculation."""
        ref_date = date(2024, 1, 1)
        assert CalendarService.age(date(1982, 8, 26), ref_date) == 41
        assert CalendarService.age(date(2000, 1, 1), ref_date) == 24
    
    def test_fun_facts(self):
        """Test fun facts generation."""
        facts = CalendarService.fun_facts(date(1982, 8, 26))
        assert any("Thursday" in fact for fact in facts)
        assert any("Virgo" in fact for fact in facts)
        assert any("Dog" in fact for fact in facts)
        assert any("Peridot" in fact for fact in facts)