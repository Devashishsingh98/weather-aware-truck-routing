"""HTTP edge. Routing, weather, and scoring live in planner.services."""

from __future__ import annotations

import logging
import math
from datetime import datetime

from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from planner.services.errors import PlannerError
from planner.services.geocode import Place, geocode_one, search_places
from planner.services.heatmap import build_heatmap
from planner.services.planning import plan_haul

logger = logging.getLogger(__name__)


def api_root(_request):
    return JsonResponse(
        {
            "service": "Weather-Aware Truck Routing",
            "endpoints": {
                "health": "/api/health/",
                "geocode": "/api/geocode/?q=Dallas,%20TX",
                "plan": "/api/plan/",
                "heatmap": "/api/heatmap/",
            },
        }
    )


class HealthView(APIView):
    def get(self, _request):
        return Response({"status": "ok"})


class GeocodeView(APIView):
    def get(self, request):
        query = str(request.query_params.get("q") or "")
        try:
            places = search_places(query)
        except PlannerError as exc:
            return Response({"detail": exc.detail}, status=exc.status)
        except Exception:
            logger.exception("geocode failed")
            return Response({"detail": "Place search failed. Try the name again."}, status=500)
        return Response(
            {
                "results": [
                    {"label": place.label, "lat": place.lat, "lon": place.lon} for place in places
                ]
            }
        )


class PlanView(APIView):
    def post(self, request):
        try:
            payload = request.data
            if not isinstance(payload, dict):
                raise PlannerError("Request body must be a JSON object.")
            departure = payload.get("departure")
            if not isinstance(departure, str) or not departure.strip():
                raise PlannerError("Choose a departure date and time.")
            load_lb = _load(payload.get("load_weight_lb"))
            interval_miles = _interval(payload.get("interval_miles"))
            origin = _place(payload.get("origin"), "origin")
            destination = _place(payload.get("destination"), "destination")
            result = plan_haul(
                origin=origin,
                destination=destination,
                departure_raw=departure.strip(),
                load_lb=load_lb,
                interval_miles=interval_miles,
            )
            return Response(result)
        except PlannerError as exc:
            return Response({"detail": exc.detail}, status=exc.status)
        except Exception:
            logger.exception("plan failed")
            return Response(
                {"detail": "Something went wrong while planning the haul. Try again in a moment."},
                status=500,
            )


class HeatmapView(APIView):
    def post(self, request):
        try:
            payload = request.data
            if not isinstance(payload, dict):
                raise PlannerError("Request body must be a JSON object.")
            geometries = payload.get("geometries")
            if not isinstance(geometries, list) or not geometries:
                raise PlannerError("Heatmap needs the route geometries from a plan.")
            departure_raw = payload.get("departure")
            if not isinstance(departure_raw, str) or not departure_raw.strip():
                raise PlannerError("Heatmap needs the departure time from the plan.")
            try:
                departure = datetime.fromisoformat(departure_raw)
            except ValueError as exc:
                raise PlannerError("Heatmap departure must be an ISO date and time.") from exc
            if departure.tzinfo is None:
                raise PlannerError("Heatmap departure must include a timezone offset.")
            result = build_heatmap(geometries, departure, _load(payload.get("load_weight_lb")))
            return Response(result)
        except PlannerError as exc:
            return Response({"detail": exc.detail}, status=exc.status)
        except Exception:
            logger.exception("heatmap failed")
            return Response(
                {"detail": "The corridor forecast could not be loaded. The routes are still usable."},
                status=500,
            )


def _place(value: object, field: str) -> Place:
    if not isinstance(value, dict):
        raise PlannerError(f"{_field_label(field)} is required.")
    query = str(value.get("query") or "").strip()
    label = str(value.get("label") or query).strip()
    lat = value.get("lat")
    lon = value.get("lon")
    if lat is not None or lon is not None:
        if lat is None or lon is None:
            raise PlannerError(f"{_field_label(field)} needs both latitude and longitude.")
        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (TypeError, ValueError) as exc:
            raise PlannerError(f"{_field_label(field)} coordinates must be numbers.") from exc
        if not (-90 <= lat_f <= 90 and -180 <= lon_f <= 180):
            raise PlannerError(f"{_field_label(field)} coordinates are out of range.")
        return Place(label=label or f"{lat_f:.4f}, {lon_f:.4f}", lat=lat_f, lon=lon_f)
    if not query:
        article = "an origin" if field == "origin" else "a destination"
        raise PlannerError(f"Enter {article}.")
    return geocode_one(query)


def _load(value: object) -> float:
    try:
        load = float(value)
    except (TypeError, ValueError) as exc:
        raise PlannerError("Load weight must be a number of pounds.") from exc
    if not math.isfinite(load) or load <= 0 or load > 200_000:
        raise PlannerError("Load weight must be between 1 and 200,000 lb.")
    return load


def _interval(value: object) -> int:
    if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
        raise PlannerError("Sample interval must be 10, 25, or 50 miles.")
    try:
        interval = int(value)
    except (TypeError, ValueError) as exc:
        raise PlannerError("Sample interval must be 10, 25, or 50 miles.") from exc
    if interval not in (10, 25, 50):
        raise PlannerError("Sample interval must be 10, 25, or 50 miles.")
    return interval


def _field_label(field: str) -> str:
    if field == "origin":
        return "Origin"
    if field == "destination":
        return "Destination"
    return field.capitalize()
