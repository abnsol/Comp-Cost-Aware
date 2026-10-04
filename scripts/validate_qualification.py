#!/usr/bin/env python3
"""Run all nine qualification cases natively and with proof tracing; no timing."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.feasibility import observable_parity, parse_result
from pln_cost.proof import SOURCE_COMMIT, extract_certificate, replay
from pln_cost.qualification import kb_records, qualifies, render_case, validate_config
from pln_cost.runtime import Runtime
from pln_cost.sexpr import read_case
from pln_cost.tracing import instrument
from pln_cost.validation import clean_completion


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--case-batch", default="run001")
    args = parser.parse_args()
    for ident in (args.run_id, args.case_batch):
        if not ident.replace("-", "").replace("_", "").isalnum():
            parser.error("Simple alphanumeric IDs with optional '-'/'_' required")
    output = PROJECT / "results/qualification/step-03" / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    report = {"purpose": "bounded native feasibility and returned-proof audit",
              "case_batch": args.case_batch, "cases": [], "passed": False,
              "cpu_costs_measured": False, "first_answer_availability_measured": False,
              "queue_occupancy_and_trimming_measured": False}
    try:
        batch = PROJECT / "results/qualification/step-02" / args.case_batch
        config = json.loads((batch / "config.json").read_text())
        manifest = json.loads((batch / "report.json").read_text())
        validate_config(config)
        if not manifest["passed"]:
            raise ValueError("Input batch did not pass static validation")
        save(output / "config.json", config)
        runtime = Runtime(PROJECT, PROJECT / "configs/runtime.json")
        limits = config["initial_correctness_limits"]
        if (limits["wall_safety_timeout_seconds"] != runtime.config["timeout_seconds"]
                or limits["stack_limit"] != "1g"):
            raise ValueError("Runtime limits differ from the reviewed specification")
        report["provenance_before"] = runtime.verify()
        if report["provenance_before"]["pln"]["commit"] != SOURCE_COMMIT:
            raise ValueError("Checker source revision mismatch")
        source = (runtime.pln / "lib_pln.metta").read_text()
        source_hash = sha(source.encode())
        if source_hash != manifest["native_library_sha256"]:
            raise ValueError("Native source changed since static validation")
        traced, patch = instrument(source)
        library = output / "lib_pln.traced.metta"
        library.write_text(traced)
        (output / "instrumentation.diff").write_text(patch)
        (output / "PLN-LICENSE.txt").write_text((runtime.pln / "LICENSE").read_text())
        report["hashes"] = {"native_library": source_hash, "traced_library": sha(traced.encode()),
                            "input_manifest": sha((batch / "report.json").read_bytes())}
        report["project_source_sha256"] = {
            str(p.relative_to(PROJECT)): sha(p.read_bytes())
            for folder in ("src", "scripts", "configs", "tests")
            for p in sorted((PROJECT / folder).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}
        expected = {(n, ordering) for n in config["development_widths"]
                    for ordering in config["input_orderings"]}
        entries = manifest["cases"]
        if len(entries) != len(expected) or {(e["width"], e["ordering"]) for e in entries} != expected:
            raise ValueError("Input batch does not contain exactly the specified cases")
        # Check every saved input before executing any case. Do not regenerate or
        # silently change the reviewed fixtures/caps during feasibility testing.
        for entry in entries:
            fixture = PROJECT / entry["case"]
            expected_text = render_case(kb_records(entry["width"], entry["ordering"], config["shuffle_seed"]), limits)
            if sha(fixture.read_bytes()) != entry["sha256"] or fixture.read_text() != expected_text:
                raise ValueError(f"Input mismatch: {fixture}")
        for entry in entries:
            fixture = PROJECT / entry["case"]
            folder = output / fixture.stem
            folder.mkdir()
            result = {"case": entry["case"], "fixture_sha256": entry["sha256"],
                      "width": entry["width"], "ordering": entry["ordering"],
                      "runs": {}, "passed": False}
            try:
                case = read_case(fixture.read_text())
                logs = {}
                for name, library_path in (("native", None), ("traced", library)):
                    print(f"Running {fixture.stem}: {name}", flush=True)
                    run = runtime.run(fixture, preload_pln=True, library_path=library_path)
                    for stream in ("stdout", "stderr"):
                        (folder / f"{name}.{stream}.txt").write_text(run[stream])
                    logs[name] = run["stdout"]
                    result["runs"][name] = {k: v for k, v in run.items() if k not in ("stdout", "stderr")}
                    result["runs"][name]["clean_completion"] = clean_completion(run)
                    result["runs"][name]["stdout_sha256"] = sha(run["stdout"].encode())
                if not all(r["clean_completion"] for r in result["runs"].values()):
                    result["status"] = "execution_failed_or_wall_timeout"
                    raise RuntimeError("One or both executions did not complete cleanly; raw logs retained")
                answer = parse_result(logs["native"], case)
                result["answer"] = answer
                result["parity"] = observable_parity(logs["native"], logs["traced"])
                result["parity"]["answer_unchanged"] = answer == parse_result(logs["traced"], case)
                if not (result["parity"]["all_original_output_unchanged"] and result["parity"]["answer_unchanged"]):
                    result["status"] = "observable_parity_failed"
                    raise ValueError("Tracing changed original output")
                if answer is None:
                    result["status"] = "no_returned_answer_within_limits"
                else:
                    cert, counts = extract_certificate(logs["traced"], case, answer, source_hash, entry["sha256"])
                    cert["origin"] = "captured_native_execution_with_print_only_tracing"
                    save(folder / "certificate.json", cert)
                    replayed = replay(cert, case, source_hash, entry["sha256"])
                    save(folder / "replay.json", replayed)
                    result["trace_events"] = counts
                    result["proof_nodes"] = replayed["nodes"]
                    result["proof_rules"] = dict(Counter(s["rule"] for s in replayed["steps"]))
                    result["passed"] = qualifies(replayed, config["success"])
                    result["status"] = "verified_returned_answer" if result["passed"] else "valid_proof_below_acceptance_threshold"
            except Exception as exc:
                result.setdefault("status", "validation_failed")
                result["error"] = f"{type(exc).__name__}: {exc}"
            save(folder / "report.json", result)
            report["cases"].append(result)
            save(output / "report.json", report)
            print(f"{fixture.stem}: {result['status']}", flush=True)
        report["provenance_after"] = runtime.verify()
        report["external_sources_unchanged"] = report["provenance_before"] == report["provenance_after"]
        report["passed"] = report["external_sources_unchanged"] and all(c["passed"] for c in report["cases"])
        report["verified_cases"] = sum(c["passed"] for c in report["cases"])
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    save(output / "report.json", report)
    print(json.dumps({"passed": report["passed"], "verified_cases": report.get("verified_cases"),
                      "error": report.get("error"), "report": str(output / "report.json")}, indent=2), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
