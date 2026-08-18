"""The caller-side half: an agent control plane's scope, in the same shape.

An agent control plane binds policy to the *caller*. It holds a registry of
agents with an owner and a scope, evaluates each action against approved policy
inline before execution, and blocks violations. The profile in this repository
binds policy to the *data*. Neither is complete, and this module exists so that
the two can be run against each other.

A `CallerScope` is deliberately structured like a dataset descriptor:

    callerId      what the dataset descriptor calls datasetId
    assurance     what it calls state -- the caller's own lifecycle
    entitlements  what it calls permissibleActions

and it is translated into the native descriptor model and handed to the same
`gate.authorize`. Using one evaluator for both sides is an experimental control,
not a shortcut: if the two halves used different evaluators, a disagreement
could come from the evaluators rather than from the policies, and precedence
would not be the only variable.

What this is NOT: a measurement of any vendor's control plane. It is a model of
the structure those products describe -- registry, inline pre-execution
decision, evidence -- built so the interaction can be studied. Every number
derived from it is designed, not measured. The data side is the opposite: those
descriptors gated a real pipeline run.

The asymmetry that matters is visible in the shape. A caller scope can condition
on the request and on the caller's own assurance. It cannot condition on the
dataset's state, because that fact does not travel with the caller. Section 8 of
SPEC.md notes the mirror-image gap on the data side: the profile has no identity
model. Each half is blind to exactly what the other one knows.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .reference import load_gate

# The context key through which a caller scope sees which dataset is being acted
# on. The caller knows the name; it does not know the state.
DATASET_KEY = "dataset"


class ScopeError(ValueError):
    """The scope document cannot be evaluated at all."""


@dataclass(frozen=True)
class CallerScope:
    caller_id: str
    version: str
    assurance: str
    entitlements: tuple

    @classmethod
    def from_json(cls, obj: dict) -> "CallerScope":
        for required in ("callerId", "version", "assurance"):
            if required not in obj:
                raise ScopeError(f"caller scope missing {required!r}")
        return cls(
            caller_id=obj["callerId"],
            version=obj["version"],
            assurance=obj["assurance"],
            entitlements=tuple(obj.get("entitlements", [])),
        )

    @classmethod
    def load(cls, path: str | Path) -> "CallerScope":
        return cls.from_json(json.loads(Path(path).read_text()))

    def to_native_json(self) -> dict:
        """The scope in the descriptor model, so the reference gate can decide it."""
        return {
            "datasetId": self.caller_id,
            "version": self.version,
            "dataType": "caller_scope",
            "state": self.assurance,
            "schema": {},
            "provenance": {},
            "policy": {},
            "permissibleActions": [
                {
                    "name": e.get("action", ""),
                    # An entitlement conditioned on the caller's assurance is the
                    # caller-side analogue of a dataset state precondition, and
                    # it is the one thing a data-side descriptor cannot express.
                    "requiresState": list(e.get("requiresAssurance", [])),
                    "conditions": e.get("conditions", {}) or {},
                }
                for e in self.entitlements
            ],
        }

    def to_descriptor(self):
        descriptor_mod, _, _ = load_gate()
        return descriptor_mod.Descriptor.from_json(self.to_native_json())

    def authorize(self, action: str, context: dict):
        """Decide from the caller's side alone."""
        _, _, gate_mod = load_gate()
        return gate_mod.authorize(self.to_descriptor(), action, context)


def load_all(directory: str | Path) -> dict[str, CallerScope]:
    out: dict[str, CallerScope] = {}
    for path in sorted(Path(directory).glob("*.json")):
        scope = CallerScope.load(path)
        out[scope.caller_id] = scope
    return out
