"""Shared fixtures: the real descriptor corpus and a generated request matrix.

The corpus is the three descriptors from `dk-nfcore-admission-gate`, not
hand-written fixtures. Testing the profile against invented descriptors would
prove the profile is self-consistent; testing it against the descriptors that
gated a real pipeline run is what the equivalence claim is about.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from croissant_policy.reference import gate_root  # noqa: E402


def corpus() -> dict[str, dict]:
    """Every native descriptor in the reference repository, by dataset id."""
    out = {}
    for path in sorted((gate_root() / "descriptors").glob("*.json")):
        native = json.loads(path.read_text())
        out[native["datasetId"]] = native
    return out


def _satisfying_value(spec):
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


def _violating_value(spec):
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


def request_matrix(native: dict) -> list[tuple[str, dict]]:
    """(action, context) pairs covering permit, every refusal class, and noise.

    Generated from the descriptor rather than listed, so a new condition in the
    corpus is covered the day it lands instead of the day somebody remembers to
    extend the test.
    """
    cases: list[tuple[str, dict]] = []
    for action in native.get("permissibleActions", []):
        name = action["name"]
        conditions = action.get("conditions", {}) or {}
        satisfying = {k: _satisfying_value(v) for k, v in conditions.items()}

        cases.append((name, dict(satisfying)))          # everything passes
        cases.append((name, {}))                        # nothing supplied
        cases.append((name, {"irrelevant": "value"}))   # keys no condition names
        for key in conditions:                          # one violation at a time
            ctx = dict(satisfying)
            ctx[key] = _violating_value(conditions[key])
            cases.append((name, ctx))
        # A value of the wrong type, which numeric comparisons must not coerce.
        for key, spec in conditions.items():
            if isinstance(spec, dict) and ("min" in spec or "max" in spec):
                ctx = dict(satisfying)
                ctx[key] = "not-a-number"
                cases.append((name, ctx))

    cases.append(("no-such-action", {}))
    cases.append(("", {}))
    return cases


def record(decision) -> dict:
    """A decision record with the timing removed, so two runs compare equal."""
    rec = decision.as_record()
    rec.pop("evalMicros", None)
    return rec
