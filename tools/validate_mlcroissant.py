#!/usr/bin/env python3
"""Check emitted documents with MLCommons' reference validator.

SPEC section 9 recorded that the `@context` had never been through
`mlcroissant`, and the repository's own validator emitted that as a warning on
every document rather than checking something weaker and letting a reader
assume it was the real thing. This closes that.

It is a separate script, and not part of `croissant_policy`, because
`mlcroissant` pulls in pandas, numpy, scipy and rdflib. The profile itself is
standard library only and stays that way; a conformance dependency that heavy
belongs behind an explicit step.

    python3 -m venv .venv && .venv/bin/pip install mlcroissant
    .venv/bin/python tools/validate_mlcroissant.py examples/*.croissant.json

`--emit-context` prints the canonical Croissant 1.0 context from mlcroissant's
own generator, which is how `vocab.CROISSANT_CONTEXT` should be refreshed --
transcribing it from the spec prose is what produced four wrong terms and two
missing ones the first time.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import mlcroissant as mlc
    from mlcroissant._src.core.context import Context, CroissantVersion
    from mlcroissant._src.core.rdf import make_context
except ImportError:  # pragma: no cover - the whole point of the script
    raise SystemExit(
        "mlcroissant is not installed. It is deliberately not a dependency of this "
        "package:\n  python3 -m venv .venv && .venv/bin/pip install mlcroissant"
    )

from croissant_policy.vocab import CROISSANT_CONTEXT  # noqa: E402


class _Capture(logging.Handler):
    """mlcroissant reports context drift through absl logging, not exceptions."""

    def __init__(self):
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def check_context() -> dict:
    """Compare vocab.CROISSANT_CONTEXT against mlcroissant's generated one."""
    official = make_context(Context(conforms_to=CroissantVersion.V_1_0))
    mine, off = set(CROISSANT_CONTEXT), set(official)
    return {
        "matches": mine == off and all(CROISSANT_CONTEXT[k] == official[k] for k in mine),
        "extraTerms": sorted(mine - off),
        "missingTerms": sorted(off - mine),
        "differingValues": sorted(k for k in mine & off if CROISSANT_CONTEXT[k] != official[k]),
    }


def validate_one(path: Path) -> dict:
    capture = _Capture()
    logging.getLogger("absl").addHandler(capture)
    result: dict = {"path": str(path)}
    try:
        dataset = mlc.Dataset(str(path))
        result["loaded"] = True
        result["name"] = dataset.metadata.name
        result["errors"] = []
        result["warnings"] = [str(w) for w in (dataset.metadata.ctx.issues.warnings or [])]
    except Exception as exc:
        result["loaded"] = False
        result["errors"] = [str(exc)]
        result["warnings"] = []
    finally:
        logging.getLogger("absl").removeHandler(capture)
    result["absl"] = capture.messages
    result["contextReportedNonStandard"] = any("not standard" in m for m in capture.messages)
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("documents", nargs="*", type=Path)
    ap.add_argument("--out", type=Path, default=Path("results/mlcroissant.json"))
    ap.add_argument("--emit-context", action="store_true",
                    help="print the canonical Croissant 1.0 context and exit")
    args = ap.parse_args()

    if args.emit_context:
        print(json.dumps(make_context(Context(conforms_to=CroissantVersion.V_1_0)),
                         indent=2, sort_keys=True))
        return 0
    if not args.documents:
        ap.error("give at least one document, or --emit-context")

    context_report = check_context()
    results = [validate_one(p) for p in args.documents]
    report = {
        "mlcroissantVersion": getattr(mlc, "__version__", "unknown"),
        "croissantVersion": "1.0",
        "context": context_report,
        "documents": results,
        "allLoaded": all(r["loaded"] for r in results),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    print(f"@context matches mlcroissant's generated Croissant 1.0 context: "
          f"{context_report['matches']}")
    if not context_report["matches"]:
        print(f"  extra:   {context_report['extraTerms']}")
        print(f"  missing: {context_report['missingTerms']}")
        print(f"  differ:  {context_report['differingValues']}")
    for r in results:
        status = "LOADS" if r["loaded"] else "FAILS"
        print(f"{status}  {r['path']}")
        for e in r["errors"]:
            for line in str(e).splitlines():
                print(f"    error:   {line.strip()}")
        for w in r["warnings"]:
            print(f"    warning: {w}")
        if r["contextReportedNonStandard"]:
            print("    warning: mlcroissant reports the @context as non-standard")
    print(f"\nwrote {args.out}")
    return 0 if report["allLoaded"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
