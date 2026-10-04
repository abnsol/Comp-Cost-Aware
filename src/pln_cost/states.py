"""Capture/restore the explicit ground PLN loop state, without CPU measurement.

Only ordered Tasks/Beliefs and loop counters are restored. Fresh processes reset
runtime caches and allocation history; this is not a hardware-state snapshot.
"""
from copy import deepcopy
import difflib

from .proof import key, sentence
from .qualification import expression
from .sexpr import read_one
from .tracing import instrument

STATE_PREFIX = "(QUAL_STATE "
TRIM_PREFIX = "(QUAL_TRIM "
FIELDS = ("next_step", "maxsteps", "task_limit", "belief_limit", "tasks", "beliefs")
SIGNATURE = "(= (PLN.Derive $Tasks $Beliefs $steps $maxsteps $taskqueuesize $beliefqueuesize)"


def instrument_states(source):
    """Keep the native loop body intact, wrapping it with an entry-state print.

    Entry is before selection; except the first entry, arguments are the prior
    expansion's completed queue updates. The terminal entry is printed as well.
    Existing proof prints are retained. A separate print marks actual removals
    by LimitSize, so absence of a trim event is directly observable.
    """
    traced, _ = instrument(source)
    if traced.count(SIGNATURE) != 1:
        raise ValueError("Expected exactly one native loop definition")
    start = traced.index(SIGNATURE)
    depth, end = 0, None
    for pos in range(start, len(traced)):
        depth += (traced[pos] == "(") - (traced[pos] == ")")
        if depth == 0:
            end = pos
            break
    if end is None:
        raise ValueError("Unbalanced native loop definition")
    body = traced[start + len(SIGNATURE):end].strip()
    replacement = (SIGNATURE + "\n   (progn\n"
                   "     (println! (QUAL_STATE $steps $maxsteps $taskqueuesize $beliefqueuesize $Tasks $Beliefs))\n"
                   f"     {body}))")
    traced = traced[:start] + replacement + traced[end + 1:]
    removal = "(LimitSize (exclude-item $lowestPriorityItem $L) $size)"
    if traced.count(removal) != 1:
        raise ValueError("Expected exactly one native queue removal")
    traced = traced.replace(removal,
        f"(progn (println! (QUAL_TRIM $size $lowestPriorityItem)) {removal})", 1)
    patch = "".join(difflib.unified_diff(source.splitlines(keepends=True), traced.splitlines(keepends=True),
                    fromfile="pinned-PLN/lib_pln.metta", tofile="generated/lib_pln.states.metta"))
    return traced, patch


def state_from_form(form):
    if not isinstance(form, list) or len(form) != 7 or form[0] != "QUAL_STATE":
        raise ValueError("Malformed state event")
    state = dict(zip(FIELDS, form[1:]))
    for name in FIELDS[:4]:
        if type(state[name]) is not int or state[name] < 1:
            raise ValueError("Invalid state counter or limit")
    if state["next_step"] > state["maxsteps"] + 1:
        raise ValueError("State beyond terminal counter")
    for name in ("tasks", "beliefs"):
        if not isinstance(state[name], list):
            raise ValueError("Invalid state queue")
        for record in state[name]:
            sentence(record)
    return state


def capture_states(log, case, limits):
    """Validate entry progression and membership in input/generated records.

    Membership validates capture consistency, not every record's proof. Only
    returned-answer ancestor proofs were independently audited in step three.
    """
    states, known = [], {key(r) for r in case["inputs"]}
    selected_count, trims = 0, []
    lines = log.splitlines()
    for line_number, line in enumerate(lines, 1):
        if line.startswith(("(STEP2_BINARY ", "(STEP2_UNARY ")):
            event = read_one(line)
            known.add(key(event[-1]))
        elif line.startswith("(SELECTED "):
            if not states or selected_count != len(states) - 1:
                raise ValueError("Unexpected selection between checkpoints")
            selected = read_one(line)[1]
            tasks = states[-1]["state"]["tasks"]
            if not tasks or selected != max(tasks, key=lambda r: sentence(r)[1][1]):
                raise ValueError("Selection does not match native confidence priority/tie order")
            selected_count += 1
        elif line.startswith(TRIM_PREFIX):
            form = read_one(line)
            if len(form) != 3:
                raise ValueError("Malformed trim event")
            sentence(form[2])
            trims.append({"line": line_number, "limit": form[1], "removed": form[2]})
        elif line.startswith(STATE_PREFIX):
            state = state_from_form(read_one(line))
            if state["next_step"] != len(states) + 1 or selected_count != len(states):
                raise ValueError("Missing or unordered state checkpoints")
            if [state[n] for n in FIELDS[1:4]] != [limits[n] for n in
                    ("maxsteps_argument", "task_queue_limit_argument", "belief_queue_limit_argument")]:
                raise ValueError("State configuration mismatch")
            if any(key(r) not in known for name in ("tasks", "beliefs") for r in state[name]):
                raise ValueError("Queue contains an uncaptured record")
            if not states and (state["tasks"] != case["inputs"] or state["beliefs"] != case["inputs"]):
                raise ValueError("Initial queues differ from the case")
            states.append({"state": state, "sha256": key(state), "trace_line": line_number})
    if not states or selected_count != len(states) - 1:
        raise ValueError("Missing terminal state")
    final = states[-1]["state"]
    if final["tasks"] and final["next_step"] <= final["maxsteps"]:
        raise ValueError("Nonterminal last checkpoint")
    return states, trims


def ready_pair(state):
    """Only compare pending original Ready facts; beliefs alone are insufficient."""
    selected = {}
    for route, ident in (("route_a", 1), ("route_b", 2)):
        matches = [r for r in state["tasks"] if r[1][0] == ["Ready", "unit0", route] and r[2] == [ident]]
        if len(matches) != 1:
            return None
        selected[route] = matches[0]
    priorities = [sentence(r)[1][1] for r in selected.values()]
    if priorities[0] != priorities[1]:
        return None
    return {"priority": priorities[0], "candidates": deepcopy(selected)}


def checkpoints_to_restore(states):
    """Fixed policy: initial, after one, midpoint, penultimate, terminal;
    plus the last noninitial equal-priority Ready-pair state, if available.
    """
    last = len(states) - 1
    if last < 1:
        return [0]
    indices = {0, 1, last // 2, last - 1, last}
    eligible = [i for i, item in enumerate(states) if ready_pair(item["state"])]
    if eligible:
        indices.add(eligible[-1])
    return sorted(indices)


def restore_fixture(snapshot, *, source_hash, fixture_hash, expected_state_hash):
    """Require caller-owned provenance/hash; preserve queue order and counters."""
    if snapshot["source_sha256"] != source_hash or snapshot["fixture_sha256"] != fixture_hash:
        raise ValueError("Snapshot provenance mismatch")
    state = snapshot["state"]
    if key(state) != expected_state_hash or snapshot["sha256"] != expected_state_hash:
        raise ValueError("Snapshot content mismatch")
    state_from_form(["QUAL_STATE"] + [state[n] for n in FIELDS])
    call = ["PLN.Derive", state["tasks"], state["beliefs"], state["next_step"],
            state["maxsteps"], state["task_limit"], state["belief_limit"]]
    return ("; Restore the exact logical state in a fresh process; no CPU claim.\n"
            f"!(println! (RESTORED_STATE {expression(call)}))\n")


def check_restoration(log, original_log, checkpoint, final_state):
    """Require exact remaining state/proof/selection events and final queues."""
    def events(lines):
        return [line for line in lines if line.startswith(
            (STATE_PREFIX, TRIM_PREFIX, "(SELECTED ", "(STEP2_BINARY ", "(STEP2_UNARY "))]
    expected = events(original_log.splitlines()[checkpoint["trace_line"] - 1:])
    actual = events(log.splitlines())
    markers = [read_one(line) for line in log.splitlines() if line.startswith("(RESTORED_STATE ")]
    if (len(markers) != 1 or len(markers[0]) != 2
            or markers[0][1] != [final_state["tasks"], final_state["beliefs"]]):
        raise ValueError("Restoration changed final queues")
    if actual != expected:
        raise ValueError("Restoration changed continuation events")
    return {"continuation_events_identical": True, "final_ordered_queues_identical": True,
            "state_checkpoints_compared": sum(line.startswith(STATE_PREFIX) for line in actual),
            "selected_records_compared": sum(line.startswith("(SELECTED ") for line in actual)}
