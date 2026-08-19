# Zenodo deposit sheet — v0.1.5

**Deposited 2026-08-18.** Concept DOI `10.5281/zenodo.22005283` (cite this one),
version DOI for v0.1.5 `10.5281/zenodo.22005284`.

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

## What the form does when you do not look

Every field below was on this sheet and four of them still came out wrong on
the first deposit, because Zenodo's defaults apply to anything left untouched:

| Field | What the form did | Why it matters |
|---|---|---|
| Licence | defaulted to **CC-BY-4.0** | the record then contradicts the Apache-2.0 `LICENSE` inside its own tarball |
| Version | left empty | nothing on the record says which release it is |
| Publication date | stamped **UTC today** | a late-evening deposit in Toronto dates a day ahead of the tag |
| Related identifiers | not carried over | the record stands unlinked to the repository and the profile IRI |

So the last step of a deposit is to re-read the published record against this
table. Metadata stays editable after publication — only the files are frozen —
so a field caught late is a form edit, not a new version.

On the date: `CITATION.cff` carries the tag's local date and Zenodo thinks in
UTC, so the two can legitimately differ by a day. Set the record to match the
tag rather than letting the default stand, and they stay comparable.

## Keep this in step

The version, date and description here are duplicated from `CITATION.cff` on
purpose: the form is filled from this file, and a sheet that drifts from the
tag deposits the wrong metadata permanently. Both are on the pre-tag checklist.
