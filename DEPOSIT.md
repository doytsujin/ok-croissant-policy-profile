# Zenodo deposit sheet — v0.2.0

**Deposited 2026-08-20.** Record `22032756`, version DOI
`10.5281/zenodo.22032756`, under concept `10.5281/zenodo.22018156` — the same
concept as v0.1.6, which is the point. Read back through the API afterwards:
two records, one concept, no second concept minted.

**A new version of an existing record**, not a new record. The concept is
`10.5281/zenodo.22018156`, created by the v0.1.6 deposit on 2026-08-19, and it
is the only concept this software will ever have. Deposit through
`POST /api/deposit/depositions/<newest-id>/actions/newversion` so the concept
DOI keeps resolving forward.

**Do not cut a GitHub release.** The webhook is disabled and must stay that way.
It works — that is the problem. It mints a concept DOI of its own, which is how
one piece of software briefly had two. See [RELEASING.md](RELEASING.md).

**File to attach:** `ok-croissant-policy-profile-v0.2.0.tar.gz`, built by
`git archive` from the tag rather than from the working tree.

| Field | Value |
|---|---|
| Resource type | Software |
| Title | A Policy Profile for Croissant: Refusal as a Property of the Dataset |
| Creator | Chernov, Alexander |
| ORCID | 0009-0007-3198-2712 |
| Publication date | 2026-08-20 |
| Version | 0.2.0 |
| Licence | Apache License 2.0 |
| Language | English |

**Description** (paste as written):

> An additive policy profile for Croissant dataset descriptors. A dataset
> declares the operations it admits and the conditions under which it admits
> them, so a gate in front of the data can permit or refuse a request from the
> descriptor alone and leave a record of what was checked. The policy is
> expressible in two decision-equivalent carriers: the profile's own terms, and
> an ODRL policy in the sc:usageInfo slot Croissant 1.1 provides. Includes a
> reference implementation, a conformance validator, SHACL shapes for both
> carriers, a PROF description of the profile's own resources, an MCP capability
> projection, a conformance corpus generated from the closed grammar, a measured
> overhead study, a caller-side/data-side precedence experiment, and a tool for
> re-deciding a stored decision archive against a later policy.

**Keywords:** croissant, dataset descriptors, admission control, data
governance, provenance, agent governance, odrl, shacl, json-ld

**Related identifiers:**

| Identifier | Relation |
|---|---|
| `https://github.com/doytsujin/ok-croissant-policy-profile/tree/v0.2.0` | is supplement to |
| `https://w3id.org/croissant-policy/0.1.0` | is documented by |

## Why 0.2.0 rather than 0.1.7

The vocabulary is unchanged, so the profile IRI stays at `0.1.0` and documents
already emitted remain conforming. What changed is **evaluation behaviour**, in
three ways that alter what a gate decides:

- Conformance clause 2 is enforced rather than merely validated. A document that
  carries the policy terms and omits the profile IRI from `conformsTo` used to
  be decided; it is now refused.
- Operands are type-checked at translation. `cpol:in` with a scalar operand used
  to raise, and with a string operand used to match substrings — so
  `{"in": "illumina"}` silently permitted `"illu"`.
- Equality is JSON\'s rather than the implementation language\'s. `bool` is a
  subclass of `int` in Python, so `{"equals": true}` used to be satisfied by an
  observed `1`.

Two of those three closed a path that **admitted a request the policy did not
describe**. A patch bump would understate that.

## What is new in 0.2.0

- An ODRL carrier (`croissant_policy/odrl.py`) and its equivalence test: the
  same policy as an `odrl:Set` in `sc:usageInfo`, decided identically record for
  record. Four of the five operators are ODRL core operators.
- SHACL shapes for both carriers, served at the namespace, with a validator that
  selects the graph by the profile a document claims.
- A PROF description (`docs/ns/0.1.0/profile.jsonld`) naming every artifact and
  its role, so a consumer can act on a `conformsTo` claim without reading a paper.
- A conformance corpus generated from the closed grammar: 22 valid and 13 defect
  cases, 57 stored documents, covering every operator, refusal class and
  conformance clause in both carriers.
- `results/conformance.json` and `results/shacl.json`.

## Upstream

The `conformsTo` defect this work surfaced in Croissant itself — profile
identifiers expand to language-tagged literals rather than IRIs — is reported as
[mlcommons/croissant#1047](https://github.com/mlcommons/croissant/issues/1047).
