"""Load motivational lines from a file and pick one per calendar day (Singapore time)."""

from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

_DEFAULT_QUOTES = (
    "Progress beats perfection. Do one thing that matters today.",
    "You do not have to see the whole staircase — just take the first step.",
    "Be gentle with yourself; you are learning and growing every day.",
    "Energy flows where attention goes. Aim it at what you want, not what you fear.",
    "Today is a fresh chance to show up as the person you want to become.",
)


def load_motivation_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    items: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("- ", "* ", "• ")):
            line = line[2:].strip()
        items.append(line)
    return items


def motivation_for_day(lines: list[str], when: datetime) -> str:
    """Deterministic offline fallback: same pseudo-random pick all day for a given local pool."""
    pool = list(lines) if lines else list(_DEFAULT_QUOTES)
    dt = when.astimezone(ZoneInfo("Asia/Singapore"))
    seed = dt.year * 10_000 + dt.month * 100 + dt.day
    return random.Random(seed).choice(pool)


def fetch_daily_motivation(client: httpx.Client, lines: list[str], when: datetime) -> str:
    """A fresh quote each day from a public quote API, falling back to the local pool on failure."""
    try:
        r = client.get("https://zenquotes.io/api/today", timeout=10.0)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            item = data[0]
            quote = str(item.get("q") or "").strip()
            author = str(item.get("a") or "").strip()
            if quote:
                return f"{quote} — {author}" if author else quote
    except Exception as exc:
        print(f"[motivation] zenquotes fetch failed ({exc}); using local pool")
    return motivation_for_day(lines, when)
