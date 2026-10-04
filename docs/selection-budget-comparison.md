# Step 5: frozen cost-informed selection under CPU budgets

**Completed: all 6,048 scheduled measurements passed execution, state and proof validation. This immediate-cost tie-breaker did not improve the measured outcomes over native selection.** Its median first-answer CPU was higher on all 21 cases. Under budgets of 0.25–16 ms, it never succeeded in a paired trial where native selection failed; native selection succeeded in 599 paired trials where it failed. All three policies reached verified answers in every generous-budget trial.

This experiment compares the three policies validated in [Step 4](cost-selector-validation.md): native confidence/queue-order selection (N), the same selection with feature/prediction overhead (O), and minimum predicted expansion cost among maximum-confidence candidates (C). It tests this particular immediate-cost tie-breaker, not a benefit-aware policy or a reproduction of BMPS/DQN.

The result establishes a budget-dependent consequence of the tested selection change, extending the earlier expansion-cost measurements. **It does not establish that computational-cost information is generally harmful, or that a different cost-and-benefit policy would help.** Neither claim was tested.

## Verified answers within CPU budgets

Each cell counts on-time, independently verified answers. At each budget and for each policy, the denominator is **180 development trials** (15 cases × 12 repetitions) or **72 held-out trials** (6 cases × 12 repetitions). These are repeated timings on deterministic synthetic cases, not hundreds of independent reasoning problems.

| CPU budget | Development N /180 | Development O /180 | Development C /180 | Held-out N /72 | Held-out O /72 | Held-out C /72 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.25 ms | 0 | 0 | 0 | 0 | 0 | 0 |
| 0.5 ms | 9 | 0 | 0 | 0 | 0 | 0 |
| 1 ms | 55 | 8 | 0 | 0 | 0 | 0 |
| 2 ms | 93 | 33 | 22 | 26 | 0 | 0 |
| 4 ms | 144 | 85 | 44 | 47 | 2 | 0 |
| 8 ms | 168 | 106 | 70 | 54 | 41 | 0 |
| 16 ms | 168 | 150 | 100 | 71 | 48 | 0 |
| 1 s, separate generous endpoint | 180 | 180 | 180 | 72 | 72 | 72 |

Across the seven tight budgets there are 1,764 N/C pairs, matched by case, budget and repetition: **236 both succeed, 929 neither succeeds, 599 N-only successes, and zero C-only successes**. The all-failure small-budget cells provide no evidence of a policy advantage. The generous endpoint supplies another 756 runs; all succeed, so its latency comparisons do not discard failed queries.

See the [per-case/per-budget summary](../results/selection/step-05/run001/summary.json) and [coverage-checked aggregate analysis](../results/selection/step-05/run001/analysis.json).

## Complete-query CPU and controls

The table gives median first-answer CPU across the 12 generous-budget runs per case and policy. Every cell represents **12/12 verified answers**. The final column is the median of the 12 paired C/N CPU ratios; it need not equal the ratio of the separately calculated medians.

| Case | Split | N, ms | O, ms | C, ms | Paired C/N |
| --- | --- | ---: | ---: | ---: | ---: |
| n001-canonical_ids | Development | 0.592 | 1.193 | 1.740 | 2.86× |
| n001-swap_ready_facts | Development | 0.608 | 1.296 | 1.524 | 2.65× |
| n001-seeded_shuffle | Development | 0.660 | 1.738 | 1.714 | 2.33× |
| n004-canonical_ids | Development | 1.134 | 2.703 | 5.091 | 5.10× |
| n004-swap_ready_facts | Development | 1.132 | 2.949 | 5.016 | 4.72× |
| n004-seeded_shuffle | Development | 1.149 | 3.050 | 5.228 | 4.64× |
| n016-canonical_ids | Development | 2.785 | 13.027 | 62.368 | 22.49× |
| n016-swap_ready_facts | Development | 3.106 | 13.107 | 57.200 | 19.10× |
| n016-seeded_shuffle | Development | 3.214 | 16.550 | 60.415 | 18.84× |
| necessary-w004-canonical_ids | Development | 1.135 | 2.631 | 13.576 | 12.21× |
| necessary-w004-swap_required_pair | Development | 1.371 | 2.810 | 11.967 | 8.70× |
| necessary-w004-seeded_shuffle | Development | 2.485 | 6.907 | 12.154 | 4.35× |
| necessary-w016-canonical_ids | Development | 4.585 | 15.105 | 86.446 | 18.93× |
| necessary-w016-swap_required_pair | Development | 3.611 | 14.006 | 88.948 | 24.16× |
| necessary-w016-seeded_shuffle | Development | 35.875 | 159.827 | 91.811 | 2.56× |
| shared-w008-canonical_ids | Held-out | 1.860 | 5.798 | 28.333 | 14.87× |
| shared-w008-swap_required_pair | Held-out | 1.749 | 5.508 | 30.428 | 14.76× |
| shared-w008-seeded_shuffle | Held-out | 8.439 | 25.805 | 26.545 | 3.26× |
| modules-w004-canonical_ids | Held-out | 2.007 | 6.831 | 55.688 | 30.14× |
| modules-w004-swap_required_pair | Held-out | 2.295 | 6.869 | 57.550 | 25.95× |
| modules-w004-seeded_shuffle | Held-out | 12.664 | 41.310 | 61.394 | 4.54× |

**Prediction overhead matters.** O preserves N's logical sequence, yet its median first-answer CPU is higher on every case. Its case-level median paired O/N ratios range from 1.92–5.04 on development cases and 2.95–3.59 on held-out cases. Across generous runs, median selector-window CPU fractions are 33.0% for N, 76.2% for O and 76.3% for C. Feature-window fractions are 0%, 52.5% and 49.9%, respectively. These windows overlap and include native priority work; they must not be added together or interpreted entirely as incremental predictor overhead. Total query CPU is the primary accounting boundary.

**Cheaper expansions can delay useful work.** The [validated width-4 trace](../results/selection/step-04/run001/policies/n004-canonical_ids/C/audit.stdout.txt) shows C selecting five cheap `Certificate -> Goal` rules before their certificates exist. Those selections add no beliefs. Certificates subsequently have lower confidence than the remaining input statements and must wait. This example reaches its first proof in 13 expansions under C versus four under N/O; the present measurements establish the corresponding total-CPU regression, including overhead.

**Fewer expansions still need not mean less CPU.** In `necessary-w016-seeded_shuffle`, C requires 40 expansions versus 58 for N/O. It is faster than O in 11/12 paired generous trials (median paired C/O ratio 0.645), but slower than N in all 12 (median paired C/N ratio 2.56). Changing the order helps relative to the already overhead-burdened control on this case, without overcoming the net cost relative to native selection. C/O differences include the interaction between the changed states, prediction work and inference; they are not an isolated subtraction of a constant overhead.

**Timing variation is retained.** C is faster than N in one of the 252 generous paired trials: `n001-canonical_ids`, repetition 8, C = 1.396 ms versus N = 1.518 ms ([C record](../results/selection/step-05/run001/runs/04105/result.json), [N record](../results/selection/step-05/run001/runs/04106/result.json)). Its median remains slower on that case. This exception was neither excluded nor treated as a reproducible speedup. Case ratios and all individual paired ratios are saved in the aggregate analysis; no statistical significance or population-generalization claim is made.

## Comparison contract

The [frozen protocol](../configs/selection-comparison.json) specifies seven loaded-query CPU budgets: 0.25, 0.5, 1, 2, 4, 8 and 16 ms, plus a separate generous 1-second cap for time-to-first-proof measurements. Every case/budget/policy combination receives 12 repetitions. All six policy orders occur twice within each case/budget; case/budget blocks are shuffled within repetition. The complete schedule is saved before held-out audits or measurements.

The 15 development cases and six held-out cases remain separate. The latter use shared side consequences or an additional disconnected module, as defined in the [data-collection record](cost-data-collection.md). They supplied no training timing labels. Neither the fitted model nor its features, policies or budgets may change in response to evaluation outcomes. This is a small synthetic task-family test, not an estimate of general PLN performance.

Each query runs serially in a fresh native process without inference warmup. The same pinned PLN rules, evidence guards, queues, step cap, stopping objective and timing wrapper apply to all arms. N preserves the native choice under the shared experimental hook; it is not an uninstrumented-runtime comparison.

## Outcome and accounting

A successful query returns a Goal with strength 1 and confidence at least 0.729, with an independently replayed proof, within its CPU budget. This measures a justified derivation under the permitted PLN rules, **not empirical probability accuracy**. Deadline checks are cooperative between expansions. An expansion can overrun the limit; actual CPU and overshoot are retained. A late answer is not an on-time success.

Loaded-query engine CPU includes selection, feature acquisition, prediction, inference, queue management, goal/deadline checks and telemetry. Process startup, library/static-model loading, parent orchestration and offline proof replay are excluded. Selection counters are diagnostic; their time is never subtracted from the outcome. The generous endpoint still records failures rather than silently reporting latency only for successful runs.

Saved audited trajectories establish the allowable state sequence for each case/policy. Development audits are reused from Step 4. Held-out audits additionally compare every transition against the native one-expansion loop and verify N/O sequence equality. Each timed run must match the appropriate audited state at its actual stopping step. Proof replay uses only that trace prefix; a later proof cannot rescue an earlier deadline miss. Invalid executions remain distinct from valid deadline misses and are retained without replacement.

There are 63 validated case/policy audit trajectories, all reaching verified proofs; the 18 held-out trajectories add 352 native transition checks. Coverage checks confirm exactly 12 measurements for every case/budget/policy combination, exact agreement with the saved schedule and independent recomputation of the saved summary. Frozen source/model hashes and native revision checks passed at the end of the measurement run. The UI interruptions did not restart the process or replace measurements.

Across all 6,048 runs, the outcomes are **2,300 on-time successes, 3,739 deadline stops and nine late returns** (eight N, one O). There are no invalid executions, exhausted searches or prediction fallbacks. Late returns remain misses. Maximum observed overshoot is 3.250 ms for N, 35.561 ms for O and 7.039 ms for C. These are observed maxima, not guaranteed bounds: cooperative deadlines do not provide hard real-time preemption.

## Scope of the finding

Within this pinned implementation, task family, machine and protocol, the frozen C policy produced worse median first-answer CPU on every case and fewer on-time verified answers than N. O demonstrates a substantial overhead cost even when the selection sequence is unchanged; inspected trajectories also demonstrate that minimizing immediate expansion cost can prefer work that makes no proof progress. This experiment does not identify how much loss would remain with a perfect cost predictor or a different feature implementation.

The six held-out cases test limited structural transfer within the constructed family, not general reasoning ability. All policies retain confidence priority, and the objective is one valid derivation with the stipulated truth values. There is no empirical probability-accuracy comparison, learned estimate of reasoning benefit, global route optimizer, ECAN change, or demonstration of a general Hyperon defect. The result is a negative controlled pilot for this particular cost-only selection rule. It neither establishes nor rules out gains from other ways of using computational-cost information.

## Evidence and reproduction

- [Comparison runner](../scripts/run_selection_comparison.py)
- [Balanced scheduling and failure-preserving summaries](../src/pln_cost/comparison.py)
- [Scheduling/denominator tests](../tests/test_comparison.py)
- [Batch report](../results/selection/step-05/run001/report.json)
- [Frozen schedule](../results/selection/step-05/run001/schedule.json)
- [Individual measurements](../results/selection/step-05/run001/runs.jsonl)
- [Saved-data analysis script](../scripts/summarize_selection_comparison.py)
- [Coverage-checked analysis and input hashes](../results/selection/step-05/run001/analysis.json)
- [Saved-artifact integrity checks](../results/selection/step-05/run001/artifact-integrity.json)

Reproduce measurements with `python3 scripts/run_selection_comparison.py --run-id NEW_ID`. The runner refuses an existing output directory, verifies frozen source/model/data hashes, retains raw native outputs and per-run execution metadata, and performs no fitting. Recompute only the analysis with `python3 scripts/summarize_selection_comparison.py results/selection/step-05/run001`; this launches no experiments. All 90 unit tests passed before starting native measurements. No concurrent tests or other agent-launched experiments ran during the sweep. The analysis script was added after measurement and does not change the frozen policy code.

Step 5 stops here for review. No model was retuned and no commit was made.

Suggested commit message: `Benchmark frozen PLN cost-informed selection across CPU budgets`
