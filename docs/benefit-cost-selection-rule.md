# Proposed usefulness-guided cost comparison

**Status: rule for review, not implemented or tested.** This specifies the next bounded comparison after [descriptor validation](benefit-signal-validation.md). It preserves the [negative cost-only result](selection-budget-comparison.md): the earlier cheapest-expansion selector had higher median first-answer CPU than native selection on all 21 cases. No improvement from the rule below has been established.

## Question and objective

Does predicted expansion cost improve on-time verified-answer success when added to the **same structural usefulness heuristic**, after charging all online overhead?

Retain the existing objective: return `CanOperate(unit0)` with strength 1, confidence at least 0.729 within tolerance, and an independently replayable native proof. Measure on-time success across CPU budgets and first-answer CPU at a separate generous endpoint. This concerns valid derivation, not empirical probability accuracy.

## Concrete selection rule

1. Find the maximum-confidence pending candidates using native confidence semantics. If only one remains, select it without usefulness or cost acquisition.
2. Otherwise obtain the current-state descriptors from the [validated description layer](../src/pln_cost/benefit_signals.py). Its present implementation describes all pending candidates; that full acquisition work must be charged even though selection remains restricted to maximum confidence.
3. Assign each eligible candidate the highest applicable category below. Retain only candidates in the highest category present.
4. Resolve the remaining tie according to the comparison arm. Select one pending statement, then execute its complete, unchanged native expansion.

| Priority | Condition from current-state descriptors | Interpretation and limitation |
| --- | --- | --- |
| 2 | `potential_goal_pairs > 0` | An applicable MP pair could produce the query. Its truth values and proof acceptance remain unverified until execution. |
| 1 | `missing_intermediate_pairs + represented_support_pairs > 0` | An applicable MP pair could produce a term connected to the query by the current implication graph. This is possible support, not proven future benefit. |
| 0 | Neither condition above | No currently applicable MP output with known query support. This includes dormant query rules; it is not a general irrelevance judgment. |

Use categories, not output counts: four alternative certificates are not assumed to be four times as valuable as one. A required expansion producing a useful certificate and many side facts still receives category 1. All of its actual native work is performed and charged.

**Missing and already represented intermediates share category 1.** Their descriptors remain separate for analysis, but we have not established that novelty is always more valuable than further evidence for a represented term. Nothing is pruned as redundant. Likewise, direct-over-intermediate priority is an explicit heuristic hypothesis, not a validated utility ordering; an apparent Goal could fail the acceptance threshold.

If descriptor coverage is unknown, use the native queue-order choice among maximum-confidence candidates for that whole selection and record the fallback. Do not classify unknown work as category 0. Coverage must be qualified for each workload; the descriptor function is not a general PLN coverage detector.

## Four comparison arms

| Arm | Selection after native confidence filtering |
| --- | --- |
| N: native reference | Native queue order; no usefulness descriptions or cost predictions. |
| B: usefulness only | Highest usefulness category, then current queue order. |
| BO: usefulness plus prediction overhead | Same category and choice as B; predict costs for the final tied contenders but ignore predictions. |
| BC: usefulness plus cost | Same category as B; choose the contender with minimum predicted immediate expansion CPU, then queue order for equal predictions. |

BO and BC skip cost prediction when only one contender survives category filtering. They use identical feature and prediction code on their respective eligible sets. Freeze the [existing cost model](../results/selection/step-04/run001/model.json); do not fit it using evaluation outcomes. New selection trajectories may encounter states unlike its training data, which must remain an explicit limitation. Nonfinite or nonpositive predictions cause the whole cost stage to fall back to B's queue-order choice, with the failure recorded.

The primary incremental-cost comparison is **BC versus B**. B versus N measures the effect of usefulness guidance including its overhead. BO versus B diagnoses the cost of obtaining predictions while preserving choices. BC versus BO compares using versus ignoring predictions, but changed trajectories can change subsequent overhead; it is not a subtraction of a constant prediction cost. A BC improvement over N alone would not establish that cost information helped.

## What this would do on the existing examples

Initially, `ReadyA` and `ReadyB` can produce missing certificates and receive category 1. An applicable `Ready -> Certificate` implication can also receive category 1: implication records are selectable tasks too. A `Certificate -> Goal` rule whose certificate is absent receives category 0. The policy therefore need not consume cheap dormant goal rules ahead of currently useful work, as the earlier cost-only policy did.

After `CertA` exists, its still-pending `CertA -> Goal` rule receives category 2 and can precede other equally confident work. If the rule was already removed from the pending queue, this policy does not reinsert it; it remains usable in the belief buffer under native inference.

In the necessary-work family, an expensive required expansion receives category 1 despite its side outputs, while an idle or side-only expansion receives category 0. This can prefer expensive useful work over cheap unhelpful work. **That preference comes from the shared usefulness heuristic, not from the cost predictor.** B may already make the same useful choices as BC; a neutral or worse BC result must be retained.

These are implications of the proposed rule and validated descriptors, not measured executions of a new selector.

## Accounting, validation and limits

Keep the pinned rules, truth formulas, evidence guards, queues, confidence priority, answer acceptance and stopping behavior identical across arms. No route commitment, task reinsertion, pruning or early stopping rule is introduced. Confidence remains primary even when a lower-confidence candidate appears more useful.

Charge descriptor acquisition, any representation transfer, feature acquisition, prediction, selection, native inference, queue management and deadline/goal checks to total query CPU. If integration involves multiple processes, accounting must cover every participating process rather than only the engine. The existing warm-call Python descriptor measurement—median 0.465 ms across saved-state medians, excluding an engine bridge—is not an integrated runtime estimate. Overhead may erase any search benefit.

Before timing, validate category and tie decisions on saved development states, unknown-coverage and prediction fallbacks, B/BO trace equality, and every changed native transition and returned proof. Any new workload needs its own rule-scope and proof qualification. Preserve cooperative deadline overshoot and late answers as misses; do not hide failures through success-only latency summaries.

Freeze the implemented rule and a measurement protocol before evaluating fresh reserved cases. Previously held-out Step 5 cases have now influenced diagnosis and are historical/development evidence for this next method, not a fresh holdout. Include differing queue orders, necessary expensive work, and cases with no useful cost distinction; do not select evaluation cases only because BC wins. Report repeated timings as repetitions of a small task set, not as independent reasoning problems.

This remains a confidence-tie intervention with cost ranking **within a coarse usefulness category**. It does not optimize complete routes, trade confidence against CPU, estimate deadline-success probability, or establish a calibrated benefit–cost tradeoff. Immediate cost is not remaining proof cost. The [paper review](benefit-cost-review-after-pilot.md) motivates distinguishing computation benefit from cost; these categories and their ordering are our experimental heuristic, not a BMPS or DQN reproduction.

**Review boundary:** this step adds only this specification. Implementation and validation follow after review; no new experiment or selector change is made here.
