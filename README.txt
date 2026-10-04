PLN computation-cost experiments
===============================

Research question
Does adding predicted computational cost to an existing PLN selection method
improve answer speed and probabilistic accuracy after including its overhead?
Improvement, no benefit and harm are all legitimate experimental outcomes.
The current qualification phase addresses time/success to a valid PLN derivation.
It does not establish improved probability accuracy against external outcomes.

Status: step-seven first-answer CPU pilot completed; stopped for review.
Start at docs/qualification/07-first-answer-results.txt. All nine KBs reached a
verified goal after 4-6 expansions, with pilot median reasoning CPU about0.38-3.02
milliseconds. Nine prefix audits and 54 fresh-process timings passed. Timing uses
an offline-known stopping checkpoint; an online answer detector and CPU-budget
policy are not implemented. The native selector/rules/queues remain unchanged.
Previous step: docs/qualification/06-paired-results.txt. Across 156 fresh processes and
1560 measured pairs, B was reproducibly costlier in 8/13 saved states. One control
fell within the relative equivalence band; four states remain unresolved because
of block-level overhead failures. The clearest result is width16: all five states
passed, with paired B/A medians 3.535-3.799. No answer-speed benefit is established.
The design is docs/qualification/01-kb-specification.txt and configs/qualification-kb.json.
The earlier machine-example work is preserved:
The returned machine-example answer now has a captured seven-node proof replayed
independently in Python. Instrumented and original runs have identical original
output, including every selected record. See docs/step-02.txt for scope and limits.
No cost estimator, relevance extension or end-to-end CPU benchmark is implemented.

The experiment is Python-led, using the actual pinned PLN MeTTa rules. Step one
uses a subprocess interface; embedded PeTTa()/hyperon.MeTTa() compatibility is
not established. No new dependency installation was needed.

Folder structure and review order
  cases/                  Small MeTTa inputs, kept separate from evaluation truth
  configs/                Runtime paths and expected source revisions
  src/pln_cost/world.py   Independent exact synthetic-world evaluator
  src/pln_cost/runtime.py Bounded Python interface to the existing engine
  src/pln_cost/validation.py  Output checks (not independent proof replay)
  src/pln_cost/tracing.py Print-only instrumentation of a generated PLN copy
  src/pln_cost/sexpr.py   Restricted ground fixture/trace parser
  src/pln_cost/proof.py   Returned-answer certificate extraction and replay
  src/pln_cost/qualification.py  KB generator and explicitly authored static proofs
  src/pln_cost/feasibility.py  Qualification output parsing and observable parity
  src/pln_cost/states.py  Native state capture, provenance and exact continuation checks
  src/pln_cost/expansion.py  Native expansion extraction, CPU clocks and separate counters
  src/pln_cost/paired.py  Repeated-state harness, calibration summaries and block analysis
  src/pln_cost/thin.py / thin_clock.pl  Thin compiled-call measurement adapter
  src/pln_cost/first_answer.py / first_clock.pl  First-goal proofs and native-loop CPU
  scripts/                Human-readable entry points; start at validate_step1.py
  tests/                  Offline input/oracle and false-success checks
  results/step-01/run001/ Original output, parity fixture and result manifest
  results/step-02/        Raw traces, instrumentation diff and replay certificates
  cases/qualification/   New authorization KBs, separate from the old diagnostic
  results/qualification/ Static proofs, native feasibility, state/restoration traces
  docs/                   Step records, limitations and review notes

Run from this project directory (Python standard library only)
  python3 -m unittest discover -s tests -v
  python3 scripts/generate_qualification.py --run-id review001
  python3 scripts/validate_qualification.py --run-id review001 --case-batch run001
  python3 scripts/validate_states.py --run-id review001 --feasibility-batch run001
  python3 scripts/validate_expansion.py --run-id review001 --state-batch run001
  python3 scripts/run_paired.py calibrate --run-id review001
  python3 scripts/repair_calibration.py diagnose --run-id review001
  python3 scripts/repair_calibration.py validate --run-id review001
  python3 scripts/repair_calibration.py calibrate --run-id review001 --validation val001
  python3 scripts/run_paired.py measure --harness thin --run-id review001 --calibration cal002
  python3 scripts/measure_first_answer.py --run-id review001
  python3 scripts/validate_step1.py --run-id review001
  python3 scripts/validate_step2.py --run-id review001
The qualification generator runs no inference: it checks source revisions and
runtime version, writes cases, and replays static proofs in Python. Qualification
validation runs two fresh processes per case (18 total), retaining both native
and traced logs and replaying captured proofs. validate_step1.py/validate_step2.py
are the earlier machine-diagnostic native runners.
State validation records the native queues at every loop entry, then restores
selected checkpoints in fresh processes. The current batch uses 56 processes
(9 captures and 47 restorations), each with the existing wall safety limit.
It does not measure CPU or restore hardware caches/allocator history.
Expansion validation uses 108 processes (36 trials, each with an unmodified
native reference, timing-only helper and diagnostic helper). The clock is inside
the engine process. These are local operation CPU samples, not total query costs.
Detailed counter logging is excluded from timing-only runs; boundary-clock costs
remain included, and probes are saved without automatically subtracting them.
The legacy paired harness has separate calibrate/measure stages. Its saved cal001
failed and remains preserved. repair_calibration.py records the thin-adapter
revision: val001 passed and repair/calibrate/cal002 passed with singleton timing.
run_paired.py measure --harness thin uses that exact validated adapter and binds
to its calibration/helper/conditions/protocol and execution-code hashes. The
main run is results/qualification/step-06/measure/run001. Default --harness legacy
remains separate and cannot consume a thin calibration. Both calibration passing
and main execution passing are distinct from all state-level analysis gates
passing. Four main states remain unresolved; no samples were discarded or retried.
First-answer measurement uses previously captured proof/state traces to identify
the earliest qualifying committed goal, validates the entire native prefix in a
separate audit, then times a direct call to the same native derivation loop.
Only SELECTED console printing is silenced in the timing copy; inference and
selection remain native. Startup/input preparation, parent orchestration and
offline verification are excluded. This is reasoning CPU to answer availability,
not online answer-return latency. Full-derivation timing excludes final Query
answer ranking. Future online observation and budget-check overhead must count.
Use a fresh run ID: existing results are never overwritten. Runtime paths in
configs/runtime.json are relative to this project. The external runtime/source
directories must already exist at the recorded revisions; the runner installs
nothing. Each engine invocation has a 60-second wall safety limit, not a CPU
benchmark budget. Step one creates three fresh engine processes sequentially;
step two creates two (original and instrumented).

Working agreement
- Discuss each step before execution, then stop and review its results.
- The user reviews and commits changes. Leave changes uncommitted and unstaged
  after each step, and provide a suggested commit message. Do not commit unless
  the user explicitly asks. Document checks and unresolved issues for review.
- Implement and validate the baseline first; audit it against CRITERIA.txt.
- Before implementing cost estimation, review the papers' problems, selection
  methods, cost/benefit models, assumptions, experiments, results and limitations.
- Review the proposed adaptation before implementing it.
- Keep independent probability truth separate from PLN confidence and derivation
  validity. Charge both Python and engine CPU, including selection overhead.
- Keep development/tuning separate from held-out evaluation.

Review checkpoint
Review docs/qualification/07-first-answer-results.txt and the native-loop timer.
Keep cal001's failure, the repair and all main-run unresolved outcomes as evidence.
The proposed next step is CPU-budget observation design and repeated budget tests,
after discussion. Do not silently grant the online policy an offline-known stop.
This new series is separate from the old diagnostic interface/proof-audit steps.
Local expansion cost gaps are established for eight fixed development states;
first-answer availability CPU now has a three-repetition pilot. Do not implement an estimator
or begin a cost-aware policy comparison before reviewing the baseline criteria
and studying the papers. Local expansion costs do not establish full proof costs.

Research context (relative to this project)
../hyperon-research-discovery-new-session-prompt.txt
../research-discovery/computation-factor-experiment-design-2026-10-03.txt
../research-discovery/example-selection-2026-10-03.txt
These are existing context documents, not new experimental results. The design
and example contain provisional choices and unresolved validation requirements.

Existing source snapshots for later validation (not vendored here)
../research-discovery/step-03/repos/PLN
  4405956947c4b53c7ff01bd565aa3b114bc970a1
../research-discovery/step-03/repos/PeTTa
  ae66fa8e41dcd5539d614706bd4e5cfb34f9608d
These are previously recorded revisions, not claims of latest upstream versions.

Version-control policy
Track source, configuration, task definitions, manifests, validation reports and
small result artifacts. Preserve provenance, commands and checksums for larger
artifacts stored outside Git; document their location rather than silently losing
them. Local environments, downloaded runtimes and caches are ignored. No remote
repository has been configured or published.
