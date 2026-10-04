#!/usr/bin/env python3
"""Generate qualification cases and replay authored proofs; do not run inference."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.proof import SOURCE_COMMIT, replay
from pln_cost.qualification import kb_records, qualifies, render_case, static_witness, validate_config
from pln_cost.runtime import Runtime
from pln_cost.sexpr import read_case


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum():
        parser.error("Simple alphanumeric run ID with optional '-'/'_' required")
    cases_dir = PROJECT / "cases/qualification" / args.run_id
    output = PROJECT / "results/qualification/step-02" / args.run_id
    if cases_dir.exists() or output.exists():
        parser.error("Run ID already exists; no artifacts overwritten")
    config_path = PROJECT / "configs/qualification-kb.json"
    config = json.loads(config_path.read_text())
    validate_config(config)
    output.mkdir(parents=True, exist_ok=False)
    cases_dir.mkdir(parents=True, exist_ok=False)
    report = {"purpose": "static KB and proof validation only", "native_inference_executed": False,
              "cost_gap_measured": False, "cases": [], "passed": False}
    try:
        runtime = Runtime(PROJECT, PROJECT / "configs/runtime.json")
        # Read-only source checks and --version only: Runtime.run is never called.
        report["source_provenance"] = runtime.verify()
        if report["source_provenance"]["pln"]["commit"] != SOURCE_COMMIT:
            raise ValueError("Checker has not been audited against this PLN revision")
        source_hash = sha((runtime.pln / "lib_pln.metta").read_bytes())
        report["native_library_sha256"] = source_hash
        save(output / "config.json", config)
        report["project_source_sha256"] = {
            str(p.relative_to(PROJECT)): sha(p.read_bytes())
            for folder in ("src", "scripts", "configs", "tests")
            for p in sorted((PROJECT / folder).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}
        certificates = {}
        for width in config["development_widths"]:
            for ordering in config["input_orderings"]:
                name = f"n{width:03d}-{ordering}"
                records = kb_records(width, ordering, config["shuffle_seed"])
                fixture = cases_dir / f"{name}.metta"
                fixture.write_text(render_case(records, config["initial_correctness_limits"]))
                case = read_case(fixture.read_text())
                if case != {"inputs": records, "marginals": {}, "query": config["query"]}:
                    raise ValueError("Generated fixture did not round-trip")
                fixture_hash = sha(fixture.read_bytes())
                routes = {"a": [1, 3, 4]}
                routes.update({f"b_{i:03d}": [2, 2*i + 3, 2*i + 4] for i in range(1, width + 1)})
                entry = {"case": str(fixture.relative_to(PROJECT)), "sha256": fixture_hash,
                         "width": width, "ordering": ordering, "input_records": len(records),
                         "static_proofs": {}}
                certificates[name] = {}
                for route, ids in routes.items():
                    cert = static_witness(case, ids, source_hash, fixture_hash)
                    result = replay(cert, case, source_hash, fixture_hash)
                    if not qualifies(result, config["success"]):
                        raise ValueError("Static proof does not meet numerical acceptance contract")
                    certificates[name][route] = cert
                    entry["static_proofs"][route] = {"valid": True, "nodes": result["nodes"],
                                                     "answer": result["answer"]}
                report["cases"].append(entry)
        save(output / "static-witnesses.json", certificates)
        report["static_witnesses_sha256"] = sha((output / "static-witnesses.json").read_bytes())
        report["static_proofs_checked"] = sum(len(c["static_proofs"]) for c in report["cases"])
        report["passed"] = True
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    save(output / "report.json", report)
    print(json.dumps({"passed": report["passed"], "cases": len(report["cases"]),
                      "static_proofs_checked": report.get("static_proofs_checked"),
                      "native_inference_executed": False, "error": report.get("error"),
                      "report": str(output / "report.json")}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
