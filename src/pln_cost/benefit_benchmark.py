"""Four-arm schedule, accounting checks and failure-preserving summaries."""
from collections import Counter, defaultdict
import random
import statistics

from .benefit_selection import MODES, choose


def schedule(cases, protocol):
    arms, repetitions = protocol["policies"], protocol["repetitions"]
    orders = protocol["balanced_arm_orders"]
    if arms != list(MODES) or repetitions != 12 or len(orders) != 4:
        raise ValueError("Expected reviewed four-arm protocol")
    if any(sorted(o) != sorted(arms) for o in orders):
        raise ValueError("Each order must contain each arm exactly once")
    if any(Counter(o[i] for o in orders) != Counter(arms) for i in range(4)):
        raise ValueError("Unbalanced positions")
    pairs = Counter(p for o in orders for p in zip(o, o[1:]))
    if len(pairs) != 12 or set(pairs.values()) != {1}:
        raise ValueError("Unbalanced within-block adjacency")
    if len({c["name"] for c in cases}) != len(cases):
        raise ValueError("Duplicate case name")
    budgets = protocol["budgets_ns"] + [protocol["generous_budget_ns"]]
    if len(set(budgets)) != len(budgets) or any(type(b) is not int or b <= 0 for b in budgets):
        raise ValueError("Invalid/duplicate budgets")
    assigned = {}
    for i, case in enumerate(cases):
        for j, budget in enumerate(budgets):
            choices = orders * 3
            random.Random(protocol["seed"] + 1000*i+j).shuffle(choices)
            assigned[(i, budget)] = choices
    jobs = []
    for rep in range(repetitions):
        blocks = [(i, b) for i in range(len(cases)) for b in budgets]
        random.Random(protocol["seed"] + rep).shuffle(blocks)
        for i, budget in blocks:
            for mode in assigned[(i, budget)][rep]:
                jobs.append(dict(id=len(jobs), case=cases[i]["name"], split=cases[i]["split"],
                    mode=mode, budget_ns=budget, repetition=rep,
                    endpoint="generous" if budget == protocol["generous_budget_ns"] else "budget"))
    return jobs


def expected_counters(states, model, mode, query):
    """Offline prefix counters; never passed to online selection."""
    totals = [0]*6
    prefixes = [totals[:]]
    for snapshot in states[:-1]:
        _, meta = choose(snapshot["state"], model, mode, query=query, marginals={})
        increment = [1, meta["classified"], len(meta["predictions"]),
                     int(meta["coverage_fallback"]), int(meta["prediction_fallback"]), int(meta["singleton"])]
        totals = [a+b for a,b in zip(totals, increment, strict=True)]
        prefixes.append(totals[:])
    return prefixes


def check_stats(stats, metrics, prefixes):
    if len(stats) != 9 or any(type(v) is not int or v < 0 for v in stats):
        raise ValueError("Malformed selector telemetry")
    done = metrics["completed_expansions"]
    if done >= len(prefixes) or [stats[i] for i in (0,1,3,6,7,8)] != prefixes[done]:
        raise ValueError("Selector counters differ from audited prefix")
    if not 0 <= stats[2]+stats[4] <= stats[5] <= metrics["engine_cpu_ns"]:
        raise ValueError("Invalid nested CPU windows")


def coverage(jobs, runs, complete=False):
    if len(runs) > len(jobs) or (complete and len(runs) != len(jobs)):
        raise ValueError("Incorrect run coverage")
    for job, row in zip(jobs, runs):
        if any(row.get(k) != v for k,v in job.items()):
            raise ValueError("Results are not the exact scheduled prefix")
        if ("result" in row) == ("error" in row):
            raise ValueError("Need exactly one valid result or execution error")
    return len(runs) == len(jobs)


def summarize(jobs, runs, comparisons=(("BC", "B"),)):
    coverage(jobs, runs)
    by_id = {r["id"]: r for r in runs}
    groups = defaultdict(list)
    # Explicit missing slots ensure partial batches retain planned denominators.
    for j in jobs:
        groups[(j["split"], j["case"], j["endpoint"], j["budget_ns"], j["mode"])].append(by_id.get(j["id"]))
    summaries = []
    for (split, case, endpoint, budget, mode), slots in sorted(groups.items()):
        observed = [r for r in slots if r is not None]
        valid = [r["result"] for r in observed if "result" in r]
        success = [r for r in valid if r["verified_success"]]
        summaries.append(dict(split=split, case=case, endpoint=endpoint, budget_ns=budget, mode=mode,
            planned=len(slots), executed=len(observed), missing=len(slots)-len(observed),
            invalid=len(observed)-len(valid), verified_successes=len(success),
            statuses=dict(Counter(r["status"] for r in valid)),
            median_success_cpu_ns=statistics.median(r["engine_cpu_ns"] for r in success) if success else None,
            maximum_overshoot_ns=max((r["overshoot_ns"] for r in valid), default=None)))
    blocks = defaultdict(dict)
    for j in jobs:
        blocks[(j["split"], j["case"], j["endpoint"], j["budget_ns"], j["repetition"])][j["mode"]] = by_id.get(j["id"])
    pairs = []
    for left, right in comparisons:
        aggregates = defaultdict(lambda: {"outcomes": Counter(), "ratios": []})
        for (split, case, endpoint, budget, rep), rows in blocks.items():
            a,b = rows[left],rows[right]
            group = aggregates[(split,case,endpoint,budget)]
            if a is None or b is None:
                label = "missing_pair"
            elif "error" in a or "error" in b:
                label = "invalid_pair"
            else:
                av,bv = a["result"]["verified_success"],b["result"]["verified_success"]
                label = "both" if av and bv else "left_only" if av else "right_only" if bv else "neither"
                if av and bv:
                    group["ratios"].append(a["result"]["engine_cpu_ns"]/b["result"]["engine_cpu_ns"])
            group["outcomes"][label] += 1
        for (split,case,endpoint,budget), g in sorted(aggregates.items()):
            ratios = g["ratios"]
            pairs.append(dict(left=left, right=right, split=split, case=case, endpoint=endpoint, budget_ns=budget,
                planned_pairs=sum(g["outcomes"].values()), outcomes=dict(g["outcomes"]),
                both_success_cpu_ratios=ratios,
                median_both_success_cpu_ratio=statistics.median(ratios) if ratios else None,
                ratio_quartiles=statistics.quantiles(ratios,n=4,method="inclusive") if len(ratios)>1 else None,
                latency_subset_complete=g["outcomes"].get("both",0)==sum(g["outcomes"].values())))
    split_totals = {}
    for row in summaries:
        k = (row['split'], row['endpoint'], row['budget_ns'], row['mode'])
        aggregate = split_totals.setdefault(k, dict(split=k[0], endpoint=k[1], budget_ns=k[2], mode=k[3],
            planned=0, executed=0, missing=0, invalid=0, verified_successes=0, statuses=Counter()))
        for field in ('planned','executed','missing','invalid','verified_successes'):
            aggregate[field] += row[field]
        aggregate['statuses'].update(row['statuses'])
    return dict(completed=len(runs)==len(jobs), planned=len(jobs), executed=len(runs),
                per_case=summaries, split_totals=[split_totals[k] for k in sorted(split_totals)], paired=pairs)
