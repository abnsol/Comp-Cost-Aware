"""Schedule, statistical units and clock/output rejection for paired profiling."""
import json
import hashlib
from pathlib import Path
import sys
import unittest
from copy import deepcopy

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.paired import analyze, balanced_orders, parse, sign_p, summarize_process
sys.path.insert(0, str(PROJECT / "scripts"))
from run_paired import check_calibration
from pln_cost.thin import thin_fixture


class PairedTests(unittest.TestCase):
    def test_thin_calibration_contract_rejects_changes(self):
        path = PROJECT / "results/qualification/step-06/repair/calibrate/cal002/report.json"
        calibration = json.loads(path.read_text())
        check_calibration(calibration, deepcopy(calibration), True)
        for field in ("adapter_sha256", "helper_sha256", "protocol_sha256", "conditions_sha256", "provenance_after"):
            changed = deepcopy(calibration)
            changed[field] = "changed"
            with self.subTest(field=field), self.assertRaises(ValueError):
                check_calibration(calibration, changed, True)
        for path in ("src/pln_cost/thin.py", "src/pln_cost/runtime.py"):
            changed = deepcopy(calibration)
            changed["project_source_sha256"][path] = "changed"
            with self.assertRaises(ValueError):
                check_calibration(calibration, changed, True)
        for field, value in (("passed", False), ("accepted_batch_size", 8), ("overhead_gate_passed", False)):
            changed = deepcopy(calibration)
            changed[field] = value
            with self.assertRaises(ValueError):
                check_calibration(changed, calibration, True)

    def test_main_thin_schedule_matches_frozen_pair_orders(self):
        protocol = json.loads((PROJECT / "configs/paired-protocol.json").read_text())
        conditions = json.loads((PROJECT / "results/qualification/step-06/repair/calibrate/cal002/conditions.json").read_text())
        for block in range(protocol["blocks"]):
            for i, condition in enumerate(conditions):
                seed = protocol["seed"] + 10000 * (block+1) + i
                _, schedule = thin_fixture("", condition, protocol, seed, 10, 10)
                self.assertEqual([s[2] for s in schedule if s[0] == "Measured"],
                                 [r for pair in balanced_orders(10, seed) for r in pair])
                self.assertEqual(len(schedule), 70)

    def test_balanced_deterministic_order(self):
        orders = balanced_orders(10, 9)
        self.assertEqual(orders, balanced_orders(10, 9))
        self.assertEqual(orders.count(["A", "B"]), 5)
        self.assertEqual(orders.count(["B", "A"]), 5)
        with self.assertRaises(ValueError):
            balanced_orders(9, 9)

    def test_missing_invalid_or_false_samples_rejected(self):
        schedule = [["Measured", 0, "A", 1]]
        base = "(PAIRED_CLOCK 3.12.3 1e-9 true)\n(PAIRED_SAMPLE Measured 0 A 1 10 100 true)"
        self.assertEqual(parse(base, schedule)["samples"][0]["batch_cpu_ns"], 100)
        for bad in (base.replace("100 true", "100 false"), base.replace("10 100", "10 -1"),
                    base.replace("Measured 0 A", "Measured 0 B"), base+"\n"+base, ""):
            with self.assertRaises(ValueError):
                parse(bad, schedule)

    def test_pairing_and_per_expansion_units(self):
        rows = [{"phase": "Measured", "pair": 0, "route": "B", "k": 8, "prepare_cpu_ns": 10, "batch_cpu_ns": 1600},
                {"phase": "Measured", "pair": 0, "route": "A", "k": 8, "prepare_cpu_ns": 10, "batch_cpu_ns": 800},
                {"phase": "Measured", "pair": 1, "route": "A", "k": 8, "prepare_cpu_ns": 10, "batch_cpu_ns": 800},
                {"phase": "Measured", "pair": 1, "route": "B", "k": 8, "prepare_cpu_ns": 10, "batch_cpu_ns": 1600},
                {"phase": "Empty", "pair": 0, "route": "A", "k": 8, "prepare_cpu_ns": 10, "batch_cpu_ns": 80}]
        summary = summarize_process({"samples": rows})
        self.assertEqual(summary["median_difference_ns"], 100)
        self.assertEqual(summary["median_ratio"], 2)
        self.assertEqual(summary["pairs"][0]["first"], "B")
        self.assertEqual(summary["empty_p95_fraction"], .1)

    def test_sign_test_uses_blocks_and_handles_ties(self):
        self.assertEqual(sign_p([1]*12), 2/4096)
        self.assertEqual(sign_p([1]*11+[-1]), 26/4096)
        self.assertEqual(sign_p([0]*12), 1)

    def test_practical_gap_and_instrumentation_gate(self):
        protocol = json.loads((PROJECT / "configs/paired-protocol.json").read_text())
        block = {"median_ratio": 2, "median_difference_ns": 100, "empty_p95_fraction": .01,
                 "median_cpu_ns": {"A": 100, "B": 200},
                 "pairs": [{"first": "A", "ratio": 2}, {"first": "B", "ratio": 2}]}
        self.assertEqual(analyze([block]*12, protocol, 10, 1)["verdict"], "B_reproducibly_costlier")
        self.assertEqual(analyze([block]*12, protocol, 200, 1)["verdict"], "inconclusive")
        block["empty_p95_fraction"] = .2
        self.assertEqual(analyze([block]*12, protocol, 10, 1)["verdict"], "instrumentation_adequacy_unresolved")
        with self.assertRaises(ValueError):
            analyze([block]*11, protocol, 10, 1)


class SavedCalibrationTests(unittest.TestCase):
    def test_main_artifacts_reproduce_analysis_without_dropping_blocks(self):
        root = PROJECT / "results/qualification/step-06/measure/run001"
        report = json.loads((root / "report.json").read_text())
        protocol = json.loads((root / "protocol.json").read_text())
        schedule = json.loads((root / "schedule.json").read_text())
        self.assertTrue(report["passed"])
        self.assertEqual(report["harness"], "thin")
        self.assertEqual(len(report["runs"]), 156)
        self.assertEqual(len(schedule), 156)
        self.assertEqual(report["measured_pairs"], 1560)
        calibration = PROJECT / "results/qualification/step-06/repair/calibrate/cal002/report.json"
        self.assertEqual(hashlib.sha256(calibration.read_bytes()).hexdigest(), report["calibration_sha256"])
        for filename, field in (("thin_clock.pl", "adapter_sha256"), ("expand.metta", "helper_sha256")):
            self.assertEqual(hashlib.sha256((root / filename).read_bytes()).hexdigest(), report[field])
        blocks = {name: [] for name in report["analysis"]}
        self.assertEqual(len(blocks), 13)
        for run, item in zip(report["runs"], schedule):
            self.assertEqual(run["label"], f"block-{item['block']:02d}/{item['name']}")
            folder = root / run["label"]
            raw = (folder / "stdout.txt").read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), run["stdout_sha256"])
            self.assertEqual(hashlib.sha256((folder / "trial.metta").read_bytes()).hexdigest(), run["fixture_sha256"])
            local_schedule = json.loads((folder / "schedule.json").read_text())
            self.assertEqual([s[2] for s in local_schedule if s[0] == "Measured"],
                             [r for pair in item["orders"] for r in pair])
            parsed = parse(raw.decode(), local_schedule)
            self.assertEqual(len(parsed["samples"]), 70)
            summary = summarize_process(parsed)
            self.assertEqual(summary, json.loads((folder / "summary.json").read_text()))
            blocks[item["name"]].append(summary)
        for i, (name, summaries) in enumerate(blocks.items()):
            self.assertEqual(len(summaries), 12)
            self.assertEqual(analyze(summaries, protocol, report["absolute_floor_ns"], protocol["seed"]+i),
                             report["analysis"][name])

    def test_failed_overhead_gate_is_retained_with_complete_samples(self):
        root = PROJECT / "results/qualification/step-06/calibrate/cal001"
        report = json.loads((root / "report.json").read_text())
        protocol = json.loads((root / "protocol.json").read_text())
        self.assertFalse(report["passed"])
        self.assertNotIn("accepted_batch_size", report)
        self.assertEqual([a["batch_size"] for a in report["attempts"]], [1, 8, 32])
        self.assertEqual(len(report["runs"]), 9)
        for attempt in report["attempts"]:
            self.assertFalse(attempt["adequate"])
            self.assertTrue(any(s["empty_p95_fraction"] > protocol["maximum_empty_p95_fraction"]
                                for s in attempt["states"]))
        for run in report["runs"]:
            folder = root / run["label"]
            with self.subTest(run=run["label"]):
                raw = (folder / "stdout.txt").read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), run["stdout_sha256"])
                schedule = json.loads((folder / "schedule.json").read_text())
                parsed = parse(raw.decode(), schedule)
                self.assertEqual(summarize_process(parsed), json.loads((folder / "summary.json").read_text()))
                self.assertEqual(sum(s["phase"] == "Measured" for s in parsed["samples"]), 60)


if __name__ == "__main__":
    unittest.main()
