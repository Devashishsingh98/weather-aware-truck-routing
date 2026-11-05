"""Batch Open-Meteo forecasts. Cells are rounded to 0.01° and cached for 30 minutes.

Rain is the liquid `rain` variable and snow is `snowfall`, both in inches per
hour via precipitation_unit=inch. Wind is the 10 m wind speed in mph, not the gust.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.cache import cache

from planner.services.config import OPEN_METEO_URL
from planner.services.errors import ExternalServiceError, PlannerError
from planner.services.forecast import HourlySeries, parse_open_meteo
from planner.services.geo import LatLon
from planner.services.http import get_json

BATCH_SIZE = 40


def grid_key(point: LatLon) -> tuple[float, float]:
    return (round(point.lat, 2), round(point.lon, 2))


def fetch_series(points: list[LatLon], latest: datetime) -> dict[tuple[float, float], HourlySeries]:
    """Fetch hourly wind, rain, and snow through `latest`.

    The window is only as long as the haul needs, and the cache key includes
    that window so a short trip cannot reuse a forecast that ends too soon.
    """

    past_days, forecast_days = _window(latest)
    unique: dict[tuple[float, float], LatLon] = {}
    for point in points:
        key = grid_key(point)
        unique.setdefault(key, LatLon(key[0], key[1]))
    resolved: dict[tuple[float, float], HourlySeries] = {}
    missing: list[tuple[tuple[float, float], LatLon]] = []
    for key, point in unique.items():
        cached = cache.get(_cache_key(key, past_days, forecast_days))
        if isinstance(cached, HourlySeries):
            resolved[key] = cached
        else:
            missing.append((key, point))
    for start in range(0, len(missing), BATCH_SIZE):
        batch = missing[start : start + BATCH_SIZE]
        payloads = _download([point for _key, point in batch], past_days, forecast_days)
        if len(payloads) != len(batch):
            raise ExternalServiceError("Weather service returned an unexpected number of locations.")
        for (key, _point), payload in zip(batch, payloads):
            if not isinstance(payload, dict):
                raise ExternalServiceError("Weather service returned an unexpected location.")
            try:
                series = parse_open_meteo(payload)
            except ValueError as exc:
                raise ExternalServiceError(str(exc)) from exc
            cache.set(_cache_key(key, past_days, forecast_days), series, timeout=60 * 30)
            resolved[key] = series
    return resolved


def fetch_timezone(point: LatLon) -> str:
    key = f"tz:v1:{point.lat:.2f}:{point.lon:.2f}"
    cached = cache.get(key)
    if isinstance(cached, str):
        return cached
    url = (
        f"{OPEN_METEO_URL}?latitude={point.lat:.4f}&longitude={point.lon:.4f}"
        "&timezone=auto&forecast_days=1&current=temperature_2m"
    )
    payload = get_json(url, timeout=10)
    if isinstance(payload, list):
        payload = payload[0] if payload else {}
    if not isinstance(payload, dict):
        return "UTC"
    name = str(payload.get("timezone") or "UTC")
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        name = "UTC"
    cache.set(key, name, timeout=60 * 60 * 24 * 7)
    return name


def localize_departure(raw: str, tzname: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise PlannerError("Departure must be an ISO date and time.") from exc
    if parsed.tzinfo is None:
        try:
            parsed = parsed.replace(tzinfo=ZoneInfo(tzname))
        except Exception as exc:
            raise PlannerError(f"Could not use timezone {tzname} for the origin.") from exc
    now = datetime.now(timezone.utc)
    instant = parsed.astimezone(timezone.utc)
    if instant < now - timedelta(hours=12):
        raise PlannerError("Departure is more than 12 hours in the past. The hourly forecast cannot cover it.")
    if instant > now + timedelta(days=6):
        raise PlannerError("Departure must be within the next 6 days so the hourly forecast covers the haul.")
    return parsed


def _window(latest: datetime) -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    latest_utc = latest.astimezone(timezone.utc)
    if latest_utc <= now:
        past_days = min(2, max(1, math.ceil((now - latest_utc).total_seconds() / 86400)))
        return past_days, 2
    ahead_days = (latest_utc - now).total_seconds() / 86400
    forecast_days = max(2, min(16, math.ceil(ahead_days) + 1))
    return 1, forecast_days


def _download(points: list[LatLon], past_days: int, forecast_days: int) -> list[object]:
    lats = ",".join(f"{point.lat:.4f}" for point in points)
    lons = ",".join(f"{point.lon:.4f}" for point in points)
    url = (
        f"{OPEN_METEO_URL}?latitude={lats}&longitude={lons}"
        "&hourly=wind_speed_10m,rain,snowfall"
        "&wind_speed_unit=mph&precipitation_unit=inch"
        f"&timezone=GMT&forecast_days={forecast_days}&past_days={past_days}"
    )
    payload = get_json(url, timeout=20)
    if isinstance(payload, dict) and payload.get("error"):
        reason = payload.get("reason") or "Weather service rejected the forecast request."
        raise ExternalServiceError(str(reason))
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return payload
    raise ExternalServiceError("Weather service returned an unexpected payload.")


def _cache_key(key: tuple[float, float], past_days: int, forecast_days: int) -> str:
    return f"wx:v2:{key[0]:.2f}:{key[1]:.2f}:{past_days}:{forecast_days}"
