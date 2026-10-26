"""US-locale formatting helpers: dollars like $1,234.56, dates like 10/25/2026."""

from datetime import date, datetime


def format_usd(amount: float) -> str:
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.2f}"


def format_us_date(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%m/%d/%Y")
