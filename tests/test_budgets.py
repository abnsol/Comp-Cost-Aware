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


class BudgetTests(unittest.TestCase):
    def setUp(self):
        root = PROJECT / "results/benefit-benchmark/run001"
        entry = next(e for e in json.loads((root / "manifest.json").read_text()) if e["name"] == "n001-canonical_ids")
        folder = root / "audits/n001-canonical_ids/N"
        self.states = json.loads((folder / "states.json").read_text())
        self.trace = (folder / "audit.stdout.txt").read_text()
        self.case = read_case((root / entry["fixture"]).read_text())
        self.config = json.loads((root / "qualification-config.json").read_text())
        self.source_hash = json.loads((root / "freeze.json").read_text())["native_library_sha256"]
        self.fixture_hash = entry["fixture_sha256"]
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
                    self.row('deadline', 1, 99, []), self.row('success', 3, 100, self.goal)):
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



if __name__ == '__main__':
    unittest.main()
