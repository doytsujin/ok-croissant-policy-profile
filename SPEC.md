# A Policy Profile for Croissant Dataset Descriptors

**Version** 0.1.0 (draft). Status: proposal. Namespace prefix: `cpol`.

## 1. Why this exists

Croissant describes what a dataset *is*. It does not say what may be *done*
with it, by whom, in which state, or what happens when a consumer asks for
something the dataset does not permit.

Those questions are answered outside the descriptor today -- in a data-use
agreement, a wiki page, or a reviewer's head -- which means an automated
consumer cannot answer them at all.

This profile adds one layer to Croissant: a machine-checkable statement of the
operations a dataset admits and the conditions under which it admits them, so
that a gate in front of the data can permit or refuse a request from the
descriptor alone, and leave a record of why.

The design constraint that shapes everything below: **a descriptor that can be
refused from is only useful if the refusal is cheap, total, and auditable.**
Cheap, because a gate on every access must not be the thing you profile.
Total, because a rule the enforcer does not understand must stop the work
rather than be skipped. Auditable, because a refusal that cannot say what was
checked is indistinguishable from a bug.

## 2. Relationship to existing work

| Standard | Answers | Does not answer |
|---|---|---|
| Croissant 1.0 | what the dataset is, how to load it | what may be done with it |
| RO-Crate / WRROC | what happened, retrospectively | whether it should have |
| DCAT / schema.org | how to find and cite it | conditions of use, mechanically |
| ODRL | how to *express* a permission | how to evaluate one (no enforcement spec) |
| ODRE | how to enforce ODRL policies | dataset structure, ML loading, drift |
| Agent control planes | whether the *caller* is in scope | whether the *data* admits the operation |

This profile is deliberately narrower than ODRL. ODRL is an expressive rights
vocabulary; this is a closed set of five operators chosen so that every policy
in the profile is decidable in constant time and explainable in one line. An
open expression language is more expressive and much harder to defend to an
auditor. Where richer rights modelling is needed, ODRL/ODRE is the right tool
and this profile does not compete with it.

The last row is the one that motivates the capability projection in section 7.
Agent control planes bind policy to a caller identity and enforce it inline
before an action runs. They cannot answer a question whose answer belongs to
the data, because the rule does not travel with the caller. This profile is the
callee half of that pair, and section 7 is the interface between them.

## 3. Conformance summary

A document conforms to this profile when all of the following hold.

1. **It is valid Croissant.** Removing every `cpol:`-prefixed term MUST leave a
   valid Croissant 1.0 document. The policy layer is purely additive: it MUST
   NOT redefine, constrain, or override any core Croissant or schema.org term.
   A Croissant consumer that has never heard of this profile MUST still be able
   to load the dataset.

   The profile IRI in `conformsTo` is removed along with the terms. This is not
   what a profile-unaware consumer does -- it ignores what it does not
   recognise and strips nothing -- but a document that keeps the claim after
   losing the terms would fail clause 3, advertising a policy it does not
   carry. Separability means the claim is separable too.
2. **`conformsTo` names both.** The dataset node MUST carry
   `"conformsTo": ["http://mlcommons.org/croissant/1.0",
   "https://w3id.org/croissant-policy/0.1.0"]`.
3. **Exactly one policy.** The dataset node MUST carry exactly one
   `cpol:policy`, whose value is a `cpol:Policy` node.
4. **Fail-closed is declared and true.** `cpol:failClosed` MUST be present on
   the policy and MUST be `true`. There is no conforming permissive mode; a
   document that wants one is not using this profile.
5. **Operators are from the closed set.** Every `cpol:Condition` MUST use an
   operator from section 5.3. An unrecognised operator is not an error in the
   document -- it is a **refusal at evaluation time** (section 6.2).

## 4. Namespace

```
cpol: https://w3id.org/croissant-policy/0.1.0/
```

The namespace is a [w3id.org](https://w3id.org) permanent identifier. It
dereferences to a human-readable profile document, and to the JSON-LD context
under content negotiation for `application/ld+json`.

A w3id rather than a direct URL, because the identifier has to outlive decisions
about hosting: every conforming document embeds this string, so moving the
document must not invalidate documents already in circulation. For the same
reason the namespace is **never reassigned and never changed in place**. A new
version gets a new path; it does not get a new host.

Nothing in the profile *depends* on the IRI dereferencing. A conforming document
is self-contained: it carries the full `@context` inline and can be read with no
network access. Resolution is for the reader who wants to know what the terms
mean, not for the evaluator.

## 5. Vocabulary

### 5.1 `cpol:Policy`

Attached to the Croissant `sc:Dataset` node via `cpol:policy`.

| Term | Range | Card. | Meaning |
|---|---|---|---|
| `cpol:state` | Text | 1 | The dataset's current lifecycle state. Opaque to the profile; compared only for equality against `cpol:requiresState`. |
| `cpol:failClosed` | Boolean | 1 | MUST be `true`. |
| `cpol:classification` | Text | 0..1 | Handling class, e.g. `public-test-data`. Informative. |
| `cpol:custodian` | Text or Organization | 0..1 | Who is accountable for the data. Informative. |
| `cpol:retentionDays` | Integer | 0..1 | Declared retention horizon. Informative in 0.1.0; not evaluated. |
| `cpol:rationale` | Text | 0..1 | Why the policy is what it is. Carried into decision records. |
| `cpol:permissibleAction` | `cpol:Action` | 1..n | The operations this dataset admits. |
| `cpol:decisionRecord` | `cr:FileObject` `@id` | 0..1 | Where decision artifacts for this dataset are written. |

An empty `cpol:permissibleAction` list is not conforming. A dataset that admits
nothing is expressed by a policy whose actions all require an unreachable state,
which is auditable; an empty list is silence, which is not.

### 5.2 `cpol:Action`

| Term | Range | Card. | Meaning |
|---|---|---|---|
| `cpol:actionName` | Text | 1 | Action identifier, unique within the policy. |
| `cpol:requiresState` | Text | 0..n | States that admit this action. Empty means state is not checked. |
| `cpol:condition` | `cpol:Condition` | 0..n | Conditions on the request context. |
| `cpol:capabilityName` | Text | 0..1 | Overrides the default capability name in section 7. |
| `cpol:description` | Text | 0..1 | Human-readable purpose; becomes the capability description. |

### 5.3 `cpol:Condition` and the closed operator set

| Term | Range | Card. | Meaning |
|---|---|---|---|
| `cpol:conditionName` | Text | 1 | Key looked up in the request context. |
| `cpol:operator` | one of below | 1 | How `expected` is compared to the observed value. |
| `cpol:expected` | JSON | 1 | The operand. |

The operator set is closed at five members:

| Operator | Passes when | Operand |
|---|---|---|
| `cpol:min` | `observed >= expected`, both numeric | number |
| `cpol:max` | `observed <= expected`, both numeric | number |
| `cpol:in` | `observed` is a member of `expected` | array |
| `cpol:equals` | `observed == expected` | any JSON scalar |
| `cpol:present` | `(observed is not null) == expected` | boolean |

Numeric comparison is on the numeric value; a non-numeric observed value under
`cpol:min`/`cpol:max` does not pass. There is no coercion of `cpol:equals`, and
no ordering on strings. Extending this set is a version bump, not a profile
extension: an evaluator MUST refuse an operator it does not implement, so a
sixth operator silently added to a document turns PERMIT into REFUSE rather
than into an unchecked pass.

## 6. Evaluation

### 6.1 The admission question

Given a conforming document, an action name, and a request context (a flat
mapping of condition names to observed values), an evaluator returns one
verdict: `PERMIT` or `REFUSE`. Evaluation is prospective -- the answer is
produced before the operation runs, and a `REFUSE` means the operation does not
run at all.

Order is fixed, because the refusal class depends on it:

1. If the policy declares no action of that name, `REFUSE / UNDECLARED_ACTION`.
2. Else if the action has a non-empty `cpol:requiresState` and `cpol:state` is
   not a member, `REFUSE / STATE_PRECONDITION`.
3. Else evaluate **every** condition (not short-circuited) and if any fails,
   `REFUSE / CONDITION_VIOLATED`.
4. Else `PERMIT`.

Step 3 evaluates all conditions even after the first failure. A record that
lists only the failing rule cannot demonstrate that the others were checked,
and demonstrating that is most of the point of the record.

### 6.2 Fail-closed

An evaluator MUST refuse, with class `CONDITION_VIOLATED` and a reason naming
the offending term, when it encounters:

- an operator outside section 5.3;
- a `cpol:Condition` missing `cpol:conditionName`, `cpol:operator`, or
  `cpol:expected`;
- a `cpol:Policy` with `cpol:failClosed` absent or not `true`.

It MUST NOT treat any of these as a document error that skips the check, and it
MUST NOT fall back to the underlying Croissant document's permissions, because
Croissant has none.

Refusal classes still follow the order in 6.1: an undeclared action refuses as
`UNDECLARED_ACTION`, and a failed state precondition refuses as
`STATE_PRECONDITION`, before any condition is looked at. The requirement here
is that these cases refuse, not that they all refuse with the same class. The
one exception is a policy that does not declare `cpol:failClosed`: the defect
is the document's rather than the request's, so an evaluator MUST refuse every
declared action on it with `CONDITION_VIOLATED` naming `cpol:failClosed`,
without letting a state precondition pre-empt the reason and report something
less specific than the truth.

### 6.3 Decision records

Every evaluation, permit or refuse, MUST be able to produce a record carrying at
minimum: verdict, dataset identity, **descriptor version**, action, observed
state, refusal class (null on permit), reasons, and the full list of conditions
checked with expected, observed, and pass/fail for each.

Descriptor version is mandatory because a decision is only reproducible against
the policy that produced it, and policies change.

## 7. Capability projection

A conforming document projects deterministically onto a set of callable
capabilities -- the form an agent consumes rather than the document itself. For
each `cpol:Action`:

- **name**: `cpol:capabilityName` if present, else `{dataset}.{actionName}` with
  the dataset name slugified.
- **description**: `cpol:description` if present, else a generated sentence
  naming the action, the dataset, and the required states.
- **input schema**: one required property per `cpol:Condition`, typed and
  constrained from its operator -- `cpol:min`/`cpol:max` become a `number` with
  `minimum`/`maximum`, `cpol:in` becomes an `enum`, `cpol:equals` becomes a
  `const`, `cpol:present` becomes a required-or-forbidden property.

Two consequences are intended. First, the constraint appears in the capability's
schema, so a well-behaved caller can avoid a refusal instead of discovering it.
Second, the schema is derived, not authored, so it cannot drift from the policy
the gate actually enforces -- the same document produces both.

The intended consumer is an agent tool registry. The projection is emitted in the
shape a Model Context Protocol tool list expects, so a registry that already
inventories agent tools can ingest data-side policy without a human transcribing
it. That transcription is the failure mode this section exists to remove: a
registry entry authored by hand drifts from the policy silently, one derived from
the document cannot.

Projection is a *description* of what will be checked, never a substitute for
checking it. A caller that satisfies the projected schema MUST still be gated.

## 8. What this profile does not do in 0.1.0

- **No identity or entitlement.** Conditions are evaluated against a context;
  who supplied that context, and whether they were entitled to, is out of scope.
  Binding this to a caller identity is the obvious next version, and the point at
  which this stops being expressible as a static document.

  This omission is deliberate rather than pending. A rule about the caller does
  not belong in a document that travels with the data, so the caller-side
  authority stays outside the profile and is composed with it instead; see
  `croissant_policy/caller.py` and `croissant_policy/conjunction.py`. Measured
  over the same request space, the two authorities refuse different things in
  both directions, and each has a class of rule the other cannot express -- the
  dataset's
  lifecycle state on one side, the caller's entitlement and assurance on the
  other. Merging them into one document would not remove that; it would hide
  which authority decided.
- **No obligations or duties.** ODRL-style consequences ("on use, notify X") are
  absent. Only permission is modelled.
- **No temporal or stateful conditions.** No windows, quotas, or counters.
  Everything is decidable from the document plus the context at one instant.
- **No drift or relearning semantics.** A policy that reacts to the dataset
  changing meaning is a separate concern and a separate document.
- **No retention enforcement.** `cpol:retentionDays` is carried, not applied.

Each omission is a place where the honest answer is that the mechanism is not
here, rather than a place where the profile quietly permits.

## 9. Validation status

**Checked with `mlcroissant` 1.1.0 against Croissant 1.0.** All three documents
in `examples/` load, with zero errors. The `@context` is byte-identical to the
one MLCommons' own generator produces for version 1.0.

Getting there corrected three real defects, which is the argument for doing it
rather than asserting clause 1 was satisfied:

1. The hand-written `@context` carried four terms it should not have --
   `arrayShape` and `isArray`, which are Croissant 1.1, and `dataBiases` and
   `dataCollection`, which are not Croissant terms at any version -- and was
   missing `equivalentProperty` and `samplingRate`. `mlcroissant` reported the
   context as non-standard. It is now generated from MLCommons' own function
   rather than transcribed.
2. The profile was writing provenance of collection to a bare `dataCollection`
   key, which under `@vocab` resolved to a schema.org term that does not exist.
   RAI terms are reached through the `rai:` prefix; it is now
   `rai:dataCollection`.
3. A `cr:FileObject` must carry `md5` or `sha256`. The decision-record node had
   neither. The emitter now computes a SHA-256 from the file, and a directory of
   decision logs becomes a `cr:FileSet`, which is a pattern and needs no
   checksum. A path that does not exist is refused rather than described with an
   invented digest.

Two warnings remain on the examples, both for *recommended* properties:
`citeAs` and `datePublished`. Both are supported as emitter overrides and
neither is invented for datasets whose citation and publication date are not
known.

Clause 1 is therefore verified for the documents in `examples/`. Note the
distinction that remains: this repository's own validator checks the profile's
conformance clauses structurally and does not parse JSON-LD.
`tools/validate_mlcroissant.py` is what checks Croissant validity, it is a
separate step because `mlcroissant` pulls in pandas, numpy, scipy and rdflib,
and the profile itself remains standard library only.

Everything in sections 5 through 7 is exercised by the test suite against the
reference evaluator.
