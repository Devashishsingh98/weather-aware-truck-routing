class PlannerError(Exception):
    """A request we can refuse with a message the UI should show as-is."""

    status = 400

    def __init__(self, detail: str, status: int | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        if status is not None:
            self.status = status


class ExternalServiceError(PlannerError):
    """Geocoder, router, or forecast did not return a usable payload."""

    status = 502
