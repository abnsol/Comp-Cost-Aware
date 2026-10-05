"""Reject failed native execution before interpreting a query result."""


def clean_completion(run):
    # Fail closed; inspect unexpected diagnostics rather than silently ignoring them.
    return (run["returncode"] == 0 and not run["timed_out"]
            and not run["stderr"].strip() and "❌" not in run["stdout"]
            and "Assertion failed" not in run["stdout"])
