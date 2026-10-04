# Step 3: prospective features and development cost data

This step prepares a dataset for the first cost estimator. It does not fit a model, change PLN selection, or measure a policy improvement. The [comparison protocol](cost-informed-selection-protocol.md) remains in force.

## Split and scope

The 15 previously inspected cases are development data: nine A/B alternatives and six necessary-work challenges. They must not be described as independent unseen tasks. The [frozen split manifest](../results/selection/step-03/run002/split-manifest.json) records fixture hashes and the saved-state sources.

Six evaluation fixtures introduce two reserved structural changes, each in canonical, required-pair-swapped and seeded-shuffle order:

- Width-8 shared side sinks: the two required endpoints imply the same side conclusions, allowing additional native revision.
- Two disconnected width-4 modules: both contain a complete proof, but only the first module's goal is queried.

Authored proof replay, native discovery and traced-output parity qualify evaluation correctness. No expansion CPU labels, learned predictions or policy comparisons are collected for these fixtures in this step. Correctness qualification reveals proof structure and native expansion counts, so this is a held-out timing/performance split, not a blinded benchmark. These remain related synthetic variants, not independent application domains.

## Development state and candidate sampling

For each development case, sample the initial state, state after one expansion, midpoint before its first native proof, and state immediately before that proof, deduplicating indices. The first-proof checkpoint is used only for offline dataset construction; it is not an online feature.

At each sampled state, profile **every pending record at maximum native confidence**, retaining queue order for its identity. This includes applicable implication records and, where eligible, derived conclusions. It does not cover lower-confidence items that the proposed tie-breaker cannot select at that checkpoint, nor every state a new policy might visit.

Before timing, expand each candidate with the existing extracted helper and compare its ordered output queues with the unmodified native one-step loop. Each measured repetition restores the same logical input state; it does not continue from the previous candidate's output. Fresh processes do not restore hardware caches or allocation history.

## Prospective features

The [feature extractor](../src/pln_cost/cost_features.py) reads only the candidate and current task/belief queues:

- Queue lengths, candidate term size and evidence-stamp size.
- Whether the candidate is an implication.
- Number of evidence-disjoint beliefs and same-term disjoint beliefs.
- Number of structurally matching, evidence-disjoint modus-ponens pairs, in either orientation.
- Products of that match count with belief/task queue lengths, as potential predictors of result-management work.

No inference is executed to obtain these features. Actual results, future proofs, query relevance, route labels and measured durations are not inputs. Match counts describe potential work, not expected usefulness. Their acquisition requires scanning the current belief buffer and checking stamps; they are not free.

The Python extraction diagnostic times all eligible candidates together, including candidate identification, over 20 repetitions per state. It is recorded separately from engine expansion CPU. It does not include prediction, cross-process communication or a complete online selector, and it is not subtracted from any result. It will need to be charged or reduced in the next implementation step.

## Measurement and quality gates

The [prespecified data protocol](../configs/cost-data-protocol.json) uses three fresh-process blocks per state. Each block runs two randomized warm-up passes and five randomized measured passes across all eligible candidates, followed by 30 empty-adapter samples. Schedules are written before the corresponding measured blocks run.

The thin adapter measures actual native expansion CPU after input/callable preparation and selection, through inference, result collection and queue updates. It verifies singleton output separately and verifies each timed result after the end clock. Logging, feature calculation, state preparation and validation are excluded from this local label. No overhead is subtracted.

Every candidate-state row retains all 15 measured samples and three block medians. Its target is the median of the three block medians. Rows for which any block's empty-adapter p95 exceeds 10% of that candidate's block median are retained but marked `fit_eligible: false`. Do not silently fit on them or present them as qualified timing evidence.

An exploratory development-only diagnostic compares structural match-count ordering with measured CPU ordering within a state's eligible set. It ignores equal feature counts and reports CPU differences below 10% separately. Its many pairwise comparisons share candidates and states: they are not independent samples or held-out model accuracy.

## Run provenance and limits

The partial [run001](../results/selection/step-03/run001/INTERRUPTED.md) was stopped after a test process was inadvertently started during profiling. Its raw evidence is retained, its report is incomplete, and its timing rows are excluded from fitting. The entire predefined procedure was restarted as run002, without concurrent agent-launched tests and without changing inputs, features, schedules or timing thresholds in response to observed costs. Run002's manifest has different output paths; fixture contents remain the same.

Native CPU labels alone do not establish that these features are cheap enough online, that a model will predict unseen states accurately, or that using predictions improves first-answer performance.

## Completed findings

The clean [run002 report](../results/selection/step-03/run002/report.json) passed its execution and output checks. It contains 236 native process records: 12 evaluation-correctness runs, 56 development state audits, and 168 timing blocks. No evaluation CPU labels were collected, no model was fitted, and no selector was changed.

- **56 saved states** from 15 development cases.
- **1,050 candidate/state rows**, each with 15 measured repetitions: **15,750 timed expansions**.
- **941 rows passed** the predeclared instrumentation gate; **109 remain unresolved** and ineligible for fitting. They remain in the dataset, without replacement measurements or relaxed thresholds.
- All 1,050 rows were reconstructed from their saved block samples to check features, sample arrays and median labels. All 83 existing/new unit tests passed before the clean measurement run.

| Candidate kind | Candidate/state rows | Rows passing timing gate |
| --- | ---: | ---: |
| Ready facts | 47 | 36 |
| Implication records | 918 | 837 |
| Irrelevant Idle facts | 70 | 53 |
| Derived Certificate | 1 | 1 |
| Derived Side conclusions | 14 | 14 |

The data covers more than ReadyA/ReadyB, but is dominated by implication records. The 15 derived-candidate rows all come from one late development state. The `same_term_disjoint` feature is zero in every development row, so these data cannot identify an effect of revision opportunities on CPU; the shared-sink evaluation explicitly tests an untrained structural variation. This is limited coverage, not a diverse training corpus for a general neural policy. All sampled states follow the native selector; a new policy may visit other states requiring development-only coverage checks.

Among eligible within-state pairs with different MP-match counts, 3,331 had matching count/CPU ordering, 85 had the reverse ordering, and 424 differed in CPU by less than 10%. This is evidence that the structural count contains a useful signal in development data, but also that it is not a perfect cost ranking. It is not a trained-model accuracy score or an independent-sample success rate.

**The current Python feature extractor is too expensive to treat as cheap guidance.** The median feature-batch CPU across states was **3.241 ms**, ranging from **0.119 to 32.710 ms**. Within each state, divide batch feature CPU by the median candidate expansion CPU: the median of those ratios was **20.80**, and even the minimum was **1.71**. Feature acquisition exceeded one typical expansion in all 56 sampled states, before adding model prediction or communication. These ratios describe a whole selection's candidate-feature batch versus one expansion, which is the relevant online overhead concern.

For example, extracting the 36 eligible candidates' features at the original width-16 canonical initial state took **16.946 ms**, while individual expansion medians ranged from **0.161 to 0.763 ms**. The implementation repeatedly validates and scans beliefs for each candidate; sharing that work or reducing the feature set is an implementation opportunity, not a measured optimization result.

Do not discard the overhead result, extend budgets just to hide it, or infer that no cost-informed method can help. Before deploying this feature pipeline in a selector, reduce and remeasure its acquisition cost, preserving feature semantics or explicitly validating a reduced alternative. Any indexing, conversion or cache maintenance needed for a query must remain inside online accounting.

The six evaluation proofs were all captured and replayed. First proof appeared at expansion 3 for canonical/swapped orders, 22 for the shared-sink shuffle, and 29 for the disconnected-module shuffle. These counts qualify reachability under the unchanged cap; they are not timing or policy-performance results.

The dataset is [development-costs.jsonl](../results/selection/step-03/run002/development-costs.jsonl), with [state manifest](../results/selection/step-03/run002/state-manifest.json). Row-level quality flags and all raw block samples are retained alongside it.

## Reproduction and review boundary

Run `python3 scripts/collect_cost_data.py --run-id NEW_ID`; existing directories are never overwritten. Use only a fully passed report and its matching split/source hashes for fitting. Do not pool the interrupted batch with the complete batch.

Review [the collector](../scripts/collect_cost_data.py), [feature tests](../tests/test_cost_features.py), and [evaluation generator](../src/pln_cost/selection_workloads.py). The next step is a cheaper feature-acquisition implementation, then a small estimator and selection hook, with overhead validation and development-only model selection before any evaluation timing results are inspected. Keep all orderings and checkpoints of a development structure together in validation folds; do not randomly split closely related timing rows and call that generalization. Stop for user review before that step.

Suggested commit message: `Collect PLN candidate cost data and freeze held-out workload fixtures`
