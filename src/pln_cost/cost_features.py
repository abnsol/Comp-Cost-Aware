"""Prospective structural CPU features; no inference, labels or goal knowledge.

These counts describe possible work, not its usefulness. Feature acquisition
must be charged when used online. No persistent cache or trained model here.
"""
from .proof import sentence

FEATURE_NAMES = (
    "belief_count", "task_count", "term_nodes", "evidence_count",
    "is_implication", "disjoint_beliefs", "same_term_disjoint",
    "mp_matches", "mp_matches_x_beliefs", "mp_matches_x_tasks",
)


def node_count(term):
    return 1 + sum(node_count(x) for x in term) if isinstance(term, list) else 1


def eligible_candidates(state):
    if not state["tasks"]:
        return []
    maximum = max(sentence(r)[1][1] for r in state["tasks"])
    return [r for r in state["tasks"] if sentence(r)[1][1] == maximum]


def features(state, candidate):
    """Read only current queues and the selected record; do not execute PLN."""
    term, _, evidence = sentence(candidate)
    is_implication = isinstance(term, list) and len(term) == 3 and term[0] == "Implication"
    selected_evidence = set(evidence)
    disjoint = same = matches = 0
    for record in state["beliefs"]:
        other, _, stamp = sentence(record)
        if selected_evidence.intersection(stamp):
            continue
        disjoint += 1
        same += other == term
        if isinstance(other, list) and len(other) == 3 and other[0] == "Implication" and other[1] == term:
            matches += 1
        if is_implication and term[1] == other:
            matches += 1
    beliefs, tasks = len(state["beliefs"]), len(state["tasks"])
    return dict(zip(FEATURE_NAMES, (beliefs, tasks, node_count(term), len(evidence),
        int(is_implication), disjoint, same, matches, matches * beliefs, matches * tasks)))
