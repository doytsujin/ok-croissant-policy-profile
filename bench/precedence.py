#!/usr/bin/env python3
"""Experiment 2: what happens when the caller's policy and the data's disagree.

An agent control plane binds policy to the caller. This profile binds policy to
the data. Both decide the same request, inline, before it runs. Nothing in the
vendor material or the descriptor literature says which one wins when they
disagree, or whether the disagreement is recorded at all.

This runs both over the full cross product of caller scopes, datasets, actions
and generated contexts, and counts four things:

  1. Whether the two authorities disagree in *both* directions. If one's permit
     set were a subset of the other's, precedence would be a non-question and
     one of the two products would be redundant.
  2. For each precedence rule, how many requests it admits that one of the
     authorities refused. That number is the governance gap, with a count.
  3. What the disagreements are made of -- specifically how many of the
     data-side refusals a caller-side plane could not have reached at all,
     because they turn on the dataset's state.
  4. What running both costs against running one.

Read the caller side as designed, not measured: the scopes in examples/callers
are a model of the structure agent control planes describe, written so the
interaction can be studied. The data side is the opposite -- those descriptors
gated a real nf-core run.
"""

from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from croissant_policy import conjunction, emit  # noqa: E402
from croissant_policy.caller import load_all  # noqa: E402
from croissant_policy.reference import gate_root, load_gate  # noqa: E402
from croissant_policy.requests import request_matrix  # noqa: E402

_, _, gate_mod = load_gate()
WARMUP = 100


def _time(fn, iterations: int) -> float:
    for _ in range(WARMUP):
        fn()
    samples = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        fn()
        samples.append(time.perf_counter_ns() - start)
    return round(statistics.median(samples) / 1000, 3)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--callers", type=Path, default=Path("examples/callers"))
    ap.add_argument("--iterations", type=int, default=2000)
    ap.add_argument("--out", type=Path, default=Path("results/precedence.json"))
    ap.add_argument("--receipt", type=Path, default=Path("examples/joint-receipt.json"))
    args = ap.parse_args()

    scopes = load_all(args.callers)
    if not scopes:
        raise SystemExit(f"no caller scopes under {args.callers}")

    datasets = {}
    for path in sorted((gate_root() / "descriptors").glob("*.json")):
        native = json.loads(path.read_text())
        datasets[native["datasetId"]] = (native, emit.emit(native))

    agreement = collections.Counter()
    by_rule = {r: collections.Counter() for r in conjunction.PRECEDENCE_RULES}
    data_only_classes = collections.Counter()
    caller_only_classes = collections.Counter()
    per_caller = collections.defaultdict(collections.Counter)
    examples = {}
    total = 0

    for caller_id, scope in scopes.items():
        for dataset_id, (native, doc) in datasets.items():
            for action, context in request_matrix(native):
                joint = conjunction.decide(scope, doc, action, context)
                total += 1
                agreement[joint.agreement] += 1
                per_caller[caller_id][joint.agreement] += 1

                if joint.agreement == conjunction.DATA_ONLY_REFUSED:
                    data_only_classes[joint.data.reason_class] += 1
                    examples.setdefault("dataOnlyRefused", joint.as_record())
                elif joint.agreement == conjunction.CALLER_ONLY_REFUSED:
                    caller_only_classes[joint.caller.reason_class] += 1
                    examples.setdefault("callerOnlyRefused", joint.as_record())

                for rule in conjunction.PRECEDENCE_RULES:
                    by_rule[rule][joint.effective(rule)] += 1
                    if joint.unsafe_under(rule):
                        by_rule[rule]["UNSAFE_ADMISSION"] += 1

    # Cost. The conjunction is two evaluations plus the bookkeeping; the point
    # is whether "run both" is a cost argument against doing it.
    native, doc = datasets["raw-reads"]
    scope = scopes["pipeline-agent"]
    ctx = {"minReadLength": 30, "platform": "illumina"}
    descriptor = conjunction.to_descriptor(doc)
    scope_descriptor = scope.to_descriptor()
    cost = {
        "dataOnlyMicros": _time(
            lambda: gate_mod.authorize(descriptor, "trim", ctx), args.iterations),
        "callerOnlyMicros": _time(
            lambda: gate_mod.authorize(scope_descriptor, "trim", ctx), args.iterations),
        # Warm: both descriptors already translated, which is the regime the
        # single-sided figures above are measured in. Charging the conjunction
        # for document parsing the baselines never paid would not be a
        # comparison, it would be a second measurement of the parser.
        "conjunctionWarmMicros": _time(
            lambda: conjunction.decide(
                scope, doc, "trim", ctx,
                data_descriptor=descriptor, caller_descriptor=scope_descriptor),
            args.iterations),
        # Cold: the profile document and the caller scope are both re-translated
        # per decision, which is what a per-task hook does.
        "conjunctionColdMicros": _time(
            lambda: conjunction.decide(scope, doc, "trim", ctx), args.iterations),
    }

    disagreements = agreement[conjunction.DATA_ONLY_REFUSED] + agreement[conjunction.CALLER_ONLY_REFUSED]
    report = {
        "callers": sorted(scopes),
        "datasets": sorted(datasets),
        "requests": total,
        "agreement": dict(agreement),
        "disagreementRatePct": round(100.0 * disagreements / total, 2) if total else 0,
        "bothDirections": (
            agreement[conjunction.DATA_ONLY_REFUSED] > 0
            and agreement[conjunction.CALLER_ONLY_REFUSED] > 0
        ),
        "dataOnlyRefusedByClass": dict(data_only_classes),
        "callerOnlyRefusedByClass": dict(caller_only_classes),
        "byPrecedence": {r: dict(c) for r, c in by_rule.items()},
        "perCaller": {k: dict(v) for k, v in per_caller.items()},
        "cost": cost,
        "callerSideIs": "designed, not measured -- see croissant_policy/caller.py",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if examples:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(examples, indent=2) + "\n")

    print(f"{total} requests: {len(scopes)} callers x {len(datasets)} datasets x generated contexts\n")
    print("agreement between the two authorities")
    for k in (conjunction.AGREE_PERMIT, conjunction.AGREE_REFUSE,
              conjunction.CALLER_ONLY_REFUSED, conjunction.DATA_ONLY_REFUSED):
        print(f"  {k:22} {agreement[k]:5}  {100.0*agreement[k]/total:5.1f}%")
    print(f"  disagreement rate      {report['disagreementRatePct']:5.1f}%   "
          f"both directions: {report['bothDirections']}")

    print("\nunsafe admissions -- requests a rule admits that an authority refused")
    for rule in conjunction.PRECEDENCE_RULES:
        c = by_rule[rule]
        unsafe = c["UNSAFE_ADMISSION"]
        print(f"  {rule:18} permits {c[gate_mod.PERMIT]:5}   unsafe {unsafe:5}  "
              f"({100.0*unsafe/total:.1f}% of all requests)")

    print("\nwhat the caller-side plane cannot reach (data-only refusals by class)")
    for cls, n in data_only_classes.most_common():
        print(f"  {cls:22} {n:5}")
    print("\nwhat the data-side gate cannot reach (caller-only refusals by class)")
    for cls, n in caller_only_classes.most_common():
        print(f"  {cls:22} {n:5}")

    print(f"\ncost per decision, warm: data-only {cost['dataOnlyMicros']} us, "
          f"caller-only {cost['callerOnlyMicros']} us, "
          f"conjunction {cost['conjunctionWarmMicros']} us")
    print(f"cost per decision, cold conjunction (both sides re-translated): "
          f"{cost['conjunctionColdMicros']} us")
    print("\nNote: the rates above are properties of the generated request matrix, "
          "which is\ndeliberately weighted toward violations. They are not base rates "
          "of real traffic.")
    print(f"\nwrote {args.out} and {args.receipt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
