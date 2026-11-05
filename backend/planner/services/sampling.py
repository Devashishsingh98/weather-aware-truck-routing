"""Place checkpoints every N miles and stamp each one with a driving ETA.

ETA is departure plus the OSRM time accumulated along the polyline. There is no
hours-of-service break. The spec asks for arrival time from cumulative duration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from planner.services.geo import METERS_PER_MILE, LatLon, location_at, prefix_sums


@dataclass(frozen=True)
class SamplePoint:
    mile: float
    point: LatLon
    eta: datetime


def sample_checkpoints(
    coords: list[LatLon],
    segment_distances_m: list[float],
    segment_durations_s: list[float],
    interval_miles: float,
    departure: datetime,
) -> list[SamplePoint]:
    if len(coords) < 2:
        raise ValueError("a route needs at least two coordinates")
    if len(segment_distances_m) != len(coords) - 1 or len(segment_durations_s) != len(segment_distances_m):
        raise ValueError("segment arrays must match the coordinate spans")
    if interval_miles <= 0:
        raise ValueError("interval must be positive")
    if departure.tzinfo is None:
        raise ValueError("departure must be timezone-aware")

    cumulative_m = prefix_sums(segment_distances_m)
    cumulative_s = prefix_sums(segment_durations_s)
    total_m = cumulative_m[-1]
    total_miles = total_m / METERS_PER_MILE

    targets = [0.0]
    cursor = interval_miles
    while cursor < total_miles - 0.05:
        targets.append(cursor)
        cursor += interval_miles
    if total_miles > 0.05 and abs(targets[-1] - total_miles) > 0.05:
        targets.append(total_miles)

    samples: list[SamplePoint] = []
    for mile in targets:
        at_end = abs(mile - total_miles) <= 1e-6
        target_m = total_m if at_end else mile * METERS_PER_MILE
        point, seconds = location_at(coords, cumulative_m, cumulative_s, target_m)
        samples.append(
            SamplePoint(
                mile=total_miles if at_end else mile,
                point=point,
                eta=departure + timedelta(seconds=seconds),
            )
        )
    return samples
