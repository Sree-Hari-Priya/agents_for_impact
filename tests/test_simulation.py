"""
Unit and integration tests for the simulate_single_network_fix graph tool
and FastAPI simulation endpoint.
"""

import unittest
from fastapi.testclient import TestClient
from agent.tools import simulate_single_network_fix
from agent.main import app


class TestSimulateSingleNetworkFix(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_simulate_tool_indianola(self):
        """Verify Indianola coordinator (SYN-PROV-MS-011) simulation."""
        res = simulate_single_network_fix(coordinator_id="SYN-PROV-MS-011", state_code="MS")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["target_coordinator"]["coordinator_id"], "SYN-PROV-MS-011")
        self.assertEqual(res["target_coordinator"]["originally_breached_chains"], 7)
        # 6 of 7 breached chains drop under 45 days
        self.assertEqual(res["target_coordinator"]["breached_cases_dropped_under_45d"], 6)
        self.assertEqual(res["target_coordinator"]["total_child_days_saved"], 246)
        self.assertEqual(len(res["remediated_chain_details"]), 6)

    def test_simulate_tool_all_coordinators_ranking(self):
        """Verify all coordinators are simulated and ranked."""
        res = simulate_single_network_fix(state_code="MS")
        self.assertEqual(res["status"], "success")
        ranking = res["all_coordinators_simulation_ranking"]
        self.assertEqual(len(ranking), 4)
        for entry in ranking:
            self.assertIn("coordinator_id", entry)
            self.assertGreater(entry["originally_breached"], 0)
            self.assertGreater(entry["breaches_dropped_under_45d"], 0)
            self.assertGreater(entry["child_days_saved"], 0)

    def test_simulate_api_endpoint(self):
        """Verify FastAPI GET /api/network/simulate."""
        resp = self.client.get("/api/network/simulate?coordinator_id=SYN-PROV-MS-012&state_code=MS")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["target_coordinator"]["coordinator_id"], "SYN-PROV-MS-012")
        self.assertEqual(data["target_coordinator"]["originally_breached_chains"], 7)
        self.assertEqual(data["target_coordinator"]["breached_cases_dropped_under_45d"], 7)


if __name__ == "__main__":
    unittest.main()
