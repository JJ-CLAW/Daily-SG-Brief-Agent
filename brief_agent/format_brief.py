"""Build friendly morning briefing text (HTML for Telegram)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .telegram_send import escape_html


def _friendly_date_singapore(when: datetime) -> str:
    dt = when.astimezone(ZoneInfo("Asia/Singapore"))
    dow = dt.strftime("%A")
    month = dt.strftime("%B")
    return f"{dow}, {dt.day} {month} {dt.year}"


def format_brief(
    headlines: list[tuple[str, str]],
    weather_line: str,
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
        lines.append("• No headlines fetched — check your network or RSS source.")
    else:
        for title, link in headlines:
            safe_title = escape_html(title)
            safe_link = escape_html(link)
            lines.append(f'• <a href="{safe_link}">{safe_title}</a>')

    lines.extend(["", "<b>Weather in Singapore</b>", escape_html(weather_line), ""])

    lines.extend(
        [
            "<b>Thought for today</b>",
            f"<i>{escape_html(motivation)}</i>",
        ]
    )

    lines.extend(["", "Have a great day! 🌿"])
    return "\n".join(lines)
