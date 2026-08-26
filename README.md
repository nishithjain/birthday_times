# Birthday Chronicles

A personalized historical chronicle that tells you what happened in the world on your birthday.

## Overview

Birthday Chronicles is a Python application that generates an interesting, historically accurate "Birthday Chronicle" describing the world around the time you were born.

**Current Version**: 0.3.0

### Features

- **Historical Events**: What happened on your birthday throughout history
- **Famous Birthdays**: Notable people born on your birthday
- **Calendar & Zodiac**: Day of week, zodiac signs, and fun facts
- **Movies**: Popular films from your birth year (TMDB integration)
- **Music**: Notable music releases
- **Sports**: Major sporting events
- **Economy**: Historical economic indicators
- **Local Database**: All data stored locally for fast retrieval

## Architecture

```SHELL

# macOS / Linux
unset PYTHONHOME
unset PYTHONPATH

python -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

python -m backend.app

```

On Windows PowerShell, use the equivalent commands below instead:

```powershell
$env:PYTHONHOME = $null
$env:PYTHONPATH = $null
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m backend.app
```

The development review links below require this Flask server to be running on
`http://127.0.0.1:5000`; they will not work when the README is opened without
starting the server.

## World News Preparation

Historical world-news files are derived from SQLite and are not generated during
application startup. Populate the event database explicitly, then generate the
offline yearly datasets:

```shell
python -m backend.importers.wikidata_events --year 1982
python -m backend.importers.wikidata_events --from-year 1950 --to-year 2026
python -m backend.tools.generate_world_news --status
python -m backend.tools.generate_world_news --year 1982
python -m backend.tools.generate_world_news --from-year 1950 --to-year 2026
python -m backend.tools.generate_world_news --all
python -m backend.tools.generate_world_news --from-year 1950 --to-year 2026 --dry-run
python -m backend.tools.generate_world_news --year 1982 --force
```

Generated files live under `backend/data/world_news/`. Files marked `reviewed`
or `approved` are protected from normal regeneration; `--force` is required to
replace them. The Flask application reads these files locally through
`WorldNewsService` and does not contact Wikidata.

Monthly weather uses NASA POWER climatology rather than exact historical
birthday weather. Only twelve monthly climate records are stored per supported
city; the active importer does not download daily Open-Meteo archive data.

## Development Visual Reviews

Development-only visual review runners are available under `/dev/sections/`.
They are intended for quickly reviewing many combinations of one component in
the browser without changing production routes or saving review output.

### Review Links

| Component | Review URL | Default scope |
| --- | --- | --- |
| Weather | <http://127.0.0.1:5000/dev/sections/weather-review> | 10 cities x 12 months (120 tests) |
| Eagle / Logo | <http://127.0.0.1:5000/dev/sections/eagle-logo-review> | 1950, 1960, 1982, 2005, and 2015 era cases |
| Extra! | <http://127.0.0.1:5000/dev/sections/extra-review> | 19 date and layout stress cases |
| Masthead | <http://127.0.0.1:5000/dev/sections/masthead-review> | 18 date, era, and title-layout cases |
| Arrival / Birth Story | <http://127.0.0.1:5000/dev/sections/arrival-review> | 10 names, locations, presidents, and era cases |
| News Around the World | <http://127.0.0.1:5000/dev/sections/world-news-review> | 10 dates across 1950-2026 |
| Around This Time | <http://127.0.0.1:5000/dev/sections/around-this-time-review> | 11 dates across 1950-2026, including low-data and boundary cases |
| Famous Birthdays | <http://127.0.0.1:5000/dev/sections/famous-birthdays-review> | Occupation preference and fallback selection |
| At The Movies | <http://127.0.0.1:5000/dev/sections/movies-review> | 9 birth years across 1950-2025 |
| Music | <http://127.0.0.1:5000/dev/sections/music-review> | 9 birth years across 1950-2025 |

The standalone Masthead component is available at
<http://127.0.0.1:5000/dev/sections/masthead>. It renders the publication
identity at `920 x 150` with a dynamic birth date and the existing newspaper
style fonts. The Masthead review runner cycles through the 18 date and era
cases in one iframe with a `1000 ms` default interval.

The standalone Extra component can also be inspected directly at
<http://127.0.0.1:5000/dev/sections/extra>. It renders the actual Chronicle
birth date in the fixed `230 x 100` component. The review runner cycles through
short dates, long month names, leap day, single- and double-digit days, and
the five Chronicle era ranges using one iframe and a `1000 ms` default interval.

### Weather Review Runner

Start the Flask development server:

```shell
python -m backend.app
```

Open the Weather review runner:

<http://127.0.0.1:5000/dev/sections/weather-review>

The default run reviews ten enabled cities across all twelve months, for 120
Weather pages total. Each test uses day `09` and year `1982`, because Weather
climatology is month-based. The runner keeps one browser page and one reused
iframe. It loads a Weather development page, waits for the iframe and Weather
copy fitting to finish, displays it for one second, and then advances.

The runner controls are:

- `PREVIOUS`: pause and show the previous test
- `PAUSE` / `RESUME`: stop or continue automatic playback
- `NEXT`: pause and show the next test
- `RESTART`: return to the first test and resume playback

Keyboard controls are also available: Space pauses or resumes, Left Arrow and
Right Arrow move between tests, and `R` restarts the run. The current test
number, city, month, date, URL, progress, and iframe preview are shown on the
page. The final test remains visible when the review completes.

Optional query parameters:

```text
?city=Bengaluru       Review one city across its twelve months
?cities=20            Review up to 25 selected cities
?month=1              Review one month across the selected cities
?interval=1500        Set the dwell interval in milliseconds
```

Examples:

```text
http://127.0.0.1:5000/dev/sections/weather-review?city=Bengaluru
http://127.0.0.1:5000/dev/sections/weather-review?month=1&cities=25
http://127.0.0.1:5000/dev/sections/weather-review?cities=20&interval=1500
```

Cities are selected from enabled `weather_locations` records with complete
monthly coverage; the runner does not insert or modify database rows. Review
state and generated URLs exist only in browser memory. The runner does not
save screenshots, HTML, JSON, CSV, logs, or browser storage data.

Future component review runners should follow the same development-only
pattern: add a dedicated test-page template and route, keep the production
route unchanged, reuse one iframe, wait for the embedded component to finish
rendering before starting the dwell timer, and keep all review state in memory.

### Eagle / Logo Review Runner

The standalone Eagle / Logo review runner is available at:

<http://127.0.0.1:5000/dev/sections/eagle-logo-review>

It automatically reviews the default era cases `1950`, `1960`, `1982`, `2005`,
and `2015` using one reused iframe and a `1000 ms` interval. The 1950 case
uses the existing 1950 variant, 1960 uses the existing original asset, and
later years show the era-unavailable state defined by the current illustration
metadata. The runner does not change the Eagle component or save review data.

Controls are `PREVIOUS`, `PAUSE` / `RESUME`, `NEXT`, and `RESTART`. Space,
Left Arrow, Right Arrow, and `R` provide the equivalent keyboard controls.

Optional query parameters:

```text
?years=1950,1960,1982    Review a custom comma-separated year list
?interval=1500            Set the dwell interval in milliseconds
```

Example:

<http://127.0.0.1:5000/dev/sections/eagle-logo-review?years=1950,1955,1960,1965,1970,1975,1980,1985,1990,1995,2000,2005,2010,2015,2020,2025&interval=1500>
