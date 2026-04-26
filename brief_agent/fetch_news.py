"""Fetch headline links from RSS (no API key)."""

from __future__ import annotations

import feedparser
import httpx

# Singapore-focused world/top stories via Google News RSS
DEFAULT_RSS_URL = (
    "https://news.google.com/rss?hl=en-SG&gl=SG&ceid=SG:en"
)

# Cloud-reliable fallbacks tried in order when the primary returns empty or an HTML captcha page.
# Google News blocks cloud-provider IPs (GitHub Actions, AWS, etc.) and returns 200 HTML instead of RSS.
_FALLBACK_URLS: list[str] = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
]


def fetch_top_headlines(
    client: httpx.Client,
    url: str = DEFAULT_RSS_URL,
    limit: int = 5,
) -> list[tuple[str, str]]:
    """Return list of (title, link) for top entries, falling back to alternative sources if blocked."""
    urls_to_try = [url] + [u for u in _FALLBACK_URLS if u != url]

    for attempt_url in urls_to_try:
        try:
            resp = client.get(attempt_url, timeout=30.0, follow_redirects=True)
            resp.raise_for_status()
            # Google News returns an HTML captcha page (200 OK, content-type: text/html) from cloud IPs.
            content_type = resp.headers.get("content-type", "")
            if "html" in content_type and "xml" not in content_type and "rss" not in content_type:
                print(f"[news] {attempt_url} returned HTML (IP-blocked); trying next source")
                continue
            parsed = feedparser.parse(resp.content)
            out: list[tuple[str, str]] = []
            for entry in parsed.entries[:limit]:
                title = getattr(entry, "title", "").strip()
                link = getattr(entry, "link", "").strip()
                if title and link:
                    out.append((title, link))
            if out:
                if attempt_url != url:
                    print(f"[news] primary source blocked; using fallback: {attempt_url}")
                return out
            print(f"[news] {attempt_url} returned 0 entries; trying next source")
        except Exception as exc:
            print(f"[news] {attempt_url} failed ({exc}); trying next source")

    return []
