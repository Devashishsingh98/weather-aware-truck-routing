from django.test import SimpleTestCase

from planner.services.risk import RiskLevel
from planner.services.scoring import (
    accumulate_risk_miles,
    describe_recommendation,
    metrics_from_checkpoints,
    rank_routes,
)
from planner.services.scoring import RouteMetrics


def metric(route_id: str, **overrides) -> RouteMetrics:
    values = {
        "no_travel_miles": 0.0,
        "severe_miles": 0.0,
        "high_miles": 0.0,
        "moderate_miles": 0.0,
        "low_miles": 100.0,
        "average_risk": 0.0,
        "duration_seconds": 1000.0,
        "distance_miles": 100.0,
    }
    values.update(overrides)
    return RouteMetrics(route_id=route_id, **values)


class SegmentMileTests(SimpleTestCase):
    def test_segment_takes_the_worse_endpoint(self):
        buckets = accumulate_risk_miles(
            [
                (0, RiskLevel.LOW),
                (10, RiskLevel.SEVERE),
                (30, RiskLevel.HIGH),
            ]
        )
        self.assertEqual(buckets[RiskLevel.SEVERE], 30)
        self.assertEqual(buckets[RiskLevel.LOW], 0)
        self.assertEqual(buckets[RiskLevel.HIGH], 0)

    def test_weighted_average_uses_miles_not_checkpoint_count(self):
        scored = metrics_from_checkpoints(
            "route-1",
            [(0, RiskLevel.LOW), (10, RiskLevel.LOW), (30, RiskLevel.HIGH)],
            duration_seconds=3600,
            distance_miles=30,
        )
        # 10 low miles and 20 high miles. High is 2, so 40 / 30.
        self.assertEqual(scored.low_miles, 10)
        self.assertEqual(scored.high_miles, 20)
        self.assertAlmostEqual(scored.average_risk, 40 / 30)
        self.assertFalse(scored.disqualified)


class RecommendationOrderTests(SimpleTestCase):
    def test_no_travel_is_worse_than_any_severe_mileage(self):
        clean = metric("clean", no_travel_miles=0, severe_miles=500, duration_seconds=99_000)
        blocked = metric("blocked", no_travel_miles=0.5, severe_miles=0, duration_seconds=1)
        self.assertEqual(rank_routes([blocked, clean])[0].route_id, "clean")

    def test_full_priority_order(self):
        routes = [
            metric("fast-severe", severe_miles=30, average_risk=1.5, duration_seconds=10_000, distance_miles=700),
            metric("slow-safe", severe_miles=0, high_miles=0, average_risk=0.2, duration_seconds=20_000, distance_miles=900),
            metric("no-travel-short", no_travel_miles=5, severe_miles=0, duration_seconds=8_000, distance_miles=600),
        ]
        self.assertEqual(
            [route.route_id for route in rank_routes(routes)],
            ["slow-safe", "fast-severe", "no-travel-short"],
        )

    def test_high_miles_before_average_risk_and_time(self):
        slower = metric("fewer-high", severe_miles=10, high_miles=1, average_risk=3, duration_seconds=9_000)
        quicker = metric("more-high", severe_miles=10, high_miles=5, average_risk=0.2, duration_seconds=1)
        self.assertEqual(rank_routes([quicker, slower])[0].route_id, "fewer-high")

    def test_average_risk_before_time(self):
        calm = metric("calm", severe_miles=0, high_miles=0, average_risk=0.4, duration_seconds=5_000)
        rougher = metric("rougher", severe_miles=0, high_miles=0, average_risk=1.0, duration_seconds=100)
        self.assertEqual(rank_routes([rougher, calm])[0].route_id, "calm")

    def test_time_before_distance(self):
        shorter_time = metric("shorter-time", duration_seconds=100, distance_miles=900)
        shorter_road = metric("shorter-road", duration_seconds=200, distance_miles=1)
        self.assertEqual(rank_routes([shorter_road, shorter_time])[0].route_id, "shorter-time")

    def test_distance_then_id_break_remaining_ties(self):
        longer = metric("b", duration_seconds=100, distance_miles=20)
        shorter = metric("z", duration_seconds=100, distance_miles=10)
        same = metric("a", duration_seconds=100, distance_miles=10)
        ordered = [route.route_id for route in rank_routes([longer, same, shorter])]
        self.assertEqual(ordered, ["a", "z", "b"])

    def test_reason_marks_an_all_disqualified_set(self):
        ordered = rank_routes(
            [
                metric("east", no_travel_miles=4, severe_miles=1, duration_seconds=3_600),
                metric("west", no_travel_miles=9, severe_miles=0, duration_seconds=3_000),
            ]
        )
        reason = describe_recommendation(ordered, {"east": "Eastern detour", "west": "Western detour"})
        self.assertIn("not a clearance", reason)
        self.assertIn("disqualifying", reason)
        self.assertIn("Eastern detour", reason)
        self.assertIn("Western detour", reason)

    def test_reason_explains_a_clean_winner(self):
        ordered = rank_routes(
            [
                metric("direct", severe_miles=2, high_miles=4, average_risk=0.3, duration_seconds=36_000),
                metric("north", severe_miles=8, high_miles=1, average_risk=0.2, duration_seconds=30_000),
            ]
        )
        reason = describe_recommendation(ordered, {"direct": "Direct", "north": "Northern detour"})
        self.assertIn("zero No Travel", reason)
        self.assertIn("Severe", reason)
        self.assertIn("Northern detour", reason)
