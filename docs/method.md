# Experiment and code map

## Question and scope

Does adding predicted immediate expansion CPU to the same usefulness-guided
selection method improve timely verified PLN answers after including online
selection overhead? This is a confidence-tie intervention on synthetic proof tasks,
not a reproduction of BMPS/DQN, empirical probability calibration, or an ECAN test.

## Runtime and reasoning loop

PLN is pinned to `4405956947c4b53c7ff01bd565aa3b114bc970a1`, PeTTa to
`ae66fa8e41dcd5539d614706bd4e5cfb34f9608d`, and SWI-Prolog to 9.3.25.
Python orchestrates runs; native PLN executes rules. [runtime.py](../src/pln_cost/runtime.py)
checks pins and launches the engine. External runtime files remain outside this repository.

The belief buffer (BB) holds premises. The pending-task queue (PQT) holds statements
waiting for expansion, including facts and implications. Initially both receive
the knowledge base. Native selection uses highest confidence, with queue order
breaking ties. An expansion scans BB, checks evidence disjointness, attempts native
binary rules in both orientations and unary rules, collects outputs, deduplicates,
updates/trims queues and removes the selected task from PQT. Its statement remains
available in BB unless removed by a size limit.

```text
Load BB/PQT → answer/deadline check → select statement → native expansion
                         ↑                           ↓
                         └──────── queue updates ────┘
```

A certificate can be used from BB before it is selected from PQT. In the saved
canonical width-1 native run, selections are ReadyA, ReadyB, ReadyA⇒CertA,
CertA⇒Goal. Goal appears after four expansions, though its proof uses only two
modus-ponens applications. `scripts/demo.py` displays this captured execution.

## Tasks

- **Alternative routes:** ReadyA⇒CertA⇒Goal; ReadyB implies `width` distinct B
  certificates, each sufficient to imply the same Goal. Selecting ReadyB may
  generate all certificates, while selecting one B implication may generate only
  one. Width does not increase proof depth.
- **Necessary work:** ReadyRequired⇒CertRequired⇒Goal. Both the required fact and
  the implication that produces the certificate have outgoing implications to
  inert side results. Four idle facts add distracting candidates. Side results
  are not extra links inserted into the required proof.

The [alternative generator](../src/pln_cost/qualification.py) and
[necessary-work generator](../src/pln_cost/selection_workloads.py) use strength 1,
confidence .9 and distinct input evidence IDs. The closed, ground task profile has
empty marginal declarations. Its qualification is not a general coverage proof
for arbitrary PLN programs.

There are 15 development cases: alternative widths 1/4/16 and necessary widths
4/16, each in canonical, swapped and seeded-shuffled order. Twelve originally
reserved cases use widths 8/32 in both constructions and three orders. They are
related size/order variants, not twelve independent task domains. The saved
[manifest](../results/benefit-benchmark/run001/manifest.json) identifies all inputs.

## Selectors

All preserve maximum-confidence priority. The shared hand-written usefulness
heuristic prefers (2) currently applicable MP pairs that could produce Goal,
then (1) pairs producing an intermediate connected to Goal, then (0) other work.
Missing and already represented intermediates share category 1. Counts do not
multiply benefit. Structural connection is not expected utility or guaranteed
answer acceptance. Unknown coverage falls back to native selection.

| Mode | Choice within confidence ties |
| --- | --- |
| N | Native queue order |
| B | Best usefulness category, then queue order |
| BO | Same as B; acquire cost predictions but ignore them |
| BC | Best usefulness category, then lowest predicted expansion CPU |

BC/B is the incremental cost comparison; B/N tests usefulness guidance. BO/B
examines prediction acquisition while preserving choices. BC/BO is not subtraction
of a constant overhead, because changed trajectories affect later work.
Singleton choices skip unnecessary prediction; invalid predictions fall back to B.

Read [benefit_selection.py](../src/pln_cost/benefit_selection.py) first. It contains
the Python reference and online category entry point. [benefit_signals.py](../src/pln_cost/benefit_signals.py)
extracts current-state structural descriptions. [benefit_selector.pl](../src/pln_cost/benefit_selector.pl)
implements native filtering/tie resolution and calls the Python descriptions through
embedded Janus. [cost_selector.pl](../src/pln_cost/cost_selector.pl) computes native
cost features/predictions. No future trace, route-name lookup or saved answer is an
online input. No online selection algorithm was changed by repository cleanup.

## Predictor and data

Weighted standardized ridge regression predicts log expansion CPU from ten
features: BB size, PQT size, term size, evidence size, implication flag, disjoint
belief count, same-term/disjoint count, MP match count and its products with BB/PQT
sizes. It predicts immediate expansion cost, not full-proof CPU or eventual benefit.
[cost_model.py](../src/pln_cost/cost_model.py) contains the fit and reference prediction.

Development collection used 56 saved native states, 1,050 candidate/state rows and
15 repetitions per row. Each candidate starts from the same restored logical state.
Three block medians produce each row's median target. Empty-adapter p95 had to be
at most 10% of the candidate median in every block: 941 rows qualified, 109 remain
retained but excluded. Expansion labels exclude selection, preparation, feature
extraction, logging and offline verification. They include native inference,
result collection and queue updates. They are not end-to-end latency labels.

[Training labels](../data/training/expansion-costs.jsonl) preserve measured samples
and eligibility flags. Model selection kept each family/width's orders and states
together in grouped validation over ridge strengths .001/.01/.1/1; .01 was selected.
[scripts/fit_cost_model.py](../scripts/fit_cost_model.py) reproduces that fitting
calculation without rerunning measurements or overwriting the frozen model.
Accuracy on new policy-generated states was not independently established.

## CPU and correctness

The query clock covers selection, embedded Python descriptions/conversion,
prediction, inference, queues, goal/deadline checks and full derivation return.
It excludes process startup, static imports/model loading, parent orchestration
and offline proof replay. Selection overhead is never subtracted. Diagnostic
windows overlap and must not be added. The clock measures process CPU, not wall time.
[budget_clock.pl](../src/pln_cost/budget_clock.pl) implements the clock/stopping guard;
[budget.py](../src/pln_cost/budget.py) verifies its outputs against captured states.

Success requires CanOperate(unit0), strength 1, confidence at least .729 within
1e-12, independently replayable proof, and return within the CPU budget. Checks
between expansions allow overshoot; late proofs remain misses. There is a common
100-expansion cap and queue arguments 4097 (maximum 4096 retained entries).

The final schedule is 27 cases × four modes × eight endpoints × twelve repetitions
= 10,368 queries. Tight budgets are .5/1/2/4/8/16/32 ms; the separate generous
endpoint is 1 second. Fresh processes ran serially, with balanced arm order and
seeded scheduling. Repetitions measure variability, not task diversity.

Authored witnesses establish a possible derivation; captured native proofs show
actual execution. [proof.py](../src/pln_cost/proof.py) independently replays the
permitted formulas and evidence. Instrumented and quiet executions, queue states,
reference selections, native one-step transitions, and B/BO sequence equality were
checked before measurement. Hashes bind the source, fixtures and outputs.

## What remains and why

The full [results](results.md) retain wins, losses, late answers and inconclusive
measurements. The earlier cost-only pilot was negative: its median first-answer
CPU exceeded native selection on all 21 tested cases. Its compact summaries and
prior expansion/first-answer findings remain under [baselines](../results/baselines/).
Their complete old runs can be recovered from the pre-cleanup Git commit.

The frozen final batch retains raw evidence so its reported outcomes can still be
verified. Its small source archive binds historical code without leaving obsolete
step runners in the active tree. Current tests and the analyzer operate on the
retained final tasks; historical source hashes do not certify current code.

The literature informed the distinction between benefit and expense and the need
to charge selection overhead. Our categories, regression predictor and comparison
arms are experimental choices, not copied paper algorithms. Related reading:
[Hay](https://arxiv.org/pdf/1207.5879),
[BMPS](https://arxiv.org/pdf/1711.06892v3),
[Stop! Planner Time](https://ojs.aaai.org/index.php/AAAI/article/view/29983/31725).
