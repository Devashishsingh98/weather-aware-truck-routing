from django.test import SimpleTestCase

from planner.services.errors import ExternalServiceError
from planner.services.geo import LatLon
from planner.services.routing import parse_osrm_response, routes_are_distinct


class OsrmParseTests(SimpleTestCase):
    def test_segment_times_are_scaled_to_the_published_duration(self):
        payload = {
            "code": "Ok",
            "routes": [
                {
                    "distance": 1000,
                    "duration": 100,
                    "geometry": {"coordinates": [[0, 0], [0, 1], [0, 2]]},
                    "legs": [
                        {
                            "distance": 1000,
                            "duration": 100,
                            "annotation": {"distance": [400, 600], "duration": [10, 10]},
                        }
                    ],
                }
            ],
        }
        route = parse_osrm_response(payload)[0]
        self.assertEqual(route.coords, [LatLon(0, 0), LatLon(1, 0), LatLon(2, 0)])
        self.assertEqual(route.segment_distances_m, [400, 600])
        self.assertEqual(route.segment_durations_s, [50, 50])

    def test_misaligned_annotations_fall_back_to_the_route_totals(self):
        payload = {
            "code": "Ok",
            "routes": [
                {
                    "distance": 1000,
                    "duration": 100,
                    "geometry": {"coordinates": [[0, 0], [0, 1], [0, 2]]},
                    "legs": [
                        {
                            "distance": 1000,
                            "duration": 100,
                            "annotation": {"distance": [1000], "duration": [100]},
                        }
                    ],
                }
            ],
        }
        route = parse_osrm_response(payload)[0]
        self.assertEqual(len(route.segment_distances_m), 2)
        self.assertAlmostEqual(sum(route.segment_distances_m), 1000)
        self.assertAlmostEqual(sum(route.segment_durations_s), 100)

    def test_no_route_is_an_error(self):
        with self.assertRaises(ExternalServiceError):
            parse_osrm_response({"code": "NoRoute", "message": "No route found between points"})


class DistinctRouteTests(SimpleTestCase):
    def test_offset_line_is_kept_and_duplicate_is_not(self):
        line = [LatLon(32 + index, -97) for index in range(5)]
        offset = [LatLon(point.lat, point.lon + 0.4) for point in line]
        self.assertTrue(routes_are_distinct(offset, [line]))
        self.assertFalse(routes_are_distinct(list(line), [line]))
