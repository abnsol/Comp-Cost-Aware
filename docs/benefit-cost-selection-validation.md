# Usefulness-guided selection: implementation and correctness validation

**The reviewed rule is implemented and passed development-only correctness checks. No new performance comparison was run.** Native inference, truth formulas, evidence guards, queues and answer acceptance remain unchanged. The [previous cost-only regression](selection-budget-comparison.md) remains part of the evidence.

## Implementation

The [Python policy reference and bridge](../src/pln_cost/benefit_selection.py) implement the [reviewed specification](benefit-cost-selection-rule.md). The [Prolog selection hook](../src/pln_cost/benefit_selector.pl) retains native maximum-confidence eligibility and calls the already validated Python descriptor function through PeTTa's embedded Janus bridge. This runs inside the engine process, not a separate Python worker. Python computes descriptions for every pending candidate; the hook applies the categories and selects among maximum-confidence candidates.

Categories prefer an applicable potential Goal output, then an applicable query-connected intermediate, then other work. Missing and represented intermediates share a category. Counts do not multiply value, and no candidate is pruned. A candidate can remain useful despite generating expensive side consequences. These are structural heuristics, not estimated probabilities of success.

The four modes are:

| Mode | Choice after maximum-confidence filtering |
| --- | --- |
| N | Native queue order |
| B | Highest usefulness category, then queue order |
| BO | Same choice as B; compute predictions for the final tied contenders and ignore them |
| BC | Same usefulness category; minimum predicted immediate expansion cost, then queue order on prediction ties |

The [existing model](../results/selection/step-04/run001/model.json) is unchanged; no retraining occurred. All modes skip unnecessary prediction, and guided modes skip description when confidence leaves one candidate. Unknown descriptor coverage falls back to native selection. Invalid predictions fall back to B's choice, preserving usefulness guidance. A potential Goal output still requires actual inference and the existing answer/proof checks.

The only change to the existing audit helper is an optional selection-reference callback. Existing cost-only callers retain their original behavior. The new generated library changes the selection call and uses the existing budget and trace wrappers; external pinned repositories were not edited.

## Validation results

The [saved protocol](../configs/benefit-selection-validation.json) and [completed report](../results/benefit-selection/run001/report.json) cover only the 15 previously qualified development cases and their saved states. Runtime revisions, source/model/input hashes and qualified fixture shapes were checked. Sources and recorded inputs were checked again after execution.

| Check | Result |
| --- | --- |
| Unit suite before native validation | **104 tests passed**, including 7 new selection tests |
| Embedded descriptor bridge | Categories agreed for **1,364 candidates across 56 saved states** |
| Native selection versus Python reference on those states | **224 choices agreed**: four modes per state |
| Complete audit trajectories | **60/60** case/mode combinations returned independently replayed valid proofs |
| Quiet versus audited execution | **60/60** matched the audited stopping state and verified answer |
| Guided expansion versus unchanged native one-step loop | **90/90 ordered queue transitions matched** |
| B versus BO | Identical complete state sequences on **all 15 cases** |
| N versus archived native trajectory | Matched on **all 15 cases** |
| Native edge probes | Equal/invalid predictions, unknown coverage, singleton, unequal confidence, changing dependencies, and zero-budget stopping passed |

The 231 native subprocess executions include saved-state probes, audited queries, quiet queries, forced one-step transition checks and edge probes. They are correctness executions, not repeated latency trials or independent sampled reasoning tasks. The 10-second validation cap is a safety/correctness allowance, not a tested operating-budget recommendation. No formerly held-out cases or fresh evaluation cases were used.

The Python reference independently applies category filtering and cost ranking; the native hook performs those choices separately. Both deliberately share the Python descriptor implementation. Thus bridge parity does not independently establish descriptor semantics: that rests on the [earlier descriptor validation](benefit-signal-validation.md), including its scan/DFS cross-check and saved native-output checks. Native one-step comparisons verify inference and ordered queue updates. Proof replay checks captured derivations against the permitted formulas; it does not establish empirical probability accuracy.

## Observed selection behavior, with attribution

All 45 guided case/mode combinations reached a verified proof in **two expansions**, whereas native required **3–58** on these development cases. Selected examples:

| Development case | N expansions | B | BO | BC |
| --- | ---: | ---: | ---: | ---: |
| Original width 4, canonical | 4 | 2 | 2 | 2 |
| Original width 4, Ready facts swapped | 4 | 2 | 2 | 2 |
| Original width 4, shuffled | 6 | 2 | 2 | 2 |
| Necessary-work width 4, canonical | 3 | 2 | 2 | 2 |
| Necessary-work width 16, shuffled | 58 | 2 | 2 | 2 |

In [canonical width 4](../results/benefit-selection/run001/policies/n004-canonical_ids/B/audit.stdout.txt), all guided modes select `ReadyA` and then its now-applicable `CertA -> Goal` rule. They avoid consuming that rule while its premise is absent. **B achieves this without cost predictions**, so the expansion reduction is attributable to the changed usefulness ordering, not evidence of an incremental cost-information benefit.

Cost does affect some choices. With the [Ready facts swapped, B](../results/benefit-selection/run001/policies/n004-swap_ready_facts/B/audit.stdout.txt) selects `ReadyB` and then a B goal rule; [BC](../results/benefit-selection/run001/policies/n004-swap_ready_facts/BC/audit.stdout.txt) selects `ReadyA` and its goal rule. Both take two expansions. This confirms that predictions are used; it does **not** establish lower total CPU after acquisition and selection overhead.

In [necessary-work width 16, shuffled, B](../results/benefit-selection/run001/policies/necessary-w016-seeded_shuffle/B/audit.stdout.txt), the first choice is the required `Ready -> Certificate` implication; [BC](../results/benefit-selection/run001/policies/necessary-w016-seeded_shuffle/BC/audit.stdout.txt) chooses the required Ready fact instead. Both perform the native side work and then derive Goal. The shared usefulness category protects necessary expensive work from idle/side-only work; that protection must not be credited to the cost predictor.

No proof-confidence improvement was established. These remain the same synthetic proof objective and accepted truth values. Fewer expansions can still cost more CPU, as the previous experiment demonstrated.

## Accounting and remaining uncertainty

The existing process CPU clock includes online Python–Prolog conversion, complete descriptor construction, category filtering, cost features and predictions, inference, queues, deadline checks and telemetry. Python module/path initialization and static configuration occur before the loaded-query interval, as do existing runtime/library setup costs. Offline reference checks and proof replay remain outside online latency.

Telemetry records `[selection calls, classified candidates, descriptor CPU, predicted candidates, cost-feature CPU, selector CPU, coverage fallbacks, prediction fallbacks, singleton choices]`. Descriptor and feature windows are within selector CPU, which is within total query CPU; these overlapping windows must not be added as separate total costs. Every quiet validation run satisfied those interval relationships. All qualified full-query runs had zero coverage/prediction fallbacks; deliberate edge tests exercised fallback behavior.

The report retains single-run diagnostic CPU values, but they are **not performance estimates**. We have not yet measured whether BC improves on B, whether B improves on N after overhead, or whether either gives more on-time answers under tight budgets. Nor has the cost model been validated on the distribution of states produced by the new selector. The previously measured Python description overhead is not assumed to disappear through integration.

Next, after code review, freeze a separate benchmark protocol with fresh reserved cases and repeated paired budgets. The primary incremental-cost comparison remains BC versus B, with BO diagnosing prediction overhead and N providing the native reference. Retain neutral and negative cases. This implementation remains restricted to confidence ties and coarse structural usefulness categories; it is not a BMPS/DQN reproduction, general PLN benefit estimator or final project proposal.

## Review and reproduction

- [Python policy and embedded bridge](../src/pln_cost/benefit_selection.py)
- [Native selection hook](../src/pln_cost/benefit_selector.pl)
- [Unit tests](../tests/test_benefit_selection.py)
- [Validation runner](../scripts/validate_benefit_selection.py)
- [Completed report and provenance](../results/benefit-selection/run001/report.json)
- [Example captured proof replay](../results/benefit-selection/run001/policies/n004-swap_ready_facts/BC/proof-replay.json)

Run `python3 -m unittest discover -s tests`, then separately `python3 scripts/validate_benefit_selection.py --run-id NEW_ID`. Existing output directories are refused. No installation or fitting is performed.

Suggested commit message: `Implement and validate usefulness-guided PLN cost selection`

No commit was made. Stop here for review before the performance benchmark.
