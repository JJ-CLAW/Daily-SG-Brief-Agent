"""Gemini agent: tool loop (RSS, weather, motivation, web search) → Telegram HTML brief."""

from __future__ import annotations

import html as html_module
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from google import genai
from google.genai import types

from .fetch_news import fetch_top_headlines
from .fetch_weather import fetch_singapore_weather
from .motivation import fetch_daily_motivation, load_motivation_lines
from .web_search import duckduckgo_instant_answer


def _friendly_date_singapore(when: datetime) -> str:
    dt = when.astimezone(ZoneInfo("Asia/Singapore"))
    return dt.strftime("%A, %d %B %Y")


def _time_of_day_greeting(when: datetime) -> str:
    hour = when.astimezone(ZoneInfo("Asia/Singapore")).hour
    if hour < 12:
        return "morning"
    elif hour < 17:
        return "afternoon"
    else:
        return "evening"


# Telegram's HTML parser only understands &amp; &lt; &gt; &quot; (and numeric &#39;) — any other
# named entity (e.g. &mdash;, &deg;) shows up literally instead of rendering. Gemini sometimes
# "escapes" ordinary punctuation into entities even when told not to, so unescape everything
# except the handful Telegram actually needs kept as markup.
_SAFE_ENTITIES = {"amp;", "lt;", "gt;", "quot;", "#39;", "apos;"}


def _fix_stray_entities(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        entity = match.group(0)
        if entity[1:] in _SAFE_ENTITIES:
            return entity
        char = html_module.unescape(entity)
        return char if char != entity else entity

    return re.sub(r"&#?[a-zA-Z0-9]+;", repl, text)


def generate_brief_with_gemini(
    *,
    http_client: httpx.Client,
    rss_url: str,
    headline_limit: int,
    motivations_path: Path,
    when: datetime,
    model: str | None = None,
    max_tool_rounds: int | None = None,
    api_key: str | None = None,
) -> str:
    """Run Gemini with automatic function calling; return HTML for Telegram."""
    key = (api_key or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key:
        raise ValueError("GEMINI_API_KEY is required for the Gemini agent path.")

    # Default to 2.5 Flash: 2.0 Flash is deprecated and often returns 429 with free_tier limit 0.
    resolved_model = (model or os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash").strip()
    max_calls = max_tool_rounds
    if max_calls is None:
        raw = os.environ.get("GEMINI_MAX_TOOL_ROUNDS", "12").strip()
        max_calls = int(raw) if raw.isdigit() else 12
    max_calls = max(1, min(max_calls, 32))

    motivation_lines = load_motivation_lines(motivations_path)
    day_label = _friendly_date_singapore(when)

    # Pre-fetch core data before entering the Gemini tool loop.
    # This guarantees weather and news appear in the brief even if Gemini skips tool calls
    # (which it can do with automatic_function_calling when it thinks it already knows the answer).
    _prefetch_headlines: list[tuple[str, str]] = []
    _prefetch_weather_summary = ""
    _prefetch_weather_time = ""
    _prefetch_weather_advice = ""
    _prefetch_motivation = fetch_daily_motivation(http_client, motivation_lines, when)
    try:
        _prefetch_headlines = fetch_top_headlines(http_client, url=rss_url, limit=headline_limit)
        print(f"[prefetch] headlines: {len(_prefetch_headlines)}")
    except Exception as exc:
        print(f"[prefetch] headlines failed: {exc}")
    try:
        _report = fetch_singapore_weather(http_client)
        _prefetch_weather_summary = _report.summary
        _prefetch_weather_time = _report.reported_time
        _prefetch_weather_advice = _report.umbrella_advice
        print(f"[prefetch] weather: {_report.as_text!r}")
    except Exception as exc:
        print(f"[prefetch] weather failed: {exc}")

    def get_rss_headlines(limit: int | None = None) -> dict:
        """Fetch top news headlines from the configured RSS feed (title and URL per story). Use for general news; prefer this over web_search for headlines."""
        try:
            lim = int(limit) if limit is not None else headline_limit
        except (TypeError, ValueError):
            lim = headline_limit
        lim = max(1, min(lim, 20))
        try:
            pairs = fetch_top_headlines(http_client, url=rss_url, limit=lim)
            print(f"[tool] get_rss_headlines: got {len(pairs)} headlines")
            return {"headlines": [{"title": t, "url": u} for t, u in pairs]}
        except Exception as exc:
            print(f"[tool] get_rss_headlines failed: {exc}")
            return {"headlines": [], "error": f"RSS fetch failed: {exc}"}

    def get_singapore_weather() -> dict:
        """Current weather in Singapore: conditions, temperature, humidity, wind, the time it was
        reported, and umbrella advice based on the chance of rain before you reach the office."""
        try:
            report = fetch_singapore_weather(http_client)
            print(f"[tool] get_singapore_weather: {report.as_text!r}")
            return {
                "summary": report.summary,
                "reported_time": report.reported_time,
                "rain_chance_percent": report.rain_chance,
                "umbrella_advice": report.umbrella_advice,
            }
        except Exception as exc:
            print(f"[tool] get_singapore_weather failed: {exc}")
            return {"summary": "Weather data temporarily unavailable.", "error": str(exc)}

    def get_todays_motivation() -> dict:
        """Today's motivational quote (fetched fresh daily, falling back to a local pool)."""
        quote = fetch_daily_motivation(http_client, motivation_lines, when)
        print(f"[tool] get_todays_motivation: {quote[:60]}...")
        return {"quote": quote}

    def web_search(query: str) -> dict:
        """Search the public web for timely facts (e.g. sports, releases) not covered by RSS or weather. Pass a short, specific query."""
        try:
            return duckduckgo_instant_answer(http_client, query)
        except Exception as exc:  # noqa: BLE001 — return error to model, keep tool loop alive
            return {"query": query, "error": str(exc), "abstract": None}

    greeting = _time_of_day_greeting(when)

    system_instruction = (
        "You write a daily briefing message for Telegram. "
        "The user prompt contains pre-fetched data (weather, headlines, motivation) — use it directly. "
        "Do not call get_rss_headlines or get_singapore_weather when that data is already supplied. "
        "Only call web_search if the HEADLINES section is empty and you need to find news. "
        "Do not invent headlines, URLs, or weather. "
        "WEATHER_TIME/WEATHER_SUMMARY/WEATHER_ADVICE are the reported time, conditions, and umbrella "
        "advice — include all three, do not drop the umbrella advice. The weather section header must "
        "read exactly '<b>SG Weather</b>' "
        "filled in, followed by WEATHER_SUMMARY and WEATHER_ADVICE each on their own line. "
        "List top stories as a numbered list (1. 2. 3. ...), not bullets. "
        "Output ONLY Telegram HTML: use <b>, <i>, <a href=\"https://...\">, <code> as needed. "
        "Never use <br>, <br/>, <div>, <p>, or any other unsupported tag — use plain newlines (\\n) for line breaks. "
        "Do not use Markdown. Telegram's HTML parser ONLY understands &amp; &lt; &gt; &quot; as entities — "
        "do not write any other HTML entity (no &mdash;, &deg;, &ndash;, &nbsp;, &hellip;, curly-quote "
        "entities, etc.). Use the real Unicode character directly for things like em dashes (—) and "
        "degree signs (°); only escape a literal &, <, or > that is not part of a tag. "
        "Structure: greeting with the date, numbered top stories with clickable links when URLs exist, "
        "Singapore weather (with reported time in the header and umbrella advice), thought for today "
        "(italic), short sign-off. "
        "Stay under 3800 characters."
    )

    _headline_block = (
        "\n".join(f"{i}. {t} <{u}>" for i, (t, u) in enumerate(_prefetch_headlines, start=1))
        if _prefetch_headlines
        else "(none — call web_search to find today's top Singapore or world news)"
    )

    user_prompt = (
        f"Today is {day_label} (Singapore time). It is currently the {greeting}. "
        f"Build today's briefing with a 'Good {greeting}!' greeting.\n\n"
        f"PRE-FETCHED DATA (use directly, do not re-fetch):\n"
        f"WEATHER_TIME: {_prefetch_weather_time or 'unknown'}\n"
        f"WEATHER_SUMMARY: {_prefetch_weather_summary or 'unavailable'}\n"
        f"WEATHER_ADVICE: {_prefetch_weather_advice or ''}\n"
        f"MOTIVATION: {_prefetch_motivation}\n"
        f"HEADLINES:\n{_headline_block}"
    )

    client = genai.Client(api_key=key)
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=[
            get_rss_headlines,
            get_singapore_weather,
            get_todays_motivation,
            web_search,
        ],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            maximum_remote_calls=max_calls,
        ),
    )

    response = client.models.generate_content(
        model=resolved_model,
        contents=user_prompt,
        config=config,
    )

    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned an empty brief.")
    print(f"[gemini] response length={len(text)}; preview={text[:200]!r}")
    # Telegram HTML only allows a small tag subset; replace unsupported line-break tags with newlines.
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = _fix_stray_entities(text)
    return text
