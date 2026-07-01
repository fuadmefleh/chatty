"""Weather lookup using Open-Meteo (free, no API key required).

Geocodes a location name via Open-Meteo's geocoding API, then fetches
current conditions and a short forecast.
"""
import aiohttp
from typing import Optional

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes
WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snowfall", 73: "Moderate snowfall", 75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


async def geocode(location: str) -> Optional[dict]:
    """Resolve a location name to lat/lon."""
    async with aiohttp.ClientSession() as session:
        async with session.get(GEOCODE_URL, params={"name": location, "count": 1, "language": "en"}) as resp:
            data = await resp.json()
            results = data.get("results")
            if not results:
                return None
            r = results[0]
            return {
                "name": r.get("name"),
                "region": r.get("admin1", ""),
                "country": r.get("country", ""),
                "latitude": r["latitude"],
                "longitude": r["longitude"],
            }


async def get_weather(latitude: float, longitude: float) -> dict:
    """Fetch current weather and 3-day forecast from Open-Meteo."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "forecast_days": 3,
        "timezone": "auto",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(WEATHER_URL, params=params) as resp:
            return await resp.json()


async def fetch_weather(location: str) -> dict:
    """Main entry point: geocode + weather lookup."""
    geo = await geocode(location)
    if not geo:
        return {"success": False, "error": f"Could not find location: {location}"}

    weather = await get_weather(geo["latitude"], geo["longitude"])

    current = weather.get("current", {})
    daily = weather.get("daily", {})

    result = {
        "success": True,
        "location": f"{geo['name']}, {geo['region']}, {geo['country']}".strip(", "),
        "current": {
            "temperature_f": current.get("temperature_2m"),
            "feels_like_f": current.get("apparent_temperature"),
            "humidity_pct": current.get("relative_humidity_2m"),
            "wind_speed_mph": current.get("wind_speed_10m"),
            "wind_direction_deg": current.get("wind_direction_10m"),
            "condition": WMO_CODES.get(current.get("weather_code"), "Unknown"),
        },
        "forecast": [],
    }

    dates = daily.get("time", [])
    for i, date in enumerate(dates):
        result["forecast"].append({
            "date": date,
            "high_f": daily["temperature_2m_max"][i],
            "low_f": daily["temperature_2m_min"][i],
            "precipitation_chance_pct": daily["precipitation_probability_max"][i],
            "condition": WMO_CODES.get(daily["weather_code"][i], "Unknown"),
        })

    return result
