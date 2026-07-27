"""Plain-text report rendering."""

from datetime import date


def _format_date(value: date, style: str) -> str:
    if style == "us":
        return value.strftime("%m/%d/%Y")
    return value.isoformat()


def render_summary(rows: list[dict[str, str]], date_format: str = "iso") -> str:
    """Render rows as a plain-text summary.

    date_format selects the date style: "iso" (the default) or "us".
    """
    lines = [f"{row['job']}: {row['status']}" for row in rows]
    stamp = _format_date(date.today(), date_format)
    return f"Report for {stamp}\n" + "\n".join(lines)
