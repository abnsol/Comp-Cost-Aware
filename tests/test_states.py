"""State order, counters, provenance, and eligibility are experimental controls."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.proof import key
from pln_cost.qualification import kb_records, expression
from pln_cost.sexpr import read_forms
from pln_cost.states import (FIELDS, capture_states, check_restoration, checkpoints_to_restore,
                            instrument_states, ready_pair, restore_fixture, state_from_form)


class StateTests(unittest.TestCase):
    def setUp(self):
        self.state = dict(zip(FIELDS, [1, 100, 4097, 4097, kb_records(1), kb_records(1)]))
        self.snapshot = {"state": self.state, "sha256": key(self.state),
                         "source_sha256": "source", "fixture_sha256": "fixture"}

    def restore(self, snapshot=None):
        return restore_fixture(self.snapshot if snapshot is None else snapshot,
            source_hash="source", fixture_hash="fixture", expected_state_hash=key(self.state))

    def test_round_trip_preserves_queues_and_counter(self):
        self.state["next_step"] = 42
        self.snapshot["sha256"] = key(self.state)
        call = read_forms(self.restore())[-1][1][1]
        self.assertEqual(call, ["PLN.Derive", self.state["tasks"], self.state["beliefs"], 42, 100, 4097, 4097])

    def test_content_hash_rejects_order_truth_evidence_and_counter_changes(self):
        for change in ("order", "truth", "evidence", "counter"):
            other = copy.deepcopy(self.snapshot)
            state = other["state"]
            if change == "order":
                state["tasks"].reverse()
            elif change == "truth":
                state["beliefs"][0][1][1][2] = .8
            elif change == "evidence":
                state["beliefs"][0][2] = [2]
            else:
                state["next_step"] = 2
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "content"):
                self.restore(other)

    def test_provenance_mismatch_rejected(self):
        for field in ("source_sha256", "fixture_sha256"):
            other = copy.deepcopy(self.snapshot)
            other[field] = "different"
            with self.assertRaisesRegex(ValueError, "provenance"):
                self.restore(other)

    def test_eligibility_requires_pending_equal_priority_candidates(self):
        self.assertEqual(ready_pair(self.state)["priority"], .9)
        self.state["tasks"][1][1][1][2] = .8
        self.assertIsNone(ready_pair(self.state))
        self.state["tasks"] = kb_records(1)[1:]
        self.assertIsNone(ready_pair(self.state))  # Ready A still exists in beliefs.

    def test_terminal_state_is_valid_but_out_of_range_is_not(self):
        for step, valid in ((101, True), (102, False), (0, False), (True, False)):
            form = ["QUAL_STATE", step, 100, 4097, 4097, [], []]
            if valid:
                self.assertEqual(state_from_form(form)["next_step"], step)
            else:
                with self.assertRaises(ValueError):
                    state_from_form(form)

    def test_checkpoint_policy_covers_terminal_and_last_ready_pair(self):
        states = [{"state": copy.deepcopy(self.state)} for _ in range(11)]
        for item in states[4:]:
            item["state"]["tasks"] = []
        self.assertEqual(checkpoints_to_restore(states), [0, 1, 3, 5, 9, 10])

    def test_continuation_requires_identical_events_and_final_queue_order(self):
        event = expression(["QUAL_STATE"] + [self.state[n] for n in FIELDS])
        queues = [self.state["tasks"], self.state["beliefs"]]
        log = event + "\n" + expression(["RESTORED_STATE", queues]) + "\ntrue\n"
        original = event + "\n(QUALIFICATION_RESULT ())\ntrue\n"
        self.assertTrue(check_restoration(log, original, {"trace_line": 1}, self.state)["final_ordered_queues_identical"])
        with self.assertRaisesRegex(ValueError, "continuation"):
            check_restoration(log.replace(event, event + "\n(SELECTED fake)"), original, {"trace_line": 1}, self.state)
        queues[0] = list(reversed(queues[0]))
        with self.assertRaisesRegex(ValueError, "final queues"):
            check_restoration(event + "\n" + expression(["RESTORED_STATE", queues]), original, {"trace_line": 1}, self.state)

    def test_unknown_source_fails_closed(self):
        with self.assertRaises(ValueError):
            instrument_states("not the pinned implementation")



if __name__ == '__main__':
    unittest.main()
