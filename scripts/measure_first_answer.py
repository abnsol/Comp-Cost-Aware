#!/usr/bin/env python3
"""Certify first native goal checkpoints, validate prefixes, then measure CPU."""
import argparse
import json
from pathlib import Path
import random
import statistics
import sys
import time

from run_paired import PROJECT, save, sha
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.first_answer import first_verified, quiet_library, prefix_fixture, validate_prefix, parse_timing
from pln_cost.proof import key
from pln_cost.runtime import Runtime
from pln_cost.sexpr import read_case, read_one
from pln_cost.states import instrument_states
from pln_cost.validation import clean_completion


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum():
        parser.error("Simple IDs only")
    output = PROJECT / "results/qualification/step-07" / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    report = {"passed": False, "cases": [], "runs": [], "scope": "offline-certified first-availability prefix CPU; no online stopping or CPU-budget experiment"}
    try:
        previous = PROJECT / "results/qualification/step-04/run001"
        prior = json.loads((previous / "report.json").read_text())
        config = json.loads((previous / "config.json").read_text())
        if not prior["passed"] or len(prior["cases"]) != 9:
            raise ValueError("Expected validated nine-case native state batch")
        save(output / "config.json", config)
        protocol = {"seed": 1950, "repetitions": 3, "endpoints": ["first", "full"],
                    "empty_probes": 30, "maximum_empty_p95_fraction": .1,
                    "inference_warmup": False, "audit_before_timings": True}
        save(output / "protocol.json", protocol)
        runtime = Runtime(PROJECT, PROJECT / "configs/runtime.json")
        report["provenance_before"] = runtime.verify()
        if report["provenance_before"] != prior["provenance_after"]:
            raise ValueError("Source/runtime changed")
        source = (runtime.pln / "lib_pln.metta").read_text()
        source_hash = sha(source.encode())
        if source_hash != prior["hashes"]["native_library"]:
            raise ValueError("Native library changed")
        audit_text, _ = instrument_states(source)
        if sha(audit_text.encode()) != prior["hashes"]["state_library"]:
            raise ValueError("State instrumentation changed")
        audit_library = output / "lib_pln.states.metta"
        audit_library.write_text(audit_text)
        quiet, patch = quiet_library(source)
        quiet_path = output / "lib_pln.quiet.metta"
        quiet_path.write_text(quiet)
        (output / "quiet.diff").write_text(patch)
        bootstrap = output / "first_clock.pl"
        bootstrap.write_bytes((PROJECT / "src/pln_cost/first_clock.pl").read_bytes())
        (output / "PLN-LICENSE.txt").write_text((runtime.pln / "LICENSE").read_text())
        report["hashes"] = {"native_library": source_hash, "state_library": sha(audit_text.encode()),
                            "quiet_library": sha(quiet.encode()), "adapter": sha(bootstrap.read_bytes()),
                            "state_report": sha((previous / "report.json").read_bytes())}
        report["project_source_sha256"] = {str(p.relative_to(PROJECT)): sha(p.read_bytes())
            for folder in ("src", "scripts", "configs", "tests") for p in sorted((PROJECT / folder).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}

        def execute(label, path, library, timed=False):
            cpu0, wall0 = time.process_time_ns(), time.perf_counter_ns()
            run = runtime.run(path, preload_pln=True, library_path=library,
                              bootstrap_path=bootstrap if timed else None)
            parent_cpu, wall = time.process_time_ns()-cpu0, time.perf_counter_ns()-wall0
            for stream in ("stdout", "stderr"):
                path.with_suffix(f".{stream}.txt").write_text(run[stream])
            metadata = {k: v for k, v in run.items() if k not in ("stdout", "stderr")}
            metadata.update(label=label, fixture=str(path.relative_to(output)), fixture_sha256=sha(path.read_bytes()),
                            stdout_sha256=sha(run["stdout"].encode()), parent_invocation_cpu_ns=parent_cpu,
                            invocation_wall_ns=wall)
            report["runs"].append(metadata)
            save(output / "report.json", report)
            if not clean_completion(run):
                raise RuntimeError(f"{label}: native execution failed; retained logs")
            return run["stdout"], metadata

        prepared = []
        for entry in prior["cases"]:
            fixture = PROJECT / entry["case"]
            name = fixture.stem
            if sha(fixture.read_bytes()) != entry["fixture_sha256"]:
                raise ValueError("Case changed")
            saved = previous / name / "snapshots.jsonl"
            raw = previous / name / "capture.stdout.txt"
            if sha(saved.read_bytes()) != entry["snapshots_sha256"] or sha(raw.read_bytes()) != entry["runs"]["capture"]["stdout_sha256"]:
                raise ValueError("Saved state/trace changed")
            states = [json.loads(l) for l in saved.read_text().splitlines()]
            if any(s["sha256"] != key(s["state"]) for s in states):
                raise ValueError("Snapshot identity changed")
            case, original = read_case(fixture.read_text()), raw.read_text()
            index, cert, checked = first_verified(states, original, case, source_hash, entry["fixture_sha256"], config["success"])
            if index < 1:
                raise ValueError("Goal unexpectedly present initially")
            folder = output / name
            folder.mkdir()
            save(folder / "certificate.json", cert)
            save(folder / "replay.json", checked)
            selected = [read_one(l)[1] for l in original.splitlines() if l.startswith("(SELECTED ")]
            result = {"name": name, "width": entry["width"], "ordering": entry["ordering"],
                      "fixture_sha256": entry["fixture_sha256"], "snapshot_sha256": entry["snapshots_sha256"],
                      "first_completed_expansions": index, "full_completed_expansions": len(states)-1,
                      "first_state_sha256": states[index]["sha256"], "proof": checked["answer"],
                      "selected_until_first": selected[:index], "answer_producing_selection": selected[index-1],
                      "ready_selection_steps": {route: [i+1 for i, r in enumerate(selected) if r[1][0] == ["Ready", "unit0", route]]
                                                for route in ("route_a", "route_b")},
                      "timings": {"first": [], "full": []}}
            report["cases"].append(result)
            path = folder / "audit-prefix.metta"
            path.write_text(prefix_fixture(case, states[index]["state"], index))
            print(f"Auditing {name}: first goal after {index} expansions", flush=True)
            log, _ = execute(f"{name}/audit", path, audit_library)
            result["prefix_parity"] = validate_prefix(log, original, states, index)
            prepared.append((case, states))
            save(output / "report.json", report)

        schedule = [{"case_index": i, "name": c["name"], "endpoint": endpoint, "repetition": rep}
                    for i, c in enumerate(report["cases"]) for endpoint in protocol["endpoints"]
                    for rep in range(protocol["repetitions"])]
        random.Random(protocol["seed"]).shuffle(schedule)
        save(output / "schedule.json", schedule)
        for item in schedule:
            i, endpoint, rep = item["case_index"], item["endpoint"], item["repetition"]
            case, states = prepared[i]
            result = report["cases"][i]
            index = result["first_completed_expansions"] if endpoint == "first" else len(states)-1
            state = states[index]["state"]
            cap = index if endpoint == "first" else config["initial_correctness_limits"]["maxsteps_argument"]
            path = output / item["name"] / f"{endpoint}-{rep:02d}.metta"
            path.write_text(prefix_fixture(case, state, cap, timed=True))
            print(f"Timing {item['name']}/{endpoint}-{rep:02d}", flush=True)
            log, metadata = execute(f"{item['name']}/{endpoint}-{rep:02d}", path, quiet_path, timed=True)
            timing = parse_timing(log, [state["tasks"], state["beliefs"]])
            metadata["timing"] = timing
            result["timings"][endpoint].append({"repetition": rep, **timing})
            save(output / "report.json", report)
        for result in report["cases"]:
            result["summary"] = {endpoint: {
                "median_cpu_ns": statistics.median(t["engine_reasoning_cpu_ns"] for t in ts),
                "range_cpu_ns": [min(t["engine_reasoning_cpu_ns"] for t in ts), max(t["engine_reasoning_cpu_ns"] for t in ts)],
                "maximum_empty_p95_fraction": max(t["empty_p95_fraction"] for t in ts),
                "overhead_adequate": all(t["overhead_adequate"] for t in ts)}
                for endpoint, ts in result["timings"].items()}
        report["provenance_after"] = runtime.verify()
        report["all_overhead_gates_passed"] = all(s["overhead_adequate"] for c in report["cases"] for s in c["summary"].values())
        report["passed"] = report["provenance_after"] == report["provenance_before"]
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    save(output / "report.json", report)
    print(json.dumps({"passed": report["passed"], "runs": len(report["runs"]), "error": report.get("error"),
                      "report": str(output / "report.json")}, indent=2), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
