# backend/services/calendar_service.py
"""Calendar, zodiac, and fun facts service."""

from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple


class CalendarService:
    """Service for calendar calculations and fun facts."""
    
    # Western zodiac signs
    ZODIAC_SIGNS = [
        ("Capricorn", (1, 1), (1, 19)),
        ("Aquarius", (1, 20), (2, 18)),
        ("Pisces", (2, 19), (3, 20)),
        ("Aries", (3, 21), (4, 19)),
        ("Taurus", (4, 20), (5, 20)),
        ("Gemini", (5, 21), (6, 20)),
        ("Cancer", (6, 21), (7, 22)),
        ("Leo", (7, 23), (8, 22)),
        ("Virgo", (8, 23), (9, 22)),
        ("Libra", (9, 23), (10, 22)),
        ("Scorpio", (10, 23), (11, 21)),
        ("Sagittarius", (11, 22), (12, 21)),
        ("Capricorn", (12, 22), (12, 31)),
    ]
    
    # Chinese zodiac animals
    CHINESE_ZODIAC = [
        "Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake",
        "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"
    ]
    
    # Birthstones by month
    BIRTHSTONES = {
        1: "Garnet",
        2: "Amethyst",
        3: "Aquamarine",
        4: "Diamond",
        5: "Emerald",
        6: "Pearl",
        7: "Ruby",
        8: "Peridot",
        9: "Sapphire",
        10: "Opal",
        11: "Topaz",
        12: "Turquoise",
    }
    
    # Generations
    GENERATIONS = [
        ("Silent Generation", 1928, 1945),
        ("Baby Boomers", 1946, 1964),
        ("Generation X", 1965, 1980),
        ("Millennials", 1981, 1996),
        ("Generation Z", 1997, 2012),
        ("Generation Alpha", 2013, 2025),
    ]
    
    @classmethod
    def day_of_week(cls, target_date: date) -> str:
        """Get day of week."""
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        return weekdays[target_date.weekday()]
    
    @classmethod
    def western_zodiac(cls, target_date: date) -> str:
        """Get western zodiac sign."""
        month, day = target_date.month, target_date.day
        
        for sign, (start_m, start_d), (end_m, end_d) in cls.ZODIAC_SIGNS:
            if (month == start_m and day >= start_d) or (month == end_m and day <= end_d):
                return sign
        
        return "Capricorn"  # Default
    
    @classmethod
    def chinese_zodiac(cls, target_date: date) -> str:
        """Get the traditional zodiac animal using the Chinese New Year boundary."""
        from backend.services.chinese_zodiac_service import chinese_zodiac_service

        return chinese_zodiac_service.get_animal_for_date(target_date) or "Unknown"
    
    @classmethod
    def birthstone(cls, target_date: date) -> str:
        """Get birthstone for the month."""
        return cls.BIRTHSTONES.get(target_date.month, "Unknown")
    
    @classmethod
    def generation(cls, target_date: date) -> str:
        """Get generation name."""
        year = target_date.year
        for name, start, end in cls.GENERATIONS:
            if start <= year <= end:
                return name
        return "Unknown Generation"
    
    @classmethod
    def is_leap_year(cls, target_date: date) -> bool:
        """Check if year is a leap year."""
        year = target_date.year
        return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    
    @classmethod
    def day_of_year(cls, target_date: date) -> int:
        """Get day of year (1-366)."""
        return target_date.timetuple().tm_yday
    
    @classmethod
    def days_in_year(cls, target_date: date) -> int:
        """Get total days in year."""
        return 366 if cls.is_leap_year(target_date) else 365
    
    @classmethod
    def days_remaining(cls, target_date: date) -> int:
        """Get days remaining in the year."""
        return cls.days_in_year(target_date) - cls.day_of_year(target_date)
    
    @classmethod
    def age(cls, birth_date: date, reference_date: Optional[date] = None) -> int:
        """Calculate age."""
        if reference_date is None:
            reference_date = date.today()
        
        age = reference_date.year - birth_date.year
        if (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day):
            age -= 1
        return age
    
    @classmethod
    def days_lived(cls, birth_date: date, reference_date: Optional[date] = None) -> int:
        """Calculate days lived."""
        if reference_date is None:
            reference_date = date.today()
        return (reference_date - birth_date).days
    
    @classmethod
    def next_birthday(cls, birth_date: date, reference_date: Optional[date] = None) -> Tuple[date, int]:
        """Calculate next birthday and days until."""
        if reference_date is None:
            reference_date = date.today()
        
        # Birthday this year
        birthday_day = birth_date.day
        if birth_date.month == 2 and birth_date.day == 29 and not cls.is_leap_year(date(reference_date.year, 1, 1)):
            birthday_day = 28
        birthday_this_year = date(reference_date.year, birth_date.month, birthday_day)
        
        # If passed, use next year
        if birthday_this_year < reference_date:
            next_birthday_day = birth_date.day
            if birth_date.month == 2 and birth_date.day == 29 and not cls.is_leap_year(date(reference_date.year + 1, 1, 1)):
                next_birthday_day = 28
            birthday_next = date(reference_date.year + 1, birth_date.month, next_birthday_day)
        else:
            birthday_next = birthday_this_year
        
        days_until = (birthday_next - reference_date).days
        return birthday_next, days_until
    
    @classmethod
    def all_calculations(cls, birth_date: date) -> Dict[str, Any]:
        """Get all calendar calculations."""
        today = date.today()
        birthday_next, days_until = cls.next_birthday(birth_date)
        
        return {
            "birth_date": birth_date.isoformat(),
            "day_of_week": cls.day_of_week(birth_date),
            "western_zodiac": cls.western_zodiac(birth_date),
            "chinese_zodiac": cls.chinese_zodiac(birth_date),
            "birthstone": cls.birthstone(birth_date),
            "generation": cls.generation(birth_date),
            "is_leap_year": cls.is_leap_year(birth_date),
            "day_of_year": cls.day_of_year(birth_date),
            "days_in_year": cls.days_in_year(birth_date),
            "days_remaining": cls.days_remaining(birth_date),
            "age": cls.age(birth_date),
            "days_lived": cls.days_lived(birth_date),
            "next_birthday": birthday_next.isoformat(),
            "days_until_birthday": days_until,
        }
    
    @classmethod
    def fun_facts(cls, birth_date: date) -> List[str]:
        """Generate fun facts about the birth date."""
        facts = []
        calc = cls.all_calculations(birth_date)
        
        facts.append(f"You were born on a {calc['day_of_week']}.")
        facts.append(f"You were born on the {calc['day_of_year']}th day of the year.")
        facts.append(f"{calc['days_remaining']} days remained in the year.")
        facts.append(f"Your Western zodiac sign is {calc['western_zodiac']}.")
        facts.append(f"Your Chinese zodiac sign is {calc['chinese_zodiac']}.")
        facts.append(f"Your birthstone is {calc['birthstone']}.")
        facts.append(f"You are part of {calc['generation']}.")
        
        if calc['is_leap_year']:
            facts.append("You were born in a leap year!")
        
        return facts