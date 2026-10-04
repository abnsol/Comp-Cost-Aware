# Cost-informed PLN selection: first comparison protocol

Status: Step 1, written for review before implementation or new experiments. This document fixes the comparison contract. Workload instances, features and estimator parameters must be recorded at their later review steps before evaluation; they are not yet selected or implemented. Existing evidence remains unchanged.

## Question and scope

Does using estimated expansion CPU to break confidence ties improve verified-answer completion within CPU budgets, or reduce CPU to a verified answer, after charging the cost of obtaining and using the estimates?

This is a test of a restricted selection intervention, not a claim that cost-aware selection already helps. It does not change priorities across different confidence values, estimate the probability that a theorem is true, or implement full rational metareasoning. An inexpensive estimator is the first candidate; a neural network or DQN is not a prerequisite. Predicting CPU and predicting eventual usefulness are separate problems.

The [preliminary findings](preliminary-pln-computation-findings.md) establish unequal costs for some equal-priority expansions and budget-sensitive native completion. The [criteria review](qualification/09-criteria-review.txt) records the missing causal comparison. The [paper review](metareasoning-papers-pln-review.md) motivates accounting for benefit, cost and overhead; it does not supply a validated PLN CPU predictor. This protocol is our experimental design, not a reproduction of a paper's algorithm.

## Fixed engine and selection contract

Use the [existing runtime pins](../configs/runtime.json): PLN `4405956947c4b53c7ff01bd565aa3b114bc970a1`, PeTTa `ae66fa8e41dcd5539d614706bd4e5cfb34f9608d`, and SWI-Prolog 9.3.25. Python orchestrates native execution. Preserve the original library and record the generated adapter diff and hashes.

All arms receive the same ordered inputs, full belief buffer and pending queue, query, rules, evidence guards, queue limits, stopping checks and acceptance criterion. Retain the existing 100-step cap and queue-limit arguments of 4097 unless a later, documented workload qualification requires a common change before evaluation.

At each selection, find the maximum native confidence. Only candidates with exactly that confidence, using native comparison semantics, are eligible for cost-based reordering. Do not introduce a numerical tolerance that silently combines different priorities. Facts, implications and derived statements remain candidates. Expand the selected statement using the unchanged native operation, including all result collection and queue updates. Do not prune its results to favor one route.

| Arm | Selection among maximum-confidence candidates |
| --- | --- |
| N: native | First in pending-queue order. No cost prediction. |
| O: overhead control | Compute the same candidate features and predictions as C, then retain the native choice. |
| C: cost-informed | Select minimum predicted expansion CPU; preserve queue order for equal estimates. |

O must execute the prediction pipeline, not simulate its overhead with a delay. It should preserve N's logical trajectory absent an earlier deadline. O and C may subsequently visit different states, so their total CPU difference is not an exact subtraction of estimator overhead. C versus N is the practical net-effect comparison; O helps diagnose the cost of gathering information without using it.

Specify prediction failure handling before evaluation: if any eligible candidate lacks a finite positive estimate, retain native tie-breaking for that selection and record the fallback. Apply identical prediction validation in O. A singleton eligible set needs no prediction in either O or C. Do not obtain missing estimates by running candidate expansions online.

## Workloads and estimator data

Keep the nine existing A/B cases as development diagnostics. They are one synthetic family, not nine independent domains. The branch labels are explanatory labels, not native route-selection actions.

Before fitting, record development and held-out structural configurations, generators and seeds. Held-out variants must change reasoning structure, not merely names or input order. Withhold their timing labels and performance outcomes from fitting and tuning. Keep canonical, swapped and shuffled orderings as within-structure controls.

Qualify three groups:

- Unequal-cost alternatives: retain the existing measured family.
- Similar-cost controls: assess measured candidate costs; width 1 alone is not proof of equality.
- Expensive necessary work: verify a valid target proof, distracting cheaper work, and the intended cost contrast. Inspect every applicable rule orientation and selectable implication for bypasses. A slow Ready expansion does not establish that every proof requires that expansion. Narrow or reject the case if necessity cannot be justified for the permitted rules and acceptance objective.

For this comparison, keep the current strength-1, confidence-at-least-0.729 acceptance criterion with `1e-12` tolerance. New cases must support this criterion; any change requires a documented amendment before comparative evaluation. Validity means a licensed replayable derivation, not empirical probabilistic accuracy.

Profile candidate expansions from restored identical logical states, covering all candidate types that the selector may encounter, not just ReadyA and ReadyB. Retain repetitions, timing-noise checks and unresolved measurements. Labels are measured expansion CPU; features must be available before expansion. Do not use generated-result counts, future proofs or measured test-candidate runtimes as free online features.

Choose the estimator and any feature processing on development data. Begin with a small transparent model; freeze features, preprocessing, fitting, parameter values and fallback rules before evaluation. Record training/data-collection costs separately. Report both duration-prediction error and ranking errors within ties; low average error alone does not establish useful selection.

## CPU and stopping contract

Preserve first-valid-answer stopping at committed belief states and cooperative deadline checks between expansions. A deadline miss is not a false answer. Report actual CPU and overshoot; these are not preemptive hard resource caps.

Charge all query-specific online work: feature extraction and cache construction, prediction, selection, inference, queue updates, goal checks, clocks and return overhead. Static runtime/model loading may remain outside the loaded-query window if identical exclusion rules are documented for all arms. Moving query-specific feature work before the timer is not permitted.

If prediction runs inside the engine process, its CPU falls within the engine clock. If it runs in a separate Python process, add nonoverlapping online process-CPU intervals and make them visible to deadline enforcement before further inference. Avoid counting child CPU twice or adding the entire orchestration process, which includes offline work. Validate accounting before timing comparisons. Report wall latency separately; communication waits are not CPU consumption.

Startup, offline training, profiling, proof replay and audit logging remain outside the online CPU budget and are reported separately. Never subtract prediction overhead from the result. A success requires a detected answer, a valid proof, and total charged CPU through return no greater than the budget. Late answers remain misses.

## Validation and run schedule

Before the comparison:

1. With unchanged selection, reproduce native candidate order and state transitions under a generous budget. With O, verify the same trajectory while predictions execute.
2. Exercise tie choice, unequal-confidence preservation, singleton handling, fallback, zero budget, absent goal and late return.
3. Independently check C's new transitions and captured proof provenance against native inference semantics. Its trace is expected to differ from the old native trace; old checkpoint matching is not an appropriate correctness test for C.
4. Keep audit logging out of performance runs. Use deterministic audited counterparts and check timed-run answers/final-state signatures against their own policy trajectory. If an outcome cannot be certified, mark it invalid rather than treating it as a success.

For existing cases use the common grid **0.25, 0.5, 1, 2, 4, 8 and 16 CPU ms** from the [baseline protocol](../configs/budget-protocol.json). Additional cases may need another common grid, chosen from development qualification before inspecting held-out policy outcomes. Use the same grid for every arm on a given task group.

Use **12 fresh-process repetitions per case/budget/arm**. Balance the six permutations of N/O/C twice within each case/budget; generate and save the complete randomized schedule with seed 1951 before execution. Keep hardware/runtime conditions consistent and avoid concurrent workloads. Rerun N in the new schedule rather than treating historical timings as a concurrent control.

Record every scheduled run, including timeouts, invalid proofs, failures and fallbacks. Do not replace unfavorable timings. An infrastructure failure may justify a separately labelled complete rerun after repair; preserve the original evidence. Record source/config/model hashes and execution environment with the results.

Also collect 12 runs per case/arm under a common generous ceiling of 1 second CPU, retaining the step cap, to measure first-answer CPU without tight-budget censoring. If qualification shows that ceiling is inadequate, amend it for all arms before evaluation. Step-cap exhaustion and ceiling misses remain failures.

## Analysis and interpretation

Primary results are on-time verified-answer counts per case and budget, reported as counts out of 12 and percentage-point differences between C and N. Show each workload group and ordering; do not hide losses in an aggregate score. Repeated timings measure runtime variability, not task generalization.

Report first-answer CPU from generous-ceiling runs with success/failure counts, paired differences where both succeed, and distribution summaries. Do not compare successful-run averages without showing excluded failures. Preserve overshoot, expansion counts, changed selections, prediction fallbacks and online overhead diagnostics. Detailed instrumentation must either be common and charged or run separately as an untimed diagnostic.

- **Benefit:** C improves deadline completion and/or answer CPU compared with N, with valid proofs and full online costs. State the cases and budgets supported; do not infer universal improvement.
- **Harm:** C delays necessary work, solves fewer cases on time, or increases answer CPU. Distinguish prediction/ranking error, overhead and poor usefulness of cheap work where traces allow it.
- **No detected benefit:** results do not show a consistent net gain. This does not establish statistical equivalence or that cost information can never help.
- **Inconclusive:** invalid accounting/proofs, unreliable timing, inadequate candidate coverage or too little evaluation prevents an interpretable comparison. Report the cause instead of a speedup claim.

Do not add relevance, learned benefit, different stopping or different candidate pruning only to C and attribute the combined change to cost. A cheap relevance comparator is desirable, but requires its own frozen definition and matched accounting. Without it, make no claim that C beats relevance-based selection. Expanding beyond confidence ties or implementing a benefit-aware learned policy is a separately reviewed experiment.

## Review checkpoints and presentation

Step 1 ends with this document. Next: qualify workloads; collect full-candidate cost data; validate the estimator and hook; run the comparison; interpret results; prepare the presentation. Stop for user review after each step. No implementation, training or new experiment is performed by this protocol step.

The presentation must distinguish completed baseline evidence, completed intervention results (if any), and proposed extensions. A negative or unresolved intervention result is retained. No claim of probabilistic-accuracy improvement, ECAN deficiency, broad Hyperon integration or paper reproduction follows from this experiment.
