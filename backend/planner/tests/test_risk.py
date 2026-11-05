"""Boundary tests for the printed risk table and the load overrides.

Wind bands are half-open at the next printed threshold: 34.9 is still the
"25–34" band, and 35.0 enters "35–44". Rain and snow share printed endpoints,
so the shared value takes the worse band. 1.00 in/hr of rain and 3.0 in/hr of
snow stay Severe because No Travel is a strict greater-than. Load rules use the
same wind cuts and only raise the wind result.
"""

from django.test import SimpleTestCase

from planner.services.risk import (
    RiskLevel,
    apply_load_rule,
    assess,
    classify_rain,
    classify_snow,
    classify_wind,
)


class WindBandTests(SimpleTestCase):
    def test_thresholds(self):
        cases = (
            (0, RiskLevel.LOW),
            (24.99, RiskLevel.LOW),
            (25, RiskLevel.MODERATE),
            (34, RiskLevel.MODERATE),
            (34.99, RiskLevel.MODERATE),
            (35, RiskLevel.HIGH),
            (44, RiskLevel.HIGH),
            (44.99, RiskLevel.HIGH),
            (45, RiskLevel.SEVERE),
            (54, RiskLevel.SEVERE),
            (54.99, RiskLevel.SEVERE),
            (55, RiskLevel.NO_TRAVEL),
            (80, RiskLevel.NO_TRAVEL),
        )
        for speed, expected in cases:
            with self.subTest(mph=speed):
                self.assertEqual(classify_wind(speed), expected)

    def test_negative_wind_is_rejected(self):
        with self.assertRaises(ValueError):
            classify_wind(-0.1)


class RainBandTests(SimpleTestCase):
    def test_thresholds_and_shared_endpoints(self):
        cases = (
            (0, RiskLevel.LOW),
            (0.099, RiskLevel.LOW),
            (0.10, RiskLevel.MODERATE),
            (0.249, RiskLevel.MODERATE),
            (0.25, RiskLevel.HIGH),
            (0.499, RiskLevel.HIGH),
            (0.50, RiskLevel.SEVERE),
            (1.00, RiskLevel.SEVERE),
            (1.01, RiskLevel.NO_TRAVEL),
            (2, RiskLevel.NO_TRAVEL),
        )
        for rate, expected in cases:
            with self.subTest(inches_per_hour=rate):
                self.assertEqual(classify_rain(rate), expected)


class SnowBandTests(SimpleTestCase):
    def test_thresholds_and_shared_endpoints(self):
        cases = (
            (0, RiskLevel.LOW),
            (0.49, RiskLevel.LOW),
            (0.5, RiskLevel.MODERATE),
            (0.99, RiskLevel.MODERATE),
            (1.0, RiskLevel.HIGH),
            (1.99, RiskLevel.HIGH),
            (2.0, RiskLevel.SEVERE),
            (3.0, RiskLevel.SEVERE),
            (3.01, RiskLevel.NO_TRAVEL),
        )
        for rate, expected in cases:
            with self.subTest(inches_per_hour=rate):
                self.assertEqual(classify_snow(rate), expected)


class LoadRuleTests(SimpleTestCase):
    def test_fifty_five_is_no_travel_for_any_load(self):
        for load in (1, 30_000, 80_000):
            with self.subTest(load=load):
                level, note = apply_load_rule(55, load, RiskLevel.NO_TRAVEL)
                self.assertEqual(level, RiskLevel.NO_TRAVEL)
                self.assertIsNotNone(note)

    def test_forty_five_to_fifty_four_depends_on_thirty_thousand(self):
        # 30,000 lb is not over the cut, so the weather band stays Severe.
        level, note = apply_load_rule(45, 30_000, RiskLevel.SEVERE)
        self.assertEqual(level, RiskLevel.SEVERE)
        self.assertIsNone(note)

        level, note = apply_load_rule(54.99, 30_001, RiskLevel.SEVERE)
        self.assertEqual(level, RiskLevel.NO_TRAVEL)
        self.assertIn("30,000", note or "")

        level, note = apply_load_rule(45, 20_000, RiskLevel.SEVERE)
        self.assertEqual(level, RiskLevel.SEVERE)
        self.assertIsNone(note)

    def test_thirty_five_to_forty_four_depends_on_forty_thousand(self):
        level, note = apply_load_rule(35, 40_000, RiskLevel.HIGH)
        self.assertEqual(level, RiskLevel.HIGH)
        self.assertIsNone(note)

        level, note = apply_load_rule(44.99, 40_001, RiskLevel.HIGH)
        self.assertEqual(level, RiskLevel.SEVERE)
        self.assertIn("40,000", note or "")

        # Just under 35 mph, a heavy load does not change the wind band.
        level, note = apply_load_rule(34.99, 80_000, RiskLevel.MODERATE)
        self.assertEqual(level, RiskLevel.MODERATE)
        self.assertIsNone(note)

    def test_load_upgrade_does_not_cross_into_no_travel_below_45(self):
        assessment = assess(44.99, 0, 0, 50_000)
        self.assertEqual(assessment.wind_risk, RiskLevel.HIGH)
        self.assertEqual(assessment.wind_risk_after_load, RiskLevel.SEVERE)
        self.assertEqual(assessment.overall, RiskLevel.SEVERE)
        self.assertEqual(assessment.factors, ("wind",))


class OverallRiskTests(SimpleTestCase):
    def test_severity_order(self):
        self.assertLess(RiskLevel.LOW, RiskLevel.MODERATE)
        self.assertLess(RiskLevel.MODERATE, RiskLevel.HIGH)
        self.assertLess(RiskLevel.HIGH, RiskLevel.SEVERE)
        self.assertLess(RiskLevel.SEVERE, RiskLevel.NO_TRAVEL)

    def test_worst_condition_wins(self):
        assessment = assess(wind_mph=30, rain_in_hr=0.30, snow_in_hr=0.1, load_lb=10_000)
        self.assertEqual(assessment.wind_risk_after_load, RiskLevel.MODERATE)
        self.assertEqual(assessment.rain_risk, RiskLevel.HIGH)
        self.assertEqual(assessment.snow_risk, RiskLevel.LOW)
        self.assertEqual(assessment.overall, RiskLevel.HIGH)
        self.assertEqual(assessment.factors, ("rain",))

    def test_snow_no_travel_beats_a_calm_wind(self):
        assessment = assess(10, 0, 3.5, 1_000)
        self.assertEqual(assessment.overall, RiskLevel.NO_TRAVEL)
        self.assertEqual(assessment.factors, ("snow",))
        self.assertIsNone(assessment.load_note)

    def test_rain_and_load_can_both_be_no_travel(self):
        assessment = assess(50, 1.2, 0, 35_000)
        self.assertEqual(assessment.wind_risk, RiskLevel.SEVERE)
        self.assertEqual(assessment.wind_risk_after_load, RiskLevel.NO_TRAVEL)
        self.assertEqual(assessment.rain_risk, RiskLevel.NO_TRAVEL)
        self.assertEqual(assessment.overall, RiskLevel.NO_TRAVEL)
        self.assertEqual(assessment.factors, ("wind", "rain"))

    def test_exact_rain_and_snow_ceilings_stay_severe(self):
        assessment = assess(0, 1.00, 3.0, 10_000)
        self.assertEqual(assessment.rain_risk, RiskLevel.SEVERE)
        self.assertEqual(assessment.snow_risk, RiskLevel.SEVERE)
        self.assertEqual(assessment.overall, RiskLevel.SEVERE)
        self.assertNotEqual(assessment.overall, RiskLevel.NO_TRAVEL)
