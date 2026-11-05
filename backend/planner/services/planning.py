"""Wire geocoding, three routes, checkpoint weather, and the recommendation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from planner.services.errors import ExternalServiceError, PlannerError
from planner.services.forecast import read_conditions
from planner.services.geo import METERS_PER_MILE, LatLon, haversine_miles, simplify
from planner.services.geocode import Place
from planner.services.risk import RiskAssessment, assess, label
from planner.services.routing import RawRoute, build_three_routes
from planner.services.sampling import SamplePoint, sample_checkpoints
from planner.services.scoring import describe_recommendation, metrics_from_checkpoints, rank_routes
from planner.services.weather import fetch_series, fetch_timezone, grid_key, localize_departure

DISPLAY_TOLERANCE_DEG = 0.003


@dataclass
class ScoredCheckpoint:
    sample: SamplePoint
    wind_mph: float
    rain_in_hr: float
    snow_in_hr: float
    assessment: RiskAssessment
    imputed: bool
    clamped: bool
    forecast_hour: datetime


def plan_haul(
    origin: Place,
    destination: Place,
    departure_raw: str,
    load_lb: float,
    interval_miles: int,
) -> dict:
    origin_point = LatLon(origin.lat, origin.lon)
    destination_point = LatLon(destination.lat, destination.lon)
    if haversine_miles(origin_point, destination_point) < 1:
        raise PlannerError("Origin and destination are too close to compare routes.")
    timezone_name = fetch_timezone(origin_point)
    departure = localize_departure(departure_raw, timezone_name)
    raw_routes, route_note = build_three_routes(origin_point, destination_point)

    sampled: list[tuple[str, RawRoute, list[SamplePoint]]] = []
    forecast_points: list[LatLon] = []
    for index, raw in enumerate(raw_routes, start=1):
        samples = sample_checkpoints(
            raw.coords,
            raw.segment_distances_m,
            raw.segment_durations_s,
            interval_miles,
            departure,
        )
        sampled.append((f"route-{index}", raw, samples))
        forecast_points.extend(sample.point for sample in samples)

    latest_eta = departure + timedelta(seconds=max(raw.duration_seconds for _route_id, raw, _samples in sampled) + 3600)
    series_by_cell = fetch_series(forecast_points, latest_eta)
    built: list[tuple[str, RawRoute, list[ScoredCheckpoint]]] = []
    metrics = []
    names: dict[str, str] = {}
    any_imputed = False
    any_clamped = False
    for route_id, raw, samples in sampled:
        scored = [_score(sample, series_by_cell, load_lb) for sample in samples]
        any_imputed = any_imputed or any(item.imputed for item in scored)
        any_clamped = any_clamped or any(item.clamped for item in scored)
        distance_miles = raw.distance_meters / METERS_PER_MILE
        metric = metrics_from_checkpoints(
            route_id,
            [(item.sample.mile, item.assessment.overall) for item in scored],
            raw.duration_seconds,
            distance_miles,
        )
        metrics.append(metric)
        names[route_id] = raw.name
        built.append((route_id, raw, scored))

    ordered = rank_routes(metrics)
    rank_of = {metric.route_id: rank for rank, metric in enumerate(ordered, start=1)}
    metric_of = {metric.route_id: metric for metric in metrics}
    winner = ordered[0]
    warnings = _warnings(any_imputed, any_clamped)
    routes = [
        _public_route(route_id, raw, scored, metric_of[route_id], rank_of[route_id], winner.route_id)
        for route_id, raw, scored in built
    ]
    routes.sort(key=lambda route: route["rank"])
    return {
        "origin": _public_place(origin),
        "destination": _public_place(destination),
        "departure": departure.isoformat(),
        "timezone": timezone_name,
        "load_weight_lb": load_lb,
        "interval_miles": interval_miles,
        "route_note": route_note,
        "warnings": warnings,
        "scoring": {
            "order": [
                "fewest No Travel miles (disqualifying, and worse than Severe)",
                "fewest Severe miles",
                "fewest High miles",
                "lowest mileage-weighted average risk",
                "shortest driving time",
                "shortest distance",
            ],
            "segment": "worse of the two checkpoint risks",
            "average_scale": {
                "Low": 0,
                "Moderate": 1,
                "High": 2,
                "Severe": 3,
                "No Travel": 4,
            },
        },
        "recommendation": {
            "route_id": winner.route_id,
            "disqualified": winner.disqualified,
            "reason": describe_recommendation(ordered, names),
        },
        "routes": routes,
    }


def _score(sample: SamplePoint, series_by_cell: dict, load_lb: float) -> ScoredCheckpoint:
    series = series_by_cell.get(grid_key(sample.point))
    if series is None:
        raise ExternalServiceError("Weather forecast was missing for a checkpoint.")
    wind, rain, snow, imputed, clamped, forecast_hour = read_conditions(series, sample.eta)
    return ScoredCheckpoint(
        sample=sample,
        wind_mph=wind,
        rain_in_hr=rain,
        snow_in_hr=snow,
        assessment=assess(wind, rain, snow, load_lb),
        imputed=imputed,
        clamped=clamped,
        forecast_hour=forecast_hour,
    )


def _public_route(
    route_id: str,
    raw: RawRoute,
    scored: list[ScoredCheckpoint],
    metric,
    rank: int,
    winner_id: str,
) -> dict:
    display = raw.coords
    if len(display) > 1200:
        display = simplify(display, DISPLAY_TOLERANCE_DEG)
    return {
        "id": route_id,
        "name": raw.name,
        "source": raw.source,
        "via_label": raw.via_label,
        "rank": rank,
        "recommended": route_id == winner_id,
        "distance_miles": round(metric.distance_miles, 1),
        "duration_seconds": round(metric.duration_seconds),
        "geometry": {
            "type": "LineString",
            "coordinates": [[round(point.lon, 5), round(point.lat, 5)] for point in display],
        },
        "checkpoints": [_public_checkpoint(item) for item in scored],
        "metrics": {
            "no_travel_miles": round(metric.no_travel_miles, 2),
            "severe_miles": round(metric.severe_miles, 2),
            "high_miles": round(metric.high_miles, 2),
            "moderate_miles": round(metric.moderate_miles, 2),
            "low_miles": round(metric.low_miles, 2),
            "average_risk": round(metric.average_risk, 3),
            "disqualified": metric.disqualified,
        },
    }


def _public_checkpoint(item: ScoredCheckpoint) -> dict:
    assessment = item.assessment
    return {
        "mile": round(item.sample.mile, 2),
        "lat": round(item.sample.point.lat, 5),
        "lon": round(item.sample.point.lon, 5),
        "eta": item.sample.eta.isoformat(),
        "wind_mph": round(item.wind_mph, 1),
        "rain_in_hr": round(item.rain_in_hr, 3),
        "snow_in_hr": round(item.snow_in_hr, 3),
        "wind_risk": label(assessment.wind_risk),
        "wind_risk_after_load": label(assessment.wind_risk_after_load),
        "rain_risk": label(assessment.rain_risk),
        "snow_risk": label(assessment.snow_risk),
        "risk": label(assessment.overall),
        "load_note": assessment.load_note,
        "factors": list(assessment.factors),
        "forecast_hour": item.forecast_hour.isoformat(),
        "imputed": item.imputed,
        "clamped": item.clamped,
    }


def _public_place(place: Place) -> dict:
    return {"label": place.label, "lat": place.lat, "lon": place.lon}


def _warnings(any_imputed: bool, any_clamped: bool) -> list[str]:
    warnings: list[str] = []
    if any_imputed:
        warnings.append("Some forecast hours were missing and were scored as calm (0).")
    if any_clamped:
        warnings.append(
            "Part of this drive falls outside the hourly forecast window, so the nearest available hour was used."
        )
    return warnings
