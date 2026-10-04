"""Measurement validation must fail on bad intervals or changed native work."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.expansion import chosen_record, counters, parse_trial, reference_fixture, build_expansion
from pln_cost.qualification import kb_records
from pln_cost.sexpr import read_forms


class ExpansionTests(unittest.TestCase):
    def setUp(self):
        self.state = {"tasks": kb_records(1), "beliefs": kb_records(1), "next_step": 1,
                      "task_limit": 4097, "belief_limit": 4097, "maxsteps": 100}

    def test_reference_preserves_other_task_order_and_beliefs(self):
        original = deepcopy(self.state)
        selected = self.state["tasks"][1]
        form = read_forms(reference_fixture(self.state, selected))[-1][1][1]
        self.assertEqual(form[0], "PLN.Derive")
        self.assertEqual(form[1], [selected, self.state["tasks"][0]] + self.state["tasks"][2:])
        self.assertEqual(form[2], self.state["beliefs"])
        self.assertEqual(form[3:], [1, 1, 4097, 4097])
        self.assertEqual(self.state, original)

    def test_absent_or_lower_priority_candidates_rejected(self):
        other = deepcopy(self.state["tasks"][0])
        other[1][1][2] = .1
        with self.assertRaisesRegex(ValueError, "pending"):
            chosen_record(self.state, other)
        self.state["tasks"][0] = other
        with self.assertRaisesRegex(ValueError, "maximum-priority"):
            chosen_record(self.state, other)

    def test_bad_clock_intervals_rejected(self):
        for interval in ("-1 2 1", "1 2 4", "1.0 2 3", "1 2"):
            with self.assertRaisesRegex(ValueError, "CPU intervals"):
                parse_trial(f"(COST_TIMES {interval})")
        with self.assertRaises(ValueError):
            parse_trial("(COST_TIMES 1 2 3)\n(COST_TIMES 1 2 3)")

    def test_unknown_source_rejected(self):
        with self.assertRaises(ValueError):
            build_expansion("not native PLN")

    def test_actual_boolean_spelling_and_missing_counter_rejection(self):
        # Retain the first failed validation: its counter parser expected True,
        # whereas PeTTa's output spelling is true. Native work itself matched.
        path = PROJECT / "results/qualification/step-05/run001/n001-canonical_ids-s000-route_a/audit.stdout.txt"
        log = path.read_text()
        trial = parse_trial(log)
        result = counters(self.state, self.state["tasks"][0], trial, log)
        self.assertEqual(result["visited_premise_pairs"], 6)
        self.assertEqual(result["stamp_disjoint_pairs"], 5)
        self.assertEqual(result["generated_binary_results"], 1)
        with self.assertRaisesRegex(ValueError, "counters"):
            counters(self.state, self.state["tasks"][0], trial, log.replace("(COST_GUARD false)\n", ""))
        with self.assertRaisesRegex(ValueError, "dispatch"):
            counters(self.state, self.state["tasks"][0], trial, log.replace("(COST_ATTEMPT unary)\n", ""))


class RecordedExpansionTests(unittest.TestCase):
    def test_all_native_counter_and_timing_records(self):
        root = PROJECT / "results/qualification/step-05/run002"
        report = json.loads((root / "report.json").read_text())
        self.assertTrue(report["passed"])
        self.assertEqual(len(report["trials"]), 36)
        for result in report["trials"]:
            folder = root / result["name"]
            with self.subTest(trial=result["name"]):
                source = json.loads((folder / "input.json").read_text())
                state = source["state"]
                logs = {}
                for mode in ("reference", "timed", "audit"):
                    raw = (folder / f"{mode}.stdout.txt").read_bytes()
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), result["runs"][mode]["stdout_sha256"])
                    logs[mode] = raw.decode()
                timed, audited = parse_trial(logs["timed"]), parse_trial(logs["audit"])
                self.assertEqual(timed["queues"], audited["queues"])
                self.assertEqual(timed["derivations"], audited["derivations"])
                from pln_cost.expansion import marked
                self.assertEqual(marked(logs["reference"], "COST_REFERENCE"), [timed["queues"]])
                chosen = chosen_record(state, source["requested"])
                self.assertEqual(counters(state, chosen, audited, logs["audit"]), result["counters"])
        diagnostic = next(t for t in report["trials"] if t["kind"] == "synthetic_cap_boundary_check")
        self.assertEqual(diagnostic["counters"]["tasks_removed_by_cap"], 5)
        self.assertEqual(diagnostic["counters"]["beliefs_removed_by_cap"], 6)


if __name__ == "__main__":
    unittest.main()
