# Resource-rational inference control for PLN

Research problem statement and preliminary evidence, 4 October 2026. Based on completed qualification Steps 6–8 and the subsequent baseline-criteria review.

## The problem the project investigates

A reasoner working under a CPU deadline must choose which available reasoning operation to perform next. In the pinned PLN implementation examined here, pending sentences are ranked by truth-value confidence. That score does not explicitly represent an expansion's computational cost, its relevance to the query, or the remaining deadline. Our experiments establish that equally prioritized expansions can have substantially different CPU costs, and separately that this baseline's ability to return a valid answer depends on the available CPU budget.

**The unresolved problem is whether making computation cost explicit improves the allocation of inference work under limited CPU, after accounting for the cost of that additional decision-making.** Cheap work can be unhelpful; expensive work can produce necessary intermediate conclusions. The objective is therefore useful reasoning within a budget, not simply selecting the cheapest expansion.

The project's first research question is:

> For the pinned PLN implementation, when does adding estimated computation cost to an otherwise unchanged inference-selection method improve verified-answer completion and time to a valid answer across CPU budgets, once all online estimation and selection overhead is charged—and when does it hurt, particularly when expensive work is necessary?

This is a hypothesis to investigate, not an improvement already demonstrated. The broader resource-rational framing asks which computation is worth its cost; the first experiment isolates **cost information as a selection factor**, without presupposing a new controller architecture or learned policy. The evidence below motivates that question but does not establish inefficient selection or a PLN/ECAN defect.

## Implementation and proof task

The examined snapshot is PLN commit `4405956947c4b53c7ff01bd565aa3b114bc970a1`, executed through PeTTa commit `ae66fa8e41dcd5539d614706bd4e5cfb34f9608d` and SWI-Prolog 9.3.25 on x86_64 Linux. Python orchestrated native execution; it did not replace PLN inference. These findings concern this pinned implementation, not every PLN or Hyperon implementation. See the [runtime pins](../configs/runtime.json) and [native source](../../research-discovery/step-03/repos/PLN/lib_pln.metta).

`PriorityRank` uses a sentence's truth-value **confidence**. `BestCandidate` replaces the current best only for a strictly greater score, so the first maximum in the ordered task queue wins ties. One **expansion** selects a sentence, scans the belief buffer, attempts binary rules in both argument orders where evidence stamps are disjoint, attempts unary rules, collects results, and updates/deduplicates/trims task and belief queues. It is potentially many rule attempts, not one inference application. Native `PLN.Query` ranks matching answers after derivation; it does not implement the first-valid-answer stopping objective used here.

The constructed query is `(CanOperate unit0)`, interpreted as authorization licensed by supplied axioms:

```text
ReadyA → CertificateA   → CanOperate
ReadyB → CertificateB_i → CanOperate   (i = 1…N)
```

A has one certificate branch; B has `N = 1, 4, 16`. Each width uses canonical input order, an order swapping only the two Ready facts, and a full seeded shuffle (seed 17): **nine cases**, containing respectively 6, 12, or 36 input records. Every input has strength 1, confidence 0.9, and a distinct evidence stamp. Both queues initially contain the complete KB, including selectable implication records. No goal, artificial delay, or cost label is supplied. The native step cap is 100; queue-limit arguments 4097 permit 4096 retained records. No trimming occurred in these workload runs. [Workload and acceptance contract](qualification/01-kb-specification.txt)

Either two-step modus-ponens route yields strength 1 and confidence approximately `0.9³ = 0.729` under the pinned formulas. Success requires a committed goal with strength 1 and confidence at least 0.729, allowing `1e-12` tolerance, and a valid replayable proof. A and B proofs have disjoint evidence and can support later revision; different B proofs share ReadyB evidence and cannot be directly revised together under the overlap guard. This tests **valid derivation**, not empirical probability accuracy. Equal priority and an equally sufficient terminal answer do not mean equal intermediate usefulness: B produces additional proof opportunities.

## Correctness and measurement validation

The evidence separates constructed witnesses from actual engine behavior:

- **Authored proofs:** 72 static proof witnesses were independently replayed in Python. They checked the task specification but did not demonstrate native discovery. [Step 2 report](../results/qualification/step-02/run001/report.json)
- **Captured native proofs:** nine unmodified runs and nine traced runs agreed on outputs and selection sequences. Nine captured final-answer certificates passed independent replay of input licensing, rule formulas, premise structure, evidence guards/unions, and acyclicity. Final answers had strength 1 and confidence approximately 0.843262 after revision. The checker covers the rules needed by these proofs, not all PLN. Step 7 separately verified the earlier first-answer certificates using only proof events available at their checkpoints. [Step 3 report](../results/qualification/step-03/run001/report.json), [proof checker](../src/pln_cost/proof.py), [Step 7 report](../results/qualification/step-07/run001/report.json)
- **State and instrumentation checks:** 435 captured states supported 47 fresh-process restoration checks; subsequent ordered queues, selections, derivations, and final states matched. Across 36 one-expansion validation trials, native reference, timed helper, and separately audited execution agreed on results and queues; validation included a separate trimming diagnostic. [State-restoration report](../results/qualification/step-04/run001/report.json), [expansion-validation report](../results/qualification/step-05/run002/report.json)

Independent replay means a separate implementation of the pinned inference formulas and proof checks, not independent empirical evidence that the probabilities describe the world.

## Local expansion CPU results

Embedded Python `time.process_time_ns()` measured engine-process user plus system CPU. The local interval begins after candidate selection and callable preparation and ends after rule application, result collection, and queue updates. It excludes startup/loading, state preparation, selection, detailed counters/logging, output validation, offline proof replay, and parent Python orchestration. Clock/bridge overhead remains included; nothing was subtracted. Nanosecond representation does not imply nanosecond accuracy.

The initial calibration failed the preset overhead criterion at every tested batch size (1, 8, 32); empty-harness p95 was 15.2–27.6% of the faster expansion median. Replacing measurement-side result-list accumulation with a thin Prolog adapter calling the same compiled expansion repaired calibration without changing inference. Singleton-result and exact-output checks remained outside timing. Recalibrated single-expansion overhead ratios were 6.20%, 5.33%, and 2.07%, below the unchanged 10% gate. [Initial calibration](../results/qualification/step-06/calibrate/cal001/report.json), [repair validation](qualification/06-thin-repair-results.txt), [recalibration](../results/qualification/step-06/repair/calibrate/cal002/report.json)

The **main measurement**, separate from calibration, covered 13 saved states where both Ready candidates remained pending at confidence 0.9: nine initial states plus two later states each for shuffled widths 4 and 16. Each state had 12 fresh-process blocks of 10 balanced, randomized A-first/B-first pairs, following 20 warm-up pairs. This produced 156 processes and **1,560 measured pairs**. Every alternative used identical saved ordered queues; preceding trial outputs never enlarged the next trial's state. Logical restoration does not restore hardware caches or allocator history.

A directional finding required an overhead proxy ≤10% in every block, a descriptive 95% ratio interval beyond 1.10, an absolute-gap interval beyond 11.915 µs, exact sign-test `p ≤ .05/13`, and practical agreement in both pair-order strata. Intervals use 5,000 whole-block bootstrap resamples. These are fixed-state descriptions, not task-generalization bounds. [Protocol](../configs/paired-protocol.json), [main execution contract](qualification/06-main-execution.txt)

| Width / ordering / completed expansions | Paired B/A CPU ratio [95% interval] | Main-run verdict |
|---|---:|---|
| 1 / canonical / 0 | 0.999 [0.993, 1.002] | Overhead unresolved |
| 1 / swapped / 0 | 1.000 [0.996, 1.004] | Within relative equivalence band |
| 1 / shuffled / 0 | 0.992 [0.967, 1.003] | Overhead unresolved |
| 4 / canonical / 0 | 1.565 [1.550, 1.574] | B costlier |
| 4 / swapped / 0 | 1.562 [1.504, 1.567] | Overhead unresolved |
| 4 / shuffled / 0 | 1.572 [1.553, 1.582] | B costlier |
| 4 / shuffled / 1 | 1.450 [1.424, 1.463] | B costlier |
| 4 / shuffled / 2 | 1.448 [1.396, 1.454] | Overhead unresolved |
| 16 / canonical / 0 | 3.799 [3.764, 3.885] | B costlier |
| 16 / swapped / 0 | 3.764 [3.738, 3.821] | B costlier |
| 16 / shuffled / 0 | 3.744 [3.629, 3.874] | B costlier |
| 16 / shuffled / 1 | 3.763 [3.666, 3.897] | B costlier |
| 16 / shuffled / 2 | 3.535 [3.463, 3.637] | B costlier |

Source: [completed Step 6 main report](../results/qualification/step-06/measure/run001/report.json) and [readable results](qualification/06-paired-results.txt). Ratios summarize paired block ratios, not the quotient of separately summarized CPU medians.

Eight states passed every directional criterion. Accepted width-4 gaps were 43–52 µs; width-16 gaps were 554–631 µs. For canonical width 16, separate A/B CPU medians were 222.55/844.07 µs. All eight findings had 12/12 positive blocks (`p = 0.00048828125`). Four states remain unresolved because their maximum overhead proxies exceeded 10% (18.15%, 17.32%, 13.48%, 11.94%); none was discarded. Only one width-1 control cleared the full overhead gate, so near-one ratios do not establish universal cost equality.

Separate counters observed one generated A result versus N B results while both scanned the same buffer (6/12/36 beliefs in canonical initial states). This supports additional generation and queue work as an explanation, but does not isolate their individual CPU contributions.

## First answers, native derivation runs, and deadlines

Step 7 measured native prefixes ending at independently verified first-answer checkpoints and `PLN.Derive` runs ending at empty tasks or the 100-expansion cap, with three fresh-process repetitions per endpoint per case. Selection, inference, queues, recursion, and termination were included; diagnostic selection printing was silenced. Startup, proof replay, and final `PLN.Query` answer ranking were excluded. Exact checkpoint/output checks passed, and all timing overhead proxies passed the 10% gate. [Step 7 measurements and interpretation](qualification/07-first-answer-results.txt)

| B width | First-answer expansions | First-answer CPU, ms | Full-derive expansions | Full-derive CPU, ms |
|---|---:|---:|---:|---:|
| 1 | 4–5 | 0.379–0.466 | 12 | 0.791–0.925 |
| 4 | 4–6 | 0.817–1.017 | 30 | 4.118–5.734 |
| 16 | 4–5 | 2.385–3.020 | 100 | 50.331–55.893 |

CPU ranges above span the three ordering-specific medians, not confidence intervals. Width-16 full-derive runs reached the 100-expansion cap with pending work; they did not exhaust the search. Widths 1 and 4 terminated with empty task queues. Individual repetitions were variable. Prefix endpoints were selected from offline traces; these timings do not themselves implement online stopping or end-to-end application latency. They also use fresh inference calls, unlike the warmed local-expansion measurements.

Every first goal arose while expanding a **Certificate→CanOperate implication record**. Canonical and swapped inputs expanded both Ready facts before answering at expansion 4. Shuffled width 4 answered through B at expansion 6, before ReadyB was selected at 7; shuffled width 16 answered through B at 5, before ReadyA at 23. Selecting a Ready candidate therefore does not exclusively select a complete proof route. A cheaper expansion cannot be equated with a cheaper complete query. Later reasoning increased confidence through revision, so time after first success is not automatically wasted.

Newer **Step 8** results establish baseline budget sensitivity: 630 fresh runs covered nine cases, seven budgets (0.25–16 ms), and ten repetitions per cell. Native selection was preserved inside a validated online goal/deadline wrapper whose observation and stopping costs were charged. There were 370 verified on-time successes and 260 misses: 0/90 successes at 0.25 ms, versus 90/90 at both 8 and 16 ms. At 4 ms, width 16 succeeded in 23/30 runs. All final states matched native checkpoints and detected proofs passed replay. This wrapper is not the original `PLN.Query` API. Checks occur between atomic expansions, so deadlines are cooperative: maximum overshoot was 1.891 ms, and late answers counted as misses. Startup and offline verification remained excluded. [Budget validation](../results/qualification/step-08/validate/val001/report.json), [measured budget results](../results/qualification/step-08/measure/run001/report.json), [accounting and limitations](qualification/08-budget-results.txt)

## What remains unestablished

**Confidence-based equal priority does not imply equal measured expansion CPU cost in this implementation and task family.** The measurements characterize a distinction the priority score does not express; they do not establish a defect or an inefficient decision. CPU deadlines demonstrably affect this baseline's completion, but the causal question—whether changing selection order improves completion under those deadlines—remains untested.

No cost-aware selection benefit, empirical probability improvement, or ECAN limitation was demonstrated. The evidence is limited to one synthetic development family, fixed inputs and reachable states, one runtime/machine, and a valid-proof objective. The nine cases are not nine independent task families; width changes both computation and available intermediate results. Generalization to other reasoning tasks, uncertain evidence, hardware, or complete application costs is not established.

## Scope of the proposed investigation

The primary outcomes are **verified-answer success by a stated CPU deadline** and **CPU time to an answer subsequently verified by proof replay**. A missed deadline is an unsolved instance at that budget, not evidence that the proposition is false. Time-to-answer results must retain failures and timeouts; averaging only successful runs could make a method that solves fewer tasks appear faster.

The decisive comparison is the same base selector with cost information disabled versus enabled. Inputs, candidate access—including implication records—rules, evidence handling, queue limits, answer criterion, observation/stopping mechanism, and deadline accounting must remain common. If query relevance or remaining-budget information is introduced, it must be shared or separately ablated. Otherwise an improvement cannot be attributed specifically to cost information. Native confidence selection and inexpensive relevance/structural heuristics are comparators, not presumed inferior methods.

Feature extraction, prediction, selection, and online goal checks must all count toward the declared CPU budget, including any such work performed in Python outside the engine. The existing baseline measures loaded-engine CPU and excludes startup and offline proof verification; it is not complete application latency. Comparisons must use consistent accounting and report actual CPU and overshoot, rather than describing the current cooperative deadlines as strict resource caps. Training and data-collection costs, if applicable, must be reported separately.

The existing cases provide a development baseline, not the entire research benchmark. Evaluation must also include validated tasks where expensive work is necessary, cheap work is irrelevant, costs are similar, and extra decision-making can outweigh any saving. Structurally held-out tasks are needed for transfer claims; reordered or renamed versions of one graph do not supply that evidence. Prediction mistakes and delayed or starved necessary work are possible failure mechanisms to measure. These requirements and remaining limitations are recorded in the [baseline-criteria review](qualification/09-criteria-review.txt).

The original ambition of faster **and more accurate probabilistic answers** remains a separate, conditional track. It requires an independently justified probabilistic target compatible with the permitted PLN assumptions and a shared answer-selection policy. Formula replay, higher confidence, and agreement with a longer PLN run do not alone establish empirical accuracy. The current workload supports the first-valid-proof question.

## How the papers inform this problem

The contribution cannot be the general idea of balancing computational benefit and cost: that has substantial prior work. [Hay et al.](https://arxiv.org/abs/1207.5879) formalize computation selection for improving a subsequent decision. [BMPS](https://cocosci.princeton.edu/papers/callawayLearningToSelect.pdf) approximates value-of-computation policies using information-value features and a specified decision model; its studied tasks use constant per-computation costs, not a ready-made predictor of heterogeneous PLN CPU costs.

[Stop! Planner Time](https://ojs.aaai.org/index.php/AAAI/article/view/29983) learns contextual planner-performance profiles. [TP-Compilation](https://starai.cs.ucla.edu/papers/VlasselaerIJCAI15.pdf) selects probabilistic-logic work using bound improvement, representation growth, and query importance. [PLN theorem-probability guidance](https://aitp-conference.org/2025/abstract/AITP_2025_paper_2.pdf) proposes prioritizing promising proof paths. These are relevant foundations and alternatives. Their different tasks and assumptions create mapping questions, not proof that no existing method can address our setting.

A value-of-computation formulation would need a defined outcome utility, current state, reference decision, continuation policy, and the costs of later work required for delayed benefits. An arbitrary priority-minus-cost score is not automatically that formulation; a CPU penalty and a deadline-constrained success objective are also different choices. Paper review must establish these mappings before an implementation is described as a reproduction or a PLN adaptation. No predictor or architecture is selected here.

The intended contribution is evidence about **when computation-cost information adds value beyond an otherwise matched selector and cheap alternatives, when its overhead or mistakes erase that value, and how far the result transfers**. Positive, neutral, and negative outcomes are all legitimate. The preliminary experiments make this question measurable; they do not predetermine its answer.
