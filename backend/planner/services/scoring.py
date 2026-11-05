"""Turn checkpoint risks into miles, then order the routes.

No Travel mileage is the first key. A corridor with any of it ranks behind every
corridor with none, even if the clean corridor has more Severe miles. That is
the disqualifying reading of "worse than Severe": it is not folded into the
Severe total, and it is not a soft penalty.

After that the spec order is Severe miles, High miles, mileage-weighted average
risk, then driving time. Distance, then route id, breaks whatever is still tied.
"""

from __future__ import annotations

from dataclasses import dataclass

from planner.services.risk import RISK_SCORE, RiskLevel


@dataclass(frozen=True)
class RouteMetrics:
    route_id: str
    no_travel_miles: float
    severe_miles: float
    high_miles: float
    moderate_miles: float
    low_miles: float
    average_risk: float
    duration_seconds: float
    distance_miles: float

    @property
    def disqualified(self) -> bool:
        return self.no_travel_miles > 0


def accumulate_risk_miles(checkpoints: list[tuple[float, RiskLevel]]) -> dict[RiskLevel, float]:
    """Miles between two checkpoints take the worse of the two risks.

    The truck is on that stretch while both samples apply, so the segment is
    charged to the more restrictive one.
    """

    buckets = {level: 0.0 for level in RiskLevel}
    if not checkpoints:
        return buckets
    ordered = sorted(checkpoints, key=lambda item: item[0])
    if len(ordered) == 1:
        return buckets
    for (start_mile, start_risk), (end_mile, end_risk) in zip(ordered, ordered[1:]):
        miles = end_mile - start_mile
        if miles <= 0:
            continue
        buckets[max(start_risk, end_risk)] += miles
    return {level: round(miles, 4) for level, miles in buckets.items()}


def metrics_from_checkpoints(
    route_id: str,
    checkpoints: list[tuple[float, RiskLevel]],
    duration_seconds: float,
    distance_miles: float,
) -> RouteMetrics:
    buckets = accumulate_risk_miles(checkpoints)
    if len(checkpoints) == 1:
        buckets[checkpoints[0][1]] = round(max(distance_miles, 0.0), 4)
    total = sum(buckets.values())
    if total <= 0:
        only = checkpoints[0][1] if checkpoints else RiskLevel.LOW
        average = float(RISK_SCORE[only])
    else:
        weighted = sum(RISK_SCORE[level] * miles for level, miles in buckets.items())
        average = weighted / total
    return RouteMetrics(
        route_id=route_id,
        no_travel_miles=buckets[RiskLevel.NO_TRAVEL],
        severe_miles=buckets[RiskLevel.SEVERE],
        high_miles=buckets[RiskLevel.HIGH],
        moderate_miles=buckets[RiskLevel.MODERATE],
        low_miles=buckets[RiskLevel.LOW],
        average_risk=average,
        duration_seconds=duration_seconds,
        distance_miles=distance_miles,
    )


def rank_routes(routes: list[RouteMetrics]) -> list[RouteMetrics]:
    return sorted(
        routes,
        key=lambda route: (
            route.no_travel_miles,
            route.severe_miles,
            route.high_miles,
            route.average_risk,
            route.duration_seconds,
            route.distance_miles,
            route.route_id,
        ),
    )


def describe_recommendation(ordered: list[RouteMetrics], names: dict[str, str]) -> str:
    if not ordered:
        return "No routes to compare."
    best = ordered[0]
    name = names.get(best.route_id, best.route_id)
    sentences = [_lead(best, name, ordered)]
    sentences.append(
        f"It has {best.severe_miles:.1f} Severe miles, {best.high_miles:.1f} High miles, "
        f"a mileage-weighted risk of {best.average_risk:.2f} on a 0–4 scale "
        f"(Low 0, Moderate 1, High 2, Severe 3, No Travel 4), and "
        f"a drive time of {_format_duration(best.duration_seconds)}."
    )
    if len(ordered) > 1:
        nxt = ordered[1]
        sentences.append(_why_ahead(best, nxt, names.get(nxt.route_id, nxt.route_id)))
    return " ".join(sentences)


def _lead(best: RouteMetrics, name: str, ordered: list[RouteMetrics]) -> str:
    if all(route.disqualified for route in ordered):
        return (
            f"{name} is the least-exposed option, and it is not a clearance to roll. "
            "No Travel miles are disqualifying and worse than Severe, but every corridor "
            f"still has some ({best.no_travel_miles:.1f} miles on this one)."
        )
    if best.disqualified:
        return (
            f"{name} has {best.no_travel_miles:.1f} No Travel miles, so it is disqualified. "
            "It only ranks first because every other corridor has more."
        )
    return (
        f"{name} stays eligible with zero No Travel miles. "
        "Any corridor that enters a No Travel sample ranks behind the corridors that do not."
    )


def _why_ahead(best: RouteMetrics, nxt: RouteMetrics, nxt_name: str) -> str:
    if nxt.no_travel_miles > best.no_travel_miles + 0.05:
        return f"{nxt_name} is next and has {nxt.no_travel_miles:.1f} No Travel miles."
    if nxt.severe_miles > best.severe_miles + 0.05:
        return (
            f"{nxt_name} is next with {nxt.severe_miles:.1f} Severe miles "
            f"versus {best.severe_miles:.1f}."
        )
    if nxt.high_miles > best.high_miles + 0.05:
        return (
            f"Severe miles tie {nxt_name}. It has more High miles "
            f"({nxt.high_miles:.1f} versus {best.high_miles:.1f})."
        )
    if nxt.average_risk > best.average_risk + 0.005:
        return (
            f"Severe and High miles tie {nxt_name}. Its average risk is higher "
            f"({nxt.average_risk:.2f} versus {best.average_risk:.2f})."
        )
    if nxt.duration_seconds > best.duration_seconds + 30:
        gap = _format_duration(nxt.duration_seconds - best.duration_seconds)
        return f"Risk ties {nxt_name}. This route is shorter by {gap}."
    return f"{nxt_name} matches on risk and time, so distance and route id decide it."


def _format_duration(seconds: float) -> str:
    minutes = int(round(abs(seconds) / 60))
    hours, mins = divmod(minutes, 60)
    if hours == 0:
        return f"{mins} min"
    return f"{hours} h {mins} min"
