"""A conformance corpus derived from the profile's own grammar.

The corpus in `ok-nfcore-admission-gate/descriptors/` is three documents that
gated a real pipeline run. It is the right evidence for one question -- does this
mechanism work in front of real execution, and what does it cost -- and it is
weak evidence for a different one: does the profile behave correctly across the
features its specification defines. Those are different questions and this module
answers the second, without diluting the first. Nothing generated here is claimed
to be real, and nothing here carries a performance number.

**What this covers is features, not documents.** The space of conforming
documents is not exhausted here and could not be: operands are arbitrary numbers
and strings, an `in` set has any cardinality, an action carries any number of
conditions, a policy declares any number of actions. What is finite and small is
the set of things the specification *names* -- five operators, three refusal
classes, five conformance clauses, two carriers, and a handful of structural
forms. That set is enumerable, so the documents exercising it can be derived
rather than remembered, which is what this module does. `requests.py` already
generates the request matrix from a descriptor; this generates the descriptors.

What the corpus is for, in order of how much it buys:

1. **Three-way agreement.** Every valid policy is expressed as a native
   descriptor, as `cpol:` terms, and as an ODRL policy in `sc:usageInfo`, and
   all three must produce identical complete decision records over the generated
   request matrix. C1 and C5 currently establish this on three descriptors; here
   it is established across every operator, every refusal class and every
   structural shape the specification allows.
2. **Fail-closed across the defect space.** Every way a document can be wrong
   that the specification names -- unknown operator, unknown profile, missing
   operand, duplicated condition name, undeclared `failClosed`, more than one
   policy -- must produce a refusal rather than a gap, in both carriers.
3. **Coverage, reported as coverage.** `coverage()` returns which operators,
   refusal classes, clauses, carriers and structural shapes the corpus
   exercises, positively and negatively. The number of documents is not the
   result and should not be reported as one.

The deliberate limit, stated here so it is not mistaken for modesty elsewhere:
these documents say nothing about what policies people actually write. Rates
computed over this corpus are properties of the generator.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# The lifecycle states the corpus uses. Real values from the deployment corpus,
# so that a reader comparing the two is not also comparing vocabularies.
STATES = ("RECEIVED", "QC_PASSED", "TRIMMED", "RETRACTED")

# One representative condition per operator, with the context values that
# satisfy and violate it. `requests.py` derives these itself for the request
# matrix; they are named here so that a case can also declare what it covers.
OPERATOR_CASES = {
    "min": {"spec": {"min": 20}, "numeric": True},
    "max": {"spec": {"max": 100}, "numeric": True},
    "in": {"spec": {"in": ["illumina", "nanopore"]}, "numeric": False},
    "equals": {"spec": {"equals": "GRCh38"}, "numeric": False},
    "present": {"spec": {"present": True}, "numeric": False},
}


@dataclass
class Case:
    """One conformance document, and what it is evidence for.

    `tags` is the whole point. A corpus that cannot say what it covers is a
    corpus whose size is the only thing anyone can report about it.
    """

    id: str
    native: dict
    tags: set[str] = field(default_factory=set)
    # Applied to the emitted cpol: document. A case with a mutator is a defect
    # case: the document is expected to be refused rather than to decide.
    mutate: object = None
    # What the defect is, in the specification's own words.
    defect: str | None = None
    # Whether the profile's SHACL shapes report it. One defect in the corpus is
    # invisible to them and it is invisible for a principled reason, not an
    # oversight: see `_defect_cases`. Claiming the shapes catch everything would
    # overstate them, and claiming they catch less than they do would understate
    # them, so each case declares which and tools/validate_shacl.py checks the
    # declaration rather than trusting it.
    shacl_detects: bool = False
    # Why this defect has no meaningful ODRL-carrier form, or None if it has
    # one. Two of them do not, and for different reasons -- see `_defect_cases`.
    # Recorded rather than inferred from the document shape, because the ODRL
    # test used to sniff the shape and silently skipped a case it should have
    # been reasoning about.
    no_odrl_form: str | None = None


def _descriptor(dataset_id: str, state: str, actions: list[dict], **extra) -> dict:
    native = {
        "datasetId": dataset_id,
        "version": "1.0.0",
        "dataType": "conformance_fixture",
        "state": state,
        "schema": {"format": "json"},
        "provenance": {"custodian": "conformance-corpus"},
        "policy": {
            "classification": "synthetic",
            "rationale": (
                "Generated from the profile grammar to exercise a specification "
                "case. Not a real dataset and not evidence about real policies."
            ),
        },
        "permissibleActions": actions,
    }
    native.update(extra)
    return native


def _action(name: str, states: list[str], conditions: dict) -> dict:
    return {"name": name, "requiresState": states, "conditions": conditions}


# --------------------------------------------------------------- valid cases


def _single_operator_cases() -> list[Case]:
    """One policy per operator. The floor of the coverage claim.

    Each is admissible in the dataset's own state, so the request matrix
    reaches PERMIT and CONDITION_VIOLATED on every operator rather than
    stopping at the state precondition.
    """
    out = []
    for operator, info in OPERATOR_CASES.items():
        out.append(Case(
            id=f"operator-{operator}",
            native=_descriptor(
                f"operator-{operator}", "QC_PASSED",
                [_action("run", ["QC_PASSED"], {"probe": info["spec"]})],
            ),
            tags={f"operator:{operator}", "shape:single-condition",
                  "verdict:permit", "refusal:condition"},
        ))
    return out


def _multi_condition_cases() -> list[Case]:
    """Policies whose actions carry more than one condition.

    Two things only appear here. The evaluator's per-condition ordering, which
    the decision record has to report in the order it checked; and the case
    where one condition passes and another fails, which is where a record that
    reports only the failing half stops being auditable.
    """
    operators = list(OPERATOR_CASES)
    out = []
    for size in (2, 3, 5):
        conditions = {
            f"probe{i}": OPERATOR_CASES[operators[i % len(operators)]]["spec"]
            for i in range(size)
        }
        out.append(Case(
            id=f"multi-condition-{size}",
            native=_descriptor(
                f"multi-condition-{size}", "QC_PASSED",
                [_action("run", ["QC_PASSED"], conditions)],
            ),
            tags={"shape:multi-condition", "verdict:permit", "refusal:condition"}
            | {f"operator:{operators[i % len(operators)]}" for i in range(size)},
        ))
    return out


def _multi_action_cases() -> list[Case]:
    """More than one admissible action, with different preconditions.

    The undeclared-action refusal is only meaningful against a descriptor that
    declares several: refusing an action on a policy that admits exactly one is
    not distinguishable from refusing everything.
    """
    out = []
    for count in (2, 3, 4):
        actions = [
            _action(
                f"act{i}",
                [STATES[i % len(STATES)]],
                {"probe": OPERATOR_CASES[list(OPERATOR_CASES)[i % 5]]["spec"]},
            )
            for i in range(count)
        ]
        out.append(Case(
            id=f"multi-action-{count}",
            native=_descriptor(f"multi-action-{count}", STATES[0], actions),
            tags={"shape:multi-action", "refusal:undeclared", "refusal:state"},
        ))
    return out


def _state_cases() -> list[Case]:
    """Lifecycle state as an admission precondition.

    The class of rule no caller-side authority can express, so the corpus
    covers it in both directions: the dataset in a state that admits the
    action, and in one that does not.
    """
    out = []
    for state in STATES:
        admits = [s for s in STATES if s != "RETRACTED"]
        out.append(Case(
            id=f"state-{state.lower()}",
            native=_descriptor(
                f"state-{state.lower()}", state,
                [_action("run", admits, {"probe": {"min": 1}})],
            ),
            tags={"shape:state-precondition", "operator:min",
                  "refusal:state" if state == "RETRACTED" else "verdict:permit"},
        ))
    # An action admissible in no state at all: declared, and unreachable.
    out.append(Case(
        id="state-unreachable",
        native=_descriptor(
            "state-unreachable", "QC_PASSED",
            [_action("run", ["NO_SUCH_STATE"], {"probe": {"min": 1}})],
        ),
        tags={"shape:state-precondition", "refusal:state"},
    ))
    return out


def _json_equality_cases() -> list[Case]:
    """Equality is JSON's, not the implementation language's.

    Three things the profile has to get right and one implementation got wrong:
    numbers compare by value so 1 and 1.0 are equal; a boolean is equal only to
    a boolean, so `equals: true` is not satisfied by 1; and membership uses the
    same relation, so `in: [1, 2]` does not admit `true`.
    """
    return [
        Case(
            id="equality-boolean",
            native=_descriptor(
                "equality-boolean", "QC_PASSED",
                [_action("run", ["QC_PASSED"], {"probe": {"equals": True}})],
            ),
            tags={"operator:equals", "shape:json-equality", "verdict:permit",
                  "refusal:condition"},
        ),
        Case(
            id="equality-number",
            native=_descriptor(
                "equality-number", "QC_PASSED",
                [_action("run", ["QC_PASSED"], {"probe": {"equals": 1}})],
            ),
            tags={"operator:equals", "shape:json-equality", "verdict:permit",
                  "refusal:condition"},
        ),
        Case(
            id="membership-number",
            native=_descriptor(
                "membership-number", "QC_PASSED",
                [_action("run", ["QC_PASSED"], {"probe": {"in": [1, 2]}})],
            ),
            tags={"operator:in", "shape:json-equality", "verdict:permit",
                  "refusal:condition"},
        ),
    ]


def _additivity_cases() -> list[Case]:
    """Documents whose descriptive half is worth something after the strip.

    Clause 1 is about what remains. A fixture with no provenance and no schema
    would satisfy it trivially, which is the same as not testing it.
    """
    native = _descriptor(
        "additivity-rich", "QC_PASSED",
        [_action("run", ["QC_PASSED"], {"probe": {"equals": "x"}})],
    )
    native["schema"] = {"format": "fastq.gz", "layout": "paired", "platform": "illumina"}
    native["provenance"] = {
        "source": "generated for the conformance corpus",
        "derivedFrom": "nothing",
        "producedBy": "croissant_policy.conformance",
        "custodian": "conformance-corpus",
        "retentionDays": 30,
        "unmappedFact": "goes to additionalProperty",
    }
    return [Case(
        id="additivity-rich",
        native=native,
        tags={"clause:1", "shape:strip", "operator:equals"},
    )]


# -------------------------------------------------------------- defect cases


def _drop_fail_closed(doc: dict) -> dict:
    del doc["cpol:policy"]["cpol:failClosed"]
    return doc


def _false_fail_closed(doc: dict) -> dict:
    doc["cpol:policy"]["cpol:failClosed"] = False
    return doc


def _unknown_operator(doc: dict) -> dict:
    doc["cpol:policy"]["cpol:permissibleAction"][0]["cpol:condition"][0][
        "cpol:operator"] = "cpol:regex"
    return doc


def _missing_operand(doc: dict) -> dict:
    del doc["cpol:policy"]["cpol:permissibleAction"][0]["cpol:condition"][0][
        "cpol:expected"]
    return doc


def _missing_condition_name(doc: dict) -> dict:
    del doc["cpol:policy"]["cpol:permissibleAction"][0]["cpol:condition"][0][
        "cpol:conditionName"]
    return doc


def _duplicate_condition_name(doc: dict) -> dict:
    conditions = doc["cpol:policy"]["cpol:permissibleAction"][0]["cpol:condition"]
    twin = json.loads(json.dumps(conditions[0]))
    twin["cpol:expected"] = "a different expectation under the same name"
    twin["cpol:operator"] = "cpol:equals"
    conditions.append(twin)
    return doc


def _two_policies(doc: dict) -> dict:
    doc["cpol:policy"] = [doc["cpol:policy"], json.loads(json.dumps(doc["cpol:policy"]))]
    return doc


def _condition_not_a_node(doc: dict) -> dict:
    doc["cpol:policy"]["cpol:permissibleAction"][0]["cpol:condition"] = ["a string"]
    return doc


def _in_scalar_operand(doc: dict) -> dict:
    """`cpol:in` with a string operand: the authoring slip that used to permit.

    Forgetting the array is the obvious mistake, and before the operand check
    existed this fell through to Python substring matching, so the policy
    admitted every substring of the operand. A rule that admits more than its
    author wrote is worse than one that crashes.
    """
    condition = doc["cpol:policy"]["cpol:permissibleAction"][0]["cpol:condition"][0]
    condition["cpol:operator"] = "cpol:in"
    condition["cpol:expected"] = "illumina"
    return doc


def _in_numeric_operand(doc: dict) -> dict:
    """`cpol:in` with a number: this used to raise TypeError, not refuse."""
    condition = doc["cpol:policy"]["cpol:permissibleAction"][0]["cpol:condition"][0]
    condition["cpol:operator"] = "cpol:in"
    condition["cpol:expected"] = 5
    return doc


def _present_non_boolean_operand(doc: dict) -> dict:
    """`cpol:present` with a string: used to be coerced with bool()."""
    condition = doc["cpol:policy"]["cpol:permissibleAction"][0]["cpol:condition"][0]
    condition["cpol:operator"] = "cpol:present"
    condition["cpol:expected"] = "yes"
    return doc


def _min_non_numeric_operand(doc: dict) -> dict:
    """`cpol:min` against a threshold that is not a number."""
    doc["cpol:policy"]["cpol:permissibleAction"][0]["cpol:condition"][0][
        "cpol:expected"] = "twenty"
    return doc


def _equals_boolean_vs_number(doc: dict) -> dict:
    """`equals: true` must not be satisfied by an observed 1.

    Not a malformed document -- this one is perfectly conforming -- so it is a
    *valid* case whose request matrix has to reach the right verdict. It lives
    among the defect helpers only because it was found alongside them: Python's
    bool is a subclass of int, so `True == 1`, and a gate using Python equality
    admitted a request whose policy said something else.
    """
    condition = doc["cpol:policy"]["cpol:permissibleAction"][0]["cpol:condition"][0]
    condition["cpol:operator"] = "cpol:equals"
    condition["cpol:expected"] = True
    return doc


def _drop_profile_claim(doc: dict) -> dict:
    doc["conformsTo"] = [c for c in doc["conformsTo"] if "croissant-policy" not in c]
    return doc


def _defect_cases() -> list[Case]:
    """Every way the specification says a document can be wrong.

    All of them are evaluated, not merely validated. A defect that a validator
    reports and an evaluator ignores is the failure mode this profile exists to
    prevent, so each case below asserts a refusal at decision time and, where
    the defect survives into the graph, a SHACL violation as well.
    """
    base = _descriptor(
        "defect-base", "QC_PASSED",
        [_action("run", ["QC_PASSED"], {"probe": {"min": 10}})],
    )
    specs = [
        ("defect-no-failclosed", _drop_fail_closed,
         "policy does not declare cpol:failClosed (clause 4)", True, "clause:4"),
        ("defect-failclosed-false", _false_fail_closed,
         "policy declares cpol:failClosed = false (clause 4)", True, "clause:4"),
        ("defect-unknown-operator", _unknown_operator,
         "operator outside the closed set (clause 5)", True, "clause:5"),
        ("defect-missing-operand", _missing_operand,
         "condition carries no cpol:expected", True, "clause:5"),
        ("defect-missing-condition-name", _missing_condition_name,
         "condition carries no cpol:conditionName", True, "clause:5"),
        # The one defect the shapes cannot see, and the reason is the same one
        # that keeps SHACL out of the evaluation path. Both conditions survive
        # into the graph as separate nodes, each individually satisfying
        # ConditionShape; what is wrong is a relationship *between* siblings --
        # no two conditions of one action may share a name. Expressing that
        # needs a SHACL-SPARQL constraint, and SHACL-SPARQL is as expressive as
        # the query language, which is precisely the unbounded fragment this
        # profile declines. So it is left to the evaluator, which collapses the
        # two into one poisoned condition and refuses.
        ("defect-duplicate-condition", _duplicate_condition_name,
         "two conditions declared under one name", False, "clause:5"),
        ("defect-two-policies", _two_policies,
         "more than one cpol:policy (clause 3)", True, "clause:3"),
        # Visible after all: `sh:class cpol:Condition` rejects a literal where
        # a node is required. This was declared invisible until the corpus was
        # checked against the shapes rather than against an assumption.
        ("defect-condition-not-a-node", _condition_not_a_node,
         "a condition that is not a node", True, "clause:5"),
        ("defect-no-profile-claim", _drop_profile_claim,
         "conformsTo does not name the profile (clause 2)", True, "clause:2"),
        # Malformed *operands*, as distinct from malformed observations. An
        # observation of the wrong type is an ordinary condition violation; an
        # operand of the wrong type is a defect in the policy, and these four
        # are the ways the closed set can be given one. None is visible to
        # SHACL: cpol:expected is an rdf:JSON literal, so the shapes cannot see
        # inside it, which is the same boundary as the duplicated name above.
        ("defect-in-scalar-operand", _in_scalar_operand,
         "cpol:in with a string operand, which used to match substrings",
         False, "clause:5"),
        ("defect-in-numeric-operand", _in_numeric_operand,
         "cpol:in with a numeric operand, which used to raise", False, "clause:5"),
        ("defect-present-non-boolean", _present_non_boolean_operand,
         "cpol:present with a non-boolean operand", False, "clause:5"),
        ("defect-min-non-numeric-operand", _min_non_numeric_operand,
         "cpol:min with a non-numeric operand", False, "clause:5"),
    ]
    # Two defects cannot be expressed through the ODRL carrier, and neither is
    # a gap in the carrier.
    #
    # `defect-two-policies` has no form because `to_odrl` is defined for exactly
    # one policy node; a document with two is refused before a carrier is
    # chosen.
    #
    # `defect-no-profile-claim` has no form because translation *writes* the
    # conformance claim: converting a document that omits its cpol: claim
    # produces one that carries a correct ODRL claim, so the defect does not
    # survive the conversion. That is a property of generating a document rather
    # than a laundering of the defect -- the ODRL carrier enforces its own
    # profile identifier, which `OdrlProfileFailsClosed` tests directly.
    no_odrl = {
        "defect-two-policies":
            "to_odrl is defined for exactly one policy node",
        "defect-no-profile-claim":
            "translation writes the conformance claim, so the omission cannot survive it",
    }
    return [
        Case(
            id=case_id,
            native=json.loads(json.dumps(base)) | {"datasetId": case_id},
            mutate=mutator,
            defect=defect,
            shacl_detects=shacl,
            no_odrl_form=no_odrl.get(case_id),
            tags={"shape:defect", clause, "operator:min",
                  "shape:malformed-operand"} if "operand" in case_id
            else {"shape:defect", clause, "operator:min"},
        )
        for case_id, mutator, defect, shacl, clause in specs
    ]


def _wrong_datatype_cases() -> list[Case]:
    """A numeric condition compared against something that is not a number.

    Not a defect in the document -- the policy is well formed -- but a case the
    evaluator has to refuse rather than coerce. `requests.py` generates the
    non-numeric context for these automatically, so the case is carried by the
    valid corpus; it is named here so coverage can claim it.
    """
    out = []
    for operator in ("min", "max"):
        out.append(Case(
            id=f"datatype-{operator}",
            native=_descriptor(
                f"datatype-{operator}", "QC_PASSED",
                [_action("run", ["QC_PASSED"], {"probe": OPERATOR_CASES[operator]["spec"]})],
            ),
            tags={f"operator:{operator}", "shape:wrong-datatype", "refusal:condition"},
        ))
    return out


# ------------------------------------------------------------------- corpus


def valid_cases() -> list[Case]:
    """Documents the specification permits. Every one must decide, not refuse."""
    return (
        _single_operator_cases()
        + _multi_condition_cases()
        + _multi_action_cases()
        + _state_cases()
        + _wrong_datatype_cases()
        + _json_equality_cases()
        + _additivity_cases()
    )


def defect_cases() -> list[Case]:
    """Documents the specification forbids. Every one must refuse, not decide."""
    return _defect_cases()


def cases() -> list[Case]:
    return valid_cases() + defect_cases()


def coverage() -> dict[str, list[str]]:
    """What the corpus exercises, grouped by dimension.

    Reported instead of a document count. A corpus of forty documents that
    covers three operators is worse than a corpus of eight that covers five,
    and only one of those two facts is visible from the size.
    """
    grouped: dict[str, set[str]] = {}
    for case in cases():
        for tag in case.tags:
            dimension, _, value = tag.partition(":")
            grouped.setdefault(dimension, set()).add(value)
    # Both carriers, for every valid case: the corpus is emitted twice.
    grouped.setdefault("carrier", set()).update({"cpol", "odrl"})
    return {k: sorted(v) for k, v in sorted(grouped.items())}


def write(outdir: Path | None, emit_documents: bool = True) -> dict:
    """Materialise the corpus, and return the manifest describing it.

    `outdir` may be None when only the manifest is wanted: the coverage claim is
    a property of the generator and does not require the documents on disk.
    """
    from . import emit as emit_mod
    from . import odrl as odrl_mod

    manifest: dict = {
        "purpose": (
            "Specification coverage for the Croissant policy profile. Generated "
            "from the closed grammar, not observed. Makes no claim about which "
            "policies are written in practice, and carries no timing figures: "
            "those come from the deployment corpus of real nf-core descriptors."
        ),
        "coverage": coverage(),
        "cases": [],
    }
    if emit_documents:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)

    for case in cases():
        entry = {
            "id": case.id,
            "tags": sorted(case.tags),
            "kind": "defect" if case.mutate else "valid",
        }
        if case.defect:
            entry["defect"] = case.defect
            entry["shaclDetects"] = case.shacl_detects
        if emit_documents:
            doc = emit_mod.emit(case.native)
            if case.mutate:
                doc = case.mutate(doc)
                (outdir / f"{case.id}.croissant.json").write_text(
                    json.dumps(doc, indent=2) + "\n")
            else:
                (outdir / f"{case.id}.croissant.json").write_text(
                    json.dumps(doc, indent=2) + "\n")
                (outdir / f"{case.id}.odrl.croissant.json").write_text(
                    json.dumps(odrl_mod.to_odrl(doc), indent=2) + "\n")
        manifest["cases"].append(entry)

    manifest["counts"] = {
        "valid": sum(1 for c in cases() if not c.mutate),
        "defect": sum(1 for c in cases() if c.mutate),
        "documents": sum(2 if not c.mutate else 1 for c in cases()),
    }
    return manifest


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="croissant_policy.conformance",
        description="Generate the specification-coverage corpus",
    )
    ap.add_argument("--outdir", type=Path,
                    default=Path(__file__).resolve().parent.parent / "conformance")
    ap.add_argument("--manifest-only", action="store_true")
    args = ap.parse_args(argv)

    manifest = write(args.outdir, emit_documents=not args.manifest_only)
    print(json.dumps(manifest["coverage"], indent=2))
    print(f"\n{manifest['counts']['valid']} valid, "
          f"{manifest['counts']['defect']} defect, "
          f"{manifest['counts']['documents']} documents")
    if not args.manifest_only:
        (args.outdir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print(f"wrote {args.outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
