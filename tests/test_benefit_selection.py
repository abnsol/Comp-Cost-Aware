import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pln_cost.benefit_selection import category, choose, native_ranks, selection_fixture
from pln_cost.benefit_signals import SCOPE


def record(term, stamp, confidence=.9):
    return ["Sentence", [term, ["stv", 1., confidence]], [stamp]]


class BenefitSelectionTests(unittest.TestCase):
    def setUp(self):
        self.model = dict(means=[0.]*10, scales=[1.]*10, weights=[0.]*10, intercept=1.)
        self.ready = record("R", 1)
        self.first = record(["Implication", "R", "C"], 2)
        self.goal = record(["Implication", "C", "G"], 3)
        self.idle = record("Idle", 4)
        self.state = dict(tasks=[self.goal, self.idle, self.ready, self.first],
                          beliefs=[self.goal, self.idle, self.ready, self.first])

    def pick(self, mode="BC", **kw):
        return choose(self.state, self.model, mode, query="G", marginals={}, **kw)

    def test_dormant_and_direct_work(self):
        self.assertEqual(native_ranks(**self.state, query="G", scope=SCOPE), ["covered", [0,0,1,1]])
        self.assertEqual(self.pick("N")[0], self.goal)
        for mode in ("B", "BO", "BC"):
            self.assertEqual(self.pick(mode)[0], self.ready)
        self.state["beliefs"].append(record("C", 5))
        selected, meta = self.pick()
        self.assertEqual(selected, self.goal)
        self.assertTrue(meta["singleton"])
        self.assertEqual(meta["predictions"], [])

    def test_expensive_required_work_is_not_displaced_by_idle(self):
        self.model["weights"][7] = 1.  # More MP matches predict greater expense.
        self.state["beliefs"].append(record(["Implication", "R", "Side"], 6))
        selected, meta = self.pick()
        self.assertEqual(selected, self.first)
        self.assertNotIn(self.idle, [r for r, _ in meta["predictions"]])
        self.assertEqual(self.pick("B")[0], self.ready)
        self.assertEqual(self.pick("BO")[0], self.ready)

    def test_cost_ties_invalid_predictions_and_unknown_coverage(self):
        self.assertEqual(self.pick()[0], self.ready)
        self.model["intercept"] = 10000.
        for mode in ("BO", "BC"):
            selected, meta = self.pick(mode)
            self.assertEqual(selected, self.ready)  # Benefit choice, not native dormant rule.
            self.assertTrue(meta["prediction_fallback"])
        selected, meta = self.pick(scope="unknown")
        self.assertEqual(selected, self.goal)
        self.assertTrue(meta["coverage_fallback"])

    def test_confidence_stays_primary_and_singleton_skips_description(self):
        self.idle[1][1][2] = .95
        with patch("pln_cost.benefit_selection.describe", side_effect=AssertionError("not needed")):
            for mode in ("B", "BO", "BC"):
                selected, meta = self.pick(mode)
                self.assertEqual(selected, self.idle)
                self.assertTrue(meta["singleton"])

    def test_represented_intermediates_and_counts_are_not_extra_value(self):
        self.state["beliefs"].append(record("C", 5))
        self.state["tasks"] = [self.ready, self.first, self.idle]
        self.assertEqual(native_ranks(**self.state, query="G", scope=SCOPE), ["covered", [1,1,0]])
        self.assertEqual(category(dict(potential_goal_pairs=0, missing_intermediate_pairs=4,
                                      represented_support_pairs=0)), 1)
        self.assertEqual(category(dict(potential_goal_pairs=0, missing_intermediate_pairs=0,
                                      represented_support_pairs=1)), 1)

    def test_overlap_and_removed_tasks(self):
        self.first[2] = self.ready[2][:]
        self.assertEqual(native_ranks(**self.state, query="G", scope=SCOPE), ["covered", [0,0,0,0]])
        self.first[2] = [2]
        self.state["tasks"] = [self.ready, self.idle]
        original = copy.deepcopy(self.state)
        self.assertEqual(self.pick()[0], self.ready)
        self.assertEqual(self.state, original)

    def test_unknown_marginals_empty_and_bad_mode(self):
        selected, meta = choose(self.state, self.model, "BC", query="G", marginals={"R": .5})
        self.assertEqual(selected, self.goal)
        self.assertTrue(meta["coverage_fallback"])
        self.assertEqual(choose(dict(tasks=[], beliefs=[]), self.model, "BC", query="G")[0], [])
        with self.assertRaises(ValueError):
            self.pick("typo")


if __name__ == "__main__":
    unittest.main()
