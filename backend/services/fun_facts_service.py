# backend/services/fun_facts_service.py
"""Generate fun facts for any date."""

import random
from datetime import date
from backend.services.calendar_service import CalendarService


class FunFactsService:
    """Generate fun facts for any date."""
    
    @staticmethod
    def get_daily_facts(target_date: date) -> list:
        """Get fun facts for a date."""
        facts = []
        
        # Day of week facts
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day_name = weekdays[target_date.weekday()]
        facts.append(f"It's a {day_name}!")
        
        # Month facts
        month_names = ["January", "February", "March", "April", "May", "June", 
                      "July", "August", "September", "October", "November", "December"]
        month = month_names[target_date.month - 1]
        facts.append(f"The month of {month} has {FunFactsService.days_in_month(target_date)} days.")
        
        # Season facts (Northern Hemisphere)
        season = FunFactsService.get_season(target_date)
        facts.append(f"It's {season} in the Northern Hemisphere.")
        
        # Zodiac
        zodiac = CalendarService.western_zodiac(target_date)
        facts.append(f"The zodiac sign is {zodiac}.")
        
        # Random fun facts
        random_facts = [
            f"The sun rises at approximately 6:00 AM and sets at 6:00 PM on {target_date.strftime('%B %d')}.",
            "The Earth completes one rotation in 24 hours.",
            "Light travels at 299,792,458 meters per second.",
            f"On {target_date.strftime('%B %d')}, the average temperature is around 20°C (68°F) in many parts of the world.",
            "The moon orbits the Earth approximately every 27.3 days.",
            "There are 24 time zones around the world.",
        ]
        
        facts.append(random.choice(random_facts))
        
        return facts
    
    @staticmethod
    def days_in_month(target_date: date) -> int:
        """Get number of days in the month."""
        if target_date.month == 2:
            return 29 if CalendarService.is_leap_year(target_date) else 28
        elif target_date.month in [4, 6, 9, 11]:
            return 30
        else:
            return 31
    
    @staticmethod
    def get_season(target_date: date) -> str:
        """Get season for Northern Hemisphere."""
        month = target_date.month
        if 3 <= month <= 5:
            return "Spring"
        elif 6 <= month <= 8:
            return "Summer"
        elif 9 <= month <= 11:
            return "Autumn"
        else:
            return "Winter"
    
    @staticmethod
    def fun_facts(target_date: date) -> list:
        """Get fun facts for a date (alias for get_daily_facts)."""
        return FunFactsService.get_daily_facts(target_date)