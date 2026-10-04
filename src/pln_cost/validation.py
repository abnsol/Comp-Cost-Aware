"""Strict result checks; these do NOT constitute independent proof replay."""
import math
import re


def clean_completion(run):
    # Fail closed; inspect unexpected diagnostics rather than silently ignoring them.
    return (run["returncode"] == 0 and not run["timed_out"]
            and not run["stderr"].strip() and "❌" not in run["stdout"]
            and "Assertion failed" not in run["stdout"])


def parse_answer(text):
    """Accept exactly one marked answer of shape ((stv number number) (IDs))."""
    lines = [line.strip() for line in text.splitlines()
             if line.strip().startswith("(STEP1_RESULT")]
    if len(lines) != 1:
        raise ValueError("Expected exactly one marked result")
    match = re.fullmatch(
        r"\(STEP1_RESULT\s+\(\(stv\s+([^\s()]+)\s+([^\s()]+)\)\s+\(([^()]*)\)\)\)",
        lines[0],
    )
    if not match:
        raise ValueError("Missing or malformed query answer")
    strength, confidence = map(float, match.group(1, 2))
    if not all(math.isfinite(x) and 0 <= x <= 1 for x in (strength, confidence)):
        raise ValueError("Invalid strength/confidence")
    evidence = [int(token) for token in match[3].split()]
    if not evidence or len(evidence) != len(set(evidence)) or not set(evidence) <= {1, 2, 3, 4}:
        raise ValueError("Invalid evidence identifiers")
    return {"strength": strength, "confidence": confidence, "evidence": evidence}
