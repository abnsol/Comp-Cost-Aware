PLN computation-cost experiments
===============================

Research question
Does adding predicted computational cost to an existing PLN selection method
improve answer speed and probabilistic accuracy after including its overhead?
Improvement, no benefit and harm are all legitimate experimental outcomes.

Status: step one implemented and checked on 2026-10-04; stopped for code review.
Python successfully called the pinned SWI/PeTTa runtime, reproduced the native
example's expected answer, and ran the authored machine-failure example.
See docs/step-01.txt for results and limits. No cost estimator or CPU benchmark.

The experiment is Python-led, using the actual pinned PLN MeTTa rules. Step one
uses a subprocess interface; embedded PeTTa()/hyperon.MeTTa() compatibility is
not established. No new dependency installation was needed.

Folder structure and review order
  cases/                  Small MeTTa inputs, kept separate from evaluation truth
  configs/                Runtime paths and expected source revisions
  src/pln_cost/world.py   Independent exact synthetic-world evaluator
  src/pln_cost/runtime.py Bounded Python interface to the existing engine
  src/pln_cost/validation.py  Output checks (not independent proof replay)
  scripts/                Human-readable entry points; start at validate_step1.py
  tests/                  Offline input/oracle and false-success checks
  results/step-01/run001/ Original output, parity fixture and result manifest
  docs/                   Step records, limitations and review notes

Run from this project directory (Python standard library only)
  python3 -m unittest discover -s tests -v
  python3 scripts/validate_step1.py --run-id review001
Use a fresh run ID: existing results are never overwritten. Runtime paths in
configs/runtime.json are relative to this project. The external runtime/source
directories must already exist at the recorded revisions; the runner installs
nothing. Each engine invocation has a 60-second wall safety limit, not a CPU
benchmark budget. This step creates three fresh engine processes sequentially.

Working agreement
- Discuss each step before execution, then stop and review its results.
- Make a focused commit for each completed meaningful step, documenting checks
  and unresolved issues. Commit partial work only when clearly labeled.
- Implement and validate the baseline first; audit it against CRITERIA.txt.
- Before implementing cost estimation, review the papers' problems, selection
  methods, cost/benefit models, assumptions, experiments, results and limitations.
- Review the proposed adaptation before implementing it.
- Keep independent probability truth separate from PLN confidence and derivation
  validity. Charge both Python and engine CPU, including selection overhead.
- Keep development/tuning separate from held-out evaluation.

Review checkpoint
Review step-one code and results before proceeding. Remaining baseline work
includes independent deduction-proof checking, fair relevance support and CPU
instrumentation. Do not begin the cost estimator, training or a benchmark yet.

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
