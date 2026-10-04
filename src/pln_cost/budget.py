"""Native loop continuation guard, checkpoint parity and deadline scoring."""
import difflib

from .expansion import one_expression, replace_once, marked
from .first_answer import quiet_library
from .proof import extract_certificate, replay, sentence
from .qualification import expression, qualifies
from .states import SIGNATURE, FIELDS, instrument_states
from .sexpr import read_one


def build_budget_library(source, audit=False):
    loop = one_expression(source, SIGNATURE)
    body = loop[len(SIGNATURE):-1].strip()
    wrapped = (SIGNATURE + "\n  (if (budget_continue $steps $Tasks $Beliefs)\n"
               + body + "\n    ($Tasks $Beliefs)))")
    result = replace_once(source, loop, wrapped)
    result = instrument_states(result)[0] if audit else quiet_library(result)[0]
    patch = "".join(difflib.unified_diff(source.splitlines(True), result.splitlines(True),
                    fromfile="pinned-PLN/lib_pln.metta", tofile="generated/lib_pln.budget.metta"))
    return result, patch


def fixture(case, config, budget):
    limits, success = config["initial_correctness_limits"], config["success"]
    call = ["budget_run", case["inputs"], case["query"], budget, limits["maxsteps_argument"],
            limits["task_queue_limit_argument"], limits["belief_queue_limit_argument"],
            success["strength"], success["minimum_confidence"], success["absolute_numeric_tolerance"]]
    return "!(println! (BUDGET_RESULT " + expression(call) + "))\n"


def check_result(log, budget, states, trace, case, source_hash, fixture_hash, success, audit=False):
    value = marked(log, "BUDGET_RESULT")
    if len(value) != 1 or not isinstance(value[0], list) or len(value[0]) != 7:
        raise ValueError("Malformed budget result")
    status, done, cpu, observer, detection, answer, queues = value[0]
    if (status not in ("success", "late_return", "deadline", "exhausted")
            or any(type(n) is not int or n < 0 for n in (done, cpu, observer, detection))
            or cpu <= 0 or done >= len(states) or not observer <= cpu or not detection <= cpu):
        raise ValueError("Invalid budget status/counters/clocks")
    state = states[done]["state"]
    if queues != [state["tasks"], state["beliefs"]]:
        raise ValueError("Budget adapter changed native checkpoint queues")
    if status == "success" and (cpu > budget or not answer):
        raise ValueError("Late or missing answer incorrectly accepted")
    if status == "late_return" and (cpu <= budget or not answer):
        raise ValueError("Invalid late-return classification")
    if status == "deadline" and cpu < budget:
        raise ValueError("Premature deadline classification")
    if status == "exhausted" and (state["tasks"] and state["next_step"] <= state["maxsteps"]):
        raise ValueError("Premature exhaustion")
    if status == "exhausted" and answer:
        raise ValueError("Exhaustion cannot include a detected goal")
    # Online stopping must not pass an earlier acceptable committed goal.
    for previous in states[:done]:
        for r in previous["state"]["beliefs"]:
            term, (strength, confidence), _ = sentence(r)
            if term == case["query"] and qualifies({"valid": True, "answer": dict(strength=strength, confidence=confidence)}, success):
                raise ValueError("Adapter continued past an earlier qualifying goal")
    prefix = "\n".join(trace.splitlines()[:states[done]["trace_line"]])
    certificate = checked = None
    if answer:
        if answer not in state["beliefs"]:
            raise ValueError("Detected answer is not in committed beliefs")
        term, (strength, confidence), evidence = sentence(answer)
        if term != case["query"]:
            raise ValueError("Detected wrong query")
        certificate, _ = extract_certificate(prefix, case, dict(strength=strength, confidence=confidence, evidence=evidence),
                                             source_hash, fixture_hash)
        checked = replay(certificate, case, source_hash, fixture_hash)
        if not qualifies(checked, success):
            raise ValueError("Detected answer does not meet proof contract")
    if audit:
        actual = [read_one(l) for l in log.splitlines() if l.startswith("(QUAL_STATE ")]
        expected = [["QUAL_STATE"] + [s["state"][k] for k in FIELDS] for s in states[:done+1]]
        if actual != expected:
            raise ValueError("Budget guard changed intermediate native states")
        markers = ("(SELECTED ", "(STEP2_BINARY ", "(STEP2_UNARY ", "(QUAL_TRIM ")
        if [l for l in log.splitlines() if l.startswith(markers)] != [l for l in prefix.splitlines() if l.startswith(markers)]:
            raise ValueError("Budget guard changed selection/proof prefix")
    return {"status": status, "completed_expansions": done, "engine_cpu_ns": cpu,
            "observer_window_cpu_ns": observer, "observer_window_fraction": observer/cpu,
            "last_detection_cpu_ns": detection, "overshoot_ns": max(0, cpu-budget),
            "verified_success": status == "success" and checked is not None,
            "detected_proof_verified": checked is not None,
            "goal_in_final_state": any(r[1][0] == case["query"] for r in state["beliefs"]),
            "audit_prefix_identical": audit}, certificate, checked
