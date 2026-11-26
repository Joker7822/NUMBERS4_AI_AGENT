"""Keep unreviewed PR code off the dedicated official-source runner."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OfficialWorkflowIsolationTests(unittest.TestCase):
    def test_pr_job_uses_hosted_read_only_runner(self):
        workflow = (ROOT / ".github/workflows/official-results.yml").read_text()
        pr = workflow.split("  pull-request-validation:\n", 1)[1].split(
            "\n  fetch-and-verify:\n", 1)[0]
        self.assertIn("if: github.event_name == 'pull_request'", pr)
        self.assertIn("runs-on: ubuntu-latest", pr)
        self.assertIn("contents: read", pr)
        self.assertIn("persist-credentials: false", pr)
        self.assertNotIn("NUMBERS4_OFFICIAL_RUNNER", pr)
        self.assertNotIn("contents: write", pr)
        self.assertNotIn("git push", pr)

    def test_pr_concurrency_never_uses_the_production_lock(self):
        workflow = (ROOT / ".github/workflows/official-results.yml").read_text()
        concurrency = workflow.split("\nconcurrency:\n", 1)[1].split("\njobs:\n", 1)[0]
        self.assertIn("github.event_name == 'pull_request' && format('numbers4-official-feed-pr-{0}', github.event.pull_request.number) || 'numbers4-official-feed-main'", concurrency)
        self.assertIn("cancel-in-progress: ${{ github.event_name == 'pull_request' }}", concurrency)
        self.assertNotIn("group: numbers4-official-feed-main", concurrency)

    def test_official_runner_requires_main_and_non_pr_event(self):
        workflow = (ROOT / ".github/workflows/official-results.yml").read_text()
        production = workflow.split("  fetch-and-verify:\n", 1)[1].split(
            "\n  deploy-current-dashboard:\n", 1)[0]
        self.assertIn("if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'", production)
        self.assertIn("vars.NUMBERS4_OFFICIAL_RUNNER", production)
        self.assertIn("contents: write", production)
        self.assertIn("issues: write", production)
        deploy = workflow.split("  deploy-current-dashboard:\n", 1)[1]
        self.assertIn("if: github.event_name != 'pull_request' && github.ref == 'refs/heads/main'", deploy)


if __name__ == "__main__":
    unittest.main()
