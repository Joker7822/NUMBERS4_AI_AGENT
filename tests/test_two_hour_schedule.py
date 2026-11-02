"""Protect the two-hour history -> research evolution -> public dashboard schedule."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TwoHourlyPipelineTests(unittest.TestCase):
    def test_single_cron_owns_refresh_at_every_even_jst_hour(self):
        history = (ROOT / ".github/workflows/online-learning.yml").read_text(encoding="utf-8")
        research = (ROOT / ".github/workflows/predictive-research.yml").read_text(encoding="utf-8")
        jobs = re.findall(r"^\s+- cron: '([^']+)'", history, re.M)
        self.assertEqual(jobs, ["0 1-23/2 * * *"])
        # GitHub cron is in UTC; adding +9 hours produces 00,02,...22 JST.
        utc_hours = list(range(1, 24, 2))
        self.assertEqual(sorted((hour + 9) % 24 for hour in utc_hours),
                         list(range(0, 24, 2)))
        self.assertIn("cancel-in-progress: false", history)
        self.assertNotRegex(research, r"(?m)^  schedule:")
        self.assertNotRegex(research, r"(?m)^\s+- cron:")

    def test_online_history_success_triggers_one_research_and_dashboard_cycle(self):
        history = (ROOT / ".github/workflows/online-learning.yml").read_text(encoding="utf-8")
        research = (ROOT / ".github/workflows/predictive-research.yml").read_text(encoding="utf-8")
        match = re.search(r"^name: (.+)$", history, re.M)
        self.assertIsNotNone(match)
        self.assertIn("workflows: ['" + match.group(1) + "']", research)
        self.assertIn("types: [completed]", research)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", research)
        self.assertIn("needs: discover-evolve-and-replay-all", research)
        self.assertIn("deploy-current-evolved-dashboard:", research)
        self.assertIn("git reset --hard origin/main", research)
        self.assertIn("latest_verification", research)
        self.assertIn("python -m numbers4_agent.cli --root . refresh-secondary", history)
        self.assertIn("python -m numbers4_agent.cli --root . replay-history", history)
        self.assertIn("result=cycle(Path('.'),queries=questions or None,", research)
        self.assertIn("result['first_evaluated_round']==2", research)
        self.assertIn("model_auto_promotion_authorized", research)
