"""Offline certificate extraction and independent deduction/MP/revision replay.

The executed inference remains native MeTTa. This checker implements a declared
subset of the pinned formulas, rather than calling PLN to validate itself. It
checks only a certificate's ancestor proof, not all search steps. Authored static
witnesses can also be replayed; their validity does not establish engine execution.
It verifies rule execution, not statistical soundness or world-truth accuracy.
"""
from collections import Counter
import hashlib
import json
import math

from .sexpr import read_one

SOURCE_COMMIT = "4405956947c4b53c7ff01bd565aa3b114bc970a1"


def key(record):
    return hashlib.sha256(json.dumps(record, separators=(",", ":")).encode()).hexdigest()


def truth(tv):
    if (not isinstance(tv, list) or len(tv) != 3 or tv[0] != "stv"
            or not all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in tv[1:])):
        raise ValueError("Invalid truth value")
    return tv[1:]


def sentence(record):
    if not isinstance(record, list) or len(record) != 3 or record[0] != "Sentence":
        raise ValueError("Expected Sentence")
    if not isinstance(record[1], list) or len(record[1]) != 2:
        raise ValueError("Invalid sentence payload")
    term, tv = record[1]
    def ground(value):
        if isinstance(value, list):
            return all(ground(part) for part in value)
        return not (isinstance(value, str) and value.startswith("$"))

    if not ground(term):
        raise ValueError("Variables are outside this ground proof checker")
    evidence = record[2]
    if (not isinstance(evidence, list) or not evidence or
            not all(type(v) is int and v > 0 for v in evidence)
            or evidence != sorted(set(evidence))):
        raise ValueError("Evidence must be a nonempty sorted set of positive IDs")
    return term, truth(tv), evidence


def extract_certificate(log, case, answer, source_hash, fixture_hash):
    """Preserve the first acyclic witness per exact record (including TV/stamp)."""
    nodes = {key(r): {"kind": "input", "record": r} for r in case["inputs"]}
    event_counts = Counter()
    for line_number, line in enumerate(log.splitlines(), 1):
        if not line.startswith(("(STEP2_BINARY", "(STEP2_UNARY")):
            continue
        event = read_one(line)
        arity = {"STEP2_BINARY": 2, "STEP2_UNARY": 1}.get(event[0])
        if arity is None or len(event) != arity + 2:
            raise ValueError("Malformed trace event")
        parents, output = event[1:-1], event[-1]
        parent_ids = [key(record) for record in parents]
        if any(ident not in nodes for ident in parent_ids):
            raise ValueError(f"Unregistered trace parent at line {line_number}")
        ident = key(output)
        nodes.setdefault(ident, {"kind": "binary" if arity == 2 else "unary",
                                 "record": output, "parents": parent_ids,
                                 "trace_line": line_number})
        event_counts[event[0]] += 1
    root_record = ["Sentence", [case["query"], ["stv", answer["strength"], answer["confidence"]]], answer["evidence"]]
    root = key(root_record)
    if root not in nodes:
        raise ValueError("Returned answer has no captured derivation")
    needed = {}

    def collect(ident):
        if ident in needed:
            return
        needed[ident] = nodes[ident]
        for parent in nodes[ident].get("parents", []):
            collect(parent)

    collect(root)
    certificate = {"source_commit": SOURCE_COMMIT, "source_sha256": source_hash,
                   "fixture_sha256": fixture_hash, "query": case["query"],
                   "marginals": case["marginals"], "root": root, "nodes": needed}
    return certificate, dict(event_counts)


def replay(certificate, case, source_hash, fixture_hash):
    """Check against externally supplied inputs/query/source, never self-authorize."""
    if (certificate["source_commit"] != SOURCE_COMMIT or certificate["source_sha256"] != source_hash
            or certificate["fixture_sha256"] != fixture_hash):
        raise ValueError("Source or fixture provenance mismatch")
    if certificate["query"] != case["query"] or certificate["marginals"] != case["marginals"]:
        raise ValueError("Query or marginal inputs mismatch")
    nodes, active, done, steps = certificate["nodes"], set(), set(), []
    allowed = {key(record) for record in case["inputs"]}

    def marginal(term):
        if not isinstance(term, str) or term not in case["marginals"]:
            raise ValueError("Missing ground marginal")
        return truth(case["marginals"][term])[0]

    def consistent(a, b, conditional):
        if a <= 0:
            return False
        lower = max(0, min(1, (a + b - 1) / a))
        upper = max(0, min(1, b / a))
        return lower <= conditional <= upper

    def visit(ident):
        if ident in active:
            raise ValueError("Cyclic certificate")
        if ident in done:
            return
        node = nodes[ident]
        if key(node["record"]) != ident:
            raise ValueError("Record identity mismatch")
        term, tv, evidence = sentence(node["record"])
        active.add(ident)
        if node["kind"] == "input":
            if ident not in allowed or node.get("parents"):
                raise ValueError("Unlicensed input")
            rule = "input"
        elif node["kind"] == "binary":
            if len(node.get("parents", [])) != 2:
                raise ValueError("Binary arity mismatch")
            for parent in node["parents"]:
                visit(parent)
            left, right = [sentence(nodes[p]["record"]) for p in node["parents"]]
            a, (f1, c1), e1 = left
            b, (f2, c2), e2 = right
            if set(e1) & set(e2) or evidence != sorted(e1 + e2):
                raise ValueError("Overlapping evidence or incorrect union")
            if a == b == term:
                if c1 >= 1 or c2 >= 1:
                    raise ValueError("Unsupported revision singularity")
                w1, w2 = c1 / (1 - c1), c2 / (1 - c2)
                weight = w1 + w2
                if weight <= 0:
                    raise ValueError("Empty revision weight")
                expected = [min(1, (w1 * f1 + w2 * f2) / weight),
                            min(1, max(weight / (weight + 1), c1, c2))]
                rule = "Revision (lib_pln.metta:136-143,211-213)"
            elif (isinstance(b, list) and len(b) == 3 and b[0] == "Implication"
                  and a == b[1] and term == b[2]):
                expected = [f1 * f2 + 0.02 * (1 - f1), (f1 * f2) * (c1 * c2)]
                rule = "ModusPonens (lib_pln.metta:124-126,216-218)"
            elif (isinstance(a, list) and isinstance(b, list) and len(a) == len(b) == 3
                  and a[0] == b[0] == "Inheritance" and a[2] == b[1]
                  and term == ["Inheritance", a[1], b[2]]):
                pa, pb, pc = marginal(a[1]), marginal(a[2]), marginal(b[2])
                if not consistent(pa, pb, f1) or not consistent(pb, pc, f2):
                    expected = [1, 0]  # Native deduction's failed-guard result.
                else:
                    strength = pc if pb > 0.9999 else f1 * f2 + (1 - f1) * (pc - pb * f2) / (1 - pb)
                    expected = [strength, (f1 * f2) * (c1 * c2)]
                rule = "Deduction (lib_pln.metta:86-101,235-242)"
            else:
                raise ValueError("Unsupported rule family")
            if not all(math.isclose(actual, predicted, rel_tol=0, abs_tol=1e-12)
                       for actual, predicted in zip(tv, expected)):
                raise ValueError("Incorrect truth calculation")
        else:
            raise ValueError("Unsupported rule family")
        active.remove(ident)
        done.add(ident)
        steps.append({"id": ident, "rule": rule, "record": node["record"],
                      "parents": node.get("parents", []), "trace_line": node.get("trace_line")})

    visit(certificate["root"])
    term, tv, evidence = sentence(nodes[certificate["root"]]["record"])
    if term != case["query"] or tv[1] <= 0:
        raise ValueError("Root is not the requested supported answer")
    if done != set(nodes):
        raise ValueError("Unreachable certificate nodes")
    return {"valid": True, "nodes": len(done), "answer": {"strength": tv[0], "confidence": tv[1], "evidence": evidence},
            "steps": steps, "scope": "certificate ancestor proof only; not all search operations"}
