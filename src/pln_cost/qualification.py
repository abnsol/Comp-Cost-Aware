"""Generate the specified ground KB and author static (not executed) witnesses.

There is no search, cost model, runtime result, or CPU measurement in this module.
Witness truth values use exact rational arithmetic for this unit-strength family.
They are replayed by the separate pinned-rule checker before being accepted.
"""
from copy import deepcopy
from fractions import Fraction
import random

from .proof import SOURCE_COMMIT, key, sentence

ORDERINGS = ("canonical_ids", "swap_ready_facts", "seeded_shuffle")
QUERY = ["CanOperate", "unit0"]


def validate_config(config):
    """Reject changed scientific assumptions instead of silently ignoring them."""
    required = {
        "schema_version": 1,
        "family": "equal_depth_alternative_authorization_proofs",
        "query": QUERY,
        "initial_strength": 1.0,
        "initial_confidence": 0.9,
        "initial_records_formula": "2*N+4",
        "selector": "native_confidence",
        "rule_profile": "full_pinned_library_loaded",
    }
    for name, expected in required.items():
        if config[name] != expected:
            raise ValueError(f"Unsupported qualification setting: {name}")
    widths = config["development_widths"]
    if (not widths or any(type(n) is not int or n < 1 for n in widths)
            or len(set(widths)) != len(widths)):
        raise ValueError("Widths must be distinct positive integers")
    if (config["input_orderings"] != list(ORDERINGS)
            or type(config["shuffle_seed"]) is not int):
        raise ValueError("Unsupported orderings or shuffle seed")
    caps = config["initial_correctness_limits"]
    for name in ("maxsteps_argument", "task_queue_limit_argument", "belief_queue_limit_argument"):
        if type(caps[name]) is not int or caps[name] <= 0:
            raise ValueError("Invalid native query limit")
    if caps["query_cpu_budget_seconds"] is not None:
        raise ValueError("CPU budgeting is not implemented by this generator")


def kb_records(width, ordering="canonical_ids", seed=17):
    if type(width) is not int or width < 1:
        raise ValueError("Width must be a positive integer")
    if ordering not in ORDERINGS:
        raise ValueError("Unknown input ordering")
    ready_a, ready_b = ["Ready", "unit0", "route_a"], ["Ready", "unit0", "route_b"]
    path_a = ["Certificate", "unit0", "path_a"]
    terms = [ready_a, ready_b, ["Implication", ready_a, path_a], ["Implication", path_a, QUERY]]
    for i in range(1, width + 1):
        path_b = ["Certificate", "unit0", f"path_b_{i:03d}"]
        terms.extend([["Implication", ready_b, path_b], ["Implication", path_b, QUERY]])
    records = [["Sentence", [deepcopy(term), ["stv", 1.0, 0.9]], [i]]
               for i, term in enumerate(terms, 1)]
    if ordering == "swap_ready_facts":
        records[0], records[1] = records[1], records[0]
    elif ordering == "seeded_shuffle":
        random.Random(seed).shuffle(records)
    return records


def expression(value):
    if isinstance(value, list):
        return "(" + " ".join(expression(part) for part in value) + ")"
    return str(value)


def render_case(records, limits):
    """The engine receives axioms/query/caps only, never the witness or costs."""
    body = "\n  ".join(expression(record) for record in records)
    call = ["PLN.Query", ["kb"], QUERY, limits["maxsteps_argument"],
            limits["task_queue_limit_argument"], limits["belief_queue_limit_argument"]]
    return ("; Qualification KB. Preload the full pinned lib_pln.metta.\n"
            "; Generated input only; no native run or cost measurement is implied.\n"
            f"(= (kb)\n ({body}))\n\n"
            f"!(println! (QUALIFICATION_RESULT {expression(call)}))\n")


def static_witness(case, input_ids, source_hash, fixture_hash):
    """Author a two-MP candidate proof, not a claim that native search found it."""
    indexed = {tuple(record[2]): record for record in case["inputs"]}
    inputs = [deepcopy(indexed[(i,)]) for i in input_ids]
    if len(inputs) != 3 or any(sentence(r)[1] != [1.0, 0.9] for r in inputs):
        raise ValueError("Static witness requires three specified unit-strength inputs")
    nodes = {key(r): {"kind": "input", "record": r} for r in inputs}
    current = inputs[0]
    for depth, implication in enumerate(inputs[1:], 2):
        term = implication[1][0]
        if term[:2] != ["Implication", current[1][0]] or len(term) != 3:
            raise ValueError("Inputs do not form the specified implication chain")
        output = ["Sentence", [deepcopy(term[2]), ["stv", 1.0, float(Fraction(9, 10) ** depth)]],
                  sorted(current[2] + implication[2])]
        nodes[key(output)] = {"kind": "binary", "record": output,
                              "parents": [key(current), key(implication)]}
        current = output
    return {"origin": "authored_static_witness_not_native_execution",
            "source_commit": SOURCE_COMMIT, "source_sha256": source_hash,
            "fixture_sha256": fixture_hash, "query": deepcopy(case["query"]),
            "marginals": deepcopy(case["marginals"]), "root": key(current), "nodes": nodes}


def qualifies(replayed, success):
    """Check numerical acceptance only AFTER successful independent proof replay.

    This says nothing about availability in a runtime's committed belief state.
    """
    answer = replayed["answer"]
    tolerance = success["absolute_numeric_tolerance"]
    return (replayed["valid"] and abs(answer["strength"] - success["strength"]) <= tolerance
            and success["minimum_confidence"] - tolerance <= answer["confidence"] <= 1)
