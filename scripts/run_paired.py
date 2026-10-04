#!/usr/bin/env python3
"""Calibrate, then run the frozen same-state CPU comparison as separate stages."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.expansion import build_expansion, parse_trial
from pln_cost.paired import analyze, balanced_orders, fixture, parse, summarize_process
from pln_cost.proof import key
from pln_cost.runtime import Runtime
from pln_cost.thin import thin_fixture
from pln_cost.validation import clean_completion


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def check_calibration(calibration, report, thin):
    fields = ["protocol_sha256", "conditions_sha256", "helper_sha256"]
    if thin:
        fields += ["adapter_sha256", "provenance_after"]
        if calibration.get("accepted_batch_size") != 1 or not calibration.get("overhead_gate_passed"):
            raise ValueError("Thin calibration must pass singleton overhead gate")
        # The fixture generator and invocation layer must match recalibration.
        for path in ("src/pln_cost/thin.py", "src/pln_cost/runtime.py"):
            if calibration["project_source_sha256"][path] != report["project_source_sha256"][path]:
                raise ValueError(f"Calibrated execution code changed: {path}")
    if not calibration["passed"] or any(calibration[field] != report[field] for field in fields):
        raise ValueError("Calibration did not pass or its contract differs")


def load_conditions(protocol):
    previous = PROJECT / "results/qualification/step-05" / protocol["expansion_validation_batch"]
    validation = json.loads((previous / "report.json").read_text())
    if not validation["passed"]:
        raise ValueError("Expansion validation did not pass")
    states_dir = PROJECT / "results/qualification/step-04" / protocol["state_batch"]
    state_report = json.loads((states_dir / "report.json").read_text())
    if sha((states_dir / "report.json").read_bytes()) != validation["hashes"]["state_report"]:
        raise ValueError("State report changed")
    authorized = set()
    for entry in state_report["cases"]:
        path = states_dir / Path(entry["case"]).stem / "snapshots.jsonl"
        if sha(path.read_bytes()) != entry["snapshots_sha256"]:
            raise ValueError("Saved state file changed")
        for line in path.read_text().splitlines():
            s = json.loads(line)
            if s["sha256"] != key(s["state"]):
                raise ValueError("Saved state hash mismatch")
            authorized.add(s["sha256"])
    conditions = {}
    for trial in validation["trials"]:
        if trial["kind"] != "forced_ready_candidate":
            continue
        name = trial["name"].rsplit("-route_", 1)[0]
        folder = previous / trial["name"]
        data = json.loads((folder / "input.json").read_text())
        if key(data["state"]) != trial["state_sha256"] or trial["state_sha256"] not in authorized:
            raise ValueError("Unvalidated measurement state")
        raw = (folder / "timed.stdout.txt").read_bytes()
        if sha(raw) != trial["runs"]["timed"]["stdout_sha256"]:
            raise ValueError("Validated native-output hash mismatch")
        measured = parse_trial(raw.decode())
        route = {"route_a": "A", "route_b": "B"}[data["requested"][1][0][2]]
        if data["requested"] != measured["selected"]:
            raise ValueError("Validated candidate mismatch")
        condition = conditions.setdefault(name, {"name": name, "state": data["state"],
            "state_sha256": trial["state_sha256"], "candidates": {}, "expected": {}})
        if condition["state"] != data["state"] or route in condition["candidates"]:
            raise ValueError("Unmatched or duplicate alternatives")
        condition["candidates"][route] = data["requested"]
        condition["expected"][route] = measured["queues"] + [measured["derivations"]]
    if len(conditions) != protocol["number_of_state_comparisons"] or any(set(c["candidates"]) != {"A", "B"} for c in conditions.values()):
        raise ValueError("Incomplete state/alternative set")
    return list(conditions.values()), validation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("calibrate", "measure"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--calibration")
    parser.add_argument("--harness", choices=("legacy", "thin"), default="legacy")
    args = parser.parse_args()
    for ident in (args.run_id, args.calibration):
        if ident is not None and not ident.replace("-", "").replace("_", "").isalnum():
            parser.error("Simple alphanumeric IDs with optional '-'/'_' required")
    if args.stage == "measure" and not args.calibration:
        parser.error("Measurement requires a completed calibration ID")
    if args.harness == "thin" and args.stage != "measure":
        parser.error("Use repair_calibration.py for thin-adapter calibration")
    root = PROJECT / "results/qualification/step-06"
    output = root / args.stage / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    report = {"stage": args.stage, "passed": False, "runs": [], "scope": "local expansion CPU on fixed development states"}
    try:
        protocol = json.loads((PROJECT / "configs/paired-protocol.json").read_text())
        thin = args.harness == "thin"
        if thin:
            protocol = {**protocol, "harness_revision": "thin_compiled_singleton_v1", "batch_sizes_to_try": [1]}
            bootstrap = output / "thin_clock.pl"
            bootstrap.write_bytes((PROJECT / "src/pln_cost/thin_clock.pl").read_bytes())
            report["adapter_sha256"] = sha(bootstrap.read_bytes())
        report["harness"] = args.harness
        save(output / "protocol.json", protocol)
        conditions, validation = load_conditions(protocol)
        save(output / "conditions.json", conditions)
        runtime = Runtime(PROJECT, PROJECT / "configs/runtime.json")
        report["provenance_before"] = runtime.verify()
        if report["provenance_before"] != validation["provenance_after"]:
            raise ValueError("Runtime/source changed")
        source = (runtime.pln / "lib_pln.metta").read_text()
        helper = build_expansion(source)
        if sha(source.encode()) != validation["hashes"]["native_library"] or sha(helper.encode()) != validation["hashes"]["plain_helper"]:
            raise ValueError("Expansion helper changed since validation")
        (output / "expand.metta").write_text(helper)
        (output / "PLN-LICENSE.txt").write_text((runtime.pln / "LICENSE").read_text())
        report["protocol_sha256"] = key(protocol)
        report["conditions_sha256"] = key(conditions)
        report["helper_sha256"] = sha(helper.encode())
        report["project_source_sha256"] = {
            str(p.relative_to(PROJECT)): sha(p.read_bytes())
            for folder in ("src", "scripts", "configs", "tests")
            for p in sorted((PROJECT / folder).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}

        def execute(label, condition, k, orders, seed, empty_count):
            folder = output / label
            folder.mkdir(parents=True)
            local_protocol = dict(protocol, empty_count=empty_count)
            if thin:
                text, expected_schedule = thin_fixture(helper, condition, protocol, seed, len(orders), empty_count)
                actual_orders = [r[2] for r in expected_schedule if r[0] == "Measured"]
                if k != 1 or actual_orders != [r for pair in orders for r in pair]:
                    raise ValueError("Thin fixture differs from frozen main schedule")
            else:
                text, expected_schedule = fixture(helper, condition["state"], condition["candidates"], condition["expected"],
                                                   k, orders, local_protocol, seed)
            path = folder / "trial.metta"
            path.write_text(text)
            save(folder / "schedule.json", expected_schedule)
            run = runtime.run(path, preload_pln=True, bootstrap_path=bootstrap if thin else None)
            for stream in ("stdout", "stderr"):
                (folder / f"{stream}.txt").write_text(run[stream])
            metadata = {k: v for k, v in run.items() if k not in ("stdout", "stderr")}
            metadata.update(name=condition["name"], label=label, batch_size=k,
                            stdout_sha256=sha(run["stdout"].encode()), fixture_sha256=sha(path.read_bytes()))
            report["runs"].append(metadata)
            if not clean_completion(run):
                save(folder / "run.json", metadata)
                raise RuntimeError(f"{label}: native execution failed; retained output")
            parsed = parse(run["stdout"], expected_schedule)
            summary = summarize_process(parsed)
            save(folder / "samples.json", parsed)
            save(folder / "summary.json", summary)
            save(folder / "run.json", metadata)
            save(output / "report.json", report)
            return summary

        if args.stage == "calibrate":
            calibration = [next(c for c in conditions if c["name"] == f"n{width:03d}-canonical_ids-s000")
                           for width in protocol["calibration_widths"]]
            report["attempts"] = []
            for k in protocol["batch_sizes_to_try"]:
                summaries = []
                for i, condition in enumerate(calibration):
                    seed = protocol["seed"] + i
                    print(f"Calibrating K={k}: {condition['name']}", flush=True)
                    summaries.append(execute(f"k{k:03d}/{condition['name']}", condition, k,
                        balanced_orders(protocol["calibration_pairs"], seed), seed, protocol["calibration_empty_batches"]))
                adequate = all(s["empty_p95_fraction"] <= protocol["maximum_empty_p95_fraction"] for s in summaries)
                report["attempts"].append({"batch_size": k, "adequate": adequate, "states": summaries})
                if adequate:
                    report["accepted_batch_size"] = k
                    report["absolute_floor_ns"] = protocol["absolute_floor_empty_median_multiplier"] * max(s["empty_median_ns"] for s in summaries)
                    break
            if "accepted_batch_size" not in report:
                raise RuntimeError("No predeclared batch size passed the instrumentation calibration gate")
        else:
            calibration_root = root / "repair" if thin else root
            calibration_path = calibration_root / "calibrate" / args.calibration / "report.json"
            calibration = json.loads(calibration_path.read_text())
            check_calibration(calibration, dict(report, provenance_after=report["provenance_before"]), thin)
            report["calibration_sha256"] = sha(calibration_path.read_bytes())
            k = calibration["accepted_batch_size"]
            report["batch_size"] = k
            report["absolute_floor_ns"] = calibration["absolute_floor_ns"]
            schedule = []
            for block in range(protocol["blocks"]):
                indices = list(range(len(conditions)))
                random.Random(protocol["seed"] + block).shuffle(indices)
                for i in indices:
                    seed = protocol["seed"] + 10000 * (block+1) + i
                    schedule.append({"block": block, "condition": i, "name": conditions[i]["name"], "seed": seed,
                                     "orders": balanced_orders(protocol["pairs_per_block"], seed)})
            save(output / "schedule.json", schedule)  # Entire schedule fixed before first main run.
            by_state = {c["name"]: [] for c in conditions}
            for item in schedule:
                label = f"block-{item['block']:02d}/{item['name']}"
                print(f"Measuring {label}", flush=True)
                summary = execute(label, conditions[item["condition"]], k, item["orders"], item["seed"], protocol["empty_batches_per_block"])
                by_state[item["name"]].append(summary)
            report["analysis"] = {name: analyze(blocks, protocol, report["absolute_floor_ns"], protocol["seed"] + i)
                                  for i, (name, blocks) in enumerate(by_state.items())}
            report["measured_pairs"] = sum(len(b["pairs"]) for blocks in by_state.values() for b in blocks)
        report["provenance_after"] = runtime.verify()
        report["passed"] = report["provenance_after"] == report["provenance_before"]
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    save(output / "report.json", report)
    print(json.dumps({"passed": report["passed"], "stage": args.stage, "runs": len(report["runs"]),
        "accepted_batch_size": report.get("accepted_batch_size"), "error": report.get("error"),
        "report": str(output / "report.json")}, indent=2), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
