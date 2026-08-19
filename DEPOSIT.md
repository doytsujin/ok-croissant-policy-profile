# Zenodo deposit sheet — v0.1.5

Field values for Zenodo's upload form. The GitHub integration does not work for
this repository, so the deposit is made by hand; see [RELEASING.md](RELEASING.md)
for why and for the surrounding order.

**File to attach:** `ok-croissant-policy-profile-v0.1.5.tar.gz`, built by
`git archive` from the tag — not a working-tree zip, which would carry whatever
happened to be uncommitted.

| Field | Value |
|---|---|
| Resource type | Software |
| Title | A Policy Profile for Croissant: Refusal as a Property of the Dataset |
| Creator | Chernov, Alexander |
| ORCID | 0009-0007-3198-2712 |
| Publication date | 2026-08-18 |
| Version | 0.1.5 |
| Licence | Apache License 2.0 |
| Language | English |

**Description** (paste as written):

> An additive policy profile for Croissant dataset descriptors. A dataset
> declares the operations it admits and the conditions under which it admits
> them, so a gate in front of the data can permit or refuse a request from the
> descriptor alone and leave a record of what was checked. Includes a reference
> implementation, a conformance validator, an MCP capability projection, a
> measured overhead study, a caller-side/data-side precedence experiment, and a
> tool for re-deciding a stored decision archive against a later policy.

**Keywords:** croissant, dataset descriptors, admission control, data
governance, provenance, agent governance

**Related identifiers:**

| Identifier | Relation |
|---|---|
| `https://github.com/doytsujin/ok-croissant-policy-profile/tree/v0.1.5` | is supplement to |
| `https://w3id.org/croissant-policy/0.1.0` | is documented by |

The first relation is the one Zenodo's own GitHub integration sets, so a manual
deposit reads the same way as an automated one. Leave communities and grants
empty — neither is in use.

## Keep this in step

The version, date and description here are duplicated from `CITATION.cff` on
purpose: the form is filled from this file, and a sheet that drifts from the
tag deposits the wrong metadata permanently. Both are on the pre-tag checklist.
