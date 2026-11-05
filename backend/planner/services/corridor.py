"""Sample a band around the drawn routes for the 48-hour field.

Points sit on each line and on perpendicular offsets. They are deduped to about
a kilometer so neighboring samples share one forecast cell.
"""

from __future__ import annotations

import math

from planner.services.geo import (
    METERS_PER_MILE,
    LatLon,
    bearing_at_distance,
    destination,
    haversine_miles,
    location_at,
    prefix_sums,
)

OFFSETS_MILES = (0.0, 16.0, -16.0, 34.0, -34.0)


def corridor_points(
    lines: list[list[LatLon]],
    spacing_miles: float = 40.0,
    cap: int = 72,
) -> list[LatLon]:
    found: list[LatLon] = []
    seen: set[tuple[float, float]] = set()
    for line in lines:
        if len(line) < 2:
            continue
        distances = [
            max(0.0, _meters(left, right))
            for left, right in zip(line, line[1:])
        ]
        cumulative = prefix_sums(distances)
        total_miles = cumulative[-1] / METERS_PER_MILE
        for mile in _mile_marks(total_miles, spacing_miles):
            target_m = cumulative[-1] if abs(mile - total_miles) <= 1e-6 else mile * METERS_PER_MILE
            anchor, _seconds = location_at(line, cumulative, [0.0] * len(cumulative), target_m)
            heading = bearing_at_distance(line, cumulative, target_m)
            for offset in OFFSETS_MILES:
                if offset == 0:
                    candidate = anchor
                else:
                    bearing = (heading + (90.0 if offset > 0 else -90.0)) % 360.0
                    candidate = destination(anchor, bearing, abs(offset))
                key = (round(candidate.lat, 2), round(candidate.lon, 2))
                if key in seen:
                    continue
                seen.add(key)
                found.append(candidate)
    if len(found) > cap:
        stride = math.ceil(len(found) / cap)
        found = found[::stride][:cap]
    return found


def _mile_marks(total_miles: float, spacing_miles: float) -> list[float]:
    marks = [0.0]
    cursor = spacing_miles
    while cursor < total_miles - 1:
        marks.append(cursor)
        cursor += spacing_miles
    if total_miles > 0.5 and abs(marks[-1] - total_miles) > 0.5:
        marks.append(total_miles)
    return marks


def _meters(origin: LatLon, dest: LatLon) -> float:
    return haversine_miles(origin, dest) * METERS_PER_MILE
