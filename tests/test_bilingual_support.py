"""
Unit tests for bilingual Spanish support in Agents for Impact.
Verifies:
1. Spanish natural language geographic resolution (e.g. 'el bronx', 'código postal 10451', 'búfalo').
2. Out-of-state Spanish city detection and jurisdiction rejection (e.g. 'los ángeles').
3. Multi-agent triage pipeline with bilingual Spanish evaluation mandate.
"""

import unittest
from agent.tools import (
    resolve_geographic_location_and_nearest_clinics,
    execute_multi_agent_triage_with_traces,
    find_compliant_toddler_pathway,
)


class TestBilingualSupport(unittest.TestCase):

    def test_spanish_borough_and_city_resolution(self):
        """Verify Spanish names and aliases for New York locations resolve accurately."""
        # 1. 'el bronx'
        res_bronx = resolve_geographic_location_and_nearest_clinics("el bronx")
        self.assertEqual(res_bronx["status"], "success")
        self.assertIn("resolved_location", res_bronx)
        self.assertEqual(res_bronx["resolved_location"]["census_tract_geoid"], "36005019700")
        self.assertIn("Bronx", res_bronx["resolved_location"]["display_name"])
        self.assertTrue(len(res_bronx["nearest_screening_clinics"]) > 0)

        # 2. 'ciudad de nueva york'
        res_nyc = resolve_geographic_location_and_nearest_clinics("ciudad de nueva york")
        self.assertEqual(res_nyc["status"], "success")
        self.assertTrue(res_nyc["resolved_location"]["census_tract_geoid"].startswith("36"))
        self.assertIn("Nueva York", res_nyc["resolved_location"]["display_name"])

        # 3. 'búfalo' (with accent)
        res_bufalo = resolve_geographic_location_and_nearest_clinics("búfalo")
        self.assertEqual(res_bufalo["status"], "success")
        self.assertTrue(res_bufalo["resolved_location"]["census_tract_geoid"].startswith("36"))
        self.assertIn("Búfalo", res_bufalo["resolved_location"]["display_name"])

        # 4. 'cataratas del niagara'
        res_niagara = resolve_geographic_location_and_nearest_clinics("cataratas del niagara")
        self.assertEqual(res_niagara["status"], "success")
        self.assertEqual(res_niagara["resolved_location"]["census_tract_geoid"], "36063022901")

    def test_spanish_zip_phrasing_resolution(self):
        """Verify Spanish phrases containing ZIP codes extract and resolve the 5-digit NY ZIP."""
        # 'código postal 10451'
        res_cp = resolve_geographic_location_and_nearest_clinics("código postal 10451")
        self.assertEqual(res_cp["status"], "success")
        self.assertIn("resolved_location", res_cp)
        self.assertEqual(res_cp["resolved_location"]["census_tract_geoid"], "36005019700")
        self.assertIn("10451", res_cp["resolved_location"]["display_name"])

        # 'CP 14094' (Lockport)
        res_cp2 = resolve_geographic_location_and_nearest_clinics("CP 14094")
        self.assertEqual(res_cp2["status"], "success")
        self.assertEqual(res_cp2["resolved_location"]["census_tract_geoid"], "36063023901")
        self.assertIn("14094", res_cp2["resolved_location"]["display_name"])

    def test_spanish_out_of_state_rejection(self):
        """Verify Spanish out-of-state city names are rejected immediately."""
        res_oos = resolve_geographic_location_and_nearest_clinics("los ángeles")
        self.assertEqual(res_oos["status"], "error")
        self.assertEqual(res_oos["error_code"], "OUT_OF_STATE_CITY")
        self.assertIn("outside New York State", res_oos["message"])

    def test_bilingual_triage_pathway(self):
        """Verify that requiring bilingual services routes to a verified bilingual hub."""
        # Route a 22-month-old in Bronx tract with Medicaid and Bilingual Evaluator
        res = find_compliant_toddler_pathway(
            child_age_months=22,
            census_tract_geoid="36005019700",
            requires_medicaid=True,
            requires_bilingual=True,
            max_wait_days=45,
        )
        self.assertTrue(len(res["recommended_pathways"]) > 0)
        best = res["recommended_pathways"][0]
        self.assertTrue(best["eval_bilingual"], "Recommended hub must have verified bilingual capacity")
        self.assertLessEqual(best["total_estimated_wait_days"], 45, "Must satisfy federal 45-day clock")

    def test_multi_agent_execution_with_bilingual_caregiver_note(self):
        """Verify multi-agent triage execution generates both English and Spanish family notes."""
        result = execute_multi_agent_triage_with_traces(
            child_age_months=20,
            census_tract_geoid="36005019700",
            requires_medicaid=True,
            requires_bilingual=True,
            max_wait_days=45,
            state_code="NY"
        )
        self.assertIn("trace_id", result)
        self.assertIn("agent_breakdown", result)
        breakdown = result["agent_breakdown"]
        self.assertIn("agents", breakdown)
        agent_names = [a["agent_name"] for a in breakdown["agents"]]
        self.assertIn("caregiver_note_agent", agent_names)

        caregiver_agent = next(a for a in breakdown["agents"] if a["agent_name"] == "caregiver_note_agent")
        cg_out = caregiver_agent["output"]
        self.assertIn("languages_generated", cg_out)
        self.assertIn("Spanish", cg_out["languages_generated"])
        self.assertIn("English", cg_out["languages_generated"])
        self.assertIn("34 CFR § 303.310", cg_out["statutory_rights_included"])


if __name__ == "__main__":
    unittest.main()
