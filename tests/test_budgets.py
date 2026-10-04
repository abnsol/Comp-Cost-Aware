"""Budget misses must never become successes through offline proof knowledge."""
import json
from pathlib import Path
import sys
import unittest
import hashlib
from copy import deepcopy

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.budget import check_result, fixture
from pln_cost.qualification import expression
from pln_cost.sexpr import read_case
sys.path.insert(0, str(PROJECT / "scripts"))
from run_budgets import summarize, validation_matches


class BudgetTests(unittest.TestCase):
    def setUp(self):
        root = PROJECT / "results/qualification/step-04/run001"
        report = json.loads((root / "report.json").read_text())
        entry = report["cases"][0]
        path = PROJECT / entry["case"]
        folder = root / path.stem
        self.states = [json.loads(l) for l in (folder / "snapshots.jsonl").read_text().splitlines()]
        self.trace = (folder / "capture.stdout.txt").read_text()
        self.case = read_case(path.read_text())
        self.config = json.loads((root / "config.json").read_text())
        self.source_hash, self.fixture_hash = report["hashes"]["native_library"], entry["fixture_sha256"]
        self.goal = next(r for r in self.states[4]["state"]["beliefs"] if r[1][0] == self.case["query"])

    def check(self, row, budget):
        log = '(BUDGET_RESULT ' + expression(row) + ')'
        return check_result(log, budget, self.states, self.trace, self.case,
                            self.source_hash, self.fixture_hash, self.config["success"])[0]

    def row(self, status, step, cpu, answer):
        s = self.states[step]["state"]
        return [status, step, cpu, 2, cpu-1, answer, [s["tasks"], s["beliefs"]]]

    def test_return_boundary_is_inclusive_but_late_answer_is_a_miss(self):
        self.assertTrue(self.check(self.row('success', 4, 100, self.goal), 100)["verified_success"])
        with self.assertRaises(ValueError):
            self.check(self.row('success', 4, 101, self.goal), 100)
        late = self.check(self.row('late_return', 4, 101, self.goal), 100)
        self.assertFalse(late["verified_success"])
        self.assertTrue(late["detected_proof_verified"])

    def test_unobserved_late_goal_is_not_rescued_offline(self):
        late = self.check(self.row('deadline', 4, 110, []), 100)
        self.assertTrue(late["goal_in_final_state"])
        self.assertFalse(late["verified_success"])
        self.assertFalse(late["detected_proof_verified"])
        self.assertEqual(late["overshoot_ns"], 10)

    def test_false_success_changed_queues_and_bad_clocks_are_rejected(self):
        for row in (self.row('success', 3, 100, []), self.row('exhausted', 1, 100, []),
                    self.row('deadline', 1, 99, []), self.row('success', 5, 100, self.goal)):
            with self.assertRaises(ValueError):
                self.check(row, 100)
        row = self.row('success', 4, 100, self.goal)
        row[-1] = [[], []]
        with self.assertRaises(ValueError):
            self.check(row, 100)
        row = self.row('deadline', 0, 100, [])
        row[3] = 101
        with self.assertRaises(ValueError):
            self.check(row, 100)

    def test_zero_budget_and_no_oracle_online_inputs(self):
        r = self.check(self.row('deadline', 0, 100, []), 0)
        self.assertFalse(r["verified_success"])
        text = fixture(self.case, self.config, 250000)
        self.assertIn('250000 100 4097 4097', text)
        self.assertNotIn('Expected', text)
        self.assertNotIn('certificate', text)


class SavedBudgetTests(unittest.TestCase):
    def test_validation_has_native_parity_and_real_negative_cases(self):
        root = PROJECT / "results/qualification/step-08/validate/val001"
        report = json.loads((root / "report.json").read_text())
        self.assertTrue(report["passed"])
        self.assertEqual(len(report["runs"]), 20)
        audits = [r for r in report["runs"] if r["audit"]]
        self.assertEqual(len(audits), 9)
        self.assertTrue(all(r["result"]["audit_prefix_identical"] and r["result"]["verified_success"] for r in audits))
        zero, absent = report["runs"][-2:]
        self.assertEqual(zero["result"]["completed_expansions"], 0)
        self.assertEqual(zero["result"]["status"], "deadline")
        self.assertEqual(absent["result"]["status"], "exhausted")
        self.assertFalse(absent["result"]["goal_in_final_state"])

    def test_validation_binding_rejects_changed_execution(self):
        path = PROJECT / "results/qualification/step-08/validate/val001/report.json"
        report = json.loads(path.read_text())
        validation_matches(report, report)
        for field in ("hashes", "provenance_before", "project_source_sha256"):
            changed = deepcopy(report)
            if field == "project_source_sha256":
                changed[field]["scripts/run_budgets.py"] = "changed"
            else:
                changed[field] = {}
            with self.assertRaises(ValueError):
                validation_matches(report, changed)

    def test_complete_sweep_raw_outputs_proofs_and_summary_reproduce(self):
        root = PROJECT / "results/qualification/step-08/measure/run001"
        report = json.loads((root / "report.json").read_text())
        self.assertTrue(report["passed"])
        self.assertEqual(len(report["runs"]), 630)
        self.assertEqual(report["summary"], summarize(report["runs"]))
        self.assertEqual(len(report["summary"]), 63)
        self.assertTrue(all(s["n"] == 10 for s in report["summary"]))
        schedule = json.loads((root / "schedule.json").read_text())
        validation = PROJECT / "results/qualification/step-08/validate/val001/report.json"
        self.assertEqual(hashlib.sha256(validation.read_bytes()).hexdigest(), report["validation_sha256"])
        previous = PROJECT / "results/qualification/step-04/run001"
        prior = json.loads((previous / "report.json").read_text())
        config = json.loads((root / "config.json").read_text())
        data = {}
        for entry in prior["cases"]:
            fixture_path = PROJECT / entry["case"]
            name = fixture_path.stem
            folder = previous / name
            data[name] = (entry, read_case(fixture_path.read_text()),
                          [json.loads(l) for l in (folder / "snapshots.jsonl").read_text().splitlines()],
                          (folder / "capture.stdout.txt").read_text())
        for job, run in zip(schedule, report["runs"]):
            self.assertEqual(run["label"], f"rep-{job['repetition']:02d}/{job['name']}/ns-{job['budget_ns']}")
            folder = root / run["label"]
            raw = (folder / "stdout.txt").read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), run["stdout_sha256"])
            self.assertEqual(hashlib.sha256((folder / "trial.metta").read_bytes()).hexdigest(), run["fixture_sha256"])
            entry, case, states, trace = data[run["name"]]
            checked, cert, proof = check_result(raw.decode(), run["budget_ns"], states, trace, case,
                report["hashes"]["native"], entry["fixture_sha256"], config["success"])
            self.assertEqual(checked, run["result"])
            if cert:
                self.assertEqual(cert, json.loads((folder / "certificate.json").read_text()))
                self.assertEqual(proof, json.loads((folder / "replay.json").read_text()))


if __name__ == '__main__':
    unittest.main()
