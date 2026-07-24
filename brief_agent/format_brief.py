"""Build friendly morning briefing text (HTML for Telegram)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .fetch_weather import WeatherReport
from .telegram_send import escape_html


def _friendly_date_singapore(when: datetime) -> str:
    dt = when.astimezone(ZoneInfo("Asia/Singapore"))
    dow = dt.strftime("%A")
    month = dt.strftime("%B")
    return f"{dow}, {dt.day} {month} {dt.year}"


def format_brief(
    headlines: list[tuple[str, str]],
    weather: WeatherReport,
    motivation: str,
    when: datetime | None = None,
) -> str:
    when = when or datetime.now(ZoneInfo("Asia/Singapore"))
    day = _friendly_date_singapore(when)

    lines: list[str] = [
        "☀️ <b>Good morning!</b>",
        f"Here is your briefing for <i>{escape_html(day)}</i> (Singapore time).",
        "",
        "<b>Top stories</b>",
    ]
    if not headlines:
        lines.append("1. No headlines fetched — check your network or RSS source.")
    else:
        for i, (title, link) in enumerate(headlines, start=1):
            safe_title = escape_html(title)
            safe_link = escape_html(link)
            lines.append(f'{i}. <a href="{safe_link}">{safe_title}</a>')

    reported_time = escape_html(weather.reported_time)
    lines.extend(
        [
            "",
            f"<b>SG Weather</b>",
            escape_html(weather.summary),
            escape_html(weather.umbrella_advice),
            "",
        ]
    )

    lines.extend(
        [
            "<b>Thought for today</b>",
            f"<i>{escape_html(motivation)}</i>",
        ]
    )

    lines.extend(["", "Have a great day! 🌿"])
    return "\n".join(lines)
