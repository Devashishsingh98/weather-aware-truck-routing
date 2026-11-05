"""Three driving options from the public OSRM server.

`alternatives=true` often returns one or two routes. When it returns fewer than
three, the missing options are new OSRM trips through a waypoint set
perpendicular to the primary line, 25 to 110 miles off it. A candidate is kept
only when sample points sit at least 8 miles, on average, off every route
already chosen. The public server has no truck profile, so these are car-legal
driving routes.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from planner.services.config import OSRM_BASE_URL
from planner.services.errors import ExternalServiceError
from planner.services.geo import (
    METERS_PER_MILE,
    LatLon,
    bearing_at_distance,
    cardinal_offset,
    destination,
    haversine_miles,
    location_at,
    mean_separation_miles,
    prefix_sums,
)
from planner.services.http import get_json

logger = logging.getLogger(__name__)

# fraction along the primary route, which side of the heading, offset as a fraction of length
VIA_ATTEMPTS = (
    (0.50, 1, 0.18),
    (0.50, -1, 0.18),
    (0.38, 1, 0.28),
    (0.62, -1, 0.28),
    (0.45, 1, 0.40),
    (0.55, -1, 0.40),
)
SEPARATION_MILES = 8.0
# Waypoint detours are optional extras; never let them hold the request open.
VIA_BUDGET_SECONDS = 20.0
VIA_TIMEOUT_SECONDS = 10.0


@dataclass
class RawRoute:
    name: str
    source: str
    via_label: str | None
    distance_meters: float
    duration_seconds: float
    coords: list[LatLon]
    segment_distances_m: list[float]
    segment_durations_s: list[float]


def build_three_routes(origin: LatLon, destination: LatLon) -> tuple[list[RawRoute], str | None]:
    initial = request_routes([origin, destination])
    chosen: list[RawRoute] = []
    for index, route in enumerate(initial):
        route.name = _osrm_name(index)
        route.source = "osrm"
        route.via_label = None
        if not chosen or routes_are_distinct(route.coords, [item.coords for item in chosen]):
            chosen.append(route)
        if len(chosen) == 3:
            return chosen, None

    note = (
        "OSRM's public driving service returned fewer than three alternatives. "
        "The extra option is a driving route through a waypoint offset perpendicular "
        "to the primary corridor, between 25 and 110 miles off that line."
    )
    base = chosen[0]
    used_names: set[str] = set()
    started = time.monotonic()
    for fraction, side, offset_fraction in VIA_ATTEMPTS:
        if len(chosen) >= 3:
            break
        if time.monotonic() - started > VIA_BUDGET_SECONDS:
            logger.warning("Stopping waypoint detours: time budget spent")
            break
        via, anchor = via_point(base, fraction, side, offset_fraction)
        try:
            routed = request_routes([origin, via, destination], timeout=VIA_TIMEOUT_SECONDS)
        except ExternalServiceError:
            logger.info("Skipping a waypoint offset that OSRM could not route")
            continue
        candidate = routed[0]
        if not routes_are_distinct(candidate.coords, [item.coords for item in chosen]):
            continue
        direction = cardinal_offset(anchor, via)
        label = f"{direction} detour"
        suffix = 2
        while label in used_names:
            label = f"{direction} detour {suffix}"
            suffix += 1
        used_names.add(label)
        candidate.name = label
        candidate.source = "via"
        candidate.via_label = direction
        chosen.append(candidate)

    if len(chosen) < 3:
        count = len(chosen)
        noun = "route" if count == 1 else "routes"
        note = (
            f"Only {count} distinct driving {noun} could be built. "
            "OSRM returned fewer than three alternatives, and the extra waypoint "
            "offsets fell back onto a corridor already in the list."
        )
    return chosen, note


def request_routes(points: list[LatLon], timeout: float = 20) -> list[RawRoute]:
    path = ";".join(f"{point.lon:.6f},{point.lat:.6f}" for point in points)
    url = f"{OSRM_BASE_URL}/route/v1/driving/{path}"
    payload = get_json(
        url,
        params={
            "alternatives": "true",
            "steps": "false",
            "geometries": "geojson",
            "overview": "full",
            "annotations": "duration,distance",
        },
        timeout=timeout,
    )
    if not isinstance(payload, dict):
        raise ExternalServiceError("Routing service returned an unexpected payload.")
    routes = parse_osrm_response(payload)
    for route in routes:
        route.name = "Route"
        route.source = "osrm"
        route.via_label = None
    return routes


def parse_osrm_response(payload: dict) -> list[RawRoute]:
    if payload.get("code") != "Ok":
        message = payload.get("message") or payload.get("code") or "unknown error"
        raise ExternalServiceError(f"Routing service could not build a drive: {message}.")
    parsed: list[RawRoute] = []
    for route in payload.get("routes") or []:
        if not isinstance(route, dict):
            continue
        coords, distances, durations, distance_m, duration_s = _parse_route(route)
        parsed.append(
            RawRoute(
                name="Route",
                source="osrm",
                via_label=None,
                distance_meters=distance_m,
                duration_seconds=duration_s,
                coords=coords,
                segment_distances_m=distances,
                segment_durations_s=durations,
            )
        )
    if not parsed:
        raise ExternalServiceError("Routing service returned no routes.")
    return parsed


def via_point(
    route: RawRoute,
    fraction: float,
    side: int,
    offset_fraction: float,
) -> tuple[LatLon, LatLon]:
    cumulative = prefix_sums(route.segment_distances_m)
    target_m = route.distance_meters * fraction
    anchor, _seconds = location_at(route.coords, cumulative, [0.0] * len(cumulative), target_m)
    heading = bearing_at_distance(route.coords, cumulative, target_m)
    distance_miles = route.distance_meters / METERS_PER_MILE
    offset_miles = max(25.0, min(110.0, distance_miles * offset_fraction))
    bearing = (heading + 90.0 * side) % 360.0
    return destination(anchor, bearing, offset_miles), anchor


def routes_are_distinct(
    candidate: list[LatLon],
    others: list[list[LatLon]],
    threshold_miles: float = SEPARATION_MILES,
) -> bool:
    return all(mean_separation_miles(candidate, other) >= threshold_miles for other in others)


def scale_to_total(values: list[float], target: float) -> list[float]:
    """Keep relative segment size, but make the pieces add up to the published total.

    On the public OSRM server, annotation durations can miss turn costs and fail
    to sum to the route duration. Scaling preserves where the truck is slow.
    """

    if not values:
        return []
    total = sum(values)
    if total <= 0:
        share = target / len(values)
        return [share for _value in values]
    factor = target / total
    return [value * factor for value in values]


def _parse_route(route: dict) -> tuple[list[LatLon], list[float], list[float], float, float]:
    geometry = route.get("geometry") or {}
    raw_coords = geometry.get("coordinates") or []
    coords = [LatLon(lat=float(pair[1]), lon=float(pair[0])) for pair in raw_coords if len(pair) >= 2]
    distance_m = float(route.get("distance") or 0)
    duration_s = float(route.get("duration") or 0)
    if len(coords) < 2:
        raise ExternalServiceError("Routing service returned a route without a geometry.")
    distances: list[float] = []
    durations: list[float] = []
    aligned = True
    for leg in route.get("legs") or []:
        if not isinstance(leg, dict):
            aligned = False
            break
        annotation = leg.get("annotation") or {}
        leg_distance = annotation.get("distance")
        leg_duration = annotation.get("duration")
        if (
            not isinstance(leg_distance, list)
            or not isinstance(leg_duration, list)
            or not leg_distance
            or len(leg_distance) != len(leg_duration)
        ):
            aligned = False
            break
        distances.extend(scale_to_total([float(value) for value in leg_distance], float(leg.get("distance") or 0)))
        durations.extend(scale_to_total([float(value) for value in leg_duration], float(leg.get("duration") or 0)))
    if not aligned or len(distances) != len(coords) - 1:
        distances, durations = _fallback_segments(coords, distance_m, duration_s)
    return coords, distances, durations, distance_m, duration_s


def _fallback_segments(
    coords: list[LatLon],
    distance_m: float,
    duration_s: float,
) -> tuple[list[float], list[float]]:
    raw = [haversine_miles(left, right) * METERS_PER_MILE for left, right in zip(coords, coords[1:])]
    return scale_to_total(raw, distance_m), scale_to_total(raw, duration_s)


def _osrm_name(index: int) -> str:
    if index == 0:
        return "Direct"
    if index == 1:
        return "Alternate corridor"
    return f"Alternate corridor {index + 1}"
