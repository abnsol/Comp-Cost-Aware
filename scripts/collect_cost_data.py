#!/usr/bin/env python3
"""Freeze held-out fixtures; collect restored-state CPU labels on development only."""
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
from pln_cost.cost_features import FEATURE_NAMES, eligible_candidates, features
from pln_cost.expansion import build_expansion, reference_fixture
from pln_cost.feasibility import observable_parity
from pln_cost.first_answer import first_verified, quiet_library
from pln_cost.paired import quantile
from pln_cost.proof import key, replay, sentence
from pln_cost.qualification import expression, qualifies, render_case, static_witness
from pln_cost.runtime import Runtime
from pln_cost.selection_workloads import evaluation_records
from pln_cost.sexpr import read_case, read_one
from pln_cost.states import capture_states, instrument_states
from pln_cost.validation import clean_completion


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def development_manifest():
    entries = []
    previous = read_json(PROJECT / "results/qualification/step-07/run001/report.json")
    if not previous["passed"]:
        raise ValueError("Original development evidence did not pass")
    for e in previous["cases"]:
        name = e["name"]
        fixture = PROJECT / f"cases/qualification/run001/{name}.metta"
        if sha(fixture.read_bytes()) != e["fixture_sha256"]:
            raise ValueError("Original fixture changed")
        snapshots = PROJECT / f"results/qualification/step-04/run001/{name}/snapshots.jsonl"
        if sha(snapshots.read_bytes()) != e["snapshot_sha256"]:
            raise ValueError("Original saved states changed")
        entries.append({"name": name, "family": "alternative", "split": "development",
            "fixture": str(fixture.relative_to(PROJECT)), "fixture_sha256": e["fixture_sha256"],
            "states_path": str(snapshots.relative_to(PROJECT)), "states_format": "jsonl",
            "states_sha256": sha(snapshots.read_bytes()), "first_step": e["first_completed_expansions"]})
    previous = read_json(PROJECT / "results/selection/step-02/run001/report.json")
    if not previous["passed"]:
        raise ValueError("Necessary-work development evidence did not pass")
    for e in previous["cases"]:
        folder = PROJECT / "results/selection/step-02/run001" / e["name"]
        fixture, snapshots = folder / "native.metta", folder / "states.json"
        if sha(fixture.read_bytes()) != e["fixture_sha256"]:
            raise ValueError("Necessary-work fixture changed")
        entries.append({"name": e["name"], "family": "necessary", "split": "development",
            "fixture": str(fixture.relative_to(PROJECT)), "fixture_sha256": e["fixture_sha256"],
            "states_path": str(snapshots.relative_to(PROJECT)), "states_format": "json",
            "states_sha256": sha(snapshots.read_bytes()), "first_step": e["first_verified_expansion"]})
    return entries


def profiling_fixture(helper, state, candidates, outputs, protocol, seed):
    """All samples execute the same immutable state, in shuffled full passes."""
    text = helper + "\n(= (Bench.Clock) (py-call (time.process_time_ns)))\n"
    for name, value in (("Data.Tasks", state["tasks"]), ("Data.Beliefs", state["beliefs"])):
        text += f"(= ({name}) {expression(value)})\n"
    tq, bq = state["task_limit"], state["belief_limit"]
    for i, candidate in enumerate(candidates):
        text += f"(= (Data.Candidate {i}) {expression(candidate)})\n"
        text += f"(= (Data.Expected {i}) {expression(outputs[i])})\n"
    text += f"""
(= (Data.One $phase $rep $i $mode)
 (let* (($tasks (Data.Tasks)) ($beliefs (Data.Beliefs))
        ($candidate (Data.Candidate $i)) ($expected (Data.Expected $i)))
  (thin_sample $phase $rep $i $mode $tasks $beliefs $candidate {tq} {bq} $expected 0)))
!(Bench.Clock)
"""
    for i in range(len(candidates)):
        text += f"!(thin_verify (Data.Tasks) (Data.Beliefs) (Data.Candidate {i}) {tq} {bq} (Data.Expected {i}))\n"
    rng, schedule = random.Random(seed), []
    for phase, count in (("Warmup", protocol["warmup_passes"]), ("Measured", protocol["measured_passes"])):
        for rep in range(count):
            indices = list(range(len(candidates)))
            rng.shuffle(indices)
            for i in indices:
                text += f"!(Data.One {phase} {rep} {i} Real)\n"
                schedule.append([phase, rep, i, 1])
    for rep in range(protocol["empty_samples"]):
        i = rep % len(candidates)
        text += f"!(Data.One Empty {rep} {i} Empty)\n"
        schedule.append(["Empty", rep, i, 1])
    return text, schedule


def parse_profile(log, schedule, count, protocol):
    rows = [read_one(l)[1:] for l in log.splitlines() if l.startswith("(PAIRED_SAMPLE ")]
    if [r[:4] for r in rows] != schedule:
        raise ValueError("Profile schedule mismatch")
    if any(len(r) != 7 or r[4] != 0 or type(r[5]) is not int or r[5] <= 0 or r[6] != "true" for r in rows):
        raise ValueError("Invalid clock or output check")
    empty = [r[5] for r in rows if r[0] == "Empty"]
    by_candidate = [[r[5] for r in rows if r[0] == "Measured" and r[2] == i] for i in range(count)]
    if any(len(xs) != protocol["measured_passes"] for xs in by_candidate):
        raise ValueError("Incomplete candidate samples")
    return {"empty_ns": empty, "empty_p95_ns": quantile(empty, .95), "candidate_samples_ns": by_candidate}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum():
        ap.error("Simple run ID required")
    output = PROJECT / "results/selection/step-03" / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    protocol = read_json(PROJECT / "configs/cost-data-protocol.json")
    base = read_json(PROJECT / "configs/qualification-kb.json")
    save(output / "protocol.json", protocol)
    report = {"passed": False, "native_runs": [], "evaluation_checks": [], "states": [],
              "model_trained": False, "policy_evaluated": False, "evaluation_cpu_labels_collected": False}

    def run(path, library, bootstrap=None):
        result = runtime.run(path, preload_pln=True, library_path=library, bootstrap_path=bootstrap)
        for stream in ("stdout", "stderr"):
            path.with_suffix(f".{stream}.txt").write_text(result[stream])
        report["native_runs"].append({"fixture": str(path.relative_to(output)),
            "fixture_sha256": sha(path.read_bytes()), "stdout_sha256": sha(result["stdout"].encode()),
            **{k: v for k, v in result.items() if k not in ("stdout", "stderr")}})
        save(output / "report.json", report)
        if not clean_completion(result):
            raise RuntimeError(f"Execution failed: {path}; raw logs retained")
        return result["stdout"]

    try:
        runtime = Runtime(PROJECT, PROJECT / "configs/runtime.json")
        report["provenance_before"] = runtime.verify()
        source = (runtime.pln / "lib_pln.metta").read_text()
        source_hash = sha(source.encode())
        report["native_library_sha256"] = source_hash
        report["source_sha256"] = {str(p.relative_to(PROJECT)): sha(p.read_bytes())
            for folder in ("src", "scripts", "configs", "tests") for p in sorted((PROJECT / folder).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}
        helper = build_expansion(source)
        (output / "expand.metta").write_text(helper)
        (output / "PLN-LICENSE.txt").write_bytes((runtime.pln / "LICENSE").read_bytes())
        bootstrap = output / "thin_clock.pl"
        bootstrap.write_bytes((PROJECT / "src/pln_cost/thin_clock.pl").read_bytes())
        quiet = output / "lib_pln.quiet.metta"
        quiet.write_text(quiet_library(source)[0])
        traced = output / "lib_pln.states.metta"
        traced.write_text(instrument_states(source)[0])
        manifest = {"development": development_manifest(), "evaluation": []}
        limits, success = base["initial_correctness_limits"], base["success"]
        # Write and hash all split members BEFORE executing new fixtures.
        evaluation_dir = output / "evaluation"
        evaluation_dir.mkdir()
        for v in protocol["evaluation"]["variants"]:
            for order in protocol["evaluation"]["orderings"]:
                name = v["name"] + "-" + order
                folder = evaluation_dir / name
                folder.mkdir()
                records = evaluation_records(v["width"], v["modules"], v["shared_sinks"], order,
                    protocol["evaluation"]["shuffle_seed"])
                fixture = folder / "native.metta"
                fixture.write_text(render_case(records, limits))
                manifest["evaluation"].append({"name": name, "split": "evaluation", "variant": v,
                    "fixture": str(fixture.relative_to(PROJECT)), "fixture_sha256": sha(fixture.read_bytes())})
        if {x["fixture_sha256"] for x in manifest["development"]} & {x["fixture_sha256"] for x in manifest["evaluation"]}:
            raise ValueError("Development/evaluation overlap")
        save(output / "split-manifest.json", manifest)
        report["split_manifest_sha256"] = sha((output / "split-manifest.json").read_bytes())
        for entry in manifest["evaluation"]:
            print(f"Held-out correctness only: {entry['name']}", flush=True)
            fixture = PROJECT / entry["fixture"]
            case = read_case(fixture.read_text())
            cert = static_witness(case, [1, 2, 3], source_hash, entry["fixture_sha256"])
            if not qualifies(replay(cert, case, source_hash, entry["fixture_sha256"]), success):
                raise ValueError("Invalid held-out authored proof")
            save(fixture.parent / "authored-proof.json", cert)
            native = run(fixture, None)
            audit_fixture = fixture.parent / "traced.metta"
            audit_fixture.write_text(fixture.read_text())
            log = run(audit_fixture, traced)
            filtered = "\n".join(l for l in log.splitlines() if not l.startswith(("(QUAL_STATE ", "(QUAL_TRIM ")))
            if not observable_parity(native, filtered)["all_original_output_unchanged"]:
                raise ValueError("Held-out instrumentation parity failed")
            states, trims = capture_states(log, case, limits)
            first, cert, checked = first_verified(states, log, case, source_hash, entry["fixture_sha256"], success)
            if trims:
                raise ValueError("Unexpected held-out trimming")
            save(fixture.parent / "first-proof.json", cert)
            save(fixture.parent / "proof-replay.json", checked)
            report["evaluation_checks"].append({"name": entry["name"], "valid": True,
                "first_proof_expansion": first, "cpu_measured": False})

        rows, jobs = [], []
        for entry in manifest["development"]:
            if entry["split"] != "development":
                raise ValueError("Timing input is not development")
            path = PROJECT / entry["states_path"]
            if sha(path.read_bytes()) != entry["states_sha256"]:
                raise ValueError("State source changed")
            saved = [json.loads(l) for l in path.read_text().splitlines()] if entry["states_format"] == "jsonl" else read_json(path)
            indices = sorted({i for i in (0, 1, entry["first_step"]//2, entry["first_step"]-1) if i < entry["first_step"]})
            for index in indices:
                snapshot = saved[index]
                state = snapshot["state"]
                if key(state) != snapshot["sha256"] or ("source_sha256" in snapshot and snapshot["source_sha256"] != source_hash):
                    raise ValueError("Invalid state provenance/content")
                candidates = eligible_candidates(state)
                if not candidates:
                    raise ValueError("No eligible candidates before first goal")
                name = entry["name"] + f"-s{index:03d}"
                folder = output / name
                folder.mkdir()
                save(folder / "state.json", state)
                row = {"name": name, "case": entry["name"], "family": entry["family"], "split": "development",
                    "checkpoint": index, "state_sha256": key(state), "candidates": candidates,
                    "features": [features(state, c) for c in candidates]}
                # Separate Python diagnostic; this is not added to native CPU
                # labels or treated as an actual online selector measurement.
                overhead = []
                for _ in range(protocol["timing"]["feature_timing_repetitions"]):
                    start = time.process_time_ns()
                    computed = [features(state, c) for c in eligible_candidates(state)]
                    end = time.process_time_ns()
                    if computed != row["features"]:
                        raise ValueError("Nondeterministic feature extraction")
                    overhead.append(end-start)
                row["all_eligible_features_python_cpu_ns"] = overhead
                save(folder / "features.json", row)
                jobs.append((row, state, folder))

        save(output / "state-manifest.json", [{k: v for k, v in row.items() if k not in ("features", "candidates", "all_eligible_features_python_cpu_ns")}
            for row, _, _ in jobs])
        # Each state's native/helper audit precedes its timing. No selection by
        # measured cost, and no state/candidate is removed after observing cost.
        for job_index, (row, state, folder) in enumerate(jobs):
            print(f"Development profile {job_index+1}/{len(jobs)}: {row['name']} ({len(row['candidates'])} candidates)", flush=True)
            audit = helper
            for i, candidate in enumerate(row["candidates"]):
                call = ["Cost.Expand", state["tasks"], state["beliefs"], candidate, state["task_limit"], state["belief_limit"]]
                audit += f"\n!(println! (DATA_OUT {i} {expression(call)}))\n"
                audit += reference_fixture(state, candidate).replace("COST_REFERENCE", f"DATA_REF_{i}")
            path = folder / "audit.metta"
            path.write_text(audit)
            log = run(path, quiet)
            outputs = {read_one(l)[1]: read_one(l)[2] for l in log.splitlines() if l.startswith("(DATA_OUT ")}
            references = {int(read_one(l)[0].removeprefix("DATA_REF_")): read_one(l)[1] for l in log.splitlines() if l.startswith("(DATA_REF_")}
            if set(outputs) != set(range(len(row["candidates"]))) or set(references) != set(outputs):
                raise ValueError("Incomplete candidate audit")
            if any(out[:2] != references[i] for i, out in outputs.items()):
                raise ValueError("Helper/native continuation mismatch")
            save(folder / "expected-outputs.json", outputs)
            blocks, schedules = [], []
            for b in range(protocol["timing"]["fresh_blocks"]):
                text, schedule = profiling_fixture(helper, state, row["candidates"], outputs, protocol["timing"],
                    protocol["seed"] + job_index*100 + b)
                path = folder / f"block-{b:02d}.metta"
                path.write_text(text)
                save(path.with_suffix(".schedule.json"), schedule)
                schedules.append((path, schedule))
            for path, schedule in schedules:
                block = parse_profile(run(path, quiet, bootstrap), schedule, len(row["candidates"]), protocol["timing"])
                save(path.with_suffix(".samples.json"), block)
                blocks.append(block)
            summary = {"name": row["name"], "candidate_count": len(row["candidates"]),
                "feature_batch_cpu_median_ns": statistics.median(row["all_eligible_features_python_cpu_ns"]),
                "minimum_candidate_cpu_ns": None, "maximum_candidate_cpu_ns": None}
            cpus = []
            for i, candidate in enumerate(row["candidates"]):
                medians = [statistics.median(b["candidate_samples_ns"][i]) for b in blocks]
                ratios = [b["empty_p95_ns"]/m for b, m in zip(blocks, medians)]
                median = statistics.median(medians)
                cpus.append(median)
                record = {"split": "development", "case": row["case"], "family": row["family"],
                    "state": row["name"], "state_sha256": row["state_sha256"], "candidate": candidate,
                    "candidate_sha256": key(candidate), "candidate_type": candidate[1][0][0],
                    "features": row["features"][i], "median_cpu_ns": median,
                    "block_medians_ns": medians, "samples_ns": [b["candidate_samples_ns"][i] for b in blocks],
                    "empty_p95_fractions": ratios,
                    "fit_eligible": max(ratios) <= protocol["timing"]["maximum_empty_p95_fraction"]}
                rows.append(record)
            summary["minimum_candidate_cpu_ns"], summary["maximum_candidate_cpu_ns"] = min(cpus), max(cpus)
            summary["feature_batch_over_cheapest_expansion"] = summary["feature_batch_cpu_median_ns"] / min(cpus)
            summary["feature_batch_over_median_expansion"] = summary["feature_batch_cpu_median_ns"] / statistics.median(cpus)
            report["states"].append(summary)
            # Save incrementally so failures retain already completed labels.
            (output / "development-costs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        report["summary"] = {"development_cases": len(manifest["development"]), "states": len(jobs),
            "candidate_state_rows": len(rows), "measured_expansions": sum(sum(len(x) for x in r["samples_ns"]) for r in rows),
            "fit_eligible_rows": sum(r["fit_eligible"] for r in rows),
            "candidate_types": dict(Counter(r["candidate_type"] for r in rows)),
            "derived_candidate_rows": sum(len(r["candidate"][2]) > 1 for r in rows),
            "evaluation_cases_verified": len(report["evaluation_checks"]),
            "feature_names": list(FEATURE_NAMES)}
        # Development-only proxy diagnostic: how often the lower match count
        # predicts the lower measured CPU within a saved state's tied set.
        concordant = discordant = ambiguous = 0
        for state in report["states"]:
            group = [r for r in rows if r["state"] == state["name"] and r["fit_eligible"]]
            for i, a in enumerate(group):
                for b in group[i+1:]:
                    diff = a["features"]["mp_matches"] - b["features"]["mp_matches"]
                    if diff == 0:
                        continue
                    ratio = max(a["median_cpu_ns"], b["median_cpu_ns"]) / min(a["median_cpu_ns"], b["median_cpu_ns"])
                    if ratio < 1.1:
                        ambiguous += 1
                    elif diff * (a["median_cpu_ns"]-b["median_cpu_ns"]) > 0:
                        concordant += 1
                    else:
                        discordant += 1
        report["development_proxy_diagnostic"] = {"feature": "mp_matches", "concordant_pairs": concordant,
            "discordant_pairs": discordant, "under_10_percent_cpu_difference": ambiguous,
            "scope": "dependent within-state pairs; exploratory, not held-out predictive accuracy"}
        report["provenance_after"] = runtime.verify()
        if report["provenance_after"] != report["provenance_before"]:
            raise ValueError("Native source/runtime changed")
        report["passed"] = True
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    save(output / "report.json", report)
    print(json.dumps({"passed": report["passed"], "error": report.get("error"),
        "summary": report.get("summary"), "report": str(output / "report.json")}, indent=2), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
