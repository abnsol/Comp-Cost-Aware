"""Thin adapter schedules preserve state, balancing and reviewed limits."""
from copy import deepcopy
import json
import hashlib
from pathlib import Path
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.thin import diagnostic_fixture, thin_fixture
from pln_cost.paired import parse, summarize_process
from pln_cost.sexpr import read_one


class ThinFixtureTests(unittest.TestCase):
    def setUp(self):
        self.protocol = json.loads((PROJECT / "configs/paired-protocol.json").read_text())
        self.condition = json.loads((PROJECT / "results/qualification/step-06/calibrate/cal001/conditions.json").read_text())[0]

    def test_singleton_schedule_preserves_original_inputs(self):
        before = deepcopy(self.condition)
        text, schedule = thin_fixture("; helper", self.condition, self.protocol, 1949, 30, 30)
        self.assertEqual(self.condition, before)
        self.assertEqual(len(schedule), 130)
        self.assertTrue(all(row[3] == 1 for row in schedule))
        measured = [s for s in schedule if s[0] == "Measured"]
        self.assertEqual(sum(s[2] == "A" for s in measured), 30)
        self.assertEqual(sum(s[2] == "B" for s in measured), 30)
        self.assertEqual(sum(measured[i][2] == "A" for i in range(0, len(measured), 2)), 15)
        self.assertNotIn("Bench.Batch", text)
        self.assertEqual(text.count("!(thin_verify"), 2)
        self.assertIn("(Bench.TaskLimit) 4097", text)

    def test_diagnostics_are_fixed_and_balanced_across_variants(self):
        _, schedule = diagnostic_fixture("; helper", self.condition, 1949)
        self.assertEqual(len(schedule), 440)
        measured = [s for s in schedule if s[0] == "Measured"]
        counts = {}
        for _, _, label, k in measured:
            counts[label, k] = counts.get((label, k), 0) + 1
        self.assertEqual(len(counts), 11)
        self.assertEqual(set(counts.values()), {30})


class SavedThinTests(unittest.TestCase):
    def test_diagnostic_samples_match_predeclared_schedule(self):
        root = PROJECT / "results/qualification/step-06/repair/diagnose/diag001"
        report = json.loads((root / "report.json").read_text())
        self.assertTrue(report["passed"])
        self.assertEqual(len(report["runs"]), 3)
        for run in report["runs"]:
            folder = root / run["name"]
            raw = (folder / "stdout.txt").read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), run["stdout_sha256"])
            rows = [read_one(l)[1:] for l in raw.decode().splitlines() if l.startswith("(HARNESS_DIAG ")]
            self.assertEqual([r[:4] for r in rows], json.loads((folder / "schedule.json").read_text()))

    def test_validated_adapter_and_unchanged_calibration_gate(self):
        base = PROJECT / "results/qualification/step-06/repair"
        for stage, ident, count in (("validate", "val001", 13), ("calibrate", "cal002", 3)):
            root = base / stage / ident
            report = json.loads((root / "report.json").read_text())
            self.assertTrue(report["passed"])
            self.assertEqual(len(report["runs"]), count)
            for run in report["runs"]:
                folder = root / run["name"]
                raw = (folder / "stdout.txt").read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), run["stdout_sha256"])
                schedule = json.loads((folder / "schedule.json").read_text())
                checked = summarize_process(parse(raw.decode(), schedule))
                self.assertEqual(checked["median_cpu_ns"], run["summary"]["median_cpu_ns"])
                if stage == "calibrate":
                    self.assertLessEqual(checked["empty_p95_fraction"], .10)
            if stage == "validate":
                self.assertTrue(report["invalid_expected_rejected"])
                self.assertIn("thin_native_output_mismatch", (root / "invalid-expected.stderr.txt").read_text())
            else:
                self.assertEqual(report["accepted_batch_size"], 1)
                self.assertTrue(report["overhead_gate_passed"])
                protocol = json.loads((root / "protocol.json").read_text())
                self.assertEqual(protocol["maximum_empty_p95_fraction"], .10)


if __name__ == "__main__":
    unittest.main()
