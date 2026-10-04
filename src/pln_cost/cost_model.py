"""Python reference for shared feature extraction and log-CPU ridge regression.

Training uses development data only. The native adapter independently computes
the same features and score; no Python subprocess is needed per selection.
"""
from collections import Counter
import math

from .cost_features import FEATURE_NAMES, node_count
from .proof import sentence


def feature_rows(state):
    """Validate/parse each record once per selection, not per candidate pair."""
    tasks = [(r, sentence(r)) for r in state["tasks"]]
    if not tasks:
        return []
    maximum = max(s[1][1] for _, s in tasks)
    beliefs = [(term, frozenset(stamp)) for term, _, stamp in map(sentence, state["beliefs"])]
    nb, nt = len(beliefs), len(tasks)
    rows = []
    for record, (term, (_, confidence), evidence) in tasks:
        if confidence != maximum:
            continue
        imp = isinstance(term, list) and len(term) == 3 and term[0] == "Implication"
        stamp = frozenset(evidence)
        disjoint = same = matches = 0
        for other, other_stamp in beliefs:
            if not stamp.isdisjoint(other_stamp):
                continue
            disjoint += 1
            same += term == other
            matches += bool(isinstance(other, list) and len(other) == 3 and other[0] == "Implication" and other[1] == term)
            matches += bool(imp and term[1] == other)
        vector = [nb, nt, node_count(term), len(evidence), int(imp), disjoint,
                  same, matches, matches*nb, matches*nt]
        rows.append((record, vector))
    return rows


def predict(model, vector):
    value = model["intercept"]
    for x, mean, scale, weight in zip(vector, model["means"], model["scales"], model["weights"], strict=True):
        value += weight * ((x-mean)/scale)
    try:
        result = math.exp(value)
    except OverflowError:
        return None
    return result if math.isfinite(result) and result > 0 else None


def choose(state, model, mode):
    if mode not in ("N", "O", "C"):
        raise ValueError("Unknown policy")
    if not state["tasks"]:
        return [], []
    native = max(state["tasks"], key=lambda r: r[1][1][2])
    eligible = [r for r in state["tasks"] if r[1][1][2] == native[1][1][2]]
    if mode == "N" or len(eligible) == 1:
        return native, []
    predictions = [(r, predict(model, vector)) for r, vector in feature_rows(state)]
    if mode == "O" or any(p is None for _, p in predictions):
        return native, predictions
    return min(predictions, key=lambda item: item[1])[0], predictions


def structure_group(row):
    parts = row["case"].split("-")
    return "-".join(parts[:2]) if parts[0] == "necessary" else parts[0]


def fit(rows, alpha):
    """Weighted, standardized ridge on log nanoseconds. No evaluation data."""
    import numpy as np
    if not rows or any(r["split"] != "development" or not r["fit_eligible"] for r in rows):
        raise ValueError("Fit requires qualified development rows only")
    counts = Counter((structure_group(r), r["state"]) for r in rows)
    states = Counter(g for g, _ in counts)
    weights = np.array([1 / (states[structure_group(r)]*counts[(structure_group(r), r["state"])]) for r in rows])
    weights /= weights.sum()
    x = np.array([[r["features"][f] for f in FEATURE_NAMES] for r in rows], dtype=float)
    y = np.log([r["median_cpu_ns"] for r in rows])
    mean = weights @ x
    scale = np.sqrt(weights @ ((x-mean)**2))
    scale[scale < 1e-12] = 1
    z = (x-mean)/scale
    intercept = float(weights @ y)
    coefficients = np.linalg.solve(z.T @ (weights[:, None]*z) + alpha*np.eye(len(FEATURE_NAMES)),
                                   z.T @ (weights*(y-intercept)))
    return {"schema_version": 1, "type": "weighted_standardized_ridge_log_cpu",
        "feature_names": list(FEATURE_NAMES), "alpha": alpha, "means": mean.tolist(),
        "scales": scale.tolist(), "weights": coefficients.tolist(), "intercept": intercept,
        "target_units": "native expansion CPU nanoseconds, excluding selection"}
