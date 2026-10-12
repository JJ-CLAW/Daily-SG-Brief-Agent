"""Singapore air quality (PSI) from NEA via data.gov.sg (no API key)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

PSI_URL = "https://api-open.data.gov.sg/v2/real-time/api/psi"
_SGT = ZoneInfo("Asia/Singapore")


@dataclass
class AirQualityReport:
    summary: str
    reading_time: str

    @property
    def as_text(self) -> str:
        return f"{self.summary} (as of {self.reading_time} SGT)"


def _band(psi: int) -> str:
    if psi <= 50:
        return "🟢 Good"
    if psi <= 100:
        return "🟡 Moderate"
    if psi <= 200:
        return "🟠 Unhealthy"
    if psi <= 300:
        return "🔴 Very unhealthy"
    return "🟣 Hazardous"


def _format_time(dt: datetime) -> str:
    return f"{dt.hour % 12 or 12}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"


def fetch_singapore_air_quality(
    client: httpx.Client, when: datetime | None = None
) -> AirQualityReport:
    """24-hour PSI and PM2.5 for the NEA reading at (or just before) `when`."""
    when = (when or datetime.now(_SGT)).astimezone(_SGT)
    r = client.get(PSI_URL, params={"date": when.strftime("%Y-%m-%d")}, timeout=20.0)
    r.raise_for_status()
    items = (r.json().get("data") or {}).get("items") or []

    # Latest hourly reading at or before the message time.
    best: tuple[datetime, dict] | None = None
    for item in items:
        try:
            ts = datetime.fromisoformat(item["timestamp"]).astimezone(_SGT)
        except (KeyError, ValueError):
            continue
        if ts <= when and (best is None or ts > best[0]):
            best = (ts, item.get("readings") or {})
    if best is None:
        return AirQualityReport("Air quality data temporarily unavailable.", "unknown time")

    ts, readings = best
    psi = readings.get("psi_twenty_four_hourly") or {}
    pm25 = readings.get("pm25_twenty_four_hourly") or {}
    national = psi.get("national") or (max(psi.values()) if psi else None)
    if national is None:
        return AirQualityReport("Air quality data temporarily unavailable.", _format_time(ts))

    regions = ", ".join(
        f"{name.capitalize()} {psi[name]}"
        for name in ("north", "south", "east", "west", "central")
        if name in psi
    )
    summary = f"{_band(int(national))} — 24h PSI {int(national)}"
    if pm25:
        summary += f", PM2.5 {int(max(pm25.values()))} µg/m³ (highest region)"
    if regions:
        summary += f"\n{regions}"
    return AirQualityReport(summary, _format_time(ts))
