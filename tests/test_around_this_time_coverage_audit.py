import sqlite3
from datetime import date

from backend.tools.audit_around_this_time_coverage import (
    audit_connection,
    classify,
    coverage_counts,
    supported_dates,
)


def test_classification_uses_the_thirty_day_count():
    assert classify((0, 0, 0, 0)) == "CRITICAL"
    assert classify((0, 0, 1, 2)) == "WEAK"
    assert classify((0, 0, 1, 3)) == "GOOD"


def test_coverage_counts_clamp_to_the_target_year():
    assert coverage_counts(
        [date(2000, 1, 1), date(1999, 12, 31), date(2000, 1, 31)],
        date(2000, 1, 1),
    ) == (1, 1, 1, 2)


def test_supported_dates_includes_leap_day():
    dates = list(supported_dates(2020, 2020))

    assert len(dates) == 366
    assert date(2020, 2, 29) in dates


def test_audit_ignores_events_from_other_years():
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE around_this_time_events (event_date TEXT)")
    connection.executemany(
        "INSERT INTO around_this_time_events VALUES (?)",
        [("1999-12-31",), ("2000-01-01",), ("2000-01-08",)],
    )

    records = audit_connection(connection, 2000, 2000)

    assert records[0]["date"] == date(2000, 1, 1)
    assert records[0]["counts"] == (1, 2, 2, 2)
    assert records[0]["classification"] == "WEAK"
    connection.close()