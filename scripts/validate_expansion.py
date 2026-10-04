#!/usr/bin/env python3
"""Validate one-expansion timing/counters; this is not a repeated cost experiment."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.expansion import (build_expansion, chosen_record, counters, marked, parse_trial,
                                reference_fixture, trial_fixture)
from pln_cost.proof import key
from pln_cost.runtime import Runtime
from pln_cost.states import ready_pair
from pln_cost.validation import clean_completion


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--state-batch", default="run001")
    args = parser.parse_args()
    for ident in (args.run_id, args.state_batch):
        if not ident.replace("-", "").replace("_", "").isalnum():
            parser.error("Simple alphanumeric IDs with optional '-'/'_' required")
    output = PROJECT / "results/qualification/step-05" / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    report = {"purpose": "instrumentation validation, not a cost-gap estimate", "passed": False,
              "trials": [], "repeated_paired_comparison_performed": False,
              "clock": "embedded Python time.process_time_ns: SWI process user+system CPU",
              "timing_excludes": ["startup/loading", "snapshot restore", "result printing", "offline counters/checks", "parent Python"],
              "timing_includes": ["boundary clock/bridge overhead", "native rules", "result collection", "queue deduplication and trimming"]}
    try:
        previous = PROJECT / "results/qualification/step-04" / args.state_batch
        prior = json.loads((previous / "report.json").read_text())
        if not prior["passed"]:
            raise ValueError("State validation did not pass")
        runtime = Runtime(PROJECT, PROJECT / "configs/runtime.json")
        report["provenance_before"] = runtime.verify()
        if report["provenance_before"] != prior["provenance_after"]:
            raise ValueError("Runtime/source changed since state validation")
        source = (runtime.pln / "lib_pln.metta").read_text()
        source_hash = sha(source.encode())
        if source_hash != prior["hashes"]["native_library"]:
            raise ValueError("Native library hash mismatch")
        plain, audit = build_expansion(source), build_expansion(source, audit=True)
        (output / "expand.metta").write_text(plain)
        (output / "expand-audit.metta").write_text(audit)
        (output / "PLN-LICENSE.txt").write_text((runtime.pln / "LICENSE").read_text())
        config = json.loads((previous / "config.json").read_text())
        if runtime.config["timeout_seconds"] != config["initial_correctness_limits"]["wall_safety_timeout_seconds"]:
            raise ValueError("Wall limit changed")
        save(output / "config.json", config)
        report["hashes"] = {"native_library": source_hash, "plain_helper": sha(plain.encode()),
                            "audit_helper": sha(audit.encode()), "state_report": sha((previous / "report.json").read_bytes())}
        report["project_source_sha256"] = {
            str(p.relative_to(PROJECT)): sha(p.read_bytes())
            for folder in ("src", "scripts", "configs", "tests")
            for p in sorted((PROJECT / folder).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}
        trials = []
        for entry in prior["cases"]:
            name = Path(entry["case"]).stem
            raw = (previous / name / "snapshots.jsonl").read_bytes()
            if sha(raw) != entry["snapshots_sha256"] or sha((PROJECT / entry["case"]).read_bytes()) != entry["fixture_sha256"]:
                raise ValueError("Saved state or original fixture changed")
            snapshots = [json.loads(line) for line in raw.splitlines()]
            for s in snapshots:
                if s["source_sha256"] != source_hash or s["fixture_sha256"] != entry["fixture_sha256"] or key(s["state"]) != s["sha256"]:
                    raise ValueError("Snapshot provenance/content mismatch")
            for index in entry["ready_pair_checkpoints"]:
                state = snapshots[index]["state"]
                pair = ready_pair(state)
                if pair is None:
                    raise ValueError("Recorded Ready-pair checkpoint is not eligible")
                for route, selected in pair["candidates"].items():
                    trials.append((f"{name}-s{index:03d}-{route}", state, selected, None, "forced_ready_candidate"))
            index = (len(snapshots) - 1) // 2
            trials.append((f"{name}-s{index:03d}-native", snapshots[index]["state"], "Native",
                           snapshots[index+1]["state"], "native_selection"))
        # A separate instrumentation test exercises queue-cap removal. It does
        # not replace or change the caps of any qualification workload.
        small = deepcopy(trials[0][1])
        small["task_limit"] = small["belief_limit"] = 2
        trials.append(("diagnostic-trim-cap2", small, "Native", None, "synthetic_cap_boundary_check"))
        report["planned_trials"] = len(trials)
        for name, state, requested, next_state, kind in trials:
            print(f"Validating {name}", flush=True)
            folder = output / name
            folder.mkdir()
            save(folder / "input.json", {"state": state, "state_sha256": key(state), "requested": requested, "kind": kind})
            result = {"name": name, "kind": kind, "state_sha256": key(state), "runs": {}, "passed": False}
            report["trials"].append(result)
            for mode, text in (("reference", reference_fixture(state, requested)),
                               ("timed", trial_fixture(state, requested, plain)),
                               ("audit", trial_fixture(state, requested, audit))):
                fixture = folder / f"{mode}.metta"
                fixture.write_text(text)
                run = runtime.run(fixture, preload_pln=True)
                for stream in ("stdout", "stderr"):
                    (folder / f"{mode}.{stream}.txt").write_text(run[stream])
                result["runs"][mode] = {k: v for k, v in run.items() if k not in ("stdout", "stderr")}
                result["runs"][mode]["stdout_sha256"] = sha(run["stdout"].encode())
                result["runs"][mode]["fixture_sha256"] = sha(fixture.read_bytes())
                if not clean_completion(run):
                    raise RuntimeError(f"{name}/{mode} failed; raw logs retained")
            reference_log = (folder / "reference.stdout.txt").read_text()
            timed_log = (folder / "timed.stdout.txt").read_text()
            audit_log = (folder / "audit.stdout.txt").read_text()
            timed, audited = parse_trial(timed_log), parse_trial(audit_log)
            chosen = chosen_record(state, requested)
            reference = marked(reference_log, "COST_REFERENCE")
            if reference != [timed["queues"]] or marked(reference_log, "SELECTED") != [chosen]:
                raise ValueError(f"{name}: extraction differs from unmodified native loop")
            for field in ("queues", "selected", "derivations"):
                if timed[field] != audited[field]:
                    raise ValueError(f"{name}: audit instrumentation changed {field}")
            if timed["selected"] != chosen:
                raise ValueError("Wrong pending candidate executed")
            if next_state is not None and timed["queues"] != [next_state["tasks"], next_state["beliefs"]]:
                raise ValueError("Natural next state differs from saved native continuation")
            result["counters"] = counters(state, chosen, audited, audit_log)
            result["timed"] = {k: v for k, v in timed.items() if k not in ("queues", "derivations")}
            result["audit_expansion_cpu_ns_including_logging"] = audited["expansion_cpu_ns"]
            result["checks"] = {"native_ordered_post_queues_identical": True, "audit_generated_results_identical": True,
                                "audit_selected_and_queues_identical": True, "counters_reconciled": True,
                                "saved_natural_next_state_identical": True if next_state is not None else None}
            result["passed"] = True
            save(folder / "report.json", result)
            save(output / "report.json", report)
        report["provenance_after"] = runtime.verify()
        report["external_sources_unchanged"] = report["provenance_before"] == report["provenance_after"]
        report["passed"] = report["external_sources_unchanged"] and all(t["passed"] for t in report["trials"])
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    save(output / "report.json", report)
    print(json.dumps({"passed": report["passed"], "trials": len(report["trials"]),
                      "error": report.get("error"), "report": str(output / "report.json")}, indent=2), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
