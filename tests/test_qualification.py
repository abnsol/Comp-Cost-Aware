"""Structural and adversarial proof checks; no engine execution or timing."""
import copy
import json
from pathlib import Path
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.proof import SOURCE_COMMIT, key, replay
from pln_cost.qualification import ORDERINGS, kb_records, qualifies, render_case, static_witness, validate_config
from pln_cost.sexpr import read_case, read_forms
from test_proof import rekey


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((PROJECT / "configs/qualification-kb.json").read_text())

    def case(self, width=1, ordering="canonical_ids"):
        return read_case(render_case(kb_records(width, ordering), self.config["initial_correctness_limits"]))

    def test_specified_sizes_truth_and_ids(self):
        for width, count in ((1, 6), (4, 12), (16, 36)):
            records = kb_records(width)
            self.assertEqual(len(records), count)
            self.assertEqual([r[2] for r in records], [[i] for i in range(1, count + 1)])
            self.assertTrue(all(r[1][1] == ["stv", 1.0, 0.9] for r in records))
            self.assertNotIn(["CanOperate", "unit0"], [r[1][0] for r in records])
            self.assertEqual(sum(r[1][0][0] == "Implication" for r in records), 2 + 2*width)

    def test_order_changes_only_order(self):
        for width in (1, 4, 16):
            canonical = kb_records(width)
            swapped = kb_records(width, "swap_ready_facts")
            self.assertEqual(swapped, [canonical[1], canonical[0]] + canonical[2:])
            shuffled = kb_records(width, "seeded_shuffle")
            self.assertEqual(shuffled, kb_records(width, "seeded_shuffle"))
            self.assertEqual({key(r) for r in shuffled}, {key(r) for r in canonical})
            self.assertNotEqual(shuffled, canonical)

    def test_generated_call_has_specified_query_and_caps_without_marginals(self):
        text = render_case(kb_records(1), self.config["initial_correctness_limits"])
        self.assertEqual(read_case(text)["marginals"], {})
        self.assertEqual(read_forms(text)[-1], ["println!", ["QUALIFICATION_RESULT",
            ["PLN.Query", ["kb"], ["CanOperate", "unit0"], 100, 4097, 4097]]])

    def test_all_72_authored_route_proofs(self):
        count = 0
        for width in (1, 4, 16):
            for ordering in ORDERINGS:
                case = self.case(width, ordering)
                routes = [[1, 3, 4]] + [[2, 2*i+3, 2*i+4] for i in range(1, width+1)]
                for ids in routes:
                    cert = static_witness(case, ids, "test-source", "test-fixture")
                    result = replay(cert, case, "test-source", "test-fixture")
                    self.assertEqual(result["nodes"], 5)
                    self.assertEqual(result["answer"], {"strength": 1.0, "confidence": 0.729, "evidence": ids})
                    self.assertEqual(sum(s["rule"].startswith("ModusPonens") for s in result["steps"]), 2)
                    self.assertTrue(qualifies(result, self.config["success"]))
                    count += 1
        self.assertEqual(count, 72)

    def test_invalid_generation_parameters_rejected(self):
        for width in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                kb_records(width)
        with self.assertRaises(ValueError):
            kb_records(1, "unknown")
        validate_config(self.config)
        self.config["initial_confidence"] = 0.8
        with self.assertRaisesRegex(ValueError, "initial_confidence"):
            validate_config(self.config)

    def test_wrong_truth_and_parent_order_rejected(self):
        case = self.case()
        original = static_witness(case, [1, 3, 4], "s", "f")
        for mutation in ("truth", "parents", "evidence", "conclusion"):
            cert = copy.deepcopy(original)
            node = cert["nodes"][cert["root"]]
            if mutation == "truth":
                node["record"][1][1][2] = 0.9
            elif mutation == "parents":
                node["parents"].reverse()
            elif mutation == "evidence":
                node["record"][2] = [1, 4]
            else:
                node["record"][1][0] = ["CanOperate", "unit1"]
            rekey(cert, cert["root"])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                replay(cert, case, "s", "f")

    def test_shared_b_evidence_prevents_revision_but_a_b_allowed(self):
        case = self.case(4)
        a = static_witness(case, [1, 3, 4], "s", "f")
        b1 = static_witness(case, [2, 5, 6], "s", "f")
        b2 = static_witness(case, [2, 7, 8], "s", "f")
        for left, right, allowed in ((a, b1, True), (b1, b2, False)):
            cert = copy.deepcopy(left)
            cert["nodes"].update(copy.deepcopy(right["nodes"]))
            stamp = sorted(set(left["nodes"][left["root"]]["record"][2] + right["nodes"][right["root"]]["record"][2]))
            # Equal-confidence revision: c = 2c/(1+c).
            record = ["Sentence", [case["query"], ["stv", 1.0, 1.458 / 1.729]], stamp]
            cert["nodes"][key(record)] = {"kind": "binary", "record": record,
                                         "parents": [left["root"], right["root"]]}
            cert["root"] = key(record)
            if allowed:
                self.assertTrue(qualifies(replay(cert, case, "s", "f"), self.config["success"]))
            else:
                with self.assertRaisesRegex(ValueError, "Overlapping evidence"):
                    replay(cert, case, "s", "f")

    def test_proof_validity_does_not_bypass_confidence_threshold(self):
        self.assertFalse(qualifies({"valid": True, "answer": {"strength": 1, "confidence": .72}}, self.config["success"]))


class ModusPonensFormulaTests(unittest.TestCase):
    def certificate(self, antecedent="P", conclusion="Q"):
        # Non-unit strength exercises the .02 fallback, not just multiplication.
        p = ["Sentence", [antecedent, ["stv", .5, .8]], [1]]
        rule = ["Sentence", [["Implication", antecedent, conclusion], ["stv", .6, .9]], [2]]
        out = ["Sentence", [conclusion, ["stv", .31, .216]], [1, 2]]
        case = {"inputs": [p, rule], "query": conclusion, "marginals": {}}
        cert = {"source_commit": SOURCE_COMMIT, "source_sha256": "s", "fixture_sha256": "f",
                "query": conclusion, "marginals": {}, "root": key(out), "nodes": {
                    key(p): {"kind": "input", "record": p},
                    key(rule): {"kind": "input", "record": rule},
                    key(out): {"kind": "binary", "record": out, "parents": [key(p), key(rule)]}}}
        return case, cert

    def test_nonunit_strength_and_confidence(self):
        case, cert = self.certificate()
        self.assertEqual(replay(cert, case, "s", "f")["answer"],
                         {"strength": .31, "confidence": .216, "evidence": [1, 2]})
        cert["nodes"][cert["root"]]["record"][1][1][1] = .3
        rekey(cert, cert["root"])
        with self.assertRaisesRegex(ValueError, "Incorrect truth"):
            replay(cert, case, "s", "f")

    def test_json_variables_cannot_bypass_ground_parser(self):
        case, cert = self.certificate(["P", "$x"], "Q")
        with self.assertRaisesRegex(ValueError, "Variables"):
            replay(cert, case, "s", "f")


if __name__ == "__main__":
    unittest.main()
