"""Thin direct-compiled-call adapter plus controlled old-harness diagnostics."""
import random

from .paired import WRAPPER, balanced_orders
from .qualification import expression


def definitions(condition):
    state = condition["state"]
    parts = []
    for name, value in (("Bench.Tasks", state["tasks"]), ("Bench.Beliefs", state["beliefs"]),
                        ("Bench.TaskLimit", state["task_limit"]), ("Bench.BeliefLimit", state["belief_limit"])):
        parts.append(f"(= ({name}) {expression(value)})")
    for route in ("A", "B"):
        parts.append(f"(= (Bench.Candidate {route}) {expression(condition['candidates'][route])})")
        parts.append(f"(= (Bench.Expected {route}) {expression(condition['expected'][route])})")
    return "\n".join(parts) + "\n"


THIN_WRAPPER = """
(= (Thin.One $phase $pair $route $mode)
  (let* (($r0 (Bench.Clock))
         ($tasks (Bench.Tasks)) ($beliefs (Bench.Beliefs))
         ($selected (Bench.Candidate $route)) ($expected (Bench.Expected $route))
         ($tq (Bench.TaskLimit)) ($bq (Bench.BeliefLimit))
         ($r1 (Bench.Clock)))
    (thin_sample $phase $pair $route $mode $tasks $beliefs $selected $tq $bq $expected (- $r1 $r0))))
"""


def thin_fixture(helper, condition, protocol, seed, pairs, empty_count):
    text = helper + "\n(= (Bench.Clock) (py-call (time.process_time_ns)))\n" + definitions(condition) + THIN_WRAPPER
    text += "!(Bench.Clock)\n"
    text += "!(println! (PAIRED_CLOCK (py-call (platform.python_version)) (py-call (getattr (py-call (time.get_clock_info process_time)) resolution)) (py-call (getattr (py-call (time.get_clock_info process_time)) monotonic))))\n"
    for route in ("A", "B"):
        text += f"!(thin_verify (Bench.Tasks) (Bench.Beliefs) (Bench.Candidate {route}) (Bench.TaskLimit) (Bench.BeliefLimit) (Bench.Expected {route}))\n"
    for i in range(30):
        text += f"!(thin_probe {i})\n"
    schedule = []
    for phase, count, offset in (("Warmup", protocol["warmup_pairs"], 1), ("Measured", pairs, 0)):
        for pair, order in enumerate(balanced_orders(count, seed + offset)):
            for route in order:
                text += f"!(Thin.One {phase} {pair} {route} Real)\n"
                schedule.append([phase, pair, route, 1])
    for i in range(empty_count):
        route = "A" if i % 2 == 0 else "B"
        text += f"!(Thin.One Empty {i} {route} Empty)\n"
        schedule.append(["Empty", i, route, 1])
    return text, schedule


DIAGNOSTICS = """
; Original empty batch with result-list construction removed. Keep argument list,
; branch and recursive inputs fixed. Output format changes only for diagnostics.
(= (Diag.NoList $k $mode $tasks $beliefs $selected $tq $bq $expected)
  (if (== $k 0) $expected
    (let* (($out (if (== $mode Empty) $expected
                    (Cost.Expand $tasks $beliefs $selected $tq $bq)))
           ($rest (Diag.NoList (- $k 1) $mode $tasks $beliefs $selected $tq $bq $expected)))
      $rest)))
; Same empty recursion and append, fewer carried arguments (no inference allowed).
(= (Diag.Small $k $mode $expected)
  (if (== $k 0) ()
    (let* (($out (if (== $mode Empty) $expected (empty)))
           ($rest (Diag.Small (- $k 1) $mode $expected)))
      (append ($out) $rest))))
(= (Diag.One $phase $i $kind $k)
  (let* (($tasks (Bench.Tasks)) ($beliefs (Bench.Beliefs))
         ($selected (Bench.Candidate A)) ($expected (Bench.Expected A))
         ($tq (Bench.TaskLimit)) ($bq (Bench.BeliefLimit))
         ($start (Bench.Clock))
         ($out (case $kind
            ((Clock $expected)
             (Lookup ((Bench.Tasks) (Bench.Beliefs) (Bench.Candidate A) (Bench.Expected A)))
             (Full (Bench.Batch $k Empty $tasks $beliefs $selected $tq $bq $expected))
             (NoList (Diag.NoList $k Empty $tasks $beliefs $selected $tq $bq $expected))
             (Small (Diag.Small $k Empty $expected)))))
         ($end (Bench.Clock)))
    (println! (HARNESS_DIAG $phase $i $kind $k (- $end $start)))))
"""


def diagnostic_fixture(helper, condition, seed):
    text = helper + WRAPPER + definitions(condition) + DIAGNOSTICS + "\n!(Bench.Clock)\n"
    rng = random.Random(seed)
    schedule = []
    # Fixed repetitions and random ordering; no conditional extension after data.
    modes = [("Clock", 1), ("Lookup", 1)] + [(name, k) for k in (1, 8, 32) for name in ("Full", "NoList", "Small")]
    for phase, count in (("Warmup", 10), ("Measured", 30)):
        for i in range(count):
            order = list(modes)
            rng.shuffle(order)
            for name, k in order:
                text += f"!(Diag.One {phase} {i} {name} {k})\n"
                schedule.append([phase, i, name, k])
    return text, schedule
