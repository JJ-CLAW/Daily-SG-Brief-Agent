"""Gemini agent: tool loop (RSS, weather, motivation, web search) → Telegram HTML brief."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from google import genai
from google.genai import types

from .fetch_news import fetch_top_headlines
from .fetch_weather import fetch_singapore_weather
from .motivation import load_motivation_lines, motivation_for_day
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

    def get_rss_headlines(limit: int | None = None) -> dict:
        """Fetch top news headlines from the configured RSS feed (title and URL per story). Use for general news; prefer this over web_search for headlines."""
        try:
            lim = int(limit) if limit is not None else headline_limit
        except (TypeError, ValueError):
            lim = headline_limit
        lim = max(1, min(lim, 20))
        pairs = fetch_top_headlines(http_client, url=rss_url, limit=lim)
        return {
            "headlines": [{"title": t, "url": u} for t, u in pairs],
        }

    def get_singapore_weather() -> dict:
        """Current weather in Singapore (conditions, temperature, humidity, wind)."""
        return {"summary": fetch_singapore_weather(http_client)}

    def get_todays_motivation() -> dict:
        """Today's motivational quote (deterministic for the Singapore calendar date)."""
        quote = motivation_for_day(motivation_lines, when)
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
        "Use the tools when you need data; do not invent headlines, URLs, or weather. "
        "Output ONLY Telegram HTML: use <b>, <i>, <a href=\"https://...\">, <code> as needed. "
        "Do not use Markdown. Escape plain text that is not inside tags (&, <, >). "
        "Structure: greeting with the date, top stories with clickable links when URLs exist, "
        "Singapore weather, thought for today (italic), short sign-off. "
        "Stay under 3800 characters. If a tool returns empty data, say so briefly instead of fabricating."
    )

    user_prompt = (
        f"Today is {day_label} (Singapore time). It is currently the {greeting}. "
        f"Build today's briefing with a 'Good {greeting}!' greeting. "
        "Call tools as needed. Include news (from RSS tool unless you deliberately supplement with web_search), "
        "Singapore weather, and today's motivation."
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
    return text
