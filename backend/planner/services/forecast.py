"""Pure Open-Meteo hourly parsing and the hour a truck is inside.

Open-Meteo hourly values are for the hour starting at the timestamp. An ETA of
14:20 uses the 14:00 value. Times are compared in UTC.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class HourlySeries:
    times: list[datetime]
    wind_mph: list[float | None]
    rain_in_hr: list[float | None]
    snow_in_hr: list[float | None]


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_open_meteo(payload: dict) -> HourlySeries:
    if payload.get("error"):
        reason = payload.get("reason") or "Weather service rejected the forecast request."
        raise ValueError(str(reason))
    hourly = payload.get("hourly") or {}
    times_raw = hourly.get("time") or []
    winds = hourly.get("wind_speed_10m") or []
    rains = hourly.get("rain") or []
    snows = hourly.get("snowfall") or []
    if not times_raw or not (len(times_raw) == len(winds) == len(rains) == len(snows)):
        raise ValueError("Weather forecast was missing hourly wind, rain, or snow.")
    return HourlySeries(
        times=[parse_utc(value) for value in times_raw],
        wind_mph=[_optional_float(value) for value in winds],
        rain_in_hr=[_optional_float(value) for value in rains],
        snow_in_hr=[_optional_float(value) for value in snows],
    )


def hour_index(times: list[datetime], eta: datetime) -> tuple[int, bool]:
    """Return the hour containing eta, and whether it was clamped to the window."""

    if not times:
        raise ValueError("forecast has no hours")
    if eta.tzinfo is None:
        raise ValueError("eta must be timezone-aware")
    eta_utc = eta.astimezone(timezone.utc)
    first = times[0]
    last = times[-1]
    if eta_utc < first:
        return 0, True
    if eta_utc >= last + timedelta(hours=1):
        return len(times) - 1, True
    lo = 0
    hi = len(times) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if times[mid] <= eta_utc:
            lo = mid
        else:
            hi = mid - 1
    return lo, False


def read_conditions(
    series: HourlySeries,
    eta: datetime,
) -> tuple[float, float, float, bool, bool, datetime]:
    """Wind mph, rain in/hr, snow in/hr, imputed, clamped, forecast hour."""

    index, clamped = hour_index(series.times, eta)
    wind = series.wind_mph[index]
    rain = series.rain_in_hr[index]
    snow = series.snow_in_hr[index]
    imputed = wind is None or rain is None or snow is None or _negative(wind) or _negative(rain) or _negative(snow)
    return (
        0.0 if wind is None or wind < 0 else wind,
        0.0 if rain is None or rain < 0 else rain,
        0.0 if snow is None or snow < 0 else snow,
        imputed,
        clamped,
        series.times[index],
    )


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _negative(value: float | None) -> bool:
    return value is not None and value < 0
