"""Read the ground, unquoted S-expressions used by this fixture and its trace.

This intentionally is not a general MeTTa parser or evaluator. No Python eval.
"""
import re


def read_forms(text):
    text = re.sub(r";[^\n]*", "", text)
    if '"' in text:
        raise ValueError("Quoted strings are outside this ground-fixture parser")
    forms, stack = [], []
    for token in re.findall(r"\(|\)|[^\s()]+", text):
        if token.startswith("$"):
            raise ValueError("Variables are outside this ground-fixture parser")
        if token == "(":
            stack.append([])
            continue
        if token == ")":
            if not stack:
                raise ValueError("Unbalanced closing parenthesis")
            value = stack.pop()
        else:
            try:
                value = int(token)
            except ValueError:
                try:
                    value = float(token)
                except ValueError:
                    value = token
        (stack[-1] if stack else forms).append(value)
    if stack:
        raise ValueError("Unclosed parenthesis")
    return forms


def read_one(text):
    forms = read_forms(text)
    if len(forms) != 1:
        raise ValueError("Expected exactly one expression")
    return forms[0]


def read_case(text):
    """Extract the external input contract; reject unfamiliar executable forms."""
    marginals, inputs, query = {}, None, None
    for form in read_forms(text):
        if form == "!":
            continue
        if not isinstance(form, list):
            raise ValueError("Unsupported fixture form")
        if len(form) == 3 and form[0] == "=" and isinstance(form[1], list):
            lhs, rhs = form[1:]
            if len(lhs) == 2 and lhs[0] == "STV" and isinstance(lhs[1], str):
                if lhs[1] in marginals:
                    raise ValueError("Duplicate marginal")
                marginals[lhs[1]] = rhs
                continue
            if lhs == ["kb"] and inputs is None:
                inputs = rhs
                continue
        if (len(form) == 2 and form[0] == "println!" and isinstance(form[1], list)
                and len(form[1]) == 2 and form[1][0] == "STEP1_RESULT"):
            call = form[1][1]
            if (isinstance(call, list) and len(call) == 6 and call[:2] == ["PLN.Query", ["kb"]]
                    and query is None):
                query = call[2]
                continue
        raise ValueError(f"Unsupported fixture form: {form}")
    if not marginals or not inputs or query is None:
        raise ValueError("Incomplete fixture contract")
    return {"inputs": inputs, "marginals": marginals, "query": query}
