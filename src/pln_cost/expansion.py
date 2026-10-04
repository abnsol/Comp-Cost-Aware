"""Native single-expansion extraction, diagnostic counters and boundary clocks.

PLN still supplies all rules, evidence guards and queue operations. Detailed
printing is confined to a separate audit variant, never the timing-only variant.
"""
import math

from .proof import sentence
from .qualification import expression
from .sexpr import read_one


def balanced_at(text, start):
    depth = 0
    for i in range(start, len(text)):
        depth += (text[i] == "(") - (text[i] == ")")
        if depth == 0:
            return text[start:i+1]
    raise ValueError("Unbalanced native expression")


def one_expression(source, prefix):
    if source.count(prefix) != 1:
        raise ValueError(f"Expected exactly one native expression: {prefix}")
    return balanced_at(source, source.index(prefix))


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"Unexpected native layout: {old}")
    return source.replace(old, new, 1)


def build_expansion(source, audit=False):
    """Extract native collapse and both queue updates verbatim. No rule rewrite.

    The helper takes a chosen pending Sentence, returns updated Tasks/Beliefs plus
    raw derivations, and does not recurse. Native SELECTED console logging is
    omitted from this diagnostic operation; selected-record output follows timing.
    """
    loop = one_expression(source, "(= (PLN.Derive $Tasks $Beliefs $steps $maxsteps")
    derivations = one_expression(loop, "(collapse (superpose")
    tasks = one_expression(loop, "(LimitSize (exclude-item")
    beliefs = one_expression(loop, "(LimitSize (ConcatUnique $Beliefs")
    if audit:
        derivations = replace_once(derivations, "(StampDisjoint $Ev1 $Ev2)",
            "(let $Allowed (StampDisjoint $Ev1 $Ev2) (progn (println! (COST_GUARD $Allowed)) $Allowed))")
        for rule, label in (("(|- $x $y)", "forward"), ("(|- $y $x)", "backward"), ("(|- $x)", "unary")):
            derivations = replace_once(derivations, rule, f"(progn (println! (COST_ATTEMPT {label})) {rule})")
        for output, label in (("(Sentence ($Txy $TVxy) $stamp)", "binary"),
                              ("(Sentence ($Tyx $TVyx) $stamp)", "binary"),
                              ("(Sentence ($T3 $TV3) $Ev1)", "unary")):
            derivations = replace_once(derivations, output,
                f"(progn (println! (COST_GENERATED {label} {output})) {output})")
    return ("; Mechanically extracted from the pinned native PLN.Derive.\n"
        "(= (Cost.Expand $Tasks $Beliefs $Selected $taskqueuesize $beliefqueuesize)\n"
        "   (let (Sentence $x $Ev1) $Selected\n"
        f"     (let $derivations {derivations}\n"
        f"       (let* (($NextTasks {tasks}) ($NextBeliefs {beliefs}))\n"
        "         ($NextTasks $NextBeliefs $derivations)))))\n")


CLOCK_WRAPPER = """
; Python's process clock executes INSIDE the SWI/PeTTa process through Janus.
; It measures process-wide user+system CPU, not wall time or parent-Python CPU.
(= (Cost.Clock) (py-call (time.process_time_ns)))
(= (Cost.Probe)
   (let* (($a (Cost.Clock)) ($b (Cost.Clock)) ($c (Cost.Clock)))
     (println! (COST_CLOCK_PROBE (- $b $a) (- $c $b) (- $c $a)))))
(= (Cost.Measure $Tasks $Beliefs $Requested $tq $bq)
   (let* (($start (Cost.Clock))
          ($selected (if (== $Requested Native)
                         (BestCandidate PriorityRank () $Tasks) $Requested))
          ($afterSelection (Cost.Clock))
          ($out (Cost.Expand $Tasks $Beliefs $selected $tq $bq))
          ($afterExpansion (Cost.Clock)))
     (progn
       (println! (COST_TIMES (- $afterSelection $start)
                             (- $afterExpansion $afterSelection)
                             (- $afterExpansion $start)))
       (println! (COST_SELECTED $selected))
       $out)))
"""


def chosen_record(state, requested):
    tasks = state["tasks"]
    if not tasks:
        raise ValueError("No pending work")
    chosen = max(tasks, key=lambda r: sentence(r)[1][1]) if requested == "Native" else requested
    if chosen not in tasks:
        raise ValueError("Selected candidate is not pending")
    if sentence(chosen)[1][1] != max(sentence(r)[1][1] for r in tasks):
        raise ValueError("Reference only supports maximum-priority alternatives")
    return chosen


def trial_fixture(state, requested, helper):
    chosen_record(state, requested)
    call = ["Cost.Measure", state["tasks"], state["beliefs"], requested, state["task_limit"], state["belief_limit"]]
    # Initialize Python/clock before the probes and expansion. This startup cost
    # is excluded from this local operation diagnostic, not from future queries.
    return helper + CLOCK_WRAPPER + "\n!(Cost.Clock)\n" + (
        "!(println! (COST_CLOCK_INFO (py-call (platform.python_version)) "
        "(py-call (getattr (py-call (time.get_clock_info process_time)) resolution)) "
        "(py-call (getattr (py-call (time.get_clock_info process_time)) monotonic))))\n"
    ) + "!(Cost.Probe)\n" * 10 + f"!(println! (COST_RESULT {expression(call)}))\n"


def reference_fixture(state, requested):
    """Unmodified native loop, stopped after one expansion.

    For a forced maximum-priority alternative only, put it first in a reference
    task copy so native tie-breaking chooses it. Removing that selected record
    leaves the other task order unchanged. Beliefs and the timed Tasks are never
    reordered. Full ordered post-queues must match, not just the answer.
    """
    chosen = chosen_record(state, requested)
    tasks = state["tasks"] if requested == "Native" else [chosen] + [r for r in state["tasks"] if r != chosen]
    call = ["PLN.Derive", tasks, state["beliefs"], state["next_step"], state["next_step"],
            state["task_limit"], state["belief_limit"]]
    return f"!(println! (COST_REFERENCE {expression(call)}))\n"


def marked(log, marker):
    rows = [read_one(line) for line in log.splitlines() if line.startswith(f"({marker} ")]
    if len(rows) != 1:
        raise ValueError(f"Expected exactly one {marker}")
    return rows[0][1:]


def parse_trial(log):
    times = marked(log, "COST_TIMES")
    if len(times) != 3 or any(type(t) is not int or t < 0 for t in times) or sum(times[:2]) != times[2]:
        raise ValueError("Invalid CPU intervals")
    selected = marked(log, "COST_SELECTED")
    if len(selected) != 1:
        raise ValueError("Malformed selected record")
    sentence(selected[0])
    result = marked(log, "COST_RESULT")
    if len(result) != 1 or not isinstance(result[0], list) or len(result[0]) != 3:
        raise ValueError("Malformed expansion result")
    for records in result[0]:
        if not isinstance(records, list):
            raise ValueError("Malformed result queue")
        for record in records:
            sentence(record)
    probes = [read_one(l)[1:] for l in log.splitlines() if l.startswith("(COST_CLOCK_PROBE ")]
    if len(probes) != 10 or any(len(p) != 3 or any(type(n) is not int or n < 0 for n in p)
                              or sum(p[:2]) != p[2] for p in probes):
        raise ValueError("Invalid boundary-clock probes")
    info = marked(log, "COST_CLOCK_INFO")
    if (len(info) != 3 or type(info[1]) not in (float, int) or not math.isfinite(info[1])
            or info[1] <= 0 or info[2] != "true"):
        raise ValueError("Clock must report positive resolution and monotonicity")
    return {"selected": selected[0], "queues": result[0][:2], "derivations": result[0][2],
            "selection_or_dispatch_cpu_ns": times[0], "expansion_cpu_ns": times[1],
            "local_total_cpu_ns": times[2], "clock_probes_ns": probes,
            "embedded_clock_info": info}


def counters(state, chosen, trial, audit_log):
    events = [read_one(l) for l in audit_log.splitlines() if l.startswith(("(COST_GUARD ", "(COST_ATTEMPT ", "(COST_GENERATED "))]
    guards = [e[1] for e in events if e[0] == "COST_GUARD"]
    passed = sum(v == "true" for v in guards)
    eligible = sum(not set(chosen[2]) & set(r[2]) for r in state["beliefs"])
    if len(guards) != len(state["beliefs"]) or passed != eligible or any(v not in ("true", "false") for v in guards):
        raise ValueError("Premise traversal/guard counters disagree with the saved state")
    attempts = [e[1] for e in events if e[0] == "COST_ATTEMPT"]
    if (attempts.count("forward") != passed or attempts.count("backward") != passed or attempts.count("unary") != 1
            or any(label not in ("forward", "backward", "unary") for label in attempts)):
        raise ValueError("Rule-dispatch counters disagree with native control flow")
    generated = [e for e in events if e[0] == "COST_GENERATED"]
    if [e[2] for e in generated] != trial["derivations"] or any(e[1] not in ("binary", "unary") for e in generated):
        raise ValueError("Generated-result counters disagree with collapse output")

    def unique(seq):
        out = []
        for r in seq:
            if r not in out:
                out.append(r)
        return out

    pre_tasks = [r for r in unique(state["tasks"] + trial["derivations"]) if r != chosen]
    pre_beliefs = unique(state["beliefs"] + trial["derivations"])
    post_tasks, post_beliefs = trial["queues"]
    # Independently reconstruct native lowest-priority removal, including tie order.
    def trim(seq, cap):
        seq = list(seq)
        while len(seq) >= cap:
            victim = min(seq, key=lambda r: sentence(r)[1][1])
            seq = [r for r in seq if r != victim]
        return seq
    if trim(pre_tasks, state["task_limit"]) != post_tasks or trim(pre_beliefs, state["belief_limit"]) != post_beliefs:
        raise ValueError("Queue accounting disagrees with native deduplication/trimming")
    return {"belief_buffer_size": len(state["beliefs"]), "visited_premise_pairs": len(guards),
            "stamp_disjoint_pairs": passed, "binary_rule_dispatches": 2*passed, "unary_rule_dispatches": 1,
            "generated_binary_results": sum(e[1] == "binary" for e in generated),
            "generated_unary_results": sum(e[1] == "unary" for e in generated),
            "unique_generated_records": len(unique(trial["derivations"])),
            "unique_new_beliefs": sum(r not in state["beliefs"] for r in unique(trial["derivations"])),
            "retained_task_additions": sum(r not in state["tasks"] for r in post_tasks),
            "retained_belief_additions": sum(r not in state["beliefs"] for r in post_beliefs),
            "tasks_removed_by_cap": len(pre_tasks) - len(post_tasks),
            "beliefs_removed_by_cap": len(pre_beliefs) - len(post_beliefs)}
