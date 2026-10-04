"""Reject future-proof leakage, altered prefixes, and invalid CPU samples."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
import hashlib

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.first_answer import first_verified, parse_timing, quiet_library, validate_prefix
from pln_cost.proof import replay
from pln_cost.sexpr import read_case
from pln_cost.qualification import expression


class FirstAnswerTests(unittest.TestCase):
    def setUp(self):
        self.root = PROJECT / "results/qualification/step-04/run001"
        self.report = json.loads((self.root / "report.json").read_text())
        self.config = json.loads((self.root / "config.json").read_text())

    def test_earliest_proof_exists_in_committed_state_for_every_case(self):
        for entry in self.report["cases"]:
            fixture = PROJECT / entry["case"]
            folder = self.root / fixture.stem
            states = [json.loads(l) for l in (folder / "snapshots.jsonl").read_text().splitlines()]
            log = (folder / "capture.stdout.txt").read_text()
            case = read_case(fixture.read_text())
            i, cert, replay = first_verified(states, log, case, self.report["hashes"]["native_library"],
                                            entry["fixture_sha256"], self.config["success"])
            with self.subTest(case=fixture.stem):
                self.assertGreater(i, 0)
                self.assertTrue(replay["valid"])
                self.assertIn(cert["nodes"][cert["root"]]["record"], states[i]["state"]["beliefs"])
                self.assertFalse(any(r[1][0] == case["query"] for s in states[:i] for r in s["state"]["beliefs"]))

    def test_future_derivation_cannot_certify_an_earlier_checkpoint(self):
        entry = self.report["cases"][0]
        fixture = PROJECT / entry["case"]
        folder = self.root / fixture.stem
        states = [json.loads(l) for l in (folder / "snapshots.jsonl").read_text().splitlines()]
        log = (folder / "capture.stdout.txt").read_text()
        case = read_case(fixture.read_text())
        args = (case, self.report["hashes"]["native_library"], entry["fixture_sha256"], self.config["success"])
        i, _, _ = first_verified(states, log, *args)
        # Move the first goal's checkpoint BEFORE its proof events, leaving the
        # later proof in the complete log. It must not be used to license it.
        changed = deepcopy(states)
        changed[i]["trace_line"] = 1
        with self.assertRaises(ValueError):
            first_verified(changed, log, *args)

    def test_quiet_copy_changes_only_one_print(self):
        source = "before (println! (SELECTED (Sentence $x $Ev1))) after"
        quiet, patch = quiet_library(source)
        self.assertEqual(quiet, "before () after")
        self.assertIn("SELECTED", patch)
        with self.assertRaises(ValueError):
            quiet_library(source + source)

    def test_clock_output_and_overhead_guards(self):
        expected = [[], []]
        log = "\n".join(f"(FIRST_EMPTY {i} 100)" for i in range(30))
        log += f"\n(FIRST_CPU 2000)\n(FIRST_QUEUES {expression(expected)})"
        self.assertTrue(parse_timing(log, expected)["overhead_adequate"])
        self.assertFalse(parse_timing(log.replace("FIRST_CPU 2000", "FIRST_CPU 500"), expected)["overhead_adequate"])
        for bad in (log.replace("FIRST_CPU 2000", "FIRST_CPU -1"), log+"\n(FIRST_CPU 2000)",
                    log.replace("(FIRST_EMPTY 2 100)", ""), log.replace("FIRST_QUEUES (() ())", "FIRST_QUEUES ()")):
            with self.assertRaises(ValueError):
                parse_timing(bad, expected)


class SavedFirstAnswerTests(unittest.TestCase):
    def test_all_timed_queues_and_samples_match_raw_logs(self):
        root = PROJECT / "results/qualification/step-07/run001"
        report = json.loads((root / "report.json").read_text())
        self.assertTrue(report["passed"])
        self.assertEqual(len(report["runs"]), 63)
        schedule = json.loads((root / "schedule.json").read_text())
        self.assertEqual(len(schedule), 54)
        actual = [r for r in report["runs"] if "timing" in r]
        self.assertEqual([r["label"] for r in actual],
                         [f"{j['name']}/{j['endpoint']}-{j['repetition']:02d}" for j in schedule])
        prior = PROJECT / "results/qualification/step-04/run001"
        cases = {c["name"]: c for c in report["cases"]}
        for run in report["runs"]:
            fixture = root / run["fixture"]
            raw = fixture.with_suffix(".stdout.txt").read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), run["stdout_sha256"])
            self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), run["fixture_sha256"])
            if "timing" not in run:
                continue
            name, endpoint = run["label"].split("/")
            states = [json.loads(l) for l in (prior / name / "snapshots.jsonl").read_text().splitlines()]
            index = cases[name]["first_completed_expansions"] if endpoint.startswith("first-") else len(states)-1
            expected = [states[index]["state"][k] for k in ("tasks", "beliefs")]
            self.assertEqual(parse_timing(raw.decode(), expected), run["timing"])
        self.assertTrue(report["all_overhead_gates_passed"])

    def test_first_proofs_and_prefix_transitions_replay_and_reject_tampering(self):
        root = PROJECT / "results/qualification/step-07/run001"
        report = json.loads((root / "report.json").read_text())
        prior = PROJECT / "results/qualification/step-04/run001"
        for c in report["cases"]:
            name = c["name"]
            case = read_case((PROJECT / "cases/qualification/run001" / f"{name}.metta").read_text())
            cert = json.loads((root / name / "certificate.json").read_text())
            checked = replay(cert, case, report["hashes"]["native_library"], c["fixture_sha256"])
            self.assertEqual(checked, json.loads((root / name / "replay.json").read_text()))
            states = [json.loads(l) for l in (prior / name / "snapshots.jsonl").read_text().splitlines()]
            original = (prior / name / "capture.stdout.txt").read_text()
            log = (root / name / "audit-prefix.stdout.txt").read_text()
            index = c["first_completed_expansions"]
            self.assertEqual(validate_prefix(log, original, states, index), c["prefix_parity"])
            with self.assertRaises(ValueError):
                validate_prefix(log.replace("(SELECTED ", "(ALTERED ", 1), original, states, index)


if __name__ == "__main__":
    unittest.main()
