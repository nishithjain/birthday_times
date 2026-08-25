"""Offline year-based movie content for the Chronicle."""

import re
from datetime import date
from typing import Any, Dict, Optional

from backend.repositories.movie_repository import MovieRepository
from backend.services.accuracy import YEAR
from backend.services.illustration_service import illustration_service


def short_description(value: Optional[str]) -> Optional[str]:
    text = " ".join((value or "").split())
    if not text:
        return None
    return re.split(r"(?<=[.!?])\s+", text)[0].strip() or text


def credit_for(movie) -> Optional[str]:
    if getattr(movie, "lead_actor", None) and getattr(movie, "director", None):
        return f"Starring {movie.lead_actor} - Directed by {movie.director}"
    if getattr(movie, "lead_actor", None):
        return f"Starring {movie.lead_actor}"
    if getattr(movie, "director", None):
        return f"Directed by {movie.director}"
    return None


class MovieService:
    """Build a Chronicle-ready movie payload from the local movies table."""

    def __init__(self, repository=MovieRepository, illustrations=illustration_service):
        self.repository = repository
        self.illustrations = illustrations

    def get_movies_for_year(self, year: int, newspaper_style_id: Optional[str] = None) -> Dict[str, Any]:
        year = int(year)
        movies = self.repository.get_by_year(year, limit=None)
        headline = f"MOVIES OF {year}"
        if not movies:
            return {"available": False, "year": year, "headline": headline, "featuredMovie": None, "secondaryMovies": [], "illustrationId": None, "illustration": None, "accuracyType": YEAR, "reason": "movie_data_unavailable"}
        featured = next((movie for movie in movies if short_description(movie.overview)), movies[0])

        def payload(movie):
            return {
                "id": movie.id,
                "title": movie.title,
                "year": movie.release_date.year if movie.release_date else year,
                "description": short_description(movie.overview),
                "credit": credit_for(movie),
                "genres": movie.genres,
                "source": movie.source,
                "sourceUrl": movie.source_url,
            }

        selected = payload(featured)
        secondary = [payload(movie) for movie in movies if movie is not featured]
        illustration = self.illustrations.get_for_context("movies", year)
        illustration_id = illustration.get("id") if illustration else None
        return {
            "available": True,
            "year": year,
            "headline": headline,
            "featuredMovie": selected,
            "secondaryMovies": secondary,
            "illustrationId": illustration_id,
            "illustration": self.illustrations.resolve_by_id(illustration_id, newspaper_style_id) if illustration_id else None,
            "accuracyType": YEAR,
            "candidates": [selected, *secondary],
        }


movie_service = MovieService()
