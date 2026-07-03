from datetime import date

from app.dates import format_report_date, format_report_month


def test_format_report_date() -> None:
    assert format_report_date(date(2026, 7, 2)) == "2026-07-02"


def test_format_report_month() -> None:
    assert format_report_month(date(2026, 7, 2)) == "2026-07"
