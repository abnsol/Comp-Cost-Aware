"""Independent synthetic population, used only by the offline evaluator.

No PLN import, truth formula, returned answer or selection logic is used here.
The joint distribution is P(A) P(B|A) P(C|A) P(D|B).
"""
from fractions import Fraction as F
from itertools import product


def population():
    """Return exact probabilities over (HighLoad, Hot, Vibrating, Fails)."""
    worlds = {}
    for a, b, c, d in product((0, 1), repeat=4):
        pb = F(4, 5) if a else F(1, 5)
        pc = F(4, 5) if a else F(1, 5)
        pd = F(9, 10) if b else F(1, 10)
        worlds[a, b, c, d] = (
            F(1, 2) * (pb if b else 1 - pb)
            * (pc if c else 1 - pc) * (pd if d else 1 - pd)
        )
    return worlds


def conditional(outcome, given):
    """Population P(attribute[outcome]=1 | attribute[given]=1)."""
    worlds = population()
    denominator = sum(p for state, p in worlds.items() if state[given])
    numerator = sum(p for state, p in worlds.items() if state[given] and state[outcome])
    return numerator / denominator


def reference():
    target = conditional(3, 0)
    return {
        "query": "P(Fails | HighLoad)",
        "target_fraction": str(target),
        "target_probability": float(target),
        "world_count": len(population()),
        "total_probability": str(sum(population().values())),
        "status": "synthetic population truth, not a required PLN answer",
    }
