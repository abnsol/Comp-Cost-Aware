"""Balanced comparison schedule and descriptive, failure-preserving summaries."""
from collections import Counter
from itertools import permutations
import random
import statistics


def schedule(cases, protocol):
    arms = protocol["policies"]
    if arms != ["N", "O", "C"] or protocol["repetitions"] != 12:
        raise ValueError("Expected reviewed three-arm, twelve-repetition protocol")
    budgets = protocol["budgets_ns"] + [protocol["generous_budget_ns"]]
    if len(set(budgets)) != len(budgets):
        raise ValueError("Duplicate budget")
    orders = {}
    for i, case in enumerate(cases):
        for j, budget in enumerate(budgets):
            choices = list(permutations(arms))*2
            random.Random(protocol["seed"] + 1000*i+j).shuffle(choices)
            orders[(case["name"], budget)] = choices
    jobs = []
    for rep in range(protocol["repetitions"]):
        blocks = [(i, b) for i in range(len(cases)) for b in budgets]
        random.Random(protocol["seed"] + rep).shuffle(blocks)
        for i, budget in blocks:
            case = cases[i]
            for mode in orders[(case["name"], budget)][rep]:
                jobs.append({"id": len(jobs), "case": case["name"], "split": case["split"],
                    "mode": mode, "budget_ns": budget, "repetition": rep,
                    "endpoint": "generous" if budget == protocol["generous_budget_ns"] else "budget"})
    return jobs


def summarize(runs):
    groups = {}
    for run in runs:
        groups.setdefault((run["split"], run["case"], run["endpoint"], run["budget_ns"], run["mode"]), []).append(run)
    summaries = []
    for (split, case, endpoint, budget, mode), rows in sorted(groups.items()):
        valid = [r["result"] for r in rows if "result" in r]
        successful = [r for r in valid if r["verified_success"]]
        summaries.append({"split": split, "case": case, "endpoint": endpoint, "budget_ns": budget,
            "mode": mode, "scheduled_runs": len(rows), "valid_runs": len(valid),
            "invalid_runs": len(rows)-len(valid), "verified_successes": len(successful),
            "statuses": dict(Counter(r["status"] for r in valid)),
            "median_actual_cpu_ns": statistics.median(r["engine_cpu_ns"] for r in valid) if valid else None,
            "median_success_cpu_ns": statistics.median(r["engine_cpu_ns"] for r in successful) if successful else None,
            "maximum_overshoot_ns": max((r["overshoot_ns"] for r in valid), default=None)})
    return summaries
