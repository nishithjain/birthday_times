"""Audit same-year Around This Time coverage across supported birth dates."""

import argparse
import sqlite3
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

from backend.config import config

MIN_YEAR = 1950
MAX_YEAR = 2026
WINDOWS = (0, 7, 15, 30)


def supported_dates(start_year: int = MIN_YEAR, end_year: int = MAX_YEAR) -> Iterable[date]:
    for year in range(start_year, end_year + 1):
        current = date(year, 1, 1)
        while current.year == year:
            yield current
            current += timedelta(days=1)


def coverage_counts(event_dates: Sequence[date], target: date) -> Tuple[int, int, int, int]:
    year_start = date(target.year, 1, 1)
    year_end = date(target.year, 12, 31)
    return tuple(
        sum(
            max(year_start, target - timedelta(days=window))
            <= event_date
            <= min(year_end, target + timedelta(days=window))
            for event_date in event_dates
        )
        for window in WINDOWS
    )


def classify(counts: Tuple[int, int, int, int]) -> str:
    return "GOOD" if counts[3] >= 3 else "WEAK" if counts[3] else "CRITICAL"


def audit_connection(connection: sqlite3.Connection, start_year: int = MIN_YEAR, end_year: int = MAX_YEAR) -> List[Dict[str, object]]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        "SELECT event_date FROM around_this_time_events WHERE event_date >= ? AND event_date < ?",
        (f"{start_year:04d}-01-01", f"{end_year + 1:04d}-01-01"),
    ).fetchall()
    by_year: Mapping[int, List[date]] = defaultdict(list)
    for row in rows:
        event_date = date.fromisoformat(row["event_date"])
        by_year[event_date.year].append(event_date)
    return [
        {"date": target, "counts": coverage_counts(by_year[target.year], target), "classification": classify(coverage_counts(by_year[target.year], target))}
        for target in supported_dates(start_year, end_year)
    ]


def _ranges(values: Sequence[date]) -> List[str]:
    if not values:
        return []
    ordered = sorted(values)
    result = []
    start = previous = ordered[0]
    for current in ordered[1:]:
        if current != previous + timedelta(days=1):
            result.append(start.isoformat() if start == previous else f"{start.isoformat()}..{previous.isoformat()}")
            start = current
        previous = current
    result.append(start.isoformat() if start == previous else f"{start.isoformat()}..{previous.isoformat()}")
    return result


def print_report(records: Sequence[Mapping[str, object]]) -> None:
    totals = Counter(str(record["classification"]) for record in records)
    total = len(records)
    print(f"total_supported_dates={total}")
    for classification_name in ("GOOD", "WEAK", "CRITICAL"):
        count = totals[classification_name]
        print(f"{classification_name.lower()}={count} ({count / total:.2%})")
    for count in (0, 1, 2):
        dates = [record["date"] for record in records if record["counts"][3] == count]
        print(f"dates_with_{count}_events={len(dates)}")
        print("  " + ", ".join(_ranges(dates)))
    year_counts = Counter()
    month_counts = Counter()
    for record in records:
        if record["classification"] != "GOOD":
            target = record["date"]
            year_counts[(target.year, record["classification"])] += 1
            month_counts[(target.year, target.month, record["classification"])] += 1
    print("lowest_years=" + ", ".join(f"{year}:{classification}={count}" for (year, classification), count in year_counts.most_common(15)))
    print("lowest_months=" + ", ".join(f"{year:04d}-{month:02d}:{classification}={count}" for (year, month, classification), count in month_counts.most_common(20)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year-from", type=int, default=MIN_YEAR)
    parser.add_argument("--year-to", type=int, default=MAX_YEAR)
    parser.add_argument("--database", type=Path, default=config.database_path)
    args = parser.parse_args()
    with sqlite3.connect(args.database) as connection:
        print_report(audit_connection(connection, args.year_from, args.year_to))


if __name__ == "__main__":
    main()
