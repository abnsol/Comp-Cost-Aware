#!/usr/bin/env python3
"""Run native regression, load-path parity and the authored small example.

Example: python3 scripts/validate_step1.py --run-id run001
Uses only the standard library plus the existing external PeTTa/PLN runtime.
Every run preserves stdout/stderr and a manifest in a new results directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.runtime import Runtime
from pln_cost.validation import clean_completion, parse_answer
from pln_cost.world import reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum():
        parser.error("Use a simple alphanumeric run ID with optional '-'/'_'")
    output = PROJECT / "results/step-01" / args.run_id
    output.mkdir(parents=True, exist_ok=False)  # Never overwrite prior evidence.
    report = {"purpose": "correctness/interface check, not a benchmark",
              "python": platform.python_version(), "checks": {}, "runs": {},
              "independent_proof_replay": "not implemented in step one"}
    try:
        runtime = Runtime(PROJECT, PROJECT / "configs/runtime.json")
        report["provenance_before"] = runtime.verify()
        report["source_sha256"] = {
            str(p.relative_to(PROJECT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("src", "scripts", "cases", "configs")
            for p in sorted((PROJECT / folder).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts
        }

        def execute(name, fixture, preload=False):
            run = runtime.run(fixture, preload_pln=preload)
            for stream in ("stdout", "stderr"):
                (output / f"{name}.{stream}.txt").write_text(run[stream])
            report["runs"][name] = {k: v for k, v in run.items() if k not in ("stdout", "stderr")}
            report["checks"][name + "_completed_cleanly"] = clean_completion(run)
            if not clean_completion(run):
                raise RuntimeError(f"{name} failed; inspect its retained stdout/stderr")
            return run["stdout"]

        # First run the upstream example unchanged with its own assertion.
        native = runtime.pln / "examples/DeductionRevision.metta"
        text = execute("native-example", native)
        report["checks"]["native_declared_assertion"] = text.count("✅") == 1
        if not report["checks"]["native_declared_assertion"]:
            raise RuntimeError("Native example did not produce its single passing assertion")

        # Parity check for our offline preload path: retain the native KB unchanged,
        # replace only imports and the final assertion with a marked query.
        source = native.read_text()
        body = source[source.index("(= (STV A)"):source.index("!(test")]
        parity_fixture = output / "native-parity.metta"
        parity_fixture.write_text(body +
            "!(println! (STEP1_RESULT (PLN.Query (kb) (Inheritance A D) 100 30 100)))\n")
        parity = parse_answer(execute("native-parity", parity_fixture, True))
        report["native_parity_answer"] = parity
        report["checks"]["preload_matches_native_expected"] = (
            abs(parity["strength"] - 0.125) < 1e-12
            and abs(parity["confidence"] - 0.30429942952553224) < 1e-12
            and parity["evidence"] == [1, 2, 3, 4])
        if not report["checks"]["preload_matches_native_expected"]:
            raise RuntimeError("Preload result differs from the native expected result")

        answer = parse_answer(execute("machine-failure", PROJECT / "cases/machine_failure.metta", True))
        report["machine_answer"] = answer
        # Only the offline evaluator sees world truth. It is never passed to PLN.
        report["world_reference"] = reference()
        report["squared_probability_error"] = (answer["strength"] - reference()["target_probability"])**2
        report["provenance_after"] = runtime.verify()
        report["checks"]["external_repositories_unchanged"] = report["provenance_before"] == report["provenance_after"]
        report["passed"] = all(report["checks"].values())
    except Exception as exc:
        report["passed"] = False
        report["error"] = f"{type(exc).__name__}: {exc}"
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "report": str(output / "report.json"),
                      "answer": report.get("machine_answer"), "error": report.get("error")}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
