from django.test import SimpleTestCase


class ApiValidationTests(SimpleTestCase):
    def test_health(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_short_geocode_query_does_not_call_upstream(self):
        response = self.client.get("/api/geocode/", {"q": "d"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

    def test_interval_must_be_one_of_the_three_steps(self):
        response = self.client.post(
            "/api/plan/",
            data={
                "origin": {"query": "Dallas, TX"},
                "destination": {"query": "Denver, CO"},
                "departure": "2026-11-06T08:00",
                "load_weight_lb": 35000,
                "interval_miles": 15,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("10, 25, or 50", response.json()["detail"])

    def test_load_must_be_positive(self):
        response = self.client.post(
            "/api/plan/",
            data={
                "origin": {"lat": 32.7, "lon": -96.8, "label": "Dallas"},
                "destination": {"lat": 39.7, "lon": -104.9, "label": "Denver"},
                "departure": "2026-11-06T08:00",
                "load_weight_lb": 0,
                "interval_miles": 25,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Load weight", response.json()["detail"])

    def test_origin_is_required(self):
        response = self.client.post(
            "/api/plan/",
            data={
                "destination": {"query": "Denver, CO"},
                "departure": "2026-11-06T08:00",
                "load_weight_lb": 35000,
                "interval_miles": 25,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Origin", response.json()["detail"])

    def test_heatmap_requires_an_aware_departure(self):
        response = self.client.post(
            "/api/heatmap/",
            data={
                "geometries": [[[-96.8, 32.7], [-104.9, 39.7]]],
                "departure": "2026-11-06T08:00",
                "load_weight_lb": 35000,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("timezone", response.json()["detail"])
