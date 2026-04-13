"""CLI: `python -m brief_agent once` or `python -m brief_agent serve`."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

from .fetch_news import DEFAULT_RSS_URL, fetch_top_headlines
from .fetch_weather import fetch_singapore_weather
from .format_brief import format_brief
from .motivation import load_motivation_lines, motivation_for_day
from .telegram_send import send_telegram_html

try:
    from .gemini_brief import generate_brief_with_gemini
except ImportError:  # pragma: no cover - optional until google-genai installed
    generate_brief_with_gemini = None  # type: ignore[misc, assignment]

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _print_gemini_failure_hints(err: BaseException) -> None:
    """Explain common Gemini 429 / quota messages (not always 'you used the whole budget')."""
    msg = str(err)
    if "RESOURCE_EXHAUSTED" in msg or "429" in msg or "quota" in msg.lower():
        print(
            "Hint: Automatic tool calling sends several generateContent requests per run "
            "(per-minute limits can trip before daily totals look full).",
            file=sys.stderr,
        )
    if "limit: 0" in msg or "free_tier" in msg.lower():
        print(
            "Hint: limit 0 on a model often means that model has no free quota for your "
            "project (e.g. deprecated model or billing not linked). Try GEMINI_MODEL=gemini-2.5-flash "
            "and see https://ai.google.dev/gemini-api/docs/troubleshooting",
            file=sys.stderr,
        )
    if "503" in msg or "UNAVAILABLE" in msg or "high demand" in msg.lower():
        print(
            "Hint: 503 from Google is usually temporary; retry in a few minutes or set "
            "GEMINI_MODEL to another Flash variant (e.g. gemini-2.5-flash-lite).",
            file=sys.stderr,
        )


def _env_path() -> Path:
    raw = os.environ.get("DAILY_BRIEF_ENV")
    return Path(raw) if raw else (PROJECT_ROOT / ".env")


def build_and_send() -> None:
    load_dotenv(_env_path())
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print(
            "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env (see .env.example).",
            file=sys.stderr,
        )
        sys.exit(1)

    motivations_path = Path(
        os.environ.get("MOTIVATIONS_FILE", str(PROJECT_ROOT / "motivations.txt"))
    ).expanduser()
    rss_url = os.environ.get("NEWS_RSS_URL", "").strip() or None
    headline_limit = int(os.environ.get("HEADLINE_COUNT", "5"))

    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    when = datetime.now(ZoneInfo("Asia/Singapore"))
    rss = rss_url or DEFAULT_RSS_URL
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()

    with httpx.Client(headers={"User-Agent": ua}) as client:
        if gemini_key and generate_brief_with_gemini is not None:
            try:
                message = generate_brief_with_gemini(
                    http_client=client,
                    rss_url=rss,
                    headline_limit=headline_limit,
                    motivations_path=motivations_path,
                    when=when,
                    model=os.environ.get("GEMINI_MODEL", "").strip() or None,
                    api_key=gemini_key,
                )
            except Exception as err:
                print(f"Gemini agent failed ({err}); using template brief.", file=sys.stderr)
                _print_gemini_failure_hints(err)
                headlines = fetch_top_headlines(
                    client, url=rss, limit=headline_limit
                )
                weather = fetch_singapore_weather(client)
                motivation_lines = load_motivation_lines(motivations_path)
                motivation = motivation_for_day(motivation_lines, when)
                message = format_brief(headlines, weather, motivation, when=when)
        else:
            if gemini_key and generate_brief_with_gemini is None:
                print(
                    "GEMINI_API_KEY is set but google-genai is not installed; "
                    "using template brief. pip install -r requirements.txt",
                    file=sys.stderr,
                )
            headlines = fetch_top_headlines(client, url=rss, limit=headline_limit)
            weather = fetch_singapore_weather(client)
            motivation_lines = load_motivation_lines(motivations_path)
            motivation = motivation_for_day(motivation_lines, when)
            message = format_brief(headlines, weather, motivation, when=when)
        if len(message) > 4000:
            message = message[:3997] + "..."
        send_telegram_html(client, token, chat_id, message)
    print("Brief sent to Telegram.")


def cmd_serve() -> None:
    tz = ZoneInfo("Asia/Singapore")
    scheduler = BlockingScheduler(timezone=tz)
    scheduler.add_job(
        build_and_send,
        CronTrigger(hour=9, minute=30, timezone=tz),
        id="morning_brief",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    print("Scheduler running: daily brief at 09:30 Asia/Singapore. Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily morning Telegram briefing.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("once", help="Fetch data and send one message now")
    sub.add_parser("serve", help="Run scheduler (09:30 SGT every day)")
    args = parser.parse_args()
    if args.cmd == "once":
        build_and_send()
    elif args.cmd == "serve":
        cmd_serve()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
