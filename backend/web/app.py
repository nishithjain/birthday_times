# backend/web/app.py
"""Flask web application for Birthday Chronicles."""

import logging
import sys
import traceback
from datetime import datetime, date
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database import initialize_database
from backend.repositories.weather_location_repository import WeatherLocationRepository
from backend.repositories.weather_repository import WeatherRepository
from backend.services.chronicle_service import ChronicleService
from backend.services.illustration_service import illustration_service
from backend.services.newspaper_style_service import newspaper_style_service

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

EXTRA_ORNAMENTS = {
    "1950": "★", "1960": "★", "1970": "✶", "1980": "✶",
    "1990": "◆", "1995": "◆", "2000": "◆", "2005": "❖",
    "2010": "❖", "2015": "•",
}

MASTHEAD_TITLES = {
    "1950": "The Birthday Gazette",
    "1960": "The Birthday Gazette",
    "1970": "The Birthday Chronicle",
    "1980": "The Birthday Chronicle",
    "1990": "The Birthday Herald",
    "1995": "The Birthday Herald",
    "2000": "The Birthday Herald",
    "2005": "The Birthday Edition",
    "2010": "The Birthday Edition",
    "2015": "The Birthday Times",
}

NEWS_DISPATCH_PRESENTATION = {
    "1950": {"image": "telegram_1950.png", "label": "Telegram", "alt": "Vintage telegram dispatch", "natural": "902 x 471", "expected": "124 x 65"},
    "1960": {"image": "wire_globe_1960.png", "label": "Wire Service", "alt": "Wire service bulletin", "natural": "808 x 538", "expected": "120 x 80"},
    "1970": {"image": "mimeograph_1970.png", "label": "News Press", "alt": "News press illustration", "natural": "1107 x 713", "expected": "124 x 80"},
    "1980": {"image": "typewriter_1980.png", "label": "News Flash", "alt": "News flash typewriter", "natural": "853 x 741", "expected": "92 x 80"},
    "1990": {"image": "computer_1990.png", "label": "Computer Bulletin", "alt": "Computer news bulletin", "natural": "1077 x 832", "expected": "103.6 x 80"},
    "1995": {"image": "computer_1990.png", "label": "Computer Bulletin", "alt": "Computer news bulletin", "natural": "1077 x 832", "expected": "103.6 x 80"},
    "2000": {"image": "pager_2000.png", "label": "News Alert", "alt": "News alert pager", "natural": "608 x 499", "expected": "98 x 80"},
    "2005": {"image": "pager_2000.png", "label": "News Alert", "alt": "News alert pager", "natural": "608 x 499", "expected": "98 x 80"},
    "2010": {"image": "ipad_2010.png", "label": "Digital Dispatch", "alt": "Digital news tablet", "natural": "1182 x 723", "expected": "124 x 76"},
    "2015": {"image": "dispatch_badge_2015.png", "label": "News Update", "alt": "News update icon", "natural": "682 x 464", "expected": "118 x 80"},
}

# Initialize Flask app
app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-production"

# Initialize database on startup
try:
    initialize_database()
    logger.info("Database initialized successfully")
except Exception as e:
    logger.warning(f"Database initialization warning: {e}")


# ============================================================
# Template filters
# ============================================================

@app.template_filter("format_date")
def format_date_filter(value):
    """Format date for display."""
    if not value:
        return ""
    try:
        d = datetime.strptime(value, "%Y-%m-%d")
        return d.strftime("%B %d, %Y")
    except:
        return value


@app.template_filter("month_day")
def month_day_filter(value):
    """Extract month and day from date."""
    if not value:
        return ""
    try:
        d = datetime.strptime(value, "%Y-%m-%d")
        return d.strftime("%B %d")
    except:
        return value


@app.template_filter("year")
def year_filter(value):
    """Extract year from date."""
    if not value:
        return ""
    try:
        d = datetime.strptime(value, "%Y-%m-%d")
        return d.strftime("%Y")
    except:
        return value


@app.template_filter("comma")
def comma_filter(value):
    """Add commas to numbers."""
    try:
        return f"{int(value):,}"
    except:
        return value


# ============================================================
# Routes
# ============================================================

@app.route("/")
def index():
    """Home page with form."""
    return render_template("index.html")


@app.route("/chronicle", methods=["POST"])
def generate_chronicle():
    """Generate and display birthday chronicle."""
    
    # Get form data
    name = request.form.get("name", "").strip()
    birth_date_str = request.form.get("birth_date", "").strip()
    country = request.form.get("country", "India").strip()
    birth_city = (request.form.get("birth_city") or request.form.get("city") or "").strip() or None
    birth_state = (request.form.get("birth_state") or request.form.get("state_region") or "").strip() or None
    country_code = request.form.get("country_code", "").strip() or None
    birth_country = request.form.get("birth_country", "").strip() or None
    latitude = request.form.get("latitude", "").strip()
    longitude = request.form.get("longitude", "").strip()
    try:
        latitude = float(latitude) if latitude else None
        longitude = float(longitude) if longitude else None
    except ValueError:
        flash("Please enter valid location coordinates.", "error")
        return redirect(url_for("index"))
    
    logger.info(
        "[WEATHER DEBUG] request birth_date=%s raw_location=%r normalized_location=%r "
        "country_input=%r birth_state=%r country_code=%r",
        birth_date_str,
        request.form.get("birth_city") or request.form.get("city"),
        birth_city,
        birth_country or country,
        birth_state,
        country_code,
    )
    
    # Validate
    if not birth_date_str:
        flash("Please enter your date of birth.", "error")
        return redirect(url_for("index"))
    
    try:
        # Parse date - try multiple formats
        birth_date = None
        for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y", "%d/%m/%Y", "%m/%d/%Y"]:
            try:
                birth_date = datetime.strptime(birth_date_str, fmt).date()
                logger.info(f"Parsed date using format {fmt}: {birth_date}")
                break
            except ValueError:
                continue
        
        if birth_date is None:
            flash("Please enter a valid date (YYYY-MM-DD or DD-MM-YYYY).", "error")
            return redirect(url_for("index"))
            
    except Exception as e:
        logger.error(f"Date parsing error: {e}")
        flash("Please enter a valid date.", "error")
        return redirect(url_for("index"))
    
    # Validate date range
    min_date = date(1950, 1, 1)
    max_date = date.today()
    
    if birth_date < min_date:
        flash("Our chronicles currently cover 1950 to present. Please enter a later date.", "error")
        return redirect(url_for("index"))
    
    if birth_date > max_date:
        flash("Please enter a date in the past.", "error")
        return redirect(url_for("index"))
    
    # Generate chronicle
    try:
        logger.info(f"Generating chronicle for {birth_date}")
        chronicle = ChronicleService.generate_chronicle(
            birth_date=birth_date,
            name=name if name else None,
            country=country,
            birth_city=birth_city,
            birth_state=birth_state,
            country_code=country_code,
            birth_country=birth_country,
            latitude=latitude,
            longitude=longitude,
        )
        logger.info("Chronicle generated successfully!")
        
    except Exception as e:
        logger.error(f"Error generating chronicle: {e}")
        logger.error(traceback.format_exc())
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for("index"))
    
    return render_template(
        chronicle["newspaper_style"]["template"],
        chronicle=chronicle,
    )


@app.route("/about")
def about():
    """About page."""
    return render_template("about.html")


@app.route("/dev/weather-copy-templates")
def weather_copy_templates():
    """Serve presentation-only Weather copy to the modular component."""
    return app.response_class(
        (PROJECT_ROOT / "backend" / "data" / "weather_copy_templates.json").read_text(encoding="utf-8"),
        mimetype="application/json",
    )


def _development_chronicle():
    raw_date = request.args.get("date", "1982-05-09")
    try:
        birth_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        birth_date = date(1982, 5, 9)
    chronicle = ChronicleService.generate_chronicle(
        birth_date=birth_date,
        name=request.args.get("name") or "Nishith",
        country=request.args.get("country", "India"),
        birth_city=request.args.get("city") or None,
    )
    if request.args.get("fixture") == "snow":
        chronicle["weather"].update({
            "available": True,
            "condition": "snow",
            "temperatureCharacter": "cold",
            "illustration": illustration_service.resolve_by_id("weather_snow", "1990"),
        })
    chronicle["section_stylesheets"] = [
        f"css/chronicles/sections/{name}.css"
        for name in ("masthead", "weather", "arrival", "world_news", "famous_birthdays", "around_this_time", "movies", "music", "zodiac", "what_things_cost", "sports", "footer")
    ]
    style_id = str(chronicle.get("newspaper_style", {}).get("id", "2015"))
    chronicle["extraOrnament"] = EXTRA_ORNAMENTS.get(style_id, "•")
    chronicle["mastheadTitle"] = MASTHEAD_TITLES.get(style_id, "The Birthday Times")
    dispatch = NEWS_DISPATCH_PRESENTATION.get(style_id, NEWS_DISPATCH_PRESENTATION["2015"])
    chronicle["arrival"]["dispatchLabel"] = dispatch["label"]
    chronicle["arrival"]["dispatchArtwork"] = {
        "displayPath": f"images/illustrations/originals/news_dispatch/{dispatch['image']}",
        "alt": dispatch["alt"],
        "natural": dispatch["natural"],
        "expected": dispatch["expected"],
    }
    return chronicle


@app.route("/dev/chronicle-master")
def development_master():
    return render_template("chronicles/master/chronicle_master.html", chronicle=_development_chronicle())


@app.route("/dev/sections/masthead-review")
def development_masthead_review():
    try:
        interval = min(max(int(request.args.get("interval", 1000)), 500), 10000)
    except ValueError:
        interval = 1000
    review_dates = [
        "1950-01-01", "1955-05-09", "1960-09-30", "1969-12-31",
        "1970-01-01", "1975-11-29", "1982-05-09", "1989-12-31",
        "1990-01-01", "1995-09-30", "2000-02-29", "2004-12-31",
        "2005-01-01", "2010-11-29", "2014-12-31", "2015-01-01",
        "2020-02-29", "2026-12-31",
    ]
    review_cases = [
        {
            "date": review_date,
            "year": int(review_date[:4]),
            "styleId": str(style := newspaper_style_service.get_style_for_year(int(review_date[:4]))["id"]),
            "mastheadTitle": MASTHEAD_TITLES.get(style, "The Birthday Times"),
        }
        for review_date in review_dates
    ]
    return render_template(
        "chronicles/test_pages/masthead_review_runner.html",
        review_cases=review_cases,
        interval=interval,
    )


@app.route("/dev/sections/masthead")
def development_masthead():
    return render_template("chronicles/test_pages/test_masthead.html", chronicle=_development_chronicle())


@app.route("/dev/sections/eagle-logo")
def development_eagle_logo():
    return render_template("chronicles/test_pages/test_eagle_logo.html", chronicle=_development_chronicle())


@app.route("/dev/sections/eagle-logo-review")
def development_eagle_logo_review():
    try:
        interval = min(max(int(request.args.get("interval", 1000)), 500), 10000)
    except ValueError:
        interval = 1000
    raw_years = request.args.get("years", "1950,1960,1982,2005,2015")
    years = []
    for value in raw_years.split(","):
        try:
            parsed = int(value.strip())
        except ValueError:
            continue
        if 1900 <= parsed <= 2100 and parsed not in years:
            years.append(parsed)
    return render_template(
        "chronicles/test_pages/eagle_logo_review_runner.html",
        review_years=years,
        interval=interval,
    )


@app.route("/dev/sections/extra")
def development_extra():
    return render_template("chronicles/test_pages/test_extra.html", chronicle=_development_chronicle())


@app.route("/dev/sections/extra-review")
def development_extra_review():
    try:
        interval = min(max(int(request.args.get("interval", 1000)), 500), 10000)
    except ValueError:
        interval = 1000
    review_dates = [
        "1950-01-01", "1955-05-09", "1955-12-31", "1960-09-30", "1965-05-09", "1969-11-29",
        "1970-01-01", "1975-02-28", "1975-05-09", "1982-05-09", "1989-12-31",
        "1990-01-01", "1992-05-09", "1995-09-30", "1997-05-09", "2000-02-29", "2002-05-09", "2004-12-31",
        "2005-01-01", "2008-05-09", "2010-11-29", "2012-05-09", "2014-12-31", "2015-01-01",
        "2018-05-09", "2020-02-29", "2025-09-30", "2026-05-09", "2026-12-31",
    ]
    review_cases = [
        {
            "date": review_date,
            "styleId": str(style := newspaper_style_service.get_style_for_year(int(review_date[:4]))["id"]),
            "ornament": EXTRA_ORNAMENTS.get(style, "•"),
        }
        for review_date in review_dates
    ]
    return render_template(
        "chronicles/test_pages/extra_review_runner.html",
        review_cases=review_cases,
        extra_ornaments=EXTRA_ORNAMENTS,
        interval=interval,
    )


@app.route("/dev/sections/arrival-review")
def development_arrival_review():
    try:
        interval = min(max(int(request.args.get("interval", 1000)), 500), 10000)
    except ValueError:
        interval = 1000
    review_cases = [
        {"date": "1955-05-09", "name": "Nishith", "city": "Bengaluru", "country": "India"},
        {"date": "1965-05-09", "name": "Nishith", "city": "Mumbai", "country": "India"},
        {"date": "1975-05-09", "name": "Avery Morgan", "city": "London", "country": "United Kingdom"},
        {"date": "1982-05-09", "name": "Nishith Jain M R", "city": "Bengaluru", "country": "India"},
        {"date": "1995-09-30", "name": "Alexandria Montgomery", "city": "Toronto", "country": "Canada"},
        {"date": "2002-11-29", "name": "Jordan Lee", "city": "Singapore", "country": "Singapore"},
        {"date": "2008-05-09", "name": "Samira Khan", "city": "Dubai", "country": "United Arab Emirates"},
        {"date": "2012-05-09", "name": "Taylor Brooks", "city": "Helsinki", "country": "Finland"},
        {"date": "2018-05-09", "name": "Morgan Ellis", "city": "Sydney", "country": "Australia"},
        {"date": "2026-12-31", "name": "Christopher Alexander Wellington", "city": "Moscow", "country": "Russia"},
        {"date": "1997-05-09", "name": "Alex Morgan", "city": "Bengaluru", "country": "India"},
        {"date": "2010-05-09", "name": "Taylor Brooks", "city": "London", "country": "United Kingdom"},
    ]
    for case in review_cases:
        case["year"] = int(case["date"][:4])
        case["styleId"] = str(newspaper_style_service.get_style_for_year(case["year"])["id"])
        dispatch = NEWS_DISPATCH_PRESENTATION.get(case["styleId"], NEWS_DISPATCH_PRESENTATION["2015"])
        case["dispatchLabel"] = dispatch["label"]
        case["dispatchArtwork"] = dispatch["image"]
        case["dispatchNatural"] = dispatch["natural"]
        case["dispatchExpected"] = dispatch["expected"]
    return render_template("chronicles/test_pages/arrival_review_runner.html", review_cases=review_cases, interval=interval)


@app.route("/dev/sections/weather-review")
def development_weather_review():
    requested_city = request.args.get("city", "").strip()
    try:
        city_count = min(max(int(request.args.get("cities", 10)), 1), 25)
    except ValueError:
        city_count = 10
    try:
        interval = min(max(int(request.args.get("interval", 1000)), 500), 10000)
    except ValueError:
        interval = 1000
    month_filter = request.args.get("month", "").strip()
    try:
        month = int(month_filter) if month_filter else None
        if month is not None and not 1 <= month <= 12:
            month = None
    except ValueError:
        month = None

    preferred_names = ["Bengaluru", "Mumbai", "Singapore", "London", "Toronto", "Moscow", "Helsinki", "Dubai", "Sydney"]
    selected = []
    if requested_city:
        requested = WeatherLocationRepository.find_city(requested_city)
        if requested and WeatherRepository.count_months(requested["id"]) == 12:
            selected.append(requested)
    else:
        for name in preferred_names:
            location = WeatherLocationRepository.find_city(name)
            if location and WeatherRepository.count_months(location["id"]) == 12:
                selected.append(location)
        if len(selected) < city_count:
            for location in WeatherLocationRepository.get_enabled_locations(major_limit=1000):
                if WeatherRepository.count_months(location["id"]) == 12 and all(item["id"] != location["id"] for item in selected):
                    selected.append(location)
                if len(selected) >= city_count:
                    break
    selected = selected[:city_count]
    return render_template(
        "chronicles/test_pages/weather_review_runner.html",
        review_cities=[location["city"] for location in selected],
        interval=interval,
        month=month,
    )


@app.route("/dev/sections/world-news-review")
def development_world_news_review():
    try:
        interval = min(max(int(request.args.get("interval", 1000)), 500), 10000)
    except ValueError:
        interval = 1000
    review_dates = [f"{year}-05-09" for year in (1950, 1955, 1960, 1970, 1982, 1990, 2000, 2010, 2020, 2026)]
    return render_template(
        "chronicles/test_pages/world_news_review_runner.html",
        review_dates=review_dates,
        interval=interval,
    )


@app.route("/dev/sections/around-this-time-review")
def development_around_this_time_review():
    try:
        interval = min(max(int(request.args.get("interval", 1000)), 500), 10000)
    except ValueError:
        interval = 1000
    return render_template(
        "chronicles/test_pages/around_this_time_review_runner.html",
        review_dates=[
            "1950-01-01", "1950-05-09", "1960-05-09", "1970-05-09",
            "1982-05-09", "1990-05-09", "2000-05-09", "2010-05-09",
            "2020-05-09", "2026-05-09", "2020-12-29",
        ],
        interval=interval,
    )


@app.route("/dev/sections/famous-birthdays-review")
def development_famous_birthdays_review():
    return render_template(
        "chronicles/test_pages/famous_birthdays_review_runner.html",
        review_dates=[
            "1950-05-09", "1955-09-30", "1960-05-09", "1970-11-29",
            "1982-05-09", "1990-09-30", "2000-02-29", "2010-05-09",
            "2020-02-29", "2025-12-31",
        ],
    )


@app.route("/dev/sections/movies-review")
def development_movies_review():
    try:
        interval = min(max(int(request.args.get("interval", 1000)), 500), 10000)
    except ValueError:
        interval = 1000
    return render_template(
        "chronicles/test_pages/movies_review_runner.html",
        review_years=[1950, 1960, 1970, 1982, 1990, 2000, 2010, 2020, 2025],
        interval=interval,
    )


@app.route("/dev/sections/music-review")
def development_music_review():
    try:
        interval = min(max(int(request.args.get("interval", 1000)), 500), 10000)
    except ValueError:
        interval = 1000
    return render_template(
        "chronicles/test_pages/music_review_runner.html",
        review_years=[1950, 1960, 1970, 1982, 1990, 2000, 2010, 2015, 2020, 2025],
        interval=interval,
    )


@app.route("/dev/sections/<section_name>")
def development_section(section_name):
    template_names = {
        "masthead": "test_masthead.html",
        "weather": "test_weather.html", "arrival": "test_arrival.html",
        "world-news": "test_world_news.html", "famous-birthdays": "test_famous_birthdays.html",
        "around-this-time": "test_around_this_time.html", "movies": "test_movies.html",
        "music": "test_music.html", "zodiac": "test_zodiac.html",
        "what-things-cost": "test_what_things_cost.html", "sports": "test_sports.html",
    }
    template = template_names.get(section_name)
    if template is None:
        return "Unknown development section", 404
    return render_template(f"chronicles/test_pages/{template}", chronicle=_development_chronicle())


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)