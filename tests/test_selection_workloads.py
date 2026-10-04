"""Adversarial checks on the restricted necessary-work argument."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.proof import replay
from pln_cost.qualification import QUERY, qualifies, render_case, static_witness
from pln_cost.selection_workloads import ORDERINGS, READY, necessary_records, validate_necessary_shape
from pln_cost.sexpr import read_case


class NecessaryWorkTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((PROJECT / "configs/qualification-kb.json").read_text())

    def case(self, width=4, ordering="canonical_ids"):
        return read_case(render_case(necessary_records(width, ordering), self.config["initial_correctness_limits"]))

    def test_all_development_proofs_and_orderings(self):
        for width in (4, 16):
            for ordering in ORDERINGS:
                case = self.case(width, ordering)
                validate_necessary_shape(case, width)
                cert = static_witness(case, [1, 2, 3], "s", "f")
                self.assertTrue(qualifies(replay(cert, case, "s", "f"), self.config["success"]))

    def test_shortcuts_and_marginals_invalidate_necessity_argument(self):
        for term in (QUERY, ["Implication", READY, QUERY]):
            case = self.case()
            case["inputs"].append(["Sentence", [term, ["stv", 1.0, .9]], [99]])
            with self.assertRaisesRegex(ValueError, "structural contract"):
                validate_necessary_shape(case, 4)
        case = self.case()
        case["marginals"]["anything"] = ["stv", 1.0, .9]
        with self.assertRaises(ValueError):
            validate_necessary_shape(case, 4)

    def test_duplicate_or_changed_evidence_rejected(self):
        case = self.case()
        altered = deepcopy(case)
        altered["inputs"][1][2] = [1]
        with self.assertRaises(ValueError):
            validate_necessary_shape(altered, 4)
        case["inputs"].append(deepcopy(case["inputs"][0]))
        with self.assertRaises(ValueError):
            validate_necessary_shape(case, 4)


if __name__ == "__main__":
    unittest.main()
