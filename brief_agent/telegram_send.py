"""Send HTML message via Telegram Bot API."""

from __future__ import annotations

import html
import httpx


def send_telegram_html(
    client: httpx.Client,
    token: str,
    chat_id: str,
    text: str,
) -> None:
    """Send message with HTML parse mode. Raises on API errors."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    r = client.post(url, json=payload, timeout=30.0)
    try:
        body = r.json()
    except ValueError:
        body = {}
    if r.is_success and body.get("ok") is True:
        return
    if r.is_success:
        raise RuntimeError(f"Telegram API error: {body}")
    desc = body.get("description") if isinstance(body, dict) else None
    if not desc:
        desc = (r.text or "")[:500] or r.reason_phrase
    raise RuntimeError(f"Telegram sendMessage failed HTTP {r.status_code}: {desc}")


def escape_html(s: str) -> str:
    return html.escape(s, quote=True)
