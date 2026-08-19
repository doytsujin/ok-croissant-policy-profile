#!/usr/bin/env python3
"""C3: what the profile path costs, per admission decision.

The gate's published figure is a 119 microsecond median for the whole gate
process and 11 microseconds for policy evaluation itself, measured over 210
decisions in a 30-replicate nf-core run. Expressing the same policy as Croissant cannot change the
evaluation -- it is the same function on the same data -- so the only thing
this measures is the translation, and the only honest question is how big it
is relative to the number it is being added to.

Two regimes are reported because they are genuinely different deployments:

  warm   the document is translated once and the descriptor is reused across
         decisions. This is what a long-lived gate does.
  cold   the document is read and translated for every decision. This is what
         a per-task hook does, and it is the regime the 119 us figure came
         from -- that process re-read its descriptor each time.

Everything is measured in-process with `perf_counter_ns`, which excludes
interpreter startup, exactly as the gate's own `wallMicros` does. That makes
the numbers comparable to the published figure and makes both of them an
underestimate of what a per-task subprocess actually costs.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from croissant_policy import emit, parse  # noqa: E402
from croissant_policy.reference import gate_root, load_gate  # noqa: E402

descriptor_mod, _, gate_mod = load_gate()

WARMUP = 200


def _time(fn, iterations: int) -> dict:
    for _ in range(WARMUP):
        fn()
    samples = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        fn()
        samples.append(time.perf_counter_ns() - start)
    samples.sort()
    return {
        "iterations": iterations,
        "medianMicros": round(statistics.median(samples) / 1000, 3),
        "meanMicros": round(statistics.fmean(samples) / 1000, 3),
        "p95Micros": round(samples[int(0.95 * len(samples)) - 1] / 1000, 3),
        "minMicros": round(samples[0] / 1000, 3),
    }


def measure(native: dict, action: str, context: dict, iterations: int) -> dict:
    doc = emit.emit(native)
    native_text = json.dumps(native)
    doc_text = json.dumps(doc)

    native_desc = descriptor_mod.Descriptor.from_json(native)
    profile_desc = parse.to_descriptor(doc)

    # Sanity: the thing being timed must be the thing being claimed.
    a = gate_mod.authorize(native_desc, action, context).as_record()
    b = gate_mod.authorize(profile_desc, action, context).as_record()
    a.pop("evalMicros"), b.pop("evalMicros")
    if a != b:
        raise SystemExit("benchmark aborted: the two paths do not agree on the decision")

    return {
        "dataset": native["datasetId"],
        "action": action,
        "verdict": a["verdict"],
        "bytes": {"native": len(native_text), "profile": len(doc_text)},
        "warm": {
            "native": _time(lambda: gate_mod.authorize(native_desc, action, context), iterations),
            "profile": _time(lambda: gate_mod.authorize(profile_desc, action, context), iterations),
        },
        "cold": {
            "native": _time(
                lambda: gate_mod.authorize(
                    descriptor_mod.Descriptor.from_json(json.loads(native_text)), action, context
                ),
                iterations,
            ),
            "profile": _time(
                lambda: gate_mod.authorize(
                    parse.to_descriptor(json.loads(doc_text)), action, context
                ),
                iterations,
            ),
        },
        "translationOnly": {
            "parseJson": _time(lambda: json.loads(doc_text), iterations),
            "toNative": _time(lambda: parse.to_native_json(json.loads(doc_text)), iterations),
            "toDescriptor": _time(lambda: parse.to_descriptor(json.loads(doc_text)), iterations),
        },
    }


def _delta(case: dict, regime: str) -> dict:
    n = case[regime]["native"]["medianMicros"]
    p = case[regime]["profile"]["medianMicros"]
    return {
        "nativeMicros": n,
        "profileMicros": p,
        "addedMicros": round(p - n, 3),
        "relativePct": round(100.0 * (p - n) / n, 1) if n else None,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Measure the profile path's overhead")
    ap.add_argument("--iterations", type=int, default=5000)
    ap.add_argument("--out", type=Path, default=Path("results/profile_overhead.json"))
    args = ap.parse_args(argv)

    descriptors = sorted((gate_root() / "descriptors").glob("*.json"))
    if not descriptors:
        raise SystemExit(f"no descriptors under {gate_root() / 'descriptors'}")

    # One permitted and one refused request per dataset: a refusal walks a
    # different path through the evaluator and there is no reason to assume it
    # costs the same.
    cases = []
    for path in descriptors:
        native = json.loads(path.read_text())
        first = native["permissibleActions"][0]
        satisfying = {}
        for key, spec in (first.get("conditions") or {}).items():
            if isinstance(spec, dict):
                satisfying[key] = (
                    spec.get("min") or spec.get("max") or spec.get("equals")
                    or (spec["in"][0] if "in" in spec else True)
                )
        cases.append(measure(native, first["name"], satisfying, args.iterations))
        cases.append(measure(native, "no-such-action", {}, args.iterations))

    report = {
        "iterationsPerCase": args.iterations,
        # The gate's identity is its directory name; its full path is this
        # machine's business and this file is committed.
        "referenceGate": gate_root().name,
        "publishedGateProcessMedianMicros": 119,
        "publishedPolicyEvalMedianMicros": 11,
        # Provenance, because this constant was wrong once. 122 us was the
        # median over the 7 decisions of the single-run study; it was retired
        # when the replication measured 210.
        "publishedFigureSource": (
            "ok-nfcore-admission-gate results/replication.json, gated arm, "
            "n=210 decisions over 30 replicates"
        ),
        "cases": cases,
        "summary": {
            "warmAddedMicrosMedian": round(
                statistics.median([_delta(c, "warm")["addedMicros"] for c in cases]), 3
            ),
            "coldAddedMicrosMedian": round(
                statistics.median([_delta(c, "cold")["addedMicros"] for c in cases]), 3
            ),
            "coldProfileMicrosMedian": round(
                statistics.median([c["cold"]["profile"]["medianMicros"] for c in cases]), 3
            ),
            # The published 119 us is a whole gate *process*: argument parsing,
            # descriptor load, authorize, and writing the decision record. The
            # cold figures here cover load + authorize only, so the two are not
            # comparable head to head. What is comparable is the delta: swapping
            # the native descriptor for a profile document adds this much to
            # that process, and nothing else about it changes.
            "projectedGateProcessMicros": None,
        },
    }
    report["summary"]["projectedGateProcessMicros"] = round(
        report["publishedGateProcessMedianMicros"]
        + report["summary"]["coldAddedMicrosMedian"], 1
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")

    print(f"{'case':34} {'warm native':>12} {'warm profile':>13} "
          f"{'cold native':>12} {'cold profile':>13}")
    for c in cases:
        label = f"{c['dataset']}:{c['action']} [{c['verdict']}]"
        print(f"{label:34} {c['warm']['native']['medianMicros']:12.3f} "
              f"{c['warm']['profile']['medianMicros']:13.3f} "
              f"{c['cold']['native']['medianMicros']:12.3f} "
              f"{c['cold']['profile']['medianMicros']:13.3f}")
    s = report["summary"]
    print()
    print(f"median added cost, warm: {s['warmAddedMicrosMedian']:+.3f} us/decision")
    print(f"median added cost, cold: {s['coldAddedMicrosMedian']:+.3f} us/decision")
    print(f"cold profile path total: {s['coldProfileMicrosMedian']:.3f} us/decision "
          "(load + authorize only)")
    print(f"projected gate process:  {s['projectedGateProcessMicros']:.1f} us "
          "= published 119 us + the cold delta")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
