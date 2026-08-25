#!/usr/bin/env python
"""
Historical Event Importer for Birthday Chronicles.

Fetches and classifies historical events from Wikidata.
"""

import argparse
import sys
import time
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import requests

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import config
from backend.models.event import HistoricalEvent
from backend.repositories import EventRepository


# ============================================================
# Wikidata Configuration
# ============================================================

WIKIDATA_ENDPOINT = config.wikidata_endpoint
USER_AGENT = config.wikidata_user_agent


# ============================================================
# Wikidata Date Properties
# ============================================================

DATE_PROPERTIES = {
    "P585": "point_in_time",   # Exact point in time
    "P580": "start_time",      # Start of an event
    "P571": "inception",       # Inception/founding date
}

PROPERTY_PRIORITY = {
    "P585": 1,
    "P580": 2,
    "P571": 3,
}


# ============================================================
# Filtering Configuration - More Lenient for Fun
# ============================================================

EXCLUDED_TYPE_KEYWORDS = [
    "sports season", "football season", "cricket season",  # Keep seasons out
    "album release",  # Keep these for entertainment
]

# ============================================================
# Category Rules - Expanded for Fun
# ============================================================

CATEGORY_RULES = {
    "war_conflict": [
        "battle", "war", "military conflict", "armed conflict",
        "invasion", "siege", "military operation",
        "terrorist attack", "terrorist incident", "bombing",
        "massacre", "coup", "coup d'état", "uprising",
        "rebellion", "revolution",
    ],
    "disaster": [
        "aviation accident", "aviation incident", "aircraft accident",
        "aircraft crash", "plane crash", "air disaster",
        "runway overrun", "railway accident", "rail accident",
        "train accident", "train collision", "shipwreck",
        "maritime disaster", "industrial accident", "industrial disaster",
        "building collapse", "bridge collapse", "earthquake",
        "tsunami", "cyclone", "hurricane", "tornado",
        "flood", "wildfire", "explosion", "disaster", "accident"
    ],
    "politics": [
        "election", "presidential election", "general election",
        "referendum", "treaty", "political event", "political crisis",
        "inauguration", "government formation", "independence",
        "declaration of independence", "assassination",
        "coronation", "abdication"
    ],
    "science_space": [
        "spaceflight", "space mission", "space launch",
        "space exploration", "scientific discovery",
        "scientific experiment", "astronomical event",
        "lunar mission", "planetary mission", "rocket launch",
        "satellite launch"
    ],
    "sports": [
        "sports competition", "sporting event", "sports event",
        "championship", "final", "tournament", "olympic event",
        "cricket match", "football match", "world cup"
    ],
    "entertainment": [
        "film", "movie", "film release", "movie premiere",
        "album", "song", "single", "concert tour", "concert",
        "music festival", "award ceremony", "show", "performance",
        "broadcast", "television premiere", "television series",
        "game release", "book release", "publication"
    ],
    "culture": [
        "ceremony", "festival", "exhibition", "world's fair",
        "cultural event", "celebration", "tradition", "holiday"
    ],
    "historical_event": [
        "historical event", "event", "incident"
    ]
}

# More generous base scores for fun
CATEGORY_BASE_SCORE = {
    "war_conflict": 3,
    "disaster": 3,
    "politics": 3,
    "science_space": 3,
    "sports": 2,
    "entertainment": 2,
    "culture": 2,
    "historical_event": 2,
    "unknown": 1
}

# Lower minimum to include more events
MINIMUM_IMPORTANCE_SCORE = 3


# ============================================================
# Date Parsing
# ============================================================

def parse_date(value: str) -> date:
    """Parse YYYY-MM-DD into a Python date."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Date must be in YYYY-MM-DD format.") from exc


# ============================================================
# Build Wikidata Query
# ============================================================

def build_query(target_date: date, property_id: str, limit: int = 100) -> str:
    """Build SPARQL query for historical events."""
    start = datetime.combine(target_date, datetime.min.time())
    end = start + timedelta(days=1)
    
    start_value = start.strftime("%Y-%m-%dT00:00:00Z")
    end_value = end.strftime("%Y-%m-%dT00:00:00Z")
    
    return f"""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX bd: <http://www.bigdata.com/rdf#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX schema: <http://schema.org/>

SELECT DISTINCT
    ?event
    ?eventLabel
    ?eventDescription
    ?eventDate
    ?country
    ?countryLabel
    ?type
    ?typeLabel
    ?article
    ?sitelinks
WHERE {{
    ?event wdt:{property_id} ?eventDate .
    FILTER (
        ?eventDate >= "{start_value}"^^xsd:dateTime &&
        ?eventDate < "{end_value}"^^xsd:dateTime
    )
    
    # Only items with an English Wikipedia page
    ?article schema:about ?event ;
             schema:isPartOf <https://en.wikipedia.org/> .
    
    OPTIONAL {{ ?event wdt:P31 ?type . }}
    OPTIONAL {{ ?event wdt:P17 ?country . }}
    OPTIONAL {{ ?event wikibase:sitelinks ?sitelinks . }}
    
    SERVICE wikibase:label {{
        bd:serviceParam wikibase:language "en" .
    }}
}}
LIMIT {int(limit)}
"""


def build_year_query(year: int, property_id: str, limit: int = 500) -> str:
    """Build a Wikidata query for all notable events in a calendar year."""
    start_value = f"{year:04d}-01-01T00:00:00Z"
    end_value = f"{year + 1:04d}-01-01T00:00:00Z"
    return f"""
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX bd: <http://www.bigdata.com/rdf#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX schema: <http://schema.org/>

SELECT DISTINCT ?event ?eventLabel ?eventDescription ?eventDate ?country
    ?countryLabel ?type ?typeLabel ?article ?sitelinks
WHERE {{
    ?event wdt:{property_id} ?eventDate .
    FILTER (?eventDate >= "{start_value}"^^xsd:dateTime &&
            ?eventDate < "{end_value}"^^xsd:dateTime)
    ?article schema:about ?event ;
             schema:isPartOf <https://en.wikipedia.org/> .
    OPTIONAL {{ ?event wdt:P31 ?type . }}
    OPTIONAL {{ ?event wdt:P17 ?country . }}
    OPTIONAL {{ ?event wikibase:sitelinks ?sitelinks . }}
    SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
LIMIT {int(limit)}
"""


# ============================================================
# HTTP Session
# ============================================================

def create_session() -> requests.Session:
    """Create HTTP session with proper headers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/sparql-results+json",
    })
    return session


def execute_query(session: requests.Session, query: str, retries: int = 3) -> Optional[Dict]:
    """Execute SPARQL query with retry logic."""
    for attempt in range(1, retries + 1):
        try:
            response = session.get(
                WIKIDATA_ENDPOINT,
                params={"query": query, "format": "json"},
                timeout=config.wikidata_timeout
            )
            
            if response.status_code == 200:
                return response.json()
            
            if response.status_code in (429, 500, 502, 503, 504):
                if attempt < retries:
                    wait = attempt * 3
                    logger.warning(f"HTTP {response.status_code}, retrying in {wait}s...")
                    time.sleep(wait)
                    continue
            
            response.raise_for_status()
            
        except requests.RequestException as exc:
            if attempt == retries:
                raise RuntimeError(f"Unable to query Wikidata: {exc}")
            wait = attempt * 3
            logger.warning(f"Request failed, retrying in {wait}s...")
            time.sleep(wait)
    
    return None


# ============================================================
# SPARQL Helper
# ============================================================

def get_value(row: Dict, field: str) -> Optional[str]:
    """Extract value from SPARQL result row."""
    value = row.get(field)
    if not value:
        return None
    return value.get("value")


def extract_qid(uri: str) -> Optional[str]:
    """Extract QID from Wikidata URI."""
    if not uri:
        return None
    return uri.rsplit("/", 1)[-1]


# ============================================================
# Convert Wikidata Results
# ============================================================

def convert_results(data: Dict, property_id: str) -> List[Dict[str, Any]]:
    """Convert Wikidata results to event dictionaries."""
    events = {}
    
    if not data:
        return []
    
    rows = data.get("results", {}).get("bindings", [])
    
    for row in rows:
        event_uri = get_value(row, "event")
        wikidata_id = extract_qid(event_uri)
        if not wikidata_id:
            continue
        
        title = get_value(row, "eventLabel")
        if not title or title == wikidata_id:
            continue
        
        event_date_value = get_value(row, "eventDate")
        if not event_date_value:
            continue
        
        try:
            clean_date = datetime.fromisoformat(
                event_date_value.replace("Z", "+00:00")
            ).date().isoformat()
        except ValueError:
            continue
        
        key = (clean_date, wikidata_id)
        
        if key not in events:
            sitelinks_value = get_value(row, "sitelinks")
            try:
                sitelinks = int(sitelinks_value) if sitelinks_value else 0
            except ValueError:
                sitelinks = 0
            
            events[key] = {
                "event_date": clean_date,
                "title": title,
                "description": get_value(row, "eventDescription"),
                "country": get_value(row, "countryLabel"),
                "wikidata_id": wikidata_id,
                "source": "Wikidata",
                "source_url": f"https://www.wikidata.org/wiki/{wikidata_id}",
                "wikipedia_url": get_value(row, "article"),
                "date_property": property_id,
                "date_property_type": DATE_PROPERTIES.get(property_id, "unknown"),
                "sitelinks": sitelinks,
                "types": []
            }
        
        # Add type
        type_id = extract_qid(get_value(row, "type"))
        type_label = get_value(row, "typeLabel")
        if type_label and type_label != type_id:
            type_obj = {"id": type_id, "label": type_label}
            if type_obj not in events[key]["types"]:
                events[key]["types"].append(type_obj)
        
        # Add country if not set
        if not events[key]["country"]:
            country = get_value(row, "countryLabel")
            if country:
                events[key]["country"] = country
    
    return list(events.values())


# ============================================================
# Text Normalization
# ============================================================

def normalize(value: str) -> str:
    """Normalize text for comparison."""
    if not value:
        return ""
    return value.strip().lower()


# ============================================================
# Determine if Excluded
# ============================================================

def is_excluded(event: Dict) -> Tuple[bool, Optional[str]]:
    """Check if event should be excluded."""
    type_labels = [normalize(item["label"]) for item in event.get("types", [])]
    
    for type_label in type_labels:
        for keyword in EXCLUDED_TYPE_KEYWORDS:
            if keyword in type_label:
                return True, f"Excluded type: {type_label}"
    
    return False, None


# ============================================================
# Categorize Event
# ============================================================

def determine_category(event: Dict) -> str:
    """Determine event category from types."""
    type_labels = [normalize(item["label"]) for item in event.get("types", [])]
    
    # Check specific categories first
    for category, keywords in CATEGORY_RULES.items():
        if category == "historical_event":
            continue
        for type_label in type_labels:
            for keyword in keywords:
                if keyword in type_label:
                    return category
    
    # Generic event classification
    for type_label in type_labels:
        for keyword in CATEGORY_RULES["historical_event"]:
            if type_label == keyword or type_label.endswith(f" {keyword}"):
                return "historical_event"
    
    return "unknown"


# ============================================================
# Calculate Importance
# ============================================================

def calculate_importance(event: Dict, category: str) -> int:
    """Calculate importance score (1-10)."""
    score = CATEGORY_BASE_SCORE.get(category, 1)
    sitelinks = event.get("sitelinks", 0)
    
    # 1. Global notability
    if sitelinks >= 150:
        score += 5
    elif sitelinks >= 100:
        score += 4
    elif sitelinks >= 50:
        score += 3
    elif sitelinks >= 20:
        score += 2
    elif sitelinks >= 10:
        score += 1
    
    # 2. Category importance bonus
    if category in ("science_space", "politics", "war_conflict"):
        score += 2
    elif category in ("sports", "entertainment") and sitelinks >= 20:
        score += 1
    elif category == "culture" and sitelinks >= 30:
        score += 1
    
    # 3. Date quality
    if event.get("date_property") == "P585":
        score += 1
    elif event.get("date_property") == "P571":
        score -= 1
    
    # 4. Description quality
    if event.get("description"):
        score += 1
    
    # 5. Low-notability penalty (more lenient)
    if sitelinks < 5:
        score -= 1
    elif sitelinks < 10:
        score -= 0  # No penalty for moderate notability
    
    # 6. Unknown category penalty
    if category == "unknown":
        score -= 1
    
    return max(1, min(score, 10))


# ============================================================
# Filter and Rank Events
# ============================================================

def classify_events(events: List[Dict]) -> Tuple[List[HistoricalEvent], List[Dict]]:
    """Classify and filter events."""
    accepted = []
    rejected = []
    
    for event in events:
        excluded, reason = is_excluded(event)
        if excluded:
            event["filter_reason"] = reason
            rejected.append(event)
            continue
        
        category = determine_category(event)
        
        # Filter minor disasters only (still keep major ones)
        if category == "disaster" and event.get("sitelinks", 0) < 5:
            event["filter_reason"] = "Minor disaster with < 5 sitelinks"
            rejected.append(event)
            continue
        
        importance = calculate_importance(event, category)
        
        if importance < MINIMUM_IMPORTANCE_SCORE:
            event["filter_reason"] = f"Importance {importance} < {MINIMUM_IMPORTANCE_SCORE}"
            rejected.append(event)
            continue
        
        # Create HistoricalEvent model
        accepted.append(HistoricalEvent(
            event_date=date.fromisoformat(event["event_date"]),
            title=event["title"],
            description=event.get("description"),
            category=category,
            country=event.get("country"),
            wikidata_id=event["wikidata_id"],
            source=event["source"],
            source_url=event["source_url"],
            wikipedia_url=event.get("wikipedia_url"),
            importance_score=importance,
            date_property=event.get("date_property"),
            date_property_type=event.get("date_property_type"),
        ))
    
    # Sort by importance
    accepted.sort(key=lambda e: (-e.importance_score, e.title.lower()))
    
    return accepted, rejected


# ============================================================
# Fetch Events
# ============================================================

def fetch_events(target_date: date, limit_per_property: int = 100) -> Tuple[List[HistoricalEvent], List[Dict]]:
    """Fetch and classify historical events from Wikidata."""
    session = create_session()
    collected = {}
    
    for property_id, property_name in DATE_PROPERTIES.items():
        logger.info(f"Searching {property_id} ({property_name})...")
        
        query = build_query(target_date, property_id, limit_per_property)
        
        try:
            data = execute_query(session, query)
        except RuntimeError as exc:
            logger.warning(f"Error querying {property_id}: {exc}")
            continue
        
        property_events = convert_results(data, property_id)
        logger.info(f"  Found {len(property_events)} candidate records.")
        
        for event in property_events:
            key = (event["event_date"], event["wikidata_id"])
            
            if key not in collected:
                collected[key] = event
                continue
            
            existing = collected[key]
            existing_priority = PROPERTY_PRIORITY.get(existing["date_property"], 99)
            new_priority = PROPERTY_PRIORITY.get(event["date_property"], 99)
            
            if new_priority < existing_priority:
                # Preserve combined types
                old_types = existing["types"]
                for item in old_types:
                    if item not in event["types"]:
                        event["types"].append(item)
                collected[key] = event
            else:
                for item in event["types"]:
                    if item not in existing["types"]:
                        existing["types"].append(item)
    
    all_events = list(collected.values())
    return classify_events(all_events)


def fetch_events_for_year(year: int, limit_per_property: int = 500) -> Tuple[List[HistoricalEvent], List[Dict]]:
    """Fetch and classify all available notable events for one year."""
    session = create_session()
    collected = {}
    for property_id, property_name in DATE_PROPERTIES.items():
        logger.info("Searching %s (%s) for %s...", property_id, property_name, year)
        try:
            data = execute_query(session, build_year_query(year, property_id, limit_per_property))
        except RuntimeError as exc:
            logger.warning("Error querying %s for %s: %s", property_id, year, exc)
            continue
        for event in convert_results(data, property_id):
            key = (event["event_date"], event["wikidata_id"])
            if key not in collected:
                collected[key] = event
            else:
                existing = collected[key]
                if PROPERTY_PRIORITY.get(event["date_property"], 99) < PROPERTY_PRIORITY.get(existing["date_property"], 99):
                    event["types"].extend(item for item in existing["types"] if item not in event["types"])
                    collected[key] = event
                else:
                    existing["types"].extend(item for item in event["types"] if item not in existing["types"])
    return classify_events(list(collected.values()))


def import_year(year: int, limit: int = 500, dry_run: bool = False) -> Tuple[int, int, int]:
    """Import one year and return candidate, inserted, and existing counts."""
    accepted, _ = fetch_events_for_year(year, limit)
    existing_keys = {(event.event_date, event.wikidata_id) for event in EventRepository.get_by_year(year)}
    new_count = sum((event.event_date, event.wikidata_id) not in existing_keys for event in accepted)
    if not dry_run:
        EventRepository.save(accepted)
    return len(accepted), new_count, len(accepted) - new_count


# ============================================================
# Display Functions
# ============================================================

def type_text(event: HistoricalEvent) -> str:
    """Get type text for display."""
    return event.category


def print_events(events: List[HistoricalEvent]) -> None:
    """Display accepted events."""
    print()
    print("=" * 80)
    print(f"ACCEPTED HISTORICAL EVENTS: {len(events)}")
    print("=" * 80)
    
    if not events:
        print()
        print("No relevant historical events found.")
        print()
        print("💡 Fun fact: Even though we didn't find major events,")
        print("   your birthday is still special! 🎉")
        return
    
    for number, event in enumerate(events, start=1):
        print()
        print(f"{number}. {event.title}")
        if event.description:
            print(f"   Description : {event.description}")
        if event.country:
            print(f"   Country     : {event.country}")
        print(f"   Category    : {event.category}")
        print(f"   Importance  : {event.importance_score}/10")
        if event.wikidata_id:
            print(f"   Wikidata    : {event.wikidata_id}")
        if event.wikipedia_url:
            print(f"   Wikipedia   : {event.wikipedia_url}")


def print_filtered_events(events: List[Dict]) -> None:
    """Display rejected events."""
    print()
    print("=" * 80)
    print(f"FILTERED / REJECTED EVENTS: {len(events)}")
    print("=" * 80)
    
    if not events:
        print()
        print("Nothing was filtered.")
        return
    
    for number, event in enumerate(events, start=1):
        print()
        print(f"{number}. {event['title']}")
        print(f"   Reason : {event.get('filter_reason', 'Unknown')}")


# ============================================================
# Main
# ============================================================

def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch, classify and save historical events from Wikidata."
    )
    parser.add_argument("--date", help="Date in YYYY-MM-DD format")
    parser.add_argument("--year", type=int, help="Import one calendar year")
    parser.add_argument("--from-year", type=int, help="First year in an import range")
    parser.add_argument("--to-year", type=int, help="Last year in an import range")
    parser.add_argument("--limit", type=int, default=100, help="Max records per property")
    parser.add_argument("--dry-run", action="store_true", help="Do not save to SQLite")
    parser.add_argument("--show-filtered", action="store_true", help="Display rejected records")
    parser.add_argument("--replace-date", action="store_true", help="Delete existing data for this date")
    
    args = parser.parse_args()

    range_mode = args.year is not None or args.from_year is not None or args.to_year is not None
    if range_mode and args.date:
        parser.error("--date cannot be combined with year options")
    if range_mode:
        start = args.year if args.year is not None else args.from_year
        end = args.year if args.year is not None else args.to_year
        if start is None or end is None or start > end:
            parser.error("provide --year or both --from-year and --to-year")
        print("Importing historical events")
        inserted = existing = failed = 0
        for year in range(start, end + 1):
            try:
                candidates, new_count, existing_count = import_year(year, args.limit, args.dry_run)
                inserted += new_count
                existing += existing_count
                print(f"{year} ... {candidates} candidates / {new_count} inserted / {existing_count} existing")
            except Exception as exc:
                failed += 1
                print(f"{year} ... FAILED: {exc}")
        print("\nSummary:")
        print(f"Years processed: {end - start + 1}")
        print(f"Inserted: {inserted}")
        print(f"Existing: {existing}")
        print(f"Failed years: {failed}")
        return

    if not args.date:
        parser.error("--date or year options are required")
    
    try:
        target_date = parse_date(args.date)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
    
    print()
    print("Birthday Chronicles - Historical Event Importer")
    print("=" * 50)
    print()
    print(f"Date: {target_date}")
    print()
    
    accepted, rejected = fetch_events(target_date, args.limit)
    
    print_events(accepted)
    
    if args.show_filtered:
        print_filtered_events(rejected)
    
    print()
    print("Summary")
    print("-------")
    print(f"Accepted : {len(accepted)}")
    print(f"Filtered : {len(rejected)}")
    
    if args.dry_run:
        print()
        print("Dry-run complete. Nothing was written to SQLite.")
        return
    
    try:
        if args.replace_date:
            deleted = EventRepository.delete_by_date(target_date)
            print()
            print(f"Removed {deleted} previously stored records.")
        
        count = EventRepository.save(accepted)
        print()
        print(f"Saved {count} historical events.")
        
    except Exception as exc:
        print()
        print("DATABASE ERROR")
        print(exc)
        sys.exit(1)


if __name__ == "__main__":
    main()