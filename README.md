# ok-croissant-policy-profile

A **policy profile for Croissant** dataset descriptors, with a reference
implementation, a conformance validator, an MCP capability projection, and
measured overhead.

Croissant describes what a dataset *is*. It does not say what may be *done*
with it, by whom, in which state, or what happens when a consumer asks for
something the dataset does not permit. This profile adds one additive layer
that answers those questions from the descriptor alone.

The specification is [SPEC.md](SPEC.md). Everything below is about the code.

Archived at [doi:10.5281/zenodo.22018156](https://doi.org/10.5281/zenodo.22018156),
which always resolves to the newest deposited version.

The records deposited before it were deleted on 2026-08-19 rather than
superseded: they published a 122 us gate-process figure taken from a 7-decision
run, which a 30-replicate run had already replaced with 119 us over 210
decisions. Files on a published record cannot be edited, so withdrawal was the
only correction available. v0.1.6 is the first release deposited under the DOI
above, and the DOIs 10.5281/zenodo.22005283, ...284, ...346, ...347 and ...386
must not be cited.

## Three independent publications

This work is published three times, from three perspectives, in three separate
repositories. Each establishes the result standing alone; none needs the others
to be read, reviewed or believed.

| Perspective | Artifact | Destination |
|---|---|---|
| **Does it run, and what does it cost?** | this repository | GitHub public + [doi:10.5281/zenodo.22018156](https://doi.org/10.5281/zenodo.22018156) |
| Is the argument sound, and what was measured? | the preprint | arXiv |
| Should the vocabulary become a standard? | the specification proposal | github.com/mlcommons/croissant |

The specification appears in this repository **and** in the proposal repository
as a copy rather than a reference, because independence requires it: an
implementation that cannot show what it implements is not self-contained, and
neither is a proposal that points elsewhere for its own normative text. They are
kept in step by hand, which is the cost of independence and is accepted
deliberately.

## The design in one paragraph

A `cpol:Policy` hangs off the Croissant `sc:Dataset` node, carrying the
dataset's state, a mandatory `failClosed`, and the actions it admits. Each
action names the states that admit it and a list of conditions drawn from a
**closed set of five operators** -- `min`, `max`, `in`, `equals`, `present`.
Closed is the point: every policy is decidable in constant time and explainable
in one line, and an operator the evaluator does not implement produces a
refusal rather than a skipped check. Where richer rights modelling is needed,
ODRL/ODRE is the right tool and this profile does not compete with it.

## There is no evaluator in this repository

That is deliberate, and it is the load-bearing decision.

A profile document is admitted or refused by translating it into the native
descriptor model of [`ok-nfcore-admission-gate`](../ok-nfcore-admission-gate)
and calling that repository's `gate.gate.authorize` -- the same function that
produced its measured 119 microsecond median over 210 decisions in a
30-replicate nf-core pipeline run.
The gate is imported, never vendored, so a decision taken through Croissant is
taken by the implementation the measurement came from rather than by a copy of
it that can drift.

Fail-closed follows from the same choice. The native evaluator already refuses
on a condition whose operator it does not recognise. So every degenerate case
-- unknown operator, missing field, duplicate condition name, a policy that
does not declare `failClosed` -- is *translated into* that condition and
refused by code that already existed. There is no new enforcement code here to
get wrong; there is a translation, and a translation that fails produces a
refusal rather than a gap.

## Claims and where they are checked

| | Claim | Checked by | Result |
|---|---|---|---|
| C1 | Every decision from the native descriptor is reproduced exactly from the profile document | [tests/test_equivalence.py](tests/test_equivalence.py) | whole decision records equal across a generated request matrix covering PERMIT and all three refusal classes |
| C2 | Strip the `cpol:` terms and a plain Croissant consumer still has a loadable dataset | [tests/test_degradation.py](tests/test_degradation.py) | no residue, no redefined term, the descriptive half survives in standard vocabulary |
| C3 | The profile path's cost is disclosed, not assumed | [bench/profile_overhead.py](bench/profile_overhead.py) | **+0.0 us** warm, **+11.7 us** cold per decision |
| C4 | Capability schemas are derived from the policy, so they cannot drift from it | [tests/test_capabilities.py](tests/test_capabilities.py) | moving a threshold in the document moves the advertised `minimum` and the gate's verdict in the same edit |
| — | The emitted documents are valid Croissant | [tools/validate_mlcroissant.py](tools/validate_mlcroissant.py) | all three load under `mlcroissant` 1.1.0 with zero errors; `@context` identical to MLCommons' generated one |
| P1 | Caller-side and data-side policy disagree in **both** directions | [tests/test_precedence.py](tests/test_precedence.py) | each refuses requests the other admits; neither permit set contains the other |
| P2 | Only the conjunction admits nothing either authority refused | [bench/precedence.py](bench/precedence.py) | of the requests some authority refused, `caller-only` still admits **23** and `data-only` **12**, while `deny-overrides` admits **0** of them |

## Measured overhead

From `bench/profile_overhead.py`, 5000 iterations per case, in-process with
`perf_counter_ns`, over the three real descriptors:

| regime | native | profile | added |
|---|---:|---:|---:|
| **warm** -- document translated once, descriptor reused | 1.8 us | 1.8 us | **0.0 us** |
| **cold** -- document read and translated per decision | 8.5 us | 20.2 us | **+11.7 us** |

Warm is zero because it is the same function on the same object; there is
nothing left to differ. Cold is where the profile actually costs something, and
most of that cost is not the profile: parsing the JSON accounts for ~9.7 us of
the ~11.7, because a Croissant document with its context is 3.1 KB against the
native descriptor's 754 B. The profile-specific translation is ~2 us.

Put against the published figure: the gate process that measured 119 us
end-to-end would become ~131 us, a 10% increase in a number four orders of
magnitude below the ~1 second tasks it gates.

What that increase is *not* is unobservable. The 30-replicate run measured a
per-task duration delta of +25.7 ms on average, 95% CI [3.3, 48.2] ms, an
interval that excludes zero -- so the gated arm is distinguishable from the
baseline in pipeline timing. That cost is the delivery mechanism rather than
the decision: the gate runs as a per-task subprocess with a ~30.2 ms median
process time, of which ~9.6 ms is bare interpreter startup. Against 30 ms of
delivery the profile's ~11.7 us is ~0.04%. An earlier version of this file
claimed the gate stayed below the resolution of Nextflow's own trace; the
replication retired that claim and it is not repeated here.

The honest caveat is the same one the gate carries: this excludes interpreter
startup, because it is measured inside the process. A per-task subprocess pays
tens of milliseconds for `python3` itself, and that dominates both paths.

## Namespace

The profile IRI is `https://w3id.org/croissant-policy/0.1.0`, a
[w3id.org](https://w3id.org) permanent identifier.

**It does not resolve yet.** The registration pull request to
[perma-id/w3id.org](https://github.com/perma-id/w3id.org) has not been
submitted, so the IRI currently returns 404. The redirect rules that will make
it resolve are ready in `w3id/croissant-policy/.htaccess`, and their target is
already live: the profile document is served from `docs/ns/` at
[doytsujin.github.io/ok-croissant-policy-profile/ns/0.1.0/](https://doytsujin.github.io/ok-croissant-policy-profile/ns/0.1.0/),
which also returns `context.jsonld` under content negotiation for
`application/ld+json`. Until the registration lands, use that URL to retrieve
the document and treat the w3id string as an identifier only.

A w3id rather than a direct URL because every conforming document embeds this
string. The identifier has to survive a change of hosting, so it is never
reassigned and never changed in place — a new version gets a new path.

## Croissant validity

`tools/validate_mlcroissant.py` runs MLCommons' reference validator. It is a
separate step behind a venv because `mlcroissant` pulls in pandas, numpy, scipy
and rdflib, and this package is standard library only.

Running it was worth doing rather than asserting. It found three defects:

- The hand-written `@context` carried four terms it should not have —
  `arrayShape` and `isArray` are Croissant **1.1**, and `dataBiases` and
  `dataCollection` are not Croissant terms at any version — and was missing
  `equivalentProperty` and `samplingRate`. It is now generated from MLCommons'
  own function.
- Provenance of collection was written to a bare `dataCollection` key, which
  under `@vocab` resolved to a schema.org term that does not exist. RAI terms go
  through the `rai:` prefix.
- A `cr:FileObject` must carry `md5` or `sha256`; the decision-record node had
  neither. The emitter now computes a SHA-256 from the file, a directory of logs
  becomes a `cr:FileSet` (a pattern, no checksum needed), and a path that does
  not exist is refused rather than described with an invented digest.

Two warnings remain, both for *recommended* properties — `citeAs` and
`datePublished`. Both are emitter overrides; neither is invented for a dataset
whose citation and publication date are not known.

## Experiment 2: caller-side vs data-side precedence

An agent control plane binds policy to the **caller**. This profile binds it to
the **data**. `bench/precedence.py` runs both over the same request space and
counts what each deployment misses.

The caller side is a **model** — four scopes in `examples/callers/` written in
the structure those products describe — so the counts are designed, not
measured. The data side is the real descriptor corpus. Both are evaluated by the
same `gate.authorize`, deliberately: different evaluators would let a
disagreement come from the evaluators rather than from the policies.

184 requests, 4 caller scopes × 3 datasets × the generated matrix:

| agreement | count |
|---|---:|
| Both permit | 12 |
| Both refuse | 137 |
| Only the caller refuses | 12 |
| Only the dataset refuses | 23 |

| deployment | admits a request an authority refused |
|---|---:|
| `caller-only` — an agent control plane alone | **23** |
| `data-only` — an admission gate alone | **12** |
| `deny-overrides` — both consulted | **0** |

Neither permit set contains the other, so precedence is a real question. The
part that does not depend on our choice of scopes: **each authority has a class
of rule the other cannot express at all.** Three of the dataset's refusals turn
on its lifecycle state, which no caller-side policy can name; six of the
caller's turn on its own lapsed assurance and four on an entitlement it does not
hold, which no descriptor can name.

Cost with both descriptors resident: **5.7 µs** against 2.5 µs for one side —
the expected factor of two. Running both is not expensive; it has simply not
been specified.

The joint receipt (`examples/joint-receipt.json`) carries both verdicts, both
condition lists including the passing conditions of the authority that
permitted, and what each of the five precedence rules would have decided.

**These rates are not base rates.** The matrix is deliberately weighted toward
violations; 19% disagreement is a property of the matrix, not of production
traffic.

## Re-deciding an archive against a later policy

`croissant_policy/recheck.py` answers the question a validation function asks
after every policy change and cannot otherwise answer: **you tightened the
policy; which of last year's admissions would fail under it today?**

Re-running the pipelines is not an option -- they took hours, the inputs may be
gone, and avoiding the second run is the point. So the decision is re-taken from
the **record**, with no original data, no pipeline, and no evaluator state.

That works only because of what the receipt already carries. Every condition is
stored with its *observed* value as well as its expected one, so the record
holds the facts the decision turned on rather than only the verdict it reached.

It runs in two directions. The arithmetic is identical; the claim being made
about the past is not, and conflating them would put a deviation finding in
front of someone who asked for a change estimate.

```sh
# backwards — the policy in force now, against decisions already taken.
# A result here is a statement about work that has happened. Exit 1 on any
# newly-refused decision, so it drops into CI as a policy-change gate.
python3 -m croissant_policy.recheck decisions.jsonl --policy current.json --mode review

# forwards — a policy not yet adopted, against the same archive. Estimates the
# blast radius before committing to the change. Adjudicates nothing historical,
# and never fails a build.
python3 -m croissant_policy.recheck decisions.jsonl --policy proposed.json \
    --mode impact --report assessment.md
```

Run against the 285-record archive from the reference repository -- thirty
replicates of a real `nf-core/demo` run -- with the `trim` read-length floor
raised from 20 to 35:

```
rechecked 255 stored decision(s) against a proposed policy
  30 record(s) set aside — governed by another policy (qc-report 30)

  coverage         100.0%

  unchanged         165
  would be refused   90
  newly permitted     0
  indeterminable      0

would be refused if the proposed policy were adopted
  raw-reads.trim   x90
      minReadLength: 30 violates >= 35
```

`--report` writes the assessment as a Markdown document — what was compared,
coverage, the result, and the method with its limits — because a quality
function attaches a document to a change control, not a shell transcript.

`--policy` takes either a Croissant profile document or a native descriptor;
which one it is is decided by the document rather than by a flag the caller can
get wrong.

### Coverage is reported before the counts

A stored decision can be re-decided only where its record carries the facts the
new policy asks about. **"12 newly refused" means one thing at 98% coverage and
nothing at all at 20%**, where the honest reading is that the archive cannot
answer the question and the twelve are whatever fell inside the answerable part.

So coverage leads the report, and below 90% the counts are labelled a lower
bound rather than a result. The report also lists which conditions the archive
lacks, because coverage is a property of what was captured at decision time: it
improves going forward and cannot be recovered for decisions already taken.

### The fourth outcome is the honest one

`INDETERMINABLE` is the method refusing to guess. If the new policy names a
condition that was never checked when the decision was taken, no observed value
for it exists anywhere, and any verdict produced would be invented.

The distinction it rests on is narrow and worth stating: a condition recorded
with `observed: null` **is** information -- it says the fact was absent at the
time, and that is re-decidable. A condition the record never mentions says
nothing at all.

One consequence follows and is not hidden: **a record's re-decidability is
proportional to how far its decision got.** A permit evaluated every condition
and records them all. A refusal on state, or on an undeclared action,
short-circuits before any condition is evaluated and carries no facts, so it can
only be re-decided where the new policy turns on state alone. That asymmetry is
a property of the gate rather than of this module, and it is reported rather
than smoothed over.

For a joint receipt only the data-side policy is re-decided; the caller's
verdict is taken as recorded, because re-deciding it would mean substituting our
own document for a separate authority's.

### A policy decides the records it governs, and no others

A receipt store holds every dataset's decisions, so a mixed archive is the
ordinary input rather than an error. Records governed by another policy are
partitioned out, counted, and named -- never decided. Deciding one anyway
produces a fabricated finding: an action this policy does not declare is
refused, correctly, for a request that was never made, and the result reads as
a permitted decision turned refusal.

An archive that holds records but none this policy governs exits **2**. That is
a mismatched invocation, not a result, and reporting it as zero findings would
be a pass in review mode and an estimate of nothing in impact mode.

### Repetition is counted, not printed

The same decision is taken on every task of every replicate, so one tightened
threshold produces ninety identical findings. Each distinct finding is stated
once with the number of decisions it covers. Nothing is truncated -- the
distinct reasons are few, so a cap would add a silent limit where none is
needed.

## Use

```bash
# Emit conforming documents from native descriptors
python3 -m croissant_policy.emit ../ok-nfcore-admission-gate/descriptors/*.json \
    --outdir examples --url https://github.com/nf-core/test-datasets \
    --license https://spdx.org/licenses/MIT.html --decision-record decisions.jsonl

# Check conformance (SPEC section 3)
python3 -m croissant_policy.validate examples/*.json

# Project onto an MCP tool list
python3 -m croissant_policy.capabilities examples/*.json --out examples/capabilities.json

# Tests and benchmarks
make test
make bench            # C3, the profile path's overhead
make precedence       # experiment 2

# Croissant validity (needs the venv)
make venv
make mlcroissant
```

`NFGATE_ROOT` points at the gate's checkout. It defaults to
`../ok-nfcore-admission-gate`, and the import fails loudly rather than falling
back to a local reimplementation, because a silent fallback is the one
behaviour that would make the test suite lie.

## Honest limits

- **The caller side of experiment 2 is designed, not measured.** The four scopes
  are ours. A different set produces different counts. What survives a different
  set is the structural result: the disagreement exists in both directions and
  each authority has a class of rule the other cannot express. Replacing the
  model with a real control plane is the largest remaining gap.
- **Croissant validity is verified for `examples/` only**, by
  `tools/validate_mlcroissant.py`. This package's own validator checks the
  profile's conformance clauses structurally and does not parse JSON-LD; it says
  so on every report.
- **The corpus is three descriptors.** Real ones, gating a real pipeline, but
  three. Equivalence over a generated request matrix on three descriptors is
  evidence, not proof.
- **No identity, no entitlement in the profile itself.** Conditions are
  evaluated against a context; who supplied it is out of scope in 0.1.0. The
  caller-side half lives in `croissant_policy/caller.py` as a separate
  authority, not as a profile term, because a rule about the caller does not
  belong in a document that travels with the data.
- **The reference gate lives in a private repository.** The profile imports its
  evaluator from `ok-nfcore-admission-gate` rather than vendoring it, which is
  the design decision that makes the equivalence claim mean anything — and it
  means a third party cannot currently run the test suite. `reference.py` fails
  with an explanation rather than silently falling back. Publishing that
  repository is the fix; vendoring a copy is not, because the copy is exactly
  what would drift.
