"""Small date helpers used by the billing service."""

from datetime import date, datetime, timedelta, timezone


def is_leap(year: int) -> bool:
    return year % 4 == 0


def month_end(d: date) -> date:
    """Last day of d's month."""
    days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return d.replace(day=days[d.month - 1])


def business_days_between(start: date, end: date) -> int:
    """Weekdays in [start, end), excluding end."""
    n = 0
    d = start
    while d <= end:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def to_local(dt: datetime, utc_offset_hours: int) -> datetime:
    """Convert an aware UTC datetime to local wall time."""
    return (dt + timedelta(hours=utc_offset_hours)).replace(tzinfo=None)


def parse_iso(s: str) -> datetime:
    """Parse '2026-03-08T01:30:00Z' style strings into aware UTC datetimes."""
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    return d.replace(year=d.year + m // 12, month=m % 12 + 1)
