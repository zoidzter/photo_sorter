"""Event detection for key dates like Christmas, Halloween, Easter, etc."""
from datetime import date, timedelta
from typing import Optional


def _easter_date(year: int) -> date:
    # Anonymous Gregorian algorithm
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def detect_event(dt: date) -> Optional[str]:
    """Return an event name for the given date, or None if not a known event window."""
    if dt is None:
        return None

    year = dt.year
    # Custom important dates (month, day) -> label
    CUSTOM_DATES = {
        (12, 1): "EnzoBirthday",
        (1, 16): "AxelBirthday",
        (5, 21): "AmhaoinBirthday",
        (3, 15): "PatrickBirthday",
    }
    # Check custom dates first (year-agnostic)
    key = (dt.month, dt.day)
    if key in CUSTOM_DATES:
        return CUSTOM_DATES[key]
    # New Year: Jan 1 +/- 1 day
    if dt.month == 1 and dt.day in (1, 2):
        return "NewYear"
    # Valentine's Day: Feb 14
    if dt.month == 2 and dt.day == 14:
        return "Valentines"
    # St Patrick's Day: Mar 17
    if dt.month == 3 and dt.day == 17:
        return "StPatricks"
    # Easter window: Good Friday to Easter Monday
    easter = _easter_date(year)
    if easter - timedelta(days=2) <= dt <= easter + timedelta(days=1):
        return "Easter"
    # Mother's Day (US): second Sunday in May (not worldwide). We'll not include as default.
    # Halloween: Oct 25-31
    if dt.month == 10 and 25 <= dt.day <= 31:
        return "Halloween"
    # Thanksgiving (US): fourth Thursday of November
    if dt.month == 11 and dt.weekday() == 3:
        # find fourth Thursday
        first = date(year, 11, 1)
        # day offset to first Thursday
        offset = (3 - first.weekday()) % 7
        fourth_thursday = first + timedelta(days=offset + 21)
        if dt == fourth_thursday:
            return "Thanksgiving"
    # Christmas: Dec 24-26 (Eve, Day, Boxing Day)
    if dt.month == 12 and dt.day in (24, 25, 26):
        return "Christmas"
    # New Year's Eve
    if dt.month == 12 and dt.day == 31:
        return "NewYearsEve"

    return None
 