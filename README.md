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

# Tests and benchmark
make test
make bench
```

`NFGATE_ROOT` points at the gate's checkout. It defaults to
`../dk-nfcore-admission-gate`, and the import fails loudly rather than falling
back to a local reimplementation, because a silent fallback is the one
behaviour that would make the test suite lie.

## Honest limits

- **The `@context` has not been checked against `mlcroissant`.** Conformance
  clause 1 is therefore unverified, and the validator says so as a warning on
  every document rather than checking a weaker structural condition and letting
  the reader assume it was the real thing. Running MLCommons' validator is a
  precondition for any external submission. See SPEC section 9.
- **The corpus is three descriptors.** Real ones, gating a real pipeline, but
  three. Equivalence over a generated request matrix on three descriptors is
  evidence, not proof.
- **No identity, no entitlement.** Conditions are evaluated against a context;
  who supplied it and whether they were entitled to is out of scope in 0.1.0.
  That boundary is the interesting one -- an agent control plane binds policy to
  the caller and cannot answer a question whose answer belongs to the data, and
  this profile is the other half of that pair -- but the two halves have not
  been run together and their precedence is undefined.
- **The profile IRI is a placeholder.** It does not resolve and is not a claim
  on any registered namespace.
