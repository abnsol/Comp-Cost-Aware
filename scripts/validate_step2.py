#!/usr/bin/env python3
"""Capture and independently replay the proof of the machine example's answer."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.proof import SOURCE_COMMIT, extract_certificate, replay
from pln_cost.runtime import Runtime
from pln_cost.sexpr import read_case
from pln_cost.tracing import instrument
from pln_cost.validation import clean_completion, parse_answer


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum():
        parser.error("Simple alphanumeric run ID with optional '-'/'_' required")
    output = PROJECT / "results/step-02" / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    report = {"purpose": "returned-answer derivation audit; no performance claims", "checks": {}, "runs": {}}
    try:
        runtime = Runtime(PROJECT, PROJECT / "configs/runtime.json")
        report["provenance_before"] = runtime.verify()
        if report["provenance_before"]["pln"]["commit"] != SOURCE_COMMIT:
            raise RuntimeError("Replay formulas have not been audited against this PLN commit")
        fixture = PROJECT / "cases/machine_failure.metta"
        case = read_case(fixture.read_text())
        source = (runtime.pln / "lib_pln.metta").read_text()
        source_hash, fixture_hash = sha(source.encode()), sha(fixture.read_bytes())
        generated, patch = instrument(source)
        library = output / "lib_pln.traced.metta"
        library.write_text(generated)
        (output / "PLN-LICENSE.txt").write_text((runtime.pln / "LICENSE").read_text())
        (output / "instrumentation.diff").write_text(patch)
        report["hashes"] = {"native_library": source_hash, "traced_library": sha(generated.encode()), "fixture": fixture_hash}
        report["project_source_sha256"] = {
            str(p.relative_to(PROJECT)): sha(p.read_bytes())
            for folder in ("src", "scripts", "cases", "configs", "tests")
            for p in sorted((PROJECT / folder).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}

        def execute(name, library_path=None):
            run = runtime.run(fixture, preload_pln=True, library_path=library_path)
            for stream in ("stdout", "stderr"):
                (output / f"{name}.{stream}.txt").write_text(run[stream])
            report["runs"][name] = {k: v for k, v in run.items() if k not in ("stdout", "stderr")}
            if not clean_completion(run):
                raise RuntimeError(f"{name} failed; retained raw output")
            return run["stdout"]

        native_log, traced_log = execute("native"), execute("traced", library)
        answer = parse_answer(native_log)
        report["checks"]["answer_unchanged"] = answer == parse_answer(traced_log)
        # All old output (including every SELECTED record) must match in order.
        filtered = [line for line in traced_log.splitlines() if not line.startswith(("(STEP2_BINARY", "(STEP2_UNARY"))]
        report["checks"]["all_original_output_unchanged"] = native_log.splitlines() == filtered
        if not all(report["checks"].values()):
            raise RuntimeError("Instrumentation changed native behaviour on this case")
        certificate, counts = extract_certificate(traced_log, case, answer, source_hash, fixture_hash)
        (output / "certificate.json").write_text(json.dumps(certificate, indent=2) + "\n")
        replayed = replay(certificate, case, source_hash, fixture_hash)
        (output / "replay.json").write_text(json.dumps(replayed, indent=2) + "\n")
        report["trace_events"] = counts
        report["proof_nodes"] = replayed["nodes"]
        report["answer"] = answer
        report["checks"]["returned_answer_proof_replayed"] = replayed["valid"]
        report["provenance_after"] = runtime.verify()
        report["checks"]["external_sources_unchanged"] = report["provenance_before"] == report["provenance_after"]
        report["passed"] = all(report["checks"].values())
    except Exception as exc:
        report["passed"] = False
        report["error"] = f"{type(exc).__name__}: {exc}"
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "answer": report.get("answer"),
                      "proof_nodes": report.get("proof_nodes"), "error": report.get("error"),
                      "report": str(output / "report.json")}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
