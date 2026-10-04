#!/usr/bin/env python3
"""Validate necessary-work development KBs and their initial CPU contrasts.

No predictor, selector intervention, training, or held-out evaluation is run.
Existing baseline artifacts and native sources are never overwritten.
"""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.expansion import build_expansion, reference_fixture
from pln_cost.feasibility import observable_parity, parse_result
from pln_cost.first_answer import first_verified, quiet_library
from pln_cost.paired import parse, summarize_process
from pln_cost.proof import replay
from pln_cost.qualification import expression, qualifies, render_case, static_witness
from pln_cost.runtime import Runtime
from pln_cost.selection_workloads import CERT, initial_state, necessary_records, validate_necessary_shape
from pln_cost.sexpr import read_case, read_one
from pln_cost.states import capture_states, instrument_states
from pln_cost.thin import thin_fixture
from pln_cost.validation import clean_completion


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum():
        ap.error("Simple run ID required")
    output = PROJECT / "results/selection/step-02" / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    protocol = json.loads((PROJECT / "configs/selection-workload-qualification.json").read_text())
    config = json.loads((PROJECT / "configs/qualification-kb.json").read_text())
    limits, success = config["initial_correctness_limits"], config["success"]
    report = {"passed": False, "scope": protocol["scope"], "native_runs": [],
              "cases": [], "cost_contrasts": [], "selection_intervention_tested": False}
    save(output / "protocol.json", protocol)
    save(output / "baseline-config.json", config)

    def run(path, library=None, bootstrap=None):
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
        runtime = Runtime(PROJECT, PROJECT / "configs/runtime.json")
        report["provenance_before"] = runtime.verify()
        source = (runtime.pln / "lib_pln.metta").read_text()
        source_hash = sha(source.encode())
        report["native_library_sha256"] = source_hash
        report["project_source_sha256"] = {str(p.relative_to(PROJECT)): sha(p.read_bytes())
            for folder in ("src", "scripts", "configs", "tests")
            for p in sorted((PROJECT / folder).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}
        traced, patch = instrument_states(source)
        library = output / "lib_pln.states.metta"
        library.write_text(traced)
        (output / "instrumentation.diff").write_text(patch)
        quiet = output / "lib_pln.quiet.metta"
        quiet.write_text(quiet_library(source)[0])
        helper = build_expansion(source)
        (output / "expand.metta").write_text(helper)
        bootstrap = output / "thin_clock.pl"
        bootstrap.write_bytes((PROJECT / "src/pln_cost/thin_clock.pl").read_bytes())
        (output / "PLN-LICENSE.txt").write_bytes((runtime.pln / "LICENSE").read_bytes())
        conditions = []
        for width in protocol["widths"]:
            for ordering in protocol["orderings"]:
                name = f"necessary-w{width:03d}-{ordering}"
                print(f"Correctness: {name}", flush=True)
                folder = output / name
                folder.mkdir()
                records = necessary_records(width, ordering, protocol["shuffle_seed"], protocol["irrelevant_facts"])
                path = folder / "native.metta"
                path.write_text(render_case(records, limits))
                case = read_case(path.read_text())
                fixture_hash = sha(path.read_bytes())
                shape = validate_necessary_shape(case, width, protocol["irrelevant_facts"])
                authored = static_witness(case, [1, 2, 3], source_hash, fixture_hash)
                authored_checked = replay(authored, case, source_hash, fixture_hash)
                if not qualifies(authored_checked, success):
                    raise ValueError("Authored proof misses acceptance")
                save(folder / "authored-proof.json", authored)
                native_log = run(path)
                trace_path = folder / "traced.metta"
                trace_path.write_text(path.read_text())
                traced_log = run(trace_path, library)
                # State/trim prints are added by the state wrapper, unlike the
                # earlier proof-only wrapper checked by observable_parity.
                filtered = "\n".join(l for l in traced_log.splitlines()
                    if not l.startswith(("(QUAL_STATE ", "(QUAL_TRIM ")))
                parity = observable_parity(native_log, filtered)
                if not parity["all_original_output_unchanged"]:
                    raise ValueError("Instrumentation changed native outputs")
                states, trims = capture_states(traced_log, case, limits)
                index, cert, checked = first_verified(states, traced_log, case, source_hash, fixture_hash, success)
                if trims:
                    raise ValueError("Unexpected trimming in workload qualification")
                final_answer = parse_result(native_log, case)
                save(folder / "captured-first-proof.json", cert)
                save(folder / "first-proof-replay.json", checked)
                save(folder / "states.json", states)
                entry = {"name": name, "shape": shape, "fixture_sha256": fixture_hash,
                    "parity": parity, "first_verified_expansion": index,
                    "first_answer": checked["answer"], "native_final_answer": final_answer,
                    "native_expansions": len(states)-1, "trimming_events": len(trims)}
                report["cases"].append(entry)
                if ordering != "canonical_ids":
                    continue
                # Removing either licensed premise is a logical negative control,
                # NOT a cost comparison (the buffer changes).
                entry["missing_premise_controls"] = []
                for missing in (1, 2):
                    negative = folder / f"without-premise-{missing}.metta"
                    negative.write_text(render_case([r for r in records if r[2] != [missing]], limits))
                    answer = parse_result(run(negative), read_case(negative.read_text()))
                    if answer is not None:
                        raise ValueError("Unexpected goal without required premise")
                    entry["missing_premise_controls"].append({"removed_id": missing, "answer": None})
                state = initial_state(records, limits)
                save(folder / "initial-state.json", state)
                # Compare every initial one-expansion helper output to the native
                # one-step loop with the same tie-selected item. All other task
                # order is preserved after that selected item is removed.
                all_helper = helper
                all_reference = ""
                for r in records:
                    ident = r[2][0]
                    call = ["Cost.Expand", records, records, r, state["task_limit"], state["belief_limit"]]
                    all_helper += f"\n!(println! (WORK_EXP {ident} {expression(call)}))\n"
                    all_reference += reference_fixture(state, r).replace("COST_REFERENCE", f"WORK_REF_{ident}")
                hp, rp = folder / "all-expansions.metta", folder / "all-references.metta"
                hp.write_text(all_helper)
                rp.write_text(all_reference)
                helper_log, reference_log = run(hp, quiet), run(rp, quiet)
                outputs = {read_one(l)[1]: read_one(l)[2] for l in helper_log.splitlines() if l.startswith("(WORK_EXP ")}
                references = {int(read_one(l)[0].removeprefix("WORK_REF_")): read_one(l)[1]
                    for l in reference_log.splitlines() if l.startswith("(WORK_REF_")}
                if len(outputs) != len(records) or len(references) != len(records):
                    raise ValueError("Incomplete initial-candidate audit")
                frontier = []
                for ident, out in outputs.items():
                    if out[:2] != references[ident]:
                        raise ValueError("Helper differs from native one-step queues")
                    if any(r[1][0] == CERT for r in out[2]):
                        frontier.append(ident)
                    expected_count = width + 1 if ident in (1, 2) else 0 if ident in (3, 4, 5, 6, 7) else 1
                    if len(out[2]) != expected_count:
                        raise ValueError(f"Unexpected derivation count for {ident}: {len(out[2])}")
                if frontier != [1, 2]:
                    raise ValueError("Unexpected certificate-producing initial candidate")
                save(folder / "initial-expansion-outputs.json", outputs)
                entry["initial_candidates_native_checked"] = len(outputs)
                entry["certificate_frontier_ids"] = frontier
                for ident in (1, 2):
                    conditions.append({"name": f"w{width:03d}-required-{ident}", "state": state,
                        "candidates": {"A": records[3], "B": records[ident-1]},
                        "expected": {"A": outputs[4], "B": outputs[ident]},
                        "labels": {"A": "irrelevant fact ID 4", "B": f"required endpoint ID {ident}"}})
            save(output / "report.json", report)
        save(output / "timing-conditions.json", conditions)
        timing = protocol["timing"]
        # Save every measurement fixture/schedule before measuring any condition.
        jobs = []
        for ci, condition in enumerate(conditions):
            folder = output / condition["name"]
            folder.mkdir()
            for block in range(timing["blocks"]):
                text, schedule = thin_fixture(helper, condition, timing, timing["seed"] + ci*100 + block,
                    timing["measured_pairs"], timing["empty_samples"])
                path = folder / f"block-{block:02d}.metta"
                path.write_text(text)
                save(path.with_suffix(".schedule.json"), schedule)
                jobs.append((condition, path, schedule))
        blocks = {c["name"]: [] for c in conditions}
        for condition, path, schedule in jobs:
            print(f"CPU qualification: {condition['name']} {path.stem}", flush=True)
            parsed = parse(run(path, quiet, bootstrap), schedule)
            summary = summarize_process(parsed)
            save(path.with_suffix(".samples.json"), parsed)
            save(path.with_suffix(".summary.json"), summary)
            blocks[condition["name"]].append(summary)
        for condition in conditions:
            bs = blocks[condition["name"]]
            adequate = all(b["empty_p95_fraction"] <= timing["maximum_empty_p95_fraction"] for b in bs)
            floor = timing["empty_median_gap_multiplier"] * max(b["empty_median_ns"] for b in bs)
            consistent = all(b["median_ratio"] > timing["minimum_ratio"] and b["median_difference_ns"] > floor for b in bs)
            entry = {"name": condition["name"], "labels": condition["labels"],
                "blocks": len(bs), "measured_pairs": sum(len(b["pairs"]) for b in bs),
                "median_cpu_ns": {r: statistics.median(b["median_cpu_ns"][r] for b in bs) for r in ("A", "B")},
                "median_paired_ratio": statistics.median(b["median_ratio"] for b in bs),
                "block_paired_ratios": [b["median_ratio"] for b in bs],
                "maximum_empty_p95_fraction": max(b["empty_p95_fraction"] for b in bs),
                "instrumentation_adequate": adequate, "minimum_gap_floor_ns": floor,
                "verdict": "consistent_initial_cost_contrast" if adequate and consistent else
                    "instrumentation_unresolved" if not adequate else "cost_contrast_inconclusive"}
            report["cost_contrasts"].append(entry)
        report["provenance_after"] = runtime.verify()
        if report["provenance_before"] != report["provenance_after"]:
            raise ValueError("Native source/runtime changed")
        report["passed"] = True  # Execution/checks passed, not a policy improvement.
        report["all_initial_cost_contrasts_qualified"] = all(e["verdict"] == "consistent_initial_cost_contrast" for e in report["cost_contrasts"])
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    save(output / "report.json", report)
    print(json.dumps({"passed": report["passed"], "error": report.get("error"),
        "cases": len(report["cases"]), "contrasts": report["cost_contrasts"],
        "report": str(output / "report.json")}, indent=2), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
