# Structural usefulness signals: validation and acquisition cost

The proposed descriptors are implemented in Python and validated on saved development states. They distinguish missing query-connected intermediates, potentially direct Goal work, represented consequences with unresolved value, and consequences with no known query connection. **No selector was changed, no benefit probability was fitted, and no query improvement was measured.**

This implements the description layer of the [review specification](benefit-signal-contract.md), following the [negative cost-only selection result](selection-budget-comparison.md).

## Implementation and scope

[benefit_signals.py](../src/pln_cost/benefit_signals.py) accepts current Tasks, Beliefs, query and an explicit qualified-scope declaration. Every call validates records, builds term/premise indexes, constructs a reverse ground-implication graph, traverses it from the query, and identifies evidence-disjoint MP pairs for **all pending candidates**. It preserves queue order and separately marks maximum-confidence eligibility. No persistent cache is used.

Each possible MP consequence is described as a potential Goal, missing query-connected intermediate, represented query-connected intermediate with unresolved value, or consequence without a known query connection. Outputs include the proposed evidence union and whether the term is already represented. Structural distance is graph distance, not remaining CPU or a guaranteed proof length. Counts are descriptive; they are not rewards or ranking weights.

The function does not run truth formulas, infer actual retained records, inspect saved future traces, read timing labels, or use route names to assign usefulness. It does not remove tasks, select candidates, alter confidence priority or stop inference. All records are treated as read-only.

Coverage is deliberately restricted. The caller must establish the closed ground workload scope; the function is not a general PLN rule-coverage detector. Missing/unknown scope, marginals, nonground records/query or an implication-producing consequence returns `coverage: unknown` with no candidate classifications. The runner verifies that each development fixture matches its qualified generated input multiset, query and empty marginals, and that each inspected state matches its saved native checkpoint. Ordinary opaque ground symbols are not interpreted as proof of general rule safety.

## Correctness evidence

The [validation report](../results/benefit-signals/run001/report.json) passed:

| Check | Coverage | What it establishes |
| --- | ---: | --- |
| Unit suite, completed before timing | 97 passing tests, including 7 new tests | Missing/present premises, mixed outputs, overlap rejection, implication-as-premise, consumed tasks, lower-confidence candidates, cycles, represented terms, unsupported scope, renaming and order checks |
| Indexed description versus offline scan/DFS reference | 1,364 pending candidates across 56 states from 15 development cases | Agreement on possible MP consequences, evidence unions, structural connection and represented-term status |
| Previously saved prospective MP feature counts | 1,050 maximum-confidence candidates | Agreement with the old `mp_matches` definition |
| Saved native all-candidate initial expansions | 54 candidates, necessary-work widths 4 and 16 | Agreement on newly generated term/evidence pairs in those initial states |

The native comparison uses [previously validated outputs](../results/selection/step-02/run001/necessary-w004-canonical_ids/initial-expansion-outputs.json), not newly executed PLN calls. It does not turn the structural descriptors into a truth-value verifier. The scan/DFS comparison is an implementation cross-check, not independent proof of utility. Renaming/order and unknown-coverage checks use authored unit cases, not a new native workload benchmark. Previously held-out cases were not used in this step.

## What the descriptors say on the reviewed examples

| Saved state and candidate | Descriptor result |
| --- | --- |
| Original width-4 initial state, ReadyA | One missing query-connected intermediate |
| Same state, ReadyB | Four missing query-connected intermediates; no assertion of four times the value |
| Same state, CertA -> Goal | Zero applicable MP pairs; marked a dormant query-connected rule |
| After native ReadyA expansion, CertA -> Goal | One potential direct Goal pair |
| Same later state, ReadyA -> CertA | One represented intermediate; value unresolved, not pruned |
| Necessary width-4 initial state, required R or L | One missing query-connected intermediate plus four unconnected side consequences |
| Same state, R -> SideFact0 | One applicable consequence with no known query connection |
| Same state, Idle | No MP contribution |

See the saved descriptors for [original initial state](../results/benefit-signals/run001/n004-canonical_ids-s000/descriptors.json), [state after ReadyA](../results/benefit-signals/run001/n004-canonical_ids-s001/descriptors.json), and [necessary-work initial state](../results/benefit-signals/run001/necessary-w004-canonical_ids-s000/descriptors.json).

“Represented” does not imply “redundant”: different evidence or truth values can still matter. The descriptors intentionally do not resolve that question. Nor does a potential Goal pair establish that its truth values meet the acceptance threshold. Native inference and independent proof replay remain necessary for actual answer validation.

## Acquisition timing

The [protocol](../configs/benefit-signal-validation.json) was saved before measurement. Five blocks each visit all 56 states in seeded shuffled order, with three warmup calls per state/block and 30 measured calls. This yields **8,400 measured full-state batches**. All run serially in one Python process; tests finished before timing. These are warm-call Python microbenchmarks, not fresh native query measurements.

Timing uses `time.process_time_ns()`. It includes input-record validation, index construction, graph traversal, evidence checks and output-description allocation for every pending candidate. It excludes JSON loading, fixture/provenance checks, result comparison and serialization, and any future native-to-Python transfer. No prebuilt index is provided for free. No clock-overhead subtraction is applied.

| Acquisition measure | CPU |
| --- | ---: |
| Median across the 56 state medians | **0.465 ms** |
| Minimum–maximum state median | **0.145–2.055 ms** |
| Original width-4 initial state, 12 pending candidates | **0.361 ms** |
| Necessary width-4 initial state, 15 pending candidates | **0.466 ms** |
| Largest state median: necessary width-16 swapped, after two expansions, 70 pending candidates | **2.055 ms** |

Each state summary is the median of its five block medians. Individual blocks vary; all raw samples are retained. The maximum empty-clock p95 / block-median ratio was **1.0542%**, below the prespecified 10% clock-resolution gate for every state/block. This gate addresses timer overhead, not Python–engine integration or every source of measurement variability. It is not a statistical significance test.

This is not a matched speed comparison with the earlier cost-feature implementation: the descriptors, candidate coverage, environment boundary and measurement batch differ. The observed scale is nontrivial beside millisecond query budgets. It does not establish that calling the function at each selection is affordable. A native implementation or indexing strategy would require its own correctness and total-cost validation; none was implemented here.

## Review boundary and reproduction

We now have a checked description layer and an acquisition-cost measurement, with explicitly unresolved novelty, proof-validity, deadline-success and integration questions. We do not yet have a benefit-aware selector or evidence that these descriptors improve selection. Review their semantics and overhead before specifying a ranking rule or cost integration. Keep the previous negative result and use new reserved evaluation cases for a method influenced by previous results.

- [Signal implementation](../src/pln_cost/benefit_signals.py)
- [Targeted tests](../tests/test_benefit_signals.py)
- [Validation/timing runner](../scripts/validate_benefit_signals.py)
- [Protocol and all-state report](../results/benefit-signals/run001/report.json)
- [Example raw timing blocks](../results/benefit-signals/run001/n004-canonical_ids-s000/timing.json)
- [Empty-clock samples](../results/benefit-signals/run001/empty-samples.json)

Run `python3 -m unittest discover -s tests` separately before measurements. Reproduce this step with `python3 scripts/validate_benefit_signals.py --run-id NEW_ID`; existing output directories are refused. The runner records source/input hashes and checks recorded files again after timing. It performs no native executions, installations or training.

Suggested commit message: `Validate PLN usefulness descriptors and measure acquisition cost`

No commit was made. Stop here for review.
