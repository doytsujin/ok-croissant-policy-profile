"""The impact assessment, as a document rather than terminal output.

A QA function does not attach a shell transcript to a change control. What it
attaches is a dated document that says what was compared, over what, what the
result was, and -- the part most tools omit -- how far the result can be
trusted.

Two things are deliberate here.

**Coverage is reported before the counts, not after.** A recheck can only decide
a stored record where the record carries the facts the new policy asks about.
Publishing "12 newly refused" without saying that 60% of the archive could not
be decided at all is not an incomplete report; it is a misleading one, because
the reader will take 12 as the answer rather than as a lower bound over an
unstated fraction.

**Repetition is counted, not printed.** An archive records the same decision on
every task of every replicate, so a single tightened condition can produce
hundreds of identical entries. Listing them one per line does not make the
document more complete; it makes the one distinct reason harder to find. Each
distinct finding appears once with the number of decisions it covers.

**The archive is named, not located.** This document is written to be handed to
a quality function and attached to a change control. An absolute path in it
identifies the machine that produced it and nothing a reader needs, so only the
file's name is rendered. Normalising here rather than at the call site means no
caller can reintroduce it.

**The mode changes the language, and only the language.** In REVIEW the tool is
asserting something about decisions already taken, which in a regulated setting
is a finding. In IMPACT it is estimating the effect of a change not yet adopted,
which is not. The arithmetic is identical; presenting one as the other would put
a deviation notice in front of someone who asked for an estimate.
"""

from __future__ import annotations

from pathlib import Path

from . import recheck as rk

_WORDING = {
    rk.REVIEW: {
        "title": "Retrospective policy review",
        "lede": (
            "Decisions already taken, re-decided against the policy currently in "
            "force. A result below is a statement about work that has happened."
        ),
        "refused": "Admitted then; would be refused under the current policy",
        "permitted": "Refused then; would be admitted under the current policy",
        "caution": (
            "This section identifies operations that were admitted under the "
            "rules in force at the time and would not be admitted under the "
            "current ones. Whether that constitutes a deviation is a judgement "
            "for the quality function, not a conclusion of this tool."
        ),
    },
    rk.IMPACT: {
        "title": "Policy change impact assessment",
        "lede": (
            "A proposed policy evaluated against the existing decision archive. "
            "Nothing below is a finding about past work: every decision in the "
            "archive was taken under the rules in force at the time."
        ),
        "refused": "Would be refused if the proposed policy were adopted",
        "permitted": "Would be admitted if the proposed policy were adopted",
        "caution": (
            "These are decisions the proposed policy would have refused. They "
            "were correctly admitted under the policy in force when they were "
            "taken. This is an estimate of future effect, not a deviation list."
        ),
    },
}


def _fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def render(
    results: list[rk.Recheck],
    totals: dict,
    *,
    mode: str = rk.REVIEW,
    policy_id: str = "",
    policy_version: str = "",
    archive: str = "",
    generated: str = "",
) -> str:
    """Produce the assessment as Markdown."""
    if mode not in rk.MODES:
        raise ValueError(f"mode must be one of {rk.MODES}, got {mode!r}")
    w = _WORDING[mode]
    counts = totals["counts"]
    cov = totals["coverage"]

    out = [f"# {w['title']}", ""]
    if generated:
        out += [f"*Generated {generated}.*", ""]
    out += [w["lede"], "", "## What was compared", ""]

    policy = policy_id or "(unnamed)"
    if policy_version:
        policy = f"{policy} @ {policy_version}"
    out += [
        f"| | |",
        f"|---|---|",
        f"| Policy evaluated | `{policy}` |",
        f"| Decision archive | `{Path(archive).name if archive else '(stdin)'}` |",
        f"| Records governed by this policy | {totals['total']} |",
    ]
    if totals.get("outOfScope"):
        named = ", ".join(
            f"`{k}` ({v})" for k, v in totals["outOfScopeDatasets"].items()
        )
        out += [
            f"| Records set aside | {totals['outOfScope']} |",
            f"| Archive total | {totals['total'] + totals['outOfScope']} |",
            "",
            f"The archive also holds {totals['outOfScope']} decision(s) governed "
            f"by another policy — {named}. They are not re-decided here and are "
            "not counted in anything below: this policy has no authority over "
            "them, and a verdict it produced for them would be an artefact of "
            "asking the wrong document.",
        ]
    out += [
        "",
        "## Coverage — read this before the counts",
        "",
    ]

    out += [
        f"**{_fmt_pct(cov)} of the records this policy governs could be "
        f"decided against it.**",
        "",
    ]
    if totals["dependable"]:
        out += [
            "A decision is re-decidable only where the record carries the facts "
            "the policy asks about. At this level the counts below can be read "
            "as the result.",
            "",
        ]
    else:
        out += [
            f"**The counts below are a lower bound, not the result.** "
            f"{counts[rk.INDETERMINABLE]} record(s) could not be decided at all "
            "because the policy asks about conditions those decisions never "
            "evaluated, so no observed value for them exists. Whatever is true "
            "of that fraction is unknown, and it is not safe to assume it "
            "resembles the part that could be decided.",
            "",
        ]

    out += [
        "## Result",
        "",
        "| Outcome | Count |",
        "|---|---:|",
        f"| Unchanged | {counts[rk.UNCHANGED]} |",
        f"| {w['refused']} | **{counts[rk.NEWLY_REFUSED]}** |",
        f"| {w['permitted']} | {counts[rk.NEWLY_PERMITTED]} |",
        f"| Could not be decided | {counts[rk.INDETERMINABLE]} |",
        "",
    ]

    refused = [r for r in results if r.outcome == rk.NEWLY_REFUSED]
    if refused:
        out += [f"## {w['refused']}", "", w["caution"], ""]
        out += [
            "| Dataset | Action | Decisions | Reason |",
            "|---|---|---:|---|",
        ]
        for r, n in rk.grouped(refused):
            who = f"<br>caller `{r.caller_id}`" if r.caller_id else ""
            reasons = "; ".join(r.reasons) or "—"
            out.append(f"| `{r.dataset_id}`{who} | `{r.action}` | {n} | {reasons} |")
        out.append("")

    permitted = [r for r in results if r.outcome == rk.NEWLY_PERMITTED]
    if permitted:
        out += [f"## {w['permitted']}", ""]
        for r, n in rk.grouped(permitted):
            count = f" — {n} decision(s)" if n > 1 else ""
            out.append(f"- `{r.dataset_id}` / `{r.action}`{count}")
        out.append("")

    undecided = [r for r in results if r.outcome == rk.INDETERMINABLE]
    if undecided:
        missing: dict[str, int] = {}
        for r in undecided:
            for name in r.missing:
                missing[name] = missing.get(name, 0) + 1
        out += [
            "## Could not be decided",
            "",
            "These records do not carry the facts this policy asks about. The "
            "conditions below were never evaluated when those decisions were "
            "taken, so no observed value for them exists in the archive.",
            "",
            "| Condition the policy asks about | Records lacking it |",
            "|---|---:|",
        ]
        for name, n in sorted(missing.items(), key=lambda kv: -kv[1]):
            out.append(f"| `{name}` | {n} |")
        out += [
            "",
            "**To make future archives answerable**, record these conditions "
            "from now on. Coverage is a property of what was captured at "
            "decision time and improves only going forward; it cannot be "
            "recovered for decisions already taken.",
            "",
        ]

    out += [
        "## Method and limits",
        "",
        "Each stored decision was re-decided from its own record: the observed "
        "value of every condition is written into the receipt at decision time, "
        "so the facts a decision turned on are in the archive. No pipeline was "
        "re-run, no original input was read, and no evaluator state was "
        "reconstructed.",
        "",
        "Three limits apply and are not worked around:",
        "",
        "1. A record can only answer questions it was asked. A condition never "
        "evaluated has no observed value, and this tool reports that rather "
        "than inferring one.",
        "2. A decision that short-circuited carries less. A refusal on state, or "
        "on an undeclared action, never reached its conditions, so it can be "
        "re-decided only where the policy turns on state alone.",
        "3. Where a record carries two authorities, only the data-side policy is "
        "re-decided. The caller's verdict is taken as recorded, because "
        "substituting our own document for a separate authority's would not be "
        "a re-decision of what happened.",
        "",
    ]
    return "\n".join(out)
