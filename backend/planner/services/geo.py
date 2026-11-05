"""Statute miles and polyline geometry. The risk table is in miles, not meters."""

from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_MILES = 3958.7613
METERS_PER_MILE = 1609.344


@dataclass(frozen=True)
class LatLon:
    lat: float
    lon: float


def haversine_miles(origin: LatLon, dest: LatLon) -> float:
    phi1 = math.radians(origin.lat)
    phi2 = math.radians(dest.lat)
    dphi = math.radians(dest.lat - origin.lat)
    dlambda = math.radians(dest.lon - origin.lon)
    hav = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    hav = min(1.0, hav)
    return 2 * EARTH_MILES * math.asin(math.sqrt(hav))


def bearing_degrees(origin: LatLon, dest: LatLon) -> float:
    phi1 = math.radians(origin.lat)
    phi2 = math.radians(dest.lat)
    dlambda = math.radians(dest.lon - origin.lon)
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def destination(start: LatLon, bearing_deg: float, distance_miles: float) -> LatLon:
    if distance_miles == 0:
        return start
    angular = distance_miles / EARTH_MILES
    theta = math.radians(bearing_deg)
    phi1 = math.radians(start.lat)
    lambda1 = math.radians(start.lon)
    sin_phi1 = math.sin(phi1)
    cos_phi1 = math.cos(phi1)
    sin_angular = math.sin(angular)
    cos_angular = math.cos(angular)
    phi2 = math.asin(sin_phi1 * cos_angular + cos_phi1 * sin_angular * math.cos(theta))
    lambda2 = lambda1 + math.atan2(
        math.sin(theta) * sin_angular * cos_phi1,
        cos_angular - sin_phi1 * math.sin(phi2),
    )
    lon = (math.degrees(lambda2) + 540.0) % 360.0 - 180.0
    return LatLon(math.degrees(phi2), lon)


def prefix_sums(values: list[float]) -> list[float]:
    cumulative = [0.0]
    for value in values:
        cumulative.append(cumulative[-1] + value)
    return cumulative


def location_at(
    coords: list[LatLon],
    cumulative_m: list[float],
    cumulative_s: list[float],
    target_m: float,
) -> tuple[LatLon, float]:
    if len(coords) < 1 or len(coords) != len(cumulative_m) or len(cumulative_m) != len(cumulative_s):
        raise ValueError("coordinate and cumulative arrays must be the same non-empty length")
    if target_m <= 0:
        return coords[0], cumulative_s[0]
    total = cumulative_m[-1]
    if target_m >= total:
        return coords[-1], cumulative_s[-1]
    # First cumulative entry strictly greater than the target, then step back one segment.
    lo = 0
    hi = len(cumulative_m) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if cumulative_m[mid] <= target_m:
            lo = mid + 1
        else:
            hi = mid
    index = min(max(lo - 1, 0), len(coords) - 2)
    span = cumulative_m[index + 1] - cumulative_m[index]
    fraction = 0.0 if span <= 0 else (target_m - cumulative_m[index]) / span
    left = coords[index]
    right = coords[index + 1]
    point = LatLon(
        left.lat + (right.lat - left.lat) * fraction,
        left.lon + (right.lon - left.lon) * fraction,
    )
    seconds = cumulative_s[index] + (cumulative_s[index + 1] - cumulative_s[index]) * fraction
    return point, seconds


def bearing_at_distance(coords: list[LatLon], cumulative_m: list[float], target_m: float) -> float:
    total = cumulative_m[-1]
    start_m = min(max(target_m, 0.0), total)
    end_m = min(total, start_m + METERS_PER_MILE)
    if end_m - start_m < 50:
        end_m = start_m
        start_m = max(0.0, end_m - METERS_PER_MILE)
    zeros = [0.0] * len(cumulative_m)
    start, _seconds = location_at(coords, cumulative_m, zeros, start_m)
    end, _seconds = location_at(coords, cumulative_m, zeros, end_m)
    if haversine_miles(start, end) < 0.01:
        return 0.0
    return bearing_degrees(start, end)


def mean_separation_miles(source: list[LatLon], other: list[LatLon], samples: int = 12) -> float:
    if len(source) < 2 or not other:
        return 0.0
    step = max(1, (len(source) - 1) // samples)
    picked = list(source[::step][:samples])
    if picked[-1] != source[-1]:
        picked.append(source[-1])
    other_step = max(1, len(other) // 300)
    other_samples = list(other[::other_step])
    if other_samples[-1] != other[-1]:
        other_samples.append(other[-1])
    total = 0.0
    for point in picked:
        total += min(haversine_miles(point, candidate) for candidate in other_samples)
    return total / len(picked)


def simplify(coords: list[LatLon], tolerance_deg: float) -> list[LatLon]:
    """Douglas–Peucker in degrees. Display geometry only; sampling uses the full line."""

    if len(coords) < 3:
        return list(coords)
    keep = [False] * len(coords)
    keep[0] = True
    keep[-1] = True
    stack = [(0, len(coords) - 1)]
    tolerance_sq = tolerance_deg * tolerance_deg
    while stack:
        start, end = stack.pop()
        if end <= start + 1:
            continue
        origin = coords[start]
        dest = coords[end]
        farthest = -1.0
        farthest_index = -1
        for index in range(start + 1, end):
            distance_sq = _segment_distance_sq(coords[index], origin, dest)
            if distance_sq > farthest:
                farthest = distance_sq
                farthest_index = index
        if farthest_index >= 0 and farthest > tolerance_sq:
            keep[farthest_index] = True
            stack.append((start, farthest_index))
            stack.append((farthest_index, end))
    return [point for point, flagged in zip(coords, keep) if flagged]


def cardinal_offset(origin: LatLon, shifted: LatLon) -> str:
    north_miles = (shifted.lat - origin.lat) * 69.0
    east_miles = (shifted.lon - origin.lon) * 69.0 * math.cos(math.radians(origin.lat))
    if abs(east_miles) >= abs(north_miles):
        return "Eastern" if east_miles >= 0 else "Western"
    return "Northern" if north_miles >= 0 else "Southern"


def _segment_distance_sq(point: LatLon, origin: LatLon, dest: LatLon) -> float:
    dx = dest.lon - origin.lon
    dy = dest.lat - origin.lat
    if dx == 0 and dy == 0:
        ex = point.lon - origin.lon
        ey = point.lat - origin.lat
        return ex * ex + ey * ey
    t = ((point.lon - origin.lon) * dx + (point.lat - origin.lat) * dy) / (dx * dx + dy * dy)
    t = min(1.0, max(0.0, t))
    ex = point.lon - (origin.lon + t * dx)
    ey = point.lat - (origin.lat + t * dy)
    return ex * ex + ey * ey
