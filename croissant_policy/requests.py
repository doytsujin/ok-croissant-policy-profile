"""Enumerating the request space a policy decides over.

Listing test requests by hand covers the cases somebody thought of on the day
they wrote them, and stops covering a policy the moment a condition is added.
These generate the requests from the policy itself: the satisfying context, the
empty one, one violation per condition, and a wrong-typed value for every
numeric condition.

Used by the test suite and by the precedence experiment, which is why it lives
in the package rather than under tests/.
"""

from __future__ import annotations


def satisfying_value(spec):
    """A context value that passes this native condition spec."""
    if not isinstance(spec, dict):
        return spec
    if "min" in spec:
        return spec["min"]
    if "max" in spec:
        return spec["max"]
    if "in" in spec:
        return spec["in"][0] if spec["in"] else None
    if "equals" in spec:
        return spec["equals"]
    if "present" in spec:
        return "anything" if spec["present"] else None
    return "unknown-operator-cannot-be-satisfied"


def violating_value(spec):
    """A context value that fails this native condition spec."""
    if not isinstance(spec, dict):
        return "not-the-expected-scalar"
    if "min" in spec:
        return spec["min"] - 1
    if "max" in spec:
        return spec["max"] + 1
    if "in" in spec:
        return "not-in-the-list"
    if "equals" in spec:
        return "not-equal"
    if "present" in spec:
        return None if spec["present"] else "unexpectedly-present"
    return None


def satisfying_context(action: dict) -> dict:
    conditions = action.get("conditions", {}) or {}
    return {k: satisfying_value(v) for k, v in conditions.items()}


def request_matrix(native: dict, include_undeclared: bool = True) -> list[tuple[str, dict]]:
    """(action, context) pairs covering permit, every refusal class, and noise."""
    cases: list[tuple[str, dict]] = []
    for action in native.get("permissibleActions", []):
        name = action["name"]
        conditions = action.get("conditions", {}) or {}
        satisfying = satisfying_context(action)

        cases.append((name, dict(satisfying)))
        cases.append((name, {}))
        cases.append((name, {"irrelevant": "value"}))
        for key in conditions:
            ctx = dict(satisfying)
            ctx[key] = violating_value(conditions[key])
            cases.append((name, ctx))
        for key, spec in conditions.items():
            if isinstance(spec, dict) and ("min" in spec or "max" in spec):
                ctx = dict(satisfying)
                ctx[key] = "not-a-number"
                cases.append((name, ctx))

    if include_undeclared:
        cases.append(("no-such-action", {}))
        cases.append(("", {}))
    return cases
