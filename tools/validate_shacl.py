#!/usr/bin/env python3
"""Check documents against the profile's SHACL shapes.

A companion to `tools/validate_mlcroissant.py`, and separate from the package
for the same reason: `pyshacl` pulls in rdflib and its dependency tree, and the
profile itself is standard library only.

    python3 -m venv .venv && .venv/bin/python -m pip install pyshacl
    .venv/bin/python tools/validate_shacl.py examples/*.croissant.json

What this checks is *not* what the gate checks. These shapes say whether a
policy document is written correctly. Whether a request is admitted is decided
by `croissant_policy.parse.authorize`, from a request context that appears in no
graph. A document can conform here and refuse everything, and that is not a
contradiction -- see the module docstring of `croissant_policy/shapes.py`.

The exit status is non-zero if any document fails, so this is usable as a gate
in its own right.

`--negative` runs the shapes against deliberately broken documents and requires
that each one *fails*. Shapes that accept everything pass silently and prove
nothing, which is the failure mode this flag exists to prevent.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

try:
    from pyshacl import validate as shacl_validate
    from rdflib import Graph
except ImportError:  # pragma: no cover - environment failure
    print(
        "pyshacl and rdflib are required.\n"
        "    python3 -m venv .venv && .venv/bin/python -m pip install pyshacl",
        file=sys.stderr,
    )
    raise SystemExit(2)

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from croissant_policy.shapes import served_path  # noqa: E402
from croissant_policy.vocab import PROFILE_IRI, claimed_iris  # noqa: E402


def _data_graph(doc: dict) -> Graph:
    g = Graph()
    g.parse(data=json.dumps(doc), format="json-ld")
    return g


def _check(doc: dict, shapes: Graph) -> tuple[bool, str]:
    conforms, _, text = shacl_validate(
        _data_graph(doc),
        shacl_graph=shapes,
        advanced=True,
        # No inference. The shapes target rdf:type as the document writes it,
        # and turning on RDFS would let a shape pass because of a type the
        # document never asserted.
        inference="none",
    )
    return conforms, text


# Each mutation names a conformance clause and breaks it. If a mutation does not
# produce a violation, the shape guarding that clause is not doing its job.
def _mutations(doc: dict) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []

    d = copy.deepcopy(doc)
    d["conformsTo"] = [
        c for c in d["conformsTo"]
        if "croissant-policy" not in (c.get("@id", "") if isinstance(c, dict) else c)
    ]
    out.append(("clause 2: profile IRI dropped from conformsTo", d))

    d = copy.deepcopy(doc)
    d["cpol:policy"] = [d["cpol:policy"], copy.deepcopy(d["cpol:policy"])]
    out.append(("clause 3: two policies", d))

    d = copy.deepcopy(doc)
    del d["cpol:policy"]["cpol:failClosed"]
    out.append(("clause 4: failClosed absent", d))

    d = copy.deepcopy(doc)
    d["cpol:policy"]["cpol:failClosed"] = False
    out.append(("clause 4: failClosed false", d))

    d = copy.deepcopy(doc)
    d["cpol:policy"]["cpol:permissibleAction"][0]["cpol:condition"][0]["cpol:operator"] = "cpol:regex"
    out.append(("clause 5: operator outside the closed set", d))

    d = copy.deepcopy(doc)
    del d["cpol:policy"]["cpol:permissibleAction"][0]["cpol:condition"][0]["cpol:expected"]
    out.append(("condition with nothing to compare against", d))

    d = copy.deepcopy(doc)
    del d["cpol:policy"]["cpol:state"]
    out.append(("policy with no lifecycle state", d))

    d = copy.deepcopy(doc)
    d["cpol:policy"]["cpol:permissibleAction"] = []
    out.append(("policy declaring no action: silence, not refusal", d))

    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="validate_shacl.py")
    ap.add_argument("documents", nargs="+", type=Path)
    ap.add_argument("--shapes", type=Path, default=None)
    ap.add_argument("--negative", action="store_true",
                    help="also require that broken documents fail")
    ap.add_argument("--corpus", type=Path, default=None,
                    help="a conformance corpus directory: every valid document "
                         "must conform and every defect the manifest says is "
                         "visible to SHACL must be reported")
    ap.add_argument("--out", type=Path, default=_REPO / "results" / "shacl.json")
    args = ap.parse_args(argv)

    shapes_path = args.shapes or served_path()
    shapes = Graph()
    shapes.parse(str(shapes_path), format="turtle")

    report: dict = {"shapes": str(shapes_path.relative_to(_REPO)), "documents": [],
                    "negative": []}
    failed = False

    for path in args.documents:
        doc = json.loads(path.read_text())
        # Shapes for a profile apply to documents that claim that profile. An
        # ODRL-carrier document claims a different one and expresses its policy
        # in odrl: terms; running these shapes over it would report the absence
        # of cpol: terms as a defect, which it is not.
        if PROFILE_IRI not in claimed_iris(doc.get("conformsTo")):
            print(f"{'SKIPPED':9s} {path}  (does not claim {PROFILE_IRI})")
            report["documents"].append({"path": str(path), "skipped": True})
            continue
        conforms, text = _check(doc, shapes)
        print(f"{'CONFORMS' if conforms else 'VIOLATES':9s} {path}")
        if not conforms:
            failed = True
            print("\n".join("    " + line for line in text.splitlines()[:20]))
        report["documents"].append(
            {"path": str(path), "conforms": conforms,
             "report": None if conforms else text}
        )

    if args.negative:
        # Only the cpol: carrier is mutated. The ODRL carrier expresses its
        # policy in odrl: terms, which these shapes deliberately do not target:
        # they are the shapes of *this* profile, and an ODRL document is
        # validated as an ODRL document.
        source = next(p for p in args.documents if not p.name.endswith(".odrl.croissant.json"))
        base = json.loads(source.read_text())
        print(f"\nnegative controls, mutating {source.name}:")
        for label, mutated in _mutations(base):
            conforms, _ = _check(mutated, shapes)
            caught = not conforms
            print(f"  {'caught ' if caught else 'MISSED ':8s} {label}")
            if not caught:
                failed = True
            report["negative"].append({"mutation": label, "caught": caught})

    if args.corpus:
        manifest = json.loads((args.corpus / "manifest.json").read_text())
        expected = {c["id"]: c for c in manifest["cases"]}
        conformed = violated = 0
        print(f"\nconformance corpus, {len(expected)} cases:")
        for case_id, case in sorted(expected.items()):
            doc = json.loads((args.corpus / f"{case_id}.croissant.json").read_text())
            conforms, _ = _check(doc, shapes)
            if case["kind"] == "valid":
                want, ok = "conform", conforms
                conformed += 1
            elif case.get("shaclDetects"):
                # A defect the manifest says the shapes can see. Defects that
                # only exist in JSON -- a duplicated key, a condition that is
                # not a node -- are refused by the evaluator and invisible here,
                # and the manifest says which is which rather than the tool
                # guessing.
                want, ok = "violate", not conforms
                violated += 1
            else:
                continue
            if not ok:
                failed = True
                print(f"  WRONG  {case_id}: expected to {want}")
        print(f"  {conformed} valid documents conform, "
              f"{violated} SHACL-visible defects reported")
        report["corpus"] = {"conformed": conformed, "violated": violated}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"\nwrote {args.out.relative_to(_REPO)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
