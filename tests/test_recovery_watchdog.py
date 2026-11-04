"""Exercise checkout-free GitHub issue recovery without a .git directory."""
from pathlib import Path
import os
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "recovery-watchdog.yml"


def recovery_shell() -> str:
    """Extract the actual GitHub Actions step, not a test-only copy."""
    source = WORKFLOW.read_text(encoding="utf-8")
    after = source.split("      - name: Open deduplicated incident after repeated failure\n", 1)[1]
    lines = after.split("        run: |\n", 1)[1].splitlines()
    script = []
    for line in lines:
        if line and not line.startswith("          "):
            break
        script.append(line)
    return textwrap.dedent("\n".join(script)) + "\n"


class RecoveryWatchdogTests(unittest.TestCase):
    def run_recovery(self, *, existing: str = "", list_exit: int = 0):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gh = root / "gh"
            gh.write_text(textwrap.dedent("""\\
                #!/usr/bin/env bash
                printf '%s\\n' "$*" >> "$GH_ARGS_LOG"
                if [[ "$1" == issue && "$2" == list ]]; then
                  printf '%s\\n' "$FAKE_GH_ISSUES"
                  exit "$FAKE_GH_LIST_EXIT"
                fi
                if [[ "$1" == issue && "$2" == create ]]; then
                  printf 'https://github.com/example/repo/issues/1\\n'
                  exit 0
                fi
                exit 99
                """), encoding="utf-8")
            gh.chmod(0o755)
            log = root / "calls.txt"
            env = os.environ.copy()
            env.update({
                "PATH": str(root) + os.pathsep + env["PATH"],
                "GH_ARGS_LOG": str(log),
                "GITHUB_REPOSITORY": "Joker7822/NUMBERS4_AI_AGENT",
                "FAILED_NAME": "Numbers4 Historical Round2 Replay and Online Research Update",
                "FAILED_URL": "https://github.com/Joker7822/NUMBERS4_AI_AGENT/actions/runs/1",
                "RUN_ID": "1", "RUN_ATTEMPT": "2",
                "FAKE_GH_ISSUES": existing,
                "FAKE_GH_LIST_EXIT": str(list_exit),
            })
            result = subprocess.run(
                ["bash", "-c", recovery_shell()], cwd=root,
                env=env, capture_output=True, text=True, check=False,
            )
            return result, log.read_text(encoding="utf-8") if log.exists() else ""

    def test_creates_incident_without_checkout(self):
        result, calls = self.run_recovery()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("issue list --repo Joker7822/NUMBERS4_AI_AGENT", calls)
        self.assertIn("issue create --repo Joker7822/NUMBERS4_AI_AGENT", calls)

    def test_duplicate_incident_is_not_created(self):
        title = ("Numbers4 recurrent workflow failure: "
                 "Numbers4 Historical Round2 Replay and Online Research Update")
        result, calls = self.run_recovery(existing=title)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Existing incident remains open", result.stdout)
        self.assertNotIn("issue create", calls)

    def test_api_failure_does_not_create_duplicate_incident(self):
        result, calls = self.run_recovery(list_exit=22)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("issue list", calls)
        self.assertNotIn("issue create", calls)


if __name__ == "__main__":
    unittest.main()
