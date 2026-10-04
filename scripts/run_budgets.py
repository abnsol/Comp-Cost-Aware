#!/usr/bin/env python3
"""Validate the online stopping adapter, then run the fixed CPU-budget sweep."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import random
import statistics
import sys
import time

from run_paired import PROJECT, save, sha
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.budget import build_budget_library, fixture, check_result
from pln_cost.proof import key
from pln_cost.runtime import Runtime
from pln_cost.sexpr import read_case
from pln_cost.validation import clean_completion


def validation_matches(validation, report):
    if not validation["passed"] or validation.get("stage") != "validate":
        raise ValueError("Passed budget-adapter validation required")
    if validation["hashes"] != report["hashes"] or validation["provenance_after"] != report["provenance_before"]:
        raise ValueError("Budget validation contract changed")
    for path in ("src/pln_cost/budget.py", "src/pln_cost/runtime.py", "scripts/run_budgets.py"):
        if validation["project_source_sha256"][path] != report["project_source_sha256"][path]:
            raise ValueError(f"Validated execution code changed: {path}")


def summarize(runs):
    groups = {}
    for r in runs:
        groups.setdefault((r["name"], r["budget_ns"]), []).append(r["result"])
    return [{"name": name, "budget_ns": budget, "n": len(rows),
             "verified_successes": sum(r["verified_success"] for r in rows),
             "statuses": dict(Counter(r["status"] for r in rows)),
             "median_engine_cpu_ns": statistics.median(r["engine_cpu_ns"] for r in rows),
             "maximum_overshoot_ns": max(r["overshoot_ns"] for r in rows),
             "median_observer_window_fraction": statistics.median(r["observer_window_fraction"] for r in rows),
             "completed_expansions_range": [min(r["completed_expansions"] for r in rows), max(r["completed_expansions"] for r in rows)],
             "late_goal_states": sum(r["goal_in_final_state"] and not r["verified_success"] for r in rows)}
            for (name, budget), rows in sorted(groups.items())]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("validate", "measure"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--validation")
    args = parser.parse_args()
    for ident in (args.run_id, args.validation):
        if ident is not None and not ident.replace("-", "").replace("_", "").isalnum():
            parser.error("Simple IDs only")
    if args.stage == "measure" and not args.validation:
        parser.error("Measurement requires --validation")
    root = PROJECT / "results/qualification/step-08"
    output = root / args.stage / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    report = {"stage": args.stage, "passed": False, "runs": []}
    try:
        protocol_path = PROJECT / "configs/budget-protocol.json"
        protocol = json.loads(protocol_path.read_text())
        save(output / "protocol.json", protocol)
        previous = PROJECT / "results/qualification/step-04" / protocol["state_batch"]
        prior = json.loads((previous / "report.json").read_text())
        first_path = PROJECT / "results/qualification/step-07" / protocol["first_answer_batch"] / "report.json"
        first = json.loads(first_path.read_text())
        config = json.loads((previous / "config.json").read_text())
        save(output / "config.json", config)
        if not prior["passed"] or not first["passed"] or len(prior["cases"]) != 9:
            raise ValueError("Prior state/first-proof validation required")
        runtime = Runtime(PROJECT, PROJECT / "configs/runtime.json")
        report["provenance_before"] = runtime.verify()
        if report["provenance_before"] != prior["provenance_after"] or report["provenance_before"] != first["provenance_after"]:
            raise ValueError("Source/runtime changed")
        source = (runtime.pln / "lib_pln.metta").read_text()
        source_hash = sha(source.encode())
        if source_hash != prior["hashes"]["native_library"] or source_hash != first["hashes"]["native_library"]:
            raise ValueError("Native library changed")
        libraries = {}
        report["hashes"] = {"native": source_hash, "protocol": sha(protocol_path.read_bytes()),
                            "state_report": sha((previous / "report.json").read_bytes()),
                            "first_report": sha(first_path.read_bytes())}
        for audit in (False, True):
            text, patch = build_budget_library(source, audit)
            name = "audit" if audit else "quiet"
            path = output / f"lib_pln.budget-{name}.metta"
            path.write_text(text)
            path.with_suffix(".diff").write_text(patch)
            libraries[audit] = path
            report["hashes"][name] = sha(text.encode())
        bootstrap = output / "budget_clock.pl"
        bootstrap.write_bytes((PROJECT / "src/pln_cost/budget_clock.pl").read_bytes())
        report["hashes"]["adapter"] = sha(bootstrap.read_bytes())
        (output / "PLN-LICENSE.txt").write_text((runtime.pln / "LICENSE").read_text())
        report["project_source_sha256"] = {str(p.relative_to(PROJECT)): sha(p.read_bytes())
            for folder in ("src", "scripts", "configs", "tests") for p in sorted((PROJECT / folder).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}
        data = []
        for entry in prior["cases"]:
            path = PROJECT / entry["case"]
            name = path.stem
            saved, raw = previous / name / "snapshots.jsonl", previous / name / "capture.stdout.txt"
            if (sha(path.read_bytes()) != entry["fixture_sha256"] or sha(saved.read_bytes()) != entry["snapshots_sha256"]
                    or sha(raw.read_bytes()) != entry["runs"]["capture"]["stdout_sha256"]):
                raise ValueError("Input/state/trace changed")
            states = [json.loads(l) for l in saved.read_text().splitlines()]
            if any(s["sha256"] != key(s["state"]) for s in states):
                raise ValueError("Saved state identity changed")
            data.append(dict(name=name, entry=entry, case=read_case(path.read_text()), states=states, trace=raw.read_text()))

        def execute(label, item, budget, audit=False, absent=False):
            folder = output / label
            folder.mkdir(parents=True)
            case = deepcopy(item["case"])
            if absent:
                case["query"] = ["NoSuchGoal", "unit0"]
            path = folder / "trial.metta"
            path.write_text(fixture(case, config, budget))
            cpu0, wall0 = time.process_time_ns(), time.perf_counter_ns()
            run = runtime.run(path, preload_pln=True, library_path=libraries[audit], bootstrap_path=bootstrap)
            parent_cpu, wall = time.process_time_ns()-cpu0, time.perf_counter_ns()-wall0
            for stream in ("stdout", "stderr"):
                (folder / f"{stream}.txt").write_text(run[stream])
            meta = {k: v for k, v in run.items() if k not in ("stdout", "stderr")}
            meta.update(label=label, name=item["name"], budget_ns=budget, audit=audit, absent_query=absent,
                        parent_invocation_cpu_ns=parent_cpu, invocation_wall_ns=wall,
                        stdout_sha256=sha(run["stdout"].encode()), fixture_sha256=sha(path.read_bytes()))
            report["runs"].append(meta)
            save(output / "report.json", report)
            if not clean_completion(run):
                raise RuntimeError(f"{label}: native execution failed; logs retained")
            checked, certificate, replay = check_result(run["stdout"], budget, item["states"], item["trace"], case,
                source_hash, item["entry"]["fixture_sha256"], config["success"], audit)
            meta["result"] = checked
            if certificate:
                save(folder / "certificate.json", certificate)
                save(folder / "replay.json", replay)
            save(folder / "run.json", meta)
            save(output / "report.json", report)
            return checked

        if args.stage == "validate":
            first_by_name = {c["name"]: c for c in first["cases"]}
            for item in data:
                for audit in (True, False):
                    label = f"{item['name']}/{'audit' if audit else 'quiet'}"
                    print(f"Validating {label}", flush=True)
                    r = execute(label, item, protocol["validation_budget_ns"], audit)
                    if not r["verified_success"] or r["completed_expansions"] != first_by_name[item["name"]]["first_completed_expansions"]:
                        raise ValueError("Adapter failed to stop at native first valid answer")
            r = execute("zero-budget", data[0], 0)
            if r["status"] != "deadline" or r["completed_expansions"] != 0 or r["verified_success"]:
                raise ValueError("Zero-budget guard failed")
            r = execute("absent-query", data[0], protocol["validation_budget_ns"], absent=True)
            if r["status"] != "exhausted" or r["verified_success"] or r["goal_in_final_state"]:
                raise ValueError("Absent-query guard failed")
        else:
            vpath = root / "validate" / args.validation / "report.json"
            validation_matches(json.loads(vpath.read_text()), report)
            report["validation_sha256"] = sha(vpath.read_bytes())
            schedule = []
            for rep in range(protocol["repetitions"]):
                block = [dict(repetition=rep, case_index=i, name=d["name"], budget_ns=b)
                         for i, d in enumerate(data) for b in protocol["budgets_ns"]]
                random.Random(protocol["seed"]+rep).shuffle(block)
                schedule.extend(block)
            save(output / "schedule.json", schedule)
            for n, job in enumerate(schedule, 1):
                label = f"rep-{job['repetition']:02d}/{job['name']}/ns-{job['budget_ns']}"
                print(f"Measuring {n}/{len(schedule)} {label}", flush=True)
                execute(label, data[job["case_index"]], job["budget_ns"])
            report["summary"] = summarize(report["runs"])
        report["provenance_after"] = runtime.verify()
        report["passed"] = report["provenance_after"] == report["provenance_before"]
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    save(output / "report.json", report)
    print(json.dumps({"passed": report["passed"], "runs": len(report["runs"]), "error": report.get("error"),
                      "report": str(output / "report.json")}, indent=2), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
