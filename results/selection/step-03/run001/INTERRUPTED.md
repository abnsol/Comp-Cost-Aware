# Interrupted measurement batch — exclude from fitting

This partial batch was deliberately stopped with SIGINT after the operator
started a unit-test process during profiling. The tests were also stopped.
This violates the intended no-competing-experiment workload condition.

All partial fixtures, logs, labels and the last saved report are retained. The
report's `passed` field remains false. Do not pool its timing rows with a later
batch or use them for fitting. No timing threshold, input, feature or schedule
was changed in response to these measurements. A complete new batch, run002,
will repeat the predefined procedure without concurrent tests. Its results,
including unresolved timing rows, must be retained without selective replacement.
