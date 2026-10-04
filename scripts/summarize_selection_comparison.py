#!/usr/bin/env python3
"""Verify complete Step 5 coverage and summarize saved runs; no native execution."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.comparison import summarize


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("batch", type=Path)
    args = ap.parse_args()
    p = args.batch
    report = json.loads((p / "report.json").read_text())
    protocol = json.loads((p / "protocol.json").read_text())
    jobs = json.loads((p / "schedule.json").read_text())
    runs = [json.loads(line) for line in (p / "runs.jsonl").read_text().splitlines()]
    if not report["passed"] or not report["completed"] or report["errors"]:
        raise ValueError("Require completed, validated batch; failures cannot be hidden")
    if not len(runs) == len(jobs) == report["completed_runs"] == report["planned_runs"]:
        raise ValueError("Incomplete scheduled coverage")
    if any({k: row[k] for k in job} != job for row, job in zip(runs, jobs, strict=True)):
        raise ValueError("Measurements differ from frozen schedule")
    if summarize(runs) != json.loads((p / "summary.json").read_text()):
        raise ValueError("Stored per-case summary differs from raw measurements")
    groups = Counter((r["case"], r["budget_ns"], r["mode"]) for r in runs)
    if set(groups.values()) != {protocol["repetitions"]}:
        raise ValueError("Missing or duplicated repetitions")
    arms = protocol["policies"]
    answer = {"coverage_verified": True, "runs": len(runs), "budget_table": [],
              "generous_cases": [], "arm_diagnostics": []}
    answer["analysis_code_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    answer["input_sha256"] = {f: hashlib.sha256((p / f).read_bytes()).hexdigest()
        for f in ("runs.jsonl", "summary.json", "schedule.json", "protocol.json", "report.json")}
    for split in ("development", "evaluation"):
        for budget in sorted({r["budget_ns"] for r in runs}):
            row = {"split": split, "budget_ns": budget, "arms": {}}
            for mode in arms:
                xs = [r for r in runs if (r["split"], r["budget_ns"], r["mode"]) == (split, budget, mode)]
                row["arms"][mode] = {"on_time": sum(r["result"]["verified_success"] for r in xs), "total": len(xs)}
            answer["budget_table"].append(row)
    for case in sorted({r["case"] for r in runs}):
        xs = {m: sorted([r for r in runs if r["case"] == case and r["mode"] == m and r["endpoint"] == "generous"],
                       key=lambda r: r["repetition"]) for m in arms}
        row = {"case": case, "split": xs["N"][0]["split"], "arms": {}, "paired": {}}
        for mode, rs in xs.items():
            good = [r for r in rs if r["result"]["verified_success"]]
            row["arms"][mode] = {
                "on_time": len(good), "total": len(rs),
                "median_actual_cpu_ns": statistics.median(r["result"]["engine_cpu_ns"] for r in rs),
                "median_success_cpu_ns": statistics.median(r["result"]["engine_cpu_ns"] for r in good) if good else None,
                "expansions": sorted({r["result"]["completed_expansions"] for r in rs})}
        for top, bottom in (("O", "N"), ("C", "N"), ("C", "O")):
            ratios = [a["result"]["engine_cpu_ns"] / b["result"]["engine_cpu_ns"]
                      for a, b in zip(xs[top], xs[bottom], strict=True)
                      if a["result"]["verified_success"] and b["result"]["verified_success"]]
            row["paired"][f"{top}/{bottom}"] = {
                "both_successful_pairs": len(ratios), "ratios": ratios,
                "median_ratio": statistics.median(ratios) if ratios else None,
                "faster_pairs": sum(r < 1 for r in ratios)}
        answer["generous_cases"].append(row)
    for mode in arms:
        xs = [r for r in runs if r["mode"] == mode]
        gs = [r for r in xs if r["endpoint"] == "generous"]
        answer["arm_diagnostics"].append({
            "mode": mode, "statuses": dict(Counter(r["result"]["status"] for r in xs)),
            "maximum_overshoot_ns": max(r["result"]["overshoot_ns"] for r in xs),
            "fallbacks": sum(r["selector_stats"][4] for r in xs),
            "generous_median_selection_fraction": statistics.median(r["selector_stats"][3]/r["result"]["engine_cpu_ns"] for r in gs),
            "generous_median_feature_fraction": statistics.median(r["selector_stats"][2]/r["result"]["engine_cpu_ns"] for r in gs)})
    # Pair successes by case, budget and repetition, retaining all misses.
    pairs = {}
    for r in runs:
        if r["endpoint"] == "budget":
            pairs.setdefault((r["case"], r["budget_ns"], r["repetition"]), {})[r["mode"]] = r["result"]["verified_success"]
    answer["budget_paired_N_C"] = {
        "both_success": sum(v["N"] and v["C"] for v in pairs.values()),
        "neither_success": sum(not v["N"] and not v["C"] for v in pairs.values()),
        "C_only_success": sum(v["C"] and not v["N"] for v in pairs.values()),
        "N_only_success": sum(v["N"] and not v["C"] for v in pairs.values())}
    (p / "analysis.json").write_text(json.dumps(answer, indent=2) + "\n")
    print(json.dumps({"coverage_verified": True, "runs": len(runs),
                      "analysis": str(p / "analysis.json"), "paired_budget_outcomes": answer["budget_paired_N_C"]}, indent=2))


if __name__ == "__main__":
    main()
