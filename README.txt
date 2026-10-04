PLN computation-cost experiments
===============================

Research question
Does adding predicted computational cost to an existing PLN selection method
improve answer speed and probabilistic accuracy after including its overhead?
Improvement, no benefit and harm are all legitimate experimental outcomes.

Status: project initialized on 2026-10-04. No experiment implementation yet.

The experiment will be Python-led, using the actual pinned PLN MeTTa rules.
Python/runtime compatibility and the baseline must be validated before adding
a cost estimator. The exact runtime interface remains to be verified.

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

Next step for discussion
Implement only the small example and Python-PLN compatibility validation.
Do not begin the cost estimator, training or a performance benchmark yet.

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
