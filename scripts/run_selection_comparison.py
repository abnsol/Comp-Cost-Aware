#!/usr/bin/env python3
"""Frozen, serial N/O/C comparison; retain deadlines, errors and raw logs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.budget import check_result
from pln_cost.comparison import schedule, summarize
from pln_cost.cost_selection import selection_fixture, audit_trace
from pln_cost.expansion import reference_fixture, marked
from pln_cost.runtime import Runtime
from pln_cost.sexpr import read_case, read_one
from pln_cost.validation import clean_completion


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum():
        ap.error("Simple run ID required")
    out = PROJECT / "results/selection/step-05" / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    protocol = load(PROJECT / "configs/selection-comparison.json")
    save(out / "protocol.json", protocol)
    report = dict(passed=False, completed=False, completed_runs=0, audits=[], errors=[])
    runs = []

    def execute(path, library):
        result = runtime.run(path, preload_pln=True, library_path=library,
                             bootstrap_path=out / "selection-bootstrap.pl")
        for stream in ("stdout", "stderr"):
            path.with_suffix(f".{stream}.txt").write_text(result[stream])
        save(path.with_suffix(".execution.json"), {
            **{k: v for k, v in result.items() if k not in ("stdout", "stderr")},
            "fixture_sha256": sha(path),
            "stdout_sha256": sha(path.with_suffix(".stdout.txt")),
            "stderr_sha256": sha(path.with_suffix(".stderr.txt"))})
        if not clean_completion(result):
            raise RuntimeError(f"Invalid native execution: {path.relative_to(out)}")
        return result["stdout"]

    try:
        prior = PROJECT / protocol["validation_batch"]
        data = PROJECT / protocol["data_batch"]
        validation = load(prior / "report.json")
        collected = load(data / "report.json")
        if not validation["passed"] or not collected["passed"]:
            raise ValueError("Previous qualification did not pass")
        for name, digest in validation["source_sha256"].items():
            if sha(PROJECT / name) != digest:
                raise ValueError(f"Frozen source changed: {name}")
        for name, digest in validation["adapter_hashes"].items():
            if sha(prior / name) != digest:
                raise ValueError(f"Frozen adapter changed: {name}")
        for name in (*validation["adapter_hashes"], "lib_pln.native-quiet.metta", "PLN-LICENSE.txt"):
            shutil.copyfile(prior / name, out / name)
        model = load(out / "model.json")
        if (sha(data / "development-costs.jsonl") != model["data_sha256"] or
                sha(data / "split-manifest.json") != model["split_manifest_sha256"] or
                sha(out / "model.json") != validation["model_sha256"]):
            raise ValueError("Training data, split or model changed")
        shutil.copyfile(data / "split-manifest.json", out / "split-manifest.json")
        runtime = Runtime(PROJECT, PROJECT / "configs/runtime.json")
        report["provenance_before"] = runtime.verify()
        source_hash = sha(runtime.pln / "lib_pln.metta")
        if source_hash != collected["native_library_sha256"]:
            raise ValueError("Native source changed")
        config = load(PROJECT / "configs/qualification-kb.json")
        manifest = load(out / "split-manifest.json")
        entries = manifest["development"] + manifest["evaluation"]
        jobs = schedule(entries, protocol)
        save(out / "schedule.json", jobs)  # Frozen before evaluation audits/timings.
        report["planned_runs"] = len(jobs)
        report["source_sha256"] = {str(p.relative_to(PROJECT)): sha(p)
            for directory in ("src", "scripts", "configs", "tests")
            for p in sorted((PROJECT / directory).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}
        report["frozen_inputs"] = {name: sha(out / name) for name in
            (*validation["adapter_hashes"], "lib_pln.native-quiet.metta", "split-manifest.json", "schedule.json", "protocol.json")}
        cases, audits = {}, {}
        for entry in entries:
            name = entry["name"]
            fixture = PROJECT / entry["fixture"]
            if sha(fixture) != entry["fixture_sha256"]:
                raise ValueError(f"Changed case: {name}")
            case = read_case(fixture.read_text())
            cases[name] = (case, entry)
            native_states = None
            for mode in protocol["policies"]:
                folder = out / "audits" / name / mode
                folder.mkdir(parents=True)
                if entry["split"] == "development":
                    old = prior / "policies" / name / mode
                    for file in ("states.json", "audit.stdout.txt", "certificate.json", "proof-replay.json"):
                        shutil.copyfile(old / file, folder / file)
                    log = (folder / "audit.stdout.txt").read_text()
                    states, selected, cert, replay = audit_trace(log, case, config, model, mode, source_hash, entry["fixture_sha256"])
                    if states != load(folder / "states.json"):
                        raise ValueError("Saved development audit changed")
                    transitions = "validated in Step 4"
                else:
                    print(f"Held-out correctness audit: {name} {mode}", flush=True)
                    path = folder / "audit.metta"
                    path.write_text(selection_fixture(case, config, protocol["audit_budget_ns"], model, mode))
                    log = execute(path, out / "lib_pln.audit.metta")
                    states, selected, cert, replay = audit_trace(log, case, config, model, mode, source_hash, entry["fixture_sha256"])
                    checked, _, _ = check_result(log, protocol["audit_budget_ns"], states, log, case,
                        source_hash, entry["fixture_sha256"], config["success"], audit=True)
                    if checked["status"] not in ("success", "exhausted"):
                        raise ValueError("Audit budget failed to cover full logical trajectory")
                    save(folder / "states.json", states)
                    save(folder / "certificate.json", cert)
                    save(folder / "proof-replay.json", replay)
                    # Every held-out arm is checked against the unmodified native
                    # one-expansion loop, not just against the new policy wrapper.
                    ref = folder / "native-transitions.metta"
                    ref.write_text("".join(reference_fixture(s["state"], c).replace("COST_REFERENCE", f"TRANSITION_{i}")
                        for i, (s, c) in enumerate(zip(states[:-1], selected, strict=True))))
                    ref_log = execute(ref, out / "lib_pln.native-quiet.metta")
                    outs = [read_one(line) for line in ref_log.splitlines() if line.startswith("(TRANSITION_")]
                    expected = [[f"TRANSITION_{i}", [states[i+1]["state"][k] for k in ("tasks", "beliefs")]]
                                for i in range(len(selected))]
                    if outs != expected:
                        raise ValueError("Held-out expansion differs from native semantics")
                    transitions = len(outs)
                if mode == "N":
                    native_states = states
                if mode == "O" and [s["state"] for s in states] != [s["state"] for s in native_states]:
                    raise ValueError("Overhead control changed native sequence")
                audits[(name, mode)] = (states, log)
                report["audits"].append(dict(case=name, mode=mode, split=entry["split"],
                    expansions=len(selected), proof_verified=cert is not None, native_transition_checks=transitions,
                    states_sha256=sha(folder / "states.json"), trace_sha256=sha(folder / "audit.stdout.txt")))
        save(out / "report.json", report)
        print(f"Audits passed; starting {len(jobs)} serial measurements. No concurrent tests.", flush=True)
        (out / "runs").mkdir()
        for job in jobs:
            row = dict(job)
            case, entry = cases[job["case"]]
            states, trace = audits[(job["case"], job["mode"])]
            folder = out / "runs" / f"{job['id']:05d}"
            folder.mkdir()
            path = folder / "query.metta"
            path.write_text(selection_fixture(case, config, job["budget_ns"], model, job["mode"]))
            try:
                log = execute(path, out / "lib_pln.quiet.metta")
                metrics, cert, replay = check_result(log, job["budget_ns"], states, trace, case,
                    source_hash, entry["fixture_sha256"], config["success"])
                stats = marked(log, "COST_STATS")[0]
                if (len(stats) != 6 or any(type(x) is not int or x < 0 for x in stats) or
                        stats[0] != metrics["completed_expansions"] or
                        not 0 <= stats[2] <= stats[3] <= metrics["engine_cpu_ns"]):
                    raise ValueError("Invalid selection telemetry")
                row.update(result=metrics, selector_stats=stats)
                if cert is not None:
                    save(folder / "certificate.json", cert)
                    save(folder / "proof-replay.json", replay)
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
                report["errors"].append({"id": job["id"], "error": row["error"]})
            save(folder / "result.json", row)
            with (out / "runs.jsonl").open("a") as stream:
                stream.write(json.dumps(row) + "\n")
            runs.append(row)
            report["completed_runs"] = len(runs)
            if len(runs) % 25 == 0 or "error" in row:
                save(out / "report.json", report)
                print(f"Measured {len(runs)}/{len(jobs)}; invalid={len(report['errors'])}", flush=True)
            if len(report["errors"]) >= 3:
                raise RuntimeError("Three invalid executions: stopped without replacement or tuning")
        report["provenance_after"] = runtime.verify()
        for name, digest in report["source_sha256"].items():
            if sha(PROJECT / name) != digest:
                raise ValueError(f"Source changed during measurement: {name}")
        for name, digest in report["frozen_inputs"].items():
            if sha(out / name) != digest:
                raise ValueError(f"Frozen input changed during measurement: {name}")
        report["completed"] = True
        report["passed"] = not report["errors"] and report["provenance_before"] == report["provenance_after"]
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    save(out / "summary.json", summarize(runs))
    save(out / "report.json", report)
    print(json.dumps({k: report.get(k) for k in ("passed", "completed", "completed_runs", "error")}), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
