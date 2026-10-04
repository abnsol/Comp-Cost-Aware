"""Offline first-goal certification and whole-native-prefix timing fixtures."""
import difflib

from .expansion import marked, replace_once
from .proof import extract_certificate, replay, sentence
from .qualification import expression, qualifies
from .sexpr import read_one


def first_verified(states, log, case, source_hash, fixture_hash, success):
    for index, snapshot in enumerate(states):
        for record in snapshot["state"]["beliefs"]:
            term, (strength, confidence), evidence = sentence(record)
            if term != case["query"]:
                continue
            answer = dict(strength=strength, confidence=confidence, evidence=evidence)
            if not qualifies({"valid": True, "answer": answer}, success):
                continue  # Only a numerical filter, not proof acceptance.
            prefix = "\n".join(log.splitlines()[:snapshot["trace_line"]])
            certificate, _ = extract_certificate(prefix, case, answer, source_hash, fixture_hash)
            checked = replay(certificate, case, source_hash, fixture_hash)
            if not qualifies(checked, success):
                raise ValueError("First goal proof failed qualification")
            return index, certificate, checked
    raise ValueError("No qualifying proof in the saved native trajectory")


def quiet_library(source):
    quiet = replace_once(source, "(println! (SELECTED (Sentence $x $Ev1)))", "()")
    patch = "".join(difflib.unified_diff(source.splitlines(True), quiet.splitlines(True),
                    fromfile="pinned-PLN/lib_pln.metta", tofile="generated/lib_pln.quiet.metta"))
    return quiet, patch


def prefix_fixture(case, state, steps, timed=False):
    args = [case["inputs"], case["inputs"], 1, steps, state["task_limit"], state["belief_limit"]]
    if timed:
        # Definitions/argument evaluation occur before the direct timer bridge.
        expected = [state["tasks"], state["beliefs"]]
        return ("!(first_probes)\n!(println! (FIRST_QUEUES " +
                expression(["first_measure"] + args + [expected]) + "))\n")
    return "!(println! (FIRST_QUEUES " + expression(["PLN.Derive"] + args) + "))\n"


def validate_prefix(log, original_log, snapshots, index):
    """Compare all native prefix transitions, proof events and selected records."""
    actual = [read_one(l) for l in log.splitlines() if l.startswith("(QUAL_STATE ")]
    expected = []
    for snapshot in snapshots[:index+1]:
        s = snapshot["state"]
        expected.append(["QUAL_STATE", s["next_step"], index, s["task_limit"], s["belief_limit"], s["tasks"], s["beliefs"]])
    if actual != expected:
        raise ValueError("Native prefix changed ordered state transitions")
    markers = ("(SELECTED ", "(STEP2_BINARY ", "(STEP2_UNARY ", "(QUAL_TRIM ")
    prefix = original_log.splitlines()[:snapshots[index]["trace_line"]]
    if [l for l in log.splitlines() if l.startswith(markers)] != [l for l in prefix if l.startswith(markers)]:
        raise ValueError("Native prefix changed selected records or derivations")
    expected_queues = [snapshots[index]["state"][k] for k in ("tasks", "beliefs")]
    if marked(log, "FIRST_QUEUES") != [expected_queues]:
        raise ValueError("Prefix final queues changed")
    return {"checkpoints_identical": len(expected), "selected_records_identical": index}


def parse_timing(log, expected):
    from .paired import quantile
    rows = [read_one(l)[1:] for l in log.splitlines() if l.startswith("(FIRST_EMPTY ")]
    if len(rows) != 30 or [r[0] for r in rows] != list(range(30)) or any(
            len(r) != 2 or type(r[1]) is not int or r[1] <= 0 for r in rows):
        raise ValueError("Invalid empty probe schedule/clock")
    measured = marked(log, "FIRST_CPU")
    if len(measured) != 1 or type(measured[0]) is not int or measured[0] <= 0:
        raise ValueError("Invalid engine CPU interval")
    if marked(log, "FIRST_QUEUES") != [expected]:
        raise ValueError("Timed native output changed")
    empty_p95 = quantile([r[1] for r in rows], .95)
    return {"engine_reasoning_cpu_ns": measured[0], "empty_p95_ns": empty_p95,
            "empty_p95_fraction": empty_p95 / measured[0],
            "overhead_adequate": empty_p95 <= .1 * measured[0], "empty_samples_ns": [r[1] for r in rows]}
