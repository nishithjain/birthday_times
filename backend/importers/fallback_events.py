# backend/importers/fallback_events.py
"""Fallback interesting events when Wikidata returns nothing."""

FALLBACK_EVENTS = {
    # Format: (month, day): [(title, description, category), ...]
    (8, 26): [
        ("Summer Heat Wave", "Record temperatures recorded across Europe", "weather"),
        ("School Year Begins", "Millions of children return to school worldwide", "culture"),
        ("Full Moon", "A beautiful full moon lights up the night sky", "astronomy"),
        ("National Dog Day", "Celebrating our furry friends across the United States", "fun"),
    ],
    (7, 20): [
        ("National Moon Day", "Celebrating the anniversary of the Moon Landing", "space"),
        ("Summer Vacation", "Peak summer travel season around the world", "culture"),
        ("Ice Cream Day", "Perfect weather for enjoying ice cream", "fun"),
    ],
    # Add more dates as needed
}

def get_fallback_events(date_obj):
    """Get fallback events for a date."""
    key = (date_obj.month, date_obj.day)
    return FALLBACK_EVENTS.get(key, [])