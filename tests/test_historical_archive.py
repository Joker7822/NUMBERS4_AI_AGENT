"""Full historical archive is descriptive, never an official result attestation."""
import json
import tempfile
import unittest
from pathlib import Path

from numbers4_agent.historical_archive import (
    ARCHIVE, PROVENANCE, STATUS, _git_blob_sha1, archive_summary, load_archive,
)


class HistoricalArchiveTests(unittest.TestCase):
    def test_all_7104_draws_contiguous_with_leading_zeroes(self):
        rows, meta = load_archive(Path("."))
        self.assertEqual(len(rows), 7104)
        self.assertEqual([r["round"] for r in rows], list(range(1, 7105)))
        self.assertEqual(rows[0], {"round": 1, "draw_date": "1994-10-07",
                                   "winning_number": "1149"})
        self.assertEqual(rows[2]["winning_number"], "0097")
        self.assertEqual(rows[-1], {"round": 7104, "draw_date": "2026-10-30",
                                    "winning_number": "5805"})
        self.assertFalse(meta["officially_verified"])
        self.assertFalse(meta["forecast_grading_authorized"])
        summary = archive_summary(Path("."))
        self.assertEqual(summary["status"], STATUS)
        self.assertEqual(summary["record_count"], 7104)

    def fixture(self):
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name)
        (root / "data").mkdir()
        for src in (ARCHIVE, PROVENANCE):
            (root / src).write_bytes(src.read_bytes())
        return directory, root

    def test_missing_both_is_explicitly_unavailable(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(archive_summary(Path(temp))["status"], "not_loaded")
            self.assertEqual(archive_summary(Path(temp))["record_count"], 0)

    def test_tampered_number_fails_hash_proof(self):
        temporary, root = self.fixture()
        with temporary:
            path = root / ARCHIVE
            raw = path.read_text(encoding="utf-8")
            self.assertIn("3,1994-10-21,0097", raw)
            path.write_text(raw.replace("3,1994-10-21,0097",
                                        "3,1994-10-21,0098", 1), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "provenance mismatch"):
                load_archive(root)

    def test_even_rehashed_missing_round_fails(self):
        temporary, root = self.fixture()
        with temporary:
            path = root / ARCHIVE
            lines = path.read_text(encoding="utf-8").splitlines()
            path.write_text("\n".join(lines[:300] + lines[301:]) + "\n", encoding="utf-8")
            meta_path = root / PROVENANCE
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["git_blob_sha1"] = _git_blob_sha1(path.read_bytes())
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing, duplicate or reordered round"):
                load_archive(root)

    def test_unsafe_official_claim_fails_closed(self):
        temporary, root = self.fixture()
        with temporary:
            path = root / PROVENANCE
            meta = json.loads(path.read_text(encoding="utf-8"))
            meta["officially_verified"] = True
            path.write_text(json.dumps(meta), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsafe authority"):
                load_archive(root)

    def test_archive_does_not_create_production_observations(self):
        from numbers4_agent.sources import corroborated_draws
        from numbers4_agent.evaluation import graded_predictions
        self.assertEqual(corroborated_draws(Path(".")), [])
        self.assertEqual(graded_predictions(Path(".")), [])


if __name__ == "__main__":
    unittest.main()
