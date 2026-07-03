"""Date-formatting helpers."""

from datetime import date


def format_report_date(value: date) -> str:
    """Format a date as 'YYYY-MM-DD' for report headers."""
    return value.strftime("%Y-%m-%d")


def format_report_month(value: date) -> str:
    """Format a date as 'YYYY-MM' for monthly report headers."""
    return value.strftime("%Y-%m")
