"""Reject false successes and changed execution order before native qualification."""
from pathlib import Path
import hashlib
import json
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.feasibility import observable_parity, parse_result
from pln_cost.qualification import kb_records
from pln_cost.proof import replay
from pln_cost.qualification import qualifies
from pln_cost.sexpr import read_case


class FeasibilityTests(unittest.TestCase):
    def setUp(self):
        self.case = {"query": ["CanOperate", "unit0"], "inputs": kb_records(16), "marginals": {}}

    def test_accept_case_evidence_beyond_old_diagnostic_ids(self):
        self.assertEqual(parse_result("(QUALIFICATION_RESULT ((stv 1.0 0.729) (2 35 36)))", self.case),
                         {"strength": 1.0, "confidence": .729, "evidence": [2, 35, 36]})

    def test_explicit_no_answer_is_not_a_malformed_or_missing_result(self):
        self.assertIsNone(parse_result("(QUALIFICATION_RESULT ())", self.case))
        for log in ("", "(QUALIFICATION_RESULT)", "(QUALIFICATION_RESULT ())\n(QUALIFICATION_RESULT ())"):
            with self.subTest(log=log), self.assertRaises(ValueError):
                parse_result(log, self.case)

    def test_malformed_truth_and_evidence_rejected(self):
        for payload in ("((stv nan .8) (1))", "((stv 1 1.1) (1))", "((stv 1 .8) ())",
                        "((stv 1 .8) (2 37))", "((stv 1 .8) (2 2))", "((stv 1 .8) (3 2))",
                        "((stv 1 .8) (2.0))", "(unresolved-query)"):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_result(f"(QUALIFICATION_RESULT {payload})", self.case)

    def test_parity_covers_selection_order_and_nontrace_output(self):
        native = "(SELECTED A)\n(SELECTED B)\n(QUALIFICATION_RESULT ())\n"
        traced = "(STEP2_BINARY p q r)\n(SELECTED A)\n(SELECTED B)\n(QUALIFICATION_RESULT ())\n"
        self.assertTrue(observable_parity(native, traced)["all_original_output_unchanged"])
        self.assertEqual(observable_parity(native, traced)["native_selected_records"], 2)
        for changed in (traced.replace("(SELECTED A)", "(SELECTED C)"),
                        traced.replace("(SELECTED A)\n(SELECTED B)", "(SELECTED B)\n(SELECTED A)"),
                        traced + "unexpected diagnostic\n"):
            self.assertFalse(observable_parity(native, changed)["all_original_output_unchanged"])


class RecordedNativeQualificationTests(unittest.TestCase):
    def test_saved_native_answers_and_certificates(self):
        # Real captured executions, distinct from the authored static witnesses.
        batch = PROJECT / "results/qualification/step-03/run001"
        report = json.loads((batch / "report.json").read_text())
        config = json.loads((batch / "config.json").read_text())
        self.assertEqual(len(report["cases"]), 9)
        for entry in report["cases"]:
            fixture = PROJECT / entry["case"]
            folder = batch / fixture.stem
            with self.subTest(case=fixture.stem):
                self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), entry["fixture_sha256"])
                case = read_case(fixture.read_text())
                cert = json.loads((folder / "certificate.json").read_text())
                self.assertEqual(cert["origin"], "captured_native_execution_with_print_only_tracing")
                checked = replay(cert, case, report["hashes"]["native_library"], entry["fixture_sha256"])
                self.assertTrue(qualifies(checked, config["success"]))
                native = (folder / "native.stdout.txt").read_text()
                traced = (folder / "traced.stdout.txt").read_text()
                for name, log in (("native", native), ("traced", traced)):
                    self.assertEqual(hashlib.sha256(log.encode()).hexdigest(), entry["runs"][name]["stdout_sha256"])
                self.assertEqual(parse_result(native, case), checked["answer"])
                self.assertEqual(parse_result(native, case), parse_result(traced, case))
                self.assertTrue(observable_parity(native, traced)["all_original_output_unchanged"])


if __name__ == "__main__":
    unittest.main()
