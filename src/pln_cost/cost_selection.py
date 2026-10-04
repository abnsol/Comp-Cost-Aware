"""Generated selection hook, Python policy reference and new-trace validation."""
import difflib

from .budget import build_budget_library, fixture
from .cost_model import choose
from .expansion import one_expression, replace_once, marked
from .proof import extract_certificate, replay, sentence
from .qualification import expression, qualifies
from .sexpr import read_one
from .states import SIGNATURE, state_from_form


def build_selection_library(source, audit=False):
    library, _ = build_budget_library(source, audit)
    loop = one_expression(library, SIGNATURE)
    changed = replace_once(loop, "(BestCandidate PriorityRank () $Tasks)", "(cost_select $Tasks $Beliefs)")
    library = replace_once(library, loop, changed)
    return library, "".join(difflib.unified_diff(source.splitlines(True), library.splitlines(True),
        fromfile="pinned-PLN/lib_pln.metta", tofile="generated/lib_pln.cost-selection.metta"))


def bootstrap_text(budget_source, selection_source):
    # Reset per-query telemetry AFTER the query start clock, so it is charged.
    old = "budget_clock(Start),\n    nb_setval(pln_budget, state(Start"
    new = "budget_clock(Start),\n    cost_reset,\n    nb_setval(pln_budget, state(Start"
    return replace_once(budget_source, old, new) + "\n" + selection_source


def config_expression(model, mode):
    return expression(["cost_config", mode, model["means"], model["scales"], model["weights"], model["intercept"]])


def selection_fixture(case, config, budget, model, mode):
    return "!" + config_expression(model, mode) + "\n" + fixture(case, config, budget) + "!(println! (COST_STATS (cost_stats)))\n"


def audit_trace(log, case, config, model, mode, source_hash, fixture_hash):
    states, selected = [], []
    for line_number, line in enumerate(log.splitlines(), 1):
        if line.startswith("(QUAL_STATE "):
            state = state_from_form(read_one(line))
            if state["next_step"] != len(states)+1 or len(selected) != len(states):
                raise ValueError("Missing or unordered policy checkpoints")
            if not states and (state["tasks"] != case["inputs"] or state["beliefs"] != case["inputs"]):
                raise ValueError("Changed policy inputs")
            states.append({"state": state, "trace_line": line_number})
        elif line.startswith("(SELECTED "):
            record = read_one(line)[1]
            if not states or len(selected) != len(states)-1:
                raise ValueError("Unexpected selection count")
            expected, _ = choose(states[-1]["state"], model, mode)
            if record != expected:
                raise ValueError("Native hook differs from Python selection reference")
            selected.append(record)
    if len(states) != len(selected)+1:
        raise ValueError("Missing final checkpoint")
    result = marked(log, "BUDGET_RESULT")[0]
    status, done, cpu, observer, detection, answer, queues = result
    if done != len(selected) or queues != [states[-1]["state"][k] for k in ("tasks", "beliefs")]:
        raise ValueError("Final policy state mismatch")
    for snapshot in states[:-1]:
        for record in snapshot["state"]["beliefs"]:
            term, (strength, confidence), _ = sentence(record)
            if term == case["query"] and qualifies({"valid": True, "answer": dict(strength=strength, confidence=confidence)}, config["success"]):
                raise ValueError("Continued past first acceptable answer")
    certificate = checked = None
    if answer:
        if answer not in queues[1]:
            raise ValueError("Answer is not committed")
        term, (strength, confidence), evidence = sentence(answer)
        if term != case["query"]:
            raise ValueError("Wrong query")
        certificate, _ = extract_certificate(log, case, dict(strength=strength, confidence=confidence, evidence=evidence), source_hash, fixture_hash)
        checked = replay(certificate, case, source_hash, fixture_hash)
        if not qualifies(checked, config["success"]):
            raise ValueError("Unqualified policy proof")
    return states, selected, certificate, checked
