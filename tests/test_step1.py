"""Offline correctness/false-success guards. No runtime required."""
from fractions import Fraction as F
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pln_cost.validation import clean_completion, parse_answer
from pln_cost.world import conditional, population


class WorldTests(unittest.TestCase):
    def test_normalized_nonnegative_population(self):
        self.assertEqual(len(population()), 16)
        self.assertEqual(sum(population().values()), 1)
        self.assertTrue(all(p >= 0 for p in population().values()))

    def test_target_and_supplied_conditionals(self):
        self.assertEqual(conditional(3, 0), F(37, 50))
        self.assertEqual(conditional(1, 0), F(4, 5))
        self.assertEqual(conditional(2, 0), F(4, 5))
        self.assertEqual(conditional(3, 1), F(9, 10))
        self.assertEqual(conditional(3, 2), F(161, 250))
        for index in range(4):
            self.assertEqual(sum(p for s, p in population().items() if s[index]), F(1, 2))

    def test_metta_inputs_match_independent_world(self):
        source = (Path(__file__).resolve().parents[1] / "cases/machine_failure.metta").read_text()
        attributes = {name: i for i, name in enumerate(("HighLoad", "Hot", "Vibrating", "Fails"))}
        records = re.findall(
            r"\(Sentence \(\(Inheritance (\w+) (\w+)\) \(stv ([\d.]+) ([\d.]+)\)\) \((\d+)\)\)", source)
        self.assertEqual(len(records), 4)
        self.assertEqual({int(record[4]) for record in records}, {1, 2, 3, 4})
        for antecedent, consequent, strength, confidence, _ in records:
            self.assertEqual(F(strength), conditional(attributes[consequent], attributes[antecedent]))
            self.assertEqual(F(confidence), F(9, 10))
        marginals = re.findall(r"\(= \(STV (\w+)\) \(stv ([\d.]+) ([\d.]+)\)\)", source)
        self.assertEqual({row[0] for row in marginals}, set(attributes))
        for name, strength, confidence in marginals:
            self.assertEqual(F(strength), sum(p for s, p in population().items() if s[attributes[name]]))
            self.assertEqual(F(confidence), F(9, 10))


class OutputTests(unittest.TestCase):
    valid = "(STEP1_RESULT ((stv 0.74 0.5832) (1 2)))"

    def test_valid_shape(self):
        self.assertEqual(parse_answer(self.valid)["evidence"], [1, 2])

    def test_no_false_success_from_invalid_output(self):
        for text in ("", "(STEP1_RESULT ())", self.valid + "\n" + self.valid,
                     self.valid.replace("0.74", "nan"), self.valid.replace("0.74", "1.2"),
                     self.valid.replace("(1 2)", "(1 1)"), self.valid.replace("(1 2)", "(99)")):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_answer(text)

    def test_zero_exit_alone_is_insufficient(self):
        run = {"returncode": 0, "timed_out": False, "stdout": "", "stderr": ""}
        self.assertTrue(clean_completion(run))  # Completion is not an answer check.
        self.assertFalse(clean_completion(dict(run, timed_out=True)))
        self.assertFalse(clean_completion(dict(run, stderr="ERROR: unexpected failure")))
        self.assertFalse(clean_completion(dict(run, stdout="❌")))


if __name__ == "__main__":
    unittest.main()
