"""Place search. Photon first, Nominatim if Photon is empty or down."""

from __future__ import annotations

from dataclasses import dataclass

from django.core.cache import cache

from planner.services.config import NOMINATIM_URL, PHOTON_URL
from planner.services.errors import ExternalServiceError, PlannerError
from planner.services.http import get_json


@dataclass(frozen=True)
class Place:
    label: str
    lat: float
    lon: float


def search_places(query: str, limit: int = 5) -> list[Place]:
    cleaned = " ".join(query.split())
    if len(cleaned) < 2:
        return []
    cache_key = "geo:v1:" + "".join(ch if ch.isalnum() else "-" for ch in cleaned.lower())
    cached = cache.get(cache_key)
    if isinstance(cached, list):
        return cached[:limit]
    places: list[Place] = []
    try:
        places = _from_photon(cleaned, limit)
    except ExternalServiceError:
        places = []
    if not places:
        places = _from_nominatim(cleaned, limit)
    if places:
        cache.set(cache_key, places, timeout=60 * 60 * 24)
    return places


def geocode_one(query: str) -> Place:
    places = search_places(query, limit=1)
    if not places:
        raise PlannerError(f'No place found for "{query}".')
    return places[0]


def _from_photon(query: str, limit: int) -> list[Place]:
    payload = get_json(PHOTON_URL, params={"q": query, "limit": limit}, timeout=12)
    if not isinstance(payload, dict):
        raise ExternalServiceError("Geocoder returned an unexpected payload.")
    places: list[Place] = []
    for feature in payload.get("features") or []:
        place = _photon_feature(feature)
        if place is not None:
            places.append(place)
        if len(places) >= limit:
            break
    return places


def _photon_feature(feature: object) -> Place | None:
    if not isinstance(feature, dict):
        return None
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        return None
    lon, lat = float(coordinates[0]), float(coordinates[1])
    properties = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    return Place(label=_photon_label(properties), lat=lat, lon=lon)


def _photon_label(properties: dict) -> str:
    name = properties.get("name") or properties.get("street") or "Unnamed place"
    parts = [str(name)]
    city = properties.get("city")
    if city and city != name:
        parts.append(str(city))
    state = properties.get("state")
    if state:
        parts.append(str(state))
    country = properties.get("country")
    if country and country not in parts:
        parts.append(str(country))
    return ", ".join(parts)


def _from_nominatim(query: str, limit: int) -> list[Place]:
    payload = get_json(
        NOMINATIM_URL,
        params={"q": query, "format": "jsonv2", "limit": limit},
        timeout=12,
    )
    if not isinstance(payload, list):
        raise ExternalServiceError("Fallback geocoder returned an unexpected payload.")
    places: list[Place] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            lat = float(item["lat"])
            lon = float(item["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        label = str(item.get("display_name") or f"{lat:.4f}, {lon:.4f}")
        places.append(Place(label=label, lat=lat, lon=lon))
        if len(places) >= limit:
            break
    return places
