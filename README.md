# PLN computation-cost experiment

A controlled test of whether predicted expansion cost improves PLN's selection
within confidence ties after charging online overhead. **The completed benchmark
did not show a consistent incremental benefit over usefulness guidance alone.**

## Start here

1. [Method and code map](docs/method.md): tasks, BB/PQT, four selectors, predictor,
   CPU accounting and proof checks.
2. [Results](docs/results.md): the single complete findings document, including
   negative and inconclusive outcomes.
3. Read a captured execution:

```sh
python3 scripts/demo.py --case n001-canonical_ids --mode N
python3 scripts/demo.py --case n001-canonical_ids --mode BC
```

These commands read and verify saved traces; they do not run timing experiments.
They print selected statements, new beliefs, the pending queue and the answer.

## Repository layout

```text
configs/                 Runtime pins and current reproduction configuration
src/pln_cost/            Selection, workloads, timing, proof and runtime code
tests/                   Current correctness and regression tests
scripts/demo.py          Walk through one saved query; optional native check
scripts/fit_cost_model.py Refit/verify the predictor from existing development data
scripts/run_benefit_benchmark.py  Prepare and measure a new reproduction batch
scripts/analyze_benefit_benchmark.py  Verify the completed batch without rerunning it
data/training/           Original development labels, CV and fitting provenance
docs/method.md           One explanation of the experiment and code
docs/results.md          One results narrative
results/benefit-benchmark/run001/  Frozen final benchmark and its original evidence
```

The old machine-failure task, step-by-step journals, interrupted/calibration runs,
old experiment drivers and redundant result notes have been removed from the
working tree. They remain in Git history at `95a1125cc8c326ce9af49a3f78e8072ace531ecc`.
Only the final benchmark and its dependencies remain in the working tree.
Earlier baseline summaries are available in Git history at
`c4af6a92b` under `results/baselines/`. The remaining source modules support the
benchmark, proof verification, predictor fitting or saved-trace walkthrough;
`tests/` checks those components. Training data and fitting provenance explain
and reproduce the predictor used in the final comparison.

## Validate without measuring new performance

```sh
python3 -m unittest discover -s tests
python3 scripts/fit_cost_model.py
python3 scripts/analyze_benefit_benchmark.py --run-id run001
```

The refit needs NumPy; it checks the frozen coefficients without overwriting them.
The full analysis checks all 10,368 saved query records, raw-output hashes,
proofs, accounting and aggregates. It does not overwrite the original report.
An optional `--output /new/path.json` saves a fresh verification report.

## Native runtime and reproduction

[Runtime configuration](configs/runtime.json) points to the existing external
PLN/PeTTa/SWI-Prolog setup under `../research-discovery/step-03/`. That external
runtime has not been moved or deleted. The code checks exact repository commits
and clean working trees before execution. The historical native bootstrap also
contains the original absolute project path; it must be regenerated when moving
the project to a different machine.

One real query, for correctness rather than timing conclusions:

```sh
python3 scripts/demo.py --case n001-canonical_ids --mode BC --native
```

A complete new reproduction is intentionally explicit and potentially lengthy:

```sh
python3 scripts/run_benefit_benchmark.py --phase prepare --run-id reproduction001
python3 scripts/run_benefit_benchmark.py --phase measure --run-id reproduction001
python3 scripts/analyze_benefit_benchmark.py --run-id reproduction001
```

Preparation qualifies every current trajectory before any timing sweep. Existing
run directories cannot be overwritten. These are now known tasks; replaying their
historical development/reserved labels does not create a fresh held-out study.
The reproduction runner rebuilds adapters from current code rather than requiring
all the deleted prerequisite steps.

## Evidence preservation

The final batch's fixtures, audits, individual results, failures, model, schedule
and original reports remain intact. `source-snapshot.zip` is a compact archive of
99 original source/input files needed to check historical frozen hashes; it is
not a second active codebase. Historical-source verification is explicitly separate
from testing the cleaned current code. Keeping raw evidence is necessary to verify
results; the Markdown report alone cannot replace it.

Cleanup validation passed: 75 unit tests, coefficient reproduction from the
retained training data, byte-identical generated native adapters, and fresh
correctness qualification of all 108 case/mode trajectories in a temporary
directory. The read-only audit rechecked all 10,368 recorded queries and 5,557
detected proofs with unchanged findings. No new performance sweep was run.
