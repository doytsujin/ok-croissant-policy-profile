"""The ODRL carrier: the same policy, in the place Croissant 1.1 puts policy.

Croissant 1.1 added a governance section that carries data use conditions in
`sc:usageInfo`, recommends DUO for simple conditions and ODRL for fine-grained
ones. It does not say how any of them is evaluated. That is the gap this package
exists to fill, and it raises an obvious question about this package's own
design: if ODRL is the sanctioned carrier, why does `cpol:` exist at all?

This module answers it by construction rather than by argument. It expresses
exactly the same policy as an ODRL Set carried in `sc:usageInfo`, parses it back
through the same translation, and hands the result to the same
`gate.authorize`. `tests/test_carrier_equivalence.py` then checks that whole
decision records -- not verdicts -- match across the two carriers over the
generated request matrix.

If they match, the claim the profile actually makes is the true one: the
contribution is the evaluation semantics, and it is independent of the carrier.
The `cpol:` form is normative because it is smaller and because a Croissant
consumer meets it without a second vocabulary; it is not load-bearing.

Two things worth knowing before reading the mapping.

**Four of the five operators are ODRL core.** `min`, `max`, `in` and `equals`
are `odrl:gteq`, `odrl:lteq`, `odrl:isAnyOf` and `odrl:eq`. Only `present` has
no ODRL equivalent -- the vocabulary defines no existence operator -- so the
profile mints one. The expressiveness objection to ODRL was never the real
disagreement, and this table is the evidence.

**ODRL already fails closed at profile granularity, and we use it.** The
Information Model (Section 3.2) requires that a processing system which does
not recognise a profile identifier MUST stop processing the policy. `_policy`
below implements exactly that: an unrecognised `odrl:profile` poisons every
action rather than being ignored. What ODRL does not specify is what happens to
an operator it does not implement *inside* a profile it does recognise, or what
the surrounding system concludes from a halted evaluation. Those are the two
this package answers, and they are the two `cpol:failClosed` is about.
"""

from __future__ import annotations

from .emit import emit as emit_cpol
from .vocab import (CROISSANT_IRI, OPERATORS, PROFILE_IRI, UNSUPPORTED_KEY,
                    conformance_claim, context, operand_defect)

ODRL_NS = "http://www.w3.org/ns/odrl/2/"

# The ODRL profile this carrier conforms to. A distinct IRI from the cpol:
# namespace: they identify different things -- one a set of Croissant terms, the
# other a set of ODRL terms -- and conflating them would make the `odrl:profile`
# check below meaningless.
ODRL_PROFILE_IRI = PROFILE_IRI + "/odrl"
CPOL_ODRL_NS = ODRL_PROFILE_IRI + "#"

# cpol operator -> ODRL operator IRI.
#
# Four resolve to ODRL core. `present` is minted, because ODRL defines no
# existence operator; that is a gap in ODRL rather than a preference of ours,
# and minting an Operator instance is precisely what Section 3.3 of the
# Information Model permits a profile to do.
_TO_ODRL_OPERATOR = {
    "cpol:min": ODRL_NS + "gteq",
    "cpol:max": ODRL_NS + "lteq",
    "cpol:in": ODRL_NS + "isAnyOf",
    "cpol:equals": ODRL_NS + "eq",
    "cpol:present": CPOL_ODRL_NS + "isPresent",
}
_FROM_ODRL_OPERATOR = {v: k for k, v in _TO_ODRL_OPERATOR.items()}

# The dataset's lifecycle state is not an ODRL core left operand -- ODRL's
# operands are about the transaction, not about the scientific state of the
# thing being transacted -- so the profile mints it. This is the term that made
# the incomparability result in the paper what it is: no caller-side authority
# can predicate on it, because it is not a property of the caller.
LEFT_STATE = CPOL_ODRL_NS + "datasetState"

# Request-context keys become minted left operands under a common path, one per
# condition name. The set is open because it comes from the descriptor, which is
# how a domain profile of ODRL normally works: the domain's properties become
# the domain's left operands.
_LEFT_CTX = CPOL_ODRL_NS + "ctx/"

# Action names likewise. ODRL's core actions (use, read, distribute...) do not
# name what a bioinformatics gate admits -- `qc`, `trim`, `align` -- and reusing
# `odrl:use` for all of them would erase the distinction the policy is about.
_ACTION = CPOL_ODRL_NS + "action/"


def _iri(node) -> str | None:
    """An ODRL term reference, which JSON-LD may write as a node or a string."""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        value = node.get("@id")
        return value if isinstance(value, str) else None
    return None


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def odrl_context() -> dict:
    """The `@context` of a document using the ODRL carrier.

    Croissant's context plus the two prefixes this carrier needs. The `cpol`
    prefix is *not* added: a document carrying the ODRL form carries no `cpol:`
    terms at all, which is what makes the equivalence test a comparison of
    carriers rather than of two spellings of the same one.
    """
    ctx = dict(context())
    del ctx["cpol"]
    del ctx["cpol:expected"]
    ctx["odrl"] = ODRL_NS
    ctx["cpolodrl"] = CPOL_ODRL_NS
    # A right operand is arbitrary JSON for the same reason cpol:expected is:
    # a number, a string, a boolean or an array. Without the typing a JSON-LD
    # processor reads an array as a set of nodes.
    ctx["odrl:rightOperand"] = {"@id": "odrl:rightOperand", "@type": "@json"}
    return ctx


# --------------------------------------------------------------------- emit


def _constraint(left: str, operator: str, right) -> dict:
    return {
        "@type": "odrl:Constraint",
        "odrl:leftOperand": {"@id": left},
        "odrl:operator": {"@id": operator},
        "odrl:rightOperand": right,
    }


def _permission(action: dict) -> dict:
    """One `cpol:Action` node -> one `odrl:Permission`.

    The state precondition and the request conditions become constraints of the
    same kind, distinguished only by their left operand. That is deliberate:
    the native evaluator checks state first and conditions second, and the
    parser below restores that split from the left operand alone.
    """
    node: dict = {
        "@type": "odrl:Permission",
        "odrl:action": {"@id": _ACTION + action["cpol:actionName"]},
    }
    constraints: list[dict] = []

    states = _as_list(action.get("cpol:requiresState"))
    if states:
        constraints.append(_constraint(LEFT_STATE, ODRL_NS + "isAnyOf", states))

    for condition in _as_list(action.get("cpol:condition")):
        # A malformed document must produce a refusal, never an exception. The
        # cpol: parser poisons a condition that is not a node; the carrier has
        # to survive the same input and arrive at the same refusal, or the two
        # carriers stop being equivalent exactly where equivalence matters.
        # Found by the conformance corpus, which generates this case.
        if not isinstance(condition, dict):
            constraints.append(_constraint(
                _LEFT_CTX + "malformed",
                CPOL_ODRL_NS + "unmapped/not-a-node",
                f"condition is {type(condition).__name__}, not a node",
            ))
            continue
        name = condition.get("cpol:conditionName")
        operator = condition.get("cpol:operator")
        # An operator outside the closed set is carried through as an
        # unmapped IRI rather than dropped. Equivalence has to hold for the
        # bad documents too, and a carrier that quietly discards a rule it
        # cannot express is the failure this whole profile exists to prevent.
        constraints.append(
            _constraint(
                _LEFT_CTX + str(name),
                _TO_ODRL_OPERATOR.get(operator, CPOL_ODRL_NS + "unmapped/" + str(operator)),
                condition.get("cpol:expected"),
            )
        )

    if constraints:
        node["odrl:constraint"] = constraints
    return node


def policy_node(cpol_policy: dict, dataset_id: str) -> dict:
    """A `cpol:Policy` node -> the equivalent `odrl:Set`.

    `odrl:Set` rather than Agreement or Offer, because a Set is ODRL's policy
    without parties, and this profile has no identity model. Choosing a
    subclass that names an assigner would be inventing an actor the descriptor
    does not know about.
    """
    node: dict = {
        "@type": "odrl:Set",
        "odrl:uid": f"{dataset_id}#policy",
        "odrl:profile": {"@id": ODRL_PROFILE_IRI},
        # The lifecycle state of the dataset now, against which each
        # permission's state constraint is evaluated.
        "cpolodrl:datasetState": cpol_policy.get("cpol:state", ""),
        # Not derivable from ODRL. Section 3.2 gives fail-closed against an
        # unknown *profile*; this declares the author's intent for a condition
        # the evaluator cannot evaluate inside a profile it does recognise,
        # which ODRL leaves open.
        "cpolodrl:failClosed": cpol_policy.get("cpol:failClosed"),
    }
    for source, target in (
        ("cpol:classification", "cpolodrl:classification"),
        ("cpol:custodian", "cpolodrl:custodian"),
        ("cpol:retentionDays", "cpolodrl:retentionDays"),
        ("cpol:rationale", "cpolodrl:rationale"),
    ):
        if cpol_policy.get(source) is not None:
            node[target] = cpol_policy[source]

    node["odrl:permission"] = [
        _permission(a) for a in _as_list(cpol_policy.get("cpol:permissibleAction"))
    ]
    if cpol_policy.get("cpol:decisionRecord"):
        node["cpolodrl:decisionRecord"] = cpol_policy["cpol:decisionRecord"]
    return node


def to_odrl(doc: dict) -> dict:
    """A `cpol:` document -> the same document with the ODRL carrier.

    Everything outside the policy node is preserved byte for byte. That is what
    makes the equivalence test in `tests/test_carrier_equivalence.py` a
    comparison of carriers and not of two independently written documents: the
    descriptive half is not merely equivalent between them, it is identical.
    """
    policies = _as_list(doc.get("cpol:policy"))
    if len(policies) != 1 or not isinstance(policies[0], dict):
        raise ValueError(
            "the ODRL carrier is defined for a document with exactly one "
            "cpol:policy; SPEC 3.3 allows no other shape"
        )

    out = {k: v for k, v in doc.items() if k not in ("@context", "cpol:policy", "conformsTo")}
    result: dict = {"@context": odrl_context()}
    result["@type"] = out.pop("@type", "sc:Dataset")
    result["name"] = out.pop("name")
    result["description"] = out.pop("description", "")
    result["conformsTo"] = conformance_claim(ODRL_PROFILE_IRI)
    result.update(out)
    result["usageInfo"] = policy_node(policies[0], doc["name"])
    return result


def emit(native: dict, **kwargs) -> dict:
    """Native descriptor -> Croissant document carrying an ODRL policy."""
    return to_odrl(emit_cpol(native, **kwargs))


# -------------------------------------------------------------------- parse


def _poison(reason: str) -> dict:
    return {UNSUPPORTED_KEY: reason}


def _native_condition(constraint) -> tuple[str, dict]:
    """One `odrl:Constraint` -> one (name, native spec) pair."""
    if not isinstance(constraint, dict):
        return ("odrl:constraint", _poison(
            f"constraint is {type(constraint).__name__}, not a node"))

    left = _iri(constraint.get("odrl:leftOperand"))
    if not isinstance(left, str) or not left.startswith(_LEFT_CTX):
        return ("odrl:leftOperand", _poison(
            f"left operand {left!r} is not a request-context operand of this profile"))
    name = left[len(_LEFT_CTX):]
    if not name:
        return ("odrl:leftOperand", _poison("left operand names no context key"))

    operator = _iri(constraint.get("odrl:operator"))
    cpol_operator = _FROM_ODRL_OPERATOR.get(operator)
    if cpol_operator is None:
        return (name, _poison(f"operator {operator!r} is outside the closed set"))

    if "odrl:rightOperand" not in constraint:
        return (name, _poison(f"constraint {name!r} has no odrl:rightOperand"))

    # Same rule as the cpol: carrier, from the same table. A carrier that
    # accepted an operand the other refuses would break equivalence exactly
    # where it matters.
    defect = operand_defect(cpol_operator, constraint["odrl:rightOperand"])
    if defect is not None:
        return (name, _poison(defect))

    return (name, {OPERATORS[cpol_operator]: constraint["odrl:rightOperand"]})


def _native_action(permission) -> dict | None:
    if not isinstance(permission, dict):
        return None
    action = _iri(permission.get("odrl:action"))
    if not isinstance(action, str) or not action.startswith(_ACTION):
        return None
    name = action[len(_ACTION):]
    if not name:
        return None

    requires: list[str] = []
    conditions: dict = {}
    for constraint in _as_list(permission.get("odrl:constraint")):
        left = _iri(constraint.get("odrl:leftOperand")) if isinstance(constraint, dict) else None
        if left == LEFT_STATE:
            right = constraint.get("odrl:rightOperand")
            requires = [s for s in _as_list(right) if isinstance(s, str)]
            continue
        key, spec = _native_condition(constraint)
        if key in conditions:
            conditions[key] = _poison(f"condition name {key!r} is declared more than once")
            continue
        conditions[key] = spec

    return {"name": name, "requiresState": requires, "conditions": conditions}


def to_native_json(doc: dict) -> dict:
    """ODRL-carrier document -> native descriptor JSON.

    The same shape `parse.to_native_json` produces from the `cpol:` carrier,
    which is the whole point: from here down there is one code path, one
    evaluator, and one decision record.
    """
    from .parse import ProfileError, _provenance, _refuse_everything, _schema

    if not isinstance(doc, dict):
        raise ProfileError("document is not a JSON object")
    name = doc.get("name")
    if not isinstance(name, str) or not name:
        raise ProfileError("document has no `name`; nothing identifies the dataset")

    sets = _as_list(doc.get("usageInfo"))
    sets = [s for s in sets if isinstance(s, dict) and s.get("@type") == "odrl:Set"]
    if not sets:
        raise ProfileError(
            f"{name!r} carries no odrl:Set in usageInfo. A Croissant document "
            "without a policy is out of scope for this profile, not refused by it."
        )
    if len(sets) > 1:
        return _refuse_everything(doc, "more than one odrl:Set in usageInfo")

    policy = sets[0]

    # ODRL Information Model, Section 3.2: an ODRL Processing system that does
    # not recognise the profile identifier MUST stop processing the policy.
    # This is the one fail-closed property the profile inherits rather than
    # argues for, and it is stronger than anything we could have written.
    declared = _iri(policy.get("odrl:profile"))
    if declared != ODRL_PROFILE_IRI:
        return _refuse_everything(
            doc, f"unrecognised ODRL profile {declared!r} (Information Model 3.2)"
        )

    actions = [a for a in (_native_action(p) for p in _as_list(policy.get("odrl:permission"))) if a]

    # Conformance clause 4, unchanged in the ODRL carrier. ODRL gives no
    # equivalent, which is exactly why the profile has to.
    if policy.get("cpolodrl:failClosed") is not True:
        actions = [
            {
                "name": a["name"],
                "requiresState": [],
                "conditions": {
                    "cpol:failClosed": _poison(
                        "policy does not declare failClosed = true (SPEC 3.4)"
                    )
                },
            }
            for a in actions
        ]

    # `_provenance` reads the descriptive half from standard Croissant terms and
    # the two facts that live on the policy node. Re-key the ODRL node so the
    # one function serves both carriers rather than growing a second copy.
    as_cpol = {
        "cpol:custodian": policy.get("cpolodrl:custodian"),
        "cpol:retentionDays": policy.get("cpolodrl:retentionDays"),
    }
    provenance = _provenance(doc, {k: v for k, v in as_cpol.items() if v is not None})

    native_policy: dict = {}
    if policy.get("cpolodrl:classification"):
        native_policy["classification"] = policy["cpolodrl:classification"]
    if policy.get("cpolodrl:rationale"):
        native_policy["rationale"] = policy["cpolodrl:rationale"]

    state = policy.get("cpolodrl:datasetState")
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
    """ODRL-carrier document -> the gate's own `Descriptor` object."""
    from .reference import load_gate

    descriptor_mod, _, _ = load_gate()
    return descriptor_mod.Descriptor.from_json(to_native_json(doc))


def authorize(doc: dict, action: str, context: dict):
    """Decide an admission request from an ODRL-carrier document.

    Same one line of policy logic as `parse.authorize`: translate, then defer.
    """
    from .reference import load_gate

    _, _, gate_mod = load_gate()
    return gate_mod.authorize(to_descriptor(doc), action, context)


def main(argv: list[str] | None = None) -> int:
    """Emit the ODRL carrier for the same descriptors `emit` takes.

    A separate entry point rather than a flag on `emit`, because the two
    carriers are two artifacts and a reader comparing them should be able to
    see both on disk at once.
    """
    import argparse
    import json
    import sys
    from pathlib import Path

    from .emit import EmitError, emit_file

    ap = argparse.ArgumentParser(
        prog="croissant_policy.odrl",
        description="Emit Croissant documents carrying an ODRL policy in usageInfo",
    )
    ap.add_argument("descriptors", nargs="+", type=Path)
    ap.add_argument("--outdir", type=Path, default=None,
                    help="write <name>.odrl.croissant.json here; default is stdout")
    ap.add_argument("--url")
    ap.add_argument("--license")
    ap.add_argument("--cite-as")
    ap.add_argument("--date-published")
    ap.add_argument("--decision-record")
    args = ap.parse_args(argv)

    overrides = dict(
        url=args.url,
        license=args.license,
        cite_as=args.cite_as,
        date_published=args.date_published,
        decision_record=args.decision_record,
    )

    for path in args.descriptors:
        try:
            doc = to_odrl(emit_file(path, **overrides))
        except (EmitError, ValueError) as exc:
            print(f"odrl: {path}: {exc}", file=sys.stderr)
            return 1
        text = json.dumps(doc, indent=2, sort_keys=False) + "\n"
        if args.outdir:
            args.outdir.mkdir(parents=True, exist_ok=True)
            out = args.outdir / f"{doc['name']}.odrl.croissant.json"
            out.write_text(text)
            print(f"odrl: {path} -> {out}", file=sys.stderr)
        else:
            sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
