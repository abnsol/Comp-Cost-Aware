# Usefulness-guided PLN selection: completed CPU-budget comparison

**The frozen 10,368-query benchmark completed and passed verification. Adding predicted expansion cost did not demonstrate a consistent net advantage over the same usefulness heuristic without predictions.** On reserved cases, BC produced 348 on-time verified answers versus B's 361 across the seven tight budgets. Latency outcomes varied, including some favorable BC measurements. This is a bounded result for this implementation and synthetic task family, not evidence that cost information is generally harmful.

## What was compared

All four policies preserve maximum-confidence priority and native PLN inference. N uses native queue-order tie-breaking. B adds the reviewed structural usefulness categories; BO makes the same choices as B while acquiring and ignoring cost predictions; BC uses the frozen predictor to choose the cheapest predicted immediate expansion within the best usefulness category. **BC versus B is the primary incremental-cost comparison.** B versus N measures usefulness guidance, including its acquisition overhead.

The [frozen protocol](benefit-cost-benchmark-protocol.md) specifies 15 development and 12 reserved cases, seven tight budgets, a separate 1-second endpoint, and 12 repetitions. Reserved cases use widths 8 and 32 in two known constructions, with three input orders each. These are four family/size profiles, not twelve independent task families. [Qualification](benefit-cost-benchmark-readiness.md) established native transitions and valid proofs before timing; all guided policies used two expansions on these cases. No policy or model was changed after reserved outcomes were inspected.

Queries ran serially in fresh processes with balanced policy ordering. Loaded-query CPU includes embedded Python conversion/classification, cost features/predictions, selection, inference, queues, deadline checks and return bookkeeping. Startup, static loading, parent orchestration and offline proof replay are excluded consistently. The recorded host was an Intel Core i5-8265U, Linux, with eight logical CPUs in the allowed affinity set. Runs were not pinned to a single core; no per-query frequency/core attribution was recorded.

An accepted answer is the target Goal with strength 1, confidence at least 0.729 within tolerance, and an independently replayable derivation under the permitted pinned PLN formulas. **This measures timely valid derivation, not empirical probability accuracy.**

## Verified answers under CPU budgets

Every development cell has denominator **180** (15 cases × 12 repetitions); every reserved cell has denominator **144** (12 × 12). The generous row is separate from the tight-budget totals.

| Budget, ms | Dev N | Dev B | Dev BO | Dev BC | Reserved N | Reserved B | Reserved BO | Reserved BC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.5 | 16 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 1 | 51 | 8 | 3 | 9 | 0 | 0 | 0 | 0 |
| 2 | 97 | 42 | 33 | 31 | 42 | 0 | 0 | 0 |
| 4 | 149 | 102 | 92 | 92 | 63 | 34 | 29 | 28 |
| 8 | 168 | 152 | 139 | 150 | 89 | 70 | 70 | 69 |
| 16 | 168 | 179 | 178 | 179 | 122 | 113 | 105 | 107 |
| 32 | 171 | 180 | 180 | 180 | 131 | 144 | 140 | 144 |
| 1,000 (generous) | 180 | 180 | 180 | 180 | 144 | 144 | 144 | 144 |

Across the tight budgets, BC/B paired outcomes were:

| Split | BC succeeds, B fails | B succeeds, BC fails | Both succeed | Neither succeeds | Total pairs |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development | 34 | 56 | 607 | 563 | 1,260 |
| Reserved | 30 | 43 | 318 | 617 | 1,008 |

Thus cost information had observed wins **and** losses; B had more on-time answers overall in both splits. Reserved BC did not exceed B's aggregate success count at any prespecified tight budget. All-failure and all-success cells provide no success-rate distinction. These counts pool repeated timings and budgets from the same small case set; they are not counts of independent reasoning problems or a population-level significance result.

Native N also remained strong: it returned 820 development and 447 reserved on-time answers across tight budgets, compared with B's 663 and 361. At 32 ms, however, B and BC both solved all reserved trials while N solved 131/144. The usefulness intervention therefore helped some expensive native searches while its overhead hurt elsewhere. This does not support a uniform improvement claim.

## First-answer CPU at the generous endpoint

All **1,296 generous-endpoint runs succeeded** (27 cases × four policies × 12 repetitions), so this table does not omit failed queries. Values are per-case median milliseconds. The BC/B column is the median of the 12 matched CPU ratios, **not** the ratio of the two separately computed medians. Ratios below 1 favor BC; the final column gives its faster paired trials. `reserved-` identifies the reserved split.

| Case | N, ms | B, ms | BO, ms | BC, ms | Paired BC/B | BC faster |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| n001-canonical_ids | 0.542 | 1.330 | 1.135 | 1.340 | 1.227 | 5/12 |
| n001-swap_ready_facts | 0.562 | 1.101 | 1.598 | 1.931 | 1.568 | 1/12 |
| n001-seeded_shuffle | 0.629 | 1.557 | 1.353 | 1.420 | 1.048 | 5/12 |
| n004-canonical_ids | 0.875 | 2.345 | 3.118 | 3.843 | 1.174 | 3/12 |
| n004-swap_ready_facts | 1.027 | 3.142 | 2.947 | 2.206 | 0.821 | 8/12 |
| n004-seeded_shuffle | 1.088 | 1.858 | 3.414 | 2.349 | 1.245 | 2/12 |
| n016-canonical_ids | 2.571 | 5.651 | 5.810 | 6.479 | 1.176 | 4/12 |
| n016-swap_ready_facts | 3.210 | 7.211 | 9.011 | 9.972 | 1.109 | 3/12 |
| n016-seeded_shuffle | 2.994 | 5.886 | 9.176 | 6.483 | 1.081 | 5/12 |
| necessary-w004-canonical_ids | 0.981 | 2.805 | 3.093 | 3.807 | 1.159 | 4/12 |
| necessary-w004-swap_required_pair | 1.653 | 4.533 | 3.424 | 3.785 | 1.093 | 5/12 |
| necessary-w004-seeded_shuffle | 2.373 | 2.673 | 4.144 | 2.601 | 1.060 | 4/12 |
| necessary-w016-canonical_ids | 3.525 | 7.444 | 8.778 | 10.121 | 1.057 | 4/12 |
| necessary-w016-swap_required_pair | 3.542 | 10.882 | 10.228 | 8.234 | 0.886 | 9/12 |
| necessary-w016-seeded_shuffle | 35.427 | 8.127 | 8.806 | 8.312 | 0.993 | 8/12 |
| reserved-alternative-w008-canonical_ids | 1.713 | 5.168 | 3.895 | 3.366 | 0.708 | 7/12 |
| reserved-alternative-w008-swap_ready_facts | 1.650 | 3.966 | 5.570 | 4.264 | 0.958 | 7/12 |
| reserved-alternative-w008-seeded_shuffle | 1.997 | 4.525 | 3.620 | 3.239 | 0.998 | 6/12 |
| reserved-alternative-w032-canonical_ids | 6.090 | 10.384 | 15.929 | 15.739 | 1.289 | 1/12 |
| reserved-alternative-w032-swap_ready_facts | 6.873 | 15.863 | 24.991 | 15.103 | 0.957 | 9/12 |
| reserved-alternative-w032-seeded_shuffle | 25.482 | 11.714 | 17.410 | 17.198 | 1.382 | 1/12 |
| reserved-necessary-w008-canonical_ids | 2.150 | 6.655 | 5.323 | 5.200 | 0.998 | 6/12 |
| reserved-necessary-w008-swap_required_pair | 1.713 | 4.956 | 6.209 | 5.374 | 0.996 | 6/12 |
| reserved-necessary-w008-seeded_shuffle | 5.238 | 4.881 | 5.032 | 5.351 | 1.054 | 5/12 |
| reserved-necessary-w032-canonical_ids | 9.406 | 19.618 | 17.116 | 17.116 | 1.014 | 5/12 |
| reserved-necessary-w032-swap_required_pair | 9.056 | 17.275 | 19.383 | 20.674 | 1.126 | 3/12 |
| reserved-necessary-w032-seeded_shuffle | 95.214 | 17.268 | 17.810 | 16.478 | 0.995 | 7/12 |

Paired median BC/B was below 1 on 3/15 development cases and 7/12 reserved cases, but BC was faster in only 70/180 and 63/144 individual generous pairs, respectively. Several favorable medians were extremely close to 1. Keep both the gains and losses; counting favorable case medians alone overstates the evidence.

A useful distinction is visible in three cases where B substantially shortened native searches: `necessary-w016-seeded_shuffle` had paired B/N median **0.238** (B faster 12/12); reserved alternative width 32 shuffled had **0.490** (11/12); reserved necessary width 32 shuffled had **0.195** (12/12). These gains are achieved by **usefulness guidance without cost predictions**. On the reserved alternative width-32 shuffled case, adding cost instead increased paired CPU relative to B: median BC/B **1.382**, with BC slower in 11/12 trials.

There are also favorable cost-associated observations, such as reserved alternative width 32 with swapped Ready facts: paired BC/B **0.957**, with BC faster in 9/12 trials. But the interquartile range of paired ratios was **0.883–1.230**, and the reserved tight-budget totals did not improve. This remains a mixed pilot outcome, not established reliable acceleration.

## Overhead and timing variability

On generous runs, median selector-window fractions of total query CPU were **32.9% N, 83.3% B, 84.5% BO and 85.2% BC**. Descriptor-window fractions were **71.3% B, 65.0% BO and 65.5% BC**. Cost-feature windows accounted for median **5.4%** in both BO and BC. These windows overlap; do not add their percentages or interpret the feature window as the entire prediction overhead. No coverage or prediction fallbacks occurred.

The descriptions and their bridge are substantial measured costs in this implementation. This supports overhead as an important limitation, but does not isolate how much performance would change under a different implementation. No overhead was subtracted from the reported query CPU.

Timing variation is material and retained. On reserved alternative width 8 canonical, BC/B had median **0.708**, yet B and BC followed the **same state sequence**; BC was faster in 7/12 pairs and slower in 5/12, with ratio quartiles **0.517, 0.708, 1.153**. This observation cannot be credited to choosing a better reasoning sequence. BO also had lower paired median CPU than B on five reserved cases despite doing additional prediction work. The exact cause of the variability was not measured; a process CPU clock and balanced ordering do not remove all runtime or hardware variation. No statistical significance claim is made, and small latency differences remain inconclusive.

## Verification and retained failures

The [runner report](../results/benefit-benchmark/run001/measurement/report.json) records completion with no invalid executions. The [post-run audit](../results/benefit-benchmark/run001/measurement/verified-analysis.json) checked every scheduled slot, individual result versus JSONL, **31,104 native fixture/output hashes**, frozen source/input/audit hashes, telemetry versus audited prefixes, raw-output metrics, and the saved aggregates. It reconstructed independent split/budget and paired outcome counts. The [analysis script](../scripts/analyze_benefit_benchmark.py) performs no native experiments.

All **5,557 detected proofs** were replayed again against their captured native prefixes and checked against saved certificates. There were **5,545 on-time successes, 4,814 deadline outcomes and nine late returns**, with no exhausted or invalid executions. Twelve detected proofs were not on-time successes: nine late returns and three deadline outcomes where the deadline was crossed during goal checking. All remain misses. A proof found after the allowed computation does not rescue an earlier deadline failure.

Deadlines are cooperative between expansions. Maximum recorded overshoot was **6.946 ms N, 18.569 ms B, 29.094 ms BO and 17.779 ms BC**. These are observations, not real-time guarantees. The [complete summary](../results/benefit-benchmark/run001/measurement/summary.json) retains per-case/budget results, paired ratios and their spread; [all individual records](../results/benefit-benchmark/run001/measurement/runs.jsonl) remain available.

## Conclusion within scope

The benchmark demonstrates that structurally guided selection can shorten some native searches enough to overcome its overhead, while being slower or less successful elsewhere. **It does not establish a consistent incremental benefit from this immediate-cost tie-breaker over the matched usefulness-only baseline.** The result includes positive, negative and inconclusive observations. It neither establishes an ECAN/PLN defect nor evaluates general benefit–cost reasoning, arbitrary PLN rule profiles, delayed utility prediction, calibrated answer accuracy, or a BMPS/DQN reproduction.

The full planned batch is complete; no additional experiments or parameter changes were made during analysis. Stop here for review.

Suggested commit message: `Record verified usefulness and cost benchmark results`
