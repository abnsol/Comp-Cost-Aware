#!/usr/bin/env python3
"""Validate structural descriptors against saved development evidence; time Python only."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import statistics
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.benefit_signals import describe, freeze, implication, SCOPE
from pln_cost.proof import key
from pln_cost.qualification import kb_records, QUERY
from pln_cost.selection_workloads import necessary_records
from pln_cost.sexpr import read_case


def load(p):
    return json.loads(p.read_text())


def save(p, obj):
    p.write_text(json.dumps(obj, indent=2) + "\n")


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def reference(state, query, candidate):
    """Offline brute-force counterpart: scan records; DFS for each consequence."""
    beliefs = state["beliefs"]
    term, ev = candidate[1][0], set(candidate[2])
    consequences = []
    for other in beliefs:
        t = other[1][0]
        if ev.intersection(other[2]):
            continue
        if implication(t) and t[1] == term:
            consequences.append((t[2], sorted(ev | set(other[2]))))
        if implication(term) and term[1] == t:
            consequences.append((term[2], sorted(ev | set(other[2]))))
    def connected(start):
        stack, seen = [start], set()
        while stack:
            node = stack.pop()
            if node == query:
                return True
            k = freeze(node)
            if k in seen:
                continue
            seen.add(k)
            stack.extend(r[1][0][2] for r in beliefs
                         if implication(r[1][0]) and r[1][0][1] == node)
        return False
    result = []
    for t, evidence in consequences:
        represented = any(r[1][0] == t for r in beliefs)
        status = ("potential_goal" if t == query else
                  "represented_intermediate_value_unresolved" if connected(t) and represented else
                  "missing_intermediate" if connected(t) else "no_known_query_connection")
        result.append((freeze(t), tuple(evidence), status, represented))
    return Counter(result)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum():
        ap.error("Simple run ID required")
    out = PROJECT / "results/benefit-signals" / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    protocol = load(PROJECT / "configs/benefit-signal-validation.json")
    save(out / "protocol.json", protocol)
    report = {"passed": False, "scope": "development descriptors; Python acquisition only",
              "native_executions": 0, "selector_changed": False, "states": []}
    inputs = {}
    def checked_load(path):
        inputs[str(path.relative_to(PROJECT))] = digest(path)
        return load(path)
    try:
        data = PROJECT / protocol["data_batch"]
        prior = checked_load(data / "report.json")
        manifest = checked_load(data / "split-manifest.json")
        if not prior["passed"] or protocol["scope"] != SCOPE:
            raise ValueError("Unqualified data or scope")
        for entry in manifest["development"]:
            path = PROJECT / entry["fixture"]
            if digest(path) != entry["fixture_sha256"]:
                raise ValueError("Changed fixture")
            inputs[entry["fixture"]] = digest(path)
            case = read_case(path.read_text())
            expected = (kb_records(int(entry["name"].split('-')[0][1:])) if entry["family"] == "alternative"
                        else necessary_records(int(entry["name"].split('-')[1][1:])))
            if case["marginals"] != {} or case["query"] != QUERY or sorted(map(key, case["inputs"])) != sorted(map(key, expected)):
                raise ValueError("Closed workload shape differs from qualified family")
            original_path = PROJECT / entry["states_path"]
            if digest(original_path) != entry["states_sha256"]:
                raise ValueError("Changed native states")
        entry_map = {e["name"]: e for e in manifest["development"]}
        states, expected_results = {}, {}
        candidates = parity = 0
        for entry in prior["states"]:
            name = entry["name"]
            state = checked_load(data / name / "state.json")
            features = checked_load(data / name / "features.json")
            if features["split"] != "development" or features["case"] not in entry_map or key(state) != features["state_sha256"]:
                raise ValueError("Wrong state or split")
            origin = entry_map[features["case"]]
            text = (PROJECT / origin["states_path"]).read_text()
            native = [json.loads(line) for line in text.splitlines()] if origin["states_format"] == "jsonl" else json.loads(text)
            if state != native[features["checkpoint"]]["state"]:
                raise ValueError("State differs from verified native checkpoint")
            result = describe(state, QUERY, scope=SCOPE, marginals={})
            if result["coverage"] != SCOPE:
                raise ValueError("Qualified state rejected")
            for row in result["candidates"]:
                projected = Counter((freeze(o["term"]), tuple(o["evidence_union"]), o["status"], o["term_already_present"]) for o in row["outputs"])
                if projected != reference(state, QUERY, row["candidate"]):
                    raise ValueError("Index/BFS disagrees with scan/DFS reference")
                candidates += 1
            by_key = {key(r["candidate"]): r for r in result["candidates"]}
            for c, fs in zip(features["candidates"], features["features"], strict=True):
                if by_key[key(c)]["mp_pairs"] != fs["mp_matches"]:
                    raise ValueError("Changed prospective MP-count semantics")
                parity += 1
            if key(state) != features["state_sha256"]:
                raise ValueError("State mutated")
            states[name], expected_results[name] = state, result
            folder = out / name; folder.mkdir()
            save(folder / "descriptors.json", result)
        # Existing native all-candidate initial expansions independently check
        # possible output terms and evidence, not just graph implementation.
        native_checks = 0
        for width in (4, 16):
            root = PROJECT / f"results/selection/step-02/run001/necessary-w{width:03d}-canonical_ids"
            initial = checked_load(root / "initial-state.json")
            outputs = checked_load(root / "initial-expansion-outputs.json")
            for row in describe(initial, QUERY, scope=SCOPE, marginals={})["candidates"]:
                ident = str(row["candidate"][2][0])
                new = [r for r in outputs[ident][1] if r not in initial["beliefs"]]
                actual = {(freeze(r[1][0]), tuple(r[2])) for r in new}
                predicted = {(freeze(o["term"]), tuple(o["evidence_union"])) for o in row["outputs"]}
                if actual != predicted:
                    raise ValueError("Descriptor disagrees with saved native initial expansion")
                native_checks += 1
        report.update(states_validated=len(states), candidates_validated=candidates,
                      archived_feature_matches=parity, saved_native_expansion_matches=native_checks)
        report["source_sha256"] = {str(p.relative_to(PROJECT)): digest(p) for p in [
            PROJECT / "src/pln_cost/benefit_signals.py", Path(__file__),
            PROJECT / "tests/test_benefit_signals.py", PROJECT / "configs/benefit-signal-validation.json",
            PROJECT / "src/pln_cost/proof.py"]}
        report["input_sha256"] = inputs
        save(out / "report.json", report)
        print(f"Validated {len(states)} states, {candidates} candidates, {native_checks} native expansions. Timing begins.", flush=True)
        samples = {name: [] for name in states}
        empties = []
        for block in range(protocol["blocks"]):
            names = list(states); random.Random(protocol["seed"] + block).shuffle(names)
            empty = []
            for _ in range(protocol["empty_repetitions"]):
                t = time.process_time_ns(); empty.append(time.process_time_ns()-t)
            empties.append(empty)
            for name in names:
                state = states[name]
                for _ in range(protocol["warmup_calls_per_state"]):
                    describe(state, QUERY, scope=SCOPE, marginals={})
                block_samples = []
                for _ in range(protocol["repetitions_per_block"]):
                    t = time.process_time_ns()
                    result = describe(state, QUERY, scope=SCOPE, marginals={})
                    elapsed = time.process_time_ns()-t
                    if result != expected_results[name]:
                        raise ValueError("Timed descriptor changed")
                    block_samples.append(elapsed)
                samples[name].append(block_samples)
            print(f"Timing block {block+1}/{protocol['blocks']} complete", flush=True)
        save(out / "empty-samples.json", empties)
        for name in states:
            blocks = samples[name]
            ratios = [sorted(e)[int(.95*(len(e)-1))]/statistics.median(b) for e, b in zip(empties, blocks, strict=True)]
            row = {"name": name, "pending_candidates": len(expected_results[name]["candidates"]),
                   "block_median_cpu_ns": [statistics.median(b) for b in blocks],
                   "median_cpu_ns": statistics.median(statistics.median(b) for b in blocks),
                   "empty_p95_fractions": ratios,
                   "timing_resolved": max(ratios) <= protocol["maximum_empty_p95_fraction"]}
            report["states"].append(row)
            save(out / name / "timing.json", {**row, "raw_blocks_ns": blocks})
        for paths in (report["source_sha256"], inputs):
            for name, expected in paths.items():
                if digest(PROJECT / name) != expected:
                    raise ValueError(f"Source/evidence changed: {name}")
        report["all_timings_resolved"] = all(r["timing_resolved"] for r in report["states"])
        report["passed"] = True  # Timing resolution is separately reported, never hidden.
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    save(out / "report.json", report)
    print(json.dumps({k: report.get(k) for k in ("passed", "error", "states_validated", "candidates_validated", "archived_feature_matches", "saved_native_expansion_matches", "all_timings_resolved")}), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
