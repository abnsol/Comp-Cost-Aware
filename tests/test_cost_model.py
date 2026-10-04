"""Prospective-feature parity and restricted selection semantics."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.cost_features import FEATURE_NAMES, features, eligible_candidates
from pln_cost.cost_model import feature_rows, choose, fit, structure_group
from pln_cost.selection_workloads import necessary_records


class CostModelTests(unittest.TestCase):
    def setUp(self):
        self.records = necessary_records(4)
        self.state = {"tasks": self.records, "beliefs": self.records}
        self.model = {"intercept": 5., "means": [0.]*10, "scales": [1.]*10, "weights": [0.]*10}

    def test_shared_features_match_slow_reference_and_do_not_mutate(self):
        before = deepcopy(self.state)
        expected = [(c, [features(self.state, c)[f] for f in FEATURE_NAMES]) for c in eligible_candidates(self.state)]
        self.assertEqual(feature_rows(self.state), expected)
        self.assertEqual(self.state, before)

    def test_cost_never_overrides_confidence_or_changes_equal_estimate_order(self):
        self.assertEqual(choose(self.state, self.model, "C")[0], self.records[0])
        self.records[-1][1][1][2] = .91
        selected, predictions = choose(self.state, self.model, "C")
        self.assertEqual(selected, self.records[-1])
        self.assertEqual(predictions, [])

    def test_overhead_control_and_invalid_prediction_keep_native_choice(self):
        self.model["weights"][7] = 1.
        self.assertNotEqual(choose(self.state, self.model, "C")[0], self.records[0])
        self.assertEqual(choose(self.state, self.model, "O")[0], self.records[0])
        self.model["intercept"] = 10000.
        self.assertEqual(choose(self.state, self.model, "C")[0], self.records[0])

    def test_structure_group_keeps_orderings_together(self):
        for name in ("n016-canonical_ids", "n016-seeded_shuffle"):
            self.assertEqual(structure_group({"case": name}), "n016")
        for name in ("necessary-w004-canonical_ids", "necessary-w004-swap_required_pair"):
            self.assertEqual(structure_group({"case": name}), "necessary-w004")

    def test_fit_rejects_evaluation_and_unresolved_labels(self):
        for row in ({"split": "evaluation", "fit_eligible": True},
                    {"split": "development", "fit_eligible": False}):
            with self.assertRaises(ValueError):
                fit([row], .1)


if __name__ == "__main__":
    unittest.main()
