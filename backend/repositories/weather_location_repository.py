"""SQLite repository for supported city weather locations."""

from typing import Any, Dict, List, Optional

from backend.database import database_connection, fetch_all, fetch_one


class WeatherLocationRepository:
    @staticmethod
    def get_by_id(location_id: int) -> Optional[Dict[str, Any]]:
        row = fetch_one("SELECT * FROM weather_locations WHERE id = ? AND enabled = 1", (location_id,))
        return dict(row) if row else None

    @staticmethod
    def get_by_location_key(location_key: str) -> Optional[Dict[str, Any]]:
        row = fetch_one("SELECT * FROM weather_locations WHERE location_key = ? AND enabled = 1", (location_key,))
        return dict(row) if row else None

    @staticmethod
    def find_city(city: str, state_region: Optional[str] = None, country_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM weather_locations WHERE lower(city) = lower(?) AND enabled = 1"
        params: List[Any] = [city.strip()]
        if state_region:
            query += " AND lower(state_region) = lower(?)"
            params.append(state_region.strip())
        if country_code:
            query += " AND upper(country_code) = upper(?)"
            params.append(country_code.strip())
        query += " ORDER BY priority ASC, population DESC, location_key ASC LIMIT 1"
        row = fetch_one(query, params)
        return dict(row) if row else None

    @staticmethod
    def search_cities(query: str, country_code: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM weather_locations WHERE enabled = 1 AND (lower(city) LIKE lower(?) OR lower(ascii_name) LIKE lower(?))"
        params: List[Any] = [f"%{query.strip()}%", f"%{query.strip()}%"]
        if country_code:
            sql += " AND upper(country_code) = upper(?)"
            params.append(country_code.strip())
        sql += " ORDER BY priority ASC, population DESC, city ASC LIMIT ?"
        params.append(min(max(limit, 1), 50))
        return [dict(row) for row in fetch_all(sql, params)]

    @staticmethod
    def get_enabled_locations(max_priority: Optional[int] = None, country_code: Optional[str] = None, min_population: Optional[int] = None, major_limit: Optional[int] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM weather_locations WHERE enabled = 1"
        params: List[Any] = []
        if max_priority is not None:
            sql += " AND priority <= ?"; params.append(max_priority)
        if country_code:
            sql += " AND upper(country_code) = upper(?)"; params.append(country_code)
        if min_population is not None:
            sql += " AND population >= ?"; params.append(min_population)
        if major_limit is not None:
            sql += " AND major_city_rank IS NOT NULL AND major_city_rank <= ?"; params.append(major_limit)
        sql += " ORDER BY priority ASC, population DESC, location_key ASC"
        return [dict(row) for row in fetch_all(sql, params)]

    @staticmethod
    def upsert_location(location: Dict[str, Any]) -> None:
        fields = ["location_key", "geoname_id", "city", "ascii_name", "state_region", "state_code", "country", "country_code", "latitude", "longitude", "timezone", "population", "feature_code", "priority", "major_city_rank", "enabled", "source"]
        values = [location.get(field) for field in fields]
        updates = ", ".join(f"{field} = excluded.{field}" for field in fields[1:])
        with database_connection() as connection:
            connection.execute(f"INSERT INTO weather_locations ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)}) ON CONFLICT(location_key) DO UPDATE SET {updates}", values)

    @staticmethod
    def countries() -> List[Dict[str, Any]]:
        return [dict(row) for row in fetch_all("SELECT country_code, country, COUNT(*) AS count FROM weather_locations WHERE enabled = 1 GROUP BY country_code, country ORDER BY country")]

    @staticmethod
    def states(country_code: str) -> List[Dict[str, Any]]:
        return [dict(row) for row in fetch_all("SELECT DISTINCT state_region FROM weather_locations WHERE enabled = 1 AND upper(country_code) = upper(?) AND state_region IS NOT NULL ORDER BY state_region", (country_code,))]

    @staticmethod
    def major_status() -> Dict[str, Any]:
        rows = fetch_all("SELECT * FROM weather_locations WHERE enabled = 1 AND major_city_rank IS NOT NULL ORDER BY major_city_rank")
        ranks = {row["major_city_rank"] for row in rows}
        return {"total": len(rows), "countries": len({row["country_code"] for row in rows}), "missing_ranks": sorted(set(range(1, 1001)) - ranks), "duplicate_ranks": len(ranks) != len(rows), "rows": [dict(row) for row in rows]}
