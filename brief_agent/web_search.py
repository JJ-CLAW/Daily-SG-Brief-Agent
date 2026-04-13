"""Lightweight web lookup for LLM tools (DuckDuckGo Instant Answer API, no API key)."""

from __future__ import annotations

from typing import Any

import httpx


def duckduckgo_instant_answer(client: httpx.Client, query: str) -> dict[str, Any]:
    """Return a compact JSON-serializable summary for the model."""
    q = query.strip()
    if not q:
        return {"error": "empty_query"}

    r = client.get(
        "https://api.duckduckgo.com/",
        params={
            "q": q,
            "format": "json",
            "no_html": "1",
            "no_redirect": "1",
        },
        timeout=25.0,
    )
    r.raise_for_status()
    data = r.json()

    abstract = (data.get("AbstractText") or "").strip()
    url = (data.get("AbstractURL") or "").strip()
    heading = (data.get("Heading") or "").strip()

    related_snippets: list[str] = []
    for item in (data.get("RelatedTopics") or [])[:6]:
        if isinstance(item, dict) and item.get("Text"):
            t = str(item["Text"]).strip()
            if t:
                related_snippets.append(t)
        elif isinstance(item, dict) and "Topics" in item:
            for sub in (item.get("Topics") or [])[:3]:
                if isinstance(sub, dict) and sub.get("Text"):
                    related_snippets.append(str(sub["Text"]).strip())

    return {
        "query": q,
        "heading": heading or None,
        "abstract": abstract or None,
        "source_url": url or None,
        "related_snippets": related_snippets,
    }
