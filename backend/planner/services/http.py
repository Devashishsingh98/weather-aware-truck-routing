"""Shared HTTP session for the public geocoder, router, and forecast."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from planner.services.config import USER_AGENT
from planner.services.errors import ExternalServiceError

_session: requests.Session | None = None


def get_session() -> requests.Session:
    global _session
    if _session is None:
        session = requests.Session()
        retry = Retry(
            total=2,
            connect=2,
            read=2,
            backoff_factor=0.4,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers["User-Agent"] = USER_AGENT
        _session = session
    return _session


def get_json(url: str, params: dict | None = None, timeout: float = 25) -> object:
    try:
        response = get_session().get(url, params=params, timeout=timeout)
    except requests.Timeout as exc:
        raise ExternalServiceError("A routing or weather service timed out. Try the haul again.") from exc
    except requests.RequestException as exc:
        raise ExternalServiceError("Could not reach a routing or weather service.") from exc
    if response.status_code >= 400:
        raise ExternalServiceError(f"A routing or weather service returned HTTP {response.status_code}.")
    try:
        return response.json()
    except ValueError as exc:
        raise ExternalServiceError("A routing or weather service returned a response that was not JSON.") from exc
