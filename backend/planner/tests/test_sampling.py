from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from planner.services.forecast import hour_index, parse_open_meteo, read_conditions
from planner.services.geo import METERS_PER_MILE, LatLon, destination, mean_separation_miles, simplify
from planner.services.sampling import sample_checkpoints


DEPARTURE = datetime(2026, 11, 6, 8, 0, tzinfo=timezone.utc)


class SamplingTests(SimpleTestCase):
    def test_interval_includes_start_and_end_and_uses_segment_time(self):
        coords = [LatLon(0, 0), LatLon(1, 0), LatLon(2, 0)]
        distances = [40 * METERS_PER_MILE, 20 * METERS_PER_MILE]
        # First 40 miles take 1 hour. The next 20 miles take 3 hours. Not a constant speed.
        durations = [3600, 10_800]
        samples = sample_checkpoints(coords, distances, durations, 25, DEPARTURE)
        miles = [sample.mile for sample in samples]
        self.assertEqual(miles, [0, 25, 50, 60])

        at_25 = samples[1]
        self.assertAlmostEqual(at_25.point.lat, 0.625)
        self.assertAlmostEqual((at_25.eta - DEPARTURE).total_seconds(), 2250)
        constant_speed_seconds = 25 / 60 * 14_400
        self.assertNotAlmostEqual((at_25.eta - DEPARTURE).total_seconds(), constant_speed_seconds)

        at_50 = samples[2]
        self.assertAlmostEqual(at_50.point.lat, 1.5)
        self.assertAlmostEqual((at_50.eta - DEPARTURE).total_seconds(), 9000)
        self.assertAlmostEqual((samples[-1].eta - DEPARTURE).total_seconds(), 14_400)

    def test_exact_multiple_does_not_duplicate_the_end(self):
        coords = [LatLon(0, 0), LatLon(1, 0), LatLon(2, 0)]
        distances = [25 * METERS_PER_MILE, 25 * METERS_PER_MILE]
        samples = sample_checkpoints(coords, distances, [1000, 1000], 25, DEPARTURE)
        self.assertEqual([sample.mile for sample in samples], [0, 25, 50])

    def test_short_haul_is_start_and_end_only(self):
        coords = [LatLon(0, 0), LatLon(1, 0)]
        samples = sample_checkpoints(coords, [5 * METERS_PER_MILE], [600], 25, DEPARTURE)
        self.assertEqual([round(sample.mile, 2) for sample in samples], [0, 5])


class ForecastHourTests(SimpleTestCase):
    def test_hour_bucket_and_clamping(self):
        start = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
        times = [start + timedelta(hours=offset) for offset in range(5)]
        index, clamped = hour_index(times, start + timedelta(minutes=20))
        self.assertEqual((index, clamped), (0, False))
        index, clamped = hour_index(times, start + timedelta(hours=1))
        self.assertEqual((index, clamped), (1, False))
        index, clamped = hour_index(times, start - timedelta(minutes=5))
        self.assertEqual((index, clamped), (0, True))
        index, clamped = hour_index(times, start + timedelta(hours=4, minutes=59))
        self.assertEqual((index, clamped), (4, False))
        index, clamped = hour_index(times, start + timedelta(hours=5))
        self.assertEqual((index, clamped), (4, True))

    def test_missing_hour_is_imputed_as_calm(self):
        payload = {
            "hourly": {
                "time": ["2026-11-06T12:00"],
                "wind_speed_10m": [None],
                "rain": [0.2],
                "snowfall": [None],
            }
        }
        series = parse_open_meteo(payload)
        wind, rain, snow, imputed, clamped, _hour = read_conditions(
            series,
            datetime(2026, 11, 6, 12, 15, tzinfo=timezone.utc),
        )
        self.assertEqual((wind, rain, snow), (0.0, 0.2, 0.0))
        self.assertTrue(imputed)
        self.assertFalse(clamped)


class GeometryTests(SimpleTestCase):
    def test_north_one_degree_is_about_69_miles(self):
        point = destination(LatLon(0, 0), 0, 69.172)
        self.assertAlmostEqual(point.lat, 1.0, places=2)
        self.assertAlmostEqual(point.lon, 0.0, places=2)

    def test_colinear_points_collapse(self):
        coords = [LatLon(0, 0), LatLon(0, 1), LatLon(0, 2), LatLon(1, 3)]
        simplified = simplify(coords, 0.01)
        self.assertEqual(simplified[0], coords[0])
        self.assertEqual(simplified[-1], coords[-1])
        self.assertLess(len(simplified), len(coords))

    def test_parallel_shift_is_distinct_and_a_copy_is_not(self):
        line = [LatLon(32, -97 + index * 0.5) for index in range(6)]
        shifted = [LatLon(point.lat + 0.5, point.lon) for point in line]
        copied = list(line)
        self.assertGreater(mean_separation_miles(line, shifted), 8)
        self.assertLess(mean_separation_miles(line, copied), 1)
