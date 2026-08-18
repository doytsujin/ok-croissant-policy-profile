"""Re-deciding a stored decision against a later policy.

The question this answers is one a validation function asks after every policy
change and cannot currently answer: *we tightened the policy in March; which of
last year's admissions would fail under it today?*

Answering it by re-running the pipelines is not an option. The runs took hours,
the inputs may be gone, and the point of asking is to avoid doing the work
twice. So the decision has to be re-taken from the **record**, without the
original data, the original pipeline, or the evaluator that produced it.

That is possible here only because of what the receipt already carries. Every
condition is stored with its *observed* value as well as its expected one, so
the record holds the facts the decision turned on -- not merely the verdict it
reached. Reconstruct the context from those observed values, evaluate the new
policy against it, and compare.

Four outcomes, and the fourth is the honest one:

    UNCHANGED        the new policy reaches the same verdict
    NEWLY_REFUSED    permitted then, refused now  <- the reason this exists
    NEWLY_PERMITTED  refused then, permitted now
    INDETERMINABLE   the new policy asks something the record does not answer

INDETERMINABLE is not a failure of the method; it is the method refusing to
guess. If a new policy names a condition that was never checked when the
decision was taken, no observed value for it exists anywhere, and any verdict
this module produced would be invented. It is reported, never assumed, in
keeping with the fail-closed discipline the rest of the profile follows.

**A record's re-decidability is proportional to how far its decision got.** A
permit evaluated every condition and records them all. A refusal on state, or
on an undeclared action, short-circuits before any condition is evaluated and
therefore carries no facts at all -- so it can only be re-decided where the new
policy turns on state alone. That asymmetry is a property of the gate, not of
this module, and `summary()` reports it rather than hiding it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from .parse import to_descriptor
from .reference import load_gate

UNCHANGED = "UNCHANGED"
NEWLY_REFUSED = "NEWLY_REFUSED"
NEWLY_PERMITTED = "NEWLY_PERMITTED"
INDETERMINABLE = "INDETERMINABLE"

OUTCOMES = (UNCHANGED, NEWLY_REFUSED, NEWLY_PERMITTED, INDETERMINABLE)


@dataclass
class Recheck:
    """One stored decision, re-decided."""

    dataset_id: str
    action: str
    caller_id: str | None
    outcome: str
    then: str
    now: str | None
    missing: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    precedence: str | None = None

    def as_record(self) -> dict:
        out = {
            "datasetId": self.dataset_id,
            "action": self.action,
            "outcome": self.outcome,
            "verdictThen": self.then,
            "verdictNow": self.now,
        }
        if self.caller_id:
            out["callerId"] = self.caller_id
        if self.precedence:
            out["precedence"] = self.precedence
        if self.missing:
            out["missingFacts"] = list(self.missing)
        if self.reasons:
            out["reasons"] = list(self.reasons)
        return out


# ---- reading the archive ------------------------------------------------


def data_side(record: dict) -> dict:
    """The half of the record the data-side policy decided.

    A joint receipt carries `caller` and `data`; a single-authority record is
    already the data side. Both shapes are accepted because both are emitted.
    """
    side = record.get("data")
    return side if isinstance(side, dict) else record


def facts(record: dict) -> dict:
    """Reconstruct the request context from what the record observed.

    A condition recorded with `observed: null` is *information*: it says the
    fact was absent when the decision was taken. That is different from a
    condition the record never mentions, which says nothing at all. The
    distinction is the whole basis of INDETERMINABLE, so absent keys are left
    absent here rather than defaulted.
    """
    side = data_side(record)
    return {
        c["name"]: c.get("observed")
        for c in side.get("conditionsChecked", [])
        if "name" in c
    }


def load_archive(path: str | Path) -> list[dict]:
    """Read a JSONL decision archive. Blank lines are skipped, not tolerated
    silently elsewhere -- a malformed line raises."""
    records = []
    with Path(path).open(encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{n}: {exc}") from exc
    return records


def load_policy(path: str | Path):
    """Load the *new* policy, as either a Croissant profile document or a
    native descriptor. Which one it is is decided by the document, not by a
    flag the caller can get wrong."""
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if "@context" in obj or "cpol:policy" in obj:
        return to_descriptor(obj)
    descriptor_mod, _, _ = load_gate()
    return descriptor_mod.Descriptor.from_json(obj)


# ---- re-deciding --------------------------------------------------------


def _required_names(action) -> tuple[str, ...]:
    return tuple(action.conditions.keys()) if action and action.conditions else ()


def recheck_one(record: dict, descriptor) -> Recheck:
    """Re-decide one stored record against a later policy.

    The policy is the new one; the *facts* are historical. So the descriptor's
    own declared state is replaced by the state the record observed at the
    time -- re-deciding asks what today's rules would have made of yesterday's
    situation, not what they make of today's.
    """
    _, _, gate_mod = load_gate()

    side = data_side(record)
    action = record.get("action") or side.get("action")
    then = record.get("verdict") or side.get("verdict")
    caller_id = record.get("callerId")
    precedence = record.get("precedence")
    observed_state = side.get("observedState", "")

    known = facts(record)
    declared = descriptor.action(action) if action else None

    # A condition the record never evaluated has no observed value anywhere.
    missing = tuple(n for n in _required_names(declared) if n not in known)
    if missing:
        return Recheck(
            dataset_id=descriptor.dataset_id,
            action=action or "",
            caller_id=caller_id,
            outcome=INDETERMINABLE,
            then=then,
            now=None,
            missing=missing,
            precedence=precedence,
            reasons=(
                f"new policy checks {', '.join(missing)}, which the stored "
                "decision never evaluated; no observed value exists",
            ),
        )

    historical = replace(descriptor, state=observed_state or descriptor.state)
    decision = gate_mod.authorize(historical, action, known)
    now = decision.verdict

    if precedence and "caller" in record:
        now = _recombine(record, now, precedence, gate_mod)

    if then == now:
        outcome = UNCHANGED
    elif then == gate_mod.PERMIT and now == gate_mod.REFUSE:
        outcome = NEWLY_REFUSED
    elif then == gate_mod.REFUSE and now == gate_mod.PERMIT:
        outcome = NEWLY_PERMITTED
    else:
        outcome = UNCHANGED

    return Recheck(
        dataset_id=descriptor.dataset_id,
        action=action or "",
        caller_id=caller_id,
        outcome=outcome,
        then=then,
        now=now,
        precedence=precedence,
        reasons=tuple(decision.reasons),
    )


def _recombine(record: dict, data_verdict: str, precedence: str, gate_mod) -> str:
    """Re-form the effective verdict for a joint receipt.

    Only the data-side policy changed. The caller's verdict is taken as
    recorded -- re-deciding it would need the caller-side policy, which is a
    separate authority's document and not ours to substitute.
    """
    caller_verdict = record.get("caller", {}).get("verdict")
    if precedence == "caller-only":
        return caller_verdict
    if precedence in ("data-only", "data-overrides"):
        return data_verdict
    if precedence == "caller-overrides":
        return caller_verdict
    # deny-overrides, and the safe default for an unknown rule
    both_ok = caller_verdict == gate_mod.PERMIT and data_verdict == gate_mod.PERMIT
    return gate_mod.PERMIT if both_ok else gate_mod.REFUSE


def recheck_all(records: list[dict], descriptor) -> list[Recheck]:
    return [recheck_one(r, descriptor) for r in records]


def summary(results: list[Recheck]) -> dict:
    counts = {o: 0 for o in OUTCOMES}
    for r in results:
        counts[r.outcome] += 1
    return {
        "total": len(results),
        "counts": counts,
        "newlyRefused": [r.as_record() for r in results if r.outcome == NEWLY_REFUSED],
        "indeterminable": [
            r.as_record() for r in results if r.outcome == INDETERMINABLE
        ],
    }


# ---- CLI ----------------------------------------------------------------


def _render(results: list[Recheck], totals: dict) -> str:
    counts = totals["counts"]
    lines = [
        f"rechecked {totals['total']} stored decision(s)",
        "",
        f"  unchanged        {counts[UNCHANGED]:>4}",
        f"  newly refused    {counts[NEWLY_REFUSED]:>4}",
        f"  newly permitted  {counts[NEWLY_PERMITTED]:>4}",
        f"  indeterminable   {counts[INDETERMINABLE]:>4}",
    ]
    refused = [r for r in results if r.outcome == NEWLY_REFUSED]
    if refused:
        lines += ["", "newly refused under the current policy"]
        for r in refused:
            who = f" caller={r.caller_id}" if r.caller_id else ""
            lines.append(f"  {r.dataset_id}.{r.action}{who}")
            for reason in r.reasons:
                lines.append(f"      {reason}")
    undecided = [r for r in results if r.outcome == INDETERMINABLE]
    if undecided:
        lines += [
            "",
            "indeterminable — the record does not carry the facts the new policy needs",
        ]
        for r in undecided:
            lines.append(
                f"  {r.dataset_id}.{r.action}  missing: {', '.join(r.missing)}"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="python -m croissant_policy.recheck",
        description=(
            "Re-decide stored decision records against a later policy, using "
            "only what the records observed. No pipeline is re-run."
        ),
    )
    ap.add_argument("archive", help="JSONL decision archive")
    ap.add_argument(
        "--policy", required=True, help="the current policy: Croissant profile or native descriptor"
    )
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    records = load_archive(args.archive)
    descriptor = load_policy(args.policy)
    results = recheck_all(records, descriptor)
    totals = summary(results)

    if args.json:
        print(json.dumps({**totals, "results": [r.as_record() for r in results]}, indent=2))
    else:
        print(_render(results, totals))

    # A newly-refused decision is the finding this tool exists to surface.
    return 1 if totals["counts"][NEWLY_REFUSED] else 0


if __name__ == "__main__":
    raise SystemExit(main())
