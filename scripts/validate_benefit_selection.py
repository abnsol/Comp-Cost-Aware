#!/usr/bin/env python3
"""Development-only correctness validation of usefulness/cost selection.

No fitting, fresh held-out evaluation, repeated timing or budget sweep.
"""
import argparse
from copy import deepcopy
from functools import partial
import hashlib
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.benefit_selection import (MODES, bootstrap, build_library, choose,
    configure, native_ranks, selection_fixture)
from pln_cost.benefit_signals import SCOPE
from pln_cost.budget import check_result
from pln_cost.cost_selection import audit_trace
from pln_cost.expansion import marked, reference_fixture
from pln_cost.first_answer import quiet_library
from pln_cost.proof import key
from pln_cost.qualification import QUERY, expression, kb_records
from pln_cost.runtime import Runtime
from pln_cost.selection_workloads import necessary_records
from pln_cost.sexpr import read_case, read_one
from pln_cost.validation import clean_completion


def load(p):
    return json.loads(p.read_text())


def save(p, obj):
    p.write_text(json.dumps(obj, indent=2) + "\n")


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum():
        ap.error("Simple run ID required")
    out = PROJECT / "results/benefit-selection" / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    report = dict(passed=False, performance_comparison=False, retrained=False,
                  held_out_evaluated=False, probes=[], policies=[], edges=[], native_runs=[])
    inputs = {}

    def remember(p):
        inputs[str(p.relative_to(PROJECT))] = digest(p)
        return p

    def run(path, library):
        result = runtime.run(path, preload_pln=True, library_path=library, bootstrap_path=boot)
        for stream in ("stdout", "stderr"):
            path.with_suffix(f".{stream}.txt").write_text(result[stream])
        report["native_runs"].append(dict(fixture=str(path.relative_to(out)),
            fixture_sha256=digest(path), stdout_sha256=hashlib.sha256(result["stdout"].encode()).hexdigest(),
            stderr_sha256=hashlib.sha256(result["stderr"].encode()).hexdigest(),
            **{k: v for k, v in result.items() if k not in ("stdout", "stderr")}))
        save(out / "report.json", report)
        if not clean_completion(result):
            raise ValueError(f"Native failure; retained logs: {path}")
        return result["stdout"]

    def probe(folder, state, query=QUERY, scope=SCOPE, fitted=None, modes=MODES):
        folder.mkdir(parents=True)
        fitted = model if fitted is None else fitted
        text = "!(py-call (time.process_time_ns))\n"
        text += "!(println! (RANKS " + expression(["benefit_ranks", state["tasks"], state["beliefs"], query, scope]) + "))\n"
        for mode in modes:
            text += configure(fitted, mode, query, scope) + "!(benefit_reset_test)\n"
            text += "!(println! (PICK_" + mode + " " + expression(["benefit_select", state["tasks"], state["beliefs"]]) + "))\n"
            text += f"!(println! (STATS_{mode} (benefit_stats)))\n"
        path = folder / "probe.metta"
        path.write_text(text)
        log = run(path, native)
        expected_ranks = native_ranks(state["tasks"], state["beliefs"], query, scope)
        if marked(log, "RANKS") != [expected_ranks]:
            raise ValueError("Embedded Python category bridge mismatch")
        checks = []
        for mode in modes:
            selected, meta = choose(state, fitted, mode, query=query, scope=scope, marginals={})
            if marked(log, f"PICK_{mode}") != [selected]:
                raise ValueError("Native policy differs from Python reference")
            stats = marked(log, f"STATS_{mode}")[0]
            if len(stats) != 9 or [stats[i] for i in (0,1,3,6,7,8)] != [
                    1, meta["classified"], len(meta["predictions"]), int(meta["coverage_fallback"]),
                    int(meta["prediction_fallback"]), int(meta["singleton"])]:
                raise ValueError("Native branch telemetry mismatch")
            if not 0 <= stats[2] + stats[4] <= stats[5]:
                raise ValueError("Invalid descriptor/feature intervals")
            checks.append(dict(mode=mode, selected=selected, stats=stats))
        save(folder / "checks.json", dict(ranks=expected_ranks, choices=checks))
        return checks

    try:
        protocol = load(remember(PROJECT / "configs/benefit-selection-validation.json"))
        save(out / "protocol.json", protocol)
        if protocol["scope"] != SCOPE or protocol["modes"] != list(MODES):
            raise ValueError("Unexpected validation scope/modes")
        data = PROJECT / protocol["data_batch"]
        previous = load(remember(data / "report.json"))
        descriptors = load(remember(PROJECT / protocol["descriptor_batch"] / "report.json"))
        if not previous["passed"] or not descriptors["passed"]:
            raise ValueError("Missing successful prerequisite validation")
        model = load(remember(PROJECT / protocol["model_path"]))
        manifest = load(remember(data / "split-manifest.json"))
        config = load(remember(PROJECT / "configs/qualification-kb.json"))
        runtime = Runtime(PROJECT, remember(PROJECT / "configs/runtime.json"))
        report["provenance_before"] = runtime.verify()
        source = (runtime.pln / "lib_pln.metta").read_text()
        source_hash = hashlib.sha256(source.encode()).hexdigest()
        if source_hash != previous["native_library_sha256"]:
            raise ValueError("Pinned source changed since data collection")
        report["native_library_sha256"] = source_hash
        report["source_sha256"] = {str(p.relative_to(PROJECT)): digest(p)
            for folder in ("src", "scripts", "configs", "tests")
            for p in sorted((PROJECT / folder).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}
        boot = out / "bootstrap.pl"
        boot.write_text(bootstrap(PROJECT))
        libraries = {}
        for audit in (False, True):
            text, diff = build_library(source, audit)
            path = out / ("lib_pln.audit.metta" if audit else "lib_pln.quiet.metta")
            path.write_text(text)
            path.with_suffix(".diff").write_text(diff)
            libraries[audit] = path
        native = out / "lib_pln.native.metta"
        native.write_text(quiet_library(source)[0])
        (out / "PLN-LICENSE.txt").write_bytes((runtime.pln / "LICENSE").read_bytes())
        report["adapter_sha256"] = {p.name: digest(p) for p in [boot, native, *libraries.values()]}
        cases, origins = {}, {}
        for entry in manifest["development"]:
            path = remember(PROJECT / entry["fixture"])
            if digest(path) != entry["fixture_sha256"]:
                raise ValueError("Changed development fixture")
            case = read_case(path.read_text())
            expected = (kb_records(int(entry["name"].split('-')[0][1:])) if entry["family"] == "alternative"
                        else necessary_records(int(entry["name"].split('-')[1][1:])))
            if case["marginals"] != {} or case["query"] != QUERY or sorted(map(key, case["inputs"])) != sorted(map(key, expected)):
                raise ValueError("Case outside previously qualified closed family")
            path = remember(PROJECT / entry["states_path"])
            if digest(path) != entry["states_sha256"]:
                raise ValueError("Changed native checkpoints")
            origins[entry["name"]] = ([json.loads(s) for s in path.read_text().splitlines()]
                                      if entry["states_format"] == "jsonl" else load(path))
            cases[entry["name"]] = case
        for entry in previous["states"]:
            name = entry["name"]
            state = load(remember(data / name / "state.json"))
            fs = load(remember(data / name / "features.json"))
            if fs["split"] != "development" or key(state) != fs["state_sha256"] or state != origins[fs["case"]][fs["checkpoint"]]["state"]:
                raise ValueError("Wrong saved state")
            print(f"Saved-state bridge and policy check: {name}", flush=True)
            probe(out / "probes" / name, state)
            report["probes"].append(dict(state=name, candidates=len(state["tasks"]), modes=list(MODES)))
        cap = protocol["validation_budget_ns"]
        for entry in manifest["development"]:
            name, case = entry["name"], cases[entry["name"]]
            paths = {}
            for mode in MODES:
                print(f"Native proof/transition validation: {name} {mode}", flush=True)
                folder = out / "policies" / name / mode
                folder.mkdir(parents=True)
                path = folder / "audit.metta"
                path.write_text(selection_fixture(case, config, cap, model, mode))
                log = run(path, libraries[True])
                states, selected, cert, checked = audit_trace(log, case, config, model, mode,
                    source_hash, entry["fixture_sha256"],
                    selection_reference=partial(choose, query=case["query"], scope=SCOPE, marginals={}))
                result, _, _ = check_result(log, cap, states, log, case, source_hash,
                    entry["fixture_sha256"], config["success"], audit=True)
                if not result["verified_success"]:
                    raise ValueError("Audit failed to reach verified proof")
                paths[mode] = [s["state"] for s in states]
                if mode == "N" and paths[mode] != [s["state"] for s in origins[name][:len(states)]]:
                    raise ValueError("Native reference trajectory changed")
                if mode == "BO" and paths[mode] != paths["B"]:
                    raise ValueError("Overhead-only arm changed usefulness decisions")
                save(folder / "states.json", states)
                save(folder / "certificate.json", cert)
                save(folder / "proof-replay.json", checked)
                transitions = 0
                if mode != "N":
                    ref = folder / "native-transitions.metta"
                    ref.write_text("".join(reference_fixture(s["state"], c).replace("COST_REFERENCE", f"TRANSITION_{i}")
                        for i, (s,c) in enumerate(zip(states[:-1], selected, strict=True))))
                    ref_log = run(ref, native)
                    forms = [read_one(line) for line in ref_log.splitlines() if line.startswith("(TRANSITION_")]
                    expected = [[f"TRANSITION_{i}", [states[i+1]["state"][k] for k in ("tasks", "beliefs")]]
                                for i in range(len(selected))]
                    if forms != expected:
                        raise ValueError("Changed native transition")
                    transitions = len(forms)
                quiet = folder / "quiet.metta"
                quiet.write_text(path.read_text())
                qlog = run(quiet, libraries[False])
                qresult, _, _ = check_result(qlog, cap, states, log, case, source_hash,
                    entry["fixture_sha256"], config["success"])
                stats = marked(qlog, "BENEFIT_STATS")[0]
                if not qresult["verified_success"] or qresult["completed_expansions"] != len(selected):
                    raise ValueError("Quiet/audit mismatch")
                if len(stats) != 9 or stats[0] != len(selected) or not 0 <= stats[2]+stats[4] <= stats[5] <= qresult["engine_cpu_ns"]:
                    raise ValueError("Invalid integrated CPU accounting")
                if stats[6:8] != [0,0]:
                    raise ValueError("Unexpected qualified-run fallback")
                report["policies"].append(dict(case=name, mode=mode, expansions=len(selected),
                    verified=True, native_transition_checks=transitions, stats=stats,
                    single_validation_cpu_ns_not_performance=qresult["engine_cpu_ns"]))
                save(out / "report.json", report)
        # Authored edge states are correctness probes, not timing observations.
        base_case = next(iter(cases.values()))
        base = dict(tasks=deepcopy(base_case["inputs"]), beliefs=deepcopy(base_case["inputs"]))
        variants = [("equal-predictions", base, {**model, "weights": [0.]*10}, SCOPE),
                    ("invalid-predictions", base, {**model, "intercept": 10000.}, SCOPE),
                    ("unknown-coverage", base, model, "unknown")]
        singleton = deepcopy(base)
        singleton["tasks"] = singleton["tasks"][:1]
        variants.append(("singleton", singleton, model, SCOPE))
        unequal = deepcopy(base)
        unequal["tasks"][-1][1][1][2] = .95
        variants.append(("unequal-confidence", unequal, model, SCOPE))
        # Scope function must reject implications that could alter dependencies.
        changing = deepcopy(base)
        changing["beliefs"].append(["Sentence", [["Implication", "X", ["Implication", "Y", "Z"]], ["stv",1.,.9]], [999]])
        variants.append(("changing-dependencies", changing, model, SCOPE))
        for label, state, fitted, scope in variants:
            checks = probe(out / "edges" / label, state, fitted=fitted, scope=scope)
            report["edges"].append(dict(name=label, choices=checks))
        for mode in MODES:
            path = out / "edges" / f"zero-{mode}.metta"
            path.write_text(selection_fixture(base_case, config, 0, model, mode))
            log = run(path, libraries[False])
            result = marked(log, "BUDGET_RESULT")[0]
            if result[0] != "deadline" or result[1] != 0 or marked(log, "BENEFIT_STATS")[0][0] != 0:
                raise ValueError("Zero budget performed work")
            report["edges"].append(dict(name=f"zero-{mode}", passed=True))
        report["provenance_after"] = runtime.verify()
        report["input_sha256"] = inputs
        if report["provenance_before"] != report["provenance_after"]:
            raise ValueError("Runtime provenance changed")
        for rel, expected in {**inputs, **report["source_sha256"]}.items():
            if digest(PROJECT / rel) != expected:
                raise ValueError(f"Input/source changed during validation: {rel}")
        report["passed"] = True
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    save(out / "report.json", report)
    print(json.dumps(dict(passed=report["passed"], error=report.get("error"),
        saved_states=len(report["probes"]), policy_runs=len(report["policies"]), report=str(out / "report.json")), indent=2), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
