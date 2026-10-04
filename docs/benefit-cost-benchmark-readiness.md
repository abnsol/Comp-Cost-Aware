# Frozen benchmark: runner and reserved-case qualification

**The runner is implemented and batch `run001` passed qualification. The 10,368-query timing sweep has not started.** This completes the implementation/qualification stage of the [reviewed protocol](benefit-cost-benchmark-protocol.md), without changing the validated selector or retraining its cost model.

## Implementation and controls

The [runner](../scripts/run_benefit_benchmark.py) requires an explicit `prepare` or `measure` phase. Preparation generates and qualifies fixtures, saves the schedule and checks execution. It cannot start the timing sweep. Measurement requires successful qualification, unchanged source/input/audit hashes and a new measurement directory; it refuses to overwrite an existing measurement batch.

The [benchmark helpers](../src/pln_cost/benefit_benchmark.py) implement the prescribed balanced four-arm schedule, audited-prefix telemetry checks, result-coverage checks and failure-preserving summaries. Partial summaries retain planned denominators and distinguish unexecuted slots, invalid executions and valid unsuccessful queries. Paired latency summaries identify when they use only a jointly successful subset. Split totals remain separate for development and reserved cases.

The existing PLN selection, descriptor, cost-model, budget and proof-checker source files remain unchanged. New files implement experiment orchestration and reporting. No BMPS/DQN implementation or new selection method is introduced here.

Before reserved native execution, preparation saved the [freeze record](../results/benefit-benchmark/run001/freeze.json), including source and artifact hashes, the copied model/adapters, generated fixtures, [manifest](../results/benefit-benchmark/run001/manifest.json), authored witnesses and complete [schedule](../results/benefit-benchmark/run001/schedule.json). Recorded source/artifact hashes were checked again after qualification.

## Checks completed

| Check | Result |
| --- | --- |
| Unit suite before preparation | **111 tests passed**, including 7 new benchmark tests |
| Fixture coverage | **15 development + 12 reserved cases** |
| Reserved novelty check | No reserved input multiset duplicated a KB in the prior development/evaluation manifest; three orderings intentionally share each family/width KB |
| Authored witness replay | **42 proofs passed**: 24 development and 18 reserved |
| Revalidated development audit trajectories | **60/60** passed, anchored to saved native trace hashes |
| Newly captured reserved audit trajectories | **48/48** returned independently replayed valid proofs |
| Reserved native one-step comparisons | **204/204** ordered queue transitions matched |
| Quiet execution versus corresponding audit | **108/108** matched stopping states, proofs and expected telemetry counters |
| Usefulness-only B versus overhead-only BO | Identical state sequences on **all 27 cases** |
| Zero-budget checks through the measurement parser | All **four modes** stopped with zero expansions and zero selection calls |

The [qualification report](../results/benefit-benchmark/run001/qualification-report.json) passed with `timing_sweep_started: false`. The 208 new native subprocess executions comprise 60 development quiet checks, 144 reserved audit/transition/quiet executions, and four zero-budget checks. They are correctness checks, not the planned repeated timing measurements.

Authored witnesses establish that the stipulated inputs admit the declared derivation; they are not captured executions. Reserved audit logs supply fresh native derivations. The quiet runs are checked against those captured trajectories and independently replayable proofs. No policy exhausted its search in this qualification batch, although the measurement runner retains exhaustion as a valid unsuccessful outcome if it occurs.

## Reserved-case behavior observed

The following ranges cover the three prespecified input orders for each family/width:

| Reserved profile | Native N expansions | B | BO | BC |
| --- | ---: | ---: | ---: | ---: |
| Alternative routes, width 8 | 4–6 | 2 | 2 | 2 |
| Alternative routes, width 32 | 4–25 | 2 | 2 | 2 |
| Necessary work, width 8 | 3–12 | 2 | 2 | 2 |
| Necessary work, width 32 | 3–61 | 2 | 2 | 2 |

All guided modes reached the accepted proof in two expansions, including B, which does not use cost predictions. Consequently, these counts **do not establish an incremental cost-information benefit**. Different two-expansion sequences may have different execution costs, and description/prediction overhead may outweigh any saving. Only the matched timing comparison can resolve that for this batch.

Examples of newly captured evidence: [width-32 shuffled alternative, native](../results/benefit-benchmark/run001/audits/reserved-alternative-w032-seeded_shuffle/N/audit.stdout.txt), [its BC proof replay](../results/benefit-benchmark/run001/audits/reserved-alternative-w032-seeded_shuffle/BC/proof-replay.json), and [width-32 shuffled necessary work, BC](../results/benefit-benchmark/run001/audits/reserved-necessary-w032-seeded_shuffle/BC/audit.stdout.txt).

These remain four family/size profiles with three orderings each, within two familiar synthetic constructions. Qualification does not establish generalization to arbitrary PLN reasoning, calibrated probability accuracy, accurate cost predictions on new states, or gains under tight budgets. The reserved cases were specified and the method frozen before their native outcomes were inspected; no tuning followed those outcomes.

## Next execution, after review

The prepared batch contains **10,368 scheduled queries**: 27 cases × eight endpoints × four modes × 12 repetitions. The primary comparison remains BC versus B, including all online overhead. There is currently no `measurement/` directory and no new benchmark success-rate or latency result.

Run the already prepared batch with:

```sh
python3 scripts/run_benefit_benchmark.py --phase measure --run-id run001
```

This is the long measurement phase; do not run concurrent tests or other experiment workers. It checks frozen artifacts before execution and again on completion. It preserves raw outputs, proof/state verification, failed queries and invalid executions, stopping after three invalid executions without replacements. After completion, independently check saved-result/aggregate agreement and artifact integrity before interpreting performance.

For reproduction of qualification in a separate new directory:

```sh
python3 -m unittest discover -s tests
python3 scripts/run_benefit_benchmark.py --phase prepare --run-id NEW_ID
```

Suggested commit message: `Prepare and qualify frozen PLN benefit-cost benchmark`

No commit was made. Stop here for code and qualification review before timing.
