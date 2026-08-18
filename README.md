# dk-croissant-policy-profile

A **policy profile for Croissant** dataset descriptors, with a reference
implementation, a conformance validator, an MCP capability projection, and
measured overhead.

Croissant describes what a dataset *is*. It does not say what may be *done*
with it, by whom, in which state, or what happens when a consumer asks for
something the dataset does not permit. This profile adds one additive layer
that answers those questions from the descriptor alone.

The specification is [SPEC.md](SPEC.md). Everything below is about the code.

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
descriptor model of [`dk-nfcore-admission-gate`](../dk-nfcore-admission-gate)
and calling that repository's `gate.gate.authorize` -- the same function that
produced its measured 122 microsecond figure on a real nf-core pipeline run.
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
| C3 | The profile path's cost is disclosed, not assumed | [bench/profile_overhead.py](bench/profile_overhead.py) | **+0.0 us** warm, **+11.9 us** cold per decision |
| C4 | Capability schemas are derived from the policy, so they cannot drift from it | [tests/test_capabilities.py](tests/test_capabilities.py) | moving a threshold in the document moves the advertised `minimum` and the gate's verdict in the same edit |
| — | The emitted documents are valid Croissant | [tools/validate_mlcroissant.py](tools/validate_mlcroissant.py) | all three load under `mlcroissant` 1.1.0 with zero errors; `@context` identical to MLCommons' generated one |
| P1 | Caller-side and data-side policy disagree in **both** directions | [tests/test_precedence.py](tests/test_precedence.py) | each refuses requests the other admits; neither permit set contains the other |
| P2 | Only the conjunction admits nothing either authority refused | [bench/precedence.py](bench/precedence.py) | `caller-only` admits **23**, `data-only` admits **12**, `deny-overrides` admits **0** |

## Measured overhead

From `bench/profile_overhead.py`, 5000 iterations per case, in-process with
`perf_counter_ns`, over the three real descriptors:

| regime | native | profile | added |
|---|---:|---:|---:|
| **warm** -- document translated once, descriptor reused | 1.8 us | 1.8 us | **0.0 us** |
| **cold** -- document read and translated per decision | 8.6 us | 20.4 us | **+11.9 us** |

Warm is zero because it is the same function on the same object; there is
nothing left to differ. Cold is where the profile actually costs something, and
most of that cost is not the profile: parsing the JSON accounts for ~9.7 us of
the ~11.9, because a Croissant document with its context is 3.2 KB against the
native descriptor's 754 B. The profile-specific translation is ~2 us.

Put against the published figure: the gate process that measured 122 us
end-to-end would become ~134 us. That is a 10% increase in a number that is
four orders of magnitude below the ~1 second tasks it gates, and it remains
below the one-second resolution of Nextflow's own trace, so it is no more
observable in pipeline timing than the original was.

The honest caveat is the same one the gate carries: this excludes interpreter
startup, because it is measured inside the process. A per-task subprocess pays
tens of milliseconds for `python3` itself, and that dominates both paths.

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

## Use

```bash
# Emit conforming documents from native descriptors
python3 -m croissant_policy.emit ../dk-nfcore-admission-gate/descriptors/*.json \
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
`../dk-nfcore-admission-gate`, and the import fails loudly rather than falling
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
- **The profile IRI is a placeholder.** It does not resolve and is not a claim
  on any registered namespace.
