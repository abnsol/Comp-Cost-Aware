PLN computation-cost experiments
===============================

Research question
Does adding predicted computational cost to an existing PLN selection method
improve answer speed and probabilistic accuracy after including its overhead?
Improvement, no benefit and harm are all legitimate experimental outcomes.

Status: step two implemented and checked on 2026-10-04; stopped for code review.
The returned machine-example answer now has a captured seven-node proof replayed
independently in Python. Instrumented and original runs have identical original
output, including every selected record. See docs/step-02.txt for scope and limits.
No cost estimator, relevance extension or CPU benchmark has been implemented.

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
  scripts/                Human-readable entry points; start at validate_step1.py
  tests/                  Offline input/oracle and false-success checks
  results/step-01/run001/ Original output, parity fixture and result manifest
  results/step-02/        Raw traces, instrumentation diff and replay certificates
  docs/                   Step records, limitations and review notes

Run from this project directory (Python standard library only)
  python3 -m unittest discover -s tests -v
  python3 scripts/validate_step1.py --run-id review001
  python3 scripts/validate_step2.py --run-id review001
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
Step two's returned-answer deductions and revision are checked; the entire search
and other rule families are not certified. The machine example is retained as a
diagnostic. Primary-task selection is now under discussion: see
docs/workload-candidates-2026-10-04.txt for equal-priority/equal-depth alternative
proofs and the distinction between rule correctness and probability accuracy.
Their CPU cost gap has not been measured. Do not implement an estimator or begin
the main benchmark before validating the new task and reviewing the papers.

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
