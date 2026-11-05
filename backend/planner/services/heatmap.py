"""48-hour corridor field. One batched forecast, then every hour is scored here."""

from __future__ import annotations

from datetime import datetime, timedelta

from planner.services.corridor import corridor_points
from planner.services.errors import PlannerError
from planner.services.forecast import read_conditions
from planner.services.geo import LatLon
from planner.services.risk import RiskLevel, assess, label
from planner.services.weather import fetch_series, grid_key


def build_heatmap(geometries: list, departure: datetime, load_lb: float) -> dict:
    lines = _lines(geometries)
    if not lines:
        raise PlannerError("Heatmap needs at least one route geometry.")
    points = corridor_points(lines)
    if not points:
        raise PlannerError("Could not build a corridor grid from these routes.")
    series_by_cell = fetch_series(points, departure + timedelta(hours=48))
    hours = [departure + timedelta(hours=offset) for offset in range(49)]
    public_points = []
    for point in points:
        series = series_by_cell.get(grid_key(point))
        if series is None:
            continue
        risks: list[int] = []
        for moment in hours:
            wind, rain, snow, _imputed, _clamped, _hour = read_conditions(series, moment)
            risks.append(int(assess(wind, rain, snow, load_lb).overall))
        public_points.append(
            {
                "lat": round(point.lat, 4),
                "lon": round(point.lon, 4),
                "risk": risks,
            }
        )
    if not public_points:
        raise PlannerError("Weather was unavailable for the corridor grid.")
    return {
        "hours": [moment.isoformat() for moment in hours],
        "risk_labels": [label(level) for level in RiskLevel],
        "points": public_points,
    }


def _lines(geometries: list) -> list[list[LatLon]]:
    lines: list[list[LatLon]] = []
    for geometry in geometries[:3]:
        if not isinstance(geometry, list):
            continue
        line: list[LatLon] = []
        for pair in geometry[:8000]:
            if not isinstance(pair, (list, tuple)) or len(pair) < 2:
                continue
            try:
                lon = float(pair[0])
                lat = float(pair[1])
            except (TypeError, ValueError):
                continue
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                line.append(LatLon(lat, lon))
        if len(line) >= 2:
            lines.append(line)
    return lines
