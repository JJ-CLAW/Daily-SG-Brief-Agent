"""Singapore current weather via Open-Meteo (no API key)."""

from __future__ import annotations

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


def _label_for_code(code: int) -> str:
    return _WMO_LABELS.get(code, f"Weather code {code}")


def fetch_singapore_weather(client: httpx.Client) -> str:
    """One-line human summary for Singapore (current conditions)."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={SINGAPORE_LAT}&longitude={SINGAPORE_LON}"
        "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
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
    if temp is None or code is None:
        return "Weather data temporarily unavailable."
    desc = _label_for_code(int(code))
    parts = [
        f"{desc}, {temp:.0f}°C",
    ]
    if hum is not None:
        parts.append(f"{hum}% humidity")
    if wind is not None:
        parts.append(f"wind {wind:.0f} km/h")
    return ", ".join(parts)
