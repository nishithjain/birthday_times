from datetime import date

from backend.models.movie import Movie
from backend.services.movie_service import MovieService


class Repository:
    movies = []

    @staticmethod
    def get_by_year(year, limit=None):
        return list(Repository.movies)


class Illustrations:
    @staticmethod
    def get_for_context(context, year=None):
        return {"id": "film-strip"}

    @staticmethod
    def resolve_by_id(illustration_id, style_id=None):
        return {"id": illustration_id, "displayPath": "images/illustrations/originals/movies/film-strip.png"}


def movie(title, year=1960, overview=None, popularity=1):
    return Movie(title=title, release_date=date(year, 1, 1), overview=overview, popularity=popularity)


def test_movie_service_selects_described_feature_and_secondary_movies():
    Repository.movies = [movie("No Synopsis", overview=None, popularity=10), movie("Featured Film", overview="A factual film description.", popularity=9), movie("Another Film", overview="Another factual description.", popularity=8)]
    result = MovieService(Repository, Illustrations).get_movies_for_year(1960)
    assert result["available"] is True
    assert result["year"] == 1960
    assert result["featuredMovie"]["title"] == "Featured Film"
    assert [item["title"] for item in result["secondaryMovies"]] == ["No Synopsis", "Another Film"]
    assert result["illustrationId"] == "film-strip"
    assert result["accuracyType"] == "year"


def test_movie_service_missing_year_is_explicit():
    Repository.movies = []
    result = MovieService(Repository, Illustrations).get_movies_for_year(1982)
    assert result["available"] is False
    assert result["reason"] == "movie_data_unavailable"
    assert result["secondaryMovies"] == []
