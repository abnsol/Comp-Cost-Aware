"""Result parsing and observable trace parity for qualification, not CPU timing."""
from .proof import sentence
from .sexpr import read_one

TRACE_PREFIXES = ("(STEP2_BINARY", "(STEP2_UNARY")


def parse_result(log, case):
    """Return None for an explicit empty answer; reject missing/malformed output.

    Evidence IDs must come from this case, not the old diagnostic's IDs 1..4.
    A well-formed answer still needs independent certificate replay.
    """
    lines = [line.strip() for line in log.splitlines()
             if line.strip().startswith("(QUALIFICATION_RESULT")]
    if len(lines) != 1:
        raise ValueError("Expected exactly one qualification result")
    form = read_one(lines[0])
    if len(form) != 2 or form[0] != "QUALIFICATION_RESULT":
        raise ValueError("Malformed qualification result")
    answer = form[1]
    if answer == []:
        return None
    if not isinstance(answer, list) or len(answer) != 2:
        raise ValueError("Malformed qualification answer")
    _, (strength, confidence), evidence = sentence(
        ["Sentence", [case["query"], answer[0]], answer[1]])
    allowed = {ident for record in case["inputs"] for ident in sentence(record)[2]}
    if not set(evidence) <= allowed:
        raise ValueError("Answer uses undeclared evidence")
    return {"strength": strength, "confidence": confidence, "evidence": evidence}


def observable_parity(native_log, traced_log):
    """Compare every original output line, including the ordered SELECTED records.

    This is evidence of observed parity on a case, not proof for all executions.
    Logging overhead is deliberately not a performance observation.
    """
    native = native_log.splitlines()
    traced = [line for line in traced_log.splitlines() if not line.startswith(TRACE_PREFIXES)]
    return {"all_original_output_unchanged": native == traced,
            "native_selected_records": sum(line.startswith("(SELECTED ") for line in native),
            "traced_selected_records": sum(line.startswith("(SELECTED ") for line in traced)}
