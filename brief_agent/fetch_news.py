"""Fetch headline links from RSS (no API key)."""

from __future__ import annotations

import feedparser
import httpx
try:
    from googlenewsdecoder import gnewsdecoder
except ImportError as _exc:  # keep the brief working without link decoding
    print(f"[news] googlenewsdecoder unavailable ({_exc}); Google News links stay undecoded")
    gnewsdecoder = None  # type: ignore[assignment]

# Singapore-focused world/top stories via Google News RSS
DEFAULT_RSS_URL = (
    "https://news.google.com/rss?hl=en-SG&gl=SG&ceid=SG:en"
)

# Cloud-reliable fallbacks tried in order when the primary returns empty or an HTML captcha page.
# Google News blocks cloud-provider IPs (GitHub Actions, AWS, etc.) and returns 200 HTML instead of RSS.
_FALLBACK_URLS: list[str] = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
]

_GOOGLE_NEWS_HOST = "news.google.com"


def _link_is_reachable(client: httpx.Client, url: str) -> bool:
    """Best-effort check that a headline link actually resolves."""
    try:
        resp = client.head(url, timeout=8.0, follow_redirects=True)
        if resp.status_code < 400:
            return True
        if resp.status_code in (405, 403):
            # Some servers reject HEAD; retry with GET before giving up.
            resp = client.get(url, timeout=8.0, follow_redirects=True)
            return resp.status_code < 400
        return False
    except Exception:
        return False


def _resolve_link(client: httpx.Client, link: str) -> str | None:
    """Return a link the user can actually open, or None if it's dead.

    Google News RSS links are opaque redirect IDs (news.google.com/rss/articles/<id>) whose
    server-side redirect can silently break — Google resolves the ID to an "invalid web address"
    for some entries, which browsers surface as a redirect error even though our own HEAD/GET
    check against the intermediate news.google.com page returns 200 OK. Decoding to the real
    publisher URL up front avoids sending readers through that redirect at all.
    """
    try:
        is_google_news = httpx.URL(link).host == _GOOGLE_NEWS_HOST
    except Exception:
        is_google_news = False

    if is_google_news and gnewsdecoder is not None:
        try:
            result = gnewsdecoder(link, interval=1)
        except Exception as exc:
            print(f"[news] gnewsdecoder error for {link}: {exc}")
            return None
        if not result or not result.get("status"):
            msg = (result or {}).get("message") if result else "no result"
            print(f"[news] could not decode Google News link ({msg}): {link}")
            return None
        decoded = result.get("decoded_url")
        if not decoded:
            return None
        link = decoded

    return link if _link_is_reachable(client, link) else None


def fetch_top_headlines(
    client: httpx.Client,
    url: str = DEFAULT_RSS_URL,
    limit: int = 5,
) -> list[tuple[str, str]]:
    """Return list of (title, link) for top entries, falling back to alternative sources if blocked
    or if individual links do not resolve."""
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
            candidates: list[tuple[str, str]] = []
            for entry in parsed.entries:
                title = getattr(entry, "title", "").strip()
                link = getattr(entry, "link", "").strip()
                if title and link:
                    candidates.append((title, link))
            if not candidates:
                print(f"[news] {attempt_url} returned 0 entries; trying next source")
                continue

            # Check more candidates than `limit` so a few dead/timed-out redirect links
            # don't shrink the final headline count.
            out: list[tuple[str, str]] = []
            checked = 0
            for title, link in candidates[: limit * 3]:
                checked += 1
                resolved = _resolve_link(client, link)
                if resolved:
                    out.append((title, resolved))
                    if len(out) >= limit:
                        break
                else:
                    print(f"[news] dropping unreachable link: {link}")
            if out:
                if attempt_url != url:
                    print(f"[news] primary source blocked; using fallback: {attempt_url}")
                return out
            print(f"[news] {attempt_url}: no reachable links among {checked} checked; trying next source")
        except Exception as exc:
            print(f"[news] {attempt_url} failed ({exc}); trying next source")

    return []
