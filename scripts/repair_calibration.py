#!/usr/bin/env python3
"""Diagnose the old wrapper, validate the thin adapter, then recalibrate only."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import statistics
import sys

from run_paired import PROJECT, load_conditions, save, sha
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.expansion import build_expansion
from pln_cost.paired import parse, summarize_process
from pln_cost.proof import key
from pln_cost.runtime import Runtime
from pln_cost.sexpr import read_one
from pln_cost.thin import diagnostic_fixture, thin_fixture
from pln_cost.validation import clean_completion


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("diagnose", "validate", "calibrate"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--validation")
    args = parser.parse_args()
    for value in (args.run_id, args.validation):
        if value is not None and not value.replace("-", "").replace("_", "").isalnum():
            parser.error("Simple IDs only")
    if args.stage == "calibrate" and not args.validation:
        parser.error("Recalibration requires a passed thin-adapter validation ID")
    root = PROJECT / "results/qualification/step-06/repair"
    output = root / args.stage / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    report = {"stage": args.stage, "passed": False, "runs": [], "main_comparison_run": False}
    try:
        protocol = json.loads((PROJECT / "configs/paired-protocol.json").read_text())
        # Explicit harness revision: singleton timings; never accumulate outputs.
        # All thresholds/warm-up/calibration pair counts remain unchanged.
        revision = {**protocol, "harness_revision": "thin_compiled_singleton_v1", "batch_sizes_to_try": [1]}
        save(output / "protocol.json", revision)
        conditions, previous = load_conditions(protocol)
        save(output / "conditions.json", conditions)
        runtime = Runtime(PROJECT, PROJECT / "configs/runtime.json")
        report["provenance_before"] = runtime.verify()
        if report["provenance_before"] != previous["provenance_after"]:
            raise ValueError("Runtime/source changed")
        source = (runtime.pln / "lib_pln.metta").read_text()
        helper = build_expansion(source)
        bootstrap = PROJECT / "src/pln_cost/thin_clock.pl"
        if sha(helper.encode()) != previous["hashes"]["plain_helper"] or sha(source.encode()) != previous["hashes"]["native_library"]:
            raise ValueError("Expansion helper/native source changed")
        (output / "expand.metta").write_text(helper)
        (output / "thin_clock.pl").write_bytes(bootstrap.read_bytes())
        (output / "PLN-LICENSE.txt").write_text((runtime.pln / "LICENSE").read_text())
        report["helper_sha256"] = sha(helper.encode())
        report["adapter_sha256"] = sha(bootstrap.read_bytes())
        report["protocol_sha256"] = key(revision)
        report["conditions_sha256"] = key(conditions)
        report["project_source_sha256"] = {
            str(p.relative_to(PROJECT)): sha(p.read_bytes())
            for folder in ("src", "scripts", "configs", "tests")
            for p in sorted((PROJECT / folder).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}
        canonical = [next(c for c in conditions if c["name"] == f"n{n:03d}-canonical_ids-s000")
                     for n in protocol["calibration_widths"]]
        if args.stage == "calibrate":
            vpath = root / "validate" / args.validation / "report.json"
            validation = json.loads(vpath.read_text())
            if not validation["passed"] or any(validation[field] != report[field] for field in
                    ("helper_sha256", "adapter_sha256", "conditions_sha256", "protocol_sha256")):
                raise ValueError("Thin adapter has not passed matching validation")
            report["validation_sha256"] = sha(vpath.read_bytes())
        selected = conditions if args.stage == "validate" else canonical
        for i, condition in enumerate(selected):
            print(f"{args.stage}: {condition['name']}", flush=True)
            folder = output / condition["name"]
            folder.mkdir()
            seed = protocol["seed"] + i
            if args.stage == "diagnose":
                text, schedule = diagnostic_fixture(helper, condition, seed)
            else:
                pairs = 2 if args.stage == "validate" else protocol["calibration_pairs"]
                text, schedule = thin_fixture(helper, condition, protocol, seed, pairs, protocol["calibration_empty_batches"])
            fixture = folder / "trial.metta"
            fixture.write_text(text)
            save(folder / "schedule.json", schedule)
            run = runtime.run(fixture, preload_pln=True,
                bootstrap_path=(output / "thin_clock.pl") if args.stage != "diagnose" else None)
            for stream in ("stdout", "stderr"):
                (folder / f"{stream}.txt").write_text(run[stream])
            metadata = {k: v for k, v in run.items() if k not in ("stdout", "stderr")}
            metadata.update(name=condition["name"], fixture_sha256=sha(fixture.read_bytes()), stdout_sha256=sha(run["stdout"].encode()))
            report["runs"].append(metadata)
            if not clean_completion(run):
                raise RuntimeError(f"{condition['name']}: native run failed; logs retained")
            if args.stage == "diagnose":
                rows = [read_one(l)[1:] for l in run["stdout"].splitlines() if l.startswith("(HARNESS_DIAG ")]
                if [r[:4] for r in rows] != schedule or any(len(r) != 5 or type(r[4]) is not int or r[4] <= 0 for r in rows):
                    raise ValueError("Incomplete diagnostic schedule or invalid CPU sample")
                groups = {}
                for phase, _, mode, k, ns in rows:
                    if phase == "Measured":
                        groups.setdefault(f"{mode}-k{k}", []).append(ns)
                summary = {name: {"n": len(values), "median_ns": statistics.median(values)} for name, values in groups.items()}
                save(folder / "samples.json", rows)
            else:
                parsed = parse(run["stdout"], schedule)
                summary = summarize_process(parsed)
                probes = [read_one(l)[2] for l in run["stdout"].splitlines() if l.startswith("(THIN_CLOCK_PROBE ")]
                if len(probes) != 30 or any(type(n) is not int or n < 0 for n in probes):
                    raise ValueError("Missing thin-clock probes")
                save(folder / "samples.json", parsed)
                summary["clock_probe_ns"] = probes
            save(folder / "summary.json", summary)
            metadata["summary"] = summary
            save(output / "report.json", report)
        if args.stage == "validate":
            # Prove the adapter's guard rejects a wrong expected result.
            bad = deepcopy(conditions[0])
            bad["expected"]["A"] = []
            text, _ = thin_fixture(helper, bad, protocol, protocol["seed"], 2, 2)
            path = output / "invalid-expected.metta"
            path.write_text(text)
            run = runtime.run(path, preload_pln=True, bootstrap_path=output / "thin_clock.pl")
            for stream in ("stdout", "stderr"):
                (output / f"invalid-expected.{stream}.txt").write_text(run[stream])
            report["invalid_expected_rejected"] = (not clean_completion(run) and
                "thin_native_output_mismatch" in run["stderr"] + run["stdout"])
            if not report["invalid_expected_rejected"]:
                raise ValueError("Wrong-output guard did not fail closed")
        if args.stage == "calibrate":
            report["overhead_gate_passed"] = all(r["summary"]["empty_p95_fraction"] <= protocol["maximum_empty_p95_fraction"] for r in report["runs"])
            if not report["overhead_gate_passed"]:
                raise RuntimeError("Thin adapter still exceeds the unchanged overhead gate")
            report["accepted_batch_size"] = 1
            report["absolute_floor_ns"] = protocol["absolute_floor_empty_median_multiplier"] * max(r["summary"]["empty_median_ns"] for r in report["runs"])
        report["provenance_after"] = runtime.verify()
        report["passed"] = report["provenance_before"] == report["provenance_after"]
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    save(output / "report.json", report)
    print(json.dumps({"passed": report["passed"], "stage": args.stage, "error": report.get("error"),
                      "report": str(output / "report.json")}, indent=2), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
