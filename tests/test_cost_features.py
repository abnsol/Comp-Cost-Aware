"""Feature-leakage and split-structure checks; no native timing."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pln_cost.cost_features import eligible_candidates, features
from pln_cost.proof import key
from pln_cost.selection_workloads import evaluation_records, necessary_records


class CostFeaturesTests(unittest.TestCase):
    def test_features_invariant_to_names_and_evidence_renumbering(self):
        records = necessary_records(4)
        state = {"tasks": records, "beliefs": records}
        expected = features(state, records[0])

        def rename(x):
            if isinstance(x, list):
                return [rename(v) for v in x]
            return {"unit0": "new_unit", "required": "renamed", "Ready": "OtherFact"}.get(x, x)

        renamed = rename(records)
        for record in renamed:
            record[2] = [record[2][0] + 100]
        self.assertEqual(expected, features({"tasks": renamed, "beliefs": renamed}, renamed[0]))

    def test_stamp_overlap_changes_match_count_and_no_mutation(self):
        records = necessary_records(4)
        state = {"tasks": records, "beliefs": records}
        before = deepcopy(state)
        self.assertEqual(features(state, records[0])["mp_matches"], 5)
        self.assertEqual(state, before)
        records[1][2] = [1]
        self.assertEqual(features(state, records[0])["mp_matches"], 4)

    def test_eligible_only_native_maximum_not_approximate_ties(self):
        records = necessary_records(1)
        records[0][1][1][2] = 0.90000000001
        self.assertEqual(eligible_candidates({"tasks": records}), [records[0]])
        self.assertEqual(eligible_candidates({"tasks": []}), [])

    def test_heldout_structures_are_distinct_and_target_ids_preserved(self):
        shared = evaluation_records(8, shared_sinks=True)
        modules = evaluation_records(4, modules=2)
        for records in (shared, modules):
            self.assertEqual([r[2] for r in records[:3]], [[1], [2], [3]])
            self.assertEqual(len({key(r) for r in records}), len(records))
            self.assertEqual(len({r[2][0] for r in records}), len(records))
        sinks = [r[1][0][2] for r in shared if r[1][0][0] == "Implication" and r[1][0][2][0] == "Side"]
        self.assertEqual(len(sinks), 16)
        self.assertEqual(len({str(x) for x in sinks}), 8)
        self.assertTrue(any(r[1][0] == ["Ready", "unit1", "required"] for r in modules))


if __name__ == "__main__":
    unittest.main()
