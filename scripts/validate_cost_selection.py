#!/usr/bin/env python3
"""Fit on development data; validate faster features and the native tie hook.

Does not run the budget sweep or inspect held-out performance. Performance
diagnostics are feature-acquisition costs, not evidence of query improvement.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.budget import check_result
from pln_cost.cost_features import FEATURE_NAMES
from pln_cost.cost_model import feature_rows, predict, fit, structure_group
from pln_cost.cost_selection import build_selection_library, bootstrap_text, config_expression, selection_fixture, audit_trace
from pln_cost.expansion import reference_fixture, marked
from pln_cost.first_answer import quiet_library
from pln_cost.proof import key
from pln_cost.qualification import expression
from pln_cost.runtime import Runtime
from pln_cost.sexpr import read_case, read_one
from pln_cost.validation import clean_completion


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2) + "\n")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(path.read_text())


def error_metrics(model, rows):
    errors, apes = [], []
    for r in rows:
        estimate = predict(model, [r["features"][f] for f in FEATURE_NAMES])
        if estimate is None:
            raise ValueError("Invalid development prediction")
        errors.append(abs(math.log(estimate/r["median_cpu_ns"])))
        apes.append(abs(estimate/r["median_cpu_ns"]-1))
    return {"rows": len(rows), "mean_absolute_log_error": statistics.mean(errors),
            "median_absolute_percentage_error": statistics.median(apes)*100}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum():
        ap.error("Simple run ID required")
    output = PROJECT / "results/selection/step-04" / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    protocol = load(PROJECT / "configs/cost-model-protocol.json")
    save(output / "protocol.json", protocol)
    report = {"passed": False, "native_runs": [], "feature_checks": [], "policy_checks": [],
              "held_out_performance_evaluated": False, "budget_comparison_run": False}

    def run(path, library, bootstrap):
        result = runtime.run(path, preload_pln=True, library_path=library, bootstrap_path=bootstrap)
        for stream in ("stdout", "stderr"):
            path.with_suffix(f".{stream}.txt").write_text(result[stream])
        report["native_runs"].append({"fixture": str(path.relative_to(output)),
            "fixture_sha256": sha(path.read_bytes()), "stdout_sha256": sha(result["stdout"].encode()),
            **{k: v for k, v in result.items() if k not in ("stdout", "stderr")}})
        save(output / "report.json", report)
        if not clean_completion(result):
            raise RuntimeError(f"Native execution failed: {path}; logs retained")
        return result["stdout"]

    try:
        data = PROJECT / protocol["data_batch"]
        previous = load(data / "report.json")
        if not previous["passed"] or previous["evaluation_cpu_labels_collected"]:
            raise ValueError("Expected passed development-only data batch")
        all_rows = [json.loads(x) for x in (data / "development-costs.jsonl").read_text().splitlines()]
        if any(r["split"] != "development" for r in all_rows):
            raise ValueError("Evaluation rows in training file")
        rows = [r for r in all_rows if r["fit_eligible"]]
        groups = sorted({structure_group(r) for r in rows})
        cross_validation = []
        print(f"Training: {len(rows)} qualified rows; {len(groups)} structural folds", flush=True)
        start = time.process_time_ns()
        for alpha in protocol["ridge_alphas"]:
            folds = []
            for group in groups:
                train = [r for r in rows if structure_group(r) != group]
                valid = [r for r in rows if structure_group(r) == group]
                model = fit(train, alpha)
                folds.append({"group": group, **error_metrics(model, valid)})
            cross_validation.append({"alpha": alpha, "folds": folds,
                "score": statistics.mean(f["mean_absolute_log_error"] for f in folds)})
        chosen = min(cross_validation, key=lambda x: x["score"])
        model = fit(rows, chosen["alpha"])
        report["fit_cpu_ns"] = time.process_time_ns()-start
        model.update(training_rows=len(rows), excluded_unresolved_rows=len(all_rows)-len(rows),
            development_structures=groups, data_sha256=sha((data / "development-costs.jsonl").read_bytes()),
            split_manifest_sha256=sha((data / "split-manifest.json").read_bytes()))
        save(output / "cross-validation.json", cross_validation)
        save(output / "model.json", model)  # Frozen before adapter/policy diagnostics.
        report["model_sha256"] = sha((output / "model.json").read_bytes())
        report["model_selection"] = chosen
        report["in_sample_error_not_generalization"] = error_metrics(model, rows)
        import numpy as np
        report["numpy_version"] = np.__version__
        runtime = Runtime(PROJECT, PROJECT / "configs/runtime.json")
        report["provenance_before"] = runtime.verify()
        source = (runtime.pln / "lib_pln.metta").read_text()
        source_hash = sha(source.encode())
        if source_hash != previous["native_library_sha256"]:
            raise ValueError("Native library changed since profiling")
        report["source_sha256"] = {str(p.relative_to(PROJECT)): sha(p.read_bytes())
            for folder in ("src", "scripts", "configs", "tests") for p in sorted((PROJECT / folder).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}
        bootstrap = output / "selection-bootstrap.pl"
        bootstrap.write_text(bootstrap_text((PROJECT / "src/pln_cost/budget_clock.pl").read_text(),
                                            (PROJECT / "src/pln_cost/cost_selector.pl").read_text()))
        libraries = {}
        for audit in (False, True):
            text, patch = build_selection_library(source, audit)
            path = output / ("lib_pln.audit.metta" if audit else "lib_pln.quiet.metta")
            path.write_text(text)
            path.with_suffix(".diff").write_text(patch)
            libraries[audit] = path
        native_quiet = output / "lib_pln.native-quiet.metta"
        native_quiet.write_text(quiet_library(source)[0])
        (output / "PLN-LICENSE.txt").write_bytes((runtime.pln / "LICENSE").read_bytes())
        report["adapter_hashes"] = {p.name: sha(p.read_bytes()) for p in
            [bootstrap, libraries[False], libraries[True], output / "model.json"]}
        # Shared Python and native feature values must match every saved row,
        # including unresolved labels. No timing labels are discarded here.
        for i, entry in enumerate(previous["states"]):
            name = entry["name"]
            print(f"Feature parity/timing {i+1}/{len(previous['states'])}: {name}", flush=True)
            state = load(data / name / "state.json")
            saved = load(data / name / "features.json")
            expected = [[c, [fs[f] for f in FEATURE_NAMES]] for c, fs in zip(saved["candidates"], saved["features"], strict=True)]
            fast = [[c, x] for c, x in feature_rows(state)]
            if fast != expected:
                raise ValueError("Shared Python features changed semantics")
            samples = []
            for _ in range(protocol["feature_timing_repetitions"]):
                t0 = time.process_time_ns()
                actual = feature_rows(state)
                samples.append(time.process_time_ns()-t0)
                if [[c, x] for c, x in actual] != expected:
                    raise ValueError("Feature nondeterminism")
            folder = output / "features" / name
            folder.mkdir(parents=True)
            path = folder / "probe.metta"
            text = "(= (Probe.Tasks) " + expression(state["tasks"]) + ")\n"
            text += "(= (Probe.Beliefs) " + expression(state["beliefs"]) + ")\n"
            text += "!(py-call (time.process_time_ns))\n"
            for rep in range(protocol["feature_timing_repetitions"]):
                text += f"!(println! (FEATURE_PROBE {rep} (cost_feature_probe (Probe.Tasks) (Probe.Beliefs))))\n"
            path.write_text(text)
            log = run(path, native_quiet, bootstrap)
            probes = [read_one(l)[1:] for l in log.splitlines() if l.startswith("(FEATURE_PROBE ")]
            if len(probes) != protocol["feature_timing_repetitions"] or [x[0] for x in probes] != list(range(len(probes))):
                raise ValueError("Missing feature probes")
            if any(x[1][1] != expected or type(x[1][0]) is not int or x[1][0] <= 0 for x in probes):
                raise ValueError("Native features differ from Python/reference")
            native_times = [x[1][0] for x in probes]
            result = {"state": name, "candidates": len(expected), "shared_python_cpu_ns": samples,
                "native_cpu_ns": native_times, "shared_python_median_ns": statistics.median(samples),
                "native_median_ns": statistics.median(native_times),
                "previous_python_median_ns": entry["feature_batch_cpu_median_ns"],
                "previous_median_expansion_ns": entry["feature_batch_cpu_median_ns"]/entry["feature_batch_over_median_expansion"]}
            save(folder / "result.json", result)
            report["feature_checks"].append(result)

        config = load(PROJECT / "configs/qualification-kb.json")
        manifest = load(data / "split-manifest.json")
        for entry in manifest["development"]:
            case_path = PROJECT / entry["fixture"]
            if sha(case_path.read_bytes()) != entry["fixture_sha256"]:
                raise ValueError("Development case changed")
            case = read_case(case_path.read_text())
            saved_path = PROJECT / entry["states_path"]
            original = [json.loads(l) for l in saved_path.read_text().splitlines()] if entry["states_format"] == "jsonl" else load(saved_path)
            for mode in ("N", "O", "C"):
                print(f"Adapter validation: {entry['name']} {mode}", flush=True)
                folder = output / "policies" / entry["name"] / mode
                folder.mkdir(parents=True)
                text = selection_fixture(case, config, protocol["validation_budget_ns"], model, mode)
                path = folder / "audit.metta"
                path.write_text(text)
                log = run(path, libraries[True], bootstrap)
                states, selected, cert, checked = audit_trace(log, case, config, model, mode, source_hash, entry["fixture_sha256"])
                audit_check, _, _ = check_result(log, protocol["validation_budget_ns"], states, log, case,
                    source_hash, entry["fixture_sha256"], config["success"], audit=True)
                if not audit_check["verified_success"]:
                    raise ValueError("Validation trajectory did not reach a verified answer within cap")
                if mode in ("N", "O") and [s["state"] for s in states] != [s["state"] for s in original[:len(states)]]:
                    raise ValueError("N/O changed native logical trajectory")
                save(folder / "states.json", states)
                save(folder / "certificate.json", cert)
                save(folder / "proof-replay.json", checked)
                transitions = 0
                if mode == "C":
                    ref = folder / "native-transitions.metta"
                    ref.write_text("".join(reference_fixture(s["state"], c).replace("COST_REFERENCE", f"TRANSITION_{i}")
                        for i, (s, c) in enumerate(zip(states[:-1], selected, strict=True))))
                    ref_log = run(ref, native_quiet, bootstrap)
                    outs = [read_one(l) for l in ref_log.splitlines() if l.startswith("(TRANSITION_")]
                    if len(outs) != len(selected):
                        raise ValueError("Missing native transition checks")
                    for i, form in enumerate(outs):
                        if form != [f"TRANSITION_{i}", [states[i+1]["state"][k] for k in ("tasks", "beliefs")]]:
                            raise ValueError("Cost policy changed native expansion semantics")
                    transitions = len(outs)
                quiet_path = folder / "quiet.metta"
                quiet_path.write_text(text)
                quiet_log = run(quiet_path, libraries[False], bootstrap)
                quiet_check, _, _ = check_result(quiet_log, protocol["validation_budget_ns"], states, log, case,
                    source_hash, entry["fixture_sha256"], config["success"])
                stats = marked(quiet_log, "COST_STATS")[0]
                if len(stats) != 6 or stats[0] != quiet_check["completed_expansions"] or not 0 <= stats[2] <= stats[3] <= quiet_check["engine_cpu_ns"]:
                    raise ValueError("Invalid charged selection telemetry")
                if not quiet_check["verified_success"] or quiet_check["completed_expansions"] != len(selected):
                    raise ValueError("Quiet/audit trajectory mismatch")
                report["policy_checks"].append({"case": entry["name"], "mode": mode,
                    "expansions": len(selected), "proof_verified": True, "native_transition_checks": transitions,
                    "quiet_validation_cpu_ns_not_comparison": quiet_check["engine_cpu_ns"], "selector_stats": stats})
        # Native edge checks through the same bridge; no paper/result claim.
        edge_dir = output / "edges"
        edge_dir.mkdir()
        state = load(data / previous["states"][0]["name"] / "state.json")
        edge_results = []
        for label, edge_model, tasks, mode in (
            ("equal-estimates", {**model, "weights": [0.]*10}, state["tasks"], "C"),
            ("invalid-estimate-fallback", {**model, "intercept": 10000.}, state["tasks"], "C"),
            ("singleton", model, [state["tasks"][0]], "C"),
            ("unequal-confidence", model, deepcopy(state["tasks"]), "C")):
            if label == "unequal-confidence":
                tasks[-1][1][1][2] = .91
            path = edge_dir / f"{label}.metta"
            call = ["cost_select", tasks, state["beliefs"]]
            path.write_text("!" + config_expression(edge_model, mode) + "\n!(py-call (time.process_time_ns))\n"
                "!(cost_reset_test)\n!(println! (EDGE " + expression(call) + "))\n!(println! (COST_STATS (cost_stats)))\n")
            # Register an explicit reset bridge for standalone selector tests.
            edge_boot = edge_dir / "bootstrap.pl"
            if not edge_boot.exists():
                edge_boot.write_text(bootstrap.read_text() + "\ncost_reset_test(true) :- cost_reset.\n:- register_fun(cost_reset_test).\n")
            edge_log = run(path, native_quiet, edge_boot)
            expected = max(tasks, key=lambda r: r[1][1][2])
            if marked(edge_log, "EDGE") != [expected]:
                raise ValueError(f"Edge selection failed: {label}")
            stats = marked(edge_log, "COST_STATS")[0]
            if label == "invalid-estimate-fallback" and stats[4] != 1:
                raise ValueError("Invalid predictions did not trigger fallback")
            if label in ("singleton", "unequal-confidence") and (stats[1] != 0 or stats[5] != 1):
                raise ValueError("Singleton unnecessarily predicted")
            edge_results.append({"test": label, "passed": True})
        base_case = read_case((PROJECT / manifest["development"][0]["fixture"]).read_text())
        for mode in ("N", "O", "C"):
            path = edge_dir / f"zero-{mode}.metta"
            path.write_text(selection_fixture(base_case, config, 0, model, mode))
            log = run(path, libraries[False], bootstrap)
            value = marked(log, "BUDGET_RESULT")[0]
            if value[0] != "deadline" or value[1] != 0 or marked(log, "COST_STATS")[0][0] != 0:
                raise ValueError("Zero budget performed selection")
            edge_results.append({"test": f"zero-budget-{mode}", "passed": True})
        absent = deepcopy(base_case)
        absent["query"] = ["NoSuchGoal", "unit0"]
        path = edge_dir / "absent.metta"
        path.write_text(selection_fixture(absent, config, protocol["validation_budget_ns"], model, "C"))
        log = run(path, libraries[False], bootstrap)
        value = marked(log, "BUDGET_RESULT")[0]
        if value[0] != "exhausted" or value[5] != []:
            raise ValueError("Absent query incorrectly accepted")
        edge_results.append({"test": "absent-goal", "passed": True})
        report["edge_checks"] = edge_results
        report["provenance_after"] = runtime.verify()
        report["passed"] = report["provenance_before"] == report["provenance_after"]
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    save(output / "report.json", report)
    print(json.dumps({"passed": report["passed"], "error": report.get("error"),
        "feature_states": len(report["feature_checks"]), "policy_cases": len(report["policy_checks"]),
        "report": str(output / "report.json")}, indent=2), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
