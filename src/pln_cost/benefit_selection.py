"""Reviewed structural categories plus an immediate-cost tie-breaker.

Python remains the online description implementation through embedded Janus.
The offline choose() reference does not supply choices to the native hook.
"""
from .benefit_signals import SCOPE, describe
from .budget import fixture
from .cost_model import feature_rows, predict
from .cost_selection import bootstrap_text, build_selection_library, config_expression
from .expansion import replace_once
from .qualification import expression

MODES = ("N", "B", "BO", "BC")


def category(row):
    if row["potential_goal_pairs"] > 0:
        return 2
    if row["missing_intermediate_pairs"] + row["represented_support_pairs"] > 0:
        return 1
    return 0


def native_ranks(tasks, beliefs, query, scope):
    """Online bridge: describe every pending candidate, return ordered categories.

    Scope includes the caller's guarantee of empty marginals and qualified rules.
    No saved traces, timing labels, model, route names or candidate choices enter.
    """
    result = describe({"tasks": tasks, "beliefs": beliefs}, query,
                      scope=scope, marginals={})
    if result["coverage"] != SCOPE:
        return ["unknown", []]
    return ["covered", [category(row) for row in result["candidates"]]]


def choose(state, model, mode, *, query, scope=SCOPE, marginals=None):
    """Offline reference; metadata exposes skip/fallback branches for validation."""
    if mode not in MODES:
        raise ValueError("Unknown usefulness policy")
    meta = {"predictions": [], "coverage_fallback": False,
            "prediction_fallback": False, "singleton": False, "classified": 0}
    tasks = state["tasks"]
    if not tasks:
        return [], meta
    native = max(tasks, key=lambda r: r[1][1][2])
    eligible = [r for r in tasks if r[1][1][2] == native[1][1][2]]
    if mode == "N":
        return native, meta
    if len(eligible) == 1:
        meta["singleton"] = True
        return native, meta
    descriptors = describe(state, query, scope=scope, marginals=marginals)
    if descriptors["coverage"] != SCOPE:
        meta["coverage_fallback"] = True
        return native, meta
    meta["classified"] = len(tasks)
    rows = [r for r in descriptors["candidates"] if r["max_confidence_eligible"]]
    best = max(map(category, rows))
    finalists = [r["candidate"] for r in rows if category(r) == best]
    if len(finalists) == 1:
        meta["singleton"] = True
    if mode == "B" or len(finalists) == 1:
        return finalists[0], meta
    predictions = [(r, predict(model, vector)) for r, vector in feature_rows(state)
                   if r in finalists]
    meta["predictions"] = predictions
    if any(p is None for _, p in predictions):
        meta["prediction_fallback"] = True
        return finalists[0], meta
    if mode == "BO":
        return finalists[0], meta
    return min(predictions, key=lambda item: item[1])[0], meta


def build_library(source, audit=False):
    import difflib
    library, _ = build_selection_library(source, audit)
    library = replace_once(library, "(cost_select $Tasks $Beliefs)",
                           "(benefit_select $Tasks $Beliefs)")
    return library, "".join(difflib.unified_diff(source.splitlines(True), library.splitlines(True),
        fromfile="pinned-PLN/lib_pln.metta", tofile="generated/lib_pln.benefit-selection.metta"))


def bootstrap(project):
    # Static path/module loading outside the loaded-query interval; all calls,
    # conversions and classification inside selection remain charged.
    path = str(project / "src").replace("\\", "\\\\").replace("'", "\\'")
    base = bootstrap_text((project / "src/pln_cost/budget_clock.pl").read_text(),
                          (project / "src/pln_cost/cost_selector.pl").read_text())
    base = replace_once(base, "    cost_reset,", "    cost_reset,\n    benefit_reset,")
    return (base + f"\n:- py_call(sys:path:insert(0, '{path}'), _).\n"
            ":- py_call(importlib:import_module('pln_cost.benefit_selection'), _).\n"
            + (project / "src/pln_cost/benefit_selector.pl").read_text())


def configure(model, mode, query, scope=SCOPE):
    if mode not in MODES:
        raise ValueError("Unknown usefulness policy")
    return ("!" + config_expression(model, "N") + "\n!" +
            expression(["benefit_config", mode, query, scope]) + "\n")


def selection_fixture(case, config, budget, model, mode, scope=SCOPE):
    if case["marginals"] != {}:
        scope = "unknown"
    return (configure(model, mode, case["query"], scope) + fixture(case, config, budget)
            + "!(println! (BENEFIT_STATS (benefit_stats)))\n")
