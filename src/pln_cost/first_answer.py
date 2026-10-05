"""Create a quiet native library without changing reasoning behavior."""
import difflib
from .expansion import replace_once


def quiet_library(source):
    quiet = replace_once(source, "(println! (SELECTED (Sentence $x $Ev1)))", "()")
    patch = "".join(difflib.unified_diff(source.splitlines(True), quiet.splitlines(True),
                    fromfile="pinned-PLN/lib_pln.metta", tofile="generated/lib_pln.quiet.metta"))
    return quiet, patch
