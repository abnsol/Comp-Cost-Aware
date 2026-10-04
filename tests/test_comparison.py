from collections import Counter, defaultdict
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pln_cost.comparison import schedule, summarize


class ComparisonTests(unittest.TestCase):
    def test_all_arm_orders_balanced_and_evaluation_preserved(self):
        cases = [{"name": "a", "split": "development"}, {"name": "b", "split": "evaluation"}]
        protocol = {"policies": ["N", "O", "C"], "repetitions": 12, "seed": 1951,
                    "budgets_ns": [1, 2], "generous_budget_ns": 100}
        jobs = schedule(cases, protocol)
        self.assertEqual(jobs, schedule(cases, protocol))
        self.assertEqual(len(jobs), 2*3*3*12)
        blocks = defaultdict(list)
        for j in jobs:
            blocks[(j["case"], j["budget_ns"], j["repetition"])].append(j["mode"])
            self.assertEqual(j["split"], cases[j["case"] == "b"]["split"])
        for case in ("a", "b"):
            for budget in (1, 2, 100):
                counts = Counter(tuple(blocks[(case, budget, rep)]) for rep in range(12))
                self.assertEqual(sorted(counts.values()), [2]*6)

    def test_failures_and_invalid_runs_remain_in_denominator(self):
        base = dict(split="evaluation", case="a", endpoint="budget", budget_ns=10, mode="C")
        runs = [{**base, "result": dict(status="success", verified_success=True, engine_cpu_ns=5, overshoot_ns=0)},
                {**base, "result": dict(status="deadline", verified_success=False, engine_cpu_ns=12, overshoot_ns=2)},
                {**base, "error": "invalid proof"}]
        s = summarize(runs)[0]
        self.assertEqual((s["scheduled_runs"], s["valid_runs"], s["invalid_runs"], s["verified_successes"]), (3, 2, 1, 1))
        self.assertEqual(s["median_actual_cpu_ns"], 8.5)
        self.assertEqual(s["maximum_overshoot_ns"], 2)


if __name__ == "__main__":
    unittest.main()
