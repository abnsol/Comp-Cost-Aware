# Matched benchmark of usefulness guidance with and without cost information

**Status: specified for review; not executed.** The [selector validation](benefit-cost-selection-validation.md) passed, including native transition and proof checks. It established that all guided policies reached a proof in two expansions on the 15 development cases. It did not establish a CPU advantage or an incremental benefit from cost prediction.

This document and the [machine-readable protocol](../configs/benefit-selection-comparison.json) specify the next measurement batch. Only these two files are added in this step; the four-arm benchmark runner and new fixture qualification remain to be implemented. This protocol does not change the selector, fit a model or report new results.

## Question and controlled comparison

**Does adding predicted expansion cost to the same usefulness-guided selection rule increase verified-answer success under CPU budgets, after charging all online overhead?**

| Mode | What it does | Purpose |
| --- | --- | --- |
| N | Native confidence and queue-order selection | Native reference |
| B | Maximum confidence, highest structural usefulness category, queue order | Cost-disabled baseline |
| BO | Same choice as B; acquire cost predictions but ignore them | Prediction-overhead control |
| BC | Same confidence/usefulness filtering; minimum predicted immediate expansion cost | Cost-enabled treatment |

**BC versus B is the primary comparison.** B versus N measures usefulness guidance including its acquisition cost. BO versus B diagnoses prediction overhead on the same reasoning sequence. BC versus BO includes changes to later states and overhead, not subtraction of a constant cost. BC beating N alone would not show that cost predictions helped.

Use the validated [selection implementation](../src/pln_cost/benefit_selection.py), [native hook](../src/pln_cost/benefit_selector.pl) and frozen [existing model](../results/selection/step-04/run001/model.json). Preserve confidence priority, the three usefulness categories, prediction fallbacks, rule semantics, evidence handling, queues, stopping checks and answer acceptance. No learned benefit model, new stopping policy, retraining or parameter tuning is part of this batch.

## Cases specified before results

Retain all **15 development cases** from the [existing manifest](../results/selection/step-03/run002/split-manifest.json): alternative-route widths 1, 4 and 16, and necessary-work widths 4 and 16, with their three existing orders. Do not select a subset because it favored a policy. These cases have influenced implementation and must be reported as development evidence.

Reserve **12 additional cases**, generated from the existing family generators:

| Family | New widths | Three input orders per width | Reason for inclusion |
| --- | --- | --- | --- |
| Alternative certificate routes | 8 and 32 | Canonical, Ready facts swapped, seeded shuffle | Compare cost choices where either route can satisfy the same proof objective |
| Necessary expensive work | 8 and 32 | Canonical, required pair swapped, seeded shuffle | Preserve cases where required work includes unavoidable side outputs |

Use shuffle seed **53** for all new shuffled inputs and four idle distractors in the necessary family. Use the existing generators' term and evidence-ID conventions. The experiment never injects sleeps or artificial cost labels. Width 8 lies between tested widths; width 32 extends beyond them. Neither is presumed to have a particular measured runtime or policy advantage.

These are **four new family/size combinations, each with three orderings**, not twelve independent task families. They test limited size/order transfer within known synthetic constructions. The previous six held-out Step 5 cases are now historical evidence and are excluded from this reserved set. Before native evaluation, check the new fixtures against prior manifested inputs; duplicate old inputs cannot silently be relabeled fresh.

Small development cases and canonical orders remain useful controls: the extra cost work may not alter choices, or its overhead may exceed any saving. Necessary-work cases protect against the misconception that cheaper operations are always preferable, but they do not test calibrated probability accuracy or a general tradeoff between answer qualities. Those remain outside this batch.

## CPU budgets and schedule

Use **0.5, 1, 2, 4, 8, 16 and 32 ms** loaded-query CPU budgets, plus a separate **1-second generous endpoint**. This covers the existing millisecond range and extends it for larger reserved inputs. The earlier all-failure 0.25-ms endpoint is omitted in advance; budgets will not be moved after seeing new results. The generous endpoint is capped, not guaranteed sufficient.

Use **12 repetitions per case/budget/mode**, totaling:

`27 cases × 8 endpoints × 4 modes × 12 repetitions = 10,368 measured queries`.

Run serially in fresh processes, one query per process, with no inference warmup. Keep unrelated tests and experiment workers stopped during measurement. Match comparisons by case, budget and repetition; each four-mode block executes consecutively. The schedule seed is **2311**, with the exact shuffle construction specified in JSON and the resulting job list saved before reserved audits.

Use the following four mode orders, each three times per case/budget:

| Order | First | Second | Third | Fourth |
| --- | --- | --- | --- | --- |
| 1 | N | B | BC | BO |
| 2 | B | BO | N | BC |
| 3 | BO | BC | B | N |
| 4 | BC | N | BO | B |

Across these orders, each mode occupies every position equally and each ordered adjacent pair occurs equally within blocks. This is a balanced subset, **not all 24 permutations**. Shuffle order assignments and case/budget blocks using the prescribed seeds. It mitigates ordering effects without making repetitions independent tasks or eliminating machine variability.

## Qualification and freeze before measurement

1. Implement the new four-arm runner and scheduling/summary checks using development evidence only. The existing N/O/C runner rejects this protocol and must not be silently reused unchanged.
2. Verify the successful [validation report](../results/benefit-selection/run001/report.json), its recorded source hashes, pinned runtimes and the model/config/manifest hashes recorded in this protocol. Save the final runner/source hashes, generated fixtures, split manifest, adapter hashes, protocol and complete schedule **before any reserved native audit**.
3. Qualify every reserved fixture's closed ground scope and empty marginals. Author witnesses and independently replay them; these remain authored proofs until captured native executions establish execution. Check that generator changes did not introduce shortcuts, new rule forms or altered query semantics.
4. Audit all reserved case/mode paths under the separate 10-second correctness allowance. Check the Python choice reference, ordered native one-step transitions, captured proof replay where a proof is returned, and B/BO sequence equality. Revalidate copied development audits against frozen sources and inputs. Complete these checks before starting timing.

Do not require every policy to solve every fixture as a condition for retaining it. A qualified task with an authored witness can still yield a valid exhausted search under a particular policy or the fixed 100-expansion limit. Retain that outcome. An incorrect transition, malformed fixture or invalid proof is an implementation/qualification failure; stop and report it rather than filtering cases by which method won. If fixing a failure requires changing the method after reserved outcomes have been inspected, identify a separate follow-up and do not claim those same outcomes are still unseen.

The later measurement stage must use the exact audited policy and sources. Static audits are not timed benchmark samples. No future trace, selected route, proof witness or measured timing is available to online selection.

## Measurement and outcomes

Keep the current proof objective: `CanOperate(unit0)`, strength 1, confidence at least 0.729 with tolerance `1e-12`, independently replayable under the permitted pinned PLN formulas. Keep the 100-expansion cap and queue-limit arguments 4097. This tests valid derivation, **not empirical probability accuracy**.

The primary result is on-time verified-answer count/rate **at every prespecified tight budget**, separately for development and reserved cases. Each mode has 180 development and 144 reserved trials per budget. Show per-case results as well as split totals; do not select only favorable budgets. For BC/B pairs, report both succeed, neither succeeds, BC-only succeeds and B-only succeeds. Preserve invalid-pair counts separately. The total tight-budget BC/B pair counts are 1,260 development and 1,008 reserved if the batch completes.

At the generous endpoint, report success/failure counts, per-case median first-answer CPU, and paired CPU ratios and their spread. Where both policies succeed in all 12 repetitions, the latency comparison is complete for that case. Otherwise identify the matched successful subset and its selection bias; never rank methods using a success-only median while hiding misses. Report actual CPU and deadline overshoot even for failures. Repeated timing variability is not evidence of broad task generalization; a lone fast trial is not a reproducible benefit.

Timing includes embedded Python conversion and description, cost features, prediction, selection, native rule execution, queue management, deadline/goal checks and return bookkeeping. Process startup, static imports/model loading, parent orchestration and offline proof replay are excluded from all modes consistently. Record the runtime and host/CPU context with the batch. Do not subtract feature or selection overhead from query CPU. Their diagnostic windows overlap and cannot be summed as independent costs.

Deadlines remain cooperative between expansions: an expansion may overrun its budget. An answer returned late is a miss even if its proof is valid. Preserve the existing distinction between deadline stops, late returns, exhausted searches and invalid execution. These measurements do not establish hard real-time guarantees.

Retain every scheduled result and raw output. Stop after three invalid executions, retain the partial batch, and do not replace failed measurements or call the batch complete. Valid deadline/exhaustion outcomes are ordinary measurements and do not trigger that stop. Verify job coverage, individual-result/aggregate agreement, source/input hashes and proof/state consistency before interpreting results.

## Interpretation boundary and next action

BC improving on B would support a **bounded incremental-cost claim** for the measured cases, budgets and implementation, with all adverse outcomes reported. If B improves on N but BC does not improve on B, the evidence supports usefulness guidance rather than cost prediction. If BC helps only against BO, it has not overcome the full prediction overhead relative to B. If all methods succeed or all fail at a budget, that endpoint supplies no success-rate distinction. Mixed results require a conditional conclusion, not a universal improvement claim.

No timing result is guaranteed. These policies still consider cost only within maximum-confidence, equal-category contenders; the current cost model predicts an immediate expansion, not a complete proof's remaining CPU. This benchmark is an incremental controlled experiment, not a demonstration of a general Hyperon/ECAN defect or a final proposal.

**Review boundary:** review this protocol before implementing its runner and qualifying the reserved fixtures. No new PLN executions, fixture generation, model training or performance measurements were performed for this step.

Suggested commit message: `Specify matched usefulness and cost benchmark protocol`
