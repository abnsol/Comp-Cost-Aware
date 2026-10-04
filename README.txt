PLN computation-cost experiments
===============================

Research question
Does adding predicted computational cost to an existing PLN selection method
improve answer speed and probabilistic accuracy after including its overhead?
Improvement, no benefit and harm are all legitimate experimental outcomes.
The current qualification phase addresses time/success to a valid PLN derivation.
It does not establish improved probability accuracy against external outcomes.

Status: qualification step three completed on 2026-10-04; stopped for review.
Start at docs/qualification/03-native-feasibility.txt. All nine generated cases
returned independently verified native PLN answers. Original and traced runs
have identical original output. CPU differences remain unmeasured.
The design is docs/qualification/01-kb-specification.txt and configs/qualification-kb.json.
The earlier machine-example work is preserved:
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
  src/pln_cost/qualification.py  KB generator and explicitly authored static proofs
  src/pln_cost/feasibility.py  Qualification output parsing and observable parity
  scripts/                Human-readable entry points; start at validate_step1.py
  tests/                  Offline input/oracle and false-success checks
  results/step-01/run001/ Original output, parity fixture and result manifest
  results/step-02/        Raw traces, instrumentation diff and replay certificates
  cases/qualification/   New authorization KBs, separate from the old diagnostic
  results/qualification/ Static validation and captured native feasibility runs
  docs/                   Step records, limitations and review notes

Run from this project directory (Python standard library only)
  python3 -m unittest discover -s tests -v
  python3 scripts/generate_qualification.py --run-id review001
  python3 scripts/validate_qualification.py --run-id review001 --case-batch run001
  python3 scripts/validate_step1.py --run-id review001
  python3 scripts/validate_step2.py --run-id review001
The qualification generator runs no inference: it checks source revisions and
runtime version, writes cases, and replays static proofs in Python. Qualification
validation runs two fresh processes per case (18 total), retaining both native
and traced logs and replaying captured proofs. validate_step1.py/validate_step2.py
are the earlier machine-diagnostic native runners.
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
Review docs/qualification/03-native-feasibility.txt and its saved traces/proofs
before qualification step four: capture and restore comparable reachable states.
This new series is separate from the old diagnostic interface/proof-audit steps.
The new task's CPU cost gap and time to first available answer remain unmeasured.
Do not implement an estimator or begin the main comparison before validating the
task, reviewing the baseline criteria and studying the papers.

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
