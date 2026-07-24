"""Singapore current weather via Open-Meteo (no API key)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx

SINGAPORE_LAT = 1.3521
SINGAPORE_LON = 103.8198

# WMO Weather interpretation codes (day) — subset for common cases
_WMO_LABELS: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    80: "Rain showers",
    81: "Moderate showers",
    82: "Violent showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

# Look this many upcoming hourly forecast points ahead (roughly the commute window)
# when deciding whether an umbrella is worth bringing.
_RAIN_LOOKAHEAD_HOURS = 4


@dataclass
class WeatherReport:
    summary: str
    reported_time: str
    rain_chance: int | None
    umbrella_advice: str

    @property
    def as_text(self) -> str:
        return "\n".join(
            [self.summary, f"Reported at {self.reported_time} SGT", self.umbrella_advice]
        )


def _label_for_code(code: int) -> str:
    return _WMO_LABELS.get(code, f"Weather code {code}")


def _format_time(raw: str | None) -> str:
    if not raw:
        return "unknown time"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return raw
    hour12 = dt.hour % 12 or 12
    suffix = "AM" if dt.hour < 12 else "PM"
    return f"{hour12}:{dt.minute:02d} {suffix}"


def _upcoming_rain_chance(data: dict, cur_time_raw: str | None) -> int | None:
    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    probs = hourly.get("precipitation_probability") or []
    if not times or not probs or not cur_time_raw:
        return None
    try:
        idx = times.index(cur_time_raw)
    except ValueError:
        idx = 0
    window = [p for p in probs[idx : idx + _RAIN_LOOKAHEAD_HOURS] if p is not None]
    if not window:
        return None
    return int(max(window))


def _umbrella_advice(rain_chance: int | None) -> str:
    if rain_chance is None:
        return "Umbrella advice unavailable — check the sky before heading out."
    if rain_chance >= 60:
        return f"☔ Bring an umbrella — {rain_chance}% chance of rain before you're at the office."
    if rain_chance >= 30:
        return f"🌂 Maybe pack an umbrella — {rain_chance}% chance of rain before you're at the office."
    return f"☀️ No umbrella needed — only {rain_chance}% chance of rain before you're at the office."


def fetch_singapore_weather(client: httpx.Client) -> WeatherReport:
    """Current conditions plus reported time and umbrella advice for Singapore."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={SINGAPORE_LAT}&longitude={SINGAPORE_LON}"
        "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        "&hourly=precipitation_probability"
        "&forecast_days=1"
        "&timezone=Asia%2FSingapore"
    )
    r = client.get(url, timeout=20.0)
    r.raise_for_status()
    data = r.json()
    cur = data.get("current") or {}
    temp = cur.get("temperature_2m")
    hum = cur.get("relative_humidity_2m")
    code = cur.get("weather_code")
    wind = cur.get("wind_speed_10m")
    cur_time_raw = cur.get("time")

    if temp is None or code is None:
        return WeatherReport(
            summary="Weather data temporarily unavailable.",
            reported_time=_format_time(cur_time_raw),
            rain_chance=None,
            umbrella_advice="Umbrella advice unavailable — check the sky before heading out.",
        )

    desc = _label_for_code(int(code))
    parts = [f"{desc}, {temp:.0f}°C"]
    if hum is not None:
        parts.append(f"{hum}% humidity")
    if wind is not None:
        parts.append(f"wind {wind:.0f} km/h")

    rain_chance = _upcoming_rain_chance(data, cur_time_raw)
    return WeatherReport(
        summary=", ".join(parts),
        reported_time=_format_time(cur_time_raw),
        rain_chance=rain_chance,
        umbrella_advice=_umbrella_advice(rain_chance),
    )
