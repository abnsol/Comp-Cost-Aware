# Step 4: fitted cost estimator and validated selection hook

The first cost-informed tie-breaker is implemented and validated. It uses a small supervised CPU predictor, not a DQN or a learned estimate of reasoning benefit. It preserves native confidence priority and changes only which equally prioritized statement is expanded next. The model is frozen; the repeated CPU-budget comparison and held-out performance evaluation have not run.

## Estimator and data separation

Training used the **941 qualified development rows** from [Step 3](cost-data-collection.md). The 109 instrumentation-unresolved rows were not fitted, and none of the six reserved evaluation cases supplied timing labels. All ten prospective structural features retain their original definitions.

The model is weighted ridge regression on log expansion CPU:

```text
predicted_CPU_ns = exp(intercept + sum_j weight_j * (feature_j - mean_j) / scale_j)
```

Training balances structures, states within structures, and qualified candidates within states. The log target ensures positive predictions without treating a negative linear estimate as a valid duration. A constant feature receives scale 1; `same_term_disjoint` is zero throughout training and its fitted coefficient is zero. The data therefore do not teach a revision-cost effect.

Model selection used five leave-one-structure-out folds: original widths 1, 4 and 16, and necessary-work widths 4 and 16. All orderings and checkpoints of a structure stayed together. The prespecified ridge strengths were 0.001, 0.01, 0.1 and 1.0; **0.01** minimized mean absolute log error averaged across groups. Parameters were then fitted on all 941 qualified rows and saved before any policy rollout inspection. No policy validation result was used to retune the model.

| Withheld development structure | Qualified validation rows | Median absolute CPU prediction error |
| --- | ---: | ---: |
| Original width 1 | 24 | 87.55% |
| Original width 4 | 83 | 15.93% |
| Original width 16 | 413 | 14.12% |
| Necessary-work width 4 | 107 | 19.20% |
| Necessary-work width 16 | 314 | 26.41% |

These are development cross-validation errors used for model selection, not final held-out performance or probabilistic-answer accuracy. The small-width error is substantial and must remain visible. In-sample median absolute prediction error was 15.33%; it is not a generalization estimate. The recorded offline training/model-selection CPU was approximately 1.24 seconds, using NumPy 2.5.3; data collection costs are separate.

See the [frozen model](../results/selection/step-04/run001/model.json), [cross-validation records](../results/selection/step-04/run001/cross-validation.json), and [prespecified model protocol](../configs/cost-model-protocol.json).

## Faster acquisition and runtime integration

The initial Python implementation revalidated and reparsed every belief for every candidate. The new Python reference shares record parsing within a selection. The live adapter calculates the same features directly inside the existing SWI/PeTTa process, avoiding a Python subprocess round trip for each selection. Python still handles model fitting, orchestration and independent validation. There is no change to native inference rules or queue updates.

Feature vectors matched exactly across the original Python implementation, shared Python implementation and native adapter on **all 1,050 saved candidate/state pairs**, including rows whose CPU labels were unresolved. Twenty acquisition probes per state gave these descriptive summaries across the 56 states:

| Feature-acquisition implementation | Median across state medians | Range of state medians |
| --- | ---: | ---: |
| Original Python, previous run | 3.241 ms | 0.119–32.710 ms |
| Shared-parsing Python reference | 0.391 ms | 0.079–3.373 ms |
| Native adapter probe | 0.462 ms | 0.089–3.728 ms |

The native probe includes identification of maximum-confidence candidates using the native priority mechanism as well as feature acquisition. Some of this priority work is also required by the baseline; the whole probe is **not** an isolated estimate of incremental cost-estimation overhead. Its median ratio to the corresponding previously measured typical expansion is still 3.68. The native probe is not faster than shared Python at every state; the reason for the engine adapter is also to avoid data crossings and keep all online work inside a common CPU boundary.

The original and new diagnostics were collected in separate runs, so these summaries are descriptive before/after measurements rather than a randomized speedup trial. Feature preparation and prediction are still nontrivial costs. No overhead is removed from the upcoming query evaluation.

## Exact selection behavior

- **N — native:** use the original confidence/queue-order choice.
- **O — overhead control:** obtain features and predictions for the maximum-confidence candidates, then retain the native choice.
- **C — cost-informed:** among those same candidates, choose the minimum predicted expansion CPU; equal estimates retain queue order.

O and C skip prediction when there is a single eligible candidate. If any prediction is nonpositive, nonfinite or cannot be computed, the whole selection falls back to the native choice. The model is a predictor of immediate expansion CPU, not remaining proof cost, proof relevance or eventual answer quality. It does not decide when to stop.

The generated MeTTa library replaces only the candidate-selection call in the native derivation loop. Rules, evidence guards, deduplication, trimming and confidence-based queue removal remain native. The original source checkout is unchanged.

Static model loading happens outside the loaded-query timing window. Query-specific feature acquisition, prediction, selection, inference and goal/deadline checks happen inside it. Per-query telemetry resets after the start clock. The selection-time counters are diagnostic windows, not a subtraction from total CPU. Their bookkeeping and clock overhead are charged. N has the same hook/telemetry wrapper, so it is the native selection policy under a shared experimental adapter, not an assertion of zero adapter overhead.

## Behavioral and proof validation

The [validation report](../results/selection/step-04/run001/report.json) passed with 169 native processes:

- 56 feature-parity/probe processes.
- Audited and quiet executions of N, O and C on all 15 development cases: 90 runs.
- 15 batched independent checks of **363 C-selected transitions** against the native one-expansion loop.
- Eight native edge checks: equal estimates, invalid-estimate fallback, singleton candidate, unequal confidence, zero budgets in all three arms, and absent query.

Every audited selection matched the independent Python policy reference. N and O preserved the saved native state trajectory. C's new state transitions matched native inference with the same selected statement. All 45 case/policy combinations reached independently replayed first-answer proofs, and their quiet runs matched the audited checkpoints. No invalid or later proof was used to rescue an earlier answer. The existing deadline validator checks that an over-budget return cannot be accepted as on time. All **88 unit tests passed before the native probes**; no concurrent agent-launched tests ran during them.

## What changed in the reasoning sequences

The hook changes behavior, and the change is not uniformly favorable even in expansion counts:

| Development case | N/O expansions to first proof | C expansions to first proof |
| --- | ---: | ---: |
| Original width 1, canonical | 4 | 7 |
| Original width 4, canonical | 4 | 13 |
| Original width 16, canonical | 4 | 37 |
| Necessary-work width 16, canonical | 3 | 40 |
| Necessary-work width 16, shuffled | 58 | 40 |

Across all 15 cases C used more expansions in 14 and fewer in one. These are verified logical sequence counts. They are **not** CPU speedup estimates: operations differ in cost, and selection overhead also matters. The one quiet run per case/arm validates execution; it is not the prespecified repeated policy comparison.

The [canonical width-4 C trace](../results/selection/step-04/run001/policies/n004-canonical_ids/C/audit.stdout.txt) explains a concrete failure mechanism:

1. C first selects the five `Certificate -> Goal` implication records while their certificates are absent. Each adds no belief.
2. It later produces certificates, but the remaining confidence-0.9 input statements still outrank those confidence-0.81 certificates.
3. The first Goal appears only at expansion 13, when a certificate is finally selected and uses its goal implication from the belief buffer.

The policy is doing what its objective specifies: preferring predicted-cheap work. Cheap inapplicable rules can be unproductive. This is evidence of a limitation of this particular cost-only tie-breaker, not proof that computational-cost information cannot improve a benefit-aware policy. It also demonstrates why an accurate duration estimate alone is insufficient.

## Review boundary and next step

The model and adapter are frozen for the next comparison. Do not retune them after observing the above sequences or drop unfavorable cases. Run the common N/O/C budget sweep, retain failures and overshoot, and keep development results separate from the six reserved evaluation cases. Only that comparison can establish the net CPU/deadline effect of this implementation. A relevance/benefit-aware policy would be a separately defined and ablated experiment.

This ridge model and tie-breaking rule are our first experimental baseline; they are not presented as a reproduction of BMPS, DQN or another paper's method. No empirical probabilistic-accuracy gain, Hyperon-wide integration or ECAN deficiency is established.

Code for review:

- [Python features, fitting and selection reference](../src/pln_cost/cost_model.py)
- [Native scoring adapter](../src/pln_cost/cost_selector.pl)
- [Generated hook and trace checks](../src/pln_cost/cost_selection.py)
- [Training/validation runner](../scripts/validate_cost_selection.py)
- [Targeted tests](../tests/test_cost_model.py)

Reproduce with `python3 scripts/validate_cost_selection.py --run-id NEW_ID`. Existing output directories are never overwritten. No files from prior experiment batches or native repositories were changed. No commit was made.

Suggested commit message: `Fit PLN cost estimator and validate confidence-tie selection adapter`
