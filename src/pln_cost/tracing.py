"""Three explicit print-only insertions into a generated copy of pinned PLN.

No inference rule or priority is replaced. Successful result constructors log
ordered parents and output, then return the exact original Sentence expression.
The original repository is never edited. Unknown source layout fails closed.
"""
import difflib


def instrument(source):
    changes = (
        ("(Sentence ($Txy $TVxy) $stamp)", "STEP2_BINARY", "(Sentence $x $Ev1) (Sentence $y $Ev2)"),
        ("(Sentence ($Tyx $TVyx) $stamp)", "STEP2_BINARY", "(Sentence $y $Ev2) (Sentence $x $Ev1)"),
        ("(Sentence ($T3 $TV3) $Ev1)", "STEP2_UNARY", "(Sentence $x $Ev1)"),
    )
    traced = source
    for original, marker, parents in changes:
        if traced.count(original) != 1:
            raise ValueError(f"Expected exactly one result constructor: {original}")
        replacement = f"(progn (println! ({marker} {parents} {original})) {original})"
        traced = traced.replace(original, replacement, 1)
    patch = "".join(difflib.unified_diff(
        source.splitlines(keepends=True), traced.splitlines(keepends=True),
        fromfile="pinned-PLN/lib_pln.metta", tofile="generated/lib_pln.traced.metta"))
    return traced, patch
