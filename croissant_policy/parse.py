"""Parse a Croissant + policy document back into the native descriptor model.

This is the whole enforcement path. There is no evaluator in this package: a
profile document is admitted or refused by translating it into the native
descriptor form and handing that to `gate.gate.authorize`, the same function
that produced the measured numbers in `dk-nfcore-admission-gate`.

That choice is what makes fail-closed cheap to believe. The native evaluator
already refuses on a condition whose operator it does not recognise -- its
`_check` falls through to a `ConditionResult(passed=False)`. So the parser does
not implement fail-closed; it *routes into* fail-closed. Every degenerate case
below -- an unknown operator, a condition missing a field, two conditions
fighting over one name, a policy that does not declare `cpol:failClosed` --
becomes a native condition keyed on `unsupportedOperator`, and the existing
gate refuses it with `CONDITION_VIOLATED` and names the offending term.

The property this buys: there is no new enforcement code in this repository
that could be wrong. There is only a translation, and a translation that fails
produces a refusal rather than a gap.
"""

from __future__ import annotations

import json
from pathlib import Path

from .reference import load_gate
from .vocab import CROISSANT_IRI, OPERATORS, PROFILE_IRI, UNSUPPORTED_KEY


class ProfileError(ValueError):
    """The document is not a policy-profile document at all.

    Raised only when there is nothing to evaluate -- not for policy defects.
    A policy defect is a refusal, not an exception; see the module docstring.
    """


def _as_list(value) -> list:
    """JSON-LD lets a single node stand in for a one-element array."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _poison(reason: str):
    """A native condition spec that the reference evaluator refuses on."""
    return {UNSUPPORTED_KEY: reason}


def _condition(node) -> tuple[str, dict]:
    """One `cpol:Condition` node -> one (name, native spec) pair."""
    if not isinstance(node, dict):
        return ("cpol:condition", _poison(f"condition is {type(node).__name__}, not a node"))

    name = node.get("cpol:conditionName")
    if not isinstance(name, str) or not name:
        return ("cpol:conditionName", _poison("condition has no cpol:conditionName"))

    operator = node.get("cpol:operator")
    if not isinstance(operator, str):
        return (name, _poison("condition has no cpol:operator"))

    native_op = OPERATORS.get(operator)
    if native_op is None:
        return (name, _poison(f"operator {operator!r} is outside the closed set"))

    if "cpol:expected" not in node:
        return (name, _poison(f"condition {name!r} has no cpol:expected"))

    return (name, {native_op: node["cpol:expected"]})


def _conditions(nodes: list) -> dict:
    """Collect condition nodes into the native `{name: spec}` dict.

    Two conditions with the same name would collapse into one and quietly drop
    a rule, so a collision poisons the name instead. Losing a rule is the exact
    failure this profile exists to prevent.
    """
    out: dict = {}
    for node in nodes:
        name, spec = _condition(node)
        if name in out:
            out[name] = _poison(f"condition name {name!r} is declared more than once")
            continue
        out[name] = spec
    return out


def _action(node) -> dict | None:
    if not isinstance(node, dict):
        return None
    name = node.get("cpol:actionName")
    if not isinstance(name, str) or not name:
        return None
    return {
        "name": name,
        "requiresState": [s for s in _as_list(node.get("cpol:requiresState")) if isinstance(s, str)],
        "conditions": _conditions(_as_list(node.get("cpol:condition"))),
    }


def _schema(doc: dict) -> dict:
    """Reconstruct the native `schema` block from standard Croissant terms."""
    schema: dict = {}
    for dist in _as_list(doc.get("distribution")):
        if not isinstance(dist, dict) or dist.get("@type") != "cr:FileSet":
            continue
        includes = dist.get("includes")
        if isinstance(includes, str) and includes.startswith("*."):
            schema["format"] = includes[2:]
        break
    for var in _as_list(doc.get("variableMeasured")):
        if isinstance(var, dict) and isinstance(var.get("name"), str):
            schema[var["name"]] = var.get("value")
    return schema


def _provenance(doc: dict, policy: dict) -> dict:
    """Reconstruct the native `provenance` block. Mirrors emit._PROVENANCE_TERMS."""
    from .emit import _ADDITIONAL_PREFIX, _PROVENANCE_TERMS  # local: avoids a cycle

    provenance: dict = {}
    for key, term in _PROVENANCE_TERMS.items():
        if doc.get(term) is not None:
            provenance[key] = doc[term]
    creator = doc.get("creator")
    if isinstance(creator, dict) and creator.get("name"):
        provenance["custodian"] = creator["name"]
    elif isinstance(policy.get("cpol:custodian"), str):
        provenance["custodian"] = policy["cpol:custodian"]
    if policy.get("cpol:retentionDays") is not None:
        provenance["retentionDays"] = policy["cpol:retentionDays"]
    for prop in _as_list(doc.get("additionalProperty")):
        if not isinstance(prop, dict):
            continue
        name = prop.get("name")
        if isinstance(name, str) and name.startswith(_ADDITIONAL_PREFIX):
            provenance[name[len(_ADDITIONAL_PREFIX):]] = prop.get("value")
    return provenance


def to_native_json(doc: dict) -> dict:
    """Profile document -> native descriptor JSON.

    The decision-relevant half -- id, version, state, actions, conditions -- is
    reconstructed exactly. The descriptive half is reconstructed from the
    standard Croissant and schema.org terms the emitter put it in.
    """
    if not isinstance(doc, dict):
        raise ProfileError("document is not a JSON object")

    name = doc.get("name")
    if not isinstance(name, str) or not name:
        raise ProfileError("document has no `name`; nothing identifies the dataset")

    policies = _as_list(doc.get("cpol:policy"))
    if not policies:
        raise ProfileError(
            f"{name!r} carries no cpol:policy. A Croissant document without the "
            "policy layer is not refused by this profile, it is out of scope for "
            "it -- gate it with a policy or do not gate it here."
        )

    # SPEC 3.3 allows exactly one policy. More than one is not a document this
    # profile can evaluate, and picking the first would be a guess about which
    # rules apply. Refuse everything by declaring no actions.
    if len(policies) > 1 or not isinstance(policies[0], dict):
        return {
            "datasetId": name,
            "version": str(doc.get("version", "")),
            "dataType": doc.get("additionalType", ""),
            "state": "",
            "schema": _schema(doc),
            "provenance": {},
            "policy": {},
            "permissibleActions": [],
        }

    policy = policies[0]
    actions = [a for a in (_action(n) for n in _as_list(policy.get("cpol:permissibleAction"))) if a]

    # Conformance clause 4. `cpol:failClosed` is not a mode switch -- there is
    # no permissive mode to switch to -- so a document that fails to declare it
    # is a document whose author's intent is unknown. Every declared action
    # gets a condition the evaluator refuses on, and `requiresState` is dropped
    # so that a state precondition cannot pre-empt the refusal and report a
    # less specific reason than the real one.
    if policy.get("cpol:failClosed") is not True:
        actions = [
            {
                "name": a["name"],
                "requiresState": [],
                "conditions": {
                    "cpol:failClosed": _poison(
                        "policy does not declare cpol:failClosed = true (SPEC 3.4)"
                    )
                },
            }
            for a in actions
        ]

    provenance = _provenance(doc, policy)

    native_policy: dict = {}
    if policy.get("cpol:classification"):
        native_policy["classification"] = policy["cpol:classification"]
    if policy.get("cpol:rationale"):
        native_policy["rationale"] = policy["cpol:rationale"]

    state = policy.get("cpol:state")
    return {
        "datasetId": name,
        "version": str(doc.get("version", "")),
        "dataType": doc.get("additionalType", ""),
        "state": state if isinstance(state, str) else "",
        "schema": _schema(doc),
        "provenance": provenance,
        "policy": native_policy,
        "permissibleActions": actions,
    }


def to_descriptor(doc: dict):
    """Profile document -> the gate's own `Descriptor` object."""
    descriptor_mod, _, _ = load_gate()
    return descriptor_mod.Descriptor.from_json(to_native_json(doc))


def load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def authorize(doc: dict, action: str, context: dict):
    """Decide an admission request from a profile document.

    One line of policy logic lives in this package, and it is this: translate,
    then defer.
    """
    _, _, gate_mod = load_gate()
    return gate_mod.authorize(to_descriptor(doc), action, context)


def conforms_to_profile(doc: dict) -> bool:
    """Cheap check that a document claims both IRIs (SPEC 3.2)."""
    claimed = _as_list(doc.get("conformsTo"))
    return CROISSANT_IRI in claimed and PROFILE_IRI in claimed
