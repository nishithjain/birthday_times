"""CLI entry point for movie database status."""

from backend.database import initialize_database
from backend.repositories.movie_repository import MovieRepository


if __name__ == "__main__":
    initialize_database()
    total = sum(MovieRepository.count_for_year(year) for year in range(1950, 2027))
    print("Movie rows:", total)
