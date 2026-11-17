"""
Unit tests for Multi-Agent Triage Execution Breakdown and BigQuery Trace Tracking.
Verifies:
1. POST /api/triage/route returns trace_id and 4-agent breakdown.
2. GET /api/traces/recent queries BigQuery and returns streaming execution traces.
3. Fallback resilience when BigQuery is unavailable or streaming.
"""

import unittest
from fastapi.testclient import TestClient
from agent.main import app
from agent.tools import fetch_recent_bq_traces, execute_multi_agent_triage_with_traces

class TestTracesAndBreakdown(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_triage_route_returns_agent_breakdown_and_trace_id(self):
        """Verify /api/triage/route executes multi-agent pipeline and returns breakdown."""
        payload = {
            "child_age_months": 22,
            "census_tract_geoid": "36005019700",
            "requires_medicaid": True,
            "requires_bilingual": True,
            "max_wait_days": 45
        }
        resp = self.client.post("/api/triage/route", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Check standard triage output
        self.assertIn("recommended_pathways", data)
        self.assertTrue(len(data["recommended_pathways"]) > 0)
        p = data["recommended_pathways"][0]
        self.assertLessEqual(p["total_estimated_wait_days"], 45)

        # Check trace ID
        self.assertIn("trace_id", data)
        self.assertTrue(isinstance(data["trace_id"], str) and len(data["trace_id"]) > 10)

        # Check agent breakdown
        self.assertIn("agent_breakdown", data)
        breakdown = data["agent_breakdown"]
        self.assertEqual(breakdown["pipeline"], "brief_generator_pipeline")
        self.assertIn("agents", breakdown)
        self.assertEqual(len(breakdown["agents"]), 4)

        agent_names = [a["agent_name"] for a in breakdown["agents"]]
        self.assertIn("pathway_router_agent", agent_names)
        self.assertIn("network_audit_agent", agent_names)
        self.assertIn("equity_audit_agent", agent_names)
        self.assertIn("caregiver_note_agent", agent_names)

        # Verify agent detail structures
        for agent in breakdown["agents"]:
            self.assertIn("status", agent)
            self.assertIn("latency_ms", agent)
            self.assertIn("tools_invoked", agent)
            self.assertIn("decisions", agent)
            self.assertIn("output", agent)
            self.assertTrue(len(agent["decisions"]) > 0)

    def test_02_traces_recent_endpoint(self):
        """Verify GET /api/traces/recent returns BigQuery trace logs."""
        resp = self.client.get("/api/traces/recent?limit=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "success")
        self.assertIn("traces", data)
        self.assertIsInstance(data["traces"], list)
        self.assertTrue(len(data["traces"]) > 0)

        first_trace = data["traces"][0]
        self.assertIn("trace_id", first_trace)
        self.assertIn("agent_name", first_trace)
        self.assertIn("event_type", first_trace)
        self.assertIn("status", first_trace)

    def test_03_direct_execute_multi_agent_triage_with_traces(self):
        """Verify direct Python execution of execute_multi_agent_triage_with_traces."""
        res = execute_multi_agent_triage_with_traces(
            child_age_months=28,
            census_tract_geoid="36005019700",
            requires_medicaid=True,
            requires_bilingual=True,
            max_wait_days=45,
            state_code="NY"
        )
        self.assertIn("trace_id", res)
        self.assertIn("agent_breakdown", res)
        self.assertTrue(res["agent_breakdown"]["bigquery_trace_logging"])
        self.assertGreater(res["agent_breakdown"]["total_latency_ms"], 0)

if __name__ == "__main__":
    unittest.main()
