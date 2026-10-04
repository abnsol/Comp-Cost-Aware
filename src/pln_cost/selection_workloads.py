"""Development-only necessary-work fixtures; no selector or cost model.

The required MP pair is R and (Implication R C). Both endpoints have outgoing
implications, including implications whose antecedent is itself an implication.
These are ground terms handled by the native MP rule, not new inference rules.
"""
from copy import deepcopy
import random

from .proof import key
from .qualification import QUERY

ORDERINGS = ("canonical_ids", "swap_required_pair", "seeded_shuffle")
READY = ["Ready", "unit0", "required"]
CERT = ["Certificate", "unit0", "required"]
LINK = ["Implication", READY, CERT]


def necessary_records(width, ordering="canonical_ids", seed=17, distractors=4):
    if type(width) is not int or width < 1 or type(distractors) is not int or distractors < 1:
        raise ValueError("Positive integer width and distractor count required")
    if ordering not in ORDERINGS:
        raise ValueError("Unsupported ordering")
    terms = [READY, LINK, ["Implication", CERT, QUERY]]
    terms += [["Idle", "unit0", f"d{i}"] for i in range(distractors)]
    for i in range(width):
        terms += [["Implication", READY, ["Side", "fact", f"s{i}"]],
                  ["Implication", LINK, ["Side", "rule", f"s{i}"]]]
    records = [["Sentence", [deepcopy(t), ["stv", 1.0, 0.9]], [i]]
               for i, t in enumerate(terms, 1)]
    if ordering == "swap_required_pair":
        records[0], records[1] = records[1], records[0]
    elif ordering == "seeded_shuffle":
        random.Random(seed).shuffle(records)
    return records


def validate_necessary_shape(case, width, distractors=4):
    """Fail closed before applying the restricted-family necessity argument.

    Exact input multiset, empty STV space, unique evidence and inert Side/Idle
    terms matter: a new shortcut or marginal invalidates the argument. This is
    not a generic theorem prover or a necessity claim for arbitrary PLN KBs.
    """
    expected = necessary_records(width, distractors=distractors)
    if (case["query"] != QUERY or case["marginals"] != {}
            or sorted(key(r) for r in case["inputs"]) != sorted(key(r) for r in expected)):
        raise ValueError("Necessary-work structural contract changed")
    return {"required_certificate_pair_ids": [1, 2], "goal_implication_id": 3,
            "cheap_candidate_id": 4, "input_records": len(expected),
            "scope": "exact closed ground fixture with no STV marginals"}


def initial_state(records, limits):
    return {"next_step": 1, "maxsteps": limits["maxsteps_argument"],
            "task_limit": limits["task_queue_limit_argument"],
            "belief_limit": limits["belief_queue_limit_argument"],
            "tasks": deepcopy(records), "beliefs": deepcopy(records)}


def evaluation_records(width, modules=1, shared_sinks=False,
                       ordering="canonical_ids", seed=29):
    """Reserved structural variants, never training instances.

    Shared sinks permit additional revision of side conclusions. Disconnected
    modules add other complete proofs with different queries; only unit0 is
    queried. The target module's witness retains input IDs 1, 2, 3.
    """
    if type(modules) is not int or modules < 1 or type(shared_sinks) is not bool:
        raise ValueError("Invalid evaluation variant")
    if ordering not in ORDERINGS:
        raise ValueError("Unsupported ordering")
    records = []
    for module in range(modules):
        unit = f"unit{module}"

        def transform(term):
            if not isinstance(term, list):
                return unit if term == "unit0" else term
            if term and term[0] == "Side":
                return ["Side", unit, "shared" if shared_sinks else term[1], term[2]]
            return [transform(part) for part in term]

        for record in necessary_records(width):
            record[1][0] = transform(record[1][0])
            record[2] = [len(records) + 1]
            records.append(record)
    if ordering == "swap_required_pair":
        records[0], records[1] = records[1], records[0]
    elif ordering == "seeded_shuffle":
        random.Random(seed).shuffle(records)
    return records
