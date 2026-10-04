"""Read-only structural descriptors, not a selector or calibrated value model.

Scope must be certified by the caller against a qualified workload. No truth
formula, native inference, future trace, cost label or route-name lookup is used.
"""
from collections import defaultdict, deque

from .proof import sentence

SCOPE = "qualified-closed-ground-mp-v1"


def freeze(term):
    if isinstance(term, list):
        return tuple(freeze(x) for x in term)
    if isinstance(term, str) and term.startswith("$"):
        raise ValueError("Non-ground term")
    return term


def implication(term):
    return isinstance(term, list) and len(term) == 3 and term[0] == "Implication"


def describe(state, query, *, scope=None, marginals=None):
    """Rebuild indexes and describe ALL pending candidates, preserving order.

    'No known connection' refers only to this current ground implication graph.
    A represented consequence is never declared redundant. Returned records are
    read-only references to the input; neither queues nor beliefs are mutated.
    """
    if scope != SCOPE or marginals != {}:
        return {"coverage": "unknown", "reason": "Unqualified scope or marginal-dependent rules", "candidates": []}
    try:
        target = freeze(query)
        beliefs = [(r, *sentence(r)) for r in state["beliefs"]]
        tasks = [(r, *sentence(r)) for r in state["tasks"]]
        if any(implication(t) and implication(t[2]) for _, t, _, _ in beliefs):
            raise ValueError("Possible new implication: static dependency coverage not established")
        present, rules, reverse = defaultdict(list), defaultdict(list), defaultdict(set)
        for record, term, tv, evidence in beliefs:
            node = freeze(term)
            present[node].append((record, frozenset(evidence)))
            if implication(term):
                antecedent, consequent = freeze(term[1]), freeze(term[2])
                rules[antecedent].append((term[2], frozenset(evidence)))
                reverse[consequent].add(antecedent)
        distances, pending = {target: 0}, deque([target])
        while pending:
            node = pending.popleft()
            for parent in reverse[node]:
                if parent not in distances:
                    distances[parent] = distances[node] + 1
                    pending.append(parent)
        maximum = max((tv[1] for _, _, tv, _ in tasks), default=None)
        rows = []
        for record, term, tv, evidence in tasks:
            ev, pairs = frozenset(evidence), []
            for consequent, other_ev in rules.get(freeze(term), ()):
                if ev.isdisjoint(other_ev):
                    pairs.append((consequent, other_ev))
            own_matches = 0
            if implication(term):
                for _, other_ev in present.get(freeze(term[1]), ()):
                    if ev.isdisjoint(other_ev):
                        pairs.append((term[2], other_ev))
                        own_matches += 1
            outputs = []
            for consequence, other_ev in pairs:
                node = freeze(consequence)
                status = ("potential_goal" if node == target else
                          "missing_intermediate" if node in distances and node not in present else
                          "represented_intermediate_value_unresolved" if node in distances else
                          "no_known_query_connection")
                outputs.append({"term": consequence, "evidence_union": sorted(ev | other_ev),
                    "status": status, "term_already_present": node in present,
                    "structural_distance": distances.get(node)})
            rows.append({"candidate": record, "max_confidence_eligible": tv[1] == maximum,
                "mp_pairs": len(pairs), "outputs": outputs,
                "potential_goal_pairs": sum(o["status"] == "potential_goal" for o in outputs),
                "missing_intermediate_pairs": sum(o["status"] == "missing_intermediate" for o in outputs),
                "represented_support_pairs": sum(o["status"] == "represented_intermediate_value_unresolved" for o in outputs),
                "unconnected_pairs": sum(o["status"] == "no_known_query_connection" for o in outputs),
                "dormant_query_rule": implication(term) and own_matches == 0 and freeze(term[2]) in distances})
        return {"coverage": SCOPE, "interpretation": "structural MP support only; not proof validity or deadline probability",
                "beliefs": len(beliefs), "tasks": len(tasks), "candidates": rows}
    except (ValueError, TypeError, KeyError) as exc:
        return {"coverage": "unknown", "reason": str(exc), "candidates": []}
