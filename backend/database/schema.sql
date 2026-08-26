-- ============================================================
-- Birthday Chronicles
-- SQLite Database Schema
-- Version 2.0
-- ============================================================

-- ------------------------------------------------------------
-- Historical Events
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS historical_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Exact date of the historical event (YYYY-MM-DD)
    event_date TEXT NOT NULL,
    
    -- Main event title
    title TEXT NOT NULL,
    
    -- Longer description
    description TEXT,
    
    -- Category: politics, science, sports, culture, etc.
    category TEXT DEFAULT 'historical_event',
    
    -- Country associated with the event
    country TEXT,
    
    -- Wikidata identifier (e.g., Q12345)
    wikidata_id TEXT NOT NULL,
    
    -- Data source
    source TEXT NOT NULL DEFAULT 'Wikidata',
    
    -- Original source URL
    source_url TEXT,
    
    -- Wikipedia article URL
    wikipedia_url TEXT,
    
    -- Importance score (1-10)
    importance_score INTEGER NOT NULL DEFAULT 5
        CHECK (importance_score >= 1 AND importance_score <= 10),
    
    -- Which Wikidata date property matched
    date_property TEXT,
    date_property_type TEXT,
    
    -- Timestamps
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(event_date, wikidata_id)
);

-- ------------------------------------------------------------
-- Around This Time Events
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS around_this_time_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_date TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT DEFAULT 'historical_event',
    external_id TEXT NOT NULL,
    source_name TEXT NOT NULL DEFAULT 'Wikidata',
    source_url TEXT,
    wikipedia_url TEXT,
    date_source TEXT,
    date_precision INTEGER NOT NULL,
    date_property_type TEXT,
    sitelink_count INTEGER NOT NULL DEFAULT 0,
    importance_score INTEGER NOT NULL DEFAULT 5
        CHECK (importance_score >= 1 AND importance_score <= 10),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(external_id, event_date)
);

-- ------------------------------------------------------------
-- Famous People
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS famous_people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Full name
    name TEXT NOT NULL,
    
    -- Birth date (YYYY-MM-DD)
    birth_date TEXT NOT NULL,
    
    -- Occupation(s)
    occupation TEXT,
    
    -- Wikidata ID
    wikidata_id TEXT NOT NULL UNIQUE,
    
    -- Wikipedia URL
    wikipedia_url TEXT,
    
    -- Number of Wikimedia sitelinks (notability indicator)
    sitelinks INTEGER DEFAULT 0,
    
    -- Notability score (1-10)
    notability_score INTEGER DEFAULT 5
        CHECK (notability_score >= 1 AND notability_score <= 10),
    
    -- Data source
    source TEXT NOT NULL DEFAULT 'Wikidata',
    source_url TEXT,
    
    -- Timestamps
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- Historical Weather
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS historical_weather (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id INTEGER,
    weather_date TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    city TEXT,
    region TEXT,
    country TEXT,
    source TEXT NOT NULL,
    source_location_id TEXT,
    source_dataset TEXT,
    source_latitude REAL,
    source_longitude REAL,
    temperature_max_c REAL,
    temperature_min_c REAL,
    temperature_mean_c REAL,
    apparent_temperature_max_c REAL,
    apparent_temperature_min_c REAL,
    precipitation_mm REAL,
    rain_mm REAL,
    snowfall_cm REAL,
    wind_speed_max_kmh REAL,
    wind_gust_max_kmh REAL,
    wind_direction_dominant_deg REAL,
    weather_code INTEGER,
    sunrise TEXT,
    sunset TEXT,
    data_quality TEXT,
    fetched_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(weather_date, latitude, longitude, source)
);

-- City catalog and resumable weather prefetch metadata.
CREATE TABLE IF NOT EXISTS weather_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_key TEXT NOT NULL UNIQUE,
    geoname_id INTEGER UNIQUE,
    city TEXT NOT NULL,
    ascii_name TEXT,
    state_region TEXT,
    state_code TEXT,
    country TEXT NOT NULL,
    country_code TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    timezone TEXT,
    population INTEGER,
    feature_code TEXT,
    priority INTEGER NOT NULL DEFAULT 3,
    major_city_rank INTEGER,
    enabled INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS weather_import_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id INTEGER NOT NULL,
    from_date TEXT NOT NULL,
    through_date TEXT,
    status TEXT NOT NULL,
    rows_imported INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT,
    completed_at TEXT,
    error_message TEXT,
    provider TEXT,
    FOREIGN KEY(location_id) REFERENCES weather_locations(id),
    UNIQUE(location_id, from_date, provider)
);

-- Active city/month climate data. The legacy daily tables above are retained
-- for existing installations but are not used by Chronicle runtime.
CREATE TABLE IF NOT EXISTS monthly_weather (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id INTEGER NOT NULL,
    month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
    avg_min_temp_c REAL,
    avg_max_temp_c REAL,
    avg_mean_temp_c REAL,
    avg_precipitation_mm REAL,
    avg_rainy_days REAL,
    avg_wind_kmh REAL,
    climate_condition TEXT,
    source TEXT NOT NULL,
    source_dataset TEXT,
    reference_period TEXT,
    fetched_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(location_id) REFERENCES weather_locations(id),
    UNIQUE(location_id, month)
);

-- ------------------------------------------------------------
-- Movies
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS movies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Movie title
    title TEXT NOT NULL,
    
    -- Release date (YYYY-MM-DD)
    release_date TEXT,
    
    -- Country of origin
    country TEXT,
    
    -- Genres (comma-separated)
    genres TEXT,
    
    -- Overview/synopsis
    overview TEXT,
    
    -- Poster URL
    poster_url TEXT,
    
    -- TMDB ID (if from TMDB)
    tmdb_id INTEGER UNIQUE,
    
    -- IMDb ID
    imdb_id TEXT,

    -- Normalized external source identity and compact credits
    source_id TEXT,
    director TEXT,
    lead_actor TEXT,
    
    -- Popularity/rating (from source)
    popularity REAL,
    vote_average REAL,
    vote_count INTEGER,
    
    -- Data source
    source TEXT NOT NULL DEFAULT 'TMDB',
    source_url TEXT,
    
    -- Timestamps
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- Music Releases
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS music_releases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Release title
    title TEXT NOT NULL,
    
    -- Artist name
    artist TEXT NOT NULL,
    
    -- Release date (YYYY-MM-DD)
    release_date TEXT,
    
    -- Album/Single/EP
    release_type TEXT DEFAULT 'album',
    
    -- Country
    country TEXT,
    
    -- Genres
    genres TEXT,
    
    -- MusicBrainz ID
    musicbrainz_id TEXT UNIQUE,
    
    -- Data source
    source TEXT NOT NULL DEFAULT 'MusicBrainz',
    source_url TEXT,
    
    -- Timestamps
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Year-level chart entries used by the newspaper music section.
CREATE TABLE IF NOT EXISTS music_tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    title TEXT NOT NULL,
    artist TEXT NOT NULL,
    chart_name TEXT,
    chart_country TEXT,
    source TEXT NOT NULL,
    source_id TEXT,
    source_url TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, year, chart_name, rank)
);

-- ------------------------------------------------------------
-- Sports Events
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sports_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Event title/name
    title TEXT NOT NULL,
    
    -- Event date (YYYY-MM-DD)
    event_date TEXT NOT NULL,
    
    -- Sport category
    sport TEXT NOT NULL,
    
    -- Description
    description TEXT,
    
    -- Country
    country TEXT,
    
    -- Winner/result
    result TEXT,
    
    -- Importance score (1-10)
    importance_score INTEGER DEFAULT 5
        CHECK (importance_score >= 1 AND importance_score <= 10),
    
    -- Wikidata ID
    wikidata_id TEXT,
    wikipedia_url TEXT,
    
    -- Data source
    source TEXT NOT NULL DEFAULT 'Wikidata',
    source_url TEXT,
    
    -- Timestamps
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(event_date, title)
);

-- ------------------------------------------------------------
-- Economic Indicators
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS economic_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Year
    year INTEGER NOT NULL,
    
    -- Country
    country TEXT NOT NULL,
    
    -- Indicator name
    indicator TEXT NOT NULL,
    
    -- Value
    value REAL,
    
    -- Unit (USD, %, etc.)
    unit TEXT,
    
    -- Data source
    source TEXT NOT NULL,
    source_url TEXT,
    
    -- Timestamps
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(year, country, indicator)
);

-- ------------------------------------------------------------
-- Indexes
-- ------------------------------------------------------------

-- Historical Events indexes
CREATE INDEX IF NOT EXISTS idx_events_date ON historical_events(event_date);
CREATE INDEX IF NOT EXISTS idx_events_wikidata ON historical_events(wikidata_id);
CREATE INDEX IF NOT EXISTS idx_events_country ON historical_events(country);
CREATE INDEX IF NOT EXISTS idx_events_category ON historical_events(category);
CREATE INDEX IF NOT EXISTS idx_events_importance ON historical_events(event_date, importance_score DESC);

CREATE INDEX IF NOT EXISTS idx_around_this_time_event_date
ON around_this_time_events(event_date);

-- Famous People indexes
CREATE INDEX IF NOT EXISTS idx_people_birth_date ON famous_people(birth_date);
CREATE INDEX IF NOT EXISTS idx_people_country ON famous_people(country);
CREATE INDEX IF NOT EXISTS idx_people_wikidata ON famous_people(wikidata_id);
CREATE INDEX IF NOT EXISTS idx_weather_date_location ON historical_weather(weather_date, latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_weather_location_date ON historical_weather(location_id, weather_date);
CREATE UNIQUE INDEX IF NOT EXISTS uq_weather_location_date_source ON historical_weather(location_id, weather_date, source);
CREATE INDEX IF NOT EXISTS idx_monthly_weather_location_month ON monthly_weather(location_id, month);
CREATE INDEX IF NOT EXISTS idx_weather_locations_country ON weather_locations(country_code);
CREATE INDEX IF NOT EXISTS idx_weather_locations_state ON weather_locations(state_region);
CREATE INDEX IF NOT EXISTS idx_weather_locations_city ON weather_locations(city);
CREATE INDEX IF NOT EXISTS idx_weather_locations_priority ON weather_locations(priority, enabled);
CREATE INDEX IF NOT EXISTS idx_weather_locations_major_rank ON weather_locations(major_city_rank);

-- Movies indexes
CREATE INDEX IF NOT EXISTS idx_movies_release_date ON movies(release_date);
CREATE INDEX IF NOT EXISTS idx_movies_tmdb_id ON movies(tmdb_id);

-- Music indexes
CREATE INDEX IF NOT EXISTS idx_music_release_date ON music_releases(release_date);
CREATE INDEX IF NOT EXISTS idx_music_tracks_year_rank ON music_tracks(year, rank);

-- Sports indexes
CREATE INDEX IF NOT EXISTS idx_sports_date ON sports_events(event_date);
CREATE INDEX IF NOT EXISTS idx_sports_sport ON sports_events(sport);

-- Economic indexes
CREATE INDEX IF NOT EXISTS idx_economic_country_year ON economic_indicators(country, year);

-- ------------------------------------------------------------
-- Triggers
-- ------------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS trg_events_updated_at
AFTER UPDATE ON historical_events
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE historical_events SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_people_updated_at
AFTER UPDATE ON famous_people
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE famous_people SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- ------------------------------------------------------------
-- Views
-- ------------------------------------------------------------

CREATE VIEW IF NOT EXISTS events_summary AS
SELECT
    event_date,
    COUNT(*) AS total_events,
    COUNT(DISTINCT country) AS countries,
    MAX(importance_score) AS highest_importance
FROM historical_events
GROUP BY event_date;