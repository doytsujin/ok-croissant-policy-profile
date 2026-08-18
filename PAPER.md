# A Policy Profile for Croissant: Refusal as a Property of the Dataset

Working draft. Target: arXiv preprint, a contribution to the MLCommons Data
working group, and a workshop track on dataset descriptors or agent governance.

## Abstract

Croissant has become the de facto machine-readable descriptor for ML datasets:
JSON-LD over schema.org, required at dataset tracks, ingested by Hugging Face,
Kaggle, OpenML and Google Dataset Search. It describes what a dataset is and
how to load it. It does not describe what may be done with it. That question is
answered today outside the descriptor -- in a data-use agreement, a wiki page,
or a reviewer's head -- which means an automated consumer cannot answer it at
all, and an agent that discovers a dataset through its descriptor discovers
nothing about the conditions of its use.

We define an additive policy profile for Croissant 1.0 in which a dataset
declares the operations it admits and the conditions under which it admits
them, so that a gate in front of the data can permit or refuse a request from
the descriptor alone and leave a record of what was checked. The profile is
deliberately narrow: a closed set of five operators, chosen so that every
policy is decidable in constant time and explainable in one line.

We show four things about the profile. Decisions taken from a profile document
are identical -- verdict, refusal class, reasons, and the full list of
conditions checked -- to decisions taken from the native descriptor of a gate
that has been run in front of a real nf-core pipeline. Removing the policy layer
leaves a valid Croissant document, verified with MLCommons' `mlcroissant`, so a
profile-unaware consumer is unaffected. The added cost is 0 microseconds when
the descriptor is reused and 11.9 microseconds when the document is re-read for
every decision, against a gate process previously measured at 122 microseconds.
And the policy projects deterministically onto Model Context Protocol tool
schemas, so an agent registry ingests data-side policy without a human
transcribing it -- which is the mechanism by which advertised constraints and
enforced constraints stop drifting apart.

We then show one thing about the setting. Agent control planes bind policy to
the caller; this profile binds it to the data. Running both authorities over the
same request space, neither one's permit set contains the other's: each refuses
requests the other admits, in both directions. A deployment that consults only
the caller admits requests the dataset refuses, and a deployment that consults
only the dataset admits requests the caller's own governance refuses. The
conjunction closes both gaps for roughly twice the cost of one decision --
5.7 microseconds against 2.5 -- and produces a single receipt naming both
authorities and carrying both condition lists, including the authority that
permitted.

## 1. The gap

Three threads are moving on dataset descriptors and only their intersection is
empty.

The **venue thread** treats the dataset as a citable object: *Scientific Data*
pioneered the Data Descriptor article type, Frontiers' FAIR² articles add
AI-readiness and executable notebooks, and in 2026 the *Journal of Biomedical
Physics and Engineering* adopted the type as well. The **format thread** is
Croissant, now the interoperable serialisation across the major dataset hubs.
The **actionability thread** is Croissant over MCP: an endpoint through which
an agent discovers, downloads and loads a dataset.

All three describe. None of them refuses. A descriptor that an agent can act
on, in a governed setting, has to be able to say no -- and to say what it
checked when it did.

The neighbouring work does not close this. RO-Crate and Workflow Run RO-Crate
record what happened, retrospectively; they do not decide whether it should.
ODRL expresses permissions without specifying evaluation, and ODRE supplies the
enforcement ODRL lacks -- but for rights over resources, not for dataset
structure, ML loading, or the state a dataset is in. Agent control planes
(watsonx Orchestrate's Agentic Control Plane, Drata's Mission Control) evaluate
an action against approved policy inline, before execution, which is
structurally the same mechanism aimed at a different subject: they bind policy
to the *caller*. A rule about what a dataset admits cannot be bound to a
caller, because it does not travel with one.

**Combining two authorities is old, and we do not claim it.** XACML has named
rule- and policy-combining algorithms since the early 2000s -- `deny-overrides`
among them, by that name -- and its ABAC model evaluates subject-side and
resource-side attributes within a single decision. Oracle's US10230732B2
(priority 2013) combines policies from separately administered sources under a
selected combining algorithm, deny-override by default. AWS Clean Rooms
enforces the most restrictive control across per-collaborator rules whose
authors cannot see each other's data, and IAM cross-account access requires a
resource-owner policy and a caller-account policy to agree. The mechanism of
section 4 is therefore not new, and any claim that consulting two authorities
is unspecified would be wrong.

Two things remain. First, these systems bind the resource-side half to a
*storage or account boundary*: a condition on the lifecycle state of a dataset
-- `QC_PASSED`, `PENDING` -- is not expressible in any of them, because the
vocabulary is access to an object rather than the scientific state of its
contents. Second, none of them travels: the policy lives in one provider's
control plane, not in a descriptor that moves with the data across
organisations. What section 4 contributes is not the conjunction but a
measurement of what is lost when the data-side half is absent, which is the
condition of every deployed agent control plane we are aware of.

## 2. Design

### 2.1 One constraint

A descriptor that can be refused from is only useful if the refusal is cheap,
total, and auditable. Cheap, because a gate on every access must not be the
thing you profile. Total, because a rule the enforcer does not understand must
stop the work rather than be skipped. Auditable, because a refusal that cannot
say what was checked is indistinguishable from a bug.

### 2.2 The layer

A `cpol:Policy` attaches to the Croissant `sc:Dataset` node. It carries the
dataset's lifecycle state, a mandatory `failClosed`, informative handling
metadata, and one or more `cpol:Action` nodes. Each action names the states
that admit it and a list of `cpol:Condition` nodes evaluated against the
request context.

The profile is additive by construction: removing every `cpol:`-prefixed term
must leave a valid Croissant document, and the layer must not redefine any core
term. The `@context` adds exactly two entries -- the namespace prefix, and one
typed term for the condition operand -- and every policy key is written
prefixed rather than aliased to a bare name, paying the verbosity to keep the
guarantee.

### 2.3 The closed operator set

`min`, `max`, `in`, `equals`, `present`. That is the whole language.

ODRL is more expressive and much harder to defend to an auditor. Five operators
mean every condition is decidable in constant time, and a decision record can
state in one line what was compared to what. Extending the set is a version
bump rather than a profile extension, because an evaluator must refuse an
operator it does not implement: a sixth operator added silently to a document
turns PERMIT into REFUSE, never into an unchecked pass.

### 2.4 Fail-closed as a property of the translation

The profile has no evaluator. A document is decided by translating it into the
native descriptor model of a gate that already exists and calling that gate.

This is what makes fail-closed cheap to believe rather than cheap to claim. The
native evaluator already refuses on a condition whose operator it does not
recognise. The translation maps every defect -- unknown operator, missing
field, duplicate condition name, a policy that does not declare `failClosed` --
onto exactly that condition. No new enforcement code exists in the profile
implementation, so there is no new enforcement code to get wrong. What exists
is a translation, and a translation that fails produces a refusal rather than a
gap.

### 2.5 Capability projection

Each action projects onto one MCP tool: a name, a generated description naming
the required states, and an input schema with one property per condition, typed
and constrained from the operator (`min` becomes `minimum`, `in` becomes an
`enum`, and so on).

Two consequences are intended. The constraint appears in the schema, so a
well-behaved caller can avoid a refusal instead of discovering it. And the
schema is derived rather than authored, so it cannot drift from the policy the
gate enforces -- the same document produces both. Hand-transcribed registry
entries are the failure mode this removes.

The projection describes what will be checked and never replaces the check. A
caller that satisfies the schema is still gated, which the evaluation of a
state precondition demonstrates directly: state is a property of the dataset,
the schema cannot carry it, and a request satisfying every advertised
constraint is still refused when the state is wrong.

## 3. Evaluation

The corpus is the three descriptors from `dk-nfcore-admission-gate`: real
descriptors that gated a real run of `nf-core/demo` v1.0.1 -- FASTQC,
SEQTK_TRIM, MULTIQC over Illumina amplicon test reads -- through Nextflow's
`process.beforeScript` hook, where a non-zero exit stops the task before its
script runs.

**C1, decision equivalence.** For every dataset, a request matrix is generated
from the descriptor rather than listed by hand: the satisfying context, the
empty context, a context of irrelevant keys, one violation per condition, a
non-numeric value for each numeric condition, and two undeclared action names.
Each request is decided twice -- once from the native descriptor, once from the
emitted profile document -- and the two complete decision records are compared,
not merely the verdicts. Two evaluators that agree on PERMIT/REFUSE and
disagree on the refusal class, the reasons, or the conditions they claim to
have checked are not equivalent in any sense an auditor would accept. All
records match, and the matrix is separately asserted to exercise PERMIT and all
three refusal classes, so that equivalence is not established over a set of
cases that happens to be trivial.

**C2, graceful degradation.** Stripping the layer leaves an `sc:Dataset` with
its name, description, distribution, provenance, custodian and schema intact
and no residue of the profile. The descriptive half of the native descriptor is
carried in standard vocabulary -- `additionalType`, `isBasedOn`,
`measurementTechnique`, `variableMeasured`, and schema.org's own
`additionalProperty` escape hatch for anything unmapped -- rather than in
`cpol:` terms, so a consumer that ignores the profile loses the policy and
nothing else. The `@context` is checked term by term against Croissant's to
confirm nothing is redefined.

Writing this test changed the specification. The profile IRI appears in
`conformsTo` as a *value*, not as a `cpol:`-prefixed key, so a literal reading
of clause 1 leaves a stripped document still claiming conformance to a profile
whose terms are gone -- a document that would fail the profile's own clause 3.
The strip now removes the claim with the terms, and the specification says so.

**C3, cost.** 5000 iterations per case, in-process, over the three descriptors,
for a permitted and a refused request each:

| regime | native | profile | added |
|---|---:|---:|---:|
| warm (document translated once, descriptor reused) | 1.8 us | 1.8 us | 0.0 us |
| cold (document read and translated per decision) | 8.6 us | 20.4 us | +11.9 us |

Warm is zero because it is the same function on the same object. Cold is where
the profile costs something, and most of that cost is not the profile: JSON
parsing accounts for about 9.7 of the 11.9 microseconds, because the Croissant
document with its context is 3.2 KB against the native descriptor's 754 B. The
profile-specific translation is about 2 microseconds.

Projected onto the published measurement, the gate process that took 122
microseconds end to end becomes about 134. That is a 10% increase in a number
four orders of magnitude below the roughly one-second tasks it gates, and it
stays below the one-second resolution of Nextflow's own trace -- so it is no
more observable in pipeline timing than the original was.

**C4, no drift.** Changing a threshold in the document changes the advertised
`minimum` and the gate's verdict in the same edit, because both are derived
from the same node. An operator outside the closed set projects as an
unsatisfiable parameter, because a capability that can never be called should
not advertise a callable schema.

## 4. Experiment 2: precedence between caller-side and data-side policy

### 4.1 The question

An agent control plane holds a registry of agents with an owner and a scope,
evaluates each action against approved policy inline before execution, and
blocks violations. That is structurally the same mechanism as the gate in
section 3, aimed at a different subject: it binds policy to the *caller*, this
profile binds it to the *data*.

Neither is complete. A caller-side rule cannot answer a question whose answer
belongs to the data, because the rule does not travel with the dataset. A
data-side descriptor cannot answer whether the caller is still in scope, because
the profile has no identity model and section 5 says so. Nothing in the vendor
material or in the descriptor literature we found states which authority wins
when they disagree, or whether the disagreement is recorded at all.

### 4.2 Method, and what is designed rather than measured

The data side is the corpus from section 3: three descriptors that gated a real
run. **The caller side is a model, and every number below inherits that.** Four
caller scopes are written in the structure the products describe -- an
identifier, an assurance state, and entitlements conditioned on the request --
representing a broadly entitled agent whose own threshold is laxer than the
dataset's, an agent scoped to agree with the dataset, an inspection-only agent,
and an agent whose attestation has lapsed.

One deliberate control: both authorities are evaluated by the same function. A
caller scope is translated into the same descriptor model and handed to the same
`gate.authorize`. If the two halves used different evaluators, a disagreement
could come from the evaluators rather than from the policies, and precedence
would not be the only variable.

The caller is given the request context plus the dataset's *name*. It is not
given the dataset's state, because that is exactly what does not travel with the
caller; supplying it would model a product that does not exist.

Five rules are enumerated rather than assumed: `deny-overrides` (permit only if
both permit), `caller-overrides`, `data-overrides`, and the two single-sided
deployments that actually exist today, `caller-only` and `data-only`.

### 4.3 Results

184 requests: 4 caller scopes × 3 datasets × the generated request matrix.

| agreement | count | share |
|---|---:|---:|
| Both permit | 12 | 6.5% |
| Both refuse | 137 | 74.5% |
| Only the caller refuses | 12 | 6.5% |
| Only the dataset refuses | 23 | 12.5% |

**Neither permit set contains the other.** Both disagreement classes are
non-empty, so precedence is a real question rather than an artifact of one
policy being stricter throughout.

| precedence rule | permits | admits a request an authority refused |
|---|---:|---:|
| `deny-overrides` | 12 | **0** |
| `caller-overrides` / `caller-only` | 35 | **23** (12.5% of requests) |
| `data-overrides` / `data-only` | 24 | **12** (6.5% of requests) |

The two rows that are not `deny-overrides` are the two products that exist. An
agent control plane operating alone admits every request in the fourth row of
the first table; an admission gate operating alone admits every request in the
third.

What each side structurally cannot reach is more interesting than the totals.
Of the 23 requests only the dataset refused, 20 violate a condition the caller
never carried and **3 turn on the dataset's lifecycle state** -- a class of rule
no caller-side policy can express, because the state is not a property of the
caller. Of the 12 only the caller refused, 6 turn on the caller's own lapsed
assurance and 4 on an entitlement the caller does not hold: the mirror image,
and equally unreachable from a descriptor.

**Cost.** With both descriptors resident, the conjunction is 5.7 µs against
2.5 µs for either side alone -- the expected factor of two plus bookkeeping.
Re-translating both documents per decision costs 17.6 µs. Running both
authorities is not expensive.

**One receipt.** The joint record carries both verdicts, both refusal classes,
both reason lists, and both condition lists including the passing conditions of
the authority that permitted. A record that keeps only the refusing half cannot
show the other authority was consulted, which is the reason to have one record
rather than two.

It also carries, for each of the five precedence rules, the verdict that rule
*would have* yielded on the same request -- not only the one applied. The
verdicts not reached are written into the record at decision time, so a later
reader determines from the record alone, without re-evaluating either policy and
without access to either document, whether the outcome depended on the
precedence rule in force. Where every rule agrees, the outcome is attributable
to the policies; where they differ, it is attributable to the configuration, and
the record says which. This matters because the policy that produced a decision
is frequently not retained in the form it had at the time, and a record that can
only be interpreted by re-running the system against a hypothetical
configuration is not evidence.

The same property makes the archive answerable after the fact. Because every
condition is stored with its observed value as well as its expected one, a
stored decision can be re-decided against a *later* policy without the original
data, the original pipeline, or the evaluator that produced it --
`croissant_policy/recheck.py` does this, and reports the fraction of an archive
that cannot be decided rather than guessing at it.

### 4.4 What these numbers are not

The rates are properties of the generated request matrix, which is deliberately
weighted toward violations -- one per condition, plus wrong types and undeclared
actions. They are not base rates of production traffic, and the 19% disagreement
figure should not be read as one. What the matrix does establish is
directional and structural: the disagreement exists in both directions, it is
not removable by choosing a stricter policy on either side, and each authority
has a class of rule the other cannot express at all.

The caller scopes are ours. A different set produces different counts. The
result that does not depend on them is the one in the previous paragraph.

## 5. What this does not do

No identity and no entitlement: conditions are evaluated against a context, and
who supplied it is out of scope. No obligations or duties. No temporal or
stateful conditions -- no windows, quotas or counters. No drift or relearning
semantics. Retention is carried and not applied, which the test suite asserts
rather than the prose merely stating.

Each omission is a place where the honest answer is that the mechanism is not
here, rather than a place where the profile quietly permits.

## 6. Threats to validity

The `@context` has now been checked against MLCommons' `mlcroissant` 1.1.0: all
three example documents load with zero errors and the context is identical to
the one MLCommons' own generator produces for Croissant 1.0. Doing so found
three defects that assertion would not have. The hand-written context carried
four terms it should not have -- two of them Croissant 1.1, two of them not
Croissant terms at any version -- and was missing two; provenance of collection
was being written to a bare `dataCollection` key that resolved to a schema.org
term that does not exist, rather than through the `rai:` prefix; and the
decision-record node was a `cr:FileObject` without the checksum Croissant
requires, which the emitter now computes rather than invents. Two warnings
remain on the examples, both for recommended properties (`citeAs`,
`datePublished`) that are supported as overrides and not fabricated.

That closes conformance clause 1 for the documents in `examples/`. It does not
close it in general: the profile's own validator checks the conformance clauses
structurally and does not parse JSON-LD.

The corpus is three descriptors. They are real and they gated real execution,
but equivalence over a generated matrix on three descriptors is evidence and
not proof. The overhead figures are in-process and exclude interpreter startup,
exactly as the gate's own published figure does, which makes them comparable
and makes both an underestimate of what a per-task subprocess costs.

The profile IRI is `https://w3id.org/croissant-policy/0.1.0`. The w3id.org
pull request and the namespace document it redirects to are both written; the
identifier is verified end to end before this paper is posted, and does not
resolve until then.

## 7. Next

- **Replace the modelled caller side with a real one.** Section 4's structural
  result stands on a model of an agent control plane. Running the conjunction
  against an actual product -- watsonx Orchestrate's control plane, or Drata's
  Mission Control -- would convert the direction into a measurement. This is now
  the largest gap in the paper.
- **A workload, not a matrix.** The disagreement rate needs a request
  distribution that reflects something real before it means anything.
- Extend the corpus beyond three descriptors.
- Take the profile to the MLCommons Data working group as a proposal rather
  than publishing it only as a preprint. The value of a profile is proportional
  to how many consumers implement it, and section 4 gives the working group a
  concrete reason to care: the profile is the half of the pair their members'
  control planes cannot supply.
