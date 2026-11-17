"""
Unit and integration tests for geographic location resolution and New York State
boundary verification (10001 - 14925, FIPS 36).
"""

import unittest
from fastapi.testclient import TestClient
from agent.tools import resolve_geographic_location_and_nearest_clinics
from agent.main import app


class TestGeoLocationValidation(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_valid_ny_zip_codes(self):
        """Verify valid New York State ZIP codes resolve to clinics in NY."""
        ny_zips = [
            ("10451", "Bronx"),
            ("10025", "Manhattan"),
            ("11201", "Brooklyn"),
            ("14094", "Lockport"),
            ("14701", "Jamestown"),
            ("13617", "Canton"),
            ("12953", "Malone"),
            ("13856", "Walton"),
            ("12207", "Albany"),
            ("13202", "Syracuse"),
        ]
        for zip_code, label in ny_zips:
            with self.subTest(zip_code=zip_code, label=label):
                res = resolve_geographic_location_and_nearest_clinics(zip_code, state_code="NY")
                self.assertEqual(res["status"], "success", f"Failed for {zip_code} ({label})")
                self.assertIn("resolved_location", res)
                self.assertTrue(res["resolved_location"]["census_tract_geoid"].startswith("36"))
                self.assertGreater(len(res["nearest_screening_clinics"]), 0)

    def test_out_of_state_zip_rejection(self):
        """Verify out-of-state ZIP codes return OUT_OF_STATE_ZIP error."""
        oos_zips = ["90210", "39201", "07030", "60601", "30301", "98101"]
        for zip_code in oos_zips:
            with self.subTest(zip_code=zip_code):
                res = resolve_geographic_location_and_nearest_clinics(zip_code, state_code="NY")
                self.assertEqual(res["status"], "error")
                self.assertEqual(res["error_code"], "OUT_OF_STATE_ZIP")
                self.assertIn("not in New York State", res["message"])

    def test_out_of_state_tract_rejection(self):
        """Verify non-NY Census tracts (not starting with 36) are rejected."""
        res = resolve_geographic_location_and_nearest_clinics("28011950200", state_code="NY")
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_code"], "OUT_OF_STATE_TRACT")

    def test_out_of_state_city_rejection(self):
        """Verify out-of-state city names are rejected."""
        res = resolve_geographic_location_and_nearest_clinics("Chicago", state_code="NY")
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["error_code"], "OUT_OF_STATE_CITY")

    def test_api_geo_resolve_endpoint(self):
        """Verify POST /api/geo/resolve endpoint behavior."""
        # Success case
        resp = self.client.post("/api/geo/resolve", json={"query": "10451", "state_code": "NY"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")

        # Out-of-state case
        resp_oos = self.client.post("/api/geo/resolve", json={"query": "90210", "state_code": "NY"})
        self.assertEqual(resp_oos.status_code, 200)
        data_oos = resp_oos.json()
        self.assertEqual(data_oos["status"], "error")
        self.assertEqual(data_oos["error_code"], "OUT_OF_STATE_ZIP")


if __name__ == "__main__":
    unittest.main()
