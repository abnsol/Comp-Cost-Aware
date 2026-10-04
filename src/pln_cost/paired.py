"""Restored-state repeated measurement and process-block analysis."""
import math
import random
import statistics

from .expansion import marked
from .qualification import expression
from .sexpr import read_one


def balanced_orders(count, seed):
    if count < 2 or count % 2:
        raise ValueError("An even positive pair count is required")
    orders = [["A", "B"] for _ in range(count // 2)] + [["B", "A"] for _ in range(count // 2)]
    random.Random(seed).shuffle(orders)
    return orders


WRAPPER = """
(= (Bench.Clock) (py-call (time.process_time_ns)))
; Recursive calls use the ORIGINAL inputs, never the preceding output queues.
(= (Bench.Batch $k $mode $tasks $beliefs $selected $tq $bq $expected)
   (if (== $k 0) ()
     (let* (($out (if (== $mode Empty) $expected
                       (Cost.Expand $tasks $beliefs $selected $tq $bq)))
            ($rest (Bench.Batch (- $k 1) $mode $tasks $beliefs $selected $tq $bq $expected)))
       (append ($out) $rest))))
(= (Bench.Check $outputs $expected)
   (if (== $outputs ()) True
     (if (== (car-atom $outputs) $expected)
         (Bench.Check (cdr-atom $outputs) $expected) False)))
(= (Bench.One $phase $pair $route $k $mode)
   (let* (($r0 (Bench.Clock))
          ($tasks (Bench.Tasks)) ($beliefs (Bench.Beliefs))
          ($selected (Bench.Candidate $route)) ($expected (Bench.Expected $route))
          ($tq (Bench.TaskLimit)) ($bq (Bench.BeliefLimit))
          ($r1 (Bench.Clock))
          ($outputs (Bench.Batch $k $mode $tasks $beliefs $selected $tq $bq $expected))
          ($end (Bench.Clock))
          ($ok (Bench.Check $outputs $expected)))
     (println! (PAIRED_SAMPLE $phase $pair $route $k (- $r1 $r0) (- $end $r1) $ok))))
"""


def fixture(helper, state, candidates, expected, k, orders, protocol, seed):
    definitions = [("Bench.Tasks", state["tasks"]), ("Bench.Beliefs", state["beliefs"]),
                   ("Bench.TaskLimit", state["task_limit"]), ("Bench.BeliefLimit", state["belief_limit"])]
    text = helper + WRAPPER
    for name, value in definitions:
        text += f"\n(= ({name}) {expression(value)})\n"
    for route in ("A", "B"):
        text += f"(= (Bench.Candidate {route}) {expression(candidates[route])})\n"
        text += f"(= (Bench.Expected {route}) {expression(expected[route])})\n"
    text += "!(Bench.Clock)\n"
    text += "!(println! (PAIRED_CLOCK (py-call (platform.python_version)) (py-call (getattr (py-call (time.get_clock_info process_time)) resolution)) (py-call (getattr (py-call (time.get_clock_info process_time)) monotonic))))\n"
    schedule = []
    for phase, phase_orders in (("Warmup", balanced_orders(protocol["warmup_pairs"], seed + 1)), ("Measured", orders)):
        for pair, order in enumerate(phase_orders):
            for route in order:
                text += f"!(Bench.One {phase} {pair} {route} {k} Real)\n"
                schedule.append([phase, pair, route, k])
    empty_count = protocol.get("empty_count", protocol["empty_batches_per_block"])
    for i in range(empty_count):
        route = "A" if i % 2 == 0 else "B"
        text += f"!(Bench.One Empty {i} {route} {k} Empty)\n"
        schedule.append(["Empty", i, route, k])
    return text, schedule


def parse(log, schedule):
    rows = [read_one(l)[1:] for l in log.splitlines() if l.startswith("(PAIRED_SAMPLE ")]
    if [r[:4] for r in rows] != schedule:
        raise ValueError("Missing, duplicate or reordered paired samples")
    for row in rows:
        if (len(row) != 7 or any(type(v) is not int or v < 0 for v in row[4:6])
                or row[5] == 0 or row[6] != "true"):
            raise ValueError("Invalid clock interval or native-output mismatch")
    info = marked(log, "PAIRED_CLOCK")
    if len(info) != 3 or type(info[1]) not in (int, float) or not 0 < info[1] < 1 or info[2] != "true":
        raise ValueError("Unsupported clock")
    return {"clock": info, "samples": [{"phase": r[0], "pair": r[1], "route": r[2], "k": r[3],
                                          "prepare_cpu_ns": r[4], "batch_cpu_ns": r[5]} for r in rows]}


def quantile(xs, q):
    xs = sorted(xs)
    index = (len(xs)-1) * q
    low = int(index)
    return xs[low] + (xs[min(low+1, len(xs)-1)] - xs[low]) * (index-low)


def summarize_process(parsed):
    samples = parsed["samples"]
    pairs = {}
    for s in samples:
        if s["phase"] == "Measured":
            pair = pairs.setdefault(s["pair"], {"first": s["route"]})
            pair[s["route"]] = s["batch_cpu_ns"] / s["k"]
    data = [{**p, "ratio": p["B"] / p["A"], "difference_ns": p["B"] - p["A"]}
            for p in pairs.values()]
    empty = [s["batch_cpu_ns"] / s["k"] for s in samples if s["phase"] == "Empty"]
    medians = {route: statistics.median(p[route] for p in data) for route in ("A", "B")}
    return {"pairs": data, "median_ratio": statistics.median(p["ratio"] for p in data),
            "median_difference_ns": statistics.median(p["difference_ns"] for p in data),
            "median_cpu_ns": medians, "empty_p95_ns": quantile(empty, .95),
            "empty_median_ns": statistics.median(empty),
            "empty_p95_fraction": quantile(empty, .95) / min(medians.values()),
            "early_late_ratio": {route: statistics.median(p[route] for p in data[len(data)//2:]) /
                                 statistics.median(p[route] for p in data[:len(data)//2]) for route in ("A", "B")},
            "median_prepare_cpu_ns": statistics.median(s["prepare_cpu_ns"] for s in samples if s["phase"] == "Measured")}


def sign_p(differences):
    positive = sum(d > 0 for d in differences)
    negative = sum(d < 0 for d in differences)
    n = positive + negative
    return min(1, 2 * sum(math.comb(n, i) for i in range(min(positive, negative)+1)) / 2**n)


def analyze(blocks, protocol, absolute_floor_ns, seed):
    if len(blocks) != protocol["blocks"]:
        raise ValueError("Incomplete block set")
    ratios = [b["median_ratio"] for b in blocks]
    differences = [b["median_difference_ns"] for b in blocks]
    rng = random.Random(seed)
    bootstrap_r, bootstrap_d = [], []
    for _ in range(protocol["bootstrap_resamples"]):
        indices = rng.choices(range(len(blocks)), k=len(blocks))
        bootstrap_r.append(statistics.median(ratios[i] for i in indices))
        bootstrap_d.append(statistics.median(differences[i] for i in indices))
    ratio_ci = [quantile(bootstrap_r, .025), quantile(bootstrap_r, .975)]
    difference_ci = [quantile(bootstrap_d, .025), quantile(bootstrap_d, .975)]
    order_ratios = {first: statistics.median(p["ratio"] for b in blocks for p in b["pairs"] if p["first"] == first)
                    for first in ("A", "B")}
    p_value = sign_p(differences)
    adequate = all(b["empty_p95_fraction"] <= protocol["maximum_block_empty_p95_fraction"] for b in blocks)
    margin = protocol["practical_ratio"]
    significant = p_value <= protocol["family_sign_alpha"] / protocol["number_of_state_comparisons"]
    if not adequate:
        verdict = "instrumentation_adequacy_unresolved"
    elif (significant and ratio_ci[0] > margin and difference_ci[0] > absolute_floor_ns
          and min(order_ratios.values()) > margin):
        verdict = "B_reproducibly_costlier"
    elif (significant and ratio_ci[1] < 1/margin and difference_ci[1] < -absolute_floor_ns
          and max(order_ratios.values()) < 1/margin):
        verdict = "A_reproducibly_costlier"
    elif ratio_ci[0] >= 1/margin and ratio_ci[1] <= margin:
        verdict = "within_relative_equivalence_band"
    else:
        verdict = "inconclusive"
    return {"verdict": verdict, "median_ratio_B_over_A": statistics.median(ratios),
            "ratio_ci95": ratio_ci, "median_difference_ns": statistics.median(differences),
            "difference_ci95_ns": difference_ci, "two_sided_sign_p": p_value,
            "bonferroni_threshold": protocol["family_sign_alpha"] / protocol["number_of_state_comparisons"],
            "pair_order_median_ratios": order_ratios, "instrumentation_adequate": adequate,
            "maximum_empty_p95_fraction": max(b["empty_p95_fraction"] for b in blocks),
            "positive_blocks": sum(d > 0 for d in differences), "negative_blocks": sum(d < 0 for d in differences),
            "absolute_practical_floor_ns": absolute_floor_ns,
            "median_cpu_ns": {route: statistics.median(b["median_cpu_ns"][route] for b in blocks) for route in ("A", "B")}}
