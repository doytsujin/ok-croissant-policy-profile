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

We show four things. Decisions taken from a profile document are identical --
verdict, refusal class, reasons, and the full list of conditions checked -- to
decisions taken from the native descriptor of a gate that has been run in front
of a real nf-core pipeline. Removing the policy layer leaves a valid Croissant
document, so a profile-unaware consumer is unaffected. The added cost is 0
microseconds when the descriptor is reused and 11.9 microseconds when the
document is re-read for every decision, against a gate process previously
measured at 122 microseconds. And the policy projects deterministically onto
Model Context Protocol tool schemas, so an agent registry ingests data-side
policy without a human transcribing it -- which is the mechanism by which
advertised constraints and enforced constraints stop drifting apart.

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

## 4. What this does not do

No identity and no entitlement: conditions are evaluated against a context, and
who supplied it is out of scope. No obligations or duties. No temporal or
stateful conditions -- no windows, quotas or counters. No drift or relearning
semantics. Retention is carried and not applied, which the test suite asserts
rather than the prose merely stating.

Each omission is a place where the honest answer is that the mechanism is not
here, rather than a place where the profile quietly permits.

## 5. Threats to validity

The `@context` has not been checked against MLCommons' `mlcroissant`
validator. Conformance clause 1 is therefore unverified, and the profile's own
validator reports that as a warning on every document instead of checking a
weaker structural condition and letting a reader assume it was the real thing.
This is the first thing to close before submission anywhere.

The corpus is three descriptors. They are real and they gated real execution,
but equivalence over a generated matrix on three descriptors is evidence and
not proof. The overhead figures are in-process and exclude interpreter startup,
exactly as the gate's own published figure does, which makes them comparable
and makes both an underestimate of what a per-task subprocess costs.

The profile IRI is a placeholder that does not resolve.

## 6. Next

- Validate the `@context` with `mlcroissant` and report the result either way.
- **The precedence experiment.** An agent control plane binds policy to the
  caller; this profile binds policy to the data. Neither is complete, and no
  vendor material or literature we found addresses what happens when the two
  disagree -- which wins, and whether the disagreement produces one joint
  receipt or two unrelated ones. The harness for this exists on both sides. It
  is the natural second experiment and it is not done; nothing in this draft
  should be read as having measured it.
- Take the profile to the MLCommons Data working group as a proposal rather
  than publishing it only as a preprint. The value of a profile is proportional
  to how many consumers implement it.
