"""Fetch headline links from RSS (no API key)."""

from __future__ import annotations

import feedparser
import httpx

# Singapore-focused world/top stories via Google News RSS
DEFAULT_RSS_URL = (
    "https://news.google.com/rss?hl=en-SG&gl=SG&ceid=SG:en"
)


def fetch_top_headlines(
    client: httpx.Client,
    url: str = DEFAULT_RSS_URL,
    limit: int = 5,
) -> list[tuple[str, str]]:
    """Return list of (title, link) for top entries."""
    resp = client.get(url, timeout=30.0, follow_redirects=True)
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)
    out: list[tuple[str, str]] = []
    for entry in parsed.entries[:limit]:
        title = getattr(entry, "title", "").strip()
        link = getattr(entry, "link", "").strip()
        if title and link:
            out.append((title, link))
    return out
