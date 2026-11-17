"""Unit test for UI look and feel: pastel colors and child-saving theme."""

import unittest
from fastapi.testclient import TestClient
from agent.main import app


class TestUITheme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.response = cls.client.get("/")

    def test_status_code_200(self):
        self.assertEqual(self.response.status_code, 200)

    def test_pastel_tokens_in_css(self):
        html = self.response.text
        self.assertIn("--pastel-sky: #f0f9ff;", html)
        self.assertIn("--pastel-mint: #f0fdf4;", html)
        self.assertIn("--pastel-peach: #fff7ed;", html)
        self.assertIn("--pastel-rose: #fff1f2;", html)
        self.assertIn("--pastel-lavender: #faf5ff;", html)
        self.assertIn("--pastel-butter: #fefce8;", html)

    def test_child_saving_thematic_elements(self):
        html = self.response.text
        self.assertIn("Saving Children's Milestones", html)
        self.assertIn("IDEA Part C 45-Day Statutory Protection", html)
        self.assertIn("Zero Lost Referrals", html)
        self.assertIn("Children at Risk of Age-Out", html)
        self.assertIn("Child-Days Saved by EHR Upgrade", html)
        self.assertIn("Protected IDEA Part C Route", html)

    def test_typography_and_pills(self):
        html = self.response.text
        self.assertIn("Quicksand", html)
        self.assertIn("Nunito", html)
        self.assertIn(".pastel-pill-chip", html)

    def test_multi_agent_cards_pastel_styling(self):
        html = self.response.text
        self.assertIn("border-top: 4px solid #38bdf8", html)  # Agent 1 Sky
        self.assertIn("border-top: 4px solid #fde047", html)  # Agent 2 Buttercup
        self.assertIn("border-top: 4px solid #86efac", html)  # Agent 3 Mint
        self.assertIn("border-top: 4px solid #d8b4fe", html)  # Agent 4 Lavender

    def test_svg_pathway_graph_pastel_theme(self):
        html = self.response.text
        self.assertIn("#7dd3fc", html)  # Pastel Sky node
        self.assertIn("#fde047", html)  # Pastel Buttercup node
        self.assertIn("#86efac", html)  # Pastel Mint node
        self.assertIn("❤️", html)         # Child-saving heart protection badge

    def test_javascript_syntax_clean(self):
        """Ensure all embedded <script> tags pass syntax validation with node --check."""
        import re, subprocess, tempfile
        html = self.response.text
        matches = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
        for i, content in enumerate(matches):
            if not content.strip():
                continue
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
                f.write(content)
                tmp_name = f.name
            try:
                res = subprocess.run(["node", "--check", tmp_name], capture_output=True, text=True)
                self.assertEqual(
                    res.returncode, 0,
                    f"Embedded script {i} has syntax error:\n{res.stderr}"
                )
            finally:
                import os
                if os.path.exists(tmp_name):
                    os.remove(tmp_name)

    def test_zip_auto_selector_and_graph_markup(self):
        """Ensure ZIP selector has onchange/Enter listeners and triage graph is defined."""
        html = self.response.text
        self.assertIn('id="geoInput"', html)
        self.assertIn('oninput="debounceGeoResolve()"', html)
        self.assertIn('onchange="resolveLocationNow()"', html)
        self.assertIn('setGeoLocation(\'10451\')', html)
        self.assertIn('setGeoLocation(\'10025\')', html)
        self.assertIn('setGeoLocation(\'14094\')', html)
        self.assertIn('setGeoLocation(\'13617\')', html)
        self.assertIn('id="triageGraphCard"', html)
        self.assertIn('id="svgTriagePathway"', html)


if __name__ == "__main__":
    unittest.main()

