#!/usr/bin/env python3
"""Capture native states and verify exact fresh-process continuation; no timing."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.runtime import Runtime
from pln_cost.sexpr import read_case
from pln_cost.states import (STATE_PREFIX, TRIM_PREFIX, capture_states, check_restoration,
                             checkpoints_to_restore, instrument_states, ready_pair, restore_fixture)
from pln_cost.validation import clean_completion


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--feasibility-batch", default="run001")
    args = parser.parse_args()
    for ident in (args.run_id, args.feasibility_batch):
        if not ident.replace("-", "").replace("_", "").isalnum():
            parser.error("Simple alphanumeric IDs with optional '-'/'_' required")
    output = PROJECT / "results/qualification/step-04" / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    report = {"purpose": "logical state restoration, not performance measurement", "cases": [],
              "passed": False, "cpu_costs_measured": False,
              "checkpoint_policy": "initial, after one, midpoint, penultimate, terminal; last Ready-pair checkpoint if distinct"}
    try:
        previous = PROJECT / "results/qualification/step-03" / args.feasibility_batch
        prior = json.loads((previous / "report.json").read_text())
        config = json.loads((previous / "config.json").read_text())
        if not prior["passed"] or len(prior["cases"]) != 9:
            raise ValueError("Expected the nine successful feasibility cases")
        limits = config["initial_correctness_limits"]
        save(output / "config.json", config)
        runtime = Runtime(PROJECT, PROJECT / "configs/runtime.json")
        report["provenance_before"] = runtime.verify()
        if runtime.config["timeout_seconds"] != limits["wall_safety_timeout_seconds"] or limits["stack_limit"] != "1g":
            raise ValueError("Runtime limits changed")
        source = (runtime.pln / "lib_pln.metta").read_text()
        source_hash = sha(source.encode())
        if source_hash != prior["hashes"]["native_library"] or report["provenance_before"] != prior["provenance_after"]:
            raise ValueError("Source/runtime differ from feasibility validation")
        library_text, patch = instrument_states(source)
        library = output / "lib_pln.states.metta"
        library.write_text(library_text)
        (output / "instrumentation.diff").write_text(patch)
        (output / "PLN-LICENSE.txt").write_text((runtime.pln / "LICENSE").read_text())
        report["hashes"] = {"native_library": source_hash, "state_library": sha(library_text.encode()),
                            "feasibility_report": sha((previous / "report.json").read_bytes())}
        report["project_source_sha256"] = {
            str(p.relative_to(PROJECT)): sha(p.read_bytes())
            for folder in ("src", "scripts", "configs", "tests")
            for p in sorted((PROJECT / folder).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}
        for entry in prior["cases"]:
            fixture = PROJECT / entry["case"]
            folder = output / fixture.stem
            folder.mkdir()
            result = {"case": entry["case"], "fixture_sha256": entry["fixture_sha256"],
                      "width": entry["width"], "ordering": entry["ordering"],
                      "runs": {}, "restorations": [], "passed": False}

            def execute(name, path):
                run = runtime.run(path, preload_pln=True, library_path=library)
                for stream in ("stdout", "stderr"):
                    (folder / f"{name}.{stream}.txt").write_text(run[stream])
                result["runs"][name] = {k: v for k, v in run.items() if k not in ("stdout", "stderr")}
                result["runs"][name]["stdout_sha256"] = sha(run["stdout"].encode())
                if not clean_completion(run):
                    raise RuntimeError(f"{name} failed or timed out; retained logs")
                return run["stdout"]

            try:
                if sha(fixture.read_bytes()) != entry["fixture_sha256"]:
                    raise ValueError("Fixture changed since feasibility run")
                baseline = (previous / fixture.stem / "traced.stdout.txt").read_text()
                if sha(baseline.encode()) != entry["runs"]["traced"]["stdout_sha256"]:
                    raise ValueError("Prior trace hash mismatch")
                print(f"Capturing {fixture.stem}", flush=True)
                log = execute("capture", fixture)
                filtered = [line for line in log.splitlines() if not line.startswith((STATE_PREFIX, TRIM_PREFIX))]
                if filtered != baseline.splitlines():
                    raise ValueError("State instrumentation changed previous proof/selection/output trace")
                result["prior_feasibility_trace_unchanged"] = True
                states, trims = capture_states(log, read_case(fixture.read_text()), limits)
                result["checkpoint_count"] = len(states)
                result["maximum_task_queue"] = max(len(s["state"]["tasks"]) for s in states)
                result["maximum_belief_queue"] = max(len(s["state"]["beliefs"]) for s in states)
                result["trim_events"] = trims
                result["ready_pair_checkpoints"] = [s["state"]["next_step"] - 1 for s in states if ready_pair(s["state"])]
                final = states[-1]["state"]
                result["final_task_queue_size"] = len(final["tasks"])
                result["termination"] = {"step_cap_reached": final["next_step"] > final["maxsteps"],
                                         "task_queue_empty": not final["tasks"]}
                snapshots = [{**s, "source_sha256": source_hash, "fixture_sha256": entry["fixture_sha256"],
                              "boundary": "loop_entry_after_previous_queue_updates",
                              "ready_pair": ready_pair(s["state"])} for s in states]
                saved = folder / "snapshots.jsonl"
                saved.write_text("".join(json.dumps(s, separators=(",", ":")) + "\n" for s in snapshots))
                result["snapshots_sha256"] = sha(saved.read_bytes())
                # Restore from the disk serialization, not the live parsed state.
                loaded = [json.loads(line) for line in saved.read_text().splitlines()]
                for index in checkpoints_to_restore(states):
                    name = f"restore-{index:03d}"
                    snapshot = loaded[index]
                    restore_path = folder / f"{name}.metta"
                    restore_path.write_text(restore_fixture(snapshot, source_hash=source_hash,
                        fixture_hash=entry["fixture_sha256"], expected_state_hash=states[index]["sha256"]))
                    print(f"  {fixture.stem}: restore after {index} expansions", flush=True)
                    resumed_log = execute(name, restore_path)
                    checks = check_restoration(resumed_log, log, states[index], final)
                    result["restorations"].append({"completed_expansions": index,
                        "state_sha256": states[index]["sha256"], "fixture_sha256": sha(restore_path.read_bytes()), **checks})
                result["passed"] = True
            except Exception as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"
            save(folder / "report.json", result)
            report["cases"].append(result)
            save(output / "report.json", report)
            print(f"{fixture.stem}: passed={result['passed']} {result.get('error', '')}", flush=True)
        report["provenance_after"] = runtime.verify()
        report["external_sources_unchanged"] = report["provenance_before"] == report["provenance_after"]
        report["passed"] = report["external_sources_unchanged"] and all(c["passed"] for c in report["cases"])
        report["restorations_checked"] = sum(len(c["restorations"]) for c in report["cases"])
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    save(output / "report.json", report)
    print(json.dumps({"passed": report["passed"], "restorations_checked": report.get("restorations_checked"),
                      "error": report.get("error"), "report": str(output / "report.json")}, indent=2), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
