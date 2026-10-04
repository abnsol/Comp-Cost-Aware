"""Replay the recorded native proof and reject meaningful certificate tampering.

Record IDs are recomputed after mutations so truth/evidence rejection is tested
independently of the superficial content-hash check. No engine run is needed.
"""
import copy
import json
from pathlib import Path
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.proof import key, replay
from pln_cost.sexpr import read_case, read_one
from pln_cost.tracing import instrument


def rekey(cert, old):
    node = cert["nodes"].pop(old)
    new = key(node["record"])
    cert["nodes"][new] = node
    for other in cert["nodes"].values():
        if "parents" in other:
            other["parents"] = [new if p == old else p for p in other["parents"]]
    if cert["root"] == old:
        cert["root"] = new


class ReplayTests(unittest.TestCase):
    def setUp(self):
        # Frozen evidence from the first real trace, not a Python-produced proof.
        self.cert = json.loads((PROJECT / "results/step-02/run001/certificate.json").read_text())
        self.case = read_case((PROJECT / "cases/machine_failure.metta").read_text())
        report = json.loads((PROJECT / "results/step-02/run001/report.json").read_text())
        self.hashes = report["hashes"]

    def check(self, cert=None, case=None):
        return replay(self.cert if cert is None else cert, self.case if case is None else case,
                      self.hashes["native_library"], self.hashes["fixture"])

    def test_native_answer_has_two_deductions_and_one_revision(self):
        result = self.check()
        self.assertEqual(result["nodes"], 7)
        self.assertEqual(sum(s["rule"].startswith("Deduction") for s in result["steps"]), 2)
        self.assertEqual(sum(s["rule"].startswith("Revision") for s in result["steps"]), 1)
        self.assertAlmostEqual(result["answer"]["strength"], 0.6879979916209911, places=12)

    def test_wrong_truth_even_with_recomputed_identity(self):
        self.cert["nodes"][self.cert["root"]]["record"][1][1][1] = 0.7
        rekey(self.cert, self.cert["root"])
        with self.assertRaisesRegex(ValueError, "Incorrect truth"):
            self.check()

    def test_wrong_evidence_union(self):
        self.cert["nodes"][self.cert["root"]]["record"][2] = [1, 2, 3]
        rekey(self.cert, self.cert["root"])
        with self.assertRaisesRegex(ValueError, "incorrect union"):
            self.check()

    def test_forged_input_even_with_recomputed_identity(self):
        ident = next(k for k, n in self.cert["nodes"].items() if n["kind"] == "input")
        self.cert["nodes"][ident]["record"][1][1][1] = 0.81
        rekey(self.cert, ident)
        with self.assertRaisesRegex(ValueError, "Unlicensed input"):
            self.check()

    def test_overlapping_evidence_even_if_inputs_are_authorized(self):
        # Independently exercise the guard with an authorized overlapping input set.
        ident = next(k for k, n in self.cert["nodes"].items()
                     if n["kind"] == "input" and n["record"][2] == [2])
        self.cert["nodes"][ident]["record"][2] = [1]
        next(r for r in self.case["inputs"] if r[2] == [2])[2] = [1]
        rekey(self.cert, ident)
        with self.assertRaisesRegex(ValueError, "Overlapping evidence"):
            self.check()

    def test_wrong_provenance(self):
        for field in ("source_commit", "source_sha256", "fixture_sha256"):
            cert = copy.deepcopy(self.cert)
            cert[field] = "wrong"
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "provenance"):
                self.check(cert)

    def test_wrong_query_or_marginal(self):
        for field, replacement in (("query", ["Inheritance", "Hot", "Fails"]), ("marginals", {})):
            cert = copy.deepcopy(self.cert)
            cert[field] = replacement
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "inputs mismatch"):
                self.check(cert)

    def test_missing_marginal_fails_closed(self):
        del self.case["marginals"]["Hot"]
        del self.cert["marginals"]["Hot"]
        with self.assertRaisesRegex(ValueError, "Missing ground marginal"):
            self.check()

    def test_unsupported_rule_fails_closed(self):
        self.cert["nodes"][self.cert["root"]]["kind"] = "unary"
        with self.assertRaisesRegex(ValueError, "Unsupported rule"):
            self.check()

    def test_wrong_deduction_premises(self):
        node = next(n for n in self.cert["nodes"].values()
                    if n["kind"] == "binary" and n["record"][2] == [1, 2])
        node["parents"].reverse()
        with self.assertRaisesRegex(ValueError, "Unsupported rule"):
            self.check()

    def test_cycle_is_rejected(self):
        self.cert["nodes"][self.cert["root"]]["parents"][0] = self.cert["root"]
        with self.assertRaisesRegex(ValueError, "Cyclic"):
            self.check()


class TraceContractTests(unittest.TestCase):
    def test_instrumentation_rejects_unknown_source(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            instrument("not the expected PLN library")

    def test_parser_rejects_truncated_or_out_of_scope_forms(self):
        for text in ("(A", "A B", "(A))", "(A $x)", '(A "text")'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                read_one(text)

    def test_case_rejects_unrecognized_executable_form(self):
        text = (PROJECT / "cases/machine_failure.metta").read_text()
        with self.assertRaisesRegex(ValueError, "Unsupported fixture form"):
            read_case(text + "\n!(unknown-operation)\n")


if __name__ == "__main__":
    unittest.main()
