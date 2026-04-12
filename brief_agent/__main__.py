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

PROJECT_ROOT = Path(__file__).resolve().parent.parent


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
    with httpx.Client(headers={"User-Agent": ua}) as client:
        headlines = fetch_top_headlines(
            client,
            url=rss_url or DEFAULT_RSS_URL,
            limit=headline_limit,
        )
        weather = fetch_singapore_weather(client)
        motivation_lines = load_motivation_lines(motivations_path)
        when = datetime.now(ZoneInfo("Asia/Singapore"))
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
