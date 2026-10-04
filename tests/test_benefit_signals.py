from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pln_cost.benefit_signals import describe, SCOPE


def rec(term, stamp, confidence=.9):
    return ["Sentence", [term, ["stv", 1., confidence]], stamp]


class BenefitSignalTests(unittest.TestCase):
    def base(self):
        records = [rec("R", [1]), rec(["Implication", "R", "C"], [2]),
                   rec(["Implication", "C", "G"], [3]),
                   rec(["Implication", "R", "S"], [4])]
        return {"tasks": deepcopy(records), "beliefs": records}

    def run_signal(self, state, query="G", **kw):
        return describe(state, query, scope=kw.get("scope", SCOPE), marginals=kw.get("marginals", {}))

    def test_missing_present_and_duplicate_not_rejected(self):
        s = self.base(); original = deepcopy(s)
        rows = self.run_signal(s)["candidates"]
        self.assertEqual(s, original)
        self.assertEqual((rows[0]["missing_intermediate_pairs"], rows[0]["unconnected_pairs"]), (1, 1))
        self.assertTrue(rows[2]["dormant_query_rule"])
        s["beliefs"].append(rec("C", [1, 2], .81))
        rows = self.run_signal(s)["candidates"]
        self.assertEqual(rows[1]["represented_support_pairs"], 1)
        self.assertEqual(rows[2]["potential_goal_pairs"], 1)
        self.assertFalse(rows[2]["dormant_query_rule"])

    def test_overlap_blocks_pair_even_when_terms_match(self):
        s = self.base(); s["beliefs"][1][2] = [1]
        self.assertEqual(self.run_signal(s)["candidates"][0]["missing_intermediate_pairs"], 0)

    def test_implication_can_also_be_an_antecedent(self):
        s = self.base(); link = s["tasks"][1][1][0]
        s["beliefs"].append(rec(["Implication", link, "Other"], [5]))
        row = self.run_signal(s)["candidates"][1]
        self.assertEqual((row["missing_intermediate_pairs"], row["unconnected_pairs"]), (1, 1))

    def test_removed_task_stays_usable_in_beliefs_and_lower_priority_preserved(self):
        s = self.base(); s["tasks"].pop(2)
        c = rec("C", [1, 2], .81); s["tasks"].append(c); s["beliefs"].append(c)
        rows = self.run_signal(s)["candidates"]
        self.assertEqual(len(rows), len(s["tasks"]))
        self.assertEqual(rows[-1]["potential_goal_pairs"], 1)
        self.assertFalse(rows[-1]["max_confidence_eligible"])

    def test_cycles_and_same_term_new_evidence_are_not_pruned(self):
        s = self.base(); s["beliefs"].extend([rec(["Implication", "C", "R"], [5]), rec("C", [6])])
        r = self.run_signal(s)
        self.assertEqual(r["coverage"], SCOPE)
        self.assertEqual(r["candidates"][0]["represented_support_pairs"], 1)
        self.assertEqual(r["candidates"][0]["outputs"][0]["evidence_union"], [1, 2])

    def test_unknown_scope_marginals_variables_and_dynamic_rules(self):
        self.assertEqual(self.run_signal(self.base(), scope="full-PLN")["coverage"], "unknown")
        self.assertEqual(self.run_signal(self.base(), marginals={"R": .5})["coverage"], "unknown")
        self.assertEqual(self.run_signal(self.base(), query="$q")["coverage"], "unknown")
        s = self.base(); s["beliefs"].append(rec(["Implication", "R", ["Implication", "X", "G"]], [5]))
        self.assertEqual(self.run_signal(s)["coverage"], "unknown")

    def test_renaming_and_order_do_not_change_descriptors(self):
        s = self.base(); original = self.run_signal(s)["candidates"]
        def rename(t):
            if isinstance(t, list): return [rename(x) for x in t]
            return {"R": "z", "C": "a", "G": "w", "S": "n"}.get(t, t)
        changed = rename(s["beliefs"])
        other = self.run_signal({"beliefs": changed[::-1], "tasks": changed[::-1]}, query="w")["candidates"]
        for a, b in zip(original, other[::-1], strict=True):
            for k in ("mp_pairs", "potential_goal_pairs", "missing_intermediate_pairs", "unconnected_pairs", "dormant_query_rule"):
                self.assertEqual(a[k], b[k])


if __name__ == "__main__":
    unittest.main()
