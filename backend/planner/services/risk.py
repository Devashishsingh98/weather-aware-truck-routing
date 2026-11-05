"""Weather and load risk.

Bands are contiguous. A printed range such as "25–34" is the integer miles per
hour in that band, so the next printed threshold is the exclusive upper bound:
25.0 is Moderate, 34.9 is still Moderate, 35.0 is High.

Rain and snow columns share their endpoints (0.25 appears in both Moderate and
High). The shared endpoint goes to the worse band. No Travel for rain and snow
is a strict greater-than, so 1.00 in/hr of rain and 3.0 in/hr of snow stay Severe.

Load rules only raise wind risk. They never lower a band that rain or snow
already set, because the worst condition wins.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4


RISK_LABELS: dict[RiskLevel, str] = {
    RiskLevel.LOW: "Low",
    RiskLevel.MODERATE: "Moderate",
    RiskLevel.HIGH: "High",
    RiskLevel.SEVERE: "Severe",
    RiskLevel.NO_TRAVEL: "No Travel",
}

# Mileage-weighted average uses this scale. Low is 0 so a calm haul scores 0.
RISK_SCORE: dict[RiskLevel, int] = {level: int(level) for level in RiskLevel}


def label(level: RiskLevel) -> str:
    try:
        return RISK_LABELS[level]
    except KeyError as exc:
        raise ValueError(f"Unknown risk level: {level!r}") from exc


def _amount(name: str, value: float) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be a non-negative finite number")
    return number


def classify_wind(mph: float) -> RiskLevel:
    speed = _amount("wind speed", mph)
    if speed >= 55:
        return RiskLevel.NO_TRAVEL
    if speed >= 45:
        return RiskLevel.SEVERE
    if speed >= 35:
        return RiskLevel.HIGH
    if speed >= 25:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def classify_rain(inches_per_hour: float) -> RiskLevel:
    rate = _amount("rain", inches_per_hour)
    if rate > 1.00:
        return RiskLevel.NO_TRAVEL
    if rate >= 0.50:
        return RiskLevel.SEVERE
    if rate >= 0.25:
        return RiskLevel.HIGH
    if rate >= 0.10:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def classify_snow(inches_per_hour: float) -> RiskLevel:
    rate = _amount("snow", inches_per_hour)
    if rate > 3.0:
        return RiskLevel.NO_TRAVEL
    if rate >= 2.0:
        return RiskLevel.SEVERE
    if rate >= 1.0:
        return RiskLevel.HIGH
    if rate >= 0.5:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def apply_load_rule(wind_mph: float, load_lb: float, wind_risk: RiskLevel) -> tuple[RiskLevel, str | None]:
    """Raise wind risk for a heavy trailer. Does not look at rain or snow."""

    speed = _amount("wind speed", wind_mph)
    load = _amount("load weight", load_lb)
    if speed >= 55:
        return RiskLevel.NO_TRAVEL, "Wind at or above 55 mph is No Travel for any load."
    if speed >= 45 and load > 30_000:
        return RiskLevel.NO_TRAVEL, "Wind 45–54 mph with a load over 30,000 lb is No Travel."
    if speed >= 35 and load > 40_000:
        return RiskLevel.SEVERE, "Wind 35–44 mph with a load over 40,000 lb is raised to Severe."
    return wind_risk, None


@dataclass(frozen=True)
class RiskAssessment:
    wind_risk: RiskLevel
    wind_risk_after_load: RiskLevel
    rain_risk: RiskLevel
    snow_risk: RiskLevel
    overall: RiskLevel
    load_note: str | None
    factors: tuple[str, ...]


def assess(wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lb: float) -> RiskAssessment:
    wind_risk = classify_wind(wind_mph)
    rain_risk = classify_rain(rain_in_hr)
    snow_risk = classify_snow(snow_in_hr)
    wind_after, load_note = apply_load_rule(wind_mph, load_lb, wind_risk)
    overall = max(wind_after, rain_risk, snow_risk)
    factors: list[str] = []
    if wind_after == overall:
        factors.append("wind")
    if rain_risk == overall:
        factors.append("rain")
    if snow_risk == overall:
        factors.append("snow")
    return RiskAssessment(
        wind_risk=wind_risk,
        wind_risk_after_load=wind_after,
        rain_risk=rain_risk,
        snow_risk=snow_risk,
        overall=overall,
        load_note=load_note,
        factors=tuple(factors),
    )
