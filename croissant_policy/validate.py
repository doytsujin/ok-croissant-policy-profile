"""Conformance checking, and the strip that conformance clause 1 is about.

Two things live here because they are the same question asked twice. `strip()`
removes the policy layer and asks what is left; `validate()` asks whether the
document was allowed to add that layer in the first place.

What this does not do is claim the document is valid Croissant. Only MLCommons'
`mlcroissant` can say that, and it is a separate step --
`tools/validate_mlcroissant.py` -- because it pulls in pandas, numpy, scipy and
rdflib while this package stays standard library only. The warning on every
report says so, rather than letting a structural check be mistaken for the real
thing. SPEC section 9 records the outcome of running it: as of mlcroissant
1.1.0, all three documents in `examples/` load with zero errors and the
`@context` matches MLCommons' generated one exactly.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .parse import _as_list
from .vocab import (CPOL_NS, CROISSANT_CONTEXT, CROISSANT_IRI, OPERATORS,
                    PROFILE_IRI, claimed_iris, operand_defect)

_MLCROISSANT_WARNING = (
    "this validator checks the profile's conformance clauses structurally and does not "
    "parse JSON-LD; run tools/validate_mlcroissant.py for Croissant validity "
    "(SPEC section 9)"
)


@dataclass
class Report:
    conforms: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, msg: str) -> None:
        self.conforms = False
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def as_json(self) -> dict:
        return {"conforms": self.conforms, "errors": self.errors, "warnings": self.warnings}


def _is_cpol(key: str) -> bool:
    return key == "cpol" or key.startswith("cpol:")


def strip(doc: dict) -> dict:
    """The document with the profile removed, recursively.

    This is the operation conformance clause 1 is written about: what is left
    when the policy layer goes away.

    The profile IRI comes out of `conformsTo` along with the terms, and that is
    not a detail. A document that still claims conformance to the profile while
    carrying none of its terms is a document that fails the profile's own
    clause 3 -- it would be advertising a policy it does not have, which is
    worse than advertising nothing. Removing the layer means removing the
    claim.

    Note this is not what a profile-unaware Croissant consumer does. That
    consumer ignores terms it does not know and never strips anything; an
    unrecognised `conformsTo` IRI is harmless to it. `strip` models the
    stronger question -- is the policy layer separable at all -- because that
    is the one clause 1 needs answered.
    """
    if isinstance(doc, dict):
        out = {k: strip(v) for k, v in doc.items() if not _is_cpol(k)}
        if "conformsTo" in out:
            # Accepts either notation, and preserves the one it was given: a
            # stripped document should differ from the original only by what
            # was removed.
            claimed = [
                c for c in _as_list(out["conformsTo"])
                if (c.get("@id") if isinstance(c, dict) else c) != PROFILE_IRI
            ]
            out["conformsTo"] = claimed if len(claimed) != 1 else claimed[0]
        return out
    if isinstance(doc, list):
        return [strip(v) for v in doc]
    return doc


def _check_additive(doc: dict, report: Report) -> None:
    ctx = doc.get("@context")
    if not isinstance(ctx, dict):
        report.error("clause 1: document has no @context object")
        return

    for key, value in ctx.items():
        if _is_cpol(key):
            continue
        if key not in CROISSANT_CONTEXT:
            report.error(
                f"clause 1: @context adds {key!r}, which is neither a Croissant 1.0 "
                "term nor in the cpol namespace"
            )
        elif value != CROISSANT_CONTEXT[key]:
            report.error(
                f"clause 1: @context redefines the Croissant term {key!r}; the policy "
                "layer must be additive"
            )
    if ctx.get("cpol") != CPOL_NS:
        report.error(f"clause 1: @context does not bind the cpol prefix to {CPOL_NS}")

    bare = strip(doc)
    if bare.get("@type") not in ("sc:Dataset", "Dataset"):
        report.error("clause 1: stripped document is not an sc:Dataset")
    for required in ("name", "description", "distribution"):
        if not bare.get(required):
            report.error(f"clause 1: stripped document has no {required!r}")
    if CROISSANT_IRI not in claimed_iris(bare.get("conformsTo")):
        report.error("clause 1: stripped document no longer conformsTo Croissant 1.0")
    if "cpol" in json.dumps(bare):
        report.error("clause 1: policy terms survive the strip; the layer is not separable")


def _check_conforms_to(doc: dict, report: Report) -> None:
    claimed = claimed_iris(doc.get("conformsTo"))
    if CROISSANT_IRI not in claimed:
        report.error(f"clause 2: conformsTo does not name {CROISSANT_IRI}")
    if PROFILE_IRI not in claimed:
        report.error(f"clause 2: conformsTo does not name {PROFILE_IRI}")


def _check_conditions(action: dict, where: str, report: Report) -> None:
    seen: set[str] = set()
    for node in _as_list(action.get("cpol:condition")):
        if not isinstance(node, dict):
            report.error(f"clause 5: {where} has a condition that is not a node")
            continue
        name = node.get("cpol:conditionName")
        if not isinstance(name, str) or not name:
            report.error(f"clause 5: {where} has a condition with no cpol:conditionName")
            continue
        if name in seen:
            report.error(f"clause 5: {where} declares condition {name!r} more than once")
        seen.add(name)
        operator = node.get("cpol:operator")
        if operator not in OPERATORS:
            report.error(
                f"clause 5: {where} condition {name!r} uses operator {operator!r}, outside "
                f"the closed set {sorted(OPERATORS)}. The evaluator refuses on this rather "
                "than skipping it, so the document is unusable, not unsafe."
            )
        if "cpol:expected" not in node:
            report.error(f"clause 5: {where} condition {name!r} has no cpol:expected")
            continue
        # The operand has to be a value the operator can actually use. Checked
        # here as well as at translation, because a validator that passes a
        # document the evaluator will refuse tells its user the opposite of the
        # truth -- and the operand cases are the ones where the two most easily
        # drift, since neither is visible to the SHACL shapes: cpol:expected is
        # an rdf:JSON literal and they cannot see inside it.
        defect = operand_defect(operator, node["cpol:expected"])
        if defect is not None:
            report.error(f"clause 5: {where} condition {name!r}: {defect}")


def _check_policy(doc: dict, report: Report) -> None:
    policies = _as_list(doc.get("cpol:policy"))
    if len(policies) != 1:
        report.error(f"clause 3: document carries {len(policies)} cpol:policy nodes, not 1")
        return
    policy = policies[0]
    if not isinstance(policy, dict):
        report.error("clause 3: cpol:policy is not a node")
        return
    if policy.get("@type") != "cpol:Policy":
        report.error("clause 3: cpol:policy node is not typed cpol:Policy")
    if not isinstance(policy.get("cpol:state"), str) or not policy.get("cpol:state"):
        report.error("clause 3: policy has no cpol:state")

    if policy.get("cpol:failClosed") is not True:
        report.error(
            "clause 4: cpol:failClosed is absent or not true. There is no conforming "
            "permissive mode; the evaluator refuses every declared action on such a "
            "document."
        )

    actions = _as_list(policy.get("cpol:permissibleAction"))
    if not actions:
        report.error(
            "clause 5: policy declares no permissible actions. A dataset that admits "
            "nothing says so with unreachable states, not with silence (SPEC 5.1)."
        )
    names: set[str] = set()
    for action in actions:
        if not isinstance(action, dict):
            report.error("clause 5: permissibleAction entry is not a node")
            continue
        name = action.get("cpol:actionName")
        if not isinstance(name, str) or not name:
            report.error("clause 5: action has no cpol:actionName")
            continue
        if name in names:
            report.error(f"clause 5: action {name!r} is declared more than once")
        names.add(name)
        _check_conditions(action, f"action {name!r}", report)


def validate(doc: dict) -> Report:
    """Check a document against SPEC section 3."""
    report = Report()
    if not isinstance(doc, dict):
        report.error("document is not a JSON object")
        return report
    _check_additive(doc, report)
    _check_conforms_to(doc, report)
    _check_policy(doc, report)
    report.warn(_MLCROISSANT_WARNING)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="croissant_policy.validate",
        description="Check documents against the profile's conformance clauses",
    )
    ap.add_argument("documents", nargs="+", type=Path)
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    args = ap.parse_args(argv)

    worst = 0
    out: dict = {}
    for path in args.documents:
        report = validate(json.loads(path.read_text()))
        out[str(path)] = report.as_json()
        if not args.json:
            status = "CONFORMS" if report.conforms else "NON-CONFORMING"
            print(f"{status}  {path}")
            for e in report.errors:
                print(f"  error:   {e}")
            for w in report.warnings:
                print(f"  warning: {w}")
        if not report.conforms:
            worst = 1
    if args.json:
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
