"""Emit a conforming Croissant + policy document from a native descriptor.

The input is the descriptor format used by `dk-nfcore-admission-gate`: a small
dependency-free JSON model with `permissibleActions`, each carrying
`requiresState` and a dict of conditions. The output is a Croissant 1.0
document with the `cpol:` layer attached.

Two rules govern everything here.

**Nothing is invented.** Every value in the output traces to a value in the
input or to an explicit override passed by the caller. The native descriptor
does not record where the files are, so the emitted `distribution` describes
their shape and not their location, and says so. Filling that in with a
plausible path would make the document look more complete and be less true.

**The condition translation preserves the native evaluator's behaviour,
including its failures.** A condition the native evaluator would refuse on --
an unrecognised operator key -- is emitted as an unrecognised `cpol:` operator,
which the parser maps back to the same refusal. Equivalence has to hold for the
bad documents too, or it is not equivalence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .vocab import CROISSANT_IRI, PROFILE_IRI, RAI_DATA_COLLECTION, context

# Native condition keys in the precedence order gate/policy.py checks them.
_NATIVE_OPERATOR_ORDER = ("min", "max", "in", "equals", "present")

# Enough of a format-to-MIME map for the corpus, with an honest fallback.
_MIME = {
    "fastq.gz": "application/gzip",
    "fastq": "text/plain",
    "html": "text/html",
    "json": "application/json",
    "jsonl": "application/jsonl",
    "csv": "text/csv",
    "tsv": "text/tab-separated-values",
    "txt": "text/plain",
    "zip": "application/zip",
}


# Where each native provenance key goes in standard vocabulary. Two keys are
# handled outside this table: `custodian` becomes `creator`, and
# `retentionDays` is the one provenance fact the policy layer actually needs,
# so it lives on the policy node. Anything not named here goes to
# `additionalProperty`, which is schema.org's own escape hatch -- dropping a
# provenance fact because the profile has no term for it would be the same
# silent loss the profile exists to prevent.
_PROVENANCE_TERMS = {
    "source": RAI_DATA_COLLECTION,     # rai:dataCollection -- how it was collected
    "derivedFrom": "isBasedOn",        # schema.org -- what it was derived from
    "producedBy": "measurementTechnique",  # schema.org -- what produced it
}
_PROVENANCE_HANDLED = set(_PROVENANCE_TERMS) | {"custodian", "retentionDays"}
_ADDITIONAL_PREFIX = "provenance."


class EmitError(ValueError):
    """The native descriptor cannot be expressed in the profile."""


def _mime(fmt: str | None) -> str:
    if not fmt:
        return "application/octet-stream"
    return _MIME.get(fmt.lower(), "application/octet-stream")


def _glob(fmt: str | None) -> str:
    return f"*.{fmt}" if fmt else "*"


def _condition(name: str, spec) -> dict:
    """One native condition -> one `cpol:Condition` node."""
    if not isinstance(spec, dict):
        # gate/policy.py treats a bare scalar as equality.
        return {
            "@type": "cpol:Condition",
            "cpol:conditionName": name,
            "cpol:operator": "cpol:equals",
            "cpol:expected": spec,
        }

    present = [k for k in _NATIVE_OPERATOR_ORDER if k in spec]
    if len(present) > 1:
        raise EmitError(
            f"condition {name!r} declares {present}; the native evaluator would "
            f"silently apply only {present[0]!r} and ignore the rest. The profile "
            "will not emit a rule that is written down and not enforced."
        )
    if present:
        op = present[0]
        return {
            "@type": "cpol:Condition",
            "cpol:conditionName": name,
            "cpol:operator": f"cpol:{op}",
            "cpol:expected": spec[op],
        }

    # No recognised operator. The native evaluator refuses on this (its
    # `_check` falls through to "unsupported"), so the emitted document must
    # refuse on it too. Carrying the unknown key through as an unknown operator
    # is what makes that happen, via the parser's mapping.
    unknown = sorted(spec)[0] if spec else "empty"
    return {
        "@type": "cpol:Condition",
        "cpol:conditionName": name,
        "cpol:operator": f"cpol:{unknown}",
        "cpol:expected": spec.get(unknown),
    }


def _action(native_action: dict) -> dict:
    name = native_action.get("name")
    if not name:
        raise EmitError("permissibleActions entry has no name")
    node: dict = {
        "@type": "cpol:Action",
        "cpol:actionName": name,
    }
    requires = list(native_action.get("requiresState", []) or [])
    if requires:
        node["cpol:requiresState"] = requires
    conditions = native_action.get("conditions", {}) or {}
    if conditions:
        # Sorted because gate/policy.py evaluates sorted by key, and a decision
        # record that lists conditions in a different order than the evaluator
        # checked them is a small lie that costs an afternoon to chase.
        node["cpol:condition"] = [_condition(k, conditions[k]) for k in sorted(conditions)]
    return node


def _policy(native: dict, decision_record: str | None) -> dict:
    actions = native.get("permissibleActions", []) or []
    if not actions:
        raise EmitError(
            f"descriptor {native.get('datasetId')!r} declares no permissible actions; "
            "SPEC 5.1 rejects an empty list because silence is not auditable"
        )

    native_policy = native.get("policy", {}) or {}
    provenance = native.get("provenance", {}) or {}

    policy: dict = {
        "@type": "cpol:Policy",
        "cpol:state": native["state"],
        "cpol:failClosed": True,
    }
    if native_policy.get("classification"):
        policy["cpol:classification"] = native_policy["classification"]
    if provenance.get("custodian"):
        policy["cpol:custodian"] = provenance["custodian"]
    if provenance.get("retentionDays") is not None:
        policy["cpol:retentionDays"] = provenance["retentionDays"]
    if native_policy.get("rationale"):
        policy["cpol:rationale"] = native_policy["rationale"]
    policy["cpol:permissibleAction"] = [_action(a) for a in actions]
    if decision_record:
        policy["cpol:decisionRecord"] = {"@id": decision_record}
    return policy


def _distribution(native: dict) -> list[dict]:
    schema = native.get("schema", {}) or {}
    fmt = schema.get("format")
    file_set = {
        "@type": "cr:FileSet",
        "@id": f"{native['datasetId']}-files",
        "name": f"{native['datasetId']}-files",
        "description": (
            f"The {native.get('dataType', 'data')} files of this dataset"
            + (f", in {fmt} form" if fmt else "")
            + ". The native descriptor records the shape of the data and not its "
            "location, so this FileSet has no containedIn; the location is supplied "
            "by whoever mounts the dataset."
        ),
        "encodingFormat": _mime(fmt),
        "includes": _glob(fmt),
    }
    return [file_set]


def _variables(native: dict) -> list[dict]:
    """Dataset-level schema facts as schema.org PropertyValue.

    `layout`, `platform` and `assay` are properties of the dataset, not columns
    of a record, so they are not a Croissant RecordSet. `variableMeasured` is
    the standard place for them and survives the strip in conformance clause 1.
    """
    schema = native.get("schema", {}) or {}
    return [
        {"@type": "sc:PropertyValue", "name": key, "value": schema[key]}
        for key in sorted(schema)
        if key != "format"
    ]


def emit(
    native: dict,
    *,
    url: str | None = None,
    license: str | None = None,
    cite_as: str | None = None,
    date_published: str | None = None,
    decision_record: str | None = None,
) -> dict:
    """Native descriptor dict -> conforming Croissant + `cpol:` document."""
    for required in ("datasetId", "version", "state"):
        if required not in native:
            raise EmitError(f"native descriptor missing {required!r}")

    provenance = native.get("provenance", {}) or {}
    description = (
        f"{native.get('dataType', 'Dataset')} described as a policy-bearing Croissant "
        f"dataset. State: {native['state']}."
    )
    if provenance.get("source"):
        description += f" Source: {provenance['source']}."

    doc: dict = {
        "@context": context(),
        "@type": "sc:Dataset",
        "name": native["datasetId"],
        "description": description,
        "conformsTo": [CROISSANT_IRI, PROFILE_IRI],
        "version": native["version"],
    }
    if url:
        doc["url"] = url
    if license:
        doc["license"] = license
    if cite_as:
        doc["citeAs"] = cite_as
    if date_published:
        doc["datePublished"] = date_published
    if provenance.get("custodian"):
        doc["creator"] = {"@type": "sc:Organization", "name": provenance["custodian"]}
    # The descriptive half of the native descriptor goes into standard
    # schema.org places rather than into `cpol:` terms, so that stripping the
    # policy layer loses the policy and nothing else. `additionalType` carries
    # the native `dataType`; `isBasedOn` carries provenance of collection.
    if native.get("dataType"):
        doc["additionalType"] = native["dataType"]
    for key, term in _PROVENANCE_TERMS.items():
        if provenance.get(key) is not None:
            doc[term] = provenance[key]
    unmapped = [k for k in sorted(provenance) if k not in _PROVENANCE_HANDLED]
    if unmapped:
        doc["additionalProperty"] = [
            {
                "@type": "sc:PropertyValue",
                "name": _ADDITIONAL_PREFIX + k,
                "value": provenance[k],
            }
            for k in unmapped
        ]

    variables = _variables(native)
    if variables:
        doc["variableMeasured"] = variables

    distribution = _distribution(native)
    record_id = None
    if decision_record:
        node = _decision_record_node(decision_record)
        record_id = node["@id"]
        distribution.append(node)
    doc["distribution"] = distribution

    doc["cpol:policy"] = _policy(native, record_id)
    return doc


def _decision_record_node(decision_record: str | Path) -> dict:
    """The distribution node `cpol:decisionRecord` points at.

    Croissant requires a `cr:FileObject` to carry `md5` or `sha256`, which is
    the right requirement and one the profile cannot satisfy by inventing a
    value. So the path must exist locally and the checksum is computed from it.
    A directory of decision logs becomes a `cr:FileSet`, which needs no
    checksum because it is a pattern rather than a byte sequence.
    """
    path = Path(decision_record)
    if path.is_dir():
        return {
            "@type": "cr:FileSet",
            "@id": path.name,
            "name": path.name,
            "description": "Decision records emitted by the gate for this dataset.",
            "encodingFormat": "application/jsonl",
            "includes": f"{path.as_posix()}/*.jsonl",
        }
    if path.is_file():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return {
            "@type": "cr:FileObject",
            "@id": path.name,
            "name": path.name,
            "description": "Decision records emitted by the gate for this dataset.",
            "encodingFormat": "application/jsonl",
            "contentUrl": path.as_posix(),
            "sha256": digest,
        }
    raise EmitError(
        f"--decision-record {decision_record!r} does not exist. Croissant requires a "
        "FileObject to carry a checksum, and the profile will not emit one it cannot "
        "compute. Point it at the decision log or the directory of logs."
    )


def emit_file(path: Path, **kw) -> dict:
    return emit(json.loads(Path(path).read_text()), **kw)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="croissant_policy.emit",
        description="Emit Croissant + cpol documents from native descriptors",
    )
    ap.add_argument("descriptors", nargs="+", type=Path)
    ap.add_argument("--outdir", type=Path, default=None,
                    help="write <name>.croissant.json here; default is stdout")
    ap.add_argument("--url")
    ap.add_argument("--license")
    ap.add_argument("--cite-as")
    ap.add_argument("--date-published")
    ap.add_argument("--decision-record",
                    help="@id of a FileObject holding this dataset's decision records")
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
            doc = emit_file(path, **overrides)
        except EmitError as exc:
            print(f"emit: {path}: {exc}", file=sys.stderr)
            return 1
        text = json.dumps(doc, indent=2, sort_keys=False) + "\n"
        if args.outdir:
            args.outdir.mkdir(parents=True, exist_ok=True)
            out = args.outdir / f"{doc['name']}.croissant.json"
            out.write_text(text)
            print(f"emit: {path} -> {out}", file=sys.stderr)
        else:
            sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
