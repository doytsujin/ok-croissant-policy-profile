"""A conformance corpus derived from the profile's own grammar.

The corpus in `ok-nfcore-admission-gate/descriptors/` is three documents that
gated a real pipeline run. It is the right evidence for one question -- does this
mechanism work in front of real execution, and what does it cost -- and it is
weak evidence for a different one: does the profile behave correctly across the
space of documents its specification permits. Those are different questions and
this module answers the second, without diluting the first. Nothing generated
here is claimed to be real, and nothing here carries a performance number.

The generator rather than a directory of hand-written JSON, because the
specification already says the thing that makes generation possible. The
operator set is closed at five. The refusal classes are three. `failClosed` is
boolean and mandatory. A closed grammar has an enumerable space of documents, and
the profile's whole argument is that the work a document implies is enumerable
from the document -- so enumerating the documents themselves is the same idea
applied one level up. `requests.py` already generates the request matrix from a
descriptor; this generates the descriptors.

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
    # Whether the profile's SHACL shapes should report it. Not every defect is
    # visible to SHACL -- a duplicated condition name collapses in JSON before
    # the graph is built -- and claiming otherwise would overstate the shapes.
    shacl_detects: bool = False


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
        ("defect-duplicate-condition", _duplicate_condition_name,
         "two conditions declared under one name", False, "clause:5"),
        ("defect-two-policies", _two_policies,
         "more than one cpol:policy (clause 3)", True, "clause:3"),
        ("defect-condition-not-a-node", _condition_not_a_node,
         "a condition that is not a node", False, "clause:5"),
        ("defect-no-profile-claim", _drop_profile_claim,
         "conformsTo does not name the profile (clause 2)", True, "clause:2"),
    ]
    return [
        Case(
            id=case_id,
            native=json.loads(json.dumps(base)) | {"datasetId": case_id},
            mutate=mutator,
            defect=defect,
            shacl_detects=shacl,
            tags={"shape:defect", clause, "operator:min"},
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
