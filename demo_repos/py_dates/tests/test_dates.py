from datetime import date, datetime, timezone

from dates import add_months, business_days_between, is_leap, month_end, parse_iso, to_local


def test_leap_basic():
    assert is_leap(2024) and not is_leap(2023)


def test_leap_century():
    assert not is_leap(1900) and is_leap(2000)


def test_month_end_feb_leap():
    assert month_end(date(2024, 2, 10)) == date(2024, 2, 29)


def test_business_days_excludes_end():
    # Mon 2026-03-02 .. Mon 2026-03-09 -> 5 weekdays
    assert business_days_between(date(2026, 3, 2), date(2026, 3, 9)) == 5


def test_parse_iso_offset():
    assert parse_iso("2026-03-08T01:30:00+00:00") == datetime(2026, 3, 8, 1, 30, tzinfo=timezone.utc)


def test_to_local_fixed_offset():
    dt = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    assert to_local(dt, -5) == datetime(2026, 1, 15, 7, 0)


def test_to_local_dst_new_york():
    # Needs a real timezone, not a fixed offset: NY is UTC-4 in July.
    dt = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
    assert to_local(dt, "America/New_York") == datetime(2026, 7, 15, 8, 0)


def test_add_months_clamps_day():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
